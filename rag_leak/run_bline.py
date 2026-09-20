"""B 线：真实检索 open 臂 —— 共享语料上 BM25 top-k，替换"每题自带 1 段金窗(≈oracle)"。

C18 说明：
- open 臂证据来源从"每题自家候选池（几乎只有金窗）"换成"共享语料（trivia-dev 全部窗口）
  的 BM25 top-k"。金窗真实参与排名，k 小时可能跌出 top-k -> 模型只能靠参数记忆答；
  k 大时金窗被召回到 -> 证据进上下文。
- 与 C 线唯一差别在 open 臂上下文。闭卷臂、prompt/解码/粒度预算、oracle 直给
  仍沿用冻结口径；B 线构集额外执行 Gate 5 前置唯一性筛选，故不能承诺与旧 C 线
  产物逐字节同一。
- 数据卫生（延续 C10' 单金段原则）：每题检索池剔除共享语料里【含该题任一旧答案别名】的窗口，
  保证 open_sub 上下文里没有未编辑的旧值复述污染 d。sub 语料 = 原语料仅该题金窗换新值。
- rank_bm25.get_scores 必须喂 token 列表（C18 检索 bug 修复），语料 token 预分词共享，
  只随题挑子集重建索引，避免每题重复 tokenize 整个语料。

用法（真实跑，proposal/substitution 与 C 线 deterministic 同源）：
  python -m rag_leak.run_bline --trivia data/trivia_dn.json --corpus data/trivia-dev.json \
      --models Qwen3-8B --k 5 --bits 4 --generator hf \
      --out rag_leak/out_b_trivia_dn_8b_k5 --pilot-n 449
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .run_pipeline import HERE, run_set, build_generator, _config_key, _t3_verdicts, _dataset_counts
from . import manifest as mf
from .data.load_raw import load_dpr_file
from .metrics.normalize import normalize_answer
from .retrieval.bm25_score import tokenize
from .schemas import Paragraph, RetrievalResult
from .tables import t1_audit, t2_retrieval, t3_gates, t4_did, t5_power, t6_ledger


# ---------------------------------------------------------------- 共享语料
def load_corpus(path: str) -> tuple[list[Paragraph], list[list[str]], list[str]]:
    """trivia-dev.json 全窗口作共享语料。返回 (Paragraphs, 每窗 token 列表, 归一化文本)。"""
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    paras, toks, norms = [], [], []
    for i, r in enumerate(rows):
        pos = (r.get("positive_ctxs") or [])
        if not pos:
            continue
        text = str(pos[0]["text"])
        if not text.strip():
            continue
        paras.append(Paragraph(doc_id=f"corpus:{i}",
                               title=str(pos[0].get("title", "")), text=text))
        toks.append(tokenize(text))
        norms.append(normalize_answer(text))
    return paras, toks, norms


def _answer_pattern(norm_ans: str) -> re.Pattern:
    return re.compile(r"(?<![0-9a-z])" + re.escape(norm_ans) + r"(?![0-9a-z])")


def _answer_patterns(answers: list[str]) -> list[re.Pattern]:
    """编译该题全部旧答案别名（normalize 后去重）。"""
    pats, seen = [], set()
    for answer in answers:
        norm = normalize_answer(answer)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        pats.append(_answer_pattern(norm))
    return pats


def _contains_answer(patterns: list[re.Pattern], norm_text: str) -> bool:
    return any(p.search(norm_text) is not None for p in patterns)


class _MemIndex:
    """对"共享语料 + 该题金窗"一次重建内存 BM25（token 预分词，只随题挑子集）。"""

    def __init__(self, paras: list[Paragraph], toks: list[list[str]], k1: float = config.BM25_K1,
                 b: float = config.BM25_B):
        from rank_bm25 import BM25Okapi
        self.paras = paras
        self.engine = BM25Okapi(toks, k1=k1, b=b)

    def search(self, query_tokens: list[str], k: int) -> list[tuple[str, float]]:
        scores = self.engine.get_scores(query_tokens)
        order = sorted(range(len(self.paras)), key=lambda i: -scores[i])[:k]
        return [(self.paras[i].doc_id, float(scores[i])) for i in order]


def make_bline_builder(corpus_paras, corpus_toks, corpus_norms, verbose: bool = False):
    """返回 run_set 的 retriever_builder(q, subs, gold, acfg)。

    语料 doc 是全仓库共享对象（引用复用，不拷贝正文）；每题只在共享里挑"不含旧答案"的子集。
    """
    n_doc = len(corpus_paras)
    n_sel_hist = []

    def builder(q, subs, gold, acfg):
        if len(gold.passages) != 1:
            raise ValueError(f"{q.id}: B 线要求单金段（trivia_dn 单金窗），实际 {len(gold.passages)} 段")
        gold_p = gold.passages[0]
        # 含任一旧答案别名 => 排除（答案整词边界，与 C 线 term_present 同口径）；
        # 金窗本身在共享语料中的原位置保留，避免 BM25 平分时因“gold 永远第 0 个”
        # 被稳定排序人为抬到 rank 1。
        pats = _answer_patterns(q.answers)
        gold_idx = next((i for i, p in enumerate(corpus_paras)
                         if p.text == gold_p.text), None)
        if gold_idx is None:
            raise ValueError(f"{q.id}: gold 窗不在共享 corpus（文本不一致）")
        sel = [i for i in range(n_doc)
               if i != gold_idx and corpus_paras[i].text != gold_p.text
               and not _contains_answer(pats, corpus_norms[i])]
        sel_set = set(sel)
        n_sel_hist.append(len(sel))
        if verbose:
            print(f"[bline] {q.id} corpus_sel={len(sel)}/{n_doc} (excl all aliases)")

        # sub 版金窗正文 = 该题 substitution 的新段落（按 old_passage 文本映射）
        new_of = {s.old_passage: s.new_passage for s in subs}
        if gold_p.text not in new_of:
            raise ValueError(f"{q.id}: gold 窗未在 substitution 中（应被替换）")
        gold_s = Paragraph(doc_id=gold_p.doc_id, title=gold_p.title, text=new_of[gold_p.text])

        # 按共享语料原始顺序构造两个索引；只在 gold 原位置替换文本，保证平分 tie-break
        # 与共享 corpus 顺序一致，且 orig/sub 的 doc 顺序完全相同。
        ctx_o, ctx_s, toks_o, toks_s = [], [], [], []
        for i in range(n_doc):
            if i == gold_idx:
                ctx_o.append(gold_p)
                ctx_s.append(gold_s)
                toks_o.append(tokenize(gold_p.text))
                toks_s.append(tokenize(gold_s.text))
            elif i in sel_set:
                ctx_o.append(corpus_paras[i])
                ctx_s.append(corpus_paras[i])
                toks_o.append(corpus_toks[i])
                toks_s.append(corpus_toks[i])
        qt = tokenize(q.text)

        idx_o = _MemIndex(ctx_o, toks_o)
        idx_s = _MemIndex(ctx_s, toks_s)
        hits_o = idx_o.search(qt, acfg.k)
        hits_s = idx_s.search(qt, acfg.k)
        gold_ids = {p.doc_id for p in gold.passages}
        rr_o = RetrievalResult(q.id, hits_o, gold_ids, acfg.k)
        rr_s = RetrievalResult(q.id, hits_s, gold_ids, acfg.k)
        return ctx_o, ctx_s, hits_o, hits_s, rr_o, rr_s, f"bm25-corpus[k={acfg.k}]"

    return builder


# ---------------------------------------------------------------- 桩（无 GPU 冒烟，验证管线符号）
class _MemoryStub:
    """确定性桩：60% 题有参数记忆（cb_orig）；开卷若目标串在上下文则答目标，
    否则记忆题回旧值、非记忆题留空。用于验证 B 线检索接线与召回梯度是否机械地传导到
    b/d —— 不做任何模型行为声明。"""

    def __init__(self, memorized_ids: set[str], old_answer_of: dict[str, str]):
        self.memorized = memorized_ids
        self.old = old_answer_of

    def generate(self, question: str, context: str | None, target_surface: str | None = None,
                 question_id: str = "", arm: str = "") -> str:
        has_memory = question_id in self.memorized
        if context:  # 开卷：有证据先跟随；无证据时只有记忆题复读旧值
            if target_surface and target_surface in context:
                return target_surface
            return self.old.get(question_id, "") if has_memory else ""
        # 闭卷：cb_sub 对新 key 没有参数记忆；cb_orig 只有记忆题答旧值。
        if arm == "cb_sub":
            return ""
        return self.old.get(question_id, "") if has_memory else ""


# ---------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B 线：共享语料真检索 open 臂（k 轴）")
    ap.add_argument("--trivia", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", default="Qwen3-8B")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--budget", type=int, default=1024, choices=config.BUDGETS)
    ap.add_argument("--granularity", default="paragraph", choices=config.GRANULARITIES)
    ap.add_argument("--generator", choices=["stub", "hf", "remote"], default="hf")
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--vllm_url", default="")
    ap.add_argument("--pilot-n", type=int, default=0,
                    help="抽样规模；>=len 时全量（C 线同池用 449）")
    ap.add_argument("--inspect", type=int, default=0)
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    from .generation.arm import ArmConfig
    acfg = ArmConfig(args.granularity, args.budget, args.k, rerank=False)

    questions = load_dpr_file(args.trivia, "trivia")
    if args.pilot_n:
        from .data.make_subset import deterministic_sample
        questions = deterministic_sample(questions, min(args.pilot_n, len(questions)),
                                         seed=config.RNG_SEED)
    print(f"[bline] 题数={len(questions)}；k={args.k}；模型={args.models}；生成={args.generator}")

    corpus_paras, corpus_toks, corpus_norms = load_corpus(args.corpus)
    print(f"[bline] 共享语料窗口={len(corpus_paras)}")
    builder = make_bline_builder(corpus_paras, corpus_toks, corpus_norms, verbose=args.inspect > 0)

    for model_name in [m.strip() for m in args.models.split(",") if m.strip()]:
        kind = "remote" if model_name == config.MODEL_32B and args.generator == "hf" else args.generator
        if kind == "stub":
            # 冒烟：取前 60% 题作"参数记忆"（机械验证检索梯度传导），不做行为声明
            ids = [q.id for q in questions]
            mem = set(ids[: int(len(ids) * 0.6)])
            old_of = {q.id: q.answers[0] for q in questions}
            gen = _MemoryStub(mem, old_of)
        else:
            gen = build_generator(kind, model_name, args.bits, args.device, args.vllm_url)
        label = f"pilot_{model_name.replace('/', '_')}"
        res = run_set(questions, gen, model_name, acfg, out_dir, label,
                      proposer=None, inspect_n=args.inspect, retriever_builder=builder,
                      pp_retrieval_policy="structural_only",
                      t2_retention_mode="conditional", record_retrieval_rows=True)
        print(f"\n########## {model_name} ##########")
        _TABLES = (("t1", t1_audit), ("t2", t2_retrieval), ("t3", t3_gates),
                   ("t4", t4_did), ("t5", t5_power), ("t6", t6_ledger))
        rendered = []
        for key, t in _TABLES:
            text = (t.render(res[key], retention_mode=res["t2_retention_mode"])
                    if key == "t2" else t.render(res[key]))
            print(text)
            rendered.append(text)
        (out_dir / f"{label}_summary.txt").write_text(
            "\n".join(rendered), encoding="utf-8")
        # B 线只用 trivia(题池)+corpus(共享语料)，不喂 nq/hotpot（空串会让 file_sha256
        # 打开 Path('')=='.' -> 对目录开读，Windows 上 PermissionError）
        b_data = {name: p for name, p in
                  (("nq", ""), ("trivia", args.trivia), ("hotpot", ""), ("corpus", args.corpus))
                  if p}
        m = mf.build_manifest(
            HERE, "bline", label,
            data_paths=b_data,
            models=[model_name], config_key=_config_key(acfg),
            gate_verdicts=_t3_verdicts(res["t3"]),
            datasets=_dataset_counts(questions))
        print(f"[R3-A] 已写 manifest -> {mf.write_manifest(out_dir, label, m)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
