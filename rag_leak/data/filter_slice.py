"""类型切片工具（C12）：把窗口化 DPR json（trivia-dev.json）按 answers[0] 的
infer_answer_type 过滤出指定类型子集（如 date,numeric），保持行结构与行内字段不变。

设计动机（round-6）：
- 核心结论只在"能产生干净反事实的 date/numeric 类型"上稳健（round-5 verdict）。
- 用同一分类器 infer_answer_type 在 load 时与运行时完全一致（q.answer_type
  即由此函数对 answers[0] 得出），保证切片归属与产物 answer_type 分层一致。
- 只筛行、不改内容：positive_ctxs 金窗、answers alias 顺序原样保留，可复现。

用法（跑完可复现地重建切片）：
  python -m rag_leak.data.filter_slice --in data/trivia-dev.json \
      --out data/trivia_dn.json --keep date,numeric
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "rag_leak"

from .load_raw import infer_answer_type  # noqa: E402


def _answer0(row: dict) -> str:
    for a in (row.get("answers") or []):
        if str(a).strip():
            return str(a).strip()
    return ""


def filter_slice(rows: list[dict], keep: set[str]) -> list[dict]:
    """按 answers[0] 类型过滤；类型无法判定（空 answers）默认丢弃。"""
    out = []
    for r in rows:
        a0 = _answer0(r)
        if not a0:
            continue
        if infer_answer_type(a0) in keep:
            out.append(r)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="按 answers[0] 类型过滤窗口化 DPR json")
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--keep", default="date,numeric",
                    help="逗号分隔的保留类型（date/numeric/name/bridge/comparison）")
    ap.add_argument("--report", action="store_true", help="打印 keep 命中数与类型分布")
    args = ap.parse_args(argv)

    rows = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    keep = {t.strip() for t in args.keep.split(",") if t.strip()}
    out = filter_slice(rows, keep)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    if args.report:
        from collections import Counter
        print(f"in={args.inp}: {len(rows)} 行 -> out={args.out}: {len(out)} 行 (keep={sorted(keep)})")
        c = Counter(infer_answer_type(_answer0(r)) for r in out)
        print("  out 类型分布:", dict(c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
