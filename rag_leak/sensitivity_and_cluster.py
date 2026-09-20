# -*- coding: utf-8 -*-
"""sensitivity_and_cluster.py —— 外部评审要求的两项稳健性补算（离线、只读产物）。

A. **顺从层切分的敏感性**：同一个"k=1 vs k=5 校正增益配对差"在三套嵌套子集定义下是否同号、
   是否同样显著；并给出 leave-one-model-out 的合并结果（排除"一个模型撑起结论"）。
      structural_term_present  ⊃  term_present_oracle_ok  ⊃  term_present_compliance_new
      （宽 → 中 → 窄：越窄＝越严格地只保留"模型确实采纳了植入值"的题）

B. **按"借值"聚类的 bootstrap**：借来的值可能被多道题共用 → 题间不独立。
   题级重抽会低估方差；这里改为**按 new_key 整簇重抽**，给出对照 CI。

产物：rag_leak/out_sensitivity.json
"""
import json
import os
import random
from collections import defaultdict
from pathlib import Path

from rag_leak.analyze_kaxis import load_arm, _rows, _subsets

ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
B = 10000
SEED = 20260903

MODELS = [
    ("Qwen3-0.6B",        "out_b8_fix_k{k}_06b", "pilot_Qwen3-0.6B_"),
    ("Qwen3-1.7B",        "out_b8_fix_k{k}_17b", "pilot_Qwen3-1.7B_"),
    ("Qwen3-4B",          "out_b8_fix_k{k}_4b",  "pilot_Qwen3-4B_"),
    ("Qwen3-4B-Instruct", "out_b8_fix_k{k}_4bi", "pilot_Qwen3-4B-Instruct_"),
    ("Qwen3-8B",          "out_b8_fix_k{k}",     "pilot_Qwen3-8B_"),
    ("Qwen3.5-4B-Base",   "out_b8_fix_k{k}_q35", "pilot_Qwen_Qwen3.5-4B-Base_"),
]
SUBSETS = ["structural_term_present", "term_present_oracle_ok", "term_present_compliance_new"]


def ci(dist, alpha=0.05):
    s = sorted(dist)
    n = len(s)
    return s[int(alpha / 2 * n)], s[min(n - 1, int((1 - alpha / 2) * n))]


def boot_ci(values, B=B, rng=None):
    rng = rng or random.Random(SEED)
    n = len(values)
    return ci([sum(values[rng.randrange(n)] for _ in range(n)) / n for _ in range(B)])


def boot_ci_cluster(values, clusters, B=B, rng=None):
    """按簇整块重抽（簇 = 借值 new_key）。"""
    rng = rng or random.Random(SEED)
    by = defaultdict(list)
    for v, c in zip(values, clusters):
        by[c].append(v)
    keys = list(by)
    m = len(keys)
    out = []
    for _ in range(B):
        pool = []
        for _ in range(m):
            pool.extend(by[keys[rng.randrange(m)]])
        out.append(sum(pool) / len(pool))
    return ci(out), m


def load_model(pat, nf):
    a1, a5 = load_arm(ROOT, 1, pat, nf), load_arm(ROOT, 5, pat, nf)
    ids = sorted(a1["fourarm"])
    subs = _subsets([a1, a5], ids, None)
    r1 = {r.question_id: r for r in _rows(a1, ids)}
    r5 = {r.question_id: r for r in _rows(a5, ids)}
    return ids, subs, r1, r5, a1["subs"]


def main():
    res = {"bootstrap": B, "seed": SEED, "sensitivity": {}, "cluster": {}}

    # ---------------- A. 切分敏感性 ----------------
    print("=" * 92)
    print("A. 顺从层切分敏感性：Δ校正增益（k=5 减 k=1，负 = k=1 更高）")
    print("=" * 92)
    print("%-20s %-26s %6s %9s %-22s %s" % ("model", "subset", "n", "delta", "95% CI", "排零"))
    print("-" * 92)
    for name, pat, nf in MODELS:
        ids, subs, r1, r5, _ = load_model(pat, nf)
        res["sensitivity"][name] = {}
        for sub in SUBSETS:
            sel = subs[sub]
            diffs = [(r5[q].d - r5[q].c) - (r1[q].d - r1[q].c) for q in sel]
            pt = sum(diffs) / len(diffs)
            lo, hi = boot_ci(diffs)
            excl = lo > 0 or hi < 0
            res["sensitivity"][name][sub] = dict(n=len(sel), delta=pt, ci=[lo, hi], excludes_zero=excl)
            print("%-20s %-26s %6d %+9.4f [%+.3f,%+.3f]%s %s"
                  % (name, sub, len(sel), pt, lo, hi, " " * 4, "是" if excl else "否"))

    # leave-one-model-out（在最窄的 compliance_new 上）
    print()
    print("leave-one-model-out（子集 = term_present_compliance_new，合并各模型的题）")
    pooled = {}
    for name, pat, nf in MODELS:
        ids, subs, r1, r5, _ = load_model(pat, nf)
        sel = subs["term_present_compliance_new"]
        pooled[name] = [(r5[q].d - r5[q].c) - (r1[q].d - r1[q].c) for q in sel]
    for drop in [None] + [m[0] for m in MODELS]:
        vals = [v for k, xs in pooled.items() if k != drop for v in xs]
        pt = sum(vals) / len(vals)
        lo, hi = boot_ci(vals, B=2000)
        tag = "全部" if drop is None else "剔除 " + drop
        print("  %-24s n=%-5d Δ=%+.4f CI=[%+.3f,%+.3f] %s"
              % (tag, len(vals), pt, lo, hi, "排零" if (lo > 0 or hi < 0) else "含零"))
        res.setdefault("leave_one_out", {})[tag] = dict(n=len(vals), delta=pt, ci=[lo, hi])

    # ---------------- B. 按借值聚类的 bootstrap ----------------
    print()
    print("=" * 92)
    print("B. 按「借值 new_key」聚类重抽 vs 题级重抽（最窄子集，primary 口径）")
    print("=" * 92)
    print("%-20s %6s %6s %10s %-22s %-22s" % ("model", "n题", "簇数", "delta", "题级 CI", "聚类 CI"))
    print("-" * 92)
    for name, pat, nf in MODELS:
        ids, subs, r1, r5, subrec = load_model(pat, nf)
        sel = subs["term_present_compliance_new"]
        diffs = [(r5[q].d - r5[q].c) - (r1[q].d - r1[q].c) for q in sel]
        clusters = [subrec[q]["new_key"] for q in sel]
        lo1, hi1 = boot_ci(diffs)
        (lo2, hi2), ncl = boot_ci_cluster(diffs, clusters)
        pt = sum(diffs) / len(diffs)
        print("%-20s %6d %6d %+10.4f [%+.3f,%+.3f]%s [%+.3f,%+.3f]%s"
              % (name, len(sel), ncl, pt, lo1, hi1, " " * 3, lo2, hi2, ""))
        res["cluster"][name] = dict(n_items=len(sel), n_clusters=ncl, delta=pt,
                                    ci_item=[lo1, hi1], ci_cluster=[lo2, hi2],
                                    item_excl=(lo1 > 0 or hi1 < 0), cluster_excl=(lo2 > 0 or hi2 < 0))

    out = ROOT / "out_sensitivity.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print()
    print("已写 %s" % out)


if __name__ == "__main__":
    main()
