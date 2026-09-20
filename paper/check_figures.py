# -*- coding: utf-8 -*-
"""check_figures.py —— 对 paper/figures 做两项客观检查（不需要肉眼看图）。

1. **字体**：图里有没有落回中文字体（SimHei 等）。英文论文里混进 CJK 字体=字体不一致。
2. **裁切**：PNG 的最外圈像素是否全是白的。有非白像素 = 内容贴边/被裁，
   （`savefig.bbox="tight"` 也不是万能的，文字超出 axes 时会被切掉）。

用法：python paper/check_figures.py
"""
import os
import sys
import zipfile

import fitz                       # PyMuPDF：读 PDF 里的字体名
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "figures")

CJK_FONT_HINTS = ("SimHei", "SimSun", "Microsoft YaHei", "MS Gothic", "Noto Sans CJK",
                  "Source Han", "FangSong", "KaiTi", "STSong")

bad_font, bad_edge = [], []

for fn in sorted(os.listdir(FIG)):
    path = os.path.join(FIG, fn)
    base = os.path.splitext(fn)[0]
    if fn.endswith(".pdf"):
        d = fitz.open(path)
        fonts = set()
        for p in d:
            for f in p.get_fonts(full=True):
                fonts.add(f[3])
        hit = [f for f in fonts if any(h.lower() in f.lower() for h in CJK_FONT_HINTS)]
        if hit:
            bad_font.append((fn, sorted(fonts)))
        print("%-26s 字体: %s" % (fn, ", ".join(sorted(fonts))))
    elif fn.endswith(".png"):
        a = np.asarray(Image.open(path).convert("L"))
        edges = {
            "top": a[0, :], "bottom": a[-1, :], "left": a[:, 0], "right": a[:, -1],
        }
        dirty = {k: int((v < 250).sum()) for k, v in edges.items() if (v < 250).sum() > 0}
        if dirty:
            bad_edge.append((fn, dirty))
        print("%-26s 尺寸 %-12s 贴边像素: %s"
              % (fn, "%dx%d" % (a.shape[1], a.shape[0]), dirty or "无"))

print()
if bad_font:
    print("❌ 用了中文字体的图：")
    for fn, fonts in bad_font:
        print("   %s -> %s" % (fn, fonts))
else:
    print("✅ 图里没有中文字体")
if bad_edge:
    print("❌ 有内容贴边（可能被裁切）的图：")
    for fn, dirty in bad_edge:
        print("   %s -> %s" % (fn, dirty))
else:
    print("✅ 所有 PNG 四周留白干净，未被裁切")

sys.exit(1 if (bad_font or bad_edge) else 0)
