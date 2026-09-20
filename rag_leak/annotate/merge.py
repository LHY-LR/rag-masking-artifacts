"""C4：两位标注者结果合并——逐维度 Cohen κ（闸门⑧）+ 冲突清单 + 一致项裁决文件。

用法：
  python -m rag_leak.annotate.merge --a anno_a.jsonl --b anno_b.jsonl --out adjudicated.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "rag_leak.annotate"

from ..construct.gate import cohen_kappa

DIMS = ("semantic_unique", "relation_plausible")


def _load(path: str | Path) -> dict[str, dict]:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            d = json.loads(line)
            out[d["task_id"]] = d
    return out


def merge_labels(path_a, path_b, out_path=None, dims=DIMS) -> dict:
    a, b = _load(path_a), _load(path_b)
    shared = sorted(set(a) & set(b))
    report = {"n_double": len(shared), "dims": list(dims), "kappa": {}, "conflicts": []}
    adjudicated = []
    for dim in dims:
        if any(dim not in a[t] or dim not in b[t] for t in shared):
            raise SystemExit(f"维度 {dim} 在两份标注里缺失")
        va = [a[t][dim] for t in shared]
        vb = [b[t][dim] for t in shared]
        if any(v is None for v in va + vb):
            report["kappa"][dim] = None  # 存在未标注项，κ 不可算
        else:
            report["kappa"][dim] = cohen_kappa(va, vb)
    for t in shared:
        diffs = [dim for dim in dims if a[t][dim] != b[t][dim]]
        if diffs:
            report["conflicts"].append({"task_id": t, "dims": diffs,
                                        "a": {d: a[t][d] for d in diffs},
                                        "b": {d: b[t][d] for d in diffs}})
        else:
            rec = dict(a[t]); rec["labeler"] = "agreed"
            adjudicated.append(rec)
    report["n_conflict"] = len(report["conflicts"])
    if out_path is not None:
        with Path(out_path).open("w", encoding="utf-8") as f:
            for rec in adjudicated:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return report


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True); ap.add_argument("--b", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--dims", default=",".join(DIMS),
                    help="要算 κ 的维度，逗号分隔。默认 %(default)s；"
                         "若标注是单一整体判断（见 C32），传 `usable`。")
    args = ap.parse_args(argv)
    dims = tuple(d.strip() for d in args.dims.split(",") if d.strip())
    rep = merge_labels(args.a, args.b, args.out or None, dims=dims)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
