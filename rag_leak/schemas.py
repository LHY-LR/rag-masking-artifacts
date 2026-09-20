"""§2 核心数据模型。

偏离说明（规格未指定 dataclass 放在哪个文件）：集中在 schemas.py，字段名、字段顺序、
字段语义与 §2 完全一致；另加 asdict/fromdict 仅用于 JSONL 落盘，不改变字段语义。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Paragraph:
    """语料段落/候选。doc_id 对 Pyserini 关键（§4.4：替换后 doc_id 不变）。

    A1 新增：sentences 保存【原始按 title 切好的句子列表】（HotpotQA 直接来自
    context.sentences，禁止 join 后再 re-split）；非 hotpot 留空列表，用时才回退
    到 data.sentences.split_sentences。只加字段，不改 text 的既有语义。
    """
    doc_id: str
    title: str
    text: str
    sentences: list[str] = field(default_factory=list)


@dataclass
class Question:
    id: str
    dataset: str                       # 'nq' | 'trivia' | 'hotpot'
    text: str
    answers: list[str]                 # 别名列表
    answer_type: str                   # 'numeric'|'date'|'name'|'bridge'|'comparison'
    # HotpotQA 独有
    support_facts: Optional[list[tuple[str, int]]] = None  # (title, sent_idx)
    paragraphs: Optional[list[Paragraph]] = None


@dataclass
class GoldEvidence:
    question_id: str
    passages: list[Paragraph]          # 金证据（可多段）
    gold_keys: list[str]               # 归一化后答案 key(们)
    gold_sentences: Optional[list[str]] = None  # HotpotQA 金句


@dataclass
class Proposal:
    """LLM 唯一可输出的东西（§7 不变量1：LLM 绝不输出改写后整段）。"""
    char_span: tuple[int, int]         # 在【原始非归一化文本】上的绝对偏移
    old: str                           # 待替换原始子串（须与原文字面匹配）
    new: str                           # 新值
    type: str                          # numeric/date/name/bridge/comparison
    reason: str                        # 一句话理由（仅审计用）
    passage_doc_id: str = ""           # 偏离说明：多跳一段一个 Proposal，记录落在哪段
    # A2 新增：'terminal'=末跳(真正回答问题) / 'bridge_sync'=仅同步桥值的中间跳
    role: str = "terminal"


@dataclass
class GateResult:
    # B3：passed 允许 None —— None=INSUFFICIENT（样本不足，不判通过/不通过）
    gate_id: int
    passed: Optional[bool]
    value: float
    detail: str
    status: str = "JUDGED"             # 'JUDGED' | 'INSUFFICIENT'
    # R3-B：三档诊断出口 'GO' | 'REVISE' | 'ABANDON' | 'INSUFFICIENT'（诊断工具/表用）
    verdict: str = "JUDGED"


@dataclass
class Substituted:
    question_id: str
    old_passage: str
    new_passage: str                   # 字节级最小改动，仅答案 span 变
    old_key: str
    new_key: str                       # 归一化答案 key
    proposal: Proposal
    gates: dict[str, GateResult] = field(default_factory=dict)
    # A2 新增：末跳新值（归一化）。c/d 臂只与它比 EM；bridge_sync 段留空串。
    terminal_key: str = ""


@dataclass
class RetrievalResult:
    question_id: str
    hits: list[tuple[str, float]]      # (doc_id, score)，开放域/distractor 口径一致
    gold_doc_ids: set[str]
    recall_at_k: int

    def gold_hit(self) -> bool:
        top = {d for d, _ in self.hits[: self.recall_at_k]}
        return bool(top & set(self.gold_doc_ids))


@dataclass
class ContextBundle:
    question_id: str
    granularity: str                   # 'sentence'|'paragraph'|'token256'
    budget: int                        # 1024 或 4096
    texts: list[str]
    tokens_used: int
    gold_present: bool


@dataclass
class Generation:
    question_id: str
    arm: str                           # 'cb_orig'|'cb_sub'|'open_orig'|'open_sub'
    model: str
    config_key: str                    # config 指纹
    raw_output: str


@dataclass
class FourArmRow:
    """每 (题,模型,配置) 一行，四臂配对（§3：四个值必须来自同一 question_id）。"""
    question_id: str
    model: str
    config_key: str
    a: int                             # CB原 EM(旧key)
    b: int                             # 开卷原 EM(旧key)
    c: int                             # CB替换 EM(新key)
    d: int                             # 开卷替换 EM(新key)
    passed_gates: bool = True          # per-protocol 口径用（ITT=False 也保留）

    @property
    def apparent_gain(self) -> int:    # 表观增益 b-a
        return self.b - self.a

    @property
    def corrected_gain(self) -> int:   # 校正增益 d-c
        return self.d - self.c

    @property
    def did(self) -> int:              # 逐题 DiD = (b-a)-(d-c)
        return (self.b - self.a) - (self.d - self.c)


# ---------- JSONL 序列化辅助（不新增字段语义） ----------
def to_jsonable(obj) -> dict:
    d = asdict(obj)
    if isinstance(obj, RetrievalResult):
        d["gold_doc_ids"] = sorted(obj.gold_doc_ids)
    return d


def gate_from_dict(d: dict) -> GateResult:
    # R3-D：passed 可能是 None（INSUFFICIENT），bool(None)=False 会丢语义，必须保留；
    # status/verdict 也一并还原，否则 JSONL 往返后 INSUFFICIENT 被误当作 FAIL。
    passed = d.get("passed")
    passed = None if passed is None else bool(passed)
    status = str(d.get("status", "JUDGED"))
    return GateResult(int(d["gate_id"]), passed, float(d["value"]), str(d["detail"]),
                      status, str(d.get("verdict", status)))
