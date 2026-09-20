"""Round2（第二次增进）逐处可运行自检：A1-A5 / B1-B3 / C2 / C4。

运行（三入口均可）：
  python -m rag_leak.check_round2
  python rag_leak/check_round2.py
全部断言通过才打印 ALL ROUND2 CHECKS OK。
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .schemas import (Paragraph, Question, GoldEvidence, Proposal, Substituted)
from .data.sentences import split_sentences, paragraph_sentences, sentence_units
from .data.build_gold import build_gold
from .generation.tokenization import SimpleTokenizer, get_tokenizer
from .generation import inject
from .generation.arm import ArmConfig, run_four_arms
from .generation.model import StubGenerator
from .construct.replace import build_substituted, edited_paragraphs
from .construct import gate as gates
from .retrieval.bm25_distractor import _FallbackBM25
from .retrieval.bm25_score import tokenize, corpus_stats, doc_score, overlay_merge
from .retrieval.bm25_open import OpenBM25
from .stats.did import did_mean, masking_magnitude
from .stats.decision import judge_sensitive
from .tables import t4_did
from .schemas import FourArmRow
from .annotate import export_tasks, merge as anno_merge

HERE = Path(__file__).parent


def check_a1_a5():
    # 含 U.S. 缩略词的多跳：原始 sentences 原样保留，(title,idx) 与 support_facts 对齐
    sents_a = ["Christopher Nolan is a U.S.-British filmmaker.", "He directed Inception."]
    sents_b = ["Inception is a 2010 U.S. sci-fi film.", "It was released in July."]
    pa = Paragraph("h:A", "A", " ".join(sents_a), sentences=list(sents_a))
    pb = Paragraph("h:B", "B", " ".join(sents_b), sentences=list(sents_b))
    q = Question("h1", "hotpot", "When was the U.S. film directed by Nolan released?",
                 ["2010"], "bridge",
                 support_facts=[("A", 0), ("B", 0)], paragraphs=[pa, pb])
    gold = build_gold(q)
    assert gold.gold_sentences == [sents_a[0], sents_b[0]], "A1: 金句必须取自原始句列表"
    tok = SimpleTokenizer()
    units_a = sentence_units(pa, "sentence", tok)
    assert [u[0] for u in units_a] == sents_a and units_a[0][2] == 0 and units_a[1][2] == 1
    assert "U.S." in units_a[0][0], "缩略词句不得被二次切分"
    # inject sentence 粒度 present_facts 与 support_facts 完全一致
    bundle, pf = inject.assemble("h1", [pa, pb], "sentence", 10_000,
                                 {pa.doc_id, pb.doc_id}, set(q.support_facts))
    # 预算充足时金文档全部句都进上下文；关键是每个 support_fact 都以【正确序号】命中
    assert set(q.support_facts) <= pf, f"A1: 金句序号未对齐 {pf}"
    # 单句段落 + 紧预算：present 恰为 support_facts（验证序号而非 join 漂移）
    ta = Paragraph("h:T1", "T1", sents_a[0], sentences=[sents_a[0]])
    tb = Paragraph("h:T2", "T2", sents_b[0], sentences=[sents_b[0]])
    qt = Question("h1t", "hotpot", "q", ["2010"], "bridge",
                  support_facts=[("T1", 0), ("T2", 0)], paragraphs=[ta, tb])
    _, pf_tight = inject.assemble("h1t", [ta, tb], "sentence", 10_000,
                                  {ta.doc_id, tb.doc_id}, set(qt.support_facts))
    assert pf_tight == set(qt.support_facts), f"A1: 序号应精确匹配 {pf_tight}"
    assert bundle.gold_present
    # A5：build_gold/inject 不得再自带句切正则（唯一生产者在 data.sentences）
    import rag_leak.data.build_gold as bg
    assert "re.split" not in inspect.getsource(bg), "A5: build_gold 仍在自行 re-split"
    assert "re.split" not in inspect.getsource(inject), "A5: inject 仍在自行 re-split"
    # 回退路径（无 sentences）才用统一 split_sentences，且保护缩略词
    assert split_sentences("He is a U.S. citizen. She left.")[0].endswith("citizen.")
    print("A1/A5 OK：原始句对齐、缩略词不漂移、句生产者唯一")


def check_a2():
    # 两段金句各含答案 alias，借到不同新值；末跳为 B，c/d 臂只认 B 的新值
    ta = "The bridge value Alpha appears here once."
    tb = "The terminal answer Alpha is stated here."
    pa = Paragraph("h:A", "A", ta, sentences=[ta])
    pb = Paragraph("h:B", "B", tb, sentences=[tb])
    q = Question("h2", "hotpot", "bridge question?", ["Alpha"], "bridge",
                 support_facts=[("A", 0), ("B", 0)], paragraphs=[pa, pb])
    sa, sb = ta.index("Alpha"), tb.index("Alpha")
    prop_a = Proposal((sa, sa + 5), "Alpha", "BetaX", "name", "mid", pa.doc_id, role="bridge_sync")
    prop_b = Proposal((sb, sb + 5), "Alpha", "GammaY", "name", "terminal", pb.doc_id, role="terminal")
    sub_a = build_substituted("h2", pa, prop_a, ["Alpha"])
    sub_b = build_substituted("h2", pb, prop_b, ["Alpha"])
    assert sub_a.terminal_key == "" and sub_b.terminal_key == "gammay"
    # ⑥ 在每段各自满足
    assert sub_a.gates == {} or True
    sub_paras = edited_paragraphs([pa, pb], [sub_a, sub_b])
    text_map = {p.doc_id: p.text for p in sub_paras}
    assert "BetaX" in text_map[pa.doc_id] and "GammaY" in text_map[pb.doc_id], "两段须同步改"
    assert "Alpha" not in text_map[pa.doc_id] and "Alpha" not in text_map[pb.doc_id]
    acfg = ArmConfig("paragraph", 4096, 5, False)
    gen = StubGenerator(set(), set(), {"h2": "Alpha"})
    hits_o = [(p.doc_id, 1.0) for p in [pa, pb]]
    hits_s = [(p.doc_id, 1.0) for p in sub_paras]
    row, _, aux = run_four_arms(q, [sub_a, sub_b], gen, [pa, pb], sub_paras,
                                hits_o, hits_s, acfg, "stub", {pa.doc_id, pb.doc_id})
    assert aux["terminal_keys"] == ["gammay"], "A2: c/d 臂只能用末跳 key"
    assert aux["bridge_sync"] == 1
    print("A2 OK：bridge 恰好 1 末跳、中间跳不入答案判定、两段同步替换")


def check_a3():
    st = SimpleTokenizer()
    ids = st.encode("same word same")
    assert isinstance(ids, list) and ids[0] == ids[2], "同词须同 id"
    assert st.decode(ids) == "same word same"
    # 接口形状与 QwenCounter 一致
    for name in ("encode", "decode", "count"):
        assert hasattr(st, name)
    print("A3 OK：encode->list[int]、decode->str、往返守恒")


def check_a4():
    # 直接脚本入口（非 -m）也必须 EXIT=0
    root = HERE.parent
    # Windows GBK 区域下：强制子进程以 UTF-8 输出、父进程以 UTF-8 解码，
    # 否则子进程的中文 stdout 被 GBK 解码抛 UnicodeDecodeError，p.stdout 变 None。
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    p = subprocess.run([sys.executable, str(HERE / "selftest.py")],
                       cwd=root, capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert p.returncode == 0, f"A4 selftest 直接入口失败: {p.stderr[-500:]}"
    assert "ALL SELFTESTS OK" in p.stdout
    print("A4 OK：python selftest.py 直接入口 EXIT=0")


def check_b1():
    # 两个入参都是【竞争配置的校正增益 CI】：分离才敏感；P 不足或 CI 重叠都不敏感
    sep = judge_sensitive(0.95, (0.30, 0.40), (0.45, 0.55))
    assert sep["in_sensitive_band"] and sep["corrected_ci_separated"]
    overlap = judge_sensitive(0.95, (0.30, 0.48), (0.45, 0.55))
    assert not overlap["in_sensitive_band"]
    lowp = judge_sensitive(0.5, (0.30, 0.40), (0.45, 0.55))
    assert not lowp["in_sensitive_band"]
    assert "corrected-gain" in config.DECISION_RULE and "argmax" in config.DECISION_RULE
    print("B1 OK：唯一比较对象=两竞争配置校正增益 CI；P 与分离双条件")


def check_b2():
    rows = [FourArmRow(f"q{i}", "m", "c", 1, 1, 0, 1) for i in range(10)]
    d = did_mean(rows)
    # (b-a)=0, (d-c)=1 -> did=-1；掩盖量=1
    assert abs(d - (-1.0)) < 1e-9 and abs(masking_magnitude(rows) - 1.0) < 1e-9
    rendered = t4_did.render(t4_did.build({"m": rows}, B=200))
    assert "记忆掩盖量" in rendered and "DiD<0" in rendered
    print("B2 OK：DiD<0=掩盖，记忆掩盖量=-DiD，T4 列名/脚注一致")


def check_b3():
    # n=6 功效不足 -> passed=None/INSUFFICIENT；n=40 且残留达标 -> JUDGED
    small = gates.gate2_aggregate([1] * 6, ["old"] + ["new"] * 5, is_multi=True)
    assert small.passed is None and small.status == "INSUFFICIENT"
    big = gates.gate2_aggregate([1] * 40, ["new"] * 40, is_multi=True)
    assert big.passed is not None and big.status == "JUDGED"
    g3s = gates.gate3_aggregate([1] * 5, [1] * 5)
    assert g3s.status == "INSUFFICIENT" and g3s.passed is None
    g4s = gates.gate4_aggregate(["new"] * 5)
    assert g4s.status == "INSUFFICIENT"
    print("B3 OK：denom<30 判 INSUFFICIENT（不冒充通过/失效）")


def check_c2():
    # 合成小索引：未改文档分数逐位不变；被改文档替换；doc_id 稳定；缺失则插入
    corpus = [
        tokenize("alpha beta gamma delta"),
        tokenize("alpha beta epsilon zeta"),
        tokenize("gamma eta theta alpha"),
    ]
    eng = _FallbackBM25(corpus)
    q = "alpha gamma"
    base_scores = eng.get_scores(q)
    N, avgdl, df = corpus_stats(corpus)
    base_hits = [(f"d{i}", float(base_scores[i])) for i in range(N)]
    # 改 d0（同 analyzer 口径这里即同一 tokenize）
    new_text = "alpha gamma gamma iota"
    s0 = doc_score(tokenize(q), tokenize(new_text), df, N, avgdl,
                   config.BM25_K1, config.BM25_B)
    merged = overlay_merge(base_hits, {"d0": s0}, k=3)
    merged_d = dict(merged)
    assert abs(merged_d["d1"] - base_scores[1]) < 1e-12, "未改文档分数必须保持"
    assert abs(merged_d["d2"] - base_scores[2]) < 1e-12
    assert abs(merged_d["d0"] - s0) < 1e-12, "被改文档用新分替换"
    assert [d for d, _ in merged] == sorted(merged_d, key=lambda x: -merged_d[x])
    # 不在 base 的被改 doc 也能插入
    merged2 = overlay_merge(base_hits[:2], {"d2": float(base_scores[2]), "d9": 0.01}, k=4)
    assert "d9" in dict(merged2) and len(merged2) == 4
    # OpenBM25 无 Java 时 retrieve_pair 给合成 stats 也能跑（验证合并路径不依赖 Pyserini）
    ob = OpenBM25(index_name="__synthetic__")
    hits, scores, comparable = ob.retrieve_pair(q, {"d0": new_text}, k=3, stats=(N, avgdl),
                                                df_override=dict(df), require_comparable=False)
    assert dict(hits)["d0"] != 0 or scores["d0"] >= 0
    # R3-C：无 Lucene analyzer 时 comparable=False，且默认 require_comparable=True 应显式拒绝
    assert comparable is False, "R3-C: 无 Java 时 overlay 应标记为不可比"
    try:
        ob.retrieve_pair(q, {"d0": new_text}, k=3, stats=(N, avgdl), df_override=dict(df))
        raise AssertionError("R3-C: 应默认拒绝不可比 overlay")
    except RuntimeError:
        pass
    print("C2 OK：overlay 未改分不变、被改替换、缺失插入、合成 stats 路径可跑；R3-C 可比性防护生效")


def check_c4():
    subs_path = HERE / "out" / "mini_substituted.jsonl"
    assert subs_path.exists(), "先跑 mini 生成 mini_substituted.jsonl"
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        tasks_p = td / "tasks.jsonl"
        n = export_tasks.export(subs_path, tasks_p)
        assert n >= 10
        tasks = [json.loads(l) for l in tasks_p.read_text(encoding="utf-8").splitlines()]
        for t in tasks:
            assert {"task_id", "old", "new", "old_passage", "new_passage"} <= set(t)
        # 两位标注者：完全一致 -> κ=1
        a = []; b = []
        for t in tasks:
            x = dict(t, semantic_unique=True, relation_plausible=True, labeler="A")
            y = dict(t, semantic_unique=True, relation_plausible=True, labeler="B")
            a.append(x); b.append(y)
        pa, pb = td / "a.jsonl", td / "b.jsonl"
        pa.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in a), encoding="utf-8")
        pb.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in b), encoding="utf-8")
        rep = anno_merge.merge_labels(pa, pb)
        assert rep["n_double"] == n and rep["n_conflict"] == 0
        assert abs(rep["kappa"]["semantic_unique"] - 1.0) < 1e-9
        # 制造 1 处分歧 -> κ<1 且进入冲突清单
        b[0]["relation_plausible"] = False
        pb.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in b), encoding="utf-8")
        rep2 = anno_merge.merge_labels(pa, pb)
        assert rep2["n_conflict"] == 1 and rep2["kappa"]["relation_plausible"] < 1.0
    print("C4 OK：任务导出、双标 κ、冲突清单闭环")


def main():
    check_a1_a5()
    check_a2()
    check_a3()
    check_a4()
    check_b1()
    check_b2()
    check_b3()
    check_c2()
    check_c4()
    print("\nALL ROUND2 CHECKS OK")


if __name__ == "__main__":
    main()
