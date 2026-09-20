"""B 线配对复评：共享语料 k 轴、v3 raw 重算、结构性纳入与正式 B1 决策。

本工具只读既有 run 的 oracle/fourarm/substituted artifacts；不会覆盖原 manifest、
metrics 或 JSONL。它把历史 ITT 与 Gate 5/6/7 全过的结构有效集合并列呈现，并按
question_id 配对 k=1/k=5，避免把两个独立点估当作配置比较。

示例：
  python -m rag_leak.analyze_bline --k1-dir rag_leak/out_b8_recall_k1 \
      --k5-dir rag_leak/out_b8_recall_k5 --trivia data/trivia_dn.json \
      --corpus data/trivia-dev.json --out rag_leak/out_b8_recall_analysis.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .data.build_gold import build_gold
from .data.load_raw import load_dpr_file
from .generation.arm import ArmConfig, build_contexts
from .offline_rescore import rescore_row
from .run_bline import load_corpus, make_bline_builder
from .schemas import FourArmRow
from .stats.decision import gain_bootstrap_replicates, judge_sensitive, ranking_flip_probability
from .stats.did import apparent_gain, corrected_gain, did_mean, masking_magnitude, paired_bootstrap


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _one(dir_path: Path, suffix: str) -> Path:
    matches = sorted(dir_path.glob(f"*{suffix}"))
    if len(matches) != 1:
        raise ValueError(f"{dir_path}: 需要恰好一个 *{suffix}，实际 {matches}")
    return matches[0]


def _load_run(dir_path: Path, key: str) -> dict:
    """加载并交叉核对一个 B-line run；输出仍完全只读。"""
    oracle_path = _one(dir_path, "_oracle_rows.jsonl")
    fourarm_path = _one(dir_path, "_fourarm.jsonl")
    sub_path = _one(dir_path, "_substituted.jsonl")
    oracle = _read_jsonl(oracle_path)
    fourarm = _read_jsonl(fourarm_path)
    subs = _read_jsonl(sub_path)
    o_by_id = {r["question_id"]: r for r in oracle}
    f_by_id = {r["question_id"]: r for r in fourarm}
    s_by_id = {r["question_id"]: r for r in subs}
    if len(o_by_id) != len(oracle) or len(f_by_id) != len(fourarm) or len(s_by_id) != len(subs):
        raise ValueError(f"{dir_path}: question_id 存在重复行")
    if set(o_by_id) != set(f_by_id) or set(o_by_id) != set(s_by_id):
        raise ValueError(f"{dir_path}: oracle/fourarm/substituted 的 question_id 集不一致")
    # 对账 v2 落盘 a/b/c/d；若不一致，拒绝给出任何 B-line 结论。
    for qid, o in o_by_id.items():
        expected = o.get("arms_em") or {}
        actual = f_by_id[qid]
        if any(int(actual[k]) != int(expected[k]) for k in ("a", "b", "c", "d")):
            raise ValueError(f"{dir_path}/{qid}: fourarm 与 oracle_rows v2 EM 不一致")
    return dict(key=key, directory=str(dir_path), oracle=o_by_id, fourarm=f_by_id,
                subs=s_by_id, paths=dict(oracle=str(oracle_path), fourarm=str(fourarm_path),
                                         substituted=str(sub_path)))


def _structural_ok(sub: dict) -> bool:
    """历史 run 的主审计条件：Gate 5/6/7 均显式 pass。"""
    gates = sub.get("gates") or {}
    return all((gates.get(k) or {}).get("passed") is True for k in ("5", "6", "7"))


def _objects(run: dict, ids: list[str]) -> list[FourArmRow]:
    out = []
    for qid in ids:
        row = run["oracle"][qid]
        s = rescore_row(row)["v3"]
        out.append(FourArmRow(qid, "B-line", run["key"],
                               a=s["cb_orig"], b=s["open_orig"],
                               c=s["cb_sub"], d=s["open_sub"], passed_gates=True))
    return out


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else float("nan")


def _summary(rows: list[FourArmRow], B: int) -> dict:
    did, did_ci, _ = paired_bootstrap(rows, did_mean, B=B)
    cor, cor_ci, _ = paired_bootstrap(rows, corrected_gain, B=B)
    return dict(
        n=len(rows),
        a=_mean([r.a for r in rows]), b=_mean([r.b for r in rows]),
        c=_mean([r.c for r in rows]), d=_mean([r.d for r in rows]),
        apparent_gain=apparent_gain(rows), corrected_gain=cor, corrected_ci=list(cor_ci),
        did=did, did_ci=list(did_ci), masking=masking_magnitude(rows),
    )


def _scalar_bootstrap(values: list[float], B: int) -> dict:
    """复用 paired_bootstrap 的抽题实现来为 k5-k1 的逐题配对差给 CI。"""
    rows = [SimpleNamespace(value=v) for v in values]
    stat = lambda rs: _mean([r.value for r in rs])
    point, ci, _ = paired_bootstrap(rows, stat, B=B)
    pos = sum(v > 0 for v in values)
    neg = sum(v < 0 for v in values)
    # 两侧 exact sign test；零差剔除，报告的是诊断而非 B1 审核规则。
    n = pos + neg
    tail = min(pos, neg)
    sign_p = min(1.0, 2 * sum(math.comb(n, i) for i in range(tail + 1)) / (2 ** n)) if n else 1.0
    return dict(mean=point, ci=list(ci), positive=pos, negative=neg, zero=len(values) - n,
                sign_test_two_sided=sign_p)


def _paired_report(k1_rows: list[FourArmRow], k5_rows: list[FourArmRow], B: int) -> dict:
    by1 = {r.question_id: r for r in k1_rows}
    by5 = {r.question_id: r for r in k5_rows}
    if set(by1) != set(by5):
        raise ValueError("paired report 的两个配置 question_id 不一致")
    # 所有差值均按 k=5 - k=1；masking = -DiD。
    fields = {
        "delta_apparent_k5_minus_k1": [by5[q].apparent_gain - by1[q].apparent_gain for q in by1],
        "delta_corrected_k5_minus_k1": [by5[q].corrected_gain - by1[q].corrected_gain for q in by1],
        "delta_did_k5_minus_k1": [by5[q].did - by1[q].did for q in by1],
        "delta_masking_k5_minus_k1": [(-by5[q].did) - (-by1[q].did) for q in by1],
    }
    return {name: _scalar_bootstrap(values, B) for name, values in fields.items()}


def _formal_b1(k1_rows: list[FourArmRow], k5_rows: list[FourArmRow], B: int) -> dict:
    """严格复用项目既有 B1 utilities；不要用 DiD CI 替代 corrected-gain CI。"""
    cfg = {"k=1": k1_rows, "k=5": k5_rows}
    app = gain_bootstrap_replicates(cfg, "apparent_gain", B=B)
    cor = gain_bootstrap_replicates(cfg, "corrected_gain", B=B)
    p_flip, app_best, cor_best = ranking_flip_probability(app, cor)
    _, app_ci, _ = paired_bootstrap(cfg[app_best], corrected_gain, B=B)
    _, cor_ci, _ = paired_bootstrap(cfg[cor_best], corrected_gain, B=B)
    verdict = judge_sensitive(p_flip, app_ci, cor_ci)
    return dict(apparent_best=app_best, corrected_best=cor_best,
                corrected_ci_apparent_best=list(app_ci), corrected_ci_corrected_best=list(cor_ci),
                **verdict)


def _reconstruct_retrieval(ids: list[str], run1: dict, run5: dict,
                           trivia_path: str, corpus_path: str, budget: int,
                           granularity: str) -> list[dict]:
    """只读重建每题两个 k 的 BM25 / injection 状态；旧 run 没有逐题 retrieval JSONL 时用。"""
    questions = {q.id: q for q in load_dpr_file(trivia_path, "trivia")}
    paras, toks, norms = load_corpus(corpus_path)
    builder = make_bline_builder(paras, toks, norms)
    out = []
    for qid in ids:
        q = questions.get(qid)
        if q is None:
            raise ValueError(f"{qid}: 不在 --trivia 中，无法重建 retrieval")
        gold = build_gold(q)
        if len(gold.passages) != 1:
            raise ValueError(f"{qid}: 重建时并非单金段")
        row = {"question_id": qid}
        for name, k, run in (("k1", 1, run1), ("k5", 5, run5)):
            sub = run["subs"][qid]
            # B builder 只读取 old/new passage；保留显式 namespace 避免把落盘 dict 当 dataclass。
            sub_obj = SimpleNamespace(old_passage=sub["old_passage"], new_passage=sub["new_passage"])
            acfg = ArmConfig(granularity, budget, k, rerank=False)
            ctx_o, ctx_s, hits_o, hits_s, rr_o, rr_s, _ = builder(q, [sub_obj], gold, acfg)
            cb_o, cb_s, _, _ = build_contexts(q, ctx_o, ctx_s, hits_o, hits_s, acfg,
                                               {p.doc_id for p in gold.passages})
            gold_id = gold.passages[0].doc_id
            rank = lambda hits: next((i for i, (d, _s) in enumerate(hits, start=1)
                                      if d == gold_id), None)
            row[name] = dict(
                orig_gold_hit=rr_o.gold_hit(), sub_gold_hit=rr_s.gold_hit(),
                orig_gold_rank=rank(hits_o), sub_gold_rank=rank(hits_s),
                ctx_orig_gold_present=cb_o.gold_present, ctx_sub_gold_present=cb_s.gold_present,
                ctx_orig_tokens=cb_o.tokens_used, ctx_sub_tokens=cb_s.tokens_used,
                orig_hit_doc_ids=[d for d, _ in hits_o], sub_hit_doc_ids=[d for d, _ in hits_s],
            )
        # 从 raw 重评后的 d 转移，便于检查“证据进入但 d 变差”的可疑题。
        e1, e5 = rescore_row(run1["oracle"][qid])["v3"], rescore_row(run5["oracle"][qid])["v3"]
        row["open_sub_transition"] = f"{e1['open_sub']}->{e5['open_sub']}"
        row["open_orig_transition"] = f"{e1['open_orig']}->{e5['open_orig']}"
        out.append(row)
    return out


def _retrieval_aggregate(rows: list[dict], key: str) -> dict:
    n = len(rows)
    oo = sum(r[key]["orig_gold_hit"] for r in rows)
    ss = sum(r[key]["sub_gold_hit"] for r in rows)
    both = sum(r[key]["orig_gold_hit"] and r[key]["sub_gold_hit"] for r in rows)
    return dict(n=n, orig_hits=oo, sub_hits=ss, joint_hits=both,
                recall_orig=oo / n, recall_sub=ss / n,
                conditional_retain=both / oo if oo else None,
                recall_drop=(oo - ss) / n)


def _mechanism_summary(audit: list[dict], run1: dict, run5: dict,
                       ids: list[str], budget: int) -> dict:
    """把 recall 进入、上下文预算与 open-sub 转移放在同一张审计交叉表。"""
    by_id = {r["question_id"]: r for r in audit}
    table: dict[str, dict[str, int]] = {}
    d_transition: dict[str, int] = {}
    budget_k5 = 0
    gold_k5_but_d_lost = 0
    for qid in ids:
        r = by_id[qid]
        recall_state = f"{int(r['k1']['sub_gold_hit'])}->{int(r['k5']['sub_gold_hit'])}"
        em1 = rescore_row(run1["oracle"][qid])["v3"]["open_sub"]
        em5 = rescore_row(run5["oracle"][qid])["v3"]["open_sub"]
        d_state = f"{em1}->{em5}"
        table.setdefault(recall_state, {})[d_state] = table.setdefault(recall_state, {}).get(d_state, 0) + 1
        d_transition[d_state] = d_transition.get(d_state, 0) + 1
        budget_k5 += int(r["k5"]["ctx_sub_tokens"] >= budget)
        gold_k5_but_d_lost += int(r["k5"]["ctx_sub_gold_present"] and d_state == "1->0")
    return dict(n=len(ids), sub_gold_recall_by_open_sub_transition=table,
                open_sub_transition=d_transition, k5_context_at_budget=budget_k5,
                k5_gold_present_but_open_sub_lost=gold_k5_but_d_lost)


def _print_group(name: str, result: dict) -> None:
    a, b = result["k1"], result["k5"]
    print(f"=== {name}  n={a['n']} ===")
    for label, d in (("k=1", a), ("k=5", b)):
        print(f"  {label}: a={d['a']:.3f} b={d['b']:.3f} c={d['c']:.3f} d={d['d']:.3f} | "
              f"表观={d['apparent_gain']:+.3f} 校正={d['corrected_gain']:+.3f} "
              f"DiD={d['did']:+.3f} CI=[{d['did_ci'][0]:+.3f},{d['did_ci'][1]:+.3f}] "
              f"掩盖={d['masking']:.3f}")
    dm = result["paired"]["delta_masking_k5_minus_k1"]
    print(f"  Δmasking(k5-k1)={dm['mean']:+.3f} CI=[{dm['ci'][0]:+.3f},{dm['ci'][1]:+.3f}] "
          f"sign-p={dm['sign_test_two_sided']:.4g}")
    b1 = result["formal_b1"]
    print(f"  B1: 表观最优={b1['apparent_best']} 校正最优={b1['corrected_best']} "
          f"P(flip)={b1['p_flip']:.3f} CI分离={b1['corrected_ci_separated']} -> {b1['verdict']}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B 线 k=1/k=5 的只读 paired v3 分析")
    ap.add_argument("--k1-dir", required=True, help="k=1 run 输出目录")
    ap.add_argument("--k5-dir", required=True, help="k=5 run 输出目录")
    ap.add_argument("--trivia", required=True, help="用于重建 shared-corpus retrieval 的题池")
    ap.add_argument("--corpus", required=True, help="共享语料 trivia-dev.json")
    ap.add_argument("--out", required=True, help="新 analysis JSON 路径（不会写入任一原 run 目录）")
    ap.add_argument("--budget", type=int, default=1024, choices=config.BUDGETS)
    ap.add_argument("--granularity", default="paragraph", choices=config.GRANULARITIES)
    ap.add_argument("--bootstrap", type=int, default=config.BOOTSTRAP_B)
    args = ap.parse_args(argv)
    if args.bootstrap < 100:
        raise SystemExit("--bootstrap 至少为 100")

    run1 = _load_run(Path(args.k1_dir), "k=1")
    run5 = _load_run(Path(args.k5_dir), "k=5")
    ids1, ids5 = set(run1["oracle"]), set(run5["oracle"])
    if ids1 != ids5:
        raise SystemExit(f"两格 question_id 不一致：仅 k1={len(ids1 - ids5)}，仅 k5={len(ids5 - ids1)}")
    ids = sorted(ids1)
    # 同一构集既是配对前提，也是 B 线最基本的 artifact integrity check。
    for qid in ids:
        if run1["subs"][qid]["new_passage"] != run5["subs"][qid]["new_passage"]:
            raise SystemExit(f"{qid}: k1/k5 new_passage 不一致，拒绝配对")

    structural = [qid for qid in ids if _structural_ok(run1["subs"][qid])
                  and _structural_ok(run5["subs"][qid])]
    term_present = [qid for qid in structural if run1["oracle"][qid].get("term_present")
                    and run5["oracle"][qid].get("term_present")]
    groups = {"historical_all": ids, "structural_gate567": structural,
              "structural_gate567_term_present": term_present}
    # 诊断性类型分层只在真冲突结构有效集合中报。
    for answer_type in ("date", "numeric"):
        groups[f"structural_term_present_{answer_type}"] = [
            qid for qid in term_present if run1["oracle"][qid].get("answer_type") == answer_type]

    result = dict(
        protocol="bline-paired-v3",
        note=("只读重评；historical_all 是 Gate 5 前置化之前的历史 ITT，正式审计以 "
              "structural_gate567 与 term_present 子集为准。"),
        inputs=dict(k1=run1["paths"], k5=run5["paths"], trivia=args.trivia, corpus=args.corpus),
        n=dict(historical_all=len(ids), structural_gate567=len(structural), term_present=len(term_present)),
        groups={},
    )
    for name, qids in groups.items():
        if not qids:
            continue
        k1_rows, k5_rows = _objects(run1, qids), _objects(run5, qids)
        block = dict(k1=_summary(k1_rows, args.bootstrap), k5=_summary(k5_rows, args.bootstrap),
                     paired=_paired_report(k1_rows, k5_rows, args.bootstrap),
                     formal_b1=_formal_b1(k1_rows, k5_rows, args.bootstrap))
        result["groups"][name] = block
        _print_group(name, block)

    audit = _reconstruct_retrieval(ids, run1, run5, args.trivia, args.corpus,
                                   args.budget, args.granularity)
    result["retrieval_reconstruction"] = dict(
        k1=_retrieval_aggregate(audit, "k1"), k5=_retrieval_aggregate(audit, "k5"), rows=audit)
    result["mechanism"] = {
        "structural_gate567": _mechanism_summary(audit, run1, run5, structural, args.budget),
        "structural_gate567_term_present": _mechanism_summary(
            audit, run1, run5, term_present, args.budget),
    }
    print("\n[T2 rebuilt]")
    for key in ("k1", "k5"):
        d = result["retrieval_reconstruction"][key]
        cond = "n/a" if d["conditional_retain"] is None else f"{d['conditional_retain']:.3f}"
        print(f"  {key}: orig={d['orig_hits']}/{d['n']} sub={d['sub_hits']}/{d['n']} "
              f"conditional_retain={cond} joint={d['joint_hits']}/{d['n']} "
              f"drop={d['recall_drop']:+.3f}")
    print("[mechanism, structural]")
    for name, d in result["mechanism"].items():
        print(f"  {name}: open_sub={d['open_sub_transition']} "
              f"gold-recall×d={d['sub_gold_recall_by_open_sub_transition']} "
              f"k5_at_budget={d['k5_context_at_budget']}/{d['n']} "
              f"k5_gold_but_d_1to0={d['k5_gold_present_but_open_sub_lost']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写只读分析：{out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
