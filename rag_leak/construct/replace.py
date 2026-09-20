"""§4.2(4) 唯一替换引擎：assert count==1 → 代码完成替换（LLM 永不碰文本）。"""
from __future__ import annotations

import json
from pathlib import Path

from ..schemas import Proposal, Substituted, Paragraph
from ..metrics.normalize import normalize_answer, whole_occurrence_count
from .validate import validate_proposal, assert_locality_by_construction


def apply_one(old_passage: str, p: Proposal) -> str:
    """唯一替换点。任何不满足唯一性/局部性的情况直接抛错，不静默修。"""
    n = whole_occurrence_count(old_passage, p.old)
    assert n == 1, f"唯一性断言失败: {p.old!r} 整词出现 {n} 次"
    s, e = p.char_span
    assert old_passage[s:e] == p.old, "span 与 old 不匹配，拒绝替换"
    new_passage = old_passage[:s] + p.new + old_passage[e:]
    # ⑥ 防御性校验：diff 全部落在 span 内（构造保证，再断言一次）
    assert assert_locality_by_construction(old_passage, p.new, p.char_span, new_passage), \
        "⑥ 编辑局部性断言失败"
    return new_passage


def build_substituted(question_id: str, old_paragraph: Paragraph, p: Proposal,
                      old_aliases: list[str]) -> Substituted:
    errs = validate_proposal(p, old_paragraph.text)
    if errs:
        raise ValueError(f"{question_id}/{old_paragraph.doc_id} 提案校验失败: {errs}")
    new_text = apply_one(old_paragraph.text, p)
    # Gate 5 是构集前置不变量而非事后报表项：借入的新值不得已在原段其他位置出现。
    # apply_one 已保证旧值唯一；这里再保证替换完成后 new 只出现于该编辑 span。
    new_count = whole_occurrence_count(new_text, p.new)
    if new_count != 1:
        raise ValueError(f"{question_id}/{old_paragraph.doc_id} Gate 5 失败: "
                         f"new 在替换后段内整词出现 {new_count} 次（须恰好 1 次）")
    new_key = normalize_answer(p.new)
    return Substituted(
        question_id=question_id,
        old_passage=old_paragraph.text,
        new_passage=new_text,
        old_key=normalize_answer(old_aliases[0]),
        new_key=new_key,
        proposal=p,
        gates={},
        # A2：只有末跳段承载答案 key；中间桥值同步段 terminal_key 留空
        terminal_key=new_key if p.role == "terminal" else "",
    )


def write_jsonl(path: str | Path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def edited_paragraphs(paragraphs: list[Paragraph], subs: list[Substituted]
                      ) -> list[Paragraph]:
    """§4.4：doc_id 不变、原地换文本（只对被改文档重建索引/向量）。"""
    by_old = {s.old_passage: s.new_passage for s in subs}
    out = []
    for p in paragraphs:
        if p.text in by_old:
            out.append(Paragraph(doc_id=p.doc_id, title=p.title, text=by_old[p.text]))
        else:
            out.append(p)
    return out
