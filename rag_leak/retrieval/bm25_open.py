"""§4.4 开放域 BM25 —— Pyserini（预建 DPR 2018-12-20 维基索引）。

§9 待确认 2（已查证，官方文档）：
    from pyserini.search.lucene import LuceneSearcher
    searcher = LuceneSearcher.from_prebuilt_index(INDEX_NAME)
    hits = searcher.search(query, k=k)
    hits[i].docid / hits[i].score
预建索引名在 config.OPEN_INDEX_NAME（经典 'wikipedia-dpr-100w'；新版有 wiki-all-6-3.* 变体）。

C2 编辑 overlay：预建索引只读，对被改 doc 用【同一 Lucene analyzer】重算 BM25 分，
未改 doc 保持原索引分数，overlay_merge 替换/插入结果行，doc_id 不变。
analyzer/集合统计在无 Pyserini(Java) 环境不可得，此时 retrieve_pair 明确报错；
overlay 的合并语义由 check_round2 的合成索引冒烟覆盖（不依赖 Java）。
"""
from __future__ import annotations

import json
from pathlib import Path

from .. import config
from ..schemas import RetrievalResult
from .bm25_score import tokenize as regex_tokenize, doc_score, overlay_merge


class OpenBM25:
    available = False

    def __init__(self, index_name: str | None = None):
        self.index_name = index_name or config.OPEN_INDEX_NAME
        self._analyzer = None
        self._analyzer_kind = "unknown"   # 'lucene' | 'regex_fallback'（R3-C 判定可比性）
        self._reader = None
        try:
            from pyserini.search.lucene import LuceneSearcher  # 延迟重依赖
            self.searcher = LuceneSearcher.from_prebuilt_index(self.index_name)
            self.available = True
        except Exception as e:
            self.searcher = None
            self._err = repr(e)

    # ---------- analyzer / 统计量（与原索引同口径） ----------
    def _lucene_analyzer(self):
        if self._analyzer is not None:
            return self._analyzer
        from pyserini.analysis import Analyzer, get_lucene_analyzer
        self._analyzer = Analyzer(get_lucene_analyzer())
        return self._analyzer

    def analyze(self, text: str) -> list[str]:
        """优先 Lucene analyzer（与建索引同口径）；无 Java 回退正则并告警（仅允许冒烟）。

        R3-C：记录实际用的 analyzer 类型（_analyzer_kind），供 retrieve_pair 判可比性。
        """
        try:
            out = self._lucene_analyzer().analyze(text)
            self._analyzer_kind = "lucene"
            return out
        except Exception:
            import warnings
            warnings.warn("Lucene analyzer 不可用，overlay 回退正则分词（与原索引口径可能有 stemming 差异）",
                          RuntimeWarning, stacklevel=2)
            self._analyzer_kind = "regex_fallback"
            return regex_tokenize(text)

    def _index_reader(self):
        if self._reader is None:
            from pyserini.index import IndexReader
            self._reader = IndexReader(self.index_name)
        return self._reader

    def collection_stats(self) -> tuple[int, float]:
        """返回 (N, avgdl)，取自原索引，保证被改文档与未改文档同一集合口径。"""
        r = self._index_reader()
        st = r.stats()
        n = int(st["documents"])
        total = int(st["total_terms"])
        return n, (total / n if n else 0.0)

    def term_df(self, term: str) -> int:
        _, df = self._index_reader().get_term_counts(term, analyzer=None)
        return int(df or 0)

    # ---------- 检索 ----------
    def search(self, query: str, k: int = config.GOLD_RECALL_K) -> list[tuple[str, float]]:
        if not self.available:
            raise RuntimeError(
                "Pyserini/预建索引不可用。开放域检索需先安装 pyserini 并下载索引 "
                f"{self.index_name}（mini 切片请使用 distractor 口径）。原始错误：{getattr(self, '_err', '')}")
        hits = self.searcher.search(query, k=k)
        return [(h.docid, float(h.score)) for h in hits]

    def edited_doc_score(self, query: str, new_text: str,
                         N: int | None = None, avgdl: float | None = None) -> float:
        """对单个被改文档，用原索引 N/avgdl/df 重算 BM25（同 analyzer）。"""
        N0, avg0 = (N, avgdl) if N is not None else self.collection_stats()
        q_toks = self.analyze(query)
        d_toks = self.analyze(new_text)
        df = {t: self.term_df(t) for t in set(q_toks)}
        return doc_score(q_toks, d_toks, df, N0, avg0, config.BM25_K1, config.BM25_B)

    def retrieve_pair(self, query: str, edited: dict[str, str],
                      k: int = config.GOLD_RECALL_K,
                      stats: tuple[int, float] | None = None,
                      df_override: dict[str, int] | None = None,
                      require_comparable: bool = True) -> tuple[list, dict, bool]:
        """C2/R3-C：返回 (合并后 hits, {doc_id: 重算分}, comparable)。edited={doc_id: 新文本}。

        stats/df_override 仅用于无 Java 的合成冒烟；真实运行留空、走原索引统计。
        R3-C：comparable=True 仅当被改文档用【与原索引同一 Lucene analyzer】重算（无 stemming 差异）；
        无 Java 时回退正则分词会与原索引分数不可比，此时若 require_comparable=True 则【显式拒绝】，
        避免开放域 gate① 被"分数口径不一致"误判。合成冒烟请传 require_comparable=False。
        """
        if not self.available and stats is None:
            raise RuntimeError("Pyserini 不可用且未提供合成 stats；开放域 overlay 需真实索引。")
        deepen = k + len(edited)
        base = self.search(query, deepen) if self.available else []
        N, avgdl = stats if stats is not None else self.collection_stats()
        edited_scores = {}
        comparable = True
        for doc_id, new_text in edited.items():
            q_toks = self.analyze(query)
            d_toks = self.analyze(new_text)
            if self._analyzer_kind != "lucene":
                comparable = False
            if df_override is not None:
                df = {t: df_override.get(t, 0) for t in set(q_toks)}
            else:
                df = {t: self.term_df(t) for t in set(q_toks)}
            edited_scores[doc_id] = doc_score(q_toks, d_toks, df, N, avgdl,
                                              config.BM25_K1, config.BM25_B)
        if require_comparable and not comparable:
            raise RuntimeError(
                "open-domain overlay 不可比：被改 doc 用正则回退分词（可能带 stemming 差异），"
                "与原索引分数不同口径，无法与未改 doc 的 Pyserini 分共同排序。"
                "请安装 Pyserini/Java 以用同一 Lucene analyzer，或显式传 require_comparable=False（仅冒烟）。")
        return overlay_merge(base, edited_scores, k), edited_scores, comparable

    def rebuild_edited(self, edited_docs: list[dict], out_index_dir: str) -> str:
        """C2：只对被改文档建增量小索引（doc_id 保持）。

        edited_docs: [{"id": doc_id, "contents": new_text}]
        优先用 pyserini LuceneIndexer 程序化建；不可用时落 jsonl 并返回离线命令。
        """
        out = Path(out_index_dir)
        out.mkdir(parents=True, exist_ok=True)
        inp = out.parent / f"{out.name}_input"
        inp.mkdir(exist_ok=True)
        with (inp / "docs.jsonl").open("w", encoding="utf-8") as f:
            for d in edited_docs:
                f.write(json.dumps({"id": d["id"], "contents": d["contents"]}, ensure_ascii=False) + "\n")
        try:
            from pyserini.index.lucene import LuceneIndexer
            indexer = LuceneIndexer(str(out))
            indexer.add_batch_dict({d["id"]: {"contents": d["contents"]} for d in edited_docs})
            indexer.close()
            return str(out)
        except Exception:
            cmd = (f"python -m pyserini.index.lucene -collection JsonCollection "
                   f"-generator DefaultLuceneDocumentGenerator -threads 1 "
                   f"-input {inp} -index {out} -storePositions -storeDocvectors")
            (out / "INDEX_COMMAND.txt").write_text(cmd, encoding="utf-8")
            return cmd

    def to_result(self, question_id: str, hits, gold_doc_ids: set[str],
                  k: int = config.GOLD_RECALL_K) -> RetrievalResult:
        return RetrievalResult(question_id, list(hits), gold_doc_ids, k)
