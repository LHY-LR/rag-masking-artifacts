r"""语料残余缺陷率的"召回校正"估计（Lincoln–Petersen 截获-再截获）—— §Limitations 那个 ≈21% 的取数脚本。

背景（为什么补这个脚本）
------------------------
论文 Limitations 里写："同一个召回校正估计量把**修复后**语料的残余率定在 ≈21%
（95% 区间 14.5–27.4%；来自 432 条里 37 条被复核器标记、复核器实测召回 0.41），修复前 ≈24%。"
这组数字此前**没有脚本**（只有散文）。本脚本把估计量与区间**显式定义并可复算**。

估计量（本脚本即唯一权威定义）
------------------------------
把"人审标记"与"复核器（模型）标记"看作对同一批缺陷的两次截获：
    n1 = 复核器标记数, n2 = 人审标记数, m = 两者交集
    N̂  = n1·n2/m                （Lincoln–Petersen）
    rate = N̂ / n_items
    recall = m / n2             （复核器相对人审的召回，论文引用的 0.41）
两点实现细节：
1. **Chapman 小样本修正**并存上报：N̂_c = (n1+1)(n2+1)/(m+1) − 1。m 较小时 LP 有偏，两者一起给。
2. **区间**用题级自举（重抽题，B=10000、seed=20260903）：人审/复核器标记集是**固定的题集**，
   自举只反映"这批题是从语料里抽出来的"这一层不确定性；m=0 的自举副本丢弃并计数（LP 无定义）。
   ⚠️ 这不是唯一的合法区间（解析的 Seber 方差也可），论文里注明所用方法。

"转移标记"的含义
----------------
复核器只在修复前语料上跑过 ⇒ 修复后语料用**按 question_id 转移**的标记计分（论文已作 caveat）。
本脚本同时打印转移过程中的损耗（有多少标记题落在被剔除的 15 条里）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ == "" or __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

HERE = Path(__file__).parent
REVIEW = HERE / "out_review_round2.json"
POOLS = {"pre_fix_446": "out_b8_full_k1", "fixed_432": "out_b8_fix_k1"}
SEED = 20260903
B = 10000


def _qids(dname: str) -> list[str]:
    p = sorted((HERE / dname).glob("*_fourarm.jsonl"))[0]
    return [json.loads(x)["question_id"] for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]


def lp(n1: int, n2: int, m: int) -> dict:
    return dict(n1=n1, n2=n2, m=m,
                recall=(m / n2 if n2 else None),
                N_lp=(n1 * n2 / m if m else None),
                N_chapman=((n1 + 1) * (n2 + 1) / (m + 1) - 1) if m else None)


def main(argv=None) -> int:
    import numpy as np
    ap = argparse.ArgumentParser(description="残余缺陷率召回校正估计")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--out", default=str(HERE / "out_residual_rate.json"))
    args = ap.parse_args(argv)

    rev = json.loads(REVIEW.read_text(encoding="utf-8"))
    human, model = set(rev["human_ids"]), set(rev["model_ids"])
    res: dict = dict(bootstrap=args.boot, seed=SEED,
                     source=str(REVIEW.name), estimator="Lincoln-Petersen (+Chapman)",
                     human_n=len(human), model_n=len(model),
                     overlap=len(human & model), union=len(human | model),
                     recall=round(len(human & model) / len(human), 4), pools={})
    print(f"人审 {len(human)} 条，复核器 {len(model)} 条，交集 {len(human & model)}，"
          f"并集 {len(human | model)}；复核器召回 = {res['recall']:.4f}")
    rng = np.random.default_rng(SEED)
    for name, d in POOLS.items():
        qids = _qids(d)
        n = len(qids)
        h = human & set(qids)
        mo = model & set(qids)
        v = lp(len(mo), len(h), len(mo & h))
        n_items_lost = len(model - set(qids))
        draws, undef = [], 0
        for _ in range(args.boot):
            pick = rng.integers(0, n, n)
            sel = [qids[i] for i in pick]
            n1 = sum(1 for q in sel if q in model)
            n2 = sum(1 for q in sel if q in human)
            m = sum(1 for q in sel if q in human and q in model)
            if m == 0:
                undef += 1
                continue
            draws.append((n1 * n2 / m) / n)
        lo, hi = np.percentile(draws, [2.5, 97.5]) if draws else (None, None)
        v.update(pool=name, dir=d, n_items=n,
                 n_human=len(h), n_model=len(mo), n_both=len(mo & h),
                 rate_lp=(v["N_lp"] / n if v["N_lp"] else None),
                 rate_chapman=(v["N_chapman"] / n if v["N_chapman"] else None),
                 ci_lp=[round(float(lo), 4), round(float(hi), 4)] if draws else None,
                 ci_undef_replicates=undef,
                 model_flags_lost_in_pool_change=n_items_lost)
        res["pools"][name] = v
        print(f"\n[{name}] n={n}  复核器标记={len(mo)}  人审={len(h)}  交集={len(mo & h)}"
              f"（转移中丢失的标记题 {n_items_lost}）")
        print(f"   召回 = {v['recall']:.4f}   N̂(LP) = {v['N_lp']:.1f} → 率 = {v['rate_lp']:.4f}"
              f"   N̂(Chapman) = {v['N_chapman']:.1f} → 率 = {v['rate_chapman']:.4f}")
        if draws:
            print(f"   题级自举 95% 区间 = [{lo:.4f}, {hi:.4f}]（m=0 丢弃 {undef} 个副本）")
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
