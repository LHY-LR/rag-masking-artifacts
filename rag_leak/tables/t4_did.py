"""T4 DiD 干跑：每规模 表观增益 / 校正增益 / DiD + bootstrap CI（ITT & per-protocol）。

B2：列名同时给 DiD（带符号）与"记忆掩盖量|DiD|"（非负），并固定符号脚注。
"""
from __future__ import annotations

from ..stats.did import (apparent_gain, corrected_gain, did_mean,
                         paired_bootstrap, split_itt_pp, masking_magnitude)


def build(rows_by_model: dict[str, list], B: int = 2000) -> dict:
    out = {}
    for model, rows in rows_by_model.items():
        itt, pp = split_itt_pp(rows)
        mu, (lo, hi), _ = paired_bootstrap(itt, did_mean, B=B)
        out[model] = dict(
            n=len(itt), apparent=apparent_gain(itt), corrected=corrected_gain(itt),
            did=mu, masking=-mu, ci=(lo, hi),
            did_pp=did_mean(pp) if pp else float("nan"),
            masking_pp=masking_magnitude(pp) if pp else float("nan"), n_pp=len(pp),
        )
    return out


def render(t: dict) -> str:
    lines = ["[T4 DiD 干跑（单配置）]",
             "  注(B2)：DiD<0 表示记忆顶高闭卷地板、掩盖真实检索收益；记忆掩盖量=-DiD（非负）。"]
    header = (f"  {'model':<12}{'n':>4}{'表观增益':>10}{'校正增益':>10}{'DiD':>9}"
              f"{'记忆掩盖量':>11}{'95%CI':>20}{'PP掩盖':>9}")
    lines.append(header)
    for model, d in sorted(t.items()):
        lines.append(
            f"  {model:<12}{d['n']:>4}{d['apparent']:>10.3f}{d['corrected']:>10.3f}"
            f"{d['did']:>9.3f}{d['masking']:>11.3f}  [{d['ci'][0]:+.3f},{d['ci'][1]:+.3f}]"
            f"{d['masking_pp']:>9.3f}")
    return "\n".join(lines)
