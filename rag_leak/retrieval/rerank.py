"""cross-encoder 重排（可选；缺依赖时 IdentityReranker 保持原序）。"""
from __future__ import annotations

RERANK_MODEL_ID = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # 冻结


class IdentityReranker:
    available = True

    def rerank(self, query: str, units: list[tuple[str, str]]) -> list[tuple[str, str]]:
        return list(units)


class CrossEncoderReranker:
    available = False

    def __init__(self, model_id: str = RERANK_MODEL_ID, device: str = "cpu"):
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_id, device=device)
            self.available = True
        except Exception as e:
            self._err = repr(e)

    def rerank(self, query: str, units: list[tuple[str, str]]) -> list[tuple[str, str]]:
        if not self.available:
            raise RuntimeError(f"cross-encoder 不可用：{getattr(self, '_err', '')}")
        scores = self.model.predict([(query, t) for _, t in units])
        order = sorted(range(len(units)), key=lambda i: -float(scores[i]))
        return [units[i] for i in order]


def get_reranker(use: bool):
    if not use:
        return IdentityReranker()
    r = CrossEncoderReranker()
    return r if r.available else IdentityReranker()
