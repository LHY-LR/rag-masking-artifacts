"""论文主图生成（可复跑，零依赖新增：venv 里已有 matplotlib/numpy）。

数据来源：`论文/Claims_Ledger.md`（写作时唯一取数来源）。
**本脚本里绝大多数数字都是手抄自账本的常量，不重新计算**——这样图与账本一一对应，
改数字必须同时改两处（是有意的摩擦，防止图文不一致）。

**唯一例外：`HP_DID`（Fig.~4b 的 HotpotQA 各模型 DiD 与 CI）改为直接读
`rag_leak/out_review_fixes.json`**（= 冻结 TOST 程序的产物，已随发布包一起提供）。
变更理由（2026-09-19，实测）：手抄路径已经出过一次无人发现的事故——原 `HP_DID` 里
Qwen3.5-4B 的 CI `[-0.0150,+0.0510]` 在**任何**表格顺序下都复现不出来（实测
`[-0.0178,+0.0483]`），即图与冻结程序不一致。改为读产物后，图恒等于冻结程序的输出；
账本仍需手写，故"图文一致"的摩擦只保留在账本一侧。

用法（论文/ 目录）：
  python paper/make_figures.py
产出：paper/figures/fig{1..5}_*.pdf
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

plt.rcParams.update({
    "figure.dpi": 150,
    "savefig.bbox": "tight",
    # 显式钉死无衬线字体：本机全局 matplotlibrc 里配了 SimHei，
    # 不写这一行的话部分刻度/文字会落到中文字体上（英文论文里字体不一致，且字距偏宽）。
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "pdf.fonttype": 42,      # 嵌入 TrueType，避免 Type3 字体（投稿要求）
    "ps.fonttype": 42,
})

C_A, C_B, C_C, C_D = "#4C72B0", "#55A868", "#C44E52", "#8172B2"
C_HP = "#937860"
OUT = Path(__file__).resolve().parent / "figures"

# ---------------------------------------------------------------- 账本数字
# 主张①：TriviaQA C 线 v2（共同 432 题，v3 口径）；masking 的 CI = −DiD 的 CI
CLINE = [
    #  标签,        masking, ci_lo, ci_hi, 显著
    ("Qwen3-0.6B",        0.0324, -0.0046, 0.0718, False),
    ("Qwen3-1.7B",        0.0949,  0.0463, 0.1458, True),
    ("Qwen3-4B",          0.1343,  0.0810, 0.1852, True),
    ("Qwen3-4B-Instruct", 0.2130,  0.1620, 0.2639, True),
    ("Qwen3-8B",          0.2315,  0.1759, 0.2847, True),
]
# 主张①：B 线 v2 六模型（n=432）
BLINE = [
    #  标签,        k=1,   k=5,    k=1 的 95% CI,     k=5 的 95% CI
    ("0.6B",        0.0370, 0.0347, (-0.0000, 0.0741), (-0.0069, 0.0764)),
    ("1.7B",        0.0856, 0.1042, (0.0394, 0.1343), (0.0602, 0.1505)),
    ("4B",          0.1551, 0.1134, (0.1019, 0.2083), (0.0602, 0.1667)),
    ("4B-Instruct", 0.2245, 0.2245, (0.1759, 0.2755), (0.1736, 0.2755)),
    ("8B",          0.2569, 0.1759, (0.2037, 0.3079), (0.1204, 0.2315)),
    ("Qwen3.5-4B",  0.3056, 0.2338, (0.2500, 0.3588), (0.1806, 0.2894)),
]
# 主张⑤主口径：顺从层配对 Δ校正（k=5 − k=1）
STRATUM = [(-0.1579, -0.2368, -0.0789), (-0.4071, -0.5071, -0.3071),
           (-0.1010, -0.1768, -0.0253), (-0.0929, -0.1694, -0.0164),
           (-0.1237, -0.1989, -0.0484), (-0.1120, -0.1701, -0.0539)]
# 主张②：前提分解（8B）
PRECOND = {
    "TriviaQA (v2)": dict(adv=0.4653, cost=0.2338),
    "HotpotQA (v2)": dict(adv=0.0458, cost=0.0534),
}
# 主张②：HotpotQA v2 各模型 DiD —— 从冻结 TOST 产物读取（理由见文件头 docstring）
_HP_ORDER = ["0.6B", "1.7B", "4B", "8B", "Qwen3.5-4B"]
_HP_LABEL = {"Qwen3.5-4B": "Q3.5-4B"}


def _load_hp_did() -> list[tuple[str, float, float, float]]:
    p = Path(__file__).resolve().parent.parent / "rag_leak" / "out_review_fixes.json"
    did = json.loads(p.read_text(encoding="utf-8"))["did"]
    out = []
    for k, v in did.items():
        if not k.startswith("HotpotQA_"):
            continue
        tag = k[len("HotpotQA_"):]
        out.append((tag, v["did"], v["ci95"][0], v["ci95"][1]))
    known = [t for t in out if t[0] in _HP_ORDER]
    unknown = [t for t in out if t[0] not in _HP_ORDER]
    if unknown:
        raise SystemExit("out_review_fixes.json 出现未登记标签 %s，请加入 _HP_ORDER（否则顺序不定）"
                         % [t[0] for t in unknown])
    return sorted(known, key=lambda t: _HP_ORDER.index(t[0]))


HP_DID = _load_hp_did()
# 主张①：跨世代闭卷 a
GEN = {"TriviaQA": (0.3744, 0.5493), "HotpotQA": (0.0560, 0.0560)}
# 主张③：缺陷分类
DEFECTS = {"wrong position": 17, "malformed value": 3,
           "new = true answer": 1, "self-contradictory": 1}
# 主张③：两处修复对 B 线 8B 的影响（v0 → v2）
ABL = {"masking (k=1)": (0.1839, 0.2569),
       "masking (k=5)": (0.0897, 0.1759),
       "stratum $\\Delta$": (-0.1500, -0.1237),
       "k-axis $\\Delta$mask": (-0.0942, -0.0810)}


def _save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.savefig(p)
    fig.savefig(p.with_suffix(".png"))     # 同时出 PNG：给老师预览用，PDF 用于投稿
    plt.close(fig)
    print(f"  已写 {p.name} + {p.with_suffix('.png').name}")


# ---------------------------------------------------------------- Fig 1 方法
def fig_method() -> None:
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.set_xlim(0, 10); ax.set_ylim(-0.95, 4); ax.axis("off")
    boxes = [
        (0.3, 2.6, "a  closed-book\noriginal answer", C_A),
        (0.3, 0.6, "c  closed-book\nsubstituted key", C_C),
        (4.0, 2.6, "b  open-book\noriginal passage", C_B),
        (4.0, 0.6, "d  open-book\nsubstituted passage", C_D),
    ]
    for x, y, t, c in boxes:
        ax.add_patch(FancyBboxPatch((x, y), 2.3, 1.1, boxstyle="round,pad=0.08",
                                    fc=c, ec="none", alpha=0.85))
        ax.text(x + 1.15, y + 0.55, t, ha="center", va="center",
                color="white", fontsize=8.5, linespacing=1.35)
    ax.add_patch(FancyArrowPatch((2.6, 3.15), (4.0, 3.15), arrowstyle="-|>",
                                 mutation_scale=12, color="0.3"))
    ax.text(3.3, 3.32, "evidence", ha="center", fontsize=8, color="0.3")
    ax.add_patch(FancyArrowPatch((2.6, 1.15), (4.0, 1.15), arrowstyle="-|>",
                                 mutation_scale=12, color="0.3"))
    ax.text(3.3, 1.32, "evidence", ha="center", fontsize=8, color="0.3")
    ax.annotate("", xy=(7.6, 3.15), xytext=(6.3, 3.15),
                arrowprops=dict(arrowstyle="-", color="0.4"))
    ax.annotate("", xy=(7.6, 1.15), xytext=(6.3, 1.15),
                arrowprops=dict(arrowstyle="-", color="0.4"))
    ax.add_patch(FancyBboxPatch((7.6, 2.6), 2.1, 1.1, boxstyle="round,pad=0.08",
                                fc="white", ec=C_B, lw=1.4))
    ax.text(8.65, 3.15, "apparent gain\n$b-a$", ha="center", va="center", fontsize=9)
    ax.add_patch(FancyBboxPatch((7.6, 0.6), 2.1, 1.1, boxstyle="round,pad=0.08",
                                fc="white", ec=C_D, lw=1.4))
    ax.text(8.65, 1.15, "corrected gain\n$d-c$", ha="center", va="center", fontsize=9)
    # 位置很讲究：第二排方框的底边在 y=0.6，方程文字块高约 0.6 个数据单位，
    # 所以底边必须放到 -0.7 以下才不会压住方框（paper/check_fig1_layout.py 会实测断言）。
    ax.text(5.0, -0.72,
            r"masking $=-(b-d)-(c-a)\;=\;(a-c)-(b-d)$"
            "\n" r"$=$ memory advantage $-$ manipulation cost",
            ha="center", va="bottom", fontsize=9.5, linespacing=1.5)
    # 不画图内标题：LaTeX 的 \caption 已经写了同一句话，重复两次是排版事故
    # （paper/check_fig1_layout.py 会连这条一起复核布局）
    _save(fig, "fig1_method.pdf")


# ---------------------------------------------------------------- Fig 2 规模
def fig_scale() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    ax = axes[0]
    labels = [c[0].replace("Qwen3-", "") for c in CLINE]
    vals = np.array([c[1] for c in CLINE])
    lo = np.array([c[2] for c in CLINE]); hi = np.array([c[3] for c in CLINE])
    x = np.arange(len(vals))
    ax.errorbar(x, vals, yerr=[vals - lo, hi - vals], fmt="o-", color=C_A,
                capsize=3, lw=1.5, ms=5)
    ax.axhline(0, color="0.6", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("masking (95% CI)")
    ax.set_title("(a) TriviaQA, C-line, $k$=1", loc="left")
    ax.set_ylim(-0.02, 0.31)

    ax = axes[1]
    x = np.arange(len(BLINE)); w = 0.38
    ax.bar(x - w / 2, [b[1] for b in BLINE], w, label="$k$=1", color=C_A)
    ax.bar(x + w / 2, [b[2] for b in BLINE], w, label="$k$=5", color=C_D)
    ax.set_xticks(x); ax.set_xticklabels([b[0] for b in BLINE], rotation=20, ha="right")
    ax.set_ylabel("masking"); ax.legend(frameon=False)
    ax.set_title("(b) TriviaQA, B-line, six models", loc="left")
    fig.tight_layout()
    _save(fig, "fig3_scale.pdf")


# ---------------------------------------------------------------- Fig 3 前提
def fig_precondition() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.7),
                             gridspec_kw={"width_ratios": [1.5, 1.0, 0.75]})
    ax = axes[0]
    names = list(PRECOND)
    x = np.arange(len(names)); w = 0.34
    adv = [PRECOND[n]["adv"] for n in names]
    cost = [PRECOND[n]["cost"] for n in names]
    ax.bar(x - w / 2, adv, w, label="memory advantage $(a-c)$", color=C_A)
    ax.bar(x + w / 2, cost, w, label="manipulation cost $(b-d)$", color=C_HP)
    for i, n in enumerate(names):
        m = PRECOND[n]["adv"] - PRECOND[n]["cost"]
        ax.text(i, max(adv[i], cost[i]) + 0.02, f"masking\n{m:+.3f}", ha="center", fontsize=8)
    ax.set_xticks(x); ax.set_xticklabels(["TriviaQA", "HotpotQA"])
    # 纵轴是**差值**（a−c 与 b−d），不是准确率本身 —— 原写 "accuracy" 是错的
    # 上界抬到 0.78：给图例留出空间，否则图例会压住 "masking +0.231" 标注
    ax.set_ylim(0, 0.78); ax.set_ylabel("accuracy difference")
    ax.legend(frameon=False, loc="upper center", fontsize=7.5)
    ax.set_title("(a) 8B: the precondition", loc="left")

    ax = axes[1]
    lab = [_HP_LABEL.get(h[0], h[0]) for h in HP_DID]
    v = np.array([h[1] for h in HP_DID])
    lo = np.array([h[2] for h in HP_DID]); hi = np.array([h[3] for h in HP_DID])
    x = np.arange(len(v))
    ax.errorbar(x, v, yerr=[v - lo, hi - v], fmt="s", color=C_HP, capsize=3, ms=6)
    ax.axhline(0, color="0.6", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(lab)
    ax.set_ylabel("DiD (95% CI)"); ax.set_ylim(-0.06, 0.15)
    ax.set_title("(b) HotpotQA: vanishes", loc="left")

    ax = axes[2]
    g = np.arange(2); w2 = 0.34
    ax.bar(g - w2 / 2, [GEN["TriviaQA"][0], GEN["HotpotQA"][0]], w2,
           color="0.75", label="Qwen3-4B")
    ax.bar(g + w2 / 2, [GEN["TriviaQA"][1], GEN["HotpotQA"][1]], w2,
           color=C_A, label="Qwen3.5-4B")
    ax.set_xticks(g); ax.set_xticklabels(["Triv.", "Hotp."])
    ax.set_ylim(0, 0.68); ax.set_ylabel("closed-book accuracy $a$")
    ax.legend(frameon=False, fontsize=7)
    ax.set_title("(c) cross-generation", loc="left")
    fig.tight_layout()
    _save(fig, "fig4_precondition.pdf")


# ---------------------------------------------------------------- Fig 4 k 轴
def fig_kaxis() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8))
    ax = axes[0]
    x = np.arange(len(BLINE)); w = 0.38
    v1 = np.array([b[1] for b in BLINE]); v5 = np.array([b[2] for b in BLINE])
    e1lo = np.array([b[3][0] for b in BLINE]); e1hi = np.array([b[3][1] for b in BLINE])
    e5lo = np.array([b[4][0] for b in BLINE]); e5hi = np.array([b[4][1] for b in BLINE])
    ax.bar(x - w / 2, v1, w, label="$k$=1", color=C_A)
    ax.bar(x + w / 2, v5, w, label="$k$=5", color=C_D)
    # 逐格 95% CI（不对称，用 yerr 的上下分量）。只有 0.6B 两格的区间触及 0。
    ax.errorbar(x - w / 2, v1, yerr=[v1 - e1lo, e1hi - v1], fmt="none",
                ecolor="0.25", capsize=2.5, lw=0.9)
    ax.errorbar(x + w / 2, v5, yerr=[v5 - e5lo, e5hi - v5], fmt="none",
                ecolor="0.25", capsize=2.5, lw=0.9)
    ax.set_xticks(x); ax.set_xticklabels([b[0] for b in BLINE], rotation=20, ha="right")
    ax.set_ylabel("masking (95% CI)"); ax.legend(frameon=False)
    ax.set_title("(a) full sample", loc="left")
    ax = axes[1]
    v = np.array([s[0] for s in STRATUM])
    lo = np.array([s[1] for s in STRATUM]); hi = np.array([s[2] for s in STRATUM])
    ax.bar(x, v, color=C_B)
    ax.errorbar(x, v, yerr=[v - lo, hi - v], fmt="none", ecolor="0.25", capsize=3)
    ax.axhline(0, color="0.6", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels([b[0] for b in BLINE], rotation=20, ha="right")
    # 与正文 Table\ref{tab:bline} 的 Δ_strat 同符号（k=5 − k=1；负值 = k=1 更高）
    ax.set_ylabel("corrected gain: $k$=5 $-$ $k$=1")
    ax.set_title("(b) compliance stratum (post-hoc cut; 6/6 significant)", loc="left")
    fig.tight_layout()
    _save(fig, "fig5_kaxis.pdf")


# ---------------------------------------------------------------- Fig 5 效度
def fig_validity() -> None:
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))
    ax = axes[0]
    ks = list(DEFECTS); vs = [DEFECTS[k] for k in ks]
    ax.barh(np.arange(len(ks)), vs, color=C_C)
    ax.set_yticks(np.arange(len(ks))); ax.set_yticklabels(ks, fontsize=7.5)
    ax.invert_yaxis(); ax.set_xlabel("items")
    ax.set_title("(a) 22/90 invalid (24.4%)", loc="left", fontsize=9)

    ax = axes[1]
    obs = [0.8227, 0.7804]
    ax.bar([0, 1], obs, color=[C_A, "0.6"])
    ax.axhline(0.8, color=C_B, ls="--", lw=1.2)
    ax.text(1.45, 0.803, "$\\kappa\\geq0.8$", color=C_B, fontsize=7.5, va="bottom", ha="right")
    ax.set_xticks([0, 1]); ax.set_xticklabels(["all 90", "n=86"], fontsize=8)
    ax.set_ylim(0.70, 0.86); ax.set_ylabel("Cohen's $\\kappa$")
    ax.set_title("(b) human audit", loc="left", fontsize=9)

    ax = axes[2]
    x = np.arange(len(ABL)); w = 0.38
    ax.bar(x - w / 2, [v[0] for v in ABL.values()], w, label="v0", color="0.7")
    ax.bar(x + w / 2, [v[1] for v in ABL.values()], w, label="v2", color=C_A)
    ax.axhline(0, color="0.6", lw=0.8, ls="--")
    ax.set_xticks(x); ax.set_xticklabels(["mask\n$k$=1", "mask\n$k$=5",
                                          "strat.\n$\\Delta$", "$k$-ax.\n$\\Delta$"],
                                         fontsize=6.5)
    ax.legend(frameon=False, fontsize=7.5)
    ax.set_title("(c) cleaning: v0 vs v2", loc="left", fontsize=9)
    fig.tight_layout()
    _save(fig, "fig2_validity.pdf")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.parse_args()
    print("生成论文主图（数字手抄自 Claims_Ledger.md）：")
    fig_method(); fig_scale(); fig_precondition(); fig_kaxis(); fig_validity()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
