"""§3 配置常量 —— 全冻结，禁止运行期改动（§7 不变量 7）。

任何对这里常量的偏离都必须写入 changelog（见实现说明）。
"""
from __future__ import annotations

import os

# ---------------- 模型 ----------------
# 本地模型（<=8B 走本机；8B×4K 需先显存压测，见 generation/model.py:vram_estimate）
MODELS = ["Qwen3-0.6B", "Qwen3-1.7B", "Qwen3-4B", "Qwen3-8B"]
MODEL_32B = "Qwen3-32B"  # 仅 probe / 关键格，远程 vLLM，只切模型名
# HF 模型 id 映射（真实运行时按本地路径或 HF id 覆盖）
HF_MODEL_IDS = {
    "Qwen3-0.6B": "Qwen/Qwen3-0.6B",
    "Qwen3-1.7B": "Qwen/Qwen3-1.7B",
    "Qwen3-4B": "Qwen/Qwen3-4B",
    "Qwen3-8B": "Qwen/Qwen3-8B",
    "Qwen3-32B": "Qwen/Qwen3-32B",
    # Phase C（第三轮·阶段二）：Instruct 顺从探针。
    # 权威枚举（hf-mirror API，author=Qwen 212 仓库）确认：Qwen3 纯文本小尺寸只有 4B 有
    # Instruct（-2507 后缀），0.6B/1.7B/8B 无纯文本 Instruct（此前登记的 4 个 id 中 3 个 404，已删）。
    # key 仍用短名 Qwen3-4B-Instruct（跑时 --models Qwen3-4B-Instruct），HF 仓库为 -2507 变体。
    "Qwen3-4B-Instruct": "Qwen/Qwen3-4B-Instruct-2507",
}
# §0：统一用 Qwen 分词器（token 计数 / 256 块 / 预算截断）
TOKENIZER_ID = "Qwen/Qwen3-0.6B"  # 分词器与模型规模无关，统一用一个 Qwen 分词器即可

# ---------------- 解码（§0 冻结） ----------------
DECODE = dict(temperature=0.0, max_new_tokens=64, do_sample=False)

# §3 固定唯一 prompt 模板；{context} 为空串时即闭卷臂（无检索上下文，不是截断残文——§7 不变量2）
PROMPT_TEMPLATE = (
    "Read the following context and answer the question with the shortest possible answer. "
    "Strictly follow the context; if the context says a value, use that exact value.\n"
    "Context: {context}\n\nQ: {question}\nA: The answer is"
)
# 闭卷臂：同一模板，仅 Context 段为空（唯一允许的差异）
PROMPT_TEMPLATE_NOCTX = (
    "Answer the question with the shortest possible answer.\n"
    "Q: {question}\nA: The answer is"
)

# Phase C（第三轮·阶段二）：Instruct 模型走 chat template（ChatML），内容措辞与 base 相同，
# 但去掉 "A: The answer is" 前缀引导——base 需要前缀续写才能答，Instruct 直接跟指令答。
# 只在 HFGenerator 检测到 "-Instruct" 时启用；base 四臂仍用上面两个 raw 模板（同臂同模板）。
PROMPT_TEMPLATE_CHAT = (
    "Read the following context and answer the question with the shortest possible answer. "
    "Strictly follow the context; if the context says a value, use that exact value.\n"
    "Context: {context}\n\nQ: {question}\nA:"
)
PROMPT_TEMPLATE_CHAT_NOCTX = (
    "Answer the question with the shortest possible answer.\n"
    "Q: {question}\nA:"
)

# ---------------- 检索/注入网格 ----------------
GRANULARITIES = ["sentence", "paragraph", "token256"]
TOKEN_BLOCK = 256
BUDGETS = [1024, 4096]
TOP_K = [5]          # 主实验
EXTRA_TOP_K = [3, 8]  # 子实验
GOLD_RECALL_K = 5

# ---------------- 子集规模 ----------------
PILOT_N = 240
SUBSET_N = 1200
MINI_N = 10

# ---------------- 八道闸门阈值（§4.7 / §5；GO/REVISE/ABANDON 出口） ----------------
GATES = {
    1: dict(name="retrieval_equivalence", retain_min=0.90, recall_drop_max=0.02,
            revise_drop=0.20, abandon_drop=0.35),
    # ② 转移矩阵残留在 CB_orig 答对子集中：P(仍答旧key|CB_orig 正确)
    2: dict(name="closed_book_collapse", resid_single=0.05, resid_multi=0.08,
            resid_32b=0.15, seq_first=50, seq_go=0.05, seq_abandon=0.15),
    3: dict(name="oracle_answerability", drop_max=0.03, revise_drop=0.08,
            abandon_drop=0.08, support_drift=0.02),
    4: dict(name="conflict_compliance", rate_min=0.90, rate_min_32b=0.85,
            revise=0.70, abandon=0.70),
    5: dict(name="key_uniqueness", min_rate=0.98),
    6: dict(name="edit_locality", min_rate=0.95),
    7: dict(name="value_unguessable", cooccur_max=0.0),
    8: dict(name="annotation_reliability", kappa_min=0.8, double_annot_frac=0.20,
            max_seconds_per_item=45, abandon_seconds=60),
}

# ---------------- 统计/决策（§4.8） ----------------
RNG_SEED = 20260903
BOOTSTRAP_B = 10000
EFFECT_DELTAS = [0.02, 0.03]
POWER = 0.80
ALPHA = 0.05
DECISION_P_FLIP = 0.80   # P(排序改变) > 0.8
CI_LEVELS = (0.025, 0.975)
# B1 敲定（唯一口径，勿与 DiD CI 混用）：比较两个【竞争配置】的【校正增益】CI——
# 即"表观最优配置"的校正增益 CI vs "校正后最优配置"的校正增益 CI（同一指标、两个配置）；
# P(表观argmax≠校正argmax)>0.8 且两配置【校正增益】CI 分离 → 判"建议改变/敏感带"。
DECISION_RULE = (
    "sensitive iff P(apparent_argmax != corrected_argmax) > 0.80 AND "
    "corrected-gain 95% CIs of the two competing configs are separated")
# B3：聚合闸门最小样本；denom 不足判 INSUFFICIENT（不通过/失效都不下）
MIN_N_FOR_GATE = {1: 30, 2: 30, 3: 30, 4: 30}

# R3-B：三档诊断出口 GO/REVISE/ABANDON 的阈值（direction 指明主指标越优方向）。
# 它只作"诊断归类"，不改上述 GATES 的"严格 pass 谓词"语义（passed 仍按 GATES 判）。
# 对 gate② 的 go 取决于规模/单多跳（aggregate 内已解析成 limit），此处只给方向 + 默认档。
GATE_VERDICT = {
    1: dict(metric="recall_drop", direction="lower", go=0.02, revise=0.20, abandon=0.35),
    3: dict(metric="abs_drop", direction="lower", go=0.03, revise=0.06, abandon=0.10),
    # ②/④ 的 go 依赖 is_multi/model，aggregate 内传入解析后的 go；revise/abandon 给默认档。
    2: dict(metric="resid_old", direction="lower", go=None, revise=0.08, abandon=0.15),
    4: dict(metric="compliance", direction="higher", go=None, revise=0.70, abandon=0.55),
}

# ---------------- 检索后端（§0 / §9 待确认 2） ----------------
# Pyserini 预建 DPR 维基索引名：经典名为 wikipedia-dpr-100w（2018-12-20 DPR 维基，2100 万 100 词段）。
# 注意：Pyserini 版本演进后存在 wiki-all-6-3.* 等新变体；真实下载前以
# `python -m pyserini.index.lucene --list` 或官方 prebuilt 列表为准，只改这一处。
OPEN_INDEX_NAME = "wikipedia-dpr-100w"
BM25_K1, BM25_B = 1.5, 0.75  # rank_bm25 / 回退实现与 Pyserini 默认对齐

DATASETS = ("nq", "trivia", "hotpot")
ARMS = ("cb_orig", "cb_sub", "open_orig", "open_sub")

# ---------------- 构集边界口径（C34） ----------------
# 背景：`whole_occurrence_count` 的整词边界字符类是 `[0-9A-Za-z]`，**小数点与千分位逗号不在其中**，
# 于是 `2.3` 里的 `3`、`3.4` 里的 `3`、`100,000` 里的 `000` 都会被当成一次"独立命中"。
# C32 人审（90 条确定性等距抽样）确认 22 条构造缺陷、其中 17 条是"改错位置"，入口即此处。
# True = 启用数字粘连判定（嵌在更长数字表达式里的命中不算命中）。
# 默认 False = **保持既有冻结产物可复现**；重新构集时用环境变量
# `RAGLEAK_STRICT_NUMERIC=1` 打开（不鼓励改本文件，改文件会让"冻结快照"漂移）。
STRICT_NUMERIC_BOUNDARY = os.environ.get("RAGLEAK_STRICT_NUMERIC", "") == "1"

# ---------------- 年份借值的年代约束（C44，Gate③ 修复） ----------------
# 背景：`ValuePool._bucket_key` 给 numeric 做了量级分桶（`_magnitude_bin`），但**年份只分到
# `("date","year")` 一桶、不约束年代接近度**，于是能把 1828 年借给一个 2013 年的实体。
# C43 诊断实测：gate③ 的 oracle drop 随 |新−旧| 单调上升（条件化后仍单调）；把借值限制在
# ≤20 年后，HotpotQA 上 drop 精确变成 0（闸门③ GO）。机理：模型一眼看出年代荒谬、拒绝照念。
# DATE_ERA_WIDTH = 年代桶宽度（年）。STRICT_DATE_ERA=True 时按此分桶、优先同桶借值。
# 默认 False = **保持既有冻结产物可复现**；重新构集时用 `RAGLEAK_STRICT_DATE_ERA=1` 打开。
DATE_ERA_WIDTH = 20
STRICT_DATE_ERA = os.environ.get("RAGLEAK_STRICT_DATE_ERA", "") == "1"

# ============================================================================
# C52（E 线，2026-09-18）：**实体借值的领域约束**
#
# 背景（round-4/5 失败记录）：name 类答案在 `_bucket_key` 里只有**一个粗桶** `("name",)`，
# 于是 "Bernard King"（篮球运动员）能借到 "Red Dead Redemption"（电子游戏）。模型一眼看出
# 荒谬 → 拒答 → `d` 臂塌方 → name 子集的 DiD 变成**正的**（4B-Instruct +0.140），
# 而 date/numeric 子集是负的（masking）。当时的处置是"需换同类型值池（构造改动，大）"，
# 被推迟至今——就是本开关要做的事。
#
# 机理与 C44 的年代桶同源：**植入值必须在语境里可信，荒谬的植入会被模型拒绝**。
# 年代桶约束"时间上可信"，本开关约束"领域上可信"。
#
# 做法（不引入 NER 依赖，纯文本）：给每道题算一个"领域签名"= 该题问句里
# **低频实词**（df ≤ STRICT_ENTITY_DF_FRAC 且长度 ≥4）中 df 最低的若干词；
# 借值时候选必须与目标题**共享 ≥ENTITY_OVERLAP_MIN 个签名词**且**词数档位相同**，
# 再按 C44 的**逐级放宽**兜底，保证**没有一条题会因找不到候选而丢失**。
#
# 默认 False = 保持既有冻结产物逐位可复现；重跑实体实验时用
# `RAGLEAK_STRICT_ENTITY_DOMAIN=1` 打开。
# ============================================================================
STRICT_ENTITY_DOMAIN = os.environ.get("RAGLEAK_STRICT_ENTITY_DOMAIN", "") == "1"
ENTITY_SIG_TOPK = 6            # 每题取多少个低频实词做签名
ENTITY_SIG_MIN_LEN = 4         # 只把长度 ≥4 的词算作实词（滤掉 of/the/and 类）
ENTITY_SIG_DF_FRAC = 0.08      # df 超过题数 8% 的词不算"有区分度"
ENTITY_OVERLAP_MIN = 2         # 一级约束：至少共享几个签名词

# C55：**答案类型约束**（第二十轮 52 条人工样例的发现：签名匹配的是"题材"不是"答案种类"，
# 约 2/3 的植入值种类不对 ⇒ 模型拒答 ⇒ (b−d) 虚高 ⇒ masking 被压成负值）。
# 只按题目 wh 桶做**偏好式**过滤（过滤后为空即退回），因此同样不丢题。
# 默认 False：既有冻结产物逐位可复现；重跑实体实验时用
# `RAGLEAK_STRICT_ENTITY_TYPE=1` 打开（需同时开 STRICT_ENTITY_DOMAIN）。
STRICT_ENTITY_TYPE = os.environ.get("RAGLEAK_STRICT_ENTITY_TYPE", "") == "1"


