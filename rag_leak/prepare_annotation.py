"""κ 标注包准备（只读输入，产出标注任务文件）：确定性抽样 + 双标模板 + 工作单。

为什么写这个脚本而不是手挑题目：手工挑 90 条会引入"挑看起来干净的题"的选择偏差，
闸门⑧ 因此不可信。抽样必须**确定性、可复现、不看模型输出**（seed 固定、只按 question_id 排序取模）。

用法（在 论文/ 目录执行）：
  python -m rag_leak.prepare_annotation --subs rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl \
      --out-dir rag_leak --n 90
产出：
  anno_subset.jsonl   —— 抽样后的 90 条（双标只用这批）
  anno_A.jsonl        —— 标注人 A 的模板（label 字段留空，只含被标对象，不含模型输出）
  anno_B.jsonl        —— 标注人 B 的模板（逐字节同 A，保证两人看到完全相同的信息）
  anno_worksheet.md   —— 给标注人看的工作单（判定标准 + 操作步骤）
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="κ 标注包准备（确定性抽样，不引入选择偏差）")
    ap.add_argument("--subs", required=True, help="已替换的受控子集 jsonl")
    ap.add_argument("--out-dir", default="rag_leak")
    ap.add_argument("--n", type=int, default=90, help="双标条数（闸门⑧要求 20%% 双人，446 的 20%% ≈ 90）")
    ap.add_argument("--trivia", default="data/trivia_dn.json",
                    help="题池：用于把 question_id 还原成题目文本（= 管线里 ValuePool 用的 subject）")
    args = ap.parse_args(argv)

    rows = _read_jsonl(Path(args.subs))
    if not rows:
        raise SystemExit(f"{args.subs} 为空")
    # 题目文本：管线里 `subject_of = lambda q: q.text`，即 subject 就是问题本身；
    # Proposal dataclass 并没有 subject 字段，所以必须从题池按 id 还原（早期版本漏了这一步，
    # 导致标注包里 subject 全空，而"新值能否被猜出"离开问题就无法判断）。
    qtext = {}
    trivia_path = Path(args.trivia)
    if trivia_path.exists():
        # 必须用管线自己的加载器：question_id（trivia-N）是 load_dpr_file 生成的，
        # 原始 json 里没有该字段，手写解析会对不上号。
        from .data.load_raw import load_dpr_file
        for q in load_dpr_file(str(trivia_path), "trivia"):
            qtext[str(q.id)] = q.text
    else:
        print(f"[warn] 题池 {trivia_path} 不存在，subject 将留空")
    # 确定性等距抽样：按 question_id 排序后均匀取 n 个（不依赖任何模型输出）
    rows = sorted(rows, key=lambda r: str(r.get("question_id")))
    n = min(args.n, len(rows))
    step = len(rows) / n
    picked = [rows[int(i * step)] for i in range(n)]
    if len(picked) != n:
        raise SystemExit("抽样数不符")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def strip(r: dict) -> dict:
        """只留判定所需信息：不含任何模型输出、不含既有 gate 结果，避免污染标注。"""
        return {
            "task_id": r.get("question_id"),
            # subject = 问题文本（管线 `subject_of = lambda q: q.text`）；
            # Proposal 无此字段，故从题池按 id 还原，兜底用 proposal.subject（旧产物里可能没有）。
            "subject": qtext.get(str(r.get("question_id")), "")
                       or (r.get("proposal") or {}).get("subject") or "",
            # 口径关键（易错，已核对管线 gate5_item）：Gate 5 用 proposal.new **逐字原文**
            # 做 whole_occurrence_count；用归一化 new_key 去找会大量假阴性。
            "old": (r.get("proposal") or {}).get("old") or r.get("old_key"),
            "new": (r.get("proposal") or {}).get("new") or r.get("new_key"),
            "old_key": r.get("old_key"),
            "new_key": r.get("new_key"),
            "answer_type": (r.get("proposal") or {}).get("type") or "",
            "old_passage": r.get("old_passage"),
            "new_passage": r.get("new_passage"),
            "semantic_unique": None,      # 待标注：见工作单口径（不是简单"出现几次"）
            "relation_plausible": None,   # 待标注：新值是否**不是**世界知识可推导的
            "labeler": "",
            "comment": "",
        }

    subset = [strip(r) for r in picked]
    (out_dir / "anno_subset.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in subset) + "\n", encoding="utf-8")
    for who in ("A", "B"):
        (out_dir / f"anno_{who}.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in subset) + "\n", encoding="utf-8")

    worksheet = f"""# κ 标注工作单（闸门⑧）

> 标注对象：`anno_subset.jsonl`（共 **{n}** 条，从 {len(rows)} 条受控子集中**确定性等距抽样**，与模型表现无关）
> 两人各自把自己那份（`anno_A.jsonl` / `anno_B.jsonl`）另存改名后逐条填写，**不要互相看**。

## 口径说明（先读，避免白标）

**这件事在干嘛**：我们把段落里的正确答案**偷偷改成了一个假答案**，用来测模型是照着段落说、还是照着自己记住的说。
但改得不好的话这个测试就白做了，所以要人工检查「这次改得合不合格」。**每题只问两件事，都填 `是` / `否`。**

**⑤ 新值所在的那句话，是在回答这道题吗？**
- 在 `new_passage` 里找到 `new`，看它落在哪句话；
- 那句话说的事**正是题目在问的** → `是`；
- 那句话说的事**跟题目没关系**（改错地方了）→ `否`。
- ⑤ 的机械部分已由代码保证，不用你重复判：管线在构集时已强制
  `whole_occurrence_count(new_passage, proposal.new) == 1`（整词边界，`'2'` 不吞 `'2006'`），
  **不满足的题根本不会进入受控子集**。你要判的是机械检查覆盖不到的那一层——
  读了替换后段落的人，能不能**毫无歧义**地认定"题目问的那个位置"就是 `new`。
  若**旧值 `old` 仍留在段内其它位置**，或段内出现**同类型的另一个候选值**（另一个年份/数字/人名）
  且无法从题面区分，读的人分不清题目问的是哪一个 → `否`。

**⑦ 这个新答案，是只有读了段落才知道的吗？**
- 遮住段落只看题目：`new` 很怪、**不读段落绝对想不到** → `是`（合格）；
- `new` 本身就是大家都知道的事实、**不读段落也答得出**（借成了同一乐队成员 / 配偶 / 同一事件的另一年份，
  或干脆就是真答案）→ `否`（不合格）。

**两个都是 `是` → 这条题合格；只要有一个 `否` → 这条题报废。**

### 三个真实例子

| 序号 | 题目 | 替换 | ⑤ | ⑦ | 结论 |
|---|---|---|---|---|---|
| 1 | 迪伦 60 年代经典专辑里的公路（真答案 61） | `61`→`57` | 是（那句话正是在说这张专辑） | 是（57 是编的） | 合格 |
| 4 | 美国有多少州名以 a 开头、以 a 结尾 | `3`→`4` | **否**（被改的是"2.3 百万囚犯"→"2.4 百万"，跟州名无关） | — | 报废 |
| 45 | 一个 therm 等于多少 BTU（真答案 100,000） | `100,000`→`100000` | 是 | **否**（`100000` 就是真答案） | 报废 |

## 逐条操作

1. 打开自己那份清单（`anno_sheet_A.tsv` 或 `anno_sheet_B.tsv`，Excel 双击即开），
   **不要手编 jsonl**；也可用纯文本直读版 `anno_90题_A.txt` / `anno_90题_B.txt`；
2. 每条填 `⑤` 与 `⑦` 两列：**`是` / `否`**（写 `true`/`false` 也认，回填脚本会自动转换）；
3. `labeler` 由回填命令的 `--labeler` 指定；备注可留空，分歧题建议写一句理由；
4. **只看** `old` / `new` / `old_passage` / `new_passage` / `subject` / `answer_type`；
   清单里**没有模型输出**，不要去别处找。

## 纪律

- **两人独立完成，不要互相看结果，也不要在标完前讨论个案**；
- 一旦开始，**先标完再讨论**；若发现判定标准要改，**停下来记录版本**，不要边改边标（κ 会失效）；
- 不要因为"看起来像模板"就跳过，每条都要填。

## 算 κ（两人都填完后，由主控执行）

```powershell
python -m rag_leak.annotate.merge --a rag_leak/anno_A.jsonl --b rag_leak/anno_B.jsonl --out rag_leak/anno_kappa.json
```

结果里**两个维度分别给 κ**（`merge.py` 的 `DIMS`）：
- `relation_plausible` 的 κ 是**闸门⑦/⑧ 的核心指标**（这才是有争议的人审维度）；
- `semantic_unique` 的 κ 反映两人对"语义唯一"这一层的判读一致性，一并报告。

κ ≥ 0.8 → 闸门⑧通过；κ < 0.8 → 回炉（看 `conflicts` 条目、修订标准、重标），**不得放宽阈值**。
"""
    (out_dir / "anno_worksheet.md").write_text(worksheet, encoding="utf-8")

    print(f"源 {len(rows)} 条 → 抽样 {n} 条（等距，确定性）")
    print(f"已写：{out_dir/'anno_subset.jsonl'}")
    print(f"已写：{out_dir/'anno_A.jsonl'} / {out_dir/'anno_B.jsonl'}（逐字节相同）")
    print(f"已写：{out_dir/'anno_worksheet.md'}")
    print("注意：anno_A/B 只含被标对象，不含任何模型输出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
