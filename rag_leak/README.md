# rag_leak —— RAG 泄漏校正实验管线

固定权重开源模型（Qwen3 0.6B→32B）上，用"原语料内最小跨度答案替换"做主对照，
DiD 分离参数记忆与检索增益，并重审检索配置（粒度×预算×重排）建议的校正协议。

## 运行

```bash
python -m rag_leak.run_pipeline --mode=mini                 # 10 题零依赖冒烟
python -m rag_leak.selftest                                 # 无依赖自检（三入口均可）
python -m rag_leak.run_pipeline --mode=pilot \
    --nq nq.json --trivia trivia.json --hotpot hotpot.json \
    --generator hf --proposer rule --models Qwen3-0.6B,Qwen3-1.7B --bits 4
```

## 运行模式矩阵（C3；各列**禁止跨列混搭**）

| mode | 生成后端 | 提案者 | 检索 | 切词 | 说明 |
|---|---|---|---|---|---|
| mini | `StubGenerator`（确定性桩） | `RuleBasedProposer` | `_FallbackBM25`(Okapi 等价实现) | `SimpleTokenizer`（词级，warning） | 只验机械正确性，结果禁止入论文 |
| pilot | `HFGenerator`（`--bits 16/8/4`，32B 用 `RemoteVLLMGenerator`） | `RuleBasedProposer`（唯一命中代码定位）/`LLMProposer`（0/多处才调 LLM，JSON 强校验） | distractor：`rank_bm25.BM25Okapi` | `QwenCounter`（Qwen3 tokenizer） | 240 题、八闸门、T1–T6 |
| grid | `HFGenerator` / `RemoteVLLMGenerator` | 同 pilot | distractor：rank_bm25；开放域：`OpenBM25`(Pyserini)+编辑 overlay；稠密：bge+faiss | `QwenCounter` | 规模×粒度×预算×k×重排大网格 |

禁止混搭（违反即结果作废）：

1. mini 的 `SimpleTokenizer`/`StubGenerator`/`_FallbackBM25` **不得**用于 pilot/grid（启用即 warning，代码另在 grid 拒绝 stub）。
2. distractor 口径（HotpotQA 10 段）与开放域口径（Pyserini 全维基）**不得混用检索器**；两模块独立。
3. 四臂必须同一生成器、同一解码（temp=0、max_new_tokens=32）、同一 prompt；闭卷臂上下文恒为 `None`。
4. LLM 只产出结构化 Proposal JSON；替换文本只能由 `construct/replace.apply_one` 执行。
5. pilot/grid 的 token 计数/切块必须是 Qwen 分词器；SimpleTokenizer 仅 mini。

## 模块地图

- `data/`：载入（HotpotQA 原始句子列表保留，A1）、金证据、值池、统一句切分 `sentences.py`（A5）
- `construct/`：提案（代码定位/LLM 消歧）、校验、最小跨度替换、八闸门
- `retrieval/`：distractor BM25、开放域 Pyserini+overlay（C2）、稠密、重排；`bm25_score.py` 为唯一 BM25 公式
- `generation/`：分词器（A3 统一 encode/decode）、模型后端、三档粒度注入、四臂
- `metrics/`：EM/F1、支持事实召回、顺从分类、②转移矩阵、NLI、泄漏探针
- `stats/`：DiD（B2 符号约定）、功效、决策（B1 校正增益 CI 口径）、多重比较
- `tables/`：T1–T6
- `annotate/`：C4 标注任务导出 + 双标 κ 合并

## Round2 变更（A/B/C）

见同目录《实现说明.md》；关键定义：
- A2：bridge c/d 臂只对**末跳新值** `terminal_key` 判 EM；
- B1：敏感带 = P(排序改变)>0.8 **且**两个竞争配置的**校正增益** CI 分离（`config.DECISION_RULE`）；
- B2：DiD<0 = 记忆掩盖检索收益，"记忆掩盖量=-DiD"；
- B3：闸门②③④ denom<30 判 `INSUFFICIENT`（`passed=None`），不下通过/失效结论。
