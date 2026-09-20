"""§4.8 决策判据（替代 argmax 翻转）：

对每规模，比较"表观最优配置"与"校正后最优配置"的增益排序；
bootstrap 得 P(两配置在表观与校正下增益排序不同)；P>0.8 且 CI 分离 → "建议改变"，落敏感带。
"""
from __future__ import annotations

import random

from .. import config


def gain_bootstrap_replicates(cfg_rows: dict[str, list], gain_attr: str,
                              B: int = config.BOOTSTRAP_B, seed: int = config.RNG_SEED
                              ) -> dict[str, list[float]]:
    """cfg_rows: {config_key: [FourArmRow...]}；返回每配置的 bootstrap 增益分布。"""
    rng = random.Random(seed)
    out: dict[str, list[float]] = {k: [] for k in cfg_rows}
    for k, rows in cfg_rows.items():
        n = len(rows)
        for _ in range(B):
            idx = [rng.randrange(n) for _ in range(n)]
            vals = [getattr(rows[i], gain_attr) for i in idx]
            out[k].append(sum(vals) / n)
    return out


def _argmax_mean(dist: dict[str, list[float]], b: int) -> str:
    best, bv = None, None
    for k, vs in dist.items():
        m = vs[b]
        if bv is None or m > bv:
            best, bv = k, m
    return best


def ranking_flip_probability(app_dist: dict[str, list[float]],
                             cor_dist: dict[str, list[float]]) -> tuple[float, str, str]:
    """P(表观 argmax ≠ 校正 argmax)，同时返回点估最优配置。"""
    keys = [k for k in app_dist if k in cor_dist]
    B = min(len(app_dist[k]) for k in keys)
    flips = 0
    for b in range(B):
        if _argmax_mean({k: app_dist[k] for k in keys}, b) != \
           _argmax_mean({k: cor_dist[k] for k in keys}, b):
            flips += 1
    app_best = max(keys, key=lambda k: sum(app_dist[k]) / len(app_dist[k]))
    cor_best = max(keys, key=lambda k: sum(cor_dist[k]) / len(cor_dist[k]))
    return flips / B, app_best, cor_best


def ci_separated(ci_a: tuple[float, float], ci_b: tuple[float, float]) -> bool:
    return ci_a[1] < ci_b[0] or ci_b[1] < ci_a[0]


def judge_sensitive(p_flip: float,
                    ci_corrected_appbest: tuple[float, float],
                    ci_corrected_corbest: tuple[float, float],
                    p_thresh: float = config.DECISION_P_FLIP) -> dict:
    """B1 唯一口径（见 config.DECISION_RULE）：

    两个入参 CI 都是【校正增益】的 bootstrap CI，分别属于两个竞争配置——
    表观 argmax 配置的校正增益 CI、校正 argmax 配置的校正增益 CI；
    不是 DiD 的 CI，也不是"表观 vs 校正"同一配置的 CI。
    判"建议改变/敏感带"当且仅当：P(排序改变)>阈值 且 两配置校正增益 CI 分离。
    """
    separated = ci_separated(ci_corrected_appbest, ci_corrected_corbest)
    change = (p_flip > p_thresh) and separated
    return dict(p_flip=p_flip, corrected_ci_separated=separated,
                in_sensitive_band=change,
                verdict="建议改变（敏感带）" if change else "建议不变")
