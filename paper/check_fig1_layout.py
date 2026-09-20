# -*- coding: utf-8 -*-
"""check_fig1_layout.py —— 实测 fig1（四臂示意图）里文字与方框是否重叠。

为什么单独写一个：fig1 是**手工放坐标**的示意图（其它图由坐标轴自动布局），
文字一旦压到方框上，只有肉眼能看出来，而肉眼在不同缩放下并不可靠。
这里用 renderer 的实际包围盒做断言，纳入常规自检。

用法：python paper/check_fig1_layout.py      （退出码 0 = 无重叠）
"""
import importlib.util
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mf", HERE / "make_figures.py")
mf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mf)

fig, ax = plt.subplots(figsize=(7.2, 3.0))
ax.set_xlim(0, 10); ax.set_ylim(-0.95, 4); ax.axis("off")
patches, texts = [], []
for x, y, t, c in [(0.3, 2.6, "a  closed-book\noriginal answer", mf.C_A),
                   (0.3, 0.6, "c  closed-book\nsubstituted key", mf.C_C),
                   (4.0, 2.6, "b  open-book\noriginal passage", mf.C_B),
                   (4.0, 0.6, "d  open-book\nsubstituted passage", mf.C_D)]:
    p = FancyBboxPatch((x, y), 2.3, 1.1, boxstyle="round,pad=0.08", fc=c, ec="none", alpha=0.85)
    ax.add_patch(p); patches.append(p)
    texts.append(ax.text(x + 1.15, y + 0.55, t, ha="center", va="center",
                         color="white", fontsize=8.5, linespacing=1.35))
for x, y, lab in [(7.6, 2.6, "apparent gain\n$b-a$"), (7.6, 0.6, "corrected gain\n$d-c$")]:
    p = FancyBboxPatch((x, y), 2.1, 1.1, boxstyle="round,pad=0.08", fc="white", ec=mf.C_B, lw=1.4)
    ax.add_patch(p); patches.append(p)
    texts.append(ax.text(x + 1.05, y + 0.55, lab, ha="center", va="center", fontsize=9))
eq = ax.text(5.0, -0.72,
             r"masking $=-(b-d)-(c-a)\;=\;(a-c)-(b-d)$"
             "\n" r"$=$ memory advantage $-$ manipulation cost",
             ha="center", va="bottom", fontsize=9.5, linespacing=1.5)
fig.canvas.draw()
r = fig.canvas.get_renderer()


def bbox(o):
    return o.get_window_extent(renderer=r) if hasattr(o, "get_window_extent") else o.get_extents()


def hit(a, b):
    return not (a.x1 < b.x0 or a.x0 > b.x1 or a.y1 < b.y0 or a.y0 > b.y1)


eb = bbox(eq)
print("方程包围盒: x=[%.1f, %.1f]  y=[%.1f, %.1f]" % (eb.x0, eb.x1, eb.y0, eb.y1))
problems = []
for t in texts:
    tb = bbox(t)
    if hit(tb, eb):
        problems.append("文字与方程重叠: %r" % t.get_text().replace("\n", " / ")[:30])
for p in patches:
    pb = bbox(p)
    if hit(pb, eb):
        problems.append("方框与方程重叠: x=[%.1f,%.1f] y=[%.1f,%.1f]" % (pb.x0, pb.x1, pb.y0, pb.y1))
if problems:
    print("\n❌ 发现 %d 处重叠：" % len(problems))
    for x in problems:
        print("   -", x)
    sys.exit(1)
print("\n✅ fig1 文字与所有方框均无重叠（实测包围盒，非目视）")
sys.exit(0)
