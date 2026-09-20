"""§4.4 distractor 内 BM25（HotpotQA 10 段内；rank_bm25 优先，缺失时用等价 Okapi 回退）。

回退实现与 rank_bm25.BM25Okapi(k1=1.5,b=0.75) 公式一致，仅供无依赖环境/mini；
真实实验以 rank_bm25 结果为准（changelog 记录用了哪个后端）。
"""
from __future__ import annotations

from collections import Counter

from .. import config
from ..schemas import Paragraph, RetrievalResult
from .bm25_score import tokenize, corpus_stats, idf_term, term_score


class _FallbackBM25:
    """等价 Okapi 回退；C2 起公式统一走 bm25_score（与 overlay 同一实现）。"""
    def __init__(self, corpus_tokens: list[list[str]], k1: float = config.BM25_K1,
                 b: float = config.BM25_B):
        self.k1, self.b = k1, b
        self.corpus = corpus_tokens
        self.N, self.avgdl, self.df = corpus_stats(corpus_tokens)
        self.idf = {t: idf_term(self.N, n) for t, n in self.df.items()}
        self.tf = [Counter(d) for d in corpus_tokens]
        self.len = [len(d) for d in corpus_tokens]

    def score(self, query_tokens: list[str], idx: int) -> float:
        score = 0.0
        tf, dl = self.tf[idx], self.len[idx]
        for q in query_tokens:
            if q not in self.idf:
                continue
            score += term_score(tf.get(q, 0), dl, self.avgdl, self.idf[q], self.k1, self.b)
        return score

    def get_scores(self, query: str) -> list[float]:
        q = tokenize(query)
        return [self.score(q, i) for i in range(self.N)]


class DistractorBM25:
    """对单题候选段建索引；edit_document 原地换文本（doc_id 顺序稳定，§4.4/§7-6）。"""

    backend = "rank_bm25"

    def __init__(self, paragraphs: list[Paragraph]):
        self.paragraphs = list(paragraphs)
        self._build()

    def _build(self):
        self.tokens = [tokenize(p.text) for p in self.paragraphs]
        try:
            from rank_bm25 import BM25Okapi
            self.engine = BM25Okapi(self.tokens, k1=config.BM25_K1, b=config.BM25_B)
            self.backend = "rank_bm25"
        except Exception:
            self.engine = _FallbackBM25(self.tokens)
            self.backend = "fallback_okapi"

    def edit_document(self, doc_id: str, new_text: str) -> None:
        """§4.4：doc_id 不变、原地换文本，只重建受影响的索引（这里整体重建，候选仅 10 段）。"""
        for i, p in enumerate(self.paragraphs):
            if p.doc_id == doc_id:
                # A1：保留原始 sentences 字段（若有），不丢原句
                self.paragraphs[i] = Paragraph(p.doc_id, p.title, new_text, list(p.sentences))
        self._build()

    def search(self, query: str, k: int = config.GOLD_RECALL_K) -> list[tuple[str, float]]:
        # C18 修复：rank_bm25 的 get_scores 是 `for q in query` 直接遍历 —— 必须传 token 列表，
        # 传原始字符串会按【字符】打分（垃圾排序）。C 线池退化（gold=唯一/主导段）未暴露，
        # B 线真检索必须在此用与语料一致的分词。fallback 后端在内部自己 tokenize，只喂原始串。
        if self.backend == "rank_bm25":
            scores = self.engine.get_scores(tokenize(query))
        else:
            scores = self.engine.get_scores(query)
        order = sorted(range(len(self.paragraphs)), key=lambda i: -scores[i])[:k]
        return [(self.paragraphs[i].doc_id, float(scores[i])) for i in order]

    def to_result(self, question_id: str, hits: list[tuple[str, float]],
                  gold_doc_ids: set[str], k: int = config.GOLD_RECALL_K) -> RetrievalResult:
        return RetrievalResult(question_id, hits, gold_doc_ids, k)
