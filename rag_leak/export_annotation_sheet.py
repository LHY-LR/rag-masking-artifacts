"""把 κ 标注包转成**人可读**的清单（Markdown + TSV，供 Excel 填写）。

为什么需要：直接编辑 jsonl 对非程序员不友好，而且容易破坏格式。
本工具只做**格式转换**，不改任何判定内容；TSV 用制表符分隔，Excel 双击即可打开并填写两列。

口径来源 = `anno_worksheet.md`（由 `prepare_annotation.py` 生成），本脚本只是它的**可用渲染**：
早期版本把 ⑦ 压缩成一句"你能猜到答案被换成了新值吗"，容易读反，且**整列漏掉了 ⑤**，
导致按表填完的 jsonl 里 `semantic_unique` 仍是 None、merge 直接报"κ 不可算"。现已修正为两列。

用法（论文/ 目录）：
  python -m rag_leak.export_annotation_sheet --anno rag_leak/anno_A.jsonl --out-dir rag_leak
产出：
  anno_sheet_A.tsv / anno_sheet_B.tsv   —— Excel 用；两列待填
  anno_清单_A.md / anno_清单_B.md        —— 阅读/打印用（含判定口径 + 完整题目与段落）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def changed_span(old: str, new: str, lctx: int = 40, rctx: int = 28) -> tuple[str, str]:
    """定位 old_passage → new_passage 的**唯一连续改动区**，用 【】 把改掉的字括起来。

    为什么不直接搜 `new` 的第一次出现：管线替换的是**旧值在窗口里的第一次字面出现**，
    而那次出现经常是巧合（日期里的数字、引文编号、别的实体的数值）。人肉去搜会指错地方，
    第一轮标注的 5 处分歧 + 2 处漏判都源于此。把改动点直接摆出来，⑤ 就只剩"这个位置在回答这道题吗"。
    """
    n = min(len(old), len(new))
    p = 0
    while p < n and old[p] == new[p]:
        p += 1
    s = 0
    while s < n - p and old[len(old) - 1 - s] == new[len(new) - 1 - s]:
        s += 1
    oi, oj = len(old) - s, len(new) - s
    pre = " ".join(old[max(0, p - lctx):p].split())
    post = " ".join(old[oi:oi + rctx].split())
    o = f"{pre}【{' '.join(old[p:oi].split())}】{post}"
    w = f"{pre}【{' '.join(new[p:oj].split())}】{post}"
    return o, w


HEADER_MD = """# κ 标注清单（{tag}）

> ## 一句话：我们把段落里的答案偷偷改掉了，现在要检查「这次改得合不合格」。
>
> 每道题只问两件事，都填 **`是`** 或 **`否`**。
> **两个都是「是」→ 这条题合格，能拿去做实验；只要有一个「否」→ 这条题报废。**

---

## 第 0 步：先看「改」那一行 —— 那才是真正被换掉的地方

每条都多了一行 **`改：旧「…」→ 新「…」`**，它是把**原段落和替换后段落逐字比对**得到的
**唯一改动点**。**不要自己去段落里搜新值**——管线是按"旧值在这段里的第一次出现"改的，
那次出现经常是个巧合（日期里的数字、引文编号、别的实体的数值），人肉搜会指错地方。

## ⑤ 改动的那个位置，是在回答这道题吗？

- 那个位置说的正是题目在问的事 → 填 **`是`**；
- 跟题目没关系（是日期、引文编号、另一个东西的数值）→ 填 **`否`**。

> **例（第 4 条）**：题目问「美国有多少个州的州名以 a 开头、以 a 结尾」，
> 改动点是 `more than 2.3 million people were incarcerated` → `2.4 million`，
> 讲的是监狱人数，**跟州名毫无关系** → **`否`**。
> **例（第 67 条）**：题目问「橄榄球球门横梁多高」，
> 改动点是 `won the Rugby World Cup the most (3` → `(2`，讲的是新西兰夺冠次数 → **`否`**。

## ⑦ 这个新答案，像不像一个"正常"的答案？

遮住段落，只看题目和新值：

- 新值是个**编出来的、事先想不到的值**（`61→57`）→ 填 **`是`**；
- 新值**就是这题的真答案**（`100,000→100000`）→ 填 **`否`**；
- 新值**形式或常识上说不通**（年份写成英文单词、`Apollo 81` 这种不存在的编号）→ 填 **`否`**。

> **例（第 45 条）**：题目问「一个 therm 等于多少 BTU」，真答案就是 100,000；
> 改动点只是去掉了千分位逗号 `100,000` → `100000` → **`否`**。
>
> **例（第 1 条）**：题目问「鲍勃·迪伦那张经典专辑里的公路」，真答案是 61；
> 改成 `Highway 57 Revisited` → 57 是编出来的 → **`是`**。

---

## 四种情况一律填「否」（第一轮实测总结）

| 情况 | 填 | 第一轮实例 |
|---|---|---|
| 改动点在**日期 / 引文编号 / 另一个实体的数值**上 | ⑤`否` | 4、17、26、32、37、50、53、55、67、68、71、76、85 |
| 新值**就是这道题的真答案**（或只差个逗号） | ⑦`否` | 45 |
| 新值**形式不对**（年份写成英文单词） | ⑦`否` | 12、15、23 |
| 新值**荒谬到不可能 / 与段落其它线索自相矛盾** | ⑦`否` | 88（`Apollo 81` 却给出 `AS-506`） |

## 纪律

- **两人独立完成**，标完之前不讨论个案，**也不要中途对答案**；
- 90 条都要填，不留空，**只看题目 / 旧值 / 新值 / 替换后段落 / 改动点**，不要去看模型输出；
- 填完把 `anno_sheet_{tag}.tsv` 交回主控（由主控用 `rag_leak.import_annotation_sheet` 回填 jsonl）。

---
"""


def _clean(s) -> str:
    """TSV 不允许制表符/换行；统一成空格，避免 Excel 串列。"""
    return " ".join(str(s or "").split())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="κ 标注包 → 人可读清单（TSV + Markdown）")
    ap.add_argument("--anno", required=True, help="anno_A.jsonl 或 anno_B.jsonl")
    ap.add_argument("--out-dir", default="rag_leak")
    ap.add_argument("--plain", action="store_true",
                    help="额外产出 anno_90题_{tag}.txt：纯文本、无 markdown 装饰，供记事本/打印直读")
    args = ap.parse_args(argv)

    src = Path(args.anno)
    rows = _read_jsonl(src)
    if not rows:
        raise SystemExit(f"{src} 为空")
    # 取文件名末尾的标注者代号（anno_A → A）；不能用 `'A' in stem`——"ANNO_B" 也含 'A'。
    tag = src.stem.upper()[-1]
    if tag not in ("A", "B"):
        tag = "A"
    out_dir = Path(args.out_dir)

    # ---------- TSV（Excel 用）----------
    tsv = out_dir / f"anno_sheet_{tag}.tsv"
    lines = ["序号\t题号\t问题\t旧值\t新值\t被改处(旧)\t被改处(新)\t替换后段落\t"
             "⑤改动处在回答这题吗(填 是/否)\t⑦新答案像正常答案吗(填 是/否)\t备注"]
    for i, r in enumerate(rows, 1):
        o_span, w_span = changed_span(str(r.get("old_passage") or ""), str(r.get("new_passage") or ""))
        lines.append("\t".join([
            str(i), _clean(r["task_id"]), _clean(r.get("subject")),
            _clean(r.get("old")), _clean(r.get("new")),
            "…" + _clean(o_span), "…" + _clean(w_span),
            _clean(r.get("new_passage")),
            "", "", "",
        ]))
    # utf-8-sig：Excel（中文 Windows）识别 BOM 才不会乱码
    tsv.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

    # ---------- Markdown（阅读/打印用）----------
    md = out_dir / f"anno_清单_{tag}.md"
    out = [HEADER_MD.format(tag=tag, n=len(rows), new="新值"), ""]
    for i, r in enumerate(rows, 1):
        o_span, w_span = changed_span(str(r.get("old_passage") or ""), str(r.get("new_passage") or ""))
        out += [f"### {i}. `{r['task_id']}`（{r.get('answer_type')}）", "",
                f"- **问题**：{r.get('subject')}",
                f"- **替换**：`{r.get('old')}` → **`{r.get('new')}`**",
                f"- **改：旧「{_clean(o_span)}」→ 新「{_clean(w_span)}」**",
                f"- **替换后段落**：", "",
                "  > " + _clean(r.get("new_passage")), ""]
        out += [f"- ⑤ 上面那个**改动点**，是在回答这道题吗？　→ ______（是 / 否）",
                f"- ⑦ 新答案 `{r.get('new')}`，像不像一个正常的答案？　→ ______（是 / 否）",
                ""]
    md.write_text("\n".join(out) + "\n", encoding="utf-8")

    print(f"已写 Excel 用清单：{tsv}（{len(rows)} 行，utf-8-sig，两列待填）")
    print(f"已写阅读用清单：{md}")

    if args.plain:
        import textwrap
        ptxt = out_dir / f"anno_90题_{tag}.txt"
        blk = ["=" * 78,
               f" κ 标注 · {len(rows)} 条（{tag}）",
               " 把段落里的答案偷偷改掉之后，检查这次改得合不合格。",
               " 每题只问两件事，都填 是 / 否。两个都「是」才算合格。",
               "   先看「改」那一行——那才是真正被换掉的地方（不要自己搜新值）。",
               "   ⑤  那个改动点，是在回答这道题吗？      （是日期/编号/别的东西 → 否）",
               "   ⑦  这个新答案，像不像一个正常答案？    （真答案/英文单词/荒谬 → 否）",
               "=" * 78, ""]
        for i, r in enumerate(rows, 1):
            o_span, w_span = changed_span(str(r.get("old_passage") or ""), str(r.get("new_passage") or ""))
            blk += [f"[{i:02d}] {r['task_id']}   ({r.get('answer_type')})",
                    f"问：{_clean(r.get('subject'))}",
                    f"换：{_clean(r.get('old'))}  →  {_clean(r.get('new'))}",
                    "改：" + textwrap.fill(f"旧「{_clean(o_span)}」 → 新「{_clean(w_span)}」",
                                          width=120, subsequent_indent="      "),
                    "段：" + textwrap.fill(_clean(r.get("new_passage")), width=104,
                                          subsequent_indent="    "),
                    "   ⑤ ______        ⑦ ______       备注：", ""]
        ptxt.write_text("\n".join(blk) + "\n", encoding="utf-8")
        print(f"已写纯文本直读版：{ptxt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
