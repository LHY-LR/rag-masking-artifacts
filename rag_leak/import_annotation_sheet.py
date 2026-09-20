"""把标注人填好的 Excel 清单（TSV）回填成 anno_X.jsonl —— 供 `annotate.merge` 算 κ。

为什么需要：标注人不该手编 jsonl（会破坏格式，且 `merge` 要求 `task_id` 逐条对齐）。
本脚本只做**读取与校验**，不做任何判定；填了 `是/否` 也算，会自动转成 `true/false`。

用法（论文/ 目录）：
  python -m rag_leak.import_annotation_sheet \\
      --sheet rag_leak/anno_sheet_A.tsv --base rag_leak/anno_A.jsonl \\
      --out rag_leak/anno_A_filled.jsonl --labeler 甲
产出：anno_A_filled.jsonl（原模板 + 两维标签），并打印填写覆盖情况；
     有漏填会**非零退出**并列出序号（宁可不写，也不要写半份）。
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

DIMS = ("semantic_unique", "relation_plausible")
_TRUE = {"是", "true", "t", "1", "y", "yes", "对", "合格"}
_FALSE = {"否", "false", "f", "0", "n", "no", "错", "不合格"}


def _parse(v: str, dim: str, where: str) -> bool | None:
    s = (v or "").strip().lower()
    if not s:
        return None
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    raise SystemExit(f"{where} 的 {dim} 无法识别：{v!r}（请填 true/false 或 是/否）")


def _col(header: list[str], *keys: str) -> int:
    for i, h in enumerate(header):
        if any(k in h for k in keys):
            return i
    raise SystemExit(f"表头里找不到含 {keys} 的列；实际表头={header}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="标注结果 → anno jsonl 回填（TSV 模式 / 序号模式）")
    ap.add_argument("--sheet", default="", help="TSV 模式：填好的 anno_sheet_X.tsv")
    ap.add_argument("--numbers", default="",
                    help="序号模式：**只报判『否』的序号**（空格或逗号分隔），其余默认『是』。"
                         "用于标注者用口头/聊天回报的情形；写入单一维度 `usable`。")
    ap.add_argument("--base", required=True, help="原始模板 anno_A.jsonl / anno_B.jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labeler", default="")
    args = ap.parse_args(argv)
    if bool(args.sheet) == bool(args.numbers):
        raise SystemExit("必须且只能给 --sheet 或 --numbers 之一")

    base = [json.loads(l) for l in Path(args.base).read_text(encoding="utf-8").splitlines() if l.strip()]
    if not base:
        raise SystemExit(f"{args.base} 为空")

    if args.numbers:
        # 单一合并维度模式：第一轮实测中两位标注者都是按"这条题合格吗"整体判的，
        # 并没有把 ⑤/⑦ 分开填。硬拆成两维会**编造**数据，所以这里只写 `usable` 一维，
        # merge 时用 --dims usable。协议偏离记在 CHANGELOG C32。
        bad = {int(x) for x in re.split(r"[,\s、，]+", args.numbers.strip()) if x.strip()}
        n = len(base)
        oob = sorted(i for i in bad if not 1 <= i <= n)
        if oob:
            raise SystemExit(f"序号超出 1..{n}：{oob}")
        out = []
        for i, r in enumerate(base, 1):
            rec = dict(r)
            rec["usable"] = i not in bad
            rec["semantic_unique"] = None
            rec["relation_plausible"] = None
            rec["labeler"] = args.labeler or rec.get("labeler") or ""
            out.append(rec)
        Path(args.out).write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")
        print(f"usable: 否={len(bad)} 是={n - len(bad)} / {n}")
        print(f"已写 {args.out}（labeler={args.labeler!r}，单一维度 usable）")
        return 0

    with Path(args.sheet).open(encoding="utf-8-sig", newline="") as f:
        rdr = csv.reader(f, delimiter="\t")
        header = next(rdr)
        i_tid = _col(header, "题号", "task_id")
        i_5 = _col(header, "语义唯一", "改动处", "在回答这题")
        i_7 = _col(header, "不可推导", "关系合理", "正常答案", "relation_plausible")
        i_cm = _col(header, "备注", "comment")
        filled = {}
        for row in rdr:
            if not any(str(c).strip() for c in row):
                continue
            if len(row) <= max(i_tid, i_5, i_7):
                raise SystemExit(f"行太短（可能 Excel 串列）：{row[:3]}")
            tid = row[i_tid].strip()
            filled[tid] = {
                "semantic_unique": _parse(row[i_5], "⑤语义唯一", tid),
                "relation_plausible": _parse(row[i_7], "⑦不可推导", tid),
                "comment": (row[i_cm].strip() if len(row) > i_cm else ""),
            }

    missing = [r["task_id"] for r in base if r["task_id"] not in filled]
    unfilled = [t for t, v in filled.items() if any(v[d] is None for d in DIMS)]
    if missing:
        raise SystemExit(f"清单里缺少 {len(missing)} 条：{missing[:10]}{'...' if len(missing) > 10 else ''}")
    if unfilled:
        raise SystemExit(f"有 {len(unfilled)} 条两列没填全：{unfilled[:10]}"
                         f"{'...' if len(unfilled) > 10 else ''}（漏填会令 κ 不可算）")

    out = []
    for r in base:
        v = filled[r["task_id"]]
        rec = dict(r)
        rec["semantic_unique"] = v["semantic_unique"]
        rec["relation_plausible"] = v["relation_plausible"]
        rec["labeler"] = args.labeler or r.get("labeler") or ""
        if v["comment"]:
            rec["comment"] = v["comment"]
        out.append(rec)
    Path(args.out).write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n", encoding="utf-8")

    n = len(out)
    for d in DIMS:
        t = sum(1 for r in out if r[d] is True)
        print(f"{d}: true={t} false={n - t} / {n}")
    print(f"已写 {args.out}（labeler={args.labeler!r}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
