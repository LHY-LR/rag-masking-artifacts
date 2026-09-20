"""T6 失败模式台账：按原因计数（0 命中/多处歧义/值池空/校验失败/人审驳回…）。"""
from __future__ import annotations

from collections import Counter


def build(failures: list[tuple[str, str]]) -> dict:
    """failures: [(question_id, reason)]"""
    c = Counter(reason for _, reason in failures)
    return dict(total=len(failures), by_reason=dict(c))


def render(t: dict) -> str:
    lines = [f"[T6 失败模式台账] 总计 {t['total']} 条"]
    for reason, n in sorted(t["by_reason"].items(), key=lambda x: -x[1]):
        lines.append(f"  {n:>3}  {reason}")
    if not t["by_reason"]:
        lines.append("  （无失败项）")
    return "\n".join(lines)
