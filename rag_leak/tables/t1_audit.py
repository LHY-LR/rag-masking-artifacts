"""T1 构集审计：数量、⑤⑥通过率、类型分布、耗时/题。"""
from __future__ import annotations

from collections import Counter
from ..schemas import Substituted


def build(subs: list[Substituted], seconds_per_item: list[float] | None = None) -> dict:
    g5 = [s.gates.get("5") for s in subs if s.gates.get("5")]
    g6 = [s.gates.get("6") for s in subs if s.gates.get("6")]
    return dict(
        n=len(subs),
        by_type=dict(Counter(s.proposal.type for s in subs)),
        gate5_pass=sum(g.passed for g in g5) / len(g5) if g5 else None,
        gate6_pass=sum(g.passed for g in g6) / len(g6) if g6 else None,
        mean_seconds=(sum(seconds_per_item) / len(seconds_per_item)) if seconds_per_item else None,
    )


def render(t: dict) -> str:
    lines = ["[T1 构集审计]", f"  替换条数: {t['n']}  类型分布: {t['by_type']}"]
    if t["gate5_pass"] is not None:
        lines.append(f"  ⑤ key 唯一通过率: {t['gate5_pass']:.3f}")
    if t["gate6_pass"] is not None:
        lines.append(f"  ⑥ 编辑局部通过率: {t['gate6_pass']:.3f}（构造保证）")
    if t["mean_seconds"] is not None:
        lines.append(f"  平均秒/题: {t['mean_seconds']:.1f}")
    return "\n".join(lines)
