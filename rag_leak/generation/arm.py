"""§4.6 四臂：对 (question_id, model, config_key) 同批题配对执行且仅执行四臂。

不变量：
- 同一 Question、同一 prompt/解码/预算口径；
- 闭卷臂 = 无检索上下文（None），不是截断残文（§7-2）；
- cb_sub/open_sub 对【新 key】比 EM，cb_orig/open_orig 对【旧 key】（§7-3）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .. import config
from ..schemas import (Question, Substituted, Paragraph, FourArmRow, Generation,
                       RetrievalResult, ContextBundle)
from ..metrics.normalize import em_any_alias
from ..metrics.compliance import classify_output
from . import inject


@dataclass
class ArmConfig:
    granularity: str = "paragraph"
    budget: int = 4096
    k: int = config.GOLD_RECALL_K
    rerank: bool = False

    @property
    def key(self) -> str:
        return f"{self.granularity}|b{self.budget}|k{self.k}|rr{int(self.rerank)}"


def _retrieve_distractor(question: Question, paragraphs: list[Paragraph], acfg: ArmConfig,
                         backend_factory):
    """distractor 口径：单题候选段内 BM25（mini 走这里）。"""
    eng = backend_factory(paragraphs)
    hits = eng.search(question.text, acfg.k)
    gold_ids = {p.doc_id for p in paragraphs}  # 调用方传入更精确的 gold ids
    return hits


def build_contexts(question: Question, orig_paras: list[Paragraph],
                   sub_paras: list[Paragraph], hits_orig: list[tuple[str, float]],
                   hits_sub: list[tuple[str, float]], acfg: ArmConfig,
                   gold_doc_ids: set[str], reranker=None):
    keep_o = [p for p in orig_paras if p.doc_id in {d for d, _ in hits_orig}]
    keep_s = [p for p in sub_paras if p.doc_id in {d for d, _ in hits_sub}]
    # 保持检索排序
    order_o = {d: i for i, (d, _) in enumerate(hits_orig)}
    order_s = {d: i for i, (d, _) in enumerate(hits_sub)}
    keep_o.sort(key=lambda p: order_o[p.doc_id])
    keep_s.sort(key=lambda p: order_s[p.doc_id])
    gold_facts = set(question.support_facts or [])
    cb_o, pf_o = inject.assemble(question.id, keep_o, acfg.granularity, acfg.budget,
                                 gold_doc_ids, gold_facts, reranker, question.text)
    cb_s, pf_s = inject.assemble(question.id, keep_s, acfg.granularity, acfg.budget,
                                 gold_doc_ids, gold_facts, reranker, question.text)
    return cb_o, cb_s, pf_o, pf_s


def run_four_arms(question: Question, subs: list[Substituted], generator,
                  orig_paragraphs: list[Paragraph], sub_paragraphs: list[Paragraph],
                  hits_orig: list[tuple[str, float]], hits_sub: list[tuple[str, float]],
                  acfg: ArmConfig, model_name: str,
                  gold_doc_ids: set[str], reranker=None) -> tuple[FourArmRow, list[Generation], dict]:
    # A2：c/d 臂只用【末跳新值】，不取所有 hop 的并集；bridge 恰好 1 个 terminal
    term_subs = [s for s in subs if s.terminal_key]
    bridge_subs = [s for s in subs if not s.terminal_key]
    if question.dataset == "hotpot":
        assert len(term_subs) == 1, (
            f"{question.id} bridge/comparison 末跳 key 必须恰好 1 个，实际 {len(term_subs)}")
    term = term_subs[0] if term_subs else subs[0]
    terminal_keys = [term.terminal_key or term.new_key]
    new_surface = term.proposal.new
    old_surface = question.answers[0]

    ctx_o, ctx_s, pf_o, pf_s = build_contexts(question, orig_paragraphs, sub_paragraphs,
                                              hits_orig, hits_sub, acfg, gold_doc_ids, reranker)
    ctx_text_o = "\n\n".join(ctx_o.texts)
    ctx_text_s = "\n\n".join(ctx_s.texts)

    plan = [
        ("cb_orig", None, old_surface, question.answers),       # 闭卷：无上下文
        ("cb_sub", None, new_surface, terminal_keys),          # A2：只对末跳新 key
        ("open_orig", ctx_text_o, old_surface, question.answers),
        ("open_sub", ctx_text_s, new_surface, terminal_keys),
    ]
    gens: list[Generation] = []
    em: dict[str, int] = {}
    classes: dict[str, str] = {}
    for arm, ctx, surface, keys in plan:
        raw = generator.generate(question.text, ctx, target_surface=surface,
                                 question_id=question.id, arm=arm)
        gens.append(Generation(question.id, arm, model_name, acfg.key, raw))
        em[arm] = em_any_alias(raw, keys)
        classes[arm] = classify_output(raw, terminal_keys, question.answers)

    row = FourArmRow(question.id, model_name, acfg.key,
                     a=em["cb_orig"], b=em["open_orig"],
                     c=em["cb_sub"], d=em["open_sub"])
    aux = dict(ctx_orig=ctx_o, ctx_sub=ctx_s, classes=classes,
               terminal_keys=terminal_keys, bridge_sync=len(bridge_subs),
               present_facts_orig=pf_o, present_facts_sub=pf_s)
    return row, gens, aux


def run_oracle_pair(question: Question, subs: list[Substituted], generator,
                    gold_orig_text: str, gold_sub_text: str, model_name: str,
                    acfg: ArmConfig) -> dict:
    """③④：金证据直给的 ORA_orig / ORA_sub（+ 闭卷分类复用四臂结果即可）。"""
    term_subs = [s for s in subs if s.terminal_key]
    term = term_subs[0] if term_subs else (subs[0] if subs else None)
    new_aliases = [term.terminal_key or term.new_key] if term else question.answers
    term_key = new_aliases[0] if new_aliases else None
    # Phase C 诊断（C7，additive，不影响任何冻结指标）：term_key 是否真的出现在金替换证据
    # gold_sub_text 里 → 区分"真冲突试次"与"无操作试次"（替换落在答案关键段之外时模型无从答新值，
    # 会把 compliance 分母掺水）。整词边界 + 大小写不敏感（C7′：term_key 常为小写而段文为原大小写，
    # 敏感匹配会把真冲突误判成无操作——hotpot-3537 ora_sub 已复述 term 仍被判 no-op）。避免 '2' 误命中 '2006'。
    _tk = (term_key or "").strip().lower()
    term_present = bool(_tk) and re.search(
        r"(?<![0-9a-z])" + re.escape(_tk) + r"(?![0-9a-z])",
        (gold_sub_text or "").lower()) is not None
    new_surface = term.proposal.new if term else question.answers[0]
    raw_o = generator.generate(question.text, gold_orig_text, question.answers[0],
                               question.id, "ora_orig")
    raw_s = generator.generate(question.text, gold_sub_text, new_surface,
                               question.id, "ora_sub")
    return dict(
        ora_orig=raw_o, ora_sub=raw_s,
        em_orig=em_any_alias(raw_o, question.answers),
        em_sub=em_any_alias(raw_s, new_aliases),
        cls_sub=classify_output(raw_s, new_aliases, question.answers),
        term_key=term_key, term_present=term_present, new_aliases=list(new_aliases),
    )
