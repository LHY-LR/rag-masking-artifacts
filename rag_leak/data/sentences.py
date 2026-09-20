"""A5 单一句子切分 / 单元生产者（全项目唯一实现，禁止再各写正则）。

- split_sentences：唯一的正则句切分，仅用于【没有原始句子列表】的语料（DPR 段）。
- paragraph_sentences：优先用 Paragraph.sentences 原始句（HotpotQA），缺失才回退正则，
  这样 (title, sent_idx) 与 supporting_facts 永远对齐（A1）。
- sentence_units：三档粒度统一出口，返回 [(unit_text, doc_id, sent_idx)]，
  sentence 与 token256（句末吸附）共用同一句边界。
"""
from __future__ import annotations

import re

from .. import config
from ..schemas import Paragraph

# 缩略词保护（含其句点整体占位）：U.S. / Mr. / Dr. / vs. / e.g. 等句点不算句末
_ABBREV = re.compile(
    r"(?:U\.S\.|U\.K\.|Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sr\.|Jr\.|St\.|vs\.|etc\.|e\.g\.|i\.e\.|a\.m\.|p\.m\.)",
    re.IGNORECASE)
_SENT_END = re.compile(r"(?<=[.!?。！？])[\"')\]]?\s+")


def split_sentences(text: str) -> list[str]:
    """唯一正则句切分；先把缩略词（含句点）整体占位，再按句末标点+空白切，最后还原。"""
    text = text.strip()
    if not text:
        return []
    placeholders: dict[str, str] = {}

    def _mask(m: re.Match) -> str:
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = m.group(0)
        return key

    protected = _ABBREV.sub(_mask, text)
    parts = [p for p in _SENT_END.split(protected) if p.strip()] or [protected]
    restored = []
    for p in parts:
        for k, v in placeholders.items():
            p = p.replace(k, v)
        restored.append(p.strip())
    return restored


def paragraph_sentences(p: Paragraph) -> list[str]:
    """A1：HotpotQA 用原始 sentences；其余回退正则（回退路径只有它一处）。"""
    if p.sentences:
        return list(p.sentences)
    return split_sentences(p.text)


def sentence_units(paragraph: Paragraph, granularity: str, tokenizer) -> list[tuple[str, str, int]]:
    """统一单元出口。sent_idx：sentence=真实句序号；paragraph=-1；token256=块内首句序号。"""
    sents = paragraph_sentences(paragraph)
    if granularity == "sentence":
        return [(s, paragraph.doc_id, i) for i, s in enumerate(sents)]
    if granularity == "paragraph":
        return [(paragraph.text, paragraph.doc_id, -1)]
    if granularity == "token256":
        # 句末吸附：累积到将超 256 token 就开新块，绝不跨句硬切（§7-4）
        units, buf, n, first_idx = [], [], 0, 0
        for i, s in enumerate(sents):
            c = tokenizer.count(s)
            if buf and n + c > config.TOKEN_BLOCK:
                units.append((" ".join(buf), paragraph.doc_id, first_idx))
                buf, n, first_idx = [], 0, i
            if not buf:
                first_idx = i
            buf.append(s)
            n += c
        if buf:
            units.append((" ".join(buf), paragraph.doc_id, first_idx))
        return units
    raise ValueError(f"未知粒度 {granularity}")
