"""T5 功效反推：由 mini/pilot 的逐题 DiD 方差反推检出 2pp/3pp @80% power 所需 n/格。"""
from __future__ import annotations

from ..stats.power import did_variance, n_required
from .. import config


def build(rows, deltas=config.EFFECT_DELTAS) -> dict:
    v = did_variance(rows)
    return dict(var=v, n_required={d: n_required(v, d) for d in deltas})


def render(t: dict) -> str:
    return ("[T5 功效反推]\n"
            f"  逐题 DiD 样本方差: {t['var']:.4f}\n"
            + "\n".join(f"  检出 {int(d*100)}pp @80% power -> n/格 >= {n}"
                        for d, n in t["n_required"].items()))
