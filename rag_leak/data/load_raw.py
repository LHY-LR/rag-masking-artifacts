"""读原始 JSON。

§9 待确认 1（已查证）：DPR nq-dev/trivia-dev.json 每条结构为
  {"question": str, "answers": [str...],
   "positive_ctxs": [{"title": str, "text": str, "score": float, "title_score": float, "psg_id": str}],
   "hard_negative_ctxs": [{"title","text",...}], "negative_ctxs": [...]}
字段名 title/text 确认存在（官方 DPR retriever 输入格式）。
HotpotQA distractor：{"_id","question","answer","type",
   "context": {"title":[...], "sentences":[[s,...],...]},
   "supporting_facts": {"title":[...], "sent_id":[...]}}
"""
from __future__ import annotations

import json
import re

from ..schemas import Question, Paragraph

_NUM_RE = re.compile(r"^[\d.,]+$")
_YEAR_RE = re.compile(r"^(1[0-9]{3}|20[0-9]{2})$")
_DATE_RE = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")


def infer_answer_type(answer: str, hotpot_type: str | None = None) -> str:
    a = answer.strip()
    if hotpot_type == "bridge":
        return "bridge"
    if hotpot_type == "comparison":
        return "comparison"
    if _YEAR_RE.match(a) or re.search(r"\d{1,4}[-/]\d{1,2}", a):
        return "date"
    if _NUM_RE.match(a):
        return "numeric"
    return "name"


def _read_json_any(path: str):
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f)
    return obj


def load_dpr_file(path: str, dataset: str) -> list[Question]:
    """NQ/TriviaQA（DPR retriever json，list[dict]）。"""
    assert dataset in ("nq", "trivia")
    rows = _read_json_any(path)
    out: list[Question] = []
    for i, r in enumerate(rows):
        paras: list[Paragraph] = []
        for grp in ("positive_ctxs", "hard_negative_ctxs", "negative_ctxs"):
            for j, c in enumerate(r.get(grp, []) or []):
                paras.append(Paragraph(
                    doc_id=f"{dataset}-{i}:{grp}:{j}",
                    title=str(c.get("title", "")),
                    text=str(c.get("text", "")),
                ))
        answers = [str(a) for a in r.get("answers", []) if str(a).strip()]
        out.append(Question(
            id=f"{dataset}-{i}",
            dataset=dataset,
            text=str(r["question"]),
            answers=answers,
            answer_type=infer_answer_type(answers[0] if answers else ""),
            support_facts=None,
            paragraphs=paras,
        ))
    return out


def load_hotpot_file(path: str) -> list[Question]:
    """HotpotQA distractor json（list[dict]）。"""
    rows = _read_json_any(path)
    out: list[Question] = []
    for i, r in enumerate(rows):
        ctx = r["context"]
        titles = list(ctx["title"])
        sentences = list(ctx["sentences"])
        paras: list[Paragraph] = []
        for title, sents in zip(titles, sentences):
            paras.append(Paragraph(
                doc_id=f"hotpot-{i}:{title}",
                title=title,
                text=" ".join(sents),   # 检索仍在段级文本上做（BM25 索引单位不变）
                sentences=list(sents),  # A1：原始句子列表原样保留，禁止 join 后 re-split
            ))
        sf = list(zip(r["supporting_facts"]["title"], r["supporting_facts"]["sent_id"]))
        ans = str(r["answer"])
        out.append(Question(
            id=f"hotpot-{i}",
            dataset="hotpot",
            text=str(r["question"]),
            answers=[ans],
            answer_type=infer_answer_type(ans, r.get("type")),
            support_facts=sf,
            paragraphs=paras,
        ))
    return out


def load_raw(path: str, dataset: str) -> list[Question]:
    if dataset == "hotpot":
        return load_hotpot_file(path)
    return load_dpr_file(path, dataset)
