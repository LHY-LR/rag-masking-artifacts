# -*- coding: utf-8 -*-
"""check_tex.py —— 本机没有 LaTeX，所以用静态检查替代编译，拦住最常见的几类硬错误。

检查项：
  1. \\begin{env} / \\end{env} 是否配对（按栈检，报出第一个不匹配处）
  2. 所有 \\cite / \\citep / \\citet 的 key 是否都在 refs.bib 里
  3. 所有 \\ref / \\eqref 是否都有对应 \\label
  4. \\includegraphics 指向的文件是否真实存在
  5. 花括号是否配平（忽略转义 \\{ \\}）
  6. 每张表：列声明数 ≥ 该表内最大 & 数+1（列声明多于使用无害，少于使用必炸）

用法：python paper/check_tex.py
"""
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "main.tex")
BIB = os.path.join(HERE, "refs.bib")

problems = []
notes = []


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def strip_comments(text):
    out = []
    for line in text.splitlines():
        # 去掉未被转义的 % 之后的内容
        i, cut = 0, None
        while True:
            j = line.find("%", i)
            if j == -1:
                break
            if j == 0 or line[j - 1] != "\\":
                cut = j
                break
            i = j + 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


def main():
    raw = read(TEX)
    # 跟随 \input{...}：把被包含的文件原样内联，否则正文里引用附录的 \ref 会被误判为悬空
    def inline(text, depth=0):
        if depth > 3:
            return text
        out = []
        for line in text.splitlines():
            m = re.match(r"\s*\\input\{([^}]*)\}\s*$", line)
            if m:
                p = m.group(1)
                if not p.lower().endswith(".tex"):
                    p += ".tex"
                q = os.path.join(os.path.dirname(TEX), p)
                if os.path.isfile(q):
                    out.append("%% ---- inlined %s ----" % p)
                    out.append(inline(read(q), depth + 1))
                    continue
            out.append(line)
        return "\n".join(out)

    raw = inline(raw)
    tex = strip_comments(raw)
    bib = read(BIB)

    # ---- 1. 环境配对 ----
    stack = []
    for m in re.finditer(r"\\(begin|end)\{([^}]*)\}", tex):
        kind, env = m.group(1), m.group(2)
        line = tex[: m.start()].count("\n") + 1
        if kind == "begin":
            stack.append((env, line))
        else:
            if not stack:
                problems.append("第 %d 行：\\end{%s} 没有对应的 \\begin" % (line, env))
            elif stack[-1][0] != env:
                problems.append("第 %d 行：\\end{%s} 与第 %d 行的 \\begin{%s} 不匹配"
                                % (line, env, stack[-1][1], stack[-1][0]))
                stack.pop()
            else:
                stack.pop()
    for env, line in stack:
        problems.append("第 %d 行：\\begin{%s} 没有 \\end" % (line, env))

    # ---- 2. 引用 key ----
    bib_keys = set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", bib))
    cited = set()
    for m in re.finditer(r"\\cite[a-z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}", tex):
        for k in m.group(1).split(","):
            k = k.strip()
            if k:
                cited.add(k)
    missing = sorted(cited - bib_keys)
    for k in missing:
        problems.append("引用了 refs.bib 里没有的 key：%s" % k)
    unused = sorted(bib_keys - cited)
    if unused:
        notes.append("refs.bib 里未被引用的条目（建议补引或删除）：%s" % ", ".join(unused))

    # ---- 3. ref / label ----
    labels = set(re.findall(r"\\label\{([^}]*)\}", tex))
    refs = set()
    for m in re.finditer(r"\\(?:ref|eqref|autoref|Cref|cref)\{([^}]*)\}", tex):
        refs.add(m.group(1).strip())
    for r in sorted(refs - labels):
        problems.append("\\ref{%s} 没有对应的 \\label" % r)
    orphan = sorted(labels - refs)
    if orphan:
        notes.append("有 \\label 但从未被引用（无害）：%s" % ", ".join(orphan))

    # ---- 4. 图片文件存在 ----
    for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]*)\}", tex):
        p = m.group(1).strip()
        cand = None
        for ext in ("", ".pdf", ".png", ".jpg", ".eps"):
            q = os.path.join(HERE, p + ext)
            if os.path.isfile(q):
                cand = q
                break
        if cand is None:
            problems.append("\\includegraphics 指向的文件不存在：%s" % p)

    # ---- 5. 花括号配平（忽略 \{ \}）----
    depth, firstneg = 0, None
    i = 0
    while i < len(tex):
        c = tex[i]
        if c == "\\":
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth < 0 and firstneg is None:
                firstneg = tex[:i].count("\n") + 1
        i += 1
    if depth != 0:
        problems.append("花括号不配平：结束时深度 %+d" % depth)
    if firstneg:
        problems.append("第 %d 行出现多余的 }" % firstneg)

    # ---- 6. 表格列数 ----
    for m in re.finditer(r"\\begin\{tabular\}\{([^}]*)\}(.*?)\\end\{tabular\}", tex, re.S):
        spec, body = m.group(1), m.group(2)
        line = tex[: m.start()].count("\n") + 1
        # 列声明数：l/c/r/p/m/b 各算 1，| 和空白不算，*{n}{...} 算 n
        ncol = 0
        for mm in re.finditer(r"\*\{(\d+)\}\{([^}]*)\}", spec):
            ncol += int(mm.group(1)) * len(re.findall(r"[lcr]", mm.group(2)))
        spec2 = re.sub(r"\*\{(\d+)\}\{([^}]*)\}", "", spec)
        ncol += len(re.findall(r"[lcrp]", spec2))
        worst = 0
        for row in body.split(r"\\"):
            row = re.sub(r"\\(top|mid|bottom)rule|\\hline|\\cmidrule(\([^)]*\))?\{[^}]*\}", "", row)
            if row.strip():
                worst = max(worst, row.count("&") + 1)
        if worst > ncol:
            problems.append("第 %d 行的表：列声明 %d 列，但正文用了 %d 列（会报 Extra alignment tab）"
                            % (line, ncol, worst))
        elif ncol > worst:
            notes.append("第 %d 行的表：列声明 %d 列但只用了 %d 列（能编译，建议收紧）"
                         % (line, ncol, worst))

    # ---- 报告 ----
    print("检查文件：%s" % TEX)
    print("引用条目 %d 个（bib 共 %d 条）；label %d 个，ref %d 个。"
          % (len(cited), len(bib_keys), len(labels), len(refs)))
    if problems:
        print("\n❌ 发现 %d 个问题：" % len(problems))
        for p in problems:
            print("   - %s" % p)
    else:
        print("\n✅ 未发现结构性问题（环境配对 / 引用 key / ref-label / 图片存在 / 花括号 / 表格列数）")
    if notes:
        print("\n提示（非错误）：")
        for n in notes:
            print("   - %s" % n)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
