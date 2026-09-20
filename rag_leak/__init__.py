"""rag_leak — RAG 泄漏校正实验管线（按《代码架构规格 v1》§0–§8 实现）。

模块边界：
  schemas.py   §2 数据模型（dataclass）
  config.py    §3 冻结常量
  data/        原始加载 / 金证据 / 抽样 / 值池
  construct/   LLM 结构化提案 -> 代码校验 -> 唯一替换 -> 八闸门
  retrieval/   开放域 BM25(Pyserini) / distractor BM25(rank_bm25) / 稠密 / 重排
  generation/  Qwen 分词器、四臂、注入组装、模型后端
  metrics/     EM/F1、支持事实召回、顺从、转移矩阵、NLI、探针
  stats/       DiD、bootstrap、功效、决策、多重比较
  tables/      T1–T6
"""

__version__ = "0.1.0"
