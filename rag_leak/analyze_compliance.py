"""Phase C 诊断（C9）：compliance 离线拆解 —— 把"真不顺从"和"仪器误差"分开。

输入：run_pipeline 落盘的 `{label}_oracle_rows.jsonl`（C8，逐题含 ora_sub 原始输出、
term_key/term_present 真冲突标记、new/old aliases、arms_raw）。
输出：stdout 拆解表 + 同目录 `{label}_decomp.json`。

判定逻辑（全部只读复盘，不改任何冻结指标）：
- 真冲突子集 = term_present=True（替换 key 确实出现在金替换证据里；否则模型无从答新值，
  记成"不顺从"是分母掺水 → 无操作试次）。
- 冗长/近答 = 输出里【整词包含】新 key（strict EM/classify 要求整行相等，会把
  "…is called the Bologna Process." 这类完整句判 0）。
- 拒答 = 命中拒绝标记（None of the provided / does not mention …）。
分法：先判 new（整词包含），再判 old，再判 refusal，其余 other。顺序与冻结的
classify_output 一致（new 优先，避免旧值是新值子串）。
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

from .metrics.normalize import extract_answer, normalize_answer, whole_occurrence_count

# 拒绝标记（小写、整串包含匹配）。覆盖 Instruct 在"证据与常识矛盾"时的保守措辞。
_REFUSAL_MARKERS = [
    "none of the provided", "does not mention", "doesn't mention", "does not state",
    "doesn't state", "is not mentioned", "isn't mentioned", "does not contain",
    "doesn't contain", "no information", "no mention", "not mentioned", "not enough",
    "cannot be determined", "cannot determine", "can't be determined", "can't determine",
    "not stated", "not provided", "does not provide", "doesn't provide", "not specified",
    "not available in the", "no context provided", "i don't know", "i don't have",
    "unknown", "not known",
]

# 四臂 → 真值别名映射（orig 臂对旧 key，sub 臂对新 key，与 §7-3 一致）
_ARM_KEY = {"cb_orig": "old", "open_orig": "old", "cb_sub": "new", "open_sub": "new"}


def _wb(text: str, alias: str) -> bool:
    """整词边界包含（大小写不敏感）。空别名/空文本返回 False。"""
    if not text or not alias:
        return False
    t = text.lower()
    a = alias.lower()
    pat = r"(?<![0-9a-z])" + re.escape(a) + r"(?![0-9a-z])"
    return re.search(pat, t) is not None


def _refusal(text: str) -> bool:
    t = extract_answer(text).lower()
    return any(m in t for m in _REFUSAL_MARKERS)


def _categorize(raw: str, new_aliases: list[str], old_aliases: list[str]) -> str:
    """new/old/refusal/other —— 整词包含口径（宽松），用于把 strict=0 拆开。"""
    if not raw:
        return "empty"
    for a in new_aliases:
        if _wb(raw, a):
            return "new"
    for a in old_aliases:
        if _wb(raw, a):
            return "old"
    if _refusal(raw):
        return "refusal"
    return "other"


def _rate(xs: list[bool]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def _row_stats(rows: list[dict], label: str, out: dict) -> None:
    n = len(rows)
    strict = [r["cls_sub"] == "new" for r in rows]
    contain = [_categorize(r["ora_sub"], r["new_aliases"], r["old_aliases"]) == "new"
               for r in rows]
    cat = [_categorize(r["ora_sub"], r["new_aliases"], r["old_aliases"]) for r in rows]
    strict_fail = [c for c, s in zip(cat, strict) if not s]
    counts = {c: strict_fail.count(c) for c in dict.fromkeys(strict_fail)}
    block = dict(
        n=n,
        compliance_strict=round(_rate(strict), 4),   # 冻结口径（= metrics.compliance）
        compliance_contain=round(_rate(contain), 4),  # 宽松：整词包含新 key
        strict_fail_breakdown=counts,                 # strict 未过者按 cat 拆分
    )
    out[label] = block
    print(f"--- {label} (n={n}) ---")
    print(f"  compliance_strict   = {block['compliance_strict']:.3f}   （冻结口径，=metrics 的 compliance）")
    print(f"  compliance_contain  = {block['compliance_contain']:.3f}   （整词包含新 key，宽松）")
    print(f"  strict 未过的拆分（宽容口径）: {counts}")
    print()


def _arm_contain_means(rows: list[dict]) -> dict:
    """四臂在"整词包含对应别名"口径下的 EM 均值（宽松版 a/b/c/d）。"""
    means: dict[str, float] = {}
    for arm in ("cb_orig", "cb_sub", "open_orig", "open_sub"):
        which = _ARM_KEY[arm]
        hits = []
        for r in rows:
            aliases = r["new_aliases"] if which == "new" else r["old_aliases"]
            raw = (r["arms_raw"] or {}).get(arm, "")
            hits.append(any(_wb(raw, a) for a in aliases))
        means[arm] = round(_rate(hits), 4)
    return means


def _type_stratify(rows: list[dict]) -> dict:
    """C11：按 answer_type 分组报顺从率；date/numeric 用同类型虚构/借用值替换→干净试次，
    name 跨题借名→类别可能荒谬。旧产物没有 answer_type 字段时跳过（不加也不报错）。"""
    groups: dict[str, list[dict]] = {}
    for r in rows:
        t = str(r.get("answer_type") or "?")
        groups.setdefault(t, []).append(r)
    out: dict[str, dict] = {}
    for t, g in sorted(groups.items()):
        conflict = [r for r in g if r.get("term_present")]
        cat = [_categorize(r["ora_sub"], r["new_aliases"], r["old_aliases"]) for r in g]
        out[t] = dict(
            n=len(g),
            compliance_strict=round(_rate([r["cls_sub"] == "new" for r in g]), 4),
            compliance_contain=round(_rate([c == "new" for c in cat]), 4),
            n_conflict=len(conflict),
            conflict_contain=round(_rate(
                [_categorize(r["ora_sub"], r["new_aliases"], r["old_aliases"]) == "new"
                 for r in conflict]), 4) if conflict else None,
        )
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="compliance 离线拆解（Phase C 诊断 C9）")
    ap.add_argument("--oracle_rows", required=True,
                    help="run_pipeline 落盘的 {label}_oracle_rows.jsonl 路径")
    args = ap.parse_args(argv)

    path = Path(args.oracle_rows)
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"载入 {len(rows)} 条 oracle 拆解行：{path}\n")

    conflict = [r for r in rows if r.get("term_present")]
    noop = [r for r in rows if not r.get("term_present")]
    print(f"真冲突试次(term 在金替换证据里) = {len(conflict)}；"
          f"无操作试次(term 不在/替换落在外) = {len(noop)}\n")

    out: dict = dict(n_total=len(rows), n_conflict=len(conflict), n_noop=len(noop))
    _row_stats(rows, "全集", out)
    if conflict:
        _row_stats(conflict, "真冲突子集(仅 term_present)", out)
    if noop:
        _row_stats(noop, "无操作子集(term 不在金证据)", out)

    # C11：按 answer_type 分层（单跳混合 date/numeric/name，只有同类型值替换才干净）
    if any(r.get("answer_type") for r in rows):
        type_out = _type_stratify(rows)
        out["answer_type"] = type_out
        print("按 answer_type 分层（同类型值替换的干净度直接决定顺从率可读性）")
        for t, blk in type_out.items():
            print(f"  {t:<9} n={blk['n']:<4} strict={blk['compliance_strict']:.3f} "
                  f"contain={blk['compliance_contain']:.3f} | "
                  f"其中真冲突 n_conf={blk['n_conflict']}: "
                  f"conflict_contain={blk['conflict_contain']:.3f}")
        print()

    # 四臂宽松口径对照：若 strict a/b/c/d 被 Instruct 整句压低，contain 版应显著更高
    arms_s = dict(
        a=_rate([bool(r["arms_em"].get("a")) for r in rows]),
        b=_rate([bool(r["arms_em"].get("b")) for r in rows]),
        c=_rate([bool(r["arms_em"].get("c")) for r in rows]),
        d=_rate([bool(r["arms_em"].get("d")) for r in rows]))
    arms_c = _arm_contain_means(rows)
    out["arms_em_strict"] = {k: round(v, 4) for k, v in arms_s.items()}
    out["arms_em_contain"] = arms_c
    print("四臂 EM 对照（strict=冻结口径逐题 EM 均值；contain=整词包含对应别名均值）")
    print(f"  strict : a={arms_s['a']:.3f} b={arms_s['b']:.3f} c={arms_s['c']:.3f} d={arms_s['d']:.3f}"
          f" | 表观={arms_s['b']-arms_s['a']:+.3f} 校正={arms_s['d']-arms_s['c']:+.3f} "
          f"DiD={ (arms_s['b']-arms_s['a'])-(arms_s['d']-arms_s['c']):+.3f}")
    print(f"  contain: a={arms_c['cb_orig']:.3f} b={arms_c['open_orig']:.3f} "
          f"c={arms_c['cb_sub']:.3f} d={arms_c['open_sub']:.3f}"
          f" | 表观={arms_c['open_orig']-arms_c['cb_orig']:+.3f} "
          f"校正={arms_c['open_sub']-arms_c['cb_sub']:+.3f} "
          f"DiD={ (arms_c['open_orig']-arms_c['cb_orig'])-(arms_c['open_sub']-arms_c['cb_sub']):+.3f}")

    out_path = path.with_name(path.stem.replace("_oracle_rows", "") + "_decomp.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {out_path}")


if __name__ == "__main__":
    main()
