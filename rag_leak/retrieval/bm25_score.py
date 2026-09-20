"""C2：BM25 Okapi 打分的唯一公式来源（distractor 回退与开放域 overlay 共用，避免两套公式）。

公式与 rank_bm25.BM25Okapi(k1=1.5,b=0.75) 一致；
IDF 用 BM25+ 稳定形式 ln(1+(N-df+0.5)/(df+0.5))。
"""
from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(s: str) -> list[str]:
    return _TOKEN_RE.findall(s.lower())


def idf_term(n: int, df: int) -> float:
    return math.log(1 + (n - df + 0.5) / (df + 0.5))


def term_score(tf: int, dl: int, avgdl: float, idf: float,
               k1: float = 1.5, b: float = 0.75) -> float:
    denom = tf + k1 * (1 - b + b * dl / (avgdl or 1.0))
    return idf * tf * (k1 + 1) / (denom or 1.0)


def doc_score(query_tokens: list[str], doc_tokens: list[str], df: dict,
              N: int, avgdl: float, k1: float = 1.5, b: float = 0.75) -> float:
    """给定集合统计量 N/avgdl/df，重算单文档对 query 的 BM25 分（overlay 用）。"""
    tf = Counter(doc_tokens)
    dl = len(doc_tokens)
    s = 0.0
    for q in query_tokens:
        if q not in df:
            continue
        s += term_score(tf.get(q, 0), dl, avgdl, idf_term(N, df[q]), k1, b)
    return s


def corpus_stats(corpus_tokens: list[list[str]]) -> tuple[int, float, Counter]:
    N = len(corpus_tokens)
    avgdl = (sum(len(d) for d in corpus_tokens) / N) if N else 0.0
    df = Counter()
    for toks in corpus_tokens:
        for t in set(toks):
            df[t] += 1
    return N, avgdl, df


def overlay_merge(base_hits: list[tuple[str, float]],
                  edited_scores: dict[str, float],
                  k: int) -> list[tuple[str, float]]:
    """C2：被改 doc 用新分【替换/插入】，未改 doc 保持原分、doc_id 不变，按分降序取 k。"""
    merged = {doc_id: score for doc_id, score in base_hits}
    for doc_id, score in edited_scores.items():
        merged[doc_id] = score  # 替换原行；不在 base 中则插入
    return sorted(merged.items(), key=lambda kv: -kv[1])[:k]
