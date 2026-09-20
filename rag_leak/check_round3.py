"""Round3（第三次增进，自主实施）逐处可运行自检：R3-A 基准一致性 / B 闸门出口 / C overlay 可比性。

运行（三入口均可）：
  python -m rag_leak.check_round3
  python rag_leak/check_round3.py
全部断言通过才打印 ALL ROUND3 CHECKS OK。
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config, manifest as mf
from .construct.verdict import decide_verdict
from .construct import gate as gates
from .schemas import GateResult

HERE = Path(__file__).parent


def check_r3_a() -> None:
    # file_sha256 稳定且随内容改变
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        f = td / "a.txt"
        f.write_text("hello world", encoding="utf-8")
        a1 = mf.file_sha256(f)
        f.write_text("hello world2", encoding="utf-8")
        a2 = mf.file_sha256(f)
        assert a1 != a2 and len(a1) == 64, "R3-A: sha256 应为 64 hex 且内容改变则变"
        # code_sha 稳定、不含文件名敏感、不抛错（包内有源码即可算）
        sha1 = mf.code_sha(HERE.parent)
        assert isinstance(sha1, str) and len(sha1) == 64
        # build_manifest 结构完整
        toy = td / "nq_toy.json"
        toy.write_text('[{"question":"q","answers":["a"]}]', encoding="utf-8")
        m = mf.build_manifest(
            HERE.parent, "mini", "mini",
            data_paths=dict(nq=str(toy)), models=["stub"],
            config_key="gran=paragraph,bud=4096,k=5,rerank=False",
            gate_verdicts=dict(stub="GO"), datasets=[dict(name="nq_toy", n=1)])
        assert m["schema_version"] == "0.3"
        assert m["dataset_files"]["nq"] == mf.file_sha256(toy), "R3-A: manifest 须记录输入文件内容哈希"
        assert m["pipeline"]["code_sha"] == sha1
        assert "发布后再污染" in m["provenance_note"] and "版本" in m["provenance_note"]
        # write_manifest 写出合法 JSON
        out = mf.write_manifest(td, "mini", m)
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["run"]["config_key"] == "gran=paragraph,bud=4096,k=5,rerank=False"
        # _config_snapshot 引用的冻结常量均已捕获，且值与 config 一致（不抛 AttributeError）
        snap = m["config_snapshot"]
        for key in ("models", "decode", "gates", "gate_verdict", "min_n_for_gate",
                    "prompt_template", "budgets", "bootstrap_b", "decision_rule", "open_index_name"):
            assert key in snap, f"R3-A: config_snapshot 缺 {key}"
        assert snap["models"] == config.MODELS and snap["gate_verdict"] == config.GATE_VERDICT
        assert snap["min_n_for_gate"] == config.MIN_N_FOR_GATE
        # R3-A 回归护栏：datasets 题数必须按实际进入的题数分数据集统计，
        # 不能用 config.MINI_N/PILOT_N 写死（mini 的 nq/trivia/hotpot 各题数不相等）。
        from .run_pipeline import _dataset_counts
        fake = [SimpleNamespace(dataset=d) for d in ("nq", "nq", "hotpot", "trivia", "hotpot", "nq")]
        assert _dataset_counts(fake) == [dict(name="hotpot", n=2), dict(name="nq", n=3),
                                         dict(name="trivia", n=1)], "R3-A: datasets 题数应分组统计实际值"
    print("R3-A OK：manifest 含输入哈希 + 代码指纹 + 冻结快照 + 发布版本声明；write/load 闭环")


def check_r3_b() -> None:
    # decide_verdict：lower / higher / INSUFFICIENT
    assert decide_verdict(0.01, 0.02, 0.20, 0.35, "lower") == "GO"
    assert decide_verdict(0.25, 0.02, 0.20, 0.35, "lower") == "REVISE"
    assert decide_verdict(0.90, 0.02, 0.20, 0.35, "lower") == "ABANDON"
    assert decide_verdict(0.95, 0.90, 0.70, 0.55, "higher") == "GO"     # higher 方向：过限=GO
    assert decide_verdict(0.10, 0.90, 0.70, 0.55, "higher") == "ABANDON" # 太低=ABANDON
    assert decide_verdict(0.95, None, 0.70, 0.55, "higher") == "REVISE"  # 无目标档(go=None)不可判GO
    assert decide_verdict(float("nan"), 0.02, 0.20, 0.35, "lower") == "INSUFFICIENT"
    assert decide_verdict(0.5, 0.02, 0.20, 0.35, "lower", insufficient=True) == "INSUFFICIENT"
    # GateResult 含 verdict 字段且默认可序列化
    g = GateResult(1, True, 0.5, "d")
    assert g.verdict == "JUDGED"
    # 聚合闸门：达标 -> GO 出现在 verdict；不足 -> INSUFFICIENT
    g1 = gates.gate1_aggregate([g for _ in range(40)], recall_orig=1.0, recall_sub=0.99)
    assert g1.verdict in ("GO", "REVISE", "ABANDON"), f"R3-B: gate① 应有诊断出口，got {g1.verdict}"
    g1s = gates.gate1_aggregate([g for _ in range(5)], recall_orig=1.0, recall_sub=0.99)
    assert g1s.verdict == "INSUFFICIENT"
    g2s = gates.gate2_aggregate([1] * 5, ["old"] + ["new"] * 4, is_multi=True)
    assert g2s.verdict == "INSUFFICIENT"
    g3 = gates.gate3_aggregate([1] * 40, [1, 0] + [1] * 38)
    assert g3.verdict in ("GO", "REVISE", "ABANDON")
    g4 = gates.gate4_aggregate(["new"] * 40, model="Qwen3-0.6B")
    assert g4.verdict in ("GO", "REVISE", "ABANDON")
    # 不变量：passed 仍严格按 GATES（verdict 只诊断分类，不吞掉严格谓词）
    assert config.GATES[1]["retain_min"] == 0.90
    # gate_from_dict（R3-D）把 verdict 无缝往返
    d = dict(gate_id=1, passed=True, value=0.5, detail="d", status="JUDGED", verdict="GO")
    gr = __import__("rag_leak.schemas", fromlist=["gate_from_dict"]).gate_from_dict(d)
    assert gr.verdict == "GO" and gr.passed is True
    d2 = dict(gate_id=1, passed=None, value=0.5, detail="d")          # 兼容无 verdict 的旧 jsonl
    gr2 = __import__("rag_leak.schemas", fromlist=["gate_from_dict"]).gate_from_dict(d2)
    assert gr2.verdict == "JUDGED"
    print("R3-B OK：GO/REVISE/ABANDON/INSUFFICIENT 三档出口、四闸门聚合均带 verdict、passed 与 verdict 分层")


def check_r3_c() -> None:
    # overlay 可比性：无 Lucene analyzer 只允许显式 require_comparable=False
    from .retrieval.bm25_open import OpenBM25
    from .retrieval.bm25_score import tokenize, corpus_stats, doc_score, overlay_merge
    from .retrieval.bm25_distractor import _FallbackBM25
    corpus = [tokenize("alpha beta gamma"), tokenize("alpha beta delta")]
    eng = _FallbackBM25(corpus)
    N, avgdl, df = corpus_stats(corpus)
    base = eng.get_scores("alpha")
    base_hits = [(f"d{i}", float(base[i])) for i in range(N)]
    s0 = doc_score(tokenize("alpha"), tokenize("alpha omega"), df, N, avgdl,
                   config.BM25_K1, config.BM25_B)
    merged = overlay_merge(base_hits, {"d0": s0}, k=3)
    assert abs(dict(merged)["d1"] - base[1]) < 1e-12, "R3-C: 未改文档分必须保持"
    ob = OpenBM25(index_name="__synthetic__")
    assert ob._analyzer_kind == "unknown"
    hits, scores, comparable = ob.retrieve_pair("alpha", {"d0": "alpha omega"},
                                                k=3, stats=(N, avgdl),
                                                df_override=dict(df), require_comparable=False)
    assert comparable is False and any(s >= 0 for s in scores.values())
    try:
        ob.retrieve_pair("alpha", {"d0": "alpha omega"}, k=3, stats=(N, avgdl),
                         df_override=dict(df))
        raise AssertionError("R3-C: 默认 require_comparable=True 应拒绝非 LUCENE overlay")
    except RuntimeError:
        pass
    print("R3-C OK：overlay 无 Java 时显式标不可比并拒绝参与开放域 gate①排序")


def main():
    check_r3_a()
    check_r3_b()
    check_r3_c()
    print("\nALL ROUND3 CHECKS OK")


if __name__ == "__main__":
    main()
