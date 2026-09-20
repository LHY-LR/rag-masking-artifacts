"""§0/§7-4：token 计数与切块统一用 Qwen 分词器。

真实运行：transformers 加载 config.TOKENIZER_ID（Qwen3 tokenizer，与规模无关）。
无依赖环境（mini）：SimpleTokenizer 词级回退——会打一次 warning，结果不得用于正式实验。
A3：两路径接口完全一致：encode(text)->list[int]、decode(ids)->str、count(text)->int。
"""
from __future__ import annotations

import re
import warnings

from .. import config

_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class SimpleTokenizer:
    """仅用于 mini 冒烟的词级回退，不是 Qwen BPE；id 单调递增，实例内可 decode 回词。"""
    is_qwen = False

    def __init__(self):
        self._id2tok: dict[int, str] = {}
        self._tok2id: dict[int, int] = {}
        self._next = 0

    def encode(self, text: str) -> list[int]:
        ids = []
        for tok in _WORD_RE.findall(text):
            key = hash(("tok", tok))  # 同词同 id（稳定映射）
            if key not in self._tok2id:
                self._tok2id[key] = self._next
                self._id2tok[self._next] = tok
                self._next += 1
            ids.append(self._tok2id[key])
        return ids

    def decode(self, ids: list[int]) -> str:
        return " ".join(self._id2tok.get(i, "") for i in ids).strip()

    def count(self, text: str) -> int:
        return len(_WORD_RE.findall(text))


class QwenCounter:
    is_qwen = True

    def __init__(self, model_id: str = config.TOKENIZER_ID):
        from transformers import AutoTokenizer
        self.tok = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

    def count(self, text: str) -> int:
        return len(self.tok.encode(text, add_special_tokens=False))

    def encode(self, text: str) -> list[int]:
        return self.tok.encode(text, add_special_tokens=False)

    def decode(self, ids: list[int]) -> str:
        return self.tok.decode(ids, skip_special_tokens=True)


_TOKENIZER = None


def get_tokenizer():
    """单例；优先 Qwen，失败回退 SimpleTokenizer（仅 mini）。"""
    global _TOKENIZER
    if _TOKENIZER is not None:
        return _TOKENIZER
    try:
        _TOKENIZER = QwenCounter()
    except Exception as e:
        warnings.warn(
            f"[冻结约束] Qwen 分词器不可用（{e!r}），回退词级 SimpleTokenizer；"
            "该回退只允许出现在 --mode=mini，正式实验必须安装 transformers 并下载 Qwen 分词器。",
            RuntimeWarning, stacklevel=2)
        _TOKENIZER = SimpleTokenizer()
    return _TOKENIZER
