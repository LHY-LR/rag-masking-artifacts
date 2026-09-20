# -*- coding: utf-8 -*-
"""entity_experiment.py —— E 线（实体借值领域约束）的池子构建与离线验证。

背景见 `config.STRICT_ENTITY_DOMAIN` 的注释：round-4/5 发现 name 类只有粗桶
`("name",)`，会跨类借值（篮球运动员 ← 电子游戏）→ 模型拒答 → `d` 臂塌方 →
name 子集 DiD 变成正的。当时的处置是"需换同类型值池（构造改动，大）"，被推迟至今。

两个子命令：

  python -m rag_leak.entity_experiment build      # 生成 data/trivia_name.json
  python -m rag_leak.entity_experiment validate   # 离线对比 旧桶 vs 领域约束 的借值质量

`validate` **不需要 GPU**：它直接调用 ValuePool 在两种设置下借值，比较
领域签名重合度、词数档位一致率，并断言**没有一条题因约束太紧而丢掉候选**。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config                                     # noqa: E402
from .data.load_raw import infer_answer_type             # noqa: E402
from .data.value_pool import ValuePool                   # noqa: E402
from .metrics.normalize import whole_occurrence_count    # noqa: E402
from .schemas import Question                            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _a0(row):
    for a in (row.get("answers") or []):
        if str(a).strip():
            return str(a).strip()
    return ""


def build(src: str = "data/trivia-dev.json", out: str = "data/trivia_name.json") -> int:
    """name 类切片：答案类型为 name，且答案在末跳金窗里**整词唯一命中**（四臂可构造）。"""
    rows = json.loads((ROOT / src).read_text(encoding="utf-8"))
    kept, no_gold, not_unique = [], 0, 0
    for r in rows:
        a0 = _a0(r)
        if not a0 or infer_answer_type(a0) != "name":
            continue
        ctxs = r.get("positive_ctxs") or []
        if not ctxs:
            no_gold += 1
            continue
        text = ctxs[-1].get("text", "")
        if whole_occurrence_count(text, a0) != 1:
            not_unique += 1
            continue
        kept.append(r)
    p = ROOT / out
    p.write_text(json.dumps(kept, ensure_ascii=False), encoding="utf-8")
    print("in=%s: %d 行" % (src, len(rows)))
    print("  非 name 或空答案: 跳过")
    print("  name 但无金窗: %d" % no_gold)
    print("  name 但末窗非唯一命中: %d" % not_unique)
    print("→ %s: **%d 行**" % (out, len(kept)))
    return len(kept)


def _questions(rows) -> list[Question]:
    qs = []
    for r in rows:
        a0 = _a0(r)
        ctxs = r.get("positive_ctxs") or []
        qs.append(Question(id=r.get("question_id") or r.get("id") or "",
                           dataset="trivia", text=r.get("question", ""),
                           answers=[a0], answer_type="name"))
    return qs


def _borrow_all(rows, strict: bool):
    """在指定设置下给每道题借一次值，返回 (question_id, old, new) 列表。

    开关直接 patch `config` 的模块属性（`borrow`/`__init__` 都是运行时读它），
    比 reload 模块稳，也避免与别的 import 顺序纠缠。
    """
    from .data.value_pool import ValuePool as VP
    config.STRICT_ENTITY_DOMAIN = strict
    try:
        qs = _questions(rows)
        pool = VP(qs)
        out = []
        for q, r in zip(qs, rows):
            ctxs = r.get("positive_ctxs") or []
            text = ctxs[-1].get("text", "") if ctxs else ""
            new = pool.borrow(q.id, r.get("question", ""), q.answers[0], "name",
                              passage_text=text)
            out.append((q.id, q.answers[0], new))
        return out
    finally:
        config.STRICT_ENTITY_DOMAIN = False


def validate(src: str = "data/trivia_name.json", n: int = 400) -> None:
    rows = json.loads((ROOT / src).read_text(encoding="utf-8"))[:n]
    print("验证用 %d 条（取自 %s）" % (len(rows), src))
    old_list = _borrow_all(rows, strict=False)
    new_list = _borrow_all(rows, strict=True)

    from .data.value_pool import ValuePool as VP2
    config.STRICT_ENTITY_DOMAIN = True
    try:
        vp = VP2(_questions(rows))
        sig, band = vp._entity_sig, vp._entity_ntok
    finally:
        config.STRICT_ENTITY_DOMAIN = False

    def stats(pairs):
        miss = sum(1 for _, _, v in pairs if not v)
        ov = Counter()
        band_ok = 0
        for _, o, v in pairs:
            if not v:
                continue
            k = len(sig.get(o, frozenset()) & sig.get(v, frozenset()))
            ov[k] += 1
            band_ok += int(band.get(o, 1) == band.get(v, 1))
        n_ok = sum(1 for _, _, v in pairs if v)
        return miss, ov, (band_ok / n_ok if n_ok else 0.0)

    m_old, ov_old, b_old = stats(old_list)
    m_new, ov_new, b_new = stats(new_list)
    print()
    print("%-26s %8s %14s %14s" % ("设置", "无候选", "★平均签名重合", "词数档位一致率"))
    print("-" * 68)
    for tag, (m, ov, b) in [("旧口径（粗桶）", (m_old, ov_old, b_old)),
                            ("领域约束（strict）", (m_new, ov_new, b_new))]:
        tot = sum(ov.values()) or 1
        avg = sum(k * c for k, c in ov.items()) / tot
        print("%-26s %8d %14.2f %13.1f%%" % (tag, m, avg, b * 100))
    print()
    print("新口径的签名重合分布:", dict(sorted(ov_new.items())))
    assert m_new == 0, "约束太紧导致 %d 条题失去候选——违反 C44 纪律" % m_new
    print()
    print("✅ 无一条题因约束丢失候选（与 C44 年代桶同一纪律）")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="E 线：实体借值领域约束")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--in", dest="inp", default="data/trivia-dev.json")
    b.add_argument("--out", default="data/trivia_name.json")
    v = sub.add_parser("validate")
    v.add_argument("--in", dest="inp", default="data/trivia_name.json")
    v.add_argument("--n", type=int, default=400)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        build(a.inp, a.out)
    else:
        validate(a.inp, a.n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
