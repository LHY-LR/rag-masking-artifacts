"""C4：把通过 ⑥ 的 Substituted 导出为标注任务 JSONL（供 ⑤语义唯一 / ⑦关系合理性 人审）。

每行一个填空任务，标注者只填 semantic_unique / relation_plausible / comment，
两人独立标注后用 merge_labels 合并算 Cohen κ（闸门⑧）。
用法：
  python -m rag_leak.annotate.export_tasks --subs out/mini_substituted.jsonl --out out/anno_tasks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "rag_leak.annotate"


def _gate6_ok(rec: dict) -> bool:
    g = rec.get("gates", {}).get("6")
    return True if g is None else bool(g.get("passed", True))


def build_task(rec: dict) -> dict:
    prop = rec.get("proposal", {})
    return {
        "task_id": f"{rec['question_id']}::{prop.get('passage_doc_id', '')}",
        "question_id": rec["question_id"],
        "doc_id": prop.get("passage_doc_id", ""),
        "old": rec.get("old_key", ""),
        "new": rec.get("new_key", ""),
        "subject": "",                       # 标注者填：被替换事实的主体
        "old_passage": rec.get("old_passage", ""),
        "new_passage": rec.get("new_passage", ""),
        "semantic_unique": None,             # ⑤ 语义上是否唯一指向（true/false）
        "relation_plausible": None,          # ⑦ 新值与主体关系是否合理（true/false）
        "labeler": None,
        "comment": "",
    }


def export(subs_path: str | Path, out_path: str | Path, require_gate6: bool = True) -> int:
    tasks = []
    for line in Path(subs_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if require_gate6 and not _gate6_ok(rec):
            continue
        tasks.append(build_task(rec))
    with Path(out_path).open("w", encoding="utf-8") as f:
        for t in tasks:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return len(tasks)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--subs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--include_failed6", action="store_true")
    args = ap.parse_args(argv)
    n = export(args.subs, args.out, require_gate6=not args.include_failed6)
    print(f"导出 {n} 条标注任务 -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
