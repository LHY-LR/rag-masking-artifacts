"""McNemar（配对 0/1，精确二项）+ Holm / BH 多重比较校正（无 scipy 依赖）。"""
from __future__ import annotations

import math


def mcnemar_exact(x01: int, x10: int) -> float:
    """双侧精确 p：不一致对 (b,c) 下，B~Bin(b+c,0.5) 的双侧尾。"""
    n = x01 + x10
    if n == 0:
        return 1.0
    k = min(x01, x10)
    # P(X<=k) 双侧 = 2 * 下尾（不超过 1）
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def holm(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        v = (m - rank) * pvals[i]
        running = max(running, v)
        adj[i] = min(1.0, running)
    return adj


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    prev = 1.0
    for rank in range(m - 1, -1, -1):
        i = order[rank]
        v = min(prev, pvals[i] * m / (rank + 1))
        adj[i] = min(1.0, v)
        prev = v
    return adj
