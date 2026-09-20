"""§4.1 归一化：复用 DPR/FiD 的 normalize_answer（lowercase → 去 a/an/the → 去标点 → 折叠空白）。

来源：facebookresearch/DPR 与 google-research/FiD 的官方实现，逐步骤对齐。
另含 SQuAD 式 token F1 与"命中任一别名"判定（§7 不变量3：新旧 key 各对各的臂）。
"""
from __future__ import annotations

import re
import string
import collections

_ARTICLES = re.compile(r"\b(a|an|the)\b", re.UNICODE)
_PUNCT = re.compile(f"[{re.escape(string.punctuation)}]")
_WS = re.compile(r"\s+")

# Phase-B changelog: base 模型常输出 "The answer is X" / "Answer: X" 等前缀，
# 精确 EM 会把已答对的题判 0（如 hotpot-1251 1.7B 实际输出 "The answer is Shane Meadows"）。
# extract_answer 去掉常见答案前缀后再匹配，语义不变（仍是 EM），只是更鲁棒。
_ANSWER_PREFIXES = [
    r"^the answer is\s*:?\s*",
    r"^answer is\s*:?\s*",
    r"^answer\s*:?\s*",
    r"^the answer\s*:?\s*",
    r"^my answer is\s*:?\s*",
    r"^i think the answer is\s*:?\s*",
    r"^the correct answer is\s*:?\s*",
    r"^the short answer is\s*:?\s*",
]


# v3（协议修订，round-6 判读触发）：strict EM 的抽取从【首行】改【首句】。
# 动机（C13，round-6 实证）：base 模型常把所有内容输出在【同一行】（"1983. Foinavon won the
# Grand National in 1983."），frozen v2 取首行整串归一化 → 即便模型开口就答 1983 也判 0，
# 系统性低估 d（证据跟随）把 DiD 顶正。对格式干净的短答（Instruct），首句 = 首行，v3 严格
# 退化为 v2；只在 verbose 单行流水账上正确截断。
_SENT_SPLIT = re.compile(r"[.!?;]\s")


def _first_sentence(text: str) -> str:
    """按句子终结符(后随空白)取第一句。'. ' 需后随空白才算句界，避免 U.S./Sept. 内截断。"""
    if not text:
        return ""
    return _SENT_SPLIT.split(text, maxsplit=1)[0].strip()


def extract_answer(raw: str) -> str:
    """去掉模型输出中常见的答案前缀，返回纯答案文本（v3：首句口径）。

    取第一行（与 generation/model.py 的 .split("\\n")[0] 一致）→ 去掉行首答案前缀 →
    按句界截到第一句。对单行流水账（base）与换行短答（instruct）统一成立。
    """
    if not raw:
        return ""
    text = raw.strip().split("\n")[0].strip()
    for pat in _ANSWER_PREFIXES:
        m = re.match(pat, text, re.IGNORECASE)
        if m:
            text = text[m.end():].strip()
            break
    return _first_sentence(text)


def normalize_answer(s: str) -> str:
    """DPR/FiD 归一化，四步顺序不可换。"""
    if s is None:
        return ""
    s = str(s).lower().strip()
    s = "".join(ch for ch in s if ch not in set(string.punctuation))  # 去标点（仅留字母数字/空白）
    s = _ARTICLES.sub(" ", s)                                         # 去冠词
    s = _WS.sub(" ", s).strip()                                       # 折叠空白
    return s


def em_score(prediction: str, gold: str) -> int:
    return int(normalize_answer(extract_answer(prediction)) == normalize_answer(gold))


def em_any_alias(prediction: str, aliases: list[str]) -> int:
    """命中任一归一化别名即算对。Phase-B：先 extract_answer 去答案前缀。"""
    p = normalize_answer(extract_answer(prediction))
    return int(any(p == normalize_answer(a) for a in aliases))


def _tokens(s: str) -> list[str]:
    return normalize_answer(s).split()


def f1_score(prediction: str, gold: str) -> float:
    """SQuAD token F1（数字/专名部分命中时用；主指标仍是 EM）。"""
    pred_toks, gold_toks = _tokens(prediction), _tokens(gold)
    if not pred_toks or not gold_toks:
        return float(pred_toks == gold_toks)
    common = collections.Counter(pred_toks) & collections.Counter(gold_toks)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_toks)
    recall = num_same / len(gold_toks)
    return 2 * precision * recall / (precision + recall)


def f1_any_alias(prediction: str, aliases: list[str]) -> float:
    return max((f1_score(prediction, a) for a in aliases), default=0.0)


_NUMERIC_VALUE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")


def strict_numeric_boundary() -> bool:
    """数字粘连判定是否启用（由 `config.STRICT_NUMERIC_BOUNDARY` 控制，C34）。"""
    from .. import config
    return bool(getattr(config, "STRICT_NUMERIC_BOUNDARY", False))


def is_glued_to_number(text: str, i1: int, i2: int, value: str) -> bool:
    """这次命中是否嵌在**更长的数字表达式**里（`2.3` 里的 `3`、`3.4` 里的 `3`、`1,000` 里的 `000`）。

    仅当 value 自身是数字时判定；专名（Paris 等）不受影响。
    为什么需要：整词边界的字符类 `[0-9A-Za-z]` 不含小数点与千分位逗号，所以 `2.3` 里的 `3`
    会被判为一次"独立命中"——这正是 C32 审计中 17 条"改错位置"缺陷的入口。
    """
    if not _NUMERIC_VALUE.match(value):
        return False
    left = text[i1 - 1] if i1 > 0 else ""
    right = text[i2] if i2 < len(text) else ""
    if left.isdigit() or right.isdigit():
        return True
    if left in ".," and i1 >= 2 and text[i1 - 2].isdigit():
        return True
    if right in ".," and i2 + 1 < len(text) and text[i2 + 1].isdigit():
        return True
    return False


def whole_occurrence_count(text: str, value: str, numeric_strict: bool | None = None) -> int:
    """整词边界计数：'2' 不计入 '2006'，'Paris' 不计入 'Parisian'。

    闸门⑤与唯一性断言必须用它，不能用 str.count（子串计数会误判数字/专名）。
    `numeric_strict=None` 时取 `config.STRICT_NUMERIC_BOUNDARY`（见 C34）。
    """
    return len(find_whole_spans(text, value, numeric_strict))


def find_whole_spans(text: str, value: str,
                     numeric_strict: bool | None = None) -> list[tuple[int, int]]:
    """整词边界下的全部字面命中区间（原始文本偏移）。

    `numeric_strict` 为真时再排除"嵌在更长数字表达式里"的命中（`2.3` 里的 `3`）。
    """
    if not value:
        return []
    strict = strict_numeric_boundary() if numeric_strict is None else numeric_strict
    pat = r"(?<![0-9A-Za-z])" + re.escape(value) + r"(?![0-9A-Za-z])"
    out = []
    for m in re.finditer(pat, text):
        if strict and is_glued_to_number(text, m.start(), m.end(), value):
            continue
        out.append((m.start(), m.end()))
    return out

