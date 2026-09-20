# -*- coding: utf-8 -*-
"""cline_holm.py —— C 线 5 个模型的多重比较校正（外部评审要求：B 线做了 Holm，C 线没做）。

做法与 `holm_stratum.py` 同一统计族：对每题的四臂取
`DiD_i = (b_i - a_i) - (d_i - c_i)`（masking 的逐题贡献，正值 = 有掩盖），
做**精确符号检验**（配对、无并列时即 McNemar 精确形式），再对 5 个模型做 **Holm 校正**
（family α = 0.05）。同时报出未校正 p 与 Holm 后的判定，便于论文只写一句话。

产物：`rag_leak/out_cline_holm.json`
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))

MODELS = [
    ("Qwen3-0.6B",        "out_s6_trivia_fix_06b",  "pilot_Qwen3-0.6B_"),
    ("Qwen3-1.7B",        "out_s6_trivia_fix_17b",  "pilot_Qwen3-1.7B_"),
    ("Qwen3-4B",          "out_s6_trivia_fix_4b",   "pilot_Qwen3-4B_"),
    ("Qwen3-4B-Instruct", "out_s6_trivia_fix_4bi",  "pilot_Qwen3-4B-Instruct_"),
    ("Qwen3-8B",          "out_s6_trivia_fix_8b",   "pilot_Qwen3-8B_"),
]


def sign_test(diffs) -> tuple[int, int, float]:
    """精确双尾符号检验（去并列）。"""
    pos = sum(1 for v in diffs if v > 0)
    neg = sum(1 for v in diffs if v < 0)
    n = pos + neg
    if n == 0:
        return pos, neg, 1.0
    k = min(pos, neg)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))
    return pos, neg, p


def main() -> int:
    rows_out = []
    for name, d, prefix in MODELS:
        p = ROOT / d / (prefix + "fourarm.jsonl")
        if not p.exists():
            print("缺产物", p)
            continue
        recs = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        diffs = [(r["b"] - r["a"]) - (r["d"] - r["c"]) for r in recs]
        n = len(diffs)
        mean_did = sum(diffs) / n
        masking = -mean_did
        pos, neg, pval = sign_test(diffs)
        rows_out.append({"model": name, "n": n, "masking": masking,
                         "pos_items": pos, "neg_items": neg, "p_raw": pval})
        print("%-18s n=%d  masking=%+.4f  逐题 DiD>0: %d / <0: %d  p=%.3g"
              % (name, n, masking, pos, neg, pval))

    # Holm 校正（family α = 0.05）
    m = len(rows_out)
    order = sorted(range(m), key=lambda i: rows_out[i]["p_raw"])
    alpha = 0.05
    prev_reject = True
    for rank, i in enumerate(order):
        thr = alpha / (m - rank)
        rej = prev_reject and (rows_out[i]["p_raw"] <= thr)
        prev_reject = rej
        rows_out[i]["holm_threshold"] = thr
        rows_out[i]["holm_significant"] = rej
        rows_out[i]["p_holm"] = min(1.0, rows_out[i]["p_raw"] * (m - rank))
    print()
    print("Holm（m=%d, α=0.05）：" % m)
    for r in sorted(rows_out, key=lambda x: x["p_raw"]):
        print("  %-18s p=%.3g  p_holm=%.3g  阈值=%.4f  %s"
              % (r["model"], r["p_raw"], r["p_holm"], r["holm_threshold"],
                 "显著" if r["holm_significant"] else "不显著"))
    out = ROOT / "out_cline_holm.json"
    out.write_text(json.dumps({"alpha": alpha, "rows": rows_out}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("已写", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
