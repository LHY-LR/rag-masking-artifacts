"""② 塌陷（§4.7）：转移矩阵，不是 1-CBsub/CBorig 比值。

定义：取 CB_orig 答对(EM=旧key) 的子集，看 CB_sub 输出落在 {新key,旧key,其他}：
  collapse_metric = P(输出=旧key | CB_orig 正确)   —— 参数记忆没被杀掉的残留
报该比例 + Wilson CI；序贯：先 50 题，点估 <5% GO、>15% ABANDON、中间追加。
"""
from __future__ import annotations

import math


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def transition_matrix(cb_orig_correct: list[bool], cb_sub_class: list[str]) -> dict:
    """cb_sub_class: 每题 'new'|'old'|'other'（仅需 CB_orig 正确的题，其余忽略）。"""
    n_old = n_new = n_other = 0
    denom = 0
    for correct, cls in zip(cb_orig_correct, cb_sub_class):
        if not correct:
            continue
        denom += 1
        if cls == "old":
            n_old += 1
        elif cls == "new":
            n_new += 1
        else:
            n_other += 1
    resid = n_old / denom if denom else float("nan")
    lo, hi = wilson_ci(n_old, denom)
    return dict(
        denom=denom, n_old=n_old, n_new=n_new, n_other=n_other,
        residual_old=resid, ci_low=lo, ci_high=hi,
        p_new=n_new / denom if denom else float("nan"),
        p_other=n_other / denom if denom else float("nan"),
    )


def sequential_gate(point_est: float, n_seen: int, cfg: dict) -> str:
    """§4.7 序贯判定，返回 'GO'|'CONTINUE'|'ABANDON'。"""
    if n_seen < cfg["seq_first"]:
        return "CONTINUE"
    if point_est < cfg["seq_go"]:
        return "GO"
    if point_est > cfg["seq_abandon"]:
        return "ABANDON"
    return "CONTINUE"
