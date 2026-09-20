"""编排：构集 → 验证 → (大网格 → 聚焦格) → 统计。

§8 最低可运行切片：python run_pipeline.py --mode=mini
  10 题玩具管线，零第三方依赖，串起 load_raw→build_gold→proposal→validate→replace
  →⑥自校验→四臂→EM→DiD 干跑表（T1–T6）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许直接 python run_pipeline.py 运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config, manifest as mf
from .schemas import FourArmRow, Substituted, to_jsonable
from .data.load_raw import load_dpr_file, load_hotpot_file
from .data.build_gold import build_gold
from .data.make_subset import deterministic_sample
from .data.value_pool import ValuePool, corpus_cooccurrence_factory
from .construct.proposal import RuleBasedProposer, LLMProposer
from .construct.replace import build_substituted, edited_paragraphs, write_jsonl
from .construct import gate as gates
from .retrieval.bm25_distractor import DistractorBM25
from .generation.model import StubGenerator, HFGenerator, RemoteVLLMGenerator, vram_estimate
from .generation.arm import ArmConfig, run_four_arms, run_oracle_pair
from .tables import t1_audit, t2_retrieval, t3_gates, t4_did, t5_power, t6_ledger

HERE = Path(__file__).parent
TOY = HERE / "toy_data"

# 玩具数据的"参数记忆"设定：6 题被模型记住，其中 1 题为强记忆（cb_sub 仍答旧值，演示②检出）
TOY_MEMORIZED = {"nq-0", "nq-2", "trivia-1", "trivia-2", "hotpot-0", "hotpot-1"}
TOY_STRONG = {"hotpot-1"}


def _config_key(acfg) -> str:
    """R3-A：把当前运行配置压成可读键，写入 manifest 的 run.config_key。"""
    return f"gran={acfg.granularity},bud={acfg.budget},k={acfg.k},rerank={acfg.rerank}"


def _dataset_counts(questions) -> list[dict]:
    """R3-A：按实际进入本轮的题数分组计数（按 q.dataset），写入 manifest 的 run.datasets。
    不能用 config.MINI_N/PILOT_N 写死——mini 的 nq/trivia/hotpot 各题数并不相等，
    且 pilot 是 deterministic_sample 后的抽样集（各数据集题数也不保证等比）。"""
    counts: dict[str, int] = {}
    for q in questions:
        counts[q.dataset] = counts.get(q.dataset, 0) + 1
    return [dict(name=d, n=n) for d, n in sorted(counts.items())]


def _t3_verdicts(t3: dict) -> dict[str, str]:
    """R3-A：把 T3 实际判出的闸门出口 GO/REVISE/ABANDON/INSUFFICIENT 快照进 manifest。"""
    out = {}
    for model, d in t3.items():
        for name, gate in d.items():
            out[f"{model}::{name}"] = str(getattr(gate, "verdict", None))
    return out


def load_mini_questions():
    qs = []
    qs += load_dpr_file(str(TOY / "nq_toy.json"), "nq")
    qs += load_dpr_file(str(TOY / "trivia_toy.json"), "trivia")
    qs += load_hotpot_file(str(TOY / "hotpot_toy.json"))
    assert len(qs) == config.MINI_N, f"mini 应为 {config.MINI_N} 题，实际 {len(qs)}"
    return qs


def _pp_retrieval_eligible(g1, policy: str) -> bool:
    """Per-protocol 是否把 retrieval hit 当纳入条件。

    C 线的每题候选池近似 oracle，沿用严格 pair-hit；B 线共享语料则故意让
    gold 在小 k 缺席，双 miss 是配置处理结果而非构集失效，故只要求结构有效。
    """
    if policy == "require_pair_hit":
        return bool(g1.passed)
    if policy == "structural_only":
        return True
    raise ValueError(f"未知 pp_retrieval_policy: {policy}")


def run_set(questions, generator, model_name, acfg, out_dir: Path, label: str,
            do_oracle: bool = True, proposer=None, retriever_cls=DistractorBM25,
            inspect_n: int = 0, retriever_builder=None,
            pp_retrieval_policy: str = "require_pair_hit",
            t2_retention_mode: str = "joint", record_retrieval_rows: bool = False):
    # C18 扩展（B 线真实检索）：retriever_builder(q, subs, gold, acfg) 若给定，替代默认
    # "每题自家候选段上 DistractorBM25" 的检索来源，返回
    #   (ctx_paras_orig, ctx_paras_sub, hits_o, hits_s, rr_o, rr_s, retriever_label)
    # 其中 ctx_paras_* 是喂给四臂上下文的段落列表（hit doc_id 必须 ∈ 它）。缺省 None =
    # C 线原路径，hook 分支结构不变；proposal/gold/substitution/闭卷/gates③④ 一律不受影响。
    # `structural_only` 是 B 线专用：低-k gold miss 是处理条件，不能污染 PP 分母。
    if pp_retrieval_policy not in ("require_pair_hit", "structural_only"):
        raise ValueError(f"未知 pp_retrieval_policy: {pp_retrieval_policy}")
    if t2_retention_mode not in ("joint", "conditional"):
        raise ValueError(f"未知 t2_retention_mode: {t2_retention_mode}")
    # 值池：从全集其他题借值；0 共现预筛在全语料上
    all_texts = [p.text for q in questions for p in (q.paragraphs or [])]
    pool = ValuePool(questions, corpus_cooccurrence_factory(all_texts))
    if proposer is None:
        proposer = RuleBasedProposer(pool)

    all_subs: list[Substituted] = []
    failures: list[tuple[str, str]] = []
    t2_records: list[dict] = []
    retrieval_rows: list[dict] = []  # B 线可选逐题 audit；C 线默认不改产物结构
    rows_by_model: dict[str, list[FourArmRow]] = {model_name: []}
    inspect_records: list[dict] = []  # 目检：dump 若干题的原样生成（--inspect 触发）
    oracle_orig, oracle_sub, oracle_cls = [], [], []
    oracle_rows: list[dict] = []  # Phase C 诊断（C8）：逐题 oracle 原始输出 + 真冲突标记
    cb_orig_correct, cb_sub_cls = [], []
    old_answer_of = {q.id: q.answers[0] for q in questions}

    for q in questions:
        gold = build_gold(q)
        if not gold.passages:
            failures.append((q.id, "build_gold: 无含金证据段"))
            continue
        outcome = proposer.propose(q, gold)
        if outcome.status == "failed":
            failures.append((q.id, outcome.reason))
            continue

        subs = []
        for prop in outcome.proposals:
            src = next((p for p in gold.passages if p.doc_id == prop.passage_doc_id), None)
            if src is None:
                failures.append((q.id, f"proposal 指向未知段 {prop.passage_doc_id}"))
                continue
            try:
                sub = build_substituted(q.id, src, prop, q.answers)
            except ValueError as e:
                failures.append((q.id, str(e)))
                continue
            # ⑤⑥⑦
            sub.gates["5"] = gates.gate5_item(sub)
            sub.gates["6"] = gates.gate6_item(sub)
            co = corpus_cooccurrence_factory(all_texts)(q.text, prop.new)
            sub.gates["7"] = gates.gate7_item(co, human_ok=True)  # mini 人审默认过；真实 20% 双标
            # Gate 5/6 是进入四臂前的构集不变量；不得把失效替换混入 ITT 后再事后报表。
            if not (sub.gates["5"].passed and sub.gates["6"].passed):
                failed = [k for k in ("5", "6") if not sub.gates[k].passed]
                failures.append((q.id, f"结构闸门未过（Gate {','.join(failed)}）"))
                continue
            subs.append(sub)
            all_subs.append(sub)
        if not subs:
            failures.append((q.id, "全部 proposal 校验失败"))
            continue
        # execution-fix: hotpot 题必须有末跳 terminal subs（答案 span 非唯一时 build_substituted 会失败），
        # 否则 c/d 臂无真值 key，arm.py 断言会崩。整题 skip 进 T6，不影响方法学语义。
        if q.dataset == "hotpot" and not any(s.terminal_key for s in subs):
            failures.append((q.id, "末跳 terminal 替换构建失败（答案 span 非唯一/0命中），整题 skip"))
            continue

        gold_doc_ids = {p.doc_id for p in gold.passages}
        sub_paras = edited_paragraphs(q.paragraphs or [], subs)

        # ① 原/替换同口径检索（distractor BM25；开放域传 OpenBM25，接口一致；
        #    B 线经 retriever_builder 换共享语料真检索，见 C18）。
        if retriever_builder is not None:
            (ctx_paras_o, ctx_paras_s, hits_o, hits_s, rr_o, rr_s,
             retriever_label) = retriever_builder(q, subs, gold, acfg)
            g1 = gates.gate1_item(rr_o, rr_s)
            t2_records.append(dict(retriever=retriever_label, dataset=q.dataset,
                                   orig_hit=rr_o.gold_hit(), sub_hit=rr_s.gold_hit()))
            # 四臂配对：上下文 = builder 返回的检索段落（金窗若被召回到则在 ctx 内）
            row, gens, aux = run_four_arms(q, subs, generator, ctx_paras_o, ctx_paras_s,
                                           hits_o, hits_s, acfg, model_name, gold_doc_ids)
        else:
            eng_o = retriever_cls(q.paragraphs or [])
            eng_s = retriever_cls(sub_paras)
            hits_o = eng_o.search(q.text, acfg.k)
            hits_s = eng_s.search(q.text, acfg.k)
            rr_o = eng_o.to_result(q.id, hits_o, gold_doc_ids, acfg.k)
            rr_s = eng_s.to_result(q.id, hits_s, gold_doc_ids, acfg.k)
            g1 = gates.gate1_item(rr_o, rr_s)
            t2_records.append(dict(retriever=f"bm25[{eng_o.backend}]", dataset=q.dataset,
                                   orig_hit=rr_o.gold_hit(), sub_hit=rr_s.gold_hit()))
            # 四臂配对
            row, gens, aux = run_four_arms(q, subs, generator, q.paragraphs or [], sub_paras,
                                           hits_o, hits_s, acfg, model_name, gold_doc_ids)
        structural_ok = all(s.gates["5"].passed and s.gates["6"].passed for s in subs)
        row.passed_gates = bool(structural_ok and _pp_retrieval_eligible(g1, pp_retrieval_policy))
        if record_retrieval_rows:
            def _gold_rank(hits):
                for rank, (doc_id, _score) in enumerate(hits, start=1):
                    if doc_id in gold_doc_ids:
                        return rank
                return None

            retrieval_rows.append(dict(
                question_id=q.id, dataset=q.dataset, retriever=retriever_label
                if retriever_builder is not None else f"bm25[{eng_o.backend}]",
                orig_gold_hit=rr_o.gold_hit(), sub_gold_hit=rr_s.gold_hit(),
                orig_gold_rank=_gold_rank(hits_o), sub_gold_rank=_gold_rank(hits_s),
                orig_hits=[dict(doc_id=d, score=s) for d, s in hits_o],
                sub_hits=[dict(doc_id=d, score=s) for d, s in hits_s],
                ctx_orig_gold_present=aux["ctx_orig"].gold_present,
                ctx_sub_gold_present=aux["ctx_sub"].gold_present,
                ctx_orig_tokens=aux["ctx_orig"].tokens_used,
                ctx_sub_tokens=aux["ctx_sub"].tokens_used,
                passed_gates=row.passed_gates,
            ))
        rows_by_model[model_name].append(row)
        cb_orig_correct.append(bool(row.a))
        cb_sub_cls.append(aux["classes"]["cb_sub"])

        if do_oracle:
            gold_o_text = "\n".join(p.text for p in gold.passages)
            sub_gold = [p for p in sub_paras if p.doc_id in gold_doc_ids]
            gold_s_text = "\n".join(p.text for p in sub_gold)
            ora = run_oracle_pair(q, subs, generator, gold_o_text, gold_s_text,
                                  model_name, acfg)
            oracle_orig.append(ora["em_orig"])
            oracle_sub.append(ora["em_sub"])
            oracle_cls.append(ora["cls_sub"])
            # Phase C 诊断（C8）：逐题 oracle 原始输出 + 真冲突标记落盘，供离线 compliance
            # 拆解（analyze_compliance.py）。纯增量，不参与 a/b/c/d 或任何冻结指标。
            oracle_rows.append(dict(
                question_id=q.id, dataset=q.dataset, question=q.text, gold=q.answers[0],
                answer_type=q.answer_type,  # C11：供单跳按 date/numeric/name 分层的顺从率拆解
                term_key=ora.get("term_key"), term_present=ora.get("term_present"),
                new_aliases=ora.get("new_aliases"), old_aliases=list(q.answers),
                ora_orig=ora["ora_orig"], ora_sub=ora["ora_sub"],
                em_orig=ora["em_orig"], em_sub=ora["em_sub"], cls_sub=ora["cls_sub"],
                arms_raw={g.arm: g.raw_output for g in gens},
                arms_em=dict(a=row.a, b=row.b, c=row.c, d=row.d)))

        # 目检：dump 前 inspect_n 题的原样生成（模型如何答、是否空/复读/只回旧值——排查 1.7B 反常用）。
        if inspect_n and len(inspect_records) < inspect_n:
            arm_raw = {g.arm: g.raw_output for g in gens}
            rec = dict(
                question_id=q.id, dataset=q.dataset, question=q.text,
                gold=q.answers[0], answer_type=q.answer_type,
                gold_passage="\n".join(p.text for p in gold.passages),
                ctx_orig="\n\n".join(t for t in aux["ctx_orig"].texts),
                ctx_sub="\n\n".join(t for t in aux["ctx_sub"].texts),
                arms=arm_raw,
                em=dict(a=row.a, b=row.b, c=row.c, d=row.d),
                classes=aux["classes"],
            )
            if do_oracle:
                rec["ora_orig"] = ora["ora_orig"]
                rec["ora_sub"] = ora["ora_sub"]
            inspect_records.append(rec)

    # ---------- 汇总表 ----------
    t1 = t1_audit.build(all_subs)
    t2 = t2_retrieval.build(t2_records)
    per_model = {model_name: {}}
    is_multi_any = any(q.dataset == "hotpot" for q in questions)
    per_model[model_name]["②塌陷"] = gates.gate2_aggregate(
        cb_orig_correct, cb_sub_cls, is_multi=is_multi_any, model=model_name)
    if oracle_orig:
        per_model[model_name]["③oracle"] = gates.gate3_aggregate(oracle_orig, oracle_sub)
        per_model[model_name]["④顺从"] = gates.gate4_aggregate(oracle_cls, model=model_name)
    t3 = t3_gates.build(per_model)
    t4 = t4_did.build(rows_by_model, B=2000)
    flat_rows = [r for rs in rows_by_model.values() for r in rs]
    t5 = t5_power.build(flat_rows)
    t6 = t6_ledger.build(failures)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(out_dir / f"{label}_substituted.jsonl",
                [dict(question_id=s.question_id, old_key=s.old_key, new_key=s.new_key,
                      old_passage=s.old_passage, new_passage=s.new_passage,
                      terminal_key=s.terminal_key,  # execution-fix: 补回遗漏的 A2 字段
                      proposal=to_jsonable(s.proposal),
                      gates={k: v.__dict__ for k, v in s.gates.items()}) for s in all_subs])
    write_jsonl(out_dir / f"{label}_fourarm.jsonl", [to_jsonable(r) for r in flat_rows])
    # Phase C：逐 run 落一份 metrics.json，把 a/b/c/d + oracle EM + 顺从率固化到产物，
    # 供离线验收核对（避免只信执行方手抄数字）。
    _m = lambda xs: sum(xs) / len(xs) if xs else None
    metrics = dict(
        label=label, model=model_name, config_key=_config_key(acfg), n=len(flat_rows),
        a=_m([r.a for r in flat_rows]), b=_m([r.b for r in flat_rows]),
        c=_m([r.c for r in flat_rows]), d=_m([r.d for r in flat_rows]),
        apparent_gain=_m([r.b for r in flat_rows]) - _m([r.a for r in flat_rows]) if flat_rows else None,
        corrected_gain=_m([r.d for r in flat_rows]) - _m([r.c for r in flat_rows]) if flat_rows else None,
        oracle_em_orig=_m(oracle_orig), oracle_em_sub=_m(oracle_sub) if oracle_sub else None,
        compliance=_m([1 if c == "new" else 0 for c in oracle_cls]) if oracle_cls else None,
    )
    (out_dir / f"{label}_metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8")
    if oracle_rows:
        write_jsonl(out_dir / f"{label}_oracle_rows.jsonl", oracle_rows)
        print(f"[diag] 已写 {len(oracle_rows)} 条 oracle 拆解行 -> "
              f"{out_dir / f'{label}_oracle_rows.jsonl'}")
    if retrieval_rows:
        write_jsonl(out_dir / f"{label}_retrieval_rows.jsonl", retrieval_rows)
        print(f"[retrieval-audit] 已写 {len(retrieval_rows)} 条逐题检索行 -> "
              f"{out_dir / f'{label}_retrieval_rows.jsonl'}")
    if inspect_records:
        write_jsonl(out_dir / f"{label}_inspect.jsonl", inspect_records)
        print(f"[inspect] 已写 {len(inspect_records)} 条生成目检 -> "
              f"{out_dir / f'{label}_inspect.jsonl'}")

    return dict(t1=t1, t2=t2, t2_retention_mode=t2_retention_mode,
                t3=t3, t4=t4, t5=t5, t6=t6, subs=all_subs,
                rows=flat_rows, retrieval_rows=retrieval_rows, model=model_name)


def print_report(res):
    print("=" * 78)
    print(f"  RAG 泄漏校正管线 —— mini 冒烟（模型桩: {res['model']}）")
    print("=" * 78)
    for t in (t1_audit, ):
        print(t.render(res["t1"]))
    print(t2_retrieval.render(res["t2"]))
    print(t3_gates.render(res["t3"]))
    print(t4_did.render(res["t4"]))
    print(t5_power.render(res["t5"]))
    print(t6_ledger.render(res["t6"]))
    print("-" * 78)
    print("说明: 玩具数据故意保留 1 个强记忆项(hotpot-1)，用于演示闸门②检出残留；")
    print("      DiD<0 表示参数记忆压缩了表观开卷增益，方向与研究假设一致。")
    print("=" * 78)


def build_generator(kind: str, model_name: str, bits: int, device: str, vllm_url: str = ""):
    """C1：pilot 真实后端工厂。stub 仅用于接线冒烟；hf 需 GPU+transformers；remote 走 vLLM。"""
    if kind == "stub":
        return StubGenerator(set(), set(), {})
    if kind == "hf":
        return HFGenerator(model_name, bits=bits, device=device)
    if kind == "remote":
        if not vllm_url:
            raise SystemExit("--generator remote 需 --vllm_url")
        return RemoteVLLMGenerator(model_name, base_url=vllm_url)
    raise SystemExit(f"未知 --generator {kind}")


def run_pilot(args, out_dir: Path, acfg) -> int:
    """C1：真实 pilot。抽样 PILOT_N，逐模型出 T1–T6；32B 走 RemoteVLLM。"""
    if not (args.nq and args.trivia and args.hotpot):
        raise SystemExit("pilot 模式需提供 --nq/--trivia/--hotpot 三个数据文件路径")
    questions = (load_dpr_file(args.nq, "nq") + load_dpr_file(args.trivia, "trivia")
                 + load_hotpot_file(args.hotpot))
    # C12：--pilot-n 允许覆盖 config.PILOT_N（round-6 date/numeric 全量切片 n≈449 > 240）。
    # 传 0 或 >= 切片规模时等价于全量跑（deterministic_sample 取 min(n, len)）。
    n_sample = args.pilot_n if args.pilot_n else config.PILOT_N
    questions = deterministic_sample(questions, n_sample, seed=config.RNG_SEED)
    print(f"[pilot] 抽样 {len(questions)} 题；模型={args.models}；生成后端={args.generator}")

    # 8B×4K 量化建议（公式化，真实以压测为准）
    for m in args.models.split(","):
        m = m.strip()
        # Phase C：剥 -Instruct 后缀再判 8B，避免漏建议（--bits 显式指定时本块不触发）
        _base = m[:-len("-Instruct")] if m.endswith("-Instruct") else m
        if _base.endswith("8B") and acfg.budget >= 4096 and args.bits != 4:
            print(f"[建议] {m}×{acfg.budget} 在 8GB 卡上请用 --bits 4（估算："
                  f"{vram_estimate(8, args.bits, acfg.budget)['total_gb']}GB）")

    for model_name in [m.strip() for m in args.models.split(",") if m.strip()]:
        kind = "remote" if model_name == config.MODEL_32B and args.generator == "hf" else args.generator
        gen = build_generator(kind, model_name, args.bits, args.device, args.vllm_url)
        all_texts = [p.text for q in questions for p in (q.paragraphs or [])]
        pool = ValuePool(questions, corpus_cooccurrence_factory(all_texts))
        proposer = (LLMProposer(lambda pr: gen.generate(pr, None), pool)
                    if args.proposer == "llm" else RuleBasedProposer(pool))
        label = f"pilot_{model_name.replace('/', '_')}"
        res = run_set(questions, gen, model_name, acfg, out_dir, label,
                      proposer=proposer, inspect_n=args.inspect)
        print(f"\n########## {model_name} ##########")
        print(t1_audit.render(res["t1"])); print(t2_retrieval.render(res["t2"]))
        print(t3_gates.render(res["t3"])); print(t4_did.render(res["t4"]))
        print(t5_power.render(res["t5"])); print(t6_ledger.render(res["t6"]))
        (out_dir / f"{label}_summary.txt").write_text(
            "\n".join([t1_audit.render(res["t1"]), t2_retrieval.render(res["t2"]),
                       t3_gates.render(res["t3"]), t4_did.render(res["t4"]),
                       t5_power.render(res["t5"]), t6_ledger.render(res["t6"])]),
            encoding="utf-8")
        m = mf.build_manifest(
            HERE, "pilot", label,
            data_paths=dict(nq=args.nq, trivia=args.trivia, hotpot=args.hotpot),
            models=[model_name], config_key=_config_key(acfg),
            gate_verdicts=_t3_verdicts(res["t3"]),
            datasets=_dataset_counts(questions))
        print(f"[R3-A] 已写可复现性 manifest -> {mf.write_manifest(out_dir, label, m)}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="RAG leak-correction pipeline")
    ap.add_argument("--mode", choices=["mini", "pilot", "grid"], default="mini")
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--granularity", default="paragraph", choices=config.GRANULARITIES)
    ap.add_argument("--budget", type=int, default=4096, choices=config.BUDGETS)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--nq", default=""); ap.add_argument("--trivia", default="")
    ap.add_argument("--hotpot", default="")
    # C1 pilot 真实后端参数
    ap.add_argument("--generator", choices=["stub", "hf", "remote"], default="stub")
    ap.add_argument("--proposer", choices=["rule", "llm"], default="rule")
    ap.add_argument("--models", default=f"{config.MODELS[0]},{config.MODELS[1]}")
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--vllm_url", default="")
    ap.add_argument("--inspect", type=int, default=0,
                    help="pilot 时 dump 前 N 题的原样生成到 *_inspect.jsonl（第三轮目检用；0=关）")
    ap.add_argument("--pilot-n", type=int, default=None,
                    help="覆盖 config.PILOT_N(=240) 的抽样规模（round-6 date/numeric 全量切片用）")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    acfg = ArmConfig(args.granularity, args.budget, args.k, rerank=False)

    if args.mode == "mini":
        questions = load_mini_questions()
        gen = StubGenerator(TOY_MEMORIZED, TOY_STRONG,
                            {q.id: q.answers[0] for q in questions})
        res = run_set(questions, gen, "stub(qwen-sim)", acfg, out_dir, "mini")
        m = mf.build_manifest(
            HERE, "mini", "mini",
            data_paths=dict(nq=str(TOY / "nq_toy.json"), trivia=str(TOY / "trivia_toy.json"),
                            hotpot=str(TOY / "hotpot_toy.json")),
            models=["stub(qwen-sim)"], config_key=_config_key(acfg),
            gate_verdicts=_t3_verdicts(res["t3"]),
            datasets=_dataset_counts(questions))
        print(f"[R3-A] 已写可复现性 manifest -> {mf.write_manifest(out_dir, 'mini', m)}")
        print_report(res)
        (out_dir / "mini_summary.txt").write_text(
            "\n".join([t1_audit.render(res["t1"]), t2_retrieval.render(res["t2"]),
                       t3_gates.render(res["t3"]), t4_did.render(res["t4"]),
                       t5_power.render(res["t5"]), t6_ledger.render(res["t6"])]),
            encoding="utf-8")
        return 0

    if args.mode == "pilot":
        return run_pilot(args, out_dir, acfg)

    # grid：聚焦格调度器（规模×预算），真正循环各格跑 run_set（第四轮执行）。
    # 懒加载 grid 模块（grid.py 顶部 import 本模块，避免循环导入）。
    if args.generator not in ("hf",):
        # 32B/remote 本轮排除；stub 仅供 python -m rag_leak.grid --backend stub 接线冒烟。
        raise SystemExit("--mode=grid 暂只支持 --generator hf（32B/remote 本轮排除；stub 禁止，见 README）。")
    from . import grid as _grid
    grid_argv = ["--nq", args.nq, "--trivia", args.trivia, "--hotpot", args.hotpot,
                 "--out", str(out_dir), "--backend", args.generator,
                 "--proposer", args.proposer, "--models", args.models,
                 "--granularity", args.granularity, "--k", str(args.k),
                 "--device", args.device]
    return _grid.main(grid_argv)


if __name__ == "__main__":
    sys.exit(main())
