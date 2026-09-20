"""HotpotQA 支持事实召回：注入上下文中覆盖了多少 (title,sent_idx) 金句。

注意（第五轮评审问题9）：oracle 臂金证据直给时该指标恒为 1，无意义；
本指标只在【真实检索臂】上计算。
"""
from __future__ import annotations


def support_fact_recall(present_facts: set[tuple[str, int]],
                        gold_facts: set[tuple[str, int]]) -> float:
    if not gold_facts:
        return float("nan")
    if not present_facts:
        return 0.0
    return len(present_facts & gold_facts) / len(gold_facts)


def present_facts_from_bundle(injected_doc_sent: set[tuple[str, int]],
                              gold_facts: set[tuple[str, int]]) -> float:
    """injected_doc_sent: 注入单元带来的 (doc_title, sent_idx) 集合。"""
    return support_fact_recall(injected_doc_sent, gold_facts)
