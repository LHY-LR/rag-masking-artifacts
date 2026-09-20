"""§4.8 逐题 DiD + 配对 bootstrap CI；ITT / per-protocol 两口径。

B2 符号约定（论文措辞统一按此，代码行为不变）：
  did_i = (b_i-a_i) - (d_i-c_i)，a=CB原 b=Open原 c=CB替 d=Open替。
  本仪器下 DiD 通常为【负】：记忆抬高原集闭卷基线 a → 压低表观增益 (b-a)；
  替换集闭卷答不出新 key、c 低 → 抬高校正增益 (d-c)。
  DiD<0 ⇔ 校正增益>表观增益 ⇔ 参数记忆在"顶高闭卷地板、掩盖真实检索收益"。
  记忆掩盖量 = -DiD = |DiD|（非负）；论文写"严格服从字符串级证据后表观增益被压缩的量"，
  不写"记忆贡献=负数"。
"""
from __future__ import annotations

import random

from .. import config
from ..schemas import FourArmRow


def did_values(rows: list[FourArmRow]) -> list[int]:
    return [r.did for r in rows]


def apparent_gain(rows: list[FourArmRow]) -> float:
    return sum(r.apparent_gain for r in rows) / len(rows) if rows else float("nan")


def corrected_gain(rows: list[FourArmRow]) -> float:
    return sum(r.corrected_gain for r in rows) / len(rows) if rows else float("nan")


def did_mean(rows: list[FourArmRow]) -> float:
    xs = did_values(rows)
    return sum(xs) / len(xs) if xs else float("nan")


def masking_magnitude(rows: list[FourArmRow]) -> float:
    """B2：记忆掩盖量 = -mean(DiD)（非负）。"""
    m = did_mean(rows)
    return -m if m == m else float("nan")


def paired_bootstrap(rows: list[FourArmRow], stat_fn=did_mean,
                     B: int = config.BOOTSTRAP_B, seed: int = config.RNG_SEED,
                     ci: tuple[float, float] = config.CI_LEVELS):
    """resample【题目】（四臂配对不拆），重算统计量分布。"""
    rng = random.Random(seed)
    n = len(rows)
    if n == 0:
        return float("nan"), (float("nan"), float("nan")), []
    boots = []
    for _ in range(B):
        sample = [rows[rng.randrange(n)] for _ in range(n)]
        boots.append(stat_fn(sample))
    boots.sort()
    lo = boots[int(ci[0] * B)]
    hi = boots[min(B - 1, int(ci[1] * B))]
    return stat_fn(rows), (lo, hi), boots


def split_itt_pp(rows: list[FourArmRow]):
    """ITT=全部；per-protocol=仅过闸（passed_gates=True）。两口径都报（§4.8）。"""
    itt = list(rows)
    pp = [r for r in rows if r.passed_gates]
    return itt, pp
