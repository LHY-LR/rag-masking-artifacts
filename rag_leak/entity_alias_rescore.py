r"""实体线 alias-aware 重打分（可复现版）—— 取代丢失的临时脚本产物 `out_entity_alias_rescore.json`。

背景与问题
----------
论文 §4.5 的实体稳健性表里有一行 "alias-aware"：把 `c`/`d` 臂从"只认单一植入 key"改成
"认该植入值的**全部写法**"（回应评审 must-fix：`a`/`b` 用全别名表、`c`/`d` 只用单 key 的不对称）。
该行原先由临时脚本算出，**脚本已丢失**，且**产物里没有存来源信息**，无法原样复现。
本脚本用**显式定义、可从冻结产物复算**的规则重做该行，取代旧产物。

本脚本的口径（唯一权威定义）
----------------------------
1. 植入值 `new_key` 在产物里是**已归一化**的串（如 `'st vitus'`，见 substituted.jsonl）。
2. 在值池的答案表里找出所有"与该植入值同形"的题（用 `normalize_answer` 双向匹配），
   把这些题的**全部答案写法**并起来 —— 这就是"该值的全部写法"。
   *注意*：值池建在**全量 1067 题**上（实测：363 条植入值中 303 条能在全量答案表里按归一化找到，
   而按原样只能找到 81 条——因为产物里存的是归一化串）。故来源题可能不在 400 抽样内。
3. `ext = (全部写法 ∪ {new_key}) \ 目标题自己的答案写法`。
   减掉目标题答案表是**必须的守卫**：否则"真值"的写法会被算成命中（把没换值的题当成答对）。
4. `c2 = em(cb_sub, ext)`、`d2 = em(open_sub, ext)`；a/b 与主口径相同（本来就用全别名表）。
   `masking2 = (d2 − c2) − (b − a)`。
5. 报告 alias-aware 与统一单 key 两种口径，以及 **Δmasking(new2 − old)** 的题级自举 CI
   （B=10000、seed=20260903、按 question_id 聚类重抽；与主文一致）。

局限（必须随结果写）
--------------------
- `new_key` 已被归一化 ⇒ 无法再区分"原始大小写写法"，故本行的 ext 是**下界式**的写法集合。
- 来源题不唯一时取**并集**（不依赖值池的枚举顺序），因此本行不继承 E-N1 的跨进程不确定性。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .data.load_raw import load_dpr_file
from .metrics.normalize import em_any_alias, normalize_answer

HERE = Path(__file__).parent
POOL_FILE = HERE.parent / "data" / "trivia_name.json"
RUNS = ["out_ent_old_4bi", "out_ent_old_8b", "out_ent_new_4bi", "out_ent_new_8b",
        "out_ent_new2_4bi", "out_ent_new2_8b"]
B = 10000
SEED = 20260903


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _one(p: Path) -> Path:
    hits = sorted(p.glob("*.jsonl"))
    return hits[0]


def build_pool_index() -> dict[str, set[str]]:
    """normalize(答案写法) -> 含该写法的题的**全部**归一化写法集合。"""
    idx: dict[str, set[str]] = {}
    for q in load_dpr_file(str(POOL_FILE), "trivia"):
        forms = {normalize_answer(a) for a in (q.answers or []) if a and str(a).strip()}
        for f in forms:
            idx.setdefault(f, set()).update(forms)
    return idx


def rescore() -> dict:
    import numpy as np
    idx = build_pool_index()
    out: dict[str, dict] = {}
    per_item: dict[str, dict] = {}
    for d in RUNS:
        base = HERE / d
        orc = {r["question_id"]: r for r in _jsonl(sorted(base.glob("*_oracle_rows.jsonl"))[0])}
        subs = {r["question_id"]: r for r in _jsonl(sorted(base.glob("*_substituted.jsonl"))[0])}
        if sorted(orc) != sorted(subs):
            raise SystemExit(f"{d}: oracle_rows 与 substituted 题集不一致")
        rows = []
        n_no_src = 0
        for qid in sorted(orc):
            r, s = orc[qid], subs[qid]
            raw = r.get("arms_raw") or {}
            target = {normalize_answer(a) for a in (r.get("old_aliases") or [])}
            key = normalize_answer(s.get("new_key") or "")
            src_forms = set(idx.get(key, set()))
            if not src_forms:
                n_no_src += 1
            ext = sorted((src_forms | {key}) - target)
            c1 = em_any_alias(raw.get("cb_sub", ""), [key])
            d1 = em_any_alias(raw.get("open_sub", ""), [key])
            c2 = em_any_alias(raw.get("cb_sub", ""), ext) if ext else 0
            d2 = em_any_alias(raw.get("open_sub", ""), ext) if ext else 0
            rows.append(dict(qid=qid, a=r["arms_em"]["a"], b=r["arms_em"]["b"],
                             c1=c1, d1=d1, c2=c2, d2=d2,
                             n_ext=len(ext), ext_extra=len(ext) - 1))
        m = lambda k: float(np.mean([x[k] for x in rows]))          # noqa: E731
        mask1 = (m("d1") - m("c1")) - (m("b") - m("a"))
        mask2 = (m("d2") - m("c2")) - (m("b") - m("a"))
        out[d] = dict(n=len(rows), n_no_source=n_no_src,
                      a=round(m("a"), 4), b=round(m("b"), 4),
                      c1=round(m("c1"), 4), d1=round(m("d1"), 4),
                      c2=round(m("c2"), 4), d2=round(m("d2"), 4),
                      m1=round(mask1, 4), m2=round(mask2, 4),
                      mean_ext_extra=round(float(np.mean([x["ext_extra"] for x in rows])), 3))
        per_item[d] = rows

    # Δmasking(new2 − old)，两种口径，题级聚类自举
    def delta(kind, model):
        o, n = per_item[f"out_ent_old_{model}"], per_item[f"out_ent_new2_{model}"]
        if kind == "uniform":
            return float(np.mean([(x["d1"] - x["c1"]) for x in n])
                         - np.mean([(x["d1"] - x["c1"]) for x in o]))
        return float(np.mean([(x["d2"] - x["c2"]) for x in n])
                     - np.mean([(x["d2"] - x["c2"]) for x in o]))

    rng = np.random.default_rng(SEED)
    res_delta = {}
    for model in ("4bi", "8b"):
        o, n = per_item[f"out_ent_old_{model}"], per_item[f"out_ent_new2_{model}"]
        qids = sorted({x["qid"] for x in o} | {x["qid"] for x in n})
        byq = {q: [] for q in qids}
        for tag, rows in (("old", o), ("new", n)):
            for x in rows:
                byq[x["qid"]].append((tag, x))
        draws = {"uniform": [], "alias": []}
        for _ in range(B):
            pick = rng.integers(0, len(qids), len(qids))
            agg = {"uniform": [0.0, 0.0], "alias": [0.0, 0.0]}
            cnt = {"old": 0, "new": 0}
            for k in pick:
                for tag, x in byq[qids[k]]:
                    cnt[tag] += 1
                    agg["uniform"][0 if tag == "old" else 1] += (x["d1"] - x["c1"])
                    agg["alias"][0 if tag == "old" else 1] += (x["d2"] - x["c2"])
            for kind in draws:
                if cnt["old"] and cnt["new"]:
                    draws[kind].append(agg[kind][1] / cnt["new"] - agg[kind][0] / cnt["old"])
        res_delta[model] = {
            kind: dict(point=round(delta(kind, model), 4),
                       lo=round(float(np.percentile(draws[kind], 2.5)), 4),
                       hi=round(float(np.percentile(draws[kind], 97.5)), 4))
            for kind in ("uniform", "alias")}
    return dict(runs=out, delta_new2_minus_old=res_delta, bootstrap=B, seed=SEED,
                definition=("ext = (值池中含该植入值的题的**全部**答案写法 ∪ {new_key}) "
                            "\\ 目标题自己的答案写法；值池 = 全量 1067 题"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="实体线 alias-aware 重打分（可复现）")
    ap.add_argument("--out", default=str(HERE / "out_entity_alias_rescore_v2.json"))
    args = ap.parse_args(argv)
    res = rescore()
    print(f"{'run':<20} {'n':>4} {'无来源':>6} {'c1':>7} {'d1':>7} {'c2':>7} {'d2':>7} "
          f"{'m1':>8} {'m2':>8} {'平均多写法':>10}")
    for d, v in res["runs"].items():
        print(f"{d:<20} {v['n']:>4} {v['n_no_source']:>6} {v['c1']:>7.4f} {v['d1']:>7.4f} "
              f"{v['c2']:>7.4f} {v['d2']:>7.4f} {v['m1']:>+8.4f} {v['m2']:>+8.4f} "
              f"{v['mean_ext_extra']:>10.2f}")
    print(f"\nΔmasking(new2 − old)，B={res['bootstrap']}，seed={res['seed']}")
    for model, v in res["delta_new2_minus_old"].items():
        for kind in ("uniform", "alias"):
            s = v[kind]
            print(f"   {model:<4} {kind:<8} {s['point']:+.4f}  95% CI [{s['lo']:+.4f}, {s['hi']:+.4f}]"
                  f"  {'排零' if s['lo'] > 0 or s['hi'] < 0 else '含零'}")
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
