# -*- coding: utf-8 -*-
"""make_overleaf_zip.py —— 打包一份可直接上传 Overleaf 的 zip。

要点：**zip 内的路径分隔符必须是正斜杠 `/`**。
PowerShell 5.1 的 Compress-Archive 会把 `figures\\x.pdf` 以反斜杠存进 zip，
Linux 侧的 Overleaf 解压后会得到一个名字里带反斜杠的平铺文件，`\\includegraphics` 就找不到图。
（2026-09-18 已实测：Compress-Archive 产物确实是反斜杠。）
所以这里用 Python zipfile 逐条指定 arcname，逐个断言不含 `\\`。
"""
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "paper_v0.1_overleaf.zip")

ROOT_FILES = ["main.tex", "appendix.tex", "refs.bib", "README.md", "make_figures.py",
              "check_tex.py", "check_figures.py", "check_fig1_layout.py"]
FIG_DIR = "figures"


def main():
    items = [(f, os.path.join(HERE, f)) for f in ROOT_FILES]
    figdir = os.path.join(HERE, FIG_DIR)
    for fn in sorted(os.listdir(figdir)):
        # arcname 手工拼 '/'：os.path.join 在 Windows 上给的是反斜杠，正是本脚本要避免的
        items.append(("%s/%s" % (FIG_DIR, fn), os.path.join(figdir, fn)))

    for arc, _ in items:
        assert "\\" not in arc, "arcname 含反斜杠: %s" % arc

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for arc, src in items:
            if not os.path.isfile(src):
                raise SystemExit("缺文件: %s" % src)
            z.write(src, arc)

    with zipfile.ZipFile(OUT) as z:
        names = z.namelist()
        bad = [n for n in names if "\\" in n]
        if bad:
            raise SystemExit("zip 内仍有反斜杠条目: %s" % bad)
        print("产物: %s" % OUT)
        print("大小: %.1f KB   条目: %d" % (os.path.getsize(OUT) / 1024.0, len(names)))
        for n in names:
            print("  %s" % n)
        print("\n自检: 全部条目用正斜杠分隔 ✅（Overleaf 解压后目录结构正确）")


if __name__ == "__main__":
    sys.exit(main())
