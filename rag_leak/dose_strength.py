r"""§5.2 两件 headline 数字的可复现重算（此前只有散文、没有脚本）：

(A) **前提的剂量反应**：17 个 model×line×depth 格上 `masking ~ 闭卷 a` 的拟合斜率
    （论文：总 0.503；C 线 0.518；B 线 0.497；留一模型 0.483–0.523；
    题级自举 95% CI [0.439,0.573]；10,000 次自举中斜率 <1 的比例 = 1.0000）。
    17 格 = C 线 5 模型（`out_s6_trivia_fix_*`）+ B 线 6 模型 × k∈{1,5}（`out_b8_fix_k{1,5}_*`），
    全部共享同一数值/日期语料与同一批题（432）。
(B) **tab:strength**：操纵代价 (b−d) 按"记忆强度"分箱。强度 = **除被评模型外**还有几个模型
    闭卷答对该题（0–5），故不是被评模型自身 a 的重述。论文只报两个极端格（strength 0 与 5）：
    均值、比值、以及两格题数。

口径与不变量
------------
- masking = 校正 − 表观 = (d−c) − (b−a)；每格一个点。
- (A) 的自举：**按格内独立重抽题**（论文原文"resampling items within each cell"），B=10000、seed=20260903；
  随机流按格名派生（不用全局流）。同时报"同题跨格配对重抽"变体作为稳健性。
- (B) 的强度只用**同一 k 的同一批格**（6 模型同 k），故 (B) 对 k=1 / k=5 分别算，
  以判定论文表用的是哪一个 k（表里只有一组数字）。
- 不变量：同一模型跨 k 的闭卷 a 必须逐题相同（否则题集或产物错配）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

HERE = Path(__file__).parent
B = 10000
SEED = 20260903
MODELS = ["Qwen3-0.6B", "Qwen3-1.7B", "Qwen3-4B", "Qwen3-4B-Instruct", "Qwen3-8B",
          "Qwen3.5-4B-Base"]
K1 = {"Qwen3-0.6B": "out_b8_fix_k1_06b", "Qwen3-1.7B": "out_b8_fix_k1_17b",
      "Qwen3-4B": "out_b8_fix_k1_4b", "Qwen3-4B-Instruct": "out_b8_fix_k1_4bi",
      "Qwen3-8B": "out_b8_fix_k1", "Qwen3.5-4B-Base": "out_b8_fix_k1_q35"}
K5 = {"Qwen3-0.6B": "out_b8_fix_k5_06b", "Qwen3-1.7B": "out_b8_fix_k5_17b",
      "Qwen3-4B": "out_b8_fix_k5_4b", "Qwen3-4B-Instruct": "out_b8_fix_k5_4bi",
      "Qwen3-8B": "out_b8_fix_k5", "Qwen3.5-4B-Base": "out_b8_fix_k5_q35"}
CLINE = {"Qwen3-0.6B": "out_s6_trivia_fix_06b", "Qwen3-1.7B": "out_s6_trivia_fix_17b",
         "Qwen3-4B": "out_s6_trivia_fix_4b", "Qwen3-4B-Instruct": "out_s6_trivia_fix_4bi",
         "Qwen3-8B": "out_s6_trivia_fix_8b"}


def _seed_int(tag: str) -> int:
    return int.from_bytes(hashlib.sha256(f"{SEED}|{tag}".encode()).digest()[:8], "big")


def load(dname: str) -> dict[str, dict]:
    d = HERE / dname
    hits = sorted(d.glob("*_fourarm.jsonl"))
    if len(hits) != 1:
        raise SystemExit(f"{d} 下应有唯一 *_fourarm.jsonl")
    return {r["question_id"]: r for r in
            (json.loads(x) for x in hits[0].read_text(encoding="utf-8").splitlines() if x.strip())}


def cells() -> list[dict]:
    """17 格（C 线 5 + B 线 12）。顺带断言跨 k 的 a 逐题一致。"""
    out = []
    for m, d in CLINE.items():
        out.append(dict(cell=f"C|{m}|k5", model=m, line="C", k=5, dir=d, rows=load(d)))
    for k, table in ((1, K1), (5, K5)):
        for m, d in table.items():
            out.append(dict(cell=f"B|{m}|k{k}", model=m, line="B", k=k, dir=d, rows=load(d)))
    ref = sorted(out[0]["rows"])
    for c in out:
        if sorted(c["rows"]) != ref:
            raise SystemExit(f"{c['cell']} 题集与参照不一致")
    for m in MODELS:
        if m in K1 and m in K5:
            r1, r5 = load(K1[m]), load(K5[m])
            diff = [q for q in r1 if r1[q]["a"] != r5[q]["a"]]
            if diff:
                raise SystemExit(f"不变量失败：{m} 的闭卷 a 在 k=1/k=5 间逐题不同（{len(diff)} 题）")
    import numpy as np
    for c in out:
        ks = sorted(c["rows"])
        c["qids"] = ks
        c["a"] = float(np.mean([c["rows"][q]["a"] for q in ks]))
        c["mask"] = float(np.mean([(c["rows"][q]["d"] - c["rows"][q]["c"])
                                   - (c["rows"][q]["b"] - c["rows"][q]["a"]) for q in ks]))
        c["adv"] = float(np.mean([c["rows"][q]["a"] - c["rows"][q]["c"] for q in ks]))
        c["cost"] = float(np.mean([c["rows"][q]["b"] - c["rows"][q]["d"] for q in ks]))
    return out


def _ols(x, y) -> tuple[float, float]:
    import numpy as np
    x, y = np.asarray(x, float), np.asarray(y, float)
    A = np.column_stack([np.ones(len(x)), x])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(beta[1]), float(beta[0])


def dose_response(cs: list[dict], b: int) -> dict:
    import numpy as np
    a = np.array([c["a"] for c in cs])
    y = np.array([c["mask"] for c in cs])
    total, icept = _ols(a, y)
    res = dict(n_cells=len(cs), slope_total=round(total, 4), intercept=round(icept, 4))
    for line in ("C", "B"):
        sel = [i for i, c in enumerate(cs) if c["line"] == line]
        s, ic = _ols(a[sel], y[sel])
        res[f"slope_{line}"] = round(s, 4)
        res[f"intercept_{line}"] = round(ic, 4)
    # 留一模型（同时去掉该模型的 C 线 1 格与 B 线 2 格）
    loo = {}
    for m in MODELS:
        sel = [i for i, c in enumerate(cs) if c["model"] != m]
        s, _ = _ols(a[sel], y[sel])
        loo[m] = round(s, 4)
    res["loo"] = loo
    res["loo_range"] = [min(loo.values()), max(loo.values())]
    # 题级自举：格内独立重抽（论文口径）
    rngs = [np.random.default_rng(_seed_int("dose|" + c["cell"])) for c in cs]
    draws = []
    for _ in range(b):
        xs, ys = [], []
        for i, c in enumerate(cs):
            n = len(c["qids"])
            idx = rngs[i].integers(0, n, n)
            aa = np.array([c["rows"][q]["a"] for q in c["qids"]])[idx]
            mm = np.array([(c["rows"][q]["d"] - c["rows"][q]["c"])
                           - (c["rows"][q]["b"] - c["rows"][q]["a"]) for q in c["qids"]])[idx]
            xs.append(aa.mean())
            ys.append(mm.mean())
        s, _ = _ols(xs, ys)
        if s == s:
            draws.append(s)
    res["boot_independent"] = dict(
        lo=round(float(np.percentile(draws, 2.5)), 4),
        hi=round(float(np.percentile(draws, 97.5)), 4),
        p_below_1=round(float(np.mean([d < 1 for d in draws])), 4), n_ok=len(draws))
    # 配对变体：所有格共用同一次题重抽
    rng = np.random.default_rng(_seed_int("dose|paired"))
    draws_p = []
    for _ in range(b):
        idx = rng.integers(0, len(cs[0]["qids"]), len(cs[0]["qids"]))
        xs, ys = [], []
        for c in cs:
            aa = np.array([c["rows"][q]["a"] for q in c["qids"]])[idx]
            mm = np.array([(c["rows"][q]["d"] - c["rows"][q]["c"])
                           - (c["rows"][q]["b"] - c["rows"][q]["a"]) for q in c["qids"]])[idx]
            xs.append(aa.mean())
            ys.append(mm.mean())
        s, _ = _ols(xs, ys)
        if s == s:
            draws_p.append(s)
    res["boot_paired"] = dict(lo=round(float(np.percentile(draws_p, 2.5)), 4),
                              hi=round(float(np.percentile(draws_p, 97.5)), 4),
                              p_below_1=round(float(np.mean([d < 1 for d in draws_p])), 4))
    return res


def strength_table(k: int) -> dict:
    """tab:strength（同一 k 的 6 个格）。strength = 其余模型闭卷答对的个数。"""
    import numpy as np
    table = K1 if k == 1 else K5
    rows = {m: load(table[m]) for m in MODELS}
    qids = sorted(rows[MODELS[0]])
    a = {m: np.array([rows[m][q]["a"] for q in qids]) for m in MODELS}
    cost = {m: np.array([rows[m][q]["b"] - rows[m][q]["d"] for q in qids]) for m in MODELS}
    out = {}
    for m in MODELS:
        others = [x for x in MODELS if x != m]
        strength = sum(a[x] for x in others)          # 0..5，不含自身
        c0 = cost[m][strength == 0]
        c5 = cost[m][strength == 5]
        out[m] = dict(
            n0=int((strength == 0).sum()), n5=int((strength == 5).sum()),
            cost0=round(float(c0.mean()), 4) if len(c0) else None,
            cost5=round(float(c5.mean()), 4) if len(c5) else None,
            ratio=round(float(c5.mean() / c0.mean()), 1) if len(c0) and c0.mean() else None,
            monotone=bool(all(
                (cost[m][strength == s].mean() if (strength == s).any() else -9)
                <= (cost[m][strength == s + 1].mean() if (strength == s + 1).any() else 9)
                for s in range(5))),
            by_strength={int(s): dict(n=int((strength == s).sum()),
                                      cost=round(float(cost[m][strength == s].mean()), 4))
                         if (strength == s).any() else None for s in range(6)})
    # 论文表注："Cell sizes are 17–146 items" —— 指所有 strength 分箱的题数范围
    ns = [b["n"] for m, v in out.items() if not m.startswith("_")
          for b in v["by_strength"].values() if b and b["n"] > 0]
    out["_bin_n_range"] = [min(ns), max(ns)]
    return out


def date_vs_numeric(boot: int) -> dict:
    """§5.2 的池内佐证（A4）：C 线同一 TriviaQA 池按答案类型切成 date / numeric 两个子池。

    论文原话："date 子池在四个较大模型上闭卷 a 更高、masking 也更大"
    （4B .184 vs .076、4B-Instruct .299 vs .111、8B .368 vs .071；两个最小模型不可分）。
    这一组数字此前**没有脚本**；本函数从 fourarm（a/b/c/d）+ oracle_rows（answer_type）复算，
    并给 date−numeric 差的题级自举 CI。
    """
    import numpy as np
    out = {}
    for m, d in CLINE.items():
        four = load(d)
        orc = {r["question_id"]: r for r in
               (json.loads(x) for x in sorted((HERE / d).glob("*_oracle_rows.jsonl"))[0]
                .read_text(encoding="utf-8").splitlines() if x.strip())}
        qids = sorted(four)
        at = {q: (orc.get(q, {}).get("answer_type") or "?") for q in qids}
        mask = {q: (four[q]["d"] - four[q]["c"]) - (four[q]["b"] - four[q]["a"]) for q in qids}
        a_of = {q: four[q]["a"] for q in qids}
        sub = {}
        for tag in ("date", "numeric"):
            ks = [q for q in qids if at[q] == tag]
            sub[tag] = dict(n=len(ks),
                            a=round(float(np.mean([a_of[q] for q in ks])), 4) if ks else None,
                            masking=round(float(np.mean([mask[q] for q in ks])), 4) if ks else None)
        # date − numeric 的题级自举（按题重抽；两子池互斥，各自独立重抽）
        rng = np.random.default_rng(_seed_int("strata|" + m))
        kd = [q for q in qids if at[q] == "date"]
        kn = [q for q in qids if at[q] == "numeric"]
        draws = []
        for _ in range(boot):
            dd = np.array([mask[kd[i]] for i in rng.integers(0, len(kd), len(kd))]) if kd else None
            nn = np.array([mask[kn[i]] for i in rng.integers(0, len(kn), len(kn))]) if kn else None
            if dd is not None and nn is not None:
                draws.append(float(dd.mean() - nn.mean()))
        out[m] = dict(**sub, diff_masking=(round(float(np.mean([mask[q] for q in kd]))
                                                - float(np.mean([mask[q] for q in kn])), 4)
                                           if kd and kn else None),
                      diff_ci=[round(float(np.percentile(draws, 2.5)), 4),
                               round(float(np.percentile(draws, 97.5)), 4)] if draws else None,
                      answer_type_other=sum(1 for q in qids if at[q] not in ("date", "numeric")))
    return out


def strength_stats(k: int, boot: int) -> dict:
    """(b−d) 与记忆强度的**可辩护**统计量。

    为什么必须补这一步：初稿写的是"六个模型的 (b−d) 随强度**单调上升**"。本脚本的逐箱剖面
    证明该说法 **5/6 模型不成立**（0.6B 在强度 1 处甚至为 −0.038；k=1 时只有 4B 严格单调）。
    真正稳健、也确实被表里两个极端支撑的说法是"**两端对比极大**"。故此处给出：
      ① 极端对比 Δ = mean(cost|s=5) − mean(cost|s=0)，题级配对自举 CI；
      ② 逐题 Spearman(strength, cost)（不依赖分箱）；
      ③ 逐箱单调性 + 完整剖面（供论文如实措辞，别再写"单调"）。
    """
    import numpy as np
    table = K1 if k == 1 else K5
    rows = {m: load(table[m]) for m in MODELS}
    qids = sorted(rows[MODELS[0]])
    a = {m: np.array([rows[m][q]["a"] for q in qids]) for m in MODELS}
    cost = {m: np.array([rows[m][q]["b"] - rows[m][q]["d"] for q in qids]) for m in MODELS}
    strength = {m: sum(a[x] for x in MODELS if x != m) for m in MODELS}

    def _rank(x):
        order = x.argsort()
        r = np.empty(len(x), float)
        r[order] = np.arange(len(x), dtype=float)
        vals, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
        for i in range(len(vals)):
            if cnt[i] > 1:
                r[inv == i] = r[inv == i].mean()
        return r

    def delta(m):
        s0, s5 = strength[m] == 0, strength[m] == 5
        if not s0.any() or not s5.any():
            return float("nan")
        return float(cost[m][s5].mean() - cost[m][s0].mean())

    def rho(m):
        x = _rank(strength[m].astype(float))
        y = _rank(cost[m])
        return float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else float("nan")

    rng = np.random.default_rng(_seed_int(f"strength|k{k}"))
    n = len(qids)
    d_draws = {m: [] for m in MODELS}
    r_draws = {m: [] for m in MODELS}
    for _ in range(boot):
        idx = rng.integers(0, n, n)
        for m in MODELS:
            c, st = cost[m][idx], strength[m][idx]
            s0, s5 = st == 0, st == 5
            if s0.any() and s5.any():
                d_draws[m].append(float(c[s5].mean() - c[s0].mean()))
            x = _rank(st.astype(float))
            y = _rank(c)
            if x.std() and y.std():
                r_draws[m].append(float(np.corrcoef(x, y)[0, 1]))

    out = {}
    for m in MODELS:
        d0 = np.percentile(d_draws[m], [2.5, 97.5])
        r0 = np.percentile(r_draws[m], [2.5, 97.5])
        sb = [-99 if not (strength[m] == s).any() else float(cost[m][strength[m] == s].mean())
              for s in range(6)]
        mono = all(x <= y for x, y in zip(sb, sb[1:]) if x > -99 and y > -99)
        out[m] = dict(spearman=round(rho(m), 4), spearman_ci=[round(float(r0[0]), 4), round(float(r0[1]), 4)],
                      delta_extreme=round(delta(m), 4),
                      delta_ci=[round(float(d0[0]), 4), round(float(d0[1]), 4)],
                      monotone_bins=bool(mono),
                      profile=[None if v <= -99 else round(v, 4) for v in sb])
    out["_n_monotone"] = sum(1 for m in MODELS if out[m]["monotone_bins"])
    out["_n_mono_spearman"] = sum(1 for m in MODELS if out[m]["spearman_ci"][0] > 0)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="§5.2 剂量反应 + tab:strength 重算")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--out", default=str(HERE / "out_dose_strength.json"))
    args = ap.parse_args(argv)
    cs = cells()
    print(f"[cells] {len(cs)} 格")
    for c in cs:
        print(f"   {c['cell']:<22} a={c['a']:.4f} masking={c['mask']:+.4f} "
              f"adv={c['adv']:+.4f} cost={c['cost']:+.4f}")
    res = dict(bootstrap=args.boot, seed=SEED, cells=[
        {k: c[k] for k in ("cell", "model", "line", "k", "a", "mask", "adv", "cost")} for c in cs],
        dose=dose_response(cs, args.boot),
        strength_k1=strength_table(1), strength_k5=strength_table(5),
        strength_stats_k1=strength_stats(1, args.boot),
        strength_stats_k5=strength_stats(5, args.boot),
        strata=date_vs_numeric(args.boot))
    d = res["dose"]
    print(f"\n[dose] 17 格斜率 = {d['slope_total']:.4f}（截距 {d['intercept']:+.4f}）")
    print(f"       C 线 {d['slope_C']:.4f} / B 线 {d['slope_B']:.4f}")
    print(f"       留一模型范围 = [{d['loo_range'][0]:.4f}, {d['loo_range'][1]:.4f}]  {d['loo']}")
    bi, bp = d["boot_independent"], d["boot_paired"]
    print(f"       题级自举（独立）95% CI = [{bi['lo']:.4f}, {bi['hi']:.4f}]  "
          f"P(slope<1) = {bi['p_below_1']:.4f}")
    print(f"       题级自举（配对）95% CI = [{bp['lo']:.4f}, {bp['hi']:.4f}]  "
          f"P(slope<1) = {bp['p_below_1']:.4f}")
    print("\n[strata] C 线按答案类型切 date / numeric（论文 §5.2 池内佐证）")
    print(f"   {'model':<22} {'date a':>8} {'date mask':>10} {'num a':>8} {'num mask':>9} "
          f"{'diff':>8} {'95% CI':>20}  n(date/num)")
    for m, v in res["strata"].items():
        ci = v["diff_ci"]
        print(f"   {m:<22} {v['date']['a']:>8.4f} {v['date']['masking']:>10.4f} "
              f"{v['numeric']['a']:>8.4f} {v['numeric']['masking']:>9.4f} "
              f"{v['diff_masking']:>+8.4f} "
              f"{('[%+.4f,%+.4f]' % (ci[0], ci[1])) if ci else 'n/a':>20}  "
              f"{v['date']['n']}/{v['numeric']['n']}")
    for kk in (1, 5):
        print(f"\n[strength k={kk}]  (分箱题数范围 {res[f'strength_k{kk}']['_bin_n_range']})")
        for m in MODELS:
            v = res[f"strength_k{kk}"][m]
            print(f"   {m:<22} {v['cost0']:+.3f} -> {v['cost5']:+.3f}  ratio={v['ratio']}x  "
                  f"n={v['n0']}/{v['n5']}  逐箱单调={v['monotone']}")
        st = res[f"strength_stats_k{kk}"]
        print(f"   -- 可辩护统计（逐题自举 B={args.boot}）--")
        for m in MODELS:
            v = st[m]
            print(f"   {m:<22} Δ(5−0)={v['delta_extreme']:+.4f} "
                  f"[{v['delta_ci'][0]:+.4f},{v['delta_ci'][1]:+.4f}]  "
                  f"rho={v['spearman']:+.4f} [{v['spearman_ci'][0]:+.4f},{v['spearman_ci'][1]:+.4f}]  "
                  f"逐箱单调={v['monotone_bins']}")
        print(f"   ⇒ 逐箱严格单调 {st['_n_monotone']}/6 模型；rho 的 CI 排零 {st['_n_mono_spearman']}/6 模型")
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
