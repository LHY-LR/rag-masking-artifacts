"""§4.3 值池：从本数据集【其他题】借值，按类型/粒度/数量级 bin/NER 匹配。

约束：
- 原值 != 新值；
- 新值与"问题主体"在全语料 0 共现（程序预筛，cooccur_fn 注入，默认全语料 grep）；
- 关系合理性人审（防借到同乐队成员/配偶）——程序只做预筛，闸门⑦记人审结果；
- 虚构值仅 numeric/date（等位数、合理区间），name 禁止虚构。
"""
from __future__ import annotations

import hashlib
import re
import random

from .. import config
from ..metrics.normalize import normalize_answer, whole_occurrence_count

_NUM_RE = re.compile(r"^[\d.,]+$")


def _magnitude_bin(v: str) -> int:
    try:
        x = abs(float(v.replace(",", "")))
        if x == 0:
            return 0
        return len(str(int(x)))  # 位数即数量级 bin
    except ValueError:
        return -1


def _date_gran(v: str) -> str:
    if re.fullmatch(r"\d{4}", v.strip()):
        return "year"
    return "full"


def _year(v: str) -> int | None:
    s = v.strip()
    if re.fullmatch(r"\d{4}", s):
        y = int(s)
        if 1000 <= y <= 2100:      # 只把"像年份"的四位数分年代桶；范围外按旧口径处理
            return y
    return None


def _era_bin(v: str, width: int) -> int | None:
    y = _year(v)
    return None if y is None else y // width


def _same_value(new: str, old: str) -> bool:
    """C53：规范形相同或互相包含 ⇒ 视为"没换值"（同一实体的另一种写法）。

    实例（E 线实测）：Wagner→Wagners、St. Louis→st louis、Keats→Keatsian、
    Burma→BurmaMyanmar、100000→100,000。这类植入既不改变答案语义，又把 c/d 一起抬高。
    长度下限 3 字符，避免 "a" in "..." 之类的误判。
    """
    n_new, n_old = normalize_answer(new), normalize_answer(old)
    if not n_new or not n_old:
        return False
    if n_new == n_old:
        return True
    return (len(n_new) >= 3 and len(n_old) >= 3
            and (n_new in n_old or n_old in n_new))


class ValuePool:
    def __init__(self, questions, cooccur_fn=None, seed: int = 20260903):
        """questions: 全量 Question（借值来源）；cooccur_fn(subject, value)->int 共现次数。"""
        self.buckets: dict[tuple, list[str]] = {}
        self._entity_sig: dict[str, frozenset] = {}   # C52：答案 -> 其来源题的领域签名
        self._entity_ntok: dict[str, int] = {}        # C52：答案 -> 词数档位
        self._qid_forms: dict[str, frozenset] = {}    # C54：题 id -> 该题答案的**全部写法**
        self._qtype: dict[str, str] = {}              # C55：答案 -> 其来源题问的答案种类
        for q in questions:
            forms = frozenset(normalize_answer(a) for a in (q.answers or [])
                              if a and str(a).strip())
            qid = getattr(q, "id", None)          # selftest 里用 SimpleNamespace，无 id
            if qid and forms:
                self._qid_forms[qid] = forms
            _tk = self._type_key(getattr(q, "text", "") or "")
            for a in (q.answers or []):
                if a and str(a).strip():
                    self._qtype.setdefault(str(a), _tk)
            for a in q.answers:
                # execution-fix: comparison 题的 yes/no 不是实体名/数字/日期，
                # 若入 name 池会被 bridge 题借走导致 "yes (born 1956) is..." 语法崩坏。
                if q.answer_type == "comparison" and a.strip().lower() in ("yes", "no"):
                    continue
                key = self._bucket_key(q.answer_type, a)
                self.buckets.setdefault(key, []).append(a)
                # C44：strict 年份桶下，把每个年份**同时**挂到旧桶 ("date","year")，
                # 作为"同年代/邻年代都空"时的兜底候选来源。
                if len(key) == 3 and key[0] == "date" and key[1] == "year":
                    self.buckets.setdefault(("date", "year"), []).append(a)
                if key == ("name",):
                    self._entity_sig.setdefault(a, self._signature(q.text))
                    self._entity_ntok.setdefault(a, self._ntok_bin(a))
        if config.STRICT_ENTITY_DOMAIN:
            self._build_signature_idf(questions)
        # 去重保序
        for k, vs in self.buckets.items():
            seen, uniq = set(), []
            for v in vs:
                if v not in seen:
                    seen.add(v)
                    uniq.append(v)
            self.buckets[k] = uniq
        self.cooccur_fn = cooccur_fn or (lambda s, v: 0)
        self.rng = random.Random(seed)

    # ---------------- C52：实体领域约束 ----------------
    @staticmethod
    def _words(text: str) -> set:
        return {w for w in re.findall(r"[a-z]{%d,}" % config.ENTITY_SIG_MIN_LEN, (text or "").lower())}

    def _build_signature_idf(self, questions) -> None:
        """算全库词频，再给每题取"低频实词"作为领域签名（df 越低越有区分度）。"""
        df: dict[str, int] = {}
        per_q = []
        for q in questions:
            ws = self._words(q.text)
            per_q.append(ws)
            for w in ws:
                df[w] = df.get(w, 0) + 1
        self._df = df
        cut = max(4, int(config.ENTITY_SIG_DF_FRAC * max(1, len(questions))))
        self._sig_cut = cut
        # ★ 取"**有区分度又可能被共享**"的词：df 在 [2, cut] 之间，且**按 df 从高到低**取前 K 个。
        #   踩过的坑：一开始按 df 从低到高取，取到的全是题目独有的专有名词（如 "Sputnik"），
        #   两道题永远不可能共享 → 实测 400 条里 41% 的借值重合度仍是 0，约束形同虚设。
        #   改成取"最热门但仍低于切点"的词（album / band / born / city），才是真正的主题词。
        for q, ws in zip(questions, per_q):
            # C53：并列必须用**全序**破。原来只按 -df 排序，df 大量并列时次序来自
            # set 迭代序 = 字符串哈希随机化 ⇒ 同一输入在两个进程里选出不同的 6 个签名词，
            # 进而借到不同的值（E 线实测：new 臂两跑 117/363 题植入值不同；PYTHONHASHSEED=0
            # 时两次结果逐字节一致）。加第二键 `w` 后签名表跨进程确定。
            info = sorted((w for w in ws if 2 <= df.get(w, 0) <= cut),
                          key=lambda w: (-df.get(w, 0), w))
            a0 = q.answers[0] if q.answers else ""
            self._entity_sig[a0] = frozenset(info[:config.ENTITY_SIG_TOPK])

    def _signature(self, text: str) -> frozenset:
        """未开 strict 时只需占位；开了 strict 会在 _build_signature_idf 里覆盖。"""
        # C53：同样要全序，否则占位签名也随哈希种子变化。
        return frozenset(sorted(self._words(text))[:config.ENTITY_SIG_TOPK])

    @staticmethod
    def _ntok_bin(v: str) -> int:
        n = len([t for t in re.split(r"\s+", v.strip()) if t])
        return 1 if n <= 1 else (2 if n == 2 else 3)

    # ---------------- C55：答案类型约束（回应"签名匹配的是题材、不是答案种类"） ----------------
    _WH_PATTERNS = (
        ("count", re.compile(r"\bhow (many|much)\b", re.I)),
        ("year", re.compile(r"\b(which|what|in what|of what) year\b|\bwhat year\b", re.I)),
        ("time", re.compile(r"^\s*(when|in what year|on what date|what date)\b", re.I)),
        ("person", re.compile(r"\b(who|whose|whom)\b", re.I)),
        ("place", re.compile(r"\bwhich (city|town|village|country|state|county|island|region|place|capital)\b", re.I)),
        ("work", re.compile(r"\bwhich (album|song|single|film|movie|book|novel|play|musical|opera|series|"
                            r"band|group|company|team|club|magazine|newspaper|painting|sculpture)\b", re.I)),
        ("org", re.compile(r"\bwhich (company|organisation|organization|agency|party|army|navy|airline|"
                           r"university|college|school|hospital|museum|church|cathedral)\b", re.I)),
    )

    @classmethod
    def _type_key(cls, question_text: str) -> str:
        """题目在问哪一类答案（粗桶，纯规则）。用于**类型相容**过滤，不依赖 NER。"""
        t = question_text or ""
        for name, pat in cls._WH_PATTERNS:
            if pat.search(t):
                return name
        return "other"

    @staticmethod
    def _has_digit(v: str) -> bool:
        return bool(re.search(r"\d", v or ""))

    def _type_ok(self, cand: str, subject_text: str) -> bool:
        """候选是否与**目标题**问的答案种类相容（两类检查）。
        ① 数字形态：题面问 count/year 之外的种类时，候选不应是纯数字（反之亦然）。
        ② wh 桶：候选来源题与目标题的 wh 桶一致，或至少都属于"实体名"大桶（person/place/work/org/other）。
        """
        cand_qt = self._qtype.get(cand)
        if cand_qt is None:
            return True                     # 没有来源题信息就不拦
        tgt = self._type_key(subject_text)
        if tgt in ("count", "year", "time"):
            return cand_qt in ("count", "year", "time")
        return cand_qt not in ("count", "year", "time")

    def _entity_ladder(self, old: str):
        """C44 式的逐级放宽：一级最严，最后一级是**旧口径**（保证不丢题）。"""
        sig_old, band = self._entity_sig.get(old, frozenset()), self._entity_ntok.get(old, 1)
        def ok(cand, min_overlap, need_band):
            if need_band and self._entity_ntok.get(cand, 1) != band:
                return False
            return len(sig_old & self._entity_sig.get(cand, frozenset())) >= min_overlap
        return [lambda c: ok(c, config.ENTITY_OVERLAP_MIN, True),
                lambda c: ok(c, 1, True),
                lambda c: ok(c, 0, True),
                lambda c: True]


    @staticmethod
    def _bucket_key(t: str, v: str) -> tuple:
        # bridge/comparison 的末跳值若本身是数字/日期，按值类型入池，保证同数量级借值
        if t == "date" or (t in ("bridge", "comparison") and _date_gran(v) == "year"
                           and re.fullmatch(r"\d{4}", v.strip())):
            # C44：strict 时年份再按年代分桶（同桶优先，见 _candidate_keys）
            if config.STRICT_DATE_ERA:
                era = _era_bin(v, config.DATE_ERA_WIDTH)
                if era is not None:
                    return ("date", "year", era)
            return ("date", _date_gran(v))
        if t == "numeric" or (t in ("bridge", "comparison") and _NUM_RE.match(v.strip())):
            return ("numeric", _magnitude_bin(v))
        # name / bridge / comparison 的实体名按粗 NER=name 池
        return ("name",)

    def _candidate_keys(self, answer_type: str, old: str) -> list[tuple]:
        """借值候选桶，按优先级排列。

        C44（Gate③ 修复）：strict 模式下年份先取**同年代桶**，空了再依次放宽到 ±1、±2、±3 个年代桶，
        最后才落到"全部年份"这个旧桶。这样绝大多数条目借到的是"同年代但不真实"的年份——
        既荒谬到模型不能从常识拒绝，又偏离到不与记忆重合（正是 C43 诊断给出的设计判据）。
        """
        key = self._bucket_key(answer_type, old)
        keys = [key]
        if len(key) == 3 and key[0] == "date" and key[1] == "year":
            era = key[2]
            keys += [("date", "year", era + d) for d in (1, -1, 2, -2, 3, -3)]
            keys.append(("date", "year"))   # 兜底：旧口径（__init__ 里已把每个年份同时挂到这个桶）
        return keys

    def borrow(self, question_id: str, subject: str, old: str, answer_type: str,
               deterministic: bool = True, passage_text: str | None = None) -> str | None:
        """返回满足约束的借值；若给出目标段落，新值不得已在段中整词出现。

        这一筛选与 Gate 5 使用同一 whole_occurrence_count，确保替换后新值只能
        出现在被编辑的那个 span。筛选发生在哈希选值前，因此在同一可选集合中仍跨
        进程确定；只有原候选违反新不变量时才会换到下一个合法值。
        """
        cands = []
        for key in self._candidate_keys(answer_type, old):
            cands = [v for v in self.buckets.get(key, [])
                     if v != old and self.cooccur_fn(subject, v) == 0
                     and (passage_text is None or whole_occurrence_count(passage_text, v) == 0)]
            if cands:
                break
        if not cands:  # name 不允许跨到数字池
            return None
        # C52：实体领域约束。逐级放宽（一级最严 → 最后一级=旧口径），
        # 因此**没有一条题会因为约束太紧而失去候选**（与 C44 年代桶同一纪律）。
        if answer_type == "name" and config.STRICT_ENTITY_DOMAIN:
            # C54 自借守卫：候选若属于**目标题自己答案表里的另一种写法**，就不是"换值"而是"换名字"。
            # TriviaQA 每题 answers 中位 11、均值 15.6、最多 183 个写法，而领域约束把候选缩小到
            # "同主题"——最同主题的恰恰是自己那些别名 ⇒ 实测 **62%（225/363）** 的题借到了自己的别名
            # （旧桶候选近千、近似随机，实测 0%）。后果：`c` 与 `d` 一起被真值的记忆抬高，**完全伪造出
            # "约束让顺从率上升、掩盖量上升"**。以下两个守卫都只在 strict 实体分支生效，
            # 因此**冻结产物（C 线/B 线/HotpotQA/旧桶臂）逐位可复现**（改动候选表会移动 sha256 取模位）。
            own_forms = self._qid_forms.get(question_id, frozenset())
            if own_forms:
                kept = [v for v in cands if normalize_answer(v) not in own_forms]
                if kept:
                    cands = kept
            # C53 同值守卫：领域约束偏好"同主题"的候选，而同一实体的另一种写法
            # （Wagner→Wagners、St. Louis→st louis、Keats→Keatsian）恰恰同主题且签名重叠最高，
            # 于是被优先借走 —— 这种植入**根本没换值**，却会把 c（闭卷答出植入值）与
            # d（开卷替换臂）一起抬高，从而伪造"掩盖量变小"。E 线实测占比 13.5%（49/363）。
            # 两个守卫都是**偏好而非硬过滤**：过滤后为空就退回未过滤候选，保住"零条丢候选"纪律。
            base = [v for v in cands if not _same_value(v, old)] or cands
            # C55 类型约束（env 门控 RAGLEAK_STRICT_ENTITY_TYPE，默认关）：签名匹配的是"题材"，
            # 会借到**种类不对**的值（count 题借到城市名、角色名题借到抽象短语、行星数量题借到人名）。
            # 52 条人工样例里约 2/3 属此类，是把实体臂 masking 压成负值的主要嫌疑。按 wh 桶偏好式过滤。
            if config.STRICT_ENTITY_TYPE:
                typed = [v for v in base if self._type_ok(v, subject)]
                if typed:
                    base = typed
            # ⚠️ 历史注记：产出**守卫前** `out_ent_new_*` 产物的代码里，这段阶梯被写了两遍
            # （第二遍在已收窄的候选集上会继续收窄，故非幂等）。C54 之后已合并为**单遍**，
            # 与 `out_ent_new2_*` 产物一致（已逐题复核）；旧产物只作对照保留。
            for level, gate in enumerate(self._entity_ladder(old)):
                sub = [v for v in base if gate(v)]
                if sub:
                    cands = sub
                    break
        # execution-fix: 用 question_id 哈希选候选，避免所有题都借到 cands[0]（值池头部集中）。
        # 同一 question_id 始终选同一值（可复现），不同题分散到不同候选。
        if deterministic:
            # execution-fix: 内置 hash(str) 受 PYTHONHASHSEED 影响，跨进程不同→同一题借不同值，
            # 破坏 R3-A 可复现性。改用 sha256 稳定摘要（跨进程/跨机一致）。
            idx = int(hashlib.sha256((question_id + "|" + old).encode("utf-8")).hexdigest(), 16) % len(cands)
            return cands[idx]
        return self.rng.choice(cands)

    @staticmethod
    def fictional(old: str, answer_type: str, rng: random.Random | None = None,
                  passage_text: str | None = None) -> str | None:
        """仅 numeric/date 允许虚构；若给出段落，候选也必须满足 Gate 5。"""
        rng = rng or random.Random(20260903)

        def allowed(candidate: str) -> bool:
            return candidate != old.strip() and (
                passage_text is None or whole_occurrence_count(passage_text, candidate) == 0)

        if answer_type == "numeric" and _NUM_RE.match(old.strip()):
            digits = len(old.strip().replace(",", "").replace(".", "").lstrip("0") or "0")
            lo = 10 ** (digits - 1) if digits > 1 else 0
            hi = 10 ** digits - 1
            for _ in range(100):  # 不得与原值相同，且不得已在目标段内出现
                cand = str(rng.randint(max(lo, 1), hi))
                if allowed(cand):
                    return cand
            return None
        if answer_type == "date" and re.fullmatch(r"\d{4}", old.strip()):
            y = int(old)
            for d in [-7, -5, 5, 7, 11, -11, 13]:  # 等位数、邻近但不相等
                cand = str(y + d)
                if allowed(cand):
                    return cand
        if answer_type == "name":
            raise ValueError("name 类型禁止虚构（§4.3，风格工件）")
        return None


def corpus_cooccurrence_factory(all_texts: list[str]):
    """全语料 0 共现预筛：subject 与 value 是否在同一段落共现（粗粒度，闸门⑦再人审）。"""
    joined = [t.lower() for t in all_texts]

    def _cooccur(subject: str, value: str) -> int:
        s, v = subject.lower().strip(), value.lower().strip()
        if not s or not v:
            return 0
        return sum(1 for t in joined if s in t and v in t)
    return _cooccur
