"""分窗归因探针（需 GPU，交执行方跑）：把 k=5 的 5 个窗口逐个单独喂给模型。

目的：区分两种机制解释，二者对论文含义完全不同——
  A. **单个干扰窗口**：某个特定窗口单独就能把答案带跑（→ 可定位的污染源）；
  B. **上下文稀释**：任一单窗无害、组合才有害（→ 深度本身的问题）。

做法（对每题固定一组条件，全部走 **与 run_bline 完全相同的** 语料池、检索器与上下文装配）：
  c0_gold      : 只喂 gold 窗（复现 k=1 的情形）
  c1_k5        : gold + k=5 的 4 个新增窗口（复现 k=5 的情形，**必须与既有 run 的 d 一致**）
  c2_w{i}      : gold + 第 i 个新增窗口（i=1..4，逐窗单独加）
  c3_gold_top1 : 只喂 gold + k=1 的 top1（若 top1 不是 gold，用于检查 gold 之外的那一个窗口）
每题统计各条件下 `open_sub` 是否答出新值（v3 口径），并输出逐题原文供人读。

**只读**：不写任何既有 run 目录；产物写入 --out / --report 指定路径。

用法（在 论文/ 目录执行；需与既有 run 相同的离线 cache 环境）：
  python -m rag_leak.probe_window_attribution \
      --analysis rag_leak/out_b8_recall_analysis_b10000_cached.json \
      --k1-dir rag_leak/out_b8_recall_k1 --k5-dir rag_leak/out_b8_recall_k5 \
      --trivia data/trivia_dn.json --corpus data/trivia-dev.json \
      --model Qwen3-8B --bits 4 \
      --out rag_leak/out_b8_window_attribution.json \
      --report rag_leak/out_b8_window_attribution.md
"""
from __future__ import annotations

import argparse
import json
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
from .metrics.compliance import classify_output
from .metrics.normalize import em_any_alias, normalize_answer, whole_occurrence_count
from .offline_rescore import rescore_row
from .run_bline import load_corpus, make_bline_builder
from .run_pipeline import build_generator
from .schemas import Paragraph


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _one(d: Path, suffix: str) -> Path:
    m = sorted(d.glob(f"*{suffix}"))
    if len(m) != 1:
        raise ValueError(f"{d}: 需要恰好一个 *{suffix}，实际 {m}")
    return m[0]


def _select_11(analysis_path: str, k1_dir: Path, k5_dir: Path) -> list[str]:
    """与 audit_bline_11 同判据：结构有效 + term_present + open_sub 由 1 变 0。"""
    a = json.loads(Path(analysis_path).read_text(encoding="utf-8"))
    mech = a["mechanism"]["structural_gate567_term_present"]
    o1 = {r["question_id"]: r for r in _read_jsonl(_one(k1_dir, "_oracle_rows.jsonl"))}
    o5 = {r["question_id"]: r for r in _read_jsonl(_one(k5_dir, "_oracle_rows.jsonl"))}
    s1 = {r["question_id"]: r for r in _read_jsonl(_one(k1_dir, "_substituted.jsonl"))}
    s5 = {r["question_id"]: r for r in _read_jsonl(_one(k5_dir, "_substituted.jsonl"))}

    def ok(s: dict) -> bool:
        g = s.get("gates") or {}
        return all((g.get(x) or {}).get("passed") is True for x in ("5", "6", "7"))

    out = []
    for q in sorted(set(o1) & set(o5)):
        if not (ok(s1[q]) and ok(s5[q])):
            continue
        if not (o1[q].get("term_present") and o5[q].get("term_present")):
            continue
        if rescore_row(o1[q])["v3"]["open_sub"] == 1 and rescore_row(o5[q])["v3"]["open_sub"] == 0:
            out.append(q)
    if len(out) != mech["k5_gold_present_but_open_sub_lost"]:
        print(f"[warn] 选中 {len(out)} 题，analysis 记 {mech['k5_gold_present_but_open_sub_lost']} 题")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="分窗归因探针（需 GPU）")
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--k1-dir", required=True)
    ap.add_argument("--k5-dir", required=True)
    ap.add_argument("--trivia", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--model", default="Qwen3-8B")
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--budget", type=int, default=1024, choices=config.BUDGETS)
    ap.add_argument("--granularity", default="paragraph", choices=config.GRANULARITIES)
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    args = ap.parse_args(argv)

    ids = _select_11(args.analysis, Path(args.k1_dir), Path(args.k5_dir))
    questions = {q.id: q for q in load_dpr_file(args.trivia, "trivia")}
    corpus_paras, corpus_toks, corpus_norms = load_corpus(args.corpus)
    builder = make_bline_builder(corpus_paras, corpus_toks, corpus_norms)
    para_by_id = {p.doc_id: p for p in corpus_paras}
    # builder 把 gold 窗按 build_gold 的 doc_id（trivia-N:positive_ctxs:0）换进上下文，
    # 与共享语料的 `corpus:i` 不同名但正文同一段；故须显式解析 gold 命名，否则 KeyError。
    para_by_text: dict[str, Paragraph] = {}
    for p in corpus_paras:
        para_by_text.setdefault(p.text, p)
    gen = build_generator("hf", args.model, args.bits, args.device, "")
    print(f"[probe] 模型={args.model} bits={args.bits} 题数={len(ids)}")

    rows = []
    oracle1 = {r["question_id"]: r for r in _read_jsonl(_one(Path(args.k1_dir), "_oracle_rows.jsonl"))}
    subs5 = {r["question_id"]: r for r in _read_jsonl(_one(Path(args.k5_dir), "_substituted.jsonl"))}
    for qid in ids:
        q = questions[qid]
        gold = build_gold(q)
        gold_p = gold.passages[0]
        s5 = subs5[qid]
        sub = SimpleNamespace(old_passage=s5["old_passage"], new_passage=s5["new_passage"])
        new_surface = (s5.get("terminal_key") or s5.get("new_key") or "")
        new_keys = [new_surface] if new_surface else (s5.get("new_key") and [s5["new_key"]] or [])

        def _para(d: str) -> Paragraph:
            """解析 top-k 里的 doc_id：共享语料 / gold 命名 / 文本回退，三者都要能命中。"""
            if d in para_by_id:
                return para_by_id[d]
            if d == gold_p.doc_id:
                return Paragraph(doc_id=gold_p.doc_id, title=gold_p.title,
                                 text=gold_p.text, sentences=list(gold_p.sentences or []))
            hit = para_by_text.get(str(d))
            if hit is not None:
                return hit
            raise KeyError(f"{qid}: top-k 里的 {d} 既不在共享语料、也不是 gold 窗")

        def run_condition(hit_ids: list[str], tag: str) -> dict:
            """按给定窗口集合装配上下文并生成（同一装配路径，保证可比）。"""
            acfg = ArmConfig(args.granularity, args.budget, len(hit_ids), rerank=False)
            hits_o = [(d, 0.0) for d in hit_ids]
            gold_s = Paragraph(doc_id=gold_p.doc_id, title=gold_p.title,
                               text=sub.new_passage, sentences=[])
            sub_paras = [gold_s if d == gold_p.doc_id else _para(d) for d in hit_ids]
            orig_paras = [_para(d) for d in hit_ids]
            _, cb_s, _, _ = build_contexts(q, orig_paras, sub_paras, hits_o, hits_o, acfg,
                                           {gold_p.doc_id})
            ctx = "\n\n".join(cb_s.texts)
            raw = gen.generate(q.text, ctx, target_surface=new_surface, question_id=qid, arm=tag)
            em = em_any_alias(raw, new_keys)
            return dict(tag=tag, n_windows=len(hit_ids), hit_doc_ids=hit_ids,
                        gold_present=cb_s.gold_present, ctx_tokens=cb_s.tokens_used,
                        em=em, raw=raw,
                        cls=classify_output(raw, new_keys, q.answers))

        # 两 k 的 top-k（用同一 builder 重建，与既有 run 口径一致）
        def topk(k: int) -> list[str]:
            acfg = ArmConfig(args.granularity, args.budget, k, rerank=False)
            _, _, ho, hs, _, _, _ = builder(q, [sub], gold, acfg)
            return [d for d, _ in hs]

        t1, t5 = topk(1), topk(5)
        added = [d for d in t5 if d not in t1]
        conds = [run_condition([gold_p.doc_id], "c0_gold"),
                 run_condition(t5, "c1_k5")]
        for i, d in enumerate(added, start=1):
            conds.append(run_condition([gold_p.doc_id, d], f"c2_w{i}"))
        if t1 and gold_p.doc_id not in t1:
            conds.append(run_condition(t1, "c3_k1_actual"))
        rows.append(dict(question_id=qid, question=q.text,
                         answer_type=oracle1[qid].get("answer_type"),
                         gold=q.answers[0], new_key=new_surface,
                         top1=t1, top5=t5, added=added, conditions=conds))

    # 汇总
    tags = ["c0_gold", "c1_k5"] + [f"c2_w{i}" for i in range(1, 5)] + ["c3_k1_actual"]
    summary = {}
    for t in tags:
        hit = [r for r in rows if any(c["tag"] == t for c in r["conditions"])]
        if not hit:
            continue
        ok = sum(next(c for c in r["conditions"] if c["tag"] == t)["em"] for r in hit)
        summary[t] = dict(n=len(hit), answered_new=ok, rate=ok / len(hit))
    result = dict(protocol="bline-window-attribution-v1",
                  note=("逐窗单独喂：若某 c2_w{i} 单独就使整组失效 → 单窗污染；"
                        "若各单窗均无害而 c1_k5 失效 → 上下文稀释。c1_k5 必须与既有 run 的 d 一致。"),
                  model=args.model, bits=args.bits, n=len(rows), summary=summary, rows=rows)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== 汇总（答出新值的题数）===")
    for t, d in summary.items():
        print(f"  {t:14s} n={d['n']:3d} 答新值={d['answered_new']:3d}  ({d['rate']:.3f})")
    print(f"\n已写：{args.out}")
    if args.report:
        lines = ["# 分窗归因探针结果", "", f"模型 {args.model}，n={len(rows)}", ""]
        for t, d in summary.items():
            lines.append(f"- **{t}**：答新值 {d['answered_new']}/{d['n']} = {d['rate']:.3f}")
        for r in rows:
            lines += ["", f"## {r['question_id']}（{r['answer_type']}）", "",
                      f"- Q：{r['question']}", f"- gold `{r['gold']}` → 新 key `{r['new_key']}`"]
            for c in r["conditions"]:
                lines += [f"- **{c['tag']}**（{c['n_windows']} 窗，tokens={c['ctx_tokens']}）EM={c['em']} cls={c['cls']}",
                          "```", (c["raw"] or "<空>")[:300], "```"]
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写报告：{args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
