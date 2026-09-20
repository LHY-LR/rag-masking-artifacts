"""§4.8 功效反推：n_req = (z_power + z_alpha/2)^2 * Var(did) / delta^2。

DiD 为配对四臂 0/1 差值，方差用逐题样本方差（配对 bootstrap 分布亦可，二者交叉核对）。
非参稳健性：真实报告同时给 bootstrap 覆盖率检验；t 近似只用于快速反推。
"""
from __future__ import annotations

import math
import statistics

from .. import config
from ..schemas import FourArmRow


def z_quantile(p: float) -> float:
    """标准正态分位数（Acklam 近似，避免 scipy 依赖）。"""
    return _inv_norm_cdf(p)


def _inv_norm_cdf(p: float) -> float:
    if p <= 0 or p >= 1:
        raise ValueError("p in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p <= phigh:
        q = p - 0.5
        r = q * q
        return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
               (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)
    q = math.sqrt(-2 * math.log(1 - p))
    return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
           ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)


def did_variance(rows: list[FourArmRow]) -> float:
    xs = [r.did for r in rows]
    return statistics.variance(xs) if len(xs) > 1 else 0.0


def n_required(var: float, delta: float, power: float = config.POWER,
               alpha: float = config.ALPHA) -> int:
    if var <= 0:
        return 0
    z = _inv_norm_cdf(power) + _inv_norm_cdf(1 - alpha / 2)
    return math.ceil(z * z * var / (delta * delta))


def power_table(rows: list[FourArmRow], deltas=config.EFFECT_DELTAS) -> dict[float, int]:
    v = did_variance(rows)
    return {d: n_required(v, d) for d in deltas}
