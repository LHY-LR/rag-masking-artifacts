"""金证据定位（第四轮定案；A1/A5 修订）：

- NQ/TriviaQA：DPR positive_ctxs 中【含任一归一化 answer alias】的段（不必人工造金段）。
- HotpotQA：supporting_facts 的 (title, sent_idx) 直接从【原始 Paragraph.sentences】取金句，
  不做任何 re-split（A1：join+re-split 会让 U.S./Mr. 等缩略词处序号漂移）。
"""
from __future__ import annotations

from ..schemas import Question, GoldEvidence
from ..metrics.normalize import normalize_answer


def _contains_alias(text: str, aliases: list[str]) -> bool:
    t = normalize_answer(text)
    return any(normalize_answer(a) in t for a in aliases)


def build_gold(q: Question) -> GoldEvidence:
    keys = sorted({normalize_answer(a) for a in q.answers if a.strip()})
    paras = q.paragraphs or []

    if q.dataset == "hotpot":
        sf = set(q.support_facts or [])
        gold_titles = {t for t, _ in sf}
        gold_passages = [p for p in paras if p.title in gold_titles]
        gold_sents: list[str] = []
        title2para = {p.title: p for p in paras}
        for title, idx in sorted(sf, key=lambda x: (x[0], x[1])):
            p = title2para.get(title)
            if p is None:
                continue
            # A1：直接用原始句子序号；越界才记缺失（真实数据这里应 100% 命中）
            if idx < len(p.sentences):
                gold_sents.append(p.sentences[idx])
        return GoldEvidence(q.id, gold_passages, keys, gold_sents or None)

    # 单跳：positive 段含 alias 者为金段
    gold = [p for p in paras
            if ":positive_ctxs:" in p.doc_id and _contains_alias(p.text, q.answers)]
    if not gold:  # 兜底：任何候选段含 alias（DPR 个别文件分组名差异）
        gold = [p for p in paras if _contains_alias(p.text, q.answers)]
    return GoldEvidence(q.id, gold, keys, None)
