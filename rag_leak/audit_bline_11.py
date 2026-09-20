"""11 题机制审计（只读）：k=1 open_sub 正确 → k=5 open_sub 变错 的逐题拆解。

背景
----
`out_b8_recall_analysis_b10000_cached.json` 的 mechanism 表给出
`k5_gold_present_but_open_sub_lost = 11`：结构真冲突集（Gate5/6/7 全过 + term_present）
里有 11 题，gold 在 k=1 与 k=5 **都已召回且实际进入 context**，且 k=5 无题触及 1024 token
预算，但 open_sub 的 EM 从 1 掉到 0。这排除了"漏召回/预算截断"，但没说明**为什么**掉。

本工具把这 11 题逐题拆开，产出**可直接判读**的证据：
  1. 两 k 的 open_sub 原始输出 + 既有 `classify_output` 归类（new/old/other）+ contain 判定；
  2. 是否在输出里**整词提到旧值**（复读 vs 拒答 vs 格式-other 的分界）；
  3. k=5 相对 k=1 **新增**的 top-k distractor（doc_id + 正文 + 是否整词含旧答案/新答案/是否 gold）；
  4. 跨题汇总：归类分布、新增 distractor 含旧答案的题数、gold rank 在两 k 间的变化。

**完全只读**：不写任何 run 目录，不覆盖 metrics/oracle/fourarm/substituted。
检索按 `run_bline` 的同一 builder (`make_bline_builder`) 重建，与旧 run 口径一致。

示例（在 论文/ 目录执行）：
  python -m rag_leak.audit_bline_11 \
      --analysis rag_leak/out_b8_recall_analysis_b10000_cached.json \
      --k1-dir rag_leak/out_b8_recall_k1 --k5-dir rag_leak/out_b8_recall_k5 \
      --trivia data/trivia_dn.json --corpus data/trivia-dev.json \
      --out rag_leak/out_b8_recall_11q_audit.json \
      --report rag_leak/out_b8_recall_11q_audit.md
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
from .generation.arm import ArmConfig
from .metrics.compliance import classify_output
from .metrics.normalize import normalize_answer, whole_occurrence_count
from .offline_rescore import rescore_row
from .run_bline import load_corpus, make_bline_builder

_DEFAULT_SNIPPET = 400


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _one(dir_path: Path, suffix: str) -> Path:
    matches = sorted(dir_path.glob(f"*{suffix}"))
    if len(matches) != 1:
        raise ValueError(f"{dir_path}: 需要恰好一个 *{suffix}，实际 {matches}")
    return matches[0]


def _load_run(dir_path: Path) -> dict:
    oracle = _read_jsonl(_one(dir_path, "_oracle_rows.jsonl"))
    subs = _read_jsonl(_one(dir_path, "_substituted.jsonl"))
    o_by_id = {r["question_id"]: r for r in oracle}
    s_by_id = {r["question_id"]: r for r in subs}
    if len(o_by_id) != len(oracle) or len(s_by_id) != len(subs):
        raise ValueError(f"{dir_path}: question_id 存在重复行")
    if set(o_by_id) != set(s_by_id):
        raise ValueError(f"{dir_path}: oracle 与 substituted 的 question_id 集不一致")
    return dict(oracle=o_by_id, subs=s_by_id, directory=str(dir_path))


def _structural_ok(sub: dict) -> bool:
    gates = sub.get("gates") or {}
    return all((gates.get(k) or {}).get("passed") is True for k in ("5", "6", "7"))


def _contains_any(raw: str, aliases: list[str]) -> bool:
    """输出里是否**整词**出现任一等价答案（复读/拒答的分界线，用全项目统一的整词计数）。"""
    return any(whole_occurrence_count(raw, a) > 0 for a in aliases if a)


def _rank(hits: list, doc_id: str):
    return next((i for i, (d, _s) in enumerate(hits, start=1) if d == doc_id), None)


def _classify(row: dict, raw: str) -> dict:
    cls = classify_output(raw, row.get("new_aliases") or [], row.get("old_aliases") or [])
    p = normalize_answer(raw)
    new_ct = _contains_any(raw, row.get("new_aliases") or [])
    old_ct = _contains_any(raw, row.get("old_aliases") or [])
    return dict(class_strict=cls, contains_new=new_ct, contains_old=old_ct,
                mentions_old=old_ct and cls != "old", empty=not p)


def _distractor_tag(par: SimpleNamespace, gold_id: str, new_key: str, old_aliases: list[str]) -> dict:
    text = par.text
    return dict(
        doc_id=par.doc_id,
        is_gold=par.doc_id == gold_id,
        has_new_key=whole_occurrence_count(text, new_key) > 0 if new_key else False,
        has_old_answer=any(whole_occurrence_count(text, a) > 0 for a in old_aliases if a),
        chars=len(text),
    )


def _fmt_passage(par: SimpleNamespace, snippet: int) -> str:
    t = " ".join(par.text.split())
    return t[:snippet] + ("…" if len(t) > snippet else "")


def audit(args) -> dict:
    analysis = json.loads(Path(args.analysis).read_text(encoding="utf-8"))
    mech = analysis.get("mechanism", {}).get("structural_gate567_term_present")
    if mech is None:
        raise SystemExit("--analysis 缺少 mechanism.structural_gate567_term_present")

    run1, run5 = _load_run(Path(args.k1_dir)), _load_run(Path(args.k5_dir))
    ids = sorted(set(run1["oracle"]) & set(run5["oracle"]))
    questions = {q.id: q for q in load_dpr_file(args.trivia, "trivia")}
    corpus_paras, corpus_toks, corpus_norms = load_corpus(args.corpus)
    builder = make_bline_builder(corpus_paras, corpus_toks, corpus_norms)
    # builder 把 gold 窗按 build_gold 的 doc_id 换进上下文，与共享语料的 `corpus:i` 不同名，
    # 但两处正文一致；故 top-k 里的 gold 要用 gold 段落自身来打 is_gold 标记（见下方 _para）。
    para_by_id = {p.doc_id: p for p in corpus_paras}

    # 目标 11 题：结构有效 + term_present + open_sub 由 1 变 0（与 mechanism 表同判据）
    selected = []
    for qid in ids:
        if not (_structural_ok(run1["subs"][qid]) and _structural_ok(run5["subs"][qid])):
            continue
        if not (run1["oracle"][qid].get("term_present") and run5["oracle"][qid].get("term_present")):
            continue
        e1 = rescore_row(run1["oracle"][qid])["v3"]
        e5 = rescore_row(run5["oracle"][qid])["v3"]
        if e1["open_sub"] == 1 and e5["open_sub"] == 0:
            selected.append(qid)
    if len(selected) != mech["k5_gold_present_but_open_sub_lost"]:
        print(f"[warn] 本工具选中 {len(selected)} 题，analysis 记 "
              f"{mech['k5_gold_present_but_open_sub_lost']} 题；以本工具逐题判据为准")

    rows = []
    for qid in selected:
        q = questions.get(qid)
        if q is None:
            raise SystemExit(f"{qid}: 不在 --trivia 中")
        gold = build_gold(q)
        if len(gold.passages) != 1:
            raise SystemExit(f"{qid}: 重建时并非单金段")
        gold_id = gold.passages[0].doc_id
        gold_text = gold.passages[0].text

        def _para(doc_id: str) -> SimpleNamespace:
            """命中共享语料用其对象；gold 用 gold 自身（doc_id 不同名，正文同一段）。"""
            if doc_id in para_by_id:
                return para_by_id[doc_id]
            if doc_id == gold_id:
                return SimpleNamespace(doc_id=gold_id, title=gold.passages[0].title, text=gold_text)
            raise KeyError(f"{qid}: top-k 里的 {doc_id} 既不在共享语料、也不是 gold 窗")
        row1, row5 = run1["oracle"][qid], run5["oracle"][qid]
        sub1 = run1["subs"][qid]
        old_aliases = row1.get("old_aliases") or []
        new_key = row1.get("term_key") or ""

        per_k = {}
        hits_by_k = {}
        for name, k, run in (("k1", 1, run1), ("k5", 5, run5)):
            sub = run["subs"][qid]
            sub_obj = SimpleNamespace(old_passage=sub["old_passage"], new_passage=sub["new_passage"])
            acfg = ArmConfig(args.granularity, args.budget, k, rerank=False)
            ctx_o, ctx_s, hits_o, hits_s, rr_o, rr_s, _ = builder(q, [sub_obj], gold, acfg)
            hits_by_k[name] = hits_s
            tagged = [_distractor_tag(_para(d), gold_id, new_key, old_aliases) for d, _s in hits_s]
            e = rescore_row(run["oracle"][qid])["v3"]
            raw = (run["oracle"][qid].get("arms_raw") or {}).get("open_sub", "")
            per_k[name] = dict(
                open_sub_em=e["open_sub"],
                gold_hit=rr_s.gold_hit(),
                gold_rank=_rank(hits_s, gold_id),
                hit_doc_ids=[d for d, _ in hits_s],
                hits=tagged,
                open_sub_raw=raw,
                cls=_classify(row5 if name == "k5" else row1, raw),
            )

        # k=5 相对 k=1 新增的窗口（顺序保持 k=5 的排名）
        new_ids = [d for d in per_k["k5"]["hit_doc_ids"] if d not in set(per_k["k1"]["hit_doc_ids"])]
        added = []
        for d in new_ids:
            par = _para(d)
            tag = _distractor_tag(par, gold_id, new_key, old_aliases)
            tag["snippet"] = _fmt_passage(par, args.snippet)
            added.append(tag)

        rows.append(dict(
            question_id=qid,
            question=q.text,
            gold=q.answers[0] if q.answers else "",
            answer_type=row1.get("answer_type"),
            old_aliases=old_aliases,
            new_key=new_key,
            old_passage=" ".join((sub1.get("old_passage") or "").split()),
            new_passage=" ".join((sub1.get("new_passage") or "").split()),
            k1=per_k["k1"],
            k5=per_k["k5"],
            added_at_k5=added,
            added_has_old_answer=sum(a["has_old_answer"] for a in added),
            gold_rank_k1=per_k["k1"]["gold_rank"],
            gold_rank_k5=per_k["k5"]["gold_rank"],
            k5_ctx_tokens=None,
        ))

    summary = dict(
        n=len(rows),
        k1_class={c: sum(r["k1"]["cls"]["class_strict"] == c for r in rows) for c in ("new", "old", "other")},
        k5_class={c: sum(r["k5"]["cls"]["class_strict"] == c for r in rows) for c in ("new", "old", "other")},
        k5_contains_old=sum(r["k5"]["cls"]["contains_old"] for r in rows),
        k5_mentions_old_but_other=sum(r["k5"]["cls"]["mentions_old"] for r in rows),
        k5_empty=sum(r["k5"]["cls"]["empty"] for r in rows),
        questions_with_added_old_value=sum(r["added_has_old_answer"] > 0 for r in rows),
        added_windows_total=sum(len(r["added_at_k5"]) for r in rows),
        gold_rank_moved=sum(r["gold_rank_k1"] != r["gold_rank_k5"] for r in rows),
        answer_type={t: sum(r["answer_type"] == t for r in rows) for t in ("date", "numeric")},
    )
    return dict(
        protocol="bline-11q-mechanism-audit-v1",
        note=("只读逐题拆解：结构真冲突集中 open_sub 由 k=1 正确转为 k=5 错误的题。"
              "class_strict 复用 metrics.compliance.classify_output；整词判定复用 whole_occurrence_count。"),
        inputs=dict(analysis=args.analysis, k1=run1["directory"], k5=run5["directory"],
                    trivia=args.trivia, corpus=args.corpus,
                    budget=args.budget, granularity=args.granularity),
        analysis_mechanism=mech,
        summary=summary,
        rows=rows,
    )


def _render(result: dict, snippet_note: bool) -> str:
    s = result["summary"]
    out = ["# B 线 11 题机制审计（只读）", ""]
    out.append(f"- 协议：`{result['protocol']}`")
    out.append(f"- 题数：**{s['n']}**（date {s['answer_type'].get('date', 0)} / numeric {s['answer_type'].get('numeric', 0)}）")
    out.append(f"- 输入：k1=`{result['inputs']['k1']}`，k5=`{result['inputs']['k5']}`")
    out.append(f"- 预算/粒度：{result['inputs']['budget']} / {result['inputs']['granularity']}"
               + ("（新增 distractor 正文见 JSON，本报告只给摘要）" if snippet_note else ""))
    out += ["", "## 0. 汇总（判读要点）", "",
            "| 指标 | k=1 | k=5 |", "|---|---:|---:|",
            f"| classify=new | {s['k1_class']['new']} | {s['k5_class']['new']} |",
            f"| classify=old | {s['k1_class']['old']} | {s['k5_class']['old']} |",
            f"| classify=other | {s['k1_class']['other']} | {s['k5_class']['other']} |", "",
            f"- k=5 输出**整词含旧答案**：**{s['k5_contains_old']}/{s['n']}**",
            f"- k=5 输出提到旧值但整体判 other（应读原文区分『说到旧值』与『复读旧值』）：**{s['k5_mentions_old_but_other']}/{s['n']}**",
            f"- k=5 空输出：**{s['k5_empty']}/{s['n']}**",
            f"- k=5 新增窗口里含旧答案的题数：**{s['questions_with_added_old_value']}/{s['n']}**"
            f"（新增窗口共 {s['added_windows_total']} 个）",
            f"- gold rank 在两 k 间变化的题数：**{s['gold_rank_moved']}/{s['n']}**", ""]
    for r in result["rows"]:
        out += [f"## {r['question_id']}（{r['answer_type']}）", "",
                f"- Q：{r['question']}",
                f"- gold：`{r['gold']}`　旧别名：{', '.join(f'`{a}`' for a in r['old_aliases'])}　新 key：`{r['new_key']}`",
                f"- 旧段：{r['old_passage'][:300]}",
                f"- 新段：{r['new_passage'][:300]}", ""]
        for name in ("k1", "k5"):
            d = r[name]
            out += [f"**{name}** EM={d['open_sub_em']}　gold_hit={d['gold_hit']}　gold_rank={d['gold_rank']}"
                    f"　class={d['cls']['class_strict']}（contains_old={d['cls']['contains_old']}）", "",
                    "```", (d["open_sub_raw"] or "<空>")[:400], "```", ""]
        if r["added_at_k5"]:
            out += ["**k=5 新增窗口**", "", "| doc_id | 含旧答案 | 含新 key | 字符数 |", "|---|---|---|---:|"]
            for a in r["added_at_k5"]:
                out.append(f"| `{a['doc_id']}` | {a['has_old_answer']} | {a['has_new_key']} | {a['chars']} |")
            out.append("")
        else:
            out += ["**k=5 新增窗口**：无（top-k 集合与 k=1 相同）", ""]
    return "\n".join(out) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B 线 11 题机制审计（只读）")
    ap.add_argument("--analysis", required=True, help="analyze_bline 产出的 analysis JSON")
    ap.add_argument("--k1-dir", required=True)
    ap.add_argument("--k5-dir", required=True)
    ap.add_argument("--trivia", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True, help="审计 JSON 输出路径（不要写进 run 目录）")
    ap.add_argument("--report", default="", help="可选：人类可读 Markdown 报告路径")
    ap.add_argument("--budget", type=int, default=1024, choices=config.BUDGETS)
    ap.add_argument("--granularity", default="paragraph", choices=config.GRANULARITIES)
    ap.add_argument("--snippet", type=int, default=_DEFAULT_SNIPPET,
                    help="新增窗口正文在 JSON 里的截断长度")
    args = ap.parse_args(argv)

    result = audit(args)
    s = result["summary"]
    print(f"=== 11 题机制审计：命中 {s['n']} 题 ===")
    print(f"  classify k1 new/old/other = {s['k1_class']['new']}/{s['k1_class']['old']}/{s['k1_class']['other']}")
    print(f"  classify k5 new/old/other = {s['k5_class']['new']}/{s['k5_class']['old']}/{s['k5_class']['other']}")
    print(f"  k5 整词含旧答案 = {s['k5_contains_old']}/{s['n']}；提到旧值但判 other = "
          f"{s['k5_mentions_old_but_other']}/{s['n']}；空输出 = {s['k5_empty']}/{s['n']}")
    print(f"  k5 新增窗口含旧答案的题 = {s['questions_with_added_old_value']}/{s['n']}"
          f"（新增窗口 {s['added_windows_total']} 个）；gold rank 变化 = {s['gold_rank_moved']}/{s['n']}")
    print(f"  类型分布：{s['answer_type']}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写审计 JSON：{out_path}")
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(_render(result, snippet_note=args.snippet > 0), encoding="utf-8")
        print(f"已写报告：{rp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
