"""第二数据集（HotpotQA）题池构建：从 dev-distractor 筛出**答案可作为年份/数字替换**的子集。

为什么必须自己筛（2026-09-14 侦察结论）：
  - HotpotQA dev-distractor **全部 7405 题都有 2 个 supporting title**，即
    `len(build_gold(q).passages) == 2` **恒成立**，所以"单金段子集"根本不存在（0 条）。
    因此 B 线（`make_bline_builder` 要求单金段）**不能**直接照搬到 HotpotQA；
    但 C 线四臂 DiD 可以（`run_four_arms` 对 hotpot 只要求"末跳 key 恰好 1 个"）。
  - 年份/数字答案共 469 题；其中**末跳金段唯一且答案字面整词命中恰 1 次**的有 **393** 题
    —— 与 C 线 TriviaQA 池（447）同量级，足够做四臂 DiD。

选择口径（全确定性、与任何模型输出无关）：
  ① `_YEAR_RE` 匹配答案，或 `_NUM_RE` 匹配答案（沿用 C 线 date/numeric 富集池的思路，
     但**按答案值判断**而非 `answer_type`——hotpot 的 answer_type 恒为 bridge/comparison）；
  ② 含答案 alias 的金段**恰好 1 个**（即唯一的"末跳"）；
  ③ 答案在该末跳金段里的**整词边界字面命中恰好 1 次**（C 线 gate⑤ 的前置条件）。

产物：
  data/hotpot_dn.json              —— 原始 hotpot 行的子集（保持原顺序，`load_hotpot_file` 直接可读）
  rag_leak/hotpot_pool_report.json —— 选择口径、逐级筛除计数、入选 id 清单

用法（论文/ 目录）：
  python -m rag_leak.prepare_hotpot_pool --src data/hotpot_dev_distractor_v1.json \
      --out data/hotpot_dn.json --report rag_leak/hotpot_pool_report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .data.build_gold import build_gold
from .data.load_raw import _NUM_RE, _YEAR_RE, load_hotpot_file
from .metrics.normalize import normalize_answer


def select(src: str) -> tuple[list[int], dict]:
    rows = json.loads(Path(src).read_text(encoding="utf-8"))
    qs = load_hotpot_file(src)
    if len(rows) != len(qs):
        raise SystemExit(f"行数不一致：raw={len(rows)} loaded={len(qs)}")

    n_year = n_num = n_term1 = n_hit1 = 0
    picked: list[int] = []
    auto_year_like = 0
    for i, q in enumerate(qs):
        a = q.answers[0].strip() if q.answers else ""
        is_year, is_num = bool(_YEAR_RE.match(a)), bool(_NUM_RE.match(a))
        if not (is_year or is_num):
            continue
        n_year += int(is_year)
        n_num += int(is_num)
        g = build_gold(q)
        term = [p for p in g.passages
                if any(normalize_answer(x) in normalize_answer(p.text) for x in q.answers)]
        if len(term) != 1:
            continue
        n_term1 += 1
        p = term[0]
        pat = r"(?<![0-9A-Za-z])" + re.escape(a) + r"(?![0-9A-Za-z])"
        if len(re.findall(pat, p.text)) != 1:
            continue
        n_hit1 += 1
        picked.append(i)
        if q.answer_type != "bridge" and q.answer_type != "comparison":
            auto_year_like += 1

    report = {
        "src": src, "n_total": len(qs),
        "n_all_two_gold": sum(1 for q in qs if len(build_gold(q).passages) == 2),
        "n_year_like": n_year, "n_num_like": n_num,
        "n_terminal_unique": n_term1, "n_selected": len(picked),
        "picked_row_indices": picked,
        "criteria": [
            "answer matches _YEAR_RE or _NUM_RE",
            "exactly one gold passage contains an answer alias (unique terminal hop)",
            "answer occurs exactly once (whole-boundary) in that terminal passage",
        ],
        "note": ("HotpotQA 全部题都有 2 个金段（bridge/comparison），故本池**只能用于 C 线四臂 DiD**；"
                 "B 线 k 轴需要单金段，不适用。选择与任何模型输出无关。"),
    }
    return picked, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="HotpotQA 年份/数字答案题池构建（确定性）")
    ap.add_argument("--src", default="data/hotpot_dev_distractor_v1.json")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    args = ap.parse_args(argv)

    picked, report = select(args.src)
    rows = json.loads(Path(args.src).read_text(encoding="utf-8"))
    subset = [rows[i] for i in picked]
    Path(args.out).write_text(json.dumps(subset, ensure_ascii=False), encoding="utf-8")
    print(f"总 {report['n_total']} → 年份/数字 {report['n_year_like']}/{report['n_num_like']} "
          f"→ 末跳唯一 {report['n_terminal_unique']} → 字面唯一 {report['n_selected']}")
    print(f"已写：{args.out}（{len(subset)} 题）")
    if args.report:
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写：{args.report}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
