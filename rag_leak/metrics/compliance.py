"""④ 冲突顺从：替换证据与参数记忆冲突时，输出落在 {新key, 旧key, 其他} 哪一类。"""
from __future__ import annotations

from .normalize import normalize_answer, extract_answer


def classify_output(raw_output: str, new_aliases: list[str], old_aliases: list[str]) -> str:
    """返回 'new' | 'old' | 'other'。先判新（新 key 优先，避免旧值是新值子串的歧义）。
    Phase-B：先 extract_answer 去答案前缀，避免 "The answer is X" 被误判为 other。"""
    p = normalize_answer(extract_answer(raw_output))
    if any(p == normalize_answer(a) for a in new_aliases):
        return "new"
    if any(p == normalize_answer(a) for a in old_aliases):
        return "old"
    return "other"


def compliance_rate(classes: list[str]) -> float:
    """答新 key 的比例（④ 阈值见 config.GATES[4]）。"""
    if not classes:
        return float("nan")
    return sum(c == "new" for c in classes) / len(classes)
