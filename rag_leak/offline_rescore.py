r"""v3 离线重评分（C13，协议修订落地工具）：从存盘 raw 用【首句抽取 EM】重算四臂。

只读复盘，不改产物。动机：frozen v2 strict EM 取"输出首行整串"归一化；base 模型把
"1983. Foinavon won ..." 整段写在【同一行】→ 即便开口就答 1983 也判 0，系统性压低
d（证据跟随）→ 把 8B base 的 DiD 顶正（round-6 判读，格式伪差）。v3 抽取改为
去前缀 → 首行 → 按 [.!?;]\s 切首句 → normalize → EM 命中任一别名（见
metrics/normalize.py:_first_sentence）；对格式干净的 Instruct 输出严格退化为 v2 strict。

输入：run_pipeline 落盘的 {label}_oracle_rows.jsonl（每行含 arms_raw 四臂原始输出、
ora_sub、old_aliases/new_aliases、answer_type、term_present、v2 现算 arms_em）。
输出：stdout 分区表 + 同目录 {label}_rescore_v3.json。

对照列 = 产物里的 v2 strict（arms_em / cls_sub）；v3 与 v2 的差异即"格式伪差纠正量"。
bootstrap 配对重抽题目，种子/次数用 config.RNG_SEED / BOOTSTRAP_B（与 stats.did 一致）。
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
from .schemas import FourArmRow
from .metrics.normalize import (extract_answer, normalize_answer, em_any_alias)
from .metrics.compliance import classify_output
from .stats.did import did_mean, paired_bootstrap, apparent_gain, corrected_gain, masking_magnitude

_ARMS = ("cb_orig", "cb_sub", "open_orig", "open_sub")
# orig 臂对旧别名比、sub 臂对新别名比（§7-3，与冻结一致）
_ALIAS_OF = {"cb_orig": "old", "cb_sub": "new", "open_orig": "old", "open_sub": "new"}
_ARM_KEY = {"cb_orig": "a", "open_orig": "b", "cb_sub": "c", "open_sub": "d"}


def _aliases(row: dict, which: str) -> list[str]:
    return row.get("new_aliases") if which == "new" else row.get("old_aliases")


def contain_any(raw: str, aliases: list[str]) -> int:
    """宽口径：整词边界包含任一归一化别名（不要求整句相等）。"""
    if not raw:
        return 0
    t = raw.lower()
    for a in aliases:
        na = normalize_answer(a)
        if not na:
            continue
        if re.search(r"(?<![0-9a-z])" + re.escape(na) + r"(?![0-9a-z])", t):
            return 1
    return 0


def first_int_val(raw: str) -> str:
    """全文第一个整数 token（去千分逗号），作为 base 声称的答案；无整数返回 ''。"""
    for tok in re.findall(r"\d[\d,]*", raw):
        return tok.replace(",", "")
    return ""


def val_any(raw: str, aliases: list[str]) -> int:
    """值口径：抽取出的首个整数 == 任一别名的纯数字。"""
    v = first_int_val(raw)
    if not v:
        return 0
    for a in aliases:
        d = re.sub(r"\D", "", normalize_answer(a))
        if d and v == d:
            return 1
    return 0


def rescore_row(row: dict) -> dict:
    """对一行重算各口径四臂 EM / oracle EM / compliance；同时报告与 v2 strict 的差异。"""
    raw_arms = row.get("arms_raw") or {}
    aliases_of = lambda arm: _aliases(row, _ALIAS_OF[arm])
    out = {scope: {} for scope in ("v3", "contain", "val")}
    for arm in _ARMS:
        raw = raw_arms.get(arm, "")
        al = aliases_of(arm)
        out["v3"][arm] = em_any_alias(raw, al)
        out["contain"][arm] = contain_any(raw, al)
        out["val"][arm] = val_any(raw, al)
    ora_sub = row.get("ora_sub", "")
    v3_ora_sub = em_any_alias(ora_sub, row.get("new_aliases") or [])
    v3_cls = classify_output(ora_sub, row.get("new_aliases") or [],
                             row.get("old_aliases") or [])
    # v2 现算的 arms_em 键是 a/b/c/d（产物落盘口径，非重算）
    v2_abcd = (row.get("arms_em") or {})
    return dict(
        v3=out["v3"], contain=out["contain"], val=out["val"],
        v3_ora_sub=int(v3_ora_sub), v3_cls=v3_cls,
        v2_abcd={k: int(v2_abcd.get(k, 0)) for k in ("a", "b", "c", "d")},
        v2_cls=row.get("cls_sub"),
    )


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _fourarm_objects(rows: list[dict], rr: list[dict], model_label: str,
                     scope: str) -> list[FourArmRow]:
    out = []
    for row, r in zip(rows, rr):
        em = r[scope]
        out.append(FourArmRow(row["question_id"], model_label, f"rescore-{scope}",
                              a=em["cb_orig"], b=em["open_orig"],
                              c=em["cb_sub"], d=em["open_sub"]))
    return out


def _scope_block(rows: list[dict], rr: list[dict], model_label: str, scope: str) -> dict:
    """按 scope 的逐行 EM 计算 a/b/c/d、表观/校正/DiD + bootstrap CI。"""
    objs = _fourarm_objects(rows, rr, model_label, scope)
    em = [r[scope] for r in rr]
    a = _mean([e["cb_orig"] for e in em]); b = _mean([e["open_orig"] for e in em])
    c = _mean([e["cb_sub"] for e in em]); d = _mean([e["open_sub"] for e in em])
    ap, co = apparent_gain(objs), corrected_gain(objs)
    did_m, (lo, hi), _ = paired_bootstrap(objs)
    return dict(
        a=round(a, 4), b=round(b, 4), c=round(c, 4), d=round(d, 4),
        apparent_gain=round(ap, 4), corrected_gain=round(co, 4),
        did=round(did_m, 4), ci=[round(lo, 4), round(hi, 4)],
        masking=round(masking_magnitude(objs), 4))


def _block(rows: list[dict], rr: list[dict], model_label: str, name: str) -> dict:
    """一组题的完整口径对照块。v3=主口径；contain/val=宽容内容口径（diagnostic）；
    v2_strict=产物落盘的 v2 strict（对 Instruct 应与 v3 全等、对 base 是"格式伪差"基准）。"""
    scopes = {s: _scope_block(rows, rr, model_label, s) for s in ("v3", "contain", "val")}
    comp = _mean([r["v3_cls"] == "new" for r in rr])
    v2a = _mean([r["v2_abcd"]["a"] for r in rr]); v2b = _mean([r["v2_abcd"]["b"] for r in rr])
    v2c = _mean([r["v2_abcd"]["c"] for r in rr]); v2d = _mean([r["v2_abcd"]["d"] for r in rr])
    v2_did = (v2b - v2a) - (v2d - v2c)
    # 格式伪差纠正量：v3 vs v2 每臂翻转了几行
    flip = {arm: sum(1 for r in rr if bool(r["v3"][arm]) != bool(
        r["v2_abcd"][_ARM_KEY[arm]])) for arm in _ARMS}
    return dict(
        name=name, n=len(rows),
        scopes=scopes,
        compliance_v3=round(comp, 4),
        v2_strict=dict(a=round(v2a, 4), b=round(v2b, 4), c=round(v2c, 4), d=round(v2d, 4),
                       did=round(v2_did, 4), compliance=round(
                           _mean([r["v2_cls"] == "new" for r in rr]), 4)),
        flip_v3_vs_v2=flip,
    )


def _fmt(blk: dict, scope: str) -> str:
    m = blk["scopes"][scope]
    return (f"a={m['a']:.3f} b={m['b']:.3f} c={m['c']:.3f} d={m['d']:.3f} | "
            f"表观={m['apparent_gain']:+.3f} 校正={m['corrected_gain']:+.3f} "
            f"DiD={m['did']:+.3f} 95%CI=[{m['ci'][0]:+.3f},{m['ci'][1]:+.3f}] "
            f"掩盖量={m['masking']:.3f}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="v3 离线重评分（C13；主口径=首句抽取 EM）")
    ap.add_argument("--oracle_rows", required=True,
                    help="run_pipeline 落盘的 {label}_oracle_rows.jsonl 路径")
    args = ap.parse_args(argv)

    path = Path(args.oracle_rows)
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    label = path.stem.replace("_oracle_rows", "")
    print(f"载入 {len(rows)} 条 oracle 拆解行：{path}\n")

    # 本工具只对 date/numeric 切片有意义（name 跨类借值→坏机器）；全行都算但按 type 分开报
    rr = [rescore_row(r) for r in rows]
    all_dn = [(r, s) for r, s in zip(rows, rr)
              if r.get("answer_type") in ("date", "numeric")]
    tp = [(r, s) for r, s in all_dn if r.get("term_present")]
    date = [(r, s) for r, s in tp if r.get("answer_type") == "date"]
    num = [(r, s) for r, s in tp if r.get("answer_type") == "numeric"]

    groups = {"all(date/numeric)": all_dn, "term_present": tp,
              "date(term_present)": date, "numeric(term_present)": num}
    out = dict(label=label, protocol="v3", n_total=len(rows), groups={})
    for name, g in groups.items():
        if not g:
            continue
        blk = _block([r for r, _ in g], [s for _, s in g], label, name)
        out["groups"][name] = blk
        v2 = blk["v2_strict"]
        print(f"=== {name}  n={blk['n']} ===")
        print(f"  v3(主口径·首句EM)  : {_fmt(blk, 'v3')}  compliance={blk['compliance_v3']:.3f}")
        print(f"  contain(宽容·整词) : {_fmt(blk, 'contain')}")
        print(f"  val(宽容·首整数)   : {_fmt(blk, 'val')}")
        print(f"  v2(strict·产物落盘) : DiD={v2['did']:+.3f} compliance={v2['compliance']:.3f} | "
              f"v3 翻片(每臂): {blk['flip_v3_vs_v2']}")
        print()
    if out["groups"]:
        allb = out["groups"]["all(date/numeric)"]
        print(f"[v2 strict 全量对照] n={allb['n']} DiD={allb['v2_strict']['did']:+.4f} "
              f"(应为产物 metrics 主数字)")

    out_path = path.with_name(path.stem.replace("_oracle_rows", "") + "_rescore_v3.json")
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {out_path}")


if __name__ == "__main__":
    main()
