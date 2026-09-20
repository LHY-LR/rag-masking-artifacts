"""§4.2 答案 span 定位 + 结构化提案。

§7 不变量1：LLM 只允许输出结构化 Proposal（JSON 严格校验），绝不输出改写后整段。
- RuleBasedProposer：mini/测试桩，纯规则定位（零依赖、确定性），用于验证"提案→代码替换"地基。
- LLMProposer：真实构集用；LLM 返回 JSON，代码逐字段校验，old 必须与原文字面匹配，否则拒。
多跳：一段一个 Proposal（偏离说明：Proposal 字段不变，只是返回 list，长度通常为 1）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..schemas import Question, GoldEvidence, Proposal
from ..metrics.normalize import normalize_answer, find_whole_spans
from ..data.value_pool import ValuePool


@dataclass
class ProposalOutcome:
    proposals: list[Proposal]
    status: str            # 'auto' | 'llm_disambig' | 'failed'
    reason: str = ""


def _find_literal_spans(text: str, aliases: list[str]) -> list[tuple[int, int, str]]:
    """在【原始未归一化文本】上找所有 alias 字面命中（绝对偏移）。"""
    from ..metrics.normalize import is_glued_to_number, strict_numeric_boundary
    strict = strict_numeric_boundary()
    hits = []
    for alias in aliases:
        # 优先整词边界（避免 '2' 命中 '2006'）；零命中再退回裸子串查找
        spans = find_whole_spans(text, alias)
        if not spans:
            start = 0
            while True:
                i = text.find(alias, start)
                if i < 0:
                    break
                # C34：兜底路径同样要排除数字粘连，否则 `2.3` 里的 `3` 会从后门溜回来
                if not (strict and is_glued_to_number(text, i, i + len(alias), alias)):
                    spans.append((i, i + len(alias)))
                start = i + 1
        for (i, j) in spans:
            hits.append((i, j, alias))
    # 归一化兜底：原文大小写/标点差异时，按归一化映射定位（仍返回原文切片）
    if not hits:
        norm = normalize_answer(text)
        for alias in aliases:
            na = normalize_answer(alias)
            j = norm.find(na)
            if j >= 0:  # 近似路径必须人审（status 降级）
                hits.append((-1, -1, alias))
    return sorted(hits, key=lambda x: (x[0], x[1]))


class RuleBasedProposer:
    """确定性测试桩：alias 唯一命中自动定位；多处/零处交失败台账（真实流程交 LLM+人审）。"""

    def __init__(self, pool: ValuePool, subject_of=None):
        self.pool = pool
        self.subject_of = subject_of or (lambda q: q.text)

    def _terminal_doc_id(self, q: Question, gold: GoldEvidence) -> str:
        """A2：末跳 = support_facts 顺序中最后一个【含答案 alias】的金段；单跳为唯一金段。"""
        alias_hit_titles = []
        for p in gold.passages:
            hits = _find_literal_spans(p.text, q.answers)
            if [h for h in hits if h[0] >= 0]:
                alias_hit_titles.append(p.title)
        if q.dataset != "hotpot":
            return gold.passages[0].doc_id if gold.passages else ""
        # 按 support_facts 出现顺序取最后一个含答案的 title
        ordered = [t for t, _ in (q.support_facts or []) if t in alias_hit_titles]
        term_title = ordered[-1] if ordered else (alias_hit_titles[-1] if alias_hit_titles else "")
        for p in gold.passages:
            if p.title == term_title:
                return p.doc_id
        return ""

    def propose(self, q: Question, gold: GoldEvidence) -> ProposalOutcome:
        props: list[Proposal] = []
        multi_flag = False
        skipped_bridge_hops = 0
        terminal_doc = self._terminal_doc_id(q, gold)
        for p in gold.passages:
            hits = _find_literal_spans(p.text, q.answers)
            exact = [h for h in hits if h[0] >= 0]
            if len(exact) == 0:
                # 多跳首跳金段不含末跳答案属正常（如"法国首都是巴黎"），跳过；
                # 单跳金段由 build_gold 保证含 alias，若 0 命中即失败
                if q.dataset == "hotpot":
                    skipped_bridge_hops += 1
                    continue
                return ProposalOutcome([], "failed", f"{p.doc_id} 金段内 0 处字面命中，需 LLM 提候选+人审")
            if len(exact) > 1:
                multi_flag = True  # 多处：真实流程 LLM 消歧+必人审；桩取第一处并标记
            s, e, old = exact[0]
            subject = self.subject_of(q)
            new = self.pool.borrow(q.id, subject, old, q.answer_type, passage_text=p.text)
            if new is None:
                # §4.3：numeric/date 允许等位数虚构兜底；name 禁止虚构
                if q.answer_type in ("numeric", "date"):
                    new = ValuePool.fictional(old, q.answer_type, passage_text=p.text)
                if new is None:
                    return ProposalOutcome([], "failed", f"{p.doc_id} 无 Gate 5 合法借值/虚构值")
            role = "terminal" if p.doc_id == terminal_doc else "bridge_sync"
            props.append(Proposal(
                char_span=(s, e), old=old, new=new, type=q.answer_type,
                reason="rule-based: unique literal alias hit; value borrowed cross-question",
                passage_doc_id=p.doc_id, role=role,
            ))
        if not props:
            return ProposalOutcome([], "failed", "所有金段均 0 处字面命中")
        n_term = sum(pr.role == "terminal" for pr in props)
        if q.dataset == "hotpot" and n_term != 1:
            return ProposalOutcome([], "failed", f"bridge/comparison 末跳不唯一（{n_term} 个 terminal）")
        status = "llm_disambig" if multi_flag else "auto"
        reason = "multi-hit, first chosen; MUST human review" if multi_flag else ""
        if skipped_bridge_hops:
            reason = (reason + "; " if reason else "") + f"跳过 {skipped_bridge_hops} 个不含末跳答案的首跳金段"
        return ProposalOutcome(props, status, reason)


class LLMProposer:
    """真实 LLM 路径：client(prompt)->str 由外部注入（模型名冻结在 config）。

    LLM 输出只可能被解析为 Proposal；任何自由文本都进不了实验（解析失败即拒）。
    """

    def __init__(self, client, pool: ValuePool):
        self.client = client
        self.pool = pool

    @staticmethod
    def _prompt(passage_text: str, aliases: list[str]) -> str:
        return (
            "You output ONLY one JSON object, no prose. Locate the answer span in the ORIGINAL passage.\n"
            'Schema: {"char_span":[int,int],"old":str,"new":str,"type":str,"reason":str}\n'
            "Rules: old must be a verbatim substring of the passage; new is a same-type replacement "
            "value you will be given separately; char_span are absolute offsets in the passage.\n"
            f"Aliases: {aliases}\nPassage:\n{passage_text}\nJSON:"
        )

    def parse(self, llm_raw: str, passage_text: str, new_value: str, ptype: str,
              doc_id: str, role: str = "terminal") -> Proposal | None:
        try:
            obj = json.loads(llm_raw)
            s, e = int(obj["char_span"][0]), int(obj["char_span"][1])
            old = str(obj["old"])
        except Exception:
            return None  # JSON/schema 不合 -> 拒，进 T6
        # 代码复核：span 与 old 必须都与原文逐字一致，否则拒绝 LLM 结果
        if not (0 <= s < e <= len(passage_text)) or passage_text[s:e] != old:
            return None
        return Proposal((s, e), old, new_value, ptype,
                        str(obj.get("reason", "")), doc_id, role)

    def propose(self, q: Question, gold: GoldEvidence) -> ProposalOutcome:
        """C1 真实构集：唯一字面命中由代码自动定位（不调 LLM）；
        0/多处才调 client 消歧，返回 JSON 经 parse 逐字校验。值仍由代码值池借取。"""
        props, used_llm = [], False
        ordered = [t for t, _ in (q.support_facts or [])]
        hit_titles = [p.title for p in gold.passages
                      if any(h[0] >= 0 for h in _find_literal_spans(p.text, q.answers))]
        term_title = ([t for t in ordered if t in hit_titles] or hit_titles)
        term_title = term_title[-1] if term_title else None
        for p in gold.passages:
            hits = [h for h in _find_literal_spans(p.text, q.answers) if h[0] >= 0]
            role = "terminal" if p.title == term_title else "bridge_sync"
            if len(hits) == 1:
                s, e, old = hits[0]
            elif len(hits) == 0 and q.dataset == "hotpot":
                continue
            else:
                used_llm = True
                new_value = self.pool.borrow(q.id, q.text, hits[0][2] if hits else q.answers[0],
                                             q.answer_type, passage_text=p.text)
                if new_value is None:
                    if q.answer_type in ("numeric", "date"):
                        new_value = ValuePool.fictional(q.answers[0], q.answer_type,
                                                        passage_text=p.text)
                    if new_value is None:
                        return ProposalOutcome([], "failed", f"{p.doc_id} 无 Gate 5 合法借值/虚构值")
                raw = self.client(self._prompt(p.text, q.answers))
                prop = self.parse(raw, p.text, new_value, q.answer_type, p.doc_id, role)
                if prop is None:
                    return ProposalOutcome([], "failed", f"{p.doc_id} LLM 提案未过逐字校验")
                props.append(prop)
                continue
            new = self.pool.borrow(q.id, q.text, old, q.answer_type, passage_text=p.text)
            if new is None:
                if q.answer_type in ("numeric", "date"):
                    new = ValuePool.fictional(old, q.answer_type, passage_text=p.text)
                if new is None:
                    return ProposalOutcome([], "failed", f"{p.doc_id} 无 Gate 5 合法借值/虚构值")
            props.append(Proposal((s, e), old, new, q.answer_type,
                                  "code-located" + (";llm-disambig" if used_llm else ""),
                                  p.doc_id, role))
        if not props:
            return ProposalOutcome([], "failed", "所有金段 0 命中")
        n_term = sum(pr.role == "terminal" for pr in props)
        if q.dataset == "hotpot" and n_term != 1:
            return ProposalOutcome([], "failed", f"末跳不唯一（{n_term}）")
        return ProposalOutcome(props, "llm_disambig" if used_llm else "auto")
