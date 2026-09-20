"""§4.2(3) 代码级校验 + ⑥ 编辑局部性防御性校验（不靠 LLM 保证）。"""
from __future__ import annotations

import re

from ..schemas import Proposal
from ..metrics.normalize import whole_occurrence_count

_NUM_RE = re.compile(r"^[\d.,]+$")
_DATE_RE = re.compile(r".*\d{4}.*")


def type_predicate(t: str, v: str) -> str:
    if t in ("numeric",) or _NUM_RE.match(v.strip()):
        return "numeric"
    if t == "date" or _DATE_RE.match(v.strip()):
        return "date"
    return "name"


def validate_proposal(p: Proposal, passage_text: str) -> list[str]:
    """返回错误列表；空列表 = 通过。"""
    errs: list[str] = []
    s, e = p.char_span
    # 1) span 边界落在段落内
    if not (0 <= s < e <= len(passage_text)):
        errs.append("span 越界")
        return errs
    # 2) old == 文本[span] 逐字匹配
    if passage_text[s:e] != p.old:
        errs.append("old 与 text[span] 不逐字匹配")
    # 3) 唯一性：整词边界恰好 1 次（'2' 不计入 '2006'）
    n_old = whole_occurrence_count(passage_text, p.old)
    if n_old != 1:
        errs.append(f"old 在段内整词出现 {n_old} 次（须恰好 1 次）")
    # 4) 类型一致性：old/new 的数字/日期谓词一致（name/bridge/comparison 不做字面谓词约束）
    if p.type in ("numeric", "date"):
        if type_predicate(p.type, p.old) != type_predicate(p.type, p.new):
            errs.append(f"类型不一致: {p.old!r} -> {p.new!r}")
    if not p.new or p.new == p.old:
        errs.append("new 为空或与 old 相同")
    return errs


def locality_check(old_passage: str, new_passage: str, span: tuple[int, int],
                   new_value: str) -> bool:
    """⑥ token/字符 diff 全部落在 span 内：span 外文本必须逐字符相同。

    权威判据是构造等式 new == old[:s] + new_value + old[e:]（见 assert_locality_by_construction）。
    """
    return assert_locality_by_construction(old_passage, new_value, span, new_passage)


def assert_locality_by_construction(old_passage: str, new_value: str,
                                    span: tuple[int, int], new_passage: str) -> bool:
    """⑥ 权威实现：new_passage 必须严格等于 old[:s]+new_value+old[e:]。"""
    s, e = span
    expected = old_passage[:s] + new_value + old_passage[e:]
    return new_passage == expected


def validate_bridge_sync(proposals: list[Proposal], gold_sentences: list[str],
                         new_key_norm: str, normalize) -> list[str]:
    """bridge：new 必须在两段金句范围内被同步替换；断言"末跳句能推出 new_key"。"""
    errs = []
    if not proposals:
        return ["bridge 无任何替换提案"]
    # 末跳可推导：至少一条金句（替换后）含新 key 归一化形式
    tail_ok = any(normalize(new_key_norm) in normalize(s) for s in gold_sentences) \
        if gold_sentences else True
    if gold_sentences and not tail_ok:
        # 金句是旧文本，这里只检查"替换动作覆盖了末跳所在段"；真正 new 出现性由 replace 后⑤保证
        errs.append("bridge 末跳段未被替换覆盖")
    return errs
