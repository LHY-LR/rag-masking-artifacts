"""§4.5 注入：三档粒度 × 预算截断（首部窗口 / 重排后截），输出 ContextBundle。

A1/A5：句切分与单元生产统一走 data.sentences，本模块不再持有正则；
单元携带真实 sent_idx（HotpotQA 来自原始句列表），present_facts 可与 support_facts 对齐。
"""
from __future__ import annotations

from ..schemas import Paragraph, ContextBundle
from ..data.sentences import sentence_units
from .tokenization import get_tokenizer


def assemble(question_id: str, paragraphs: list[Paragraph], granularity: str, budget: int,
             gold_doc_ids: set[str], gold_facts: set[tuple[str, int]] | None = None,
             reranker=None, query: str | None = None) -> tuple[ContextBundle, set]:
    """返回 (ContextBundle, present_facts)；present_facts 为注入覆盖到的 (title,sent_idx)。"""
    tok = get_tokenizer()
    units = []
    for p in paragraphs:
        units.extend(sentence_units(p, granularity, tok))

    if reranker is not None and query is not None:
        scored = reranker.rerank(query, [(f"{d}|{i}", t) for t, d, i in units])
        idx = {(d, i): (t, d, i) for t, d, i in units}
        ordered = []
        for key, _ in scored:
            d, i = key.split("|", 1)
            ordered.append(idx[(d, int(i))])
        units = ordered

    doc_title = {p.doc_id: p.title for p in paragraphs}
    picked, used = [], 0
    present_facts: set[tuple[str, int]] = set()
    gold_in_docs = False
    for text, doc_id, sent_i in units:
        c = tok.count(text)
        if used + c > budget:
            break
        picked.append(text)
        used += c
        if doc_id in gold_doc_ids:
            gold_in_docs = True
        if sent_i >= 0 and doc_id in gold_doc_ids:
            present_facts.add((doc_title.get(doc_id, doc_id), sent_i))

    gold_present = gold_in_docs
    if gold_facts is not None:
        # sentence 粒度精确到 (title,sent_idx)；粗粒度退化为金文档命中
        gold_present = bool(present_facts & gold_facts) if granularity == "sentence" \
            else gold_in_docs
    bundle = ContextBundle(question_id, granularity, budget, picked, used, gold_present)
    return bundle, present_facts
