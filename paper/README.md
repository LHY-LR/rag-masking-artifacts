# paper/ —— 论文草稿 v0.1（给老师看的第一版）

## 怎么读

- **`main.tex`** —— 正文（LaTeX，英文）。
- **`refs.bib`** —— 参考文献。**头注写明了哪些已核实、哪些是凭记忆重建、必须投稿前逐条核对。**
- **`figures/*.png`** —— **直接双击就能看**，给老师预览用。
- **`figures/*.pdf`** —— 矢量图，投稿用（LaTeX 里引的是这一份）。
- **`make_figures.py`** —— 图的生成脚本，**可复跑**：`python paper/make_figures.py`（在 `论文/` 目录下跑）。
  脚本里的数字是手抄自 `../Claims_Ledger.md` 的常量，改数必须同时改两处（有意设计的摩擦，防止图文不一致）。

## 怎么编译 PDF

### 最快路径（推荐，零安装）

1. 打开 <https://www.overleaf.com> → 登录 → **New Project** → **Upload Project**
2. 选 **`paper_v0.1_overleaf.zip`**（就在本目录，258 KB，已打包好）
3. 打开后确认左上角 **Menu → Compiler = pdfLaTeX**（默认就是），Main document = `main.tex`
4. 点 **Recompile** → 右侧出 PDF，点 **Download PDF**

zip 里的目录结构已按 Overleaf 要求做对（zip 内用正斜杠 `/`，`figures/` 是子目录）。
本机 PowerShell 的 `Compress-Archive` 会写成反斜杠，导致 Linux 侧解压后图片找不到 —— 所以打包脚本
用 Python 显式指定路径：`python paper/make_overleaf_zip.py`（内含自检）。

### 本机编译（可选）

**本机没有 LaTeX**（已查：`pdflatex` / `xelatex` / `latexmk` / `pandoc` 均未安装）。
若想本机编译，需装 TeX Live 或 MiKTeX（约 1–4 GB）。
`main.tex` 用的是**标准 article 版式**，任何 TeX 发行版都能编。投稿换 ACL 模板时，按文件头注释改两行即可。

### 编译前自检（不需要 LaTeX）

```powershell
& "<repo>\venv\Scripts\python.exe" "<repo>\paper\check_tex.py"
```

检查环境配对 / 引用 key 是否存在 / `\ref` 是否有 `\label` / 图片文件是否存在 / 花括号配平 / 表格列数。
**当前结果：✅ 无结构性问题（环境配对 / 引用 key / ref-label / 图片 / 花括号 / 表格列数），
42 条参考文献全部被本文引用**（bib 共 42 条，逐条联网核对记录见 `../参考文献核实_20260918.md`）。

## 这一版的状态（诚实标注）

| 部分 | 状态 |
|---|---|
| 摘要 / 引言 / 协议 / 结果 / 讨论 / 局限 / 结论 | **已写完**，数字全部来自 `Claims_Ledger.md` |
| 五张主图 | **已生成**（PNG + 矢量 PDF） |
| **§4.5 实体型答案（新增）** | **已写完**（领域约束扩展 + 三个构造缺陷审计 + Table 6）；数字见 `../Claims_Ledger.md` §9.7 与 `../判定合集_历轮结论与主张定稿.md` 第 9 节 |
| **Related Work** | **已写完**（6 段：参数知识局限 / 记忆—上下文冲突 / 反事实证据 / 一次增益量了什么 / 数据有效性与审计 / 统计方法 + 定位段） |
| 参考文献 | **42 条，全部逐条联网核对完毕**（三路独立核验 + arXiv API 批量核 14 个 ID + Crossref 批量核 22 个 DOI）。
核对中查出并修正 **7 处**：标题错 2、**作者名单错 3**（ClashEval 10→3、Sun 2026 4→3、**Hong 2024 6→5 且其中 3 个名字是凭空编的**）、venue 错 2（MEMIT 应为 ICLR 2023；Sun 2026 确认为 Findings）、年份错 1（Lost in the Middle 应为 TACL 2024）、缺页码/DOI 若干、`memdelta` 整条由不可验证的 HF 数据集换为可验证论文。
**当前 42 条全部有权威标识（arXiv ID 或 DOI），零残留。** 详见 `../参考文献核实_20260918.md` |
| 附录 | **已填充**（`appendix.tex`，由 `rag_leak/make_appendix.py` **自动从产物生成**，10 张表：B 线四臂 12 格 / HotpotQA 四臂 + 闸门 / 切分敏感性 / leave-one-model-out / **B 线 k 轴五档（v2）** / 聚类 bootstrap / 22 条缺陷逐条 / 预筛混淆矩阵 / 清洗消融 / TriviaQA 闸门，外加 11 条披露）。**≥12 行的表已由生成器自动裹进 `minipage` 防跨页丢表头** |
| 英语 | 结构与论证完整，**投稿前需要一遍母语润色**（唯一还没做的实质项） |

> **2026-09-20 收尾更新**：① HotpotQA 由 3 模型扩到 **5 模型**（5/5 通过 δ=5pp 等价检验）；
> ② **B 线 k 轴升级为 v2 语料五档**（Qwen3-8B，新增附录 `tab:app-kaxis5`，P(翻转)=0.854 但预注册第二条仍未满足）；
> ③ **实体线补 Qwen3-1.7B**，据此把"实体池不在这条曲线上"改写成"**低 a 处一致、高 a 处偏离**"；
> ④ 剂量反应一节补上"连续强度的两种算子"结果（水平量无增量、边际量小增量，exploratory）。
> ⑤ B5 无替换协议 pilot 已完成三模型，**只进账本不进正文**。

> **正文里没有任何红色 TODO。** 摘要关于发布的那句已改为 "will be released upon publication"
> （`main.tex` 里仍留 `% TODO(submission)` 注释：拿到仓库地址后插 URL 并把这句改回 "are released"）。

---

## 审稿驱动项（2026-09-18 第二轮，**已全部处理**）

| 编号 | 问题 | 处理 |
|---|---|---|
| R1 | 分解的信息量被高估（`c` 贴地板 ⇒ `(a−c)≈a`） | 摘要 §与引言一律改写为"**accounting identity**，其内容是**识别哪一项可动**"，与正文调门一致；标题 Bounding→**Localising** |
| R2 | 清洗消融只覆盖 B 线 8B，却写 "every conclusion" | 已补 **v2 全量清洗重算：20/20 个 model×line×depth 格符号与显著性全不变**；措辞与证据范围一致（并披露 HotpotQA 三行 Δ=0 是"没题可剔"） |
| R3 | 摘要 24.4% 未标语料版本 | 摘要改为 "a 20.2\% sample of the **pre-fix** corpus" |
| R4 | 12 个 masking CI 无处可查 | 附录 Table A.1 增加 **"\mask (95% CI)" 列（12 行全给）**，fig5(a) 补误差棒；并据此把 **11/12 更正为 10/12** |
| R5 | 摘要 +0.31 未标模型来源 | 摘要已注 "the largest value comes from a cross-generation model that is not modality-matched" |
| R7 | TOST 的 ±5pp 无依据 | §5.2 已补 δ 的事前选取理由，并同时报 3.5pp 半宽 |
| R8 | 无种子值 | §3.2 写明 `seed 20260903`（且说明抽样同种子 ⇒ 各条件题集相同） |
| D | 实体型答案只有一句 limitation | 新增 **§4.5**：约束证据 + 三个构造缺陷（含**自借 62%**）+ 单变量对照表 + 两条披露；同步摘要/引言/§2/§8/§9 |

---

## 定稿前待办（用户 2026-09-18 决定：**先不修，等彻底定稿一起处理**）

| 优先 | 事项 | 说明 |
|---|---|---|
| **P0** | ~~仓库链接~~ **✅ 已完成** | 代码/语料/产物已发布，**匿名链接已写进摘要与附录**：<https://anonymous.4open.science/r/ragmask-9c41d7b/>（匿名镜像有效期至 **2027-09-19**，策略 Remove when expired）。更新内容后需回镜像页点 **Update Repository**（或等自动同步）。
| **P0** | **英语母语润色** | 结构与术语一致，但作者非母语；不阻塞送审（外部评审也判"不阻塞"） |
| ~~P1~~ | ~~Table（聚类 bootstrap）跨页不重复表头~~ **✅ 已修（2026-09-20）** | 生成器现在把**行数 ≥12 的表自动裹进 `minipage`**，任何长表都无法在分页处断开（`make_appendix.py` 后处理，5 张表已生效） |
| P1 | **换会议模板** | 现在是**单栏 article**（刻意如此：便于给老师批注）。投稿换 ACL/EMNLP 双栏样式后**分页会大幅变化**，届时上面这条跨页问题可能自然消失。`main.tex` 头部注释写了换法 |
| P1 | **作者块** | 现为 `Anonymous draft v0.1 — for internal review`。通信作者姓名/单位/邮箱待补 |
| ~~P2~~ | ~~Figure 2(c) 轴标签偏小~~ **✅ 已修（2026-09-20）** | 标签缩短为 `strat.` / `$k$-ax.` 并把字号调到 6.5pt，消除相邻标签碰撞；图已重生成 |
| — | ~~`k∈{3,10,20}` 只有 148 pilot（v0 语料）~~ **✅ 已升级（2026-09-20）** | Qwen3-8B 在 **v2、n=432、五档**全跑完，新增附录 `tab:app-kaxis5`；其余 5 模型仍仅 k∈{1,5} |
| — | ~~HotpotQA 补 Qwen3-0.6B/1.7B~~ **✅ 已完成（2026-09-20）** | "无记忆 → 无掩盖"已从 3 模型扩到 **5 模型**（5/5 通过 δ=5pp 等价检验） |

## 两个编译级的坑（已修，别再踩）

1. **附录表格曾经混进中文**：`make_appendix.py` 早期版本直接把产物里的中文枚举值（`全量` /
   `人审抽样` / `剔坏样本` / `剔除 X`）写进了表格正文。**pdfLaTeX + `inputenc` 遇到 CJK 会直接报错**
   （`Unicode character ... not set up for use with LaTeX`），或者在宽松设置下**静默丢字**。
   现在脚本里有 `SCOPE_EN` / `tag_en()` 映射，**产物生成后会自动检查**；`main.tex` 与
   `appendix.tex` 现在**零中文**（`refs.bib` 里只剩注释含中文，BibTeX 会跳过；已核注释行内无 `@`）。
2. **附录表格改成非浮动**（`\captionof{table}` + `center`，不再用 `table` 浮动体）：
   浮动体会被 LaTeX 推迟到下一节之后，出现"A.7 标题下面没有表"的假象。非浮动保证表跟在标题正下方。

> 自查命令（不需要 LaTeX）：
> ```powershell
> $py = "<repo>\venv\Scripts\python.exe"
> & $py "<repo>\paper\check_tex.py"            # 结构/引用/表格
> & $py "<repo>\paper\check_figures.py"        # 中文字体 / 裁切
> & $py "<repo>\paper\check_fig1_layout.py"    # fig1 文字与方框重叠
> ```

3. **fig1 的方程文字曾压住方框**（2026-09-18 修）：该图是手工放坐标的示意图，
   `masking = …` 那两行一度和第二排方框（`c` / `d` / `corrected gain`）下缘重叠约 23 px。
   **肉眼在不同缩放下不可靠**，所以新增 `check_fig1_layout.py`：用 renderer 的实际包围盒
   做断言，纳入常规自检。现在实测无重叠。

## 与账本的对应

正文里每个数字都能在 `../Claims_Ledger.md` 找到出处，且全部基于**最终语料 v2**（两处构集修复已应用）。
账本里的 11 条披露清单已分别落到正文、Limitations 或脚注；3 条 limitation 写在第 7 节。
