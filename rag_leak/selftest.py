"""无依赖自检：统计算法、归一化、显存估算、双配置决策路径。

运行（A4：三入口任一均可）：
  python -m rag_leak.selftest
  python rag_leak/selftest.py
  python selftest.py
"""
from __future__ import annotations

import random
import sys
from pathlib import Path
from types import SimpleNamespace

if __package__ in (None, ""):  # A4：与 run_pipeline/cli 对齐的直接脚本入口 shim
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .generation.model import vram_estimate
from .generation.tokenization import SimpleTokenizer
from .schemas import FourArmRow, Paragraph, Proposal
from .data.value_pool import ValuePool
from .construct.replace import build_substituted
from .construct.gate import gate1_item
from .tables import t2_retrieval
from .stats.multiple import mcnemar_exact, holm, benjamini_hochberg
from .stats.power import n_required, z_quantile
from .stats.decision import gain_bootstrap_replicates, ranking_flip_probability, judge_sensitive
from .metrics.transition import transition_matrix, wilson_ci
from .metrics.normalize import normalize_answer, whole_occurrence_count


def _bline_invariant_selfcheck():
    """C19：B 线 Gate 5 前置准入、conditional retention 与 PP 语义回归。"""
    qs = [
        SimpleNamespace(answers=["10"], answer_type="numeric"),
        SimpleNamespace(answers=["12"], answer_type="numeric"),
        SimpleNamespace(answers=["13"], answer_type="numeric"),
    ]
    pool = ValuePool(qs, cooccur_fn=lambda _subject, _value: 0)
    passage = "The value was 10, while the earlier record was 12."
    # 12 是同段既有新值，必须被过滤；13 是唯一合法候选，且重复调用稳定。
    got1 = pool.borrow("q-target", "subject", "10", "numeric", passage_text=passage)
    got2 = pool.borrow("q-target", "subject", "10", "numeric", passage_text=passage)
    assert got1 == got2 == "13", (got1, got2)

    p = Paragraph("p", "t", passage)
    bad = Proposal((14, 16), "10", "12", "numeric", "test", "p")
    try:
        build_substituted("q-target", p, bad, ["10"])
        raise AssertionError("Gate 5 防御性断言应拒绝段内已出现的新值")
    except ValueError as exc:
        assert "Gate 5" in str(exc), exc

    # joint hit 不能冒充 P(sub|orig)：2/4 与 2/3 是不同概念。
    t2 = t2_retrieval.build([
        dict(retriever="b", dataset="trivia", orig_hit=True, sub_hit=True),
        dict(retriever="b", dataset="trivia", orig_hit=True, sub_hit=True),
        dict(retriever="b", dataset="trivia", orig_hit=True, sub_hit=False),
        dict(retriever="b", dataset="trivia", orig_hit=False, sub_hit=False),
    ])
    d = t2["b|trivia"]
    assert d["joint_hit_rate"] == 0.5 and abs(d["conditional_retain"] - 2 / 3) < 1e-12

    from .run_pipeline import _pp_retrieval_eligible
    from .schemas import RetrievalResult
    g1_fail = gate1_item(RetrievalResult("q", [], {"gold"}, 1),
                         RetrievalResult("q", [], {"gold"}, 1))
    assert _pp_retrieval_eligible(g1_fail, "require_pair_hit") is False
    assert _pp_retrieval_eligible(g1_fail, "structural_only") is True
    print("C19 B-line Gate 5 / conditional retention / PP policy OK")


def main():
    assert abs(z_quantile(0.975) - 1.959964) < 1e-3
    assert mcnemar_exact(0, 0) == 1.0
    assert [round(x, 3) for x in holm([0.01, 0.04, 0.03])] == [0.03, 0.06, 0.06]
    assert n_required(0.25, 0.03) > 0
    m = transition_matrix([1, 1, 1, 1], ["old", "other", "other", "other"])
    assert abs(m["residual_old"] - 0.25) < 1e-9
    lo, hi = wilson_ci(1, 4)
    assert 0 <= lo < hi <= 1
    assert normalize_answer("The 1815, date") == "1815 date"
    assert whole_occurrence_count("2006 had 2 events", "2") == 1
    assert whole_occurrence_count("Paris and Parisian", "Paris") == 1

    # A3：SimpleTokenizer 接口与 QwenCounter 对齐（encode->list[int]、decode->str、往返）
    st = SimpleTokenizer()
    ids = st.encode("U.S. film Inception 2010")
    assert isinstance(ids, list) and all(isinstance(i, int) for i in ids)
    assert st.decode(st.encode("inception film inception")) == "inception film inception"
    print("A3 tokenizer codec OK:", ids)

    print("== §9-3 8B 显存估算（公式化，真实以压测为准） ==")
    for bits in (16, 8, 4):
        e = vram_estimate(8, bits, 4096)
        print(f"  Qwen3-8B {bits:>2}bit @4096: weights={e['weights_gb']}GB "
              f"kv={e['kv_gb']}GB total={e['total_gb']}GB fits_8GB={e['fits_8gb']}")
    e = vram_estimate(8, 4, 1024)
    print(f"  Qwen3-8B Q4 @1024: total={e['total_gb']}GB fits_8GB={e['fits_8gb']}")

    print("== 双配置决策路径（合成数据；B1 比较对象=两配置校正增益 CI） ==")
    random.seed(1)

    def mk(shift):
        return [FourArmRow(f"q{i}", "m", "c",
                           1 if random.random() < 0.4 + shift else 0, 1, 0, 1)
                for i in range(60)]

    A = {"cfgX": mk(0.0), "cfgY": mk(0.05)}
    app = gain_bootstrap_replicates(A, "apparent_gain", B=1000)
    cor = gain_bootstrap_replicates(A, "corrected_gain", B=1000)
    p, ab, cb = ranking_flip_probability(app, cor)
    print(f"  P(排序改变)={p:.3f} 表观最优={ab} 校正最优={cb}")
    sep = judge_sensitive(0.9, (0.10, 0.20), (0.21, 0.30))   # 校正增益 CI 分离
    overlap = judge_sensitive(0.9, (0.10, 0.25), (0.20, 0.35))
    assert sep["in_sensitive_band"] is True and sep["corrected_ci_separated"] is True
    assert overlap["corrected_ci_separated"] is False and overlap["in_sensitive_band"] is False
    weak = judge_sensitive(0.5, (0.10, 0.20), (0.21, 0.30))  # P 不够
    assert weak["in_sensitive_band"] is False
    print("  B1 judge_sensitive 三例(分离/重叠/P不足) OK")
    _bline_invariant_selfcheck()
    _converter_selfcheck()
    print("ALL SELFTESTS OK")


def _converter_selfcheck():
    """C10″：windowed converter（rc parquet 行 dict → 窗口化 DPR json）纯逻辑自检。

    真实 rc 行是 dict-of-lists（rank/title/url/search_context 平行列表），entity_pages 为空 dict。
    这里直接用该形状的行 dict 迭代，不依赖 pyarrow/datasets。
    """
    from .data.load_trivia_rc import convert, _wb_spans_lower

    def row(q, nv, aliases, pages, ep=None):
        return {"question": q,
                "answer": {"normalized_value": nv, "aliases": aliases},
                "search_results": {"rank": list(range(len(pages))),
                                   "title": [p[0] for p in pages],
                                   "url": [""] * len(pages),
                                   "search_context": [p[1] for p in pages]},
                "entity_pages": (ep if ep is not None
                                 else {"title": [], "wiki_context": []})}

    fake = [
        # R1 保持：1889 出现两次，第一次窗口与问题共享 >=2 词（completed/tower）→ 金窗口；
        # "Paris" 页不含 alias → 干扰段。
        row("In which year was the Eiffel Tower completed?", "1889", [],
            [("Eiffel Tower", "The Eiffel Tower in Paris was completed in 1889 for the "
                              "World's Fair, and it opened on 31 March 1889."),
             ("Paris", "Paris is the capital of France.")]),
        # R2 保持：Berlin 出现两次且相距很远；只有第二次窗口与"Reichstag"共现 >=2 → 金窗收在第二次，
        # 窗口内 alias 恰好一次。
        row("In which city is the Reichstag building located?", "Berlin", [],
            [("Berlin", "Berlin is the capital of Germany and a cultural centre. "
                        "Thousands of words of unrelated filler text keep the two "
                        "occurrences far apart from one another entirely. " * 3 +
                        "The Reichstag building is in Berlin.")]),
        # R3 丢弃：alias 在页里出现，但没有任何窗口与问题共享 >=2 内容词 → no_gold
        row("Who directed Titanic?", "Cameron", [],
            [("Titanic", "A Cameron film won awards, yet this sentence says nothing about "
                         "directors or ocean liners or sinking ships.")]),
        # R4 丢弃：无候选页 → no_page
        row("no paras question here", "X", [], []),
        # R5 丢弃：无答案别名 → no_answer
        row("no answer given here", None, [], [("t", "some context body text.")]),
    ]

    res = convert(iter(fake), max_q=10, radius=90, min_overlap=2, prox=90, max_cand=5)
    st = res["stats"]
    assert st["kept"] == 2, st
    assert st["no_gold"] == 1 and st["no_page"] == 1 and st["no_answer"] == 1, st
    assert st["multi_alias_win"] == 0, st
    by_q = {r["question"]: r for r in res["rows"]}
    eif = by_q["In which year was the Eiffel Tower completed?"]
    win = eif["positive_ctxs"][0]["text"]
    # 窗口含答案且不含第二次 1889（单次出现）；干扰段=不含 alias 的 Paris 页
    assert len(_wb_spans_lower(win.lower(), "1889")) == 1, win
    assert eif["positive_ctxs"][0]["title"] == "Eiffel Tower"
    assert "completed" in win and "opened on 31 March 1889" not in win, win
    assert eif["answers"][0] == "1889"
    assert [n["title"] for n in eif["negative_ctxs"]] == ["Paris"], eif
    ber = by_q["In which city is the Reichstag building located?"]
    bwin = ber["positive_ctxs"][0]["text"]
    assert "Reichstag" in bwin and len(_wb_spans_lower(bwin.lower(), "berlin")) == 1, bwin
    assert "cultural centre" not in bwin, bwin  # 第二窗不含第一次 Berlin 所在句
    print("C10″ windowed converter（rc dict-of-lists → 窗口化 DPR json）逻辑 OK")


if __name__ == "__main__":
    main()
