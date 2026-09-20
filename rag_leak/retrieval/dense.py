"""稠密检索：bge + faiss（§0）。重依赖可选；只对被改 doc 重建向量（§7-6）。"""
from __future__ import annotations

from .. import config
from ..schemas import Paragraph, RetrievalResult

DENSE_MODEL_ID = "BAAI/bge-base-en-v1.5"  # 冻结，真实运行前确认离线可用


class DenseRetriever:
    available = False

    def __init__(self, paragraphs: list[Paragraph] | None = None,
                 model_id: str = DENSE_MODEL_ID, device: str = "cpu"):
        try:
            from sentence_transformers import SentenceTransformer
            import faiss  # noqa: F401
            self.model = SentenceTransformer(model_id, device=device)
            self._faiss = __import__("faiss")
            self.available = True
        except Exception as e:
            self.model = None
            self._err = repr(e)
            return
        self.paragraphs: list[Paragraph] = []
        self.index = None
        if paragraphs:
            self.build(paragraphs)

    def encode_texts(self, texts: list[str], normalize: bool = True):
        if not self.available:
            raise RuntimeError(f"bge/faiss 不可用：{getattr(self, '_err', '')}")
        import numpy as np
        v = self.model.encode(texts, normalize_embeddings=normalize,
                              convert_to_numpy=True, show_progress_bar=False)
        return np.ascontiguousarray(v, dtype="float32")

    def build(self, paragraphs: list[Paragraph]) -> None:
        self.paragraphs = list(paragraphs)
        emb = self.encode_texts([p.text for p in self.paragraphs])
        self.index = self._faiss.IndexFlatIP(emb.shape[1])
        self.index.add(emb)

    def update_documents(self, edited: dict[str, str]) -> None:
        """只重建被改 doc 的向量（doc_id 位置不变）。"""
        id2pos = {p.doc_id: i for i, p in enumerate(self.paragraphs)}
        emb = self.encode_texts([new for new in edited.values()])
        for (doc_id, _new), vec in zip(edited.items(), emb):
            pos = id2pos[doc_id]
            self.paragraphs[pos] = Paragraph(doc_id, self.paragraphs[pos].title, edited[doc_id])
            self.index.reset()  # 小规模重建（distractor 10 段级）；开放域需按 id 局部重建
            self.index.add(self.encode_texts([p.text for p in self.paragraphs]))

    def search(self, query: str, k: int = config.GOLD_RECALL_K) -> list[tuple[str, float]]:
        qv = self.encode_texts([query])
        sim, idx = self.index.search(qv, k)
        return [(self.paragraphs[i].doc_id, float(s)) for s, i in zip(sim[0], idx[0])]

    def to_result(self, question_id, hits, gold_doc_ids, k=config.GOLD_RECALL_K):
        return RetrievalResult(question_id, hits, gold_doc_ids, k)
