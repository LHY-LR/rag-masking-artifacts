# -*- coding: utf-8 -*-
"""holm_stratum.py —— 对"顺从层配对 Δ校正增益"做多重比较校正（外部评审要求）。

用法：python -m rag_leak.holm_stratum
做法：复用 analyze_kaxis 的 load_arm / _subsets / _rows，取 term_present_compliance_new
子集内每题的 corrected gain（k=1 与 k=5），做**精确符号检验**（配对二值数据，无并列时
即 McNemar 的精确形式），再对 6 个模型做 Holm 校正（family α = 0.05）。
输出同时落盘 rag_leak/out_stratum_holm.json。
"""
import json
import math
import os
from pathlib import Path

from rag_leak.analyze_kaxis import load_arm, _rows, _subsets

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))

MODELS = [
    ("Qwen3-0.6B",        "out_b8_fix_k{k}_06b", "pilot_Qwen3-0.6B_"),
    ("Qwen3-1.7B",        "out_b8_fix_k{k}_17b", "pilot_Qwen3-1.7B_"),
    ("Qwen3-4B",          "out_b8_fix_k{k}_4b",  "pilot_Qwen3-4B_"),
    ("Qwen3-4B-Instruct", "out_b8_fix_k{k}_4bi", "pilot_Qwen3-4B-Instruct_"),
    # 8B 是参考模型，目录不带后缀（out_b8_fix_k{k}）
    ("Qwen3-8B",          "out_b8_fix_k{k}",     "pilot_Qwen3-8B_"),
    ("Qwen3.5-4B-Base",   "out_b8_fix_k{k}_q35", "pilot_Qwen_Qwen3.5-4B-Base_"),
]


def sign_test(diffs):
    pos = sum(1 for v in diffs if v > 0)
    neg = sum(1 for v in diffs if v < 0)
    n = pos + neg
    tail = min(pos, neg)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(tail + 1)) / (2 ** n)) if n else 1.0
    return pos, neg, len(diffs) - n, p


def main():
    rows_out = []
    for name, pat, nf in MODELS:
        a1 = load_arm(ROOT, 1, pat, nf)
        a5 = load_arm(ROOT, 5, pat, nf)
        ids = sorted(a1["fourarm"])
        sub = _subsets([a1, a5], ids, None)["term_present_compliance_new"]
        r1 = {r.question_id: r for r in _rows(a1, sub)}
        r5 = {r.question_id: r for r in _rows(a5, sub)}
        diffs = []
        for qid in sub:
            x, y = r1[qid], r5[qid]
            cg1 = x.d - x.c
            cg5 = y.d - y.c
            diffs.append(cg5 - cg1)          # k=5 减 k=1；负 = k=1 更好
        pos, neg, zero, p = sign_test(diffs)
        mean = sum(diffs) / len(diffs)
        rows_out.append(dict(model=name, n=len(sub), delta_k5_minus_k1=mean,
                             positive=pos, negative=neg, tied=zero, p_raw=p))

    # Holm（step-down）
    order = sorted(range(len(rows_out)), key=lambda i: rows_out[i]["p_raw"])
    m = len(rows_out)
    prev = 0.0
    for rank, i in enumerate(order):
        adj = min(1.0, max(prev, (m - rank) * rows_out[i]["p_raw"]))
        rows_out[i]["p_holm"] = adj
        rows_out[i]["rank"] = rank + 1
        prev = adj
    for r in rows_out:
        r["significant_holm_05"] = r["p_holm"] < 0.05

    print("%-20s %5s %10s %6s %6s %6s %10s %10s %s"
          % ("model", "n", "Δ(k5-k1)", "+", "-", "tie", "p_raw", "p_Holm", "Holm .05"))
    print("-" * 104)
    for r in rows_out:
        print("%-20s %5d %+10.4f %6d %6d %6d %10.2e %10.2e %s"
              % (r["model"], r["n"], r["delta_k5_minus_k1"], r["positive"], r["negative"],
                 r["tied"], r["p_raw"], r["p_holm"], "显著" if r["significant_holm_05"] else "不显著"))
    nsig = sum(1 for r in rows_out if r["significant_holm_05"])
    print("-" * 104)
    print("Holm 校正后仍显著：%d/%d" % (nsig, len(rows_out)))

    out = ROOT / "out_stratum_holm.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(dict(family_alpha=0.05, method="Holm step-down on exact sign test",
                       subset="term_present_compliance_new", results=rows_out),
                  f, ensure_ascii=False, indent=1)
    print("已写 %s" % out)


if __name__ == "__main__":
    main()
