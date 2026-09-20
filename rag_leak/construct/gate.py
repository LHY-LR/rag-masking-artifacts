"""§5 八道闸门，逐题判定，GateResult 出口；②③④⑧为集合级聚合。"""
from __future__ import annotations

from .. import config
from ..schemas import RetrievalResult, GateResult, Substituted
from ..metrics.normalize import normalize_answer, whole_occurrence_count
from ..metrics.transition import transition_matrix, sequential_gate
from ..metrics.compliance import classify_output
from .verdict import decide_verdict


# ---------- ① 检索等价（逐题；句级也要过——调用方对三档粒度各跑一次） ----------
def gate1_item(rr_orig: RetrievalResult, rr_sub: RetrievalResult) -> GateResult:
    hit_o, hit_s = rr_orig.gold_hit(), rr_sub.gold_hit()
    retained = int(hit_o and hit_s)
    return GateResult(
        1, bool(retained), float(retained),
        f"orig_hit={int(hit_o)} sub_hit={int(hit_s)} hit->miss={int(hit_o and not hit_s)}")


def gate1_aggregate(items: list[GateResult], recall_orig: float, recall_sub: float,
                    cfg: dict | None = None, min_n: int | None = None) -> GateResult:
    cfg = cfg or config.GATES[1]
    min_n = config.MIN_N_FOR_GATE[1] if min_n is None else min_n
    vt = config.GATE_VERDICT[1]
    retain = sum(g.value for g in items) / len(items) if items else float("nan")
    drop = recall_orig - recall_sub
    n_items = len(items)
    detail = (f"retain={retain:.3f} recall_drop={drop:+.3f} "
              f"(orig={recall_orig:.3f},sub={recall_sub:.3f})")
    if n_items < min_n:  # R3-B：① 也要 INSUFFICIENT
        g = GateResult(1, None, retain, f"INSUFFICIENT(n={n_items}<{min_n}) {detail}",
                       status="INSUFFICIENT")
        g.verdict = "INSUFFICIENT"
        return g
    passed = (retain >= cfg["retain_min"]) and (drop <= cfg["recall_drop_max"])
    g = GateResult(1, passed, retain, detail)
    # verdict 基于 recall_drop 档位；但若保留率本身不达标，不能判 GO——降级 REVISE/ABANDON
    v = decide_verdict(drop, vt["go"], vt["revise"], vt["abandon"], vt["direction"])
    if retain < cfg["retain_min"]:
        v = "ABANDON" if retain < 0.5 else "REVISE"
    g.verdict = v
    return g


# ---------- ② 塌陷（集合级，§4.7 转移矩阵） ----------
def gate2_aggregate(cb_orig_correct: list[bool], cb_sub_class: list[str],
                    is_multi: bool, model: str = "", cfg: dict | None = None,
                    min_n: int | None = None) -> GateResult:
    cfg = cfg or config.GATES[2]
    min_n = config.MIN_N_FOR_GATE[2] if min_n is None else min_n
    m = transition_matrix(cb_orig_correct, cb_sub_class)
    limit = cfg["resid_32b"] if "32B" in model else (cfg["resid_multi"] if is_multi else cfg["resid_single"])
    resid = m["residual_old"]
    detail = (f"resid_old={resid:.3f} Wilson95=({m['ci_low']:.3f},{m['ci_high']:.3f}) "
              f"n={m['denom']} new={m['n_new']} other={m['n_other']} limit={limit}")
    if m["denom"] < min_n:  # B3：功效不足，不判通过/失效
        g = GateResult(2, None, resid if resid == resid else 0.0,
                       f"INSUFFICIENT(n={m['denom']}<{min_n}, 待足够样本再判) {detail}",
                       status="INSUFFICIENT")
        g.verdict = "INSUFFICIENT"
        return g
    seq = sequential_gate(resid, m["denom"], cfg)
    passed = (resid <= limit) and (m["ci_high"] <= limit + 0.05)  # CI 上界不超出阈值太多
    vt = config.GATE_VERDICT[2]
    g = GateResult(2, passed, resid, detail + f" seq={seq}")
    # verdict：用已解析的 limit 作 go（随规模/单多跳不同），revise/abandon 用默认档
    g.verdict = decide_verdict(resid, limit, vt["revise"], vt["abandon"], vt["direction"])
    return g


# ---------- ③ oracle 可答性（逐题 + 集合聚合） ----------
def gate3_item(ora_orig_em: int, ora_sub_em: int) -> GateResult:
    return GateResult(3, bool(ora_orig_em == ora_sub_em),
                      float(ora_sub_em - ora_orig_em), f"orig={ora_orig_em} sub={ora_sub_em}")


def gate3_aggregate(ora_orig: list[int], ora_sub: list[int], cfg: dict | None = None,
                    min_n: int | None = None) -> GateResult:
    min_n = config.MIN_N_FOR_GATE[3] if min_n is None else min_n
    drop = (sum(ora_orig) - sum(ora_sub)) / max(1, len(ora_orig))
    cfg = cfg or config.GATES[3]
    detail = (f"EM_orig={sum(ora_orig)/len(ora_orig):.3f} "
              f"EM_sub={sum(ora_sub)/len(ora_sub):.3f} drop={drop:+.3f}")
    if len(ora_orig) < min_n:
        g = GateResult(3, None, drop,
                       f"INSUFFICIENT(n={len(ora_orig)}<{min_n}) {detail}",
                       status="INSUFFICIENT")
        g.verdict = "INSUFFICIENT"
        return g
    vt = config.GATE_VERDICT[3]
    g = GateResult(3, abs(drop) <= cfg["drop_max"], drop, detail)
    g.verdict = decide_verdict(abs(drop), vt["go"], vt["revise"], vt["abandon"], vt["direction"])
    return g


# ---------- ④ 冲突顺从（逐题分类 + 集合聚合） ----------
def gate4_item(raw_output: str, new_aliases: list[str], old_aliases: list[str]) -> tuple[GateResult, str]:
    cls = classify_output(raw_output, new_aliases, old_aliases)
    return GateResult(4, cls == "new", 1.0 if cls == "new" else 0.0, f"class={cls}"), cls


def gate4_aggregate(classes: list[str], model: str = "", cfg: dict | None = None,
                    min_n: int | None = None) -> GateResult:
    min_n = config.MIN_N_FOR_GATE[4] if min_n is None else min_n
    cfg = cfg or config.GATES[4]
    rate = sum(c == "new" for c in classes) / len(classes) if classes else float("nan")
    limit = cfg["rate_min_32b"] if "32B" in model else cfg["rate_min"]
    if len(classes) < min_n:
        g = GateResult(4, None, rate if rate == rate else 0.0,
                       f"INSUFFICIENT(n={len(classes)}<{min_n}) compliance={rate:.3f} limit={limit}",
                       status="INSUFFICIENT")
        g.verdict = "INSUFFICIENT"
        return g
    vt = config.GATE_VERDICT[4]
    g = GateResult(4, rate >= limit, rate,
                   f"compliance={rate:.3f} limit={limit} n={len(classes)}")
    g.verdict = decide_verdict(rate, limit, vt["revise"], vt["abandon"], vt["direction"])
    return g


# ---------- ⑤ key 唯一性：新值在改后段恰好 1 次（程序部分） ----------
def gate5_item(sub: Substituted) -> GateResult:
    n = whole_occurrence_count(sub.new_passage, sub.proposal.new)  # 整词边界，'2'≠'2006'
    return GateResult(5, n == 1, float(n), f"new_value_whole_count={n}（语义唯一性另需人审）")


# ---------- ⑥ 编辑局部：span 外零改动（构造保证，防御性复核） ----------
def gate6_item(sub: Substituted) -> GateResult:
    s, e = sub.proposal.char_span
    expected = sub.old_passage[:s] + sub.proposal.new + sub.old_passage[e:]
    ok = expected == sub.new_passage
    outside_changed = 0 if ok else 1
    return GateResult(6, ok, 1.0 - outside_changed, "span 外零改动" if ok else "span 外存在改动")


# ---------- ⑦ 值不可猜：0 共现（程序）+ 关系合理性（人审结果传入） ----------
def gate7_item(cooccur: int, human_ok: bool = True) -> GateResult:
    return GateResult(7, cooccur == 0 and human_ok, float(cooccur),
                      f"cooccur={cooccur} human_relation_ok={human_ok}")


# ---------- ⑧ 标注可靠：Cohen's κ ----------
def cohen_kappa(labels_a: list, labels_b: list) -> float:
    assert len(labels_a) == len(labels_b)
    n = len(labels_a)
    if n == 0:
        return float("nan")
    classes = sorted(set(labels_a) | set(labels_b))
    po = sum(a == b for a, b in zip(labels_a, labels_b)) / n
    pe = 0.0
    for c in classes:
        pa = sum(a == c for a in labels_a) / n
        pb = sum(b == c for b in labels_b) / n
        pe += pa * pb
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def gate8_aggregate(labels_a: list, labels_b: list, cfg: dict | None = None) -> GateResult:
    cfg = cfg or config.GATES[8]
    k = cohen_kappa(labels_a, labels_b)
    return GateResult(8, k >= cfg["kappa_min"], k, f"cohen_kappa={k:.3f} n_double={len(labels_a)}")
