"""泄漏探针：问题↔金证据的 n-gram 表面重合度（嵌入重合为可选重依赖）。

定位（第五轮评审）：作为"流行/长尾"分层协变量（接 Mallen 2023），不是记忆的直接度量。
词级 n-gram 覆盖：问题中有多少 1/2-gram 直接出现在金证据里——"表面可命中"程度。
"""
from __future__ import annotations

from .normalize import normalize_answer


def _ngrams(toks: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def ngram_overlap(question: str, passage: str, ns: tuple[int, ...] = (1, 2)) -> dict[str, float]:
    q = normalize_answer(question).split()
    p = set(normalize_answer(passage).split())
    pset_bigrams = _ngrams(normalize_answer(passage).split(), 2)
    out: dict[str, float] = {}
    if 1 in ns:
        out["unigram_recall"] = (
            sum(t in p for t in q) / len(q) if q else 0.0
        )
    if 2 in ns:
        qb = _ngrams(q, 2)
        out["bigram_recall"] = (len(qb & pset_bigrams) / len(qb)) if qb else 0.0
    return out


def embedding_overlap(question: str, passage: str, dense_retriever) -> float | None:
    """可选：用与检索一致的稠密编码器算余弦；无后端时返回 None。"""
    if dense_retriever is None or not getattr(dense_retriever, "available", False):
        return None
    import numpy as np
    v = dense_retriever.encode_texts([question, passage], normalize=True)
    return float(np.dot(v[0], v[1]))
