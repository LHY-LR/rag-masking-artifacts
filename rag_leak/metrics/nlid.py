"""固定 NLI 蕴含模型（替代 RAGAS，回应第五轮评审问题9：judge 必须冻结版本）。

真实运行：锁定一个固定 entailment 模型 id（写死在 NLI_MODEL_ID，不允许用被测 Qwen 自判）。
mini/无依赖环境：StubNLI 返回 None（未知），调用方必须降级为只报 EM/支持事实召回。
"""
from __future__ import annotations

# 冻结：真实实验前确认该模型可离线加载，版本写进 changelog
NLI_MODEL_ID = "cross-encoder/nli-deberta-v3-small"


class StubNLI:
    available = False

    def entail(self, premise: str, hypothesis: str) -> float | None:
        return None


class FrozenNLI:
    available = True

    def __init__(self, model_id: str = NLI_MODEL_ID, device: str = "cpu"):
        try:
            from sentence_transformers import CrossEncoder  # 延迟重依赖
        except Exception as e:  # pragma: no cover
            raise ImportError("需要 sentence-transformers 才能使用 FrozenNLI") from e
        self.model = CrossEncoder(model_id, device=device)
        self.label_map = {0: "contradiction", 1: "entailment", 2: "neutral"}

    def entail(self, premise: str, hypothesis: str) -> float:
        scores = self.model.predict([(premise, hypothesis)])[0]
        # cross-encoder NLI 输出顺序依模型而定；此处返回 entailment 概率，真实接入时校准一次
        return float(scores[1])


def get_nli():
    try:
        return FrozenNLI()
    except Exception:
        return StubNLI()
