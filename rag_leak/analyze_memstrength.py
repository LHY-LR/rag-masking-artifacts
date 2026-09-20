r"""B3 离线判读：连续记忆强度 lp_old 能否在恒等式之外解释掩盖量。

回答的问题（这正是 B3 存在的理由）
----------------------------------
主文 H4 剂量-反应是「masking ~ 二值 a」的斜率 0.503。但

    masking = (a - c) + (d - b)

里 **a 逐字出现**，所以该斜率天然含机械成分。本脚本换成 **不出现在恒等式里** 的连续强度
lp_old（闭卷下旧答案串的 teacher-forced 平均对数概率），做三件事：

1. **组内（同一模型跨题）**：masking_i 与 lp_old_i 的 Pearson/Spearman 相关。跨题比较
   与"跨模型比较"是两件不同的证据，后者可能被模型规模/家族混杂。
2. **合并回归**：先做**组内中心化**（去掉模型均值，消掉跨模型混杂），再回归
    masking_z ~ lp_old_z 与 masking_z ~ a_z；以及**二元**回归 masking_z ~ lp_old_z + a_z。
   若控制 a 之后 lp_old 的系数仍显著为正 → "记忆强度"携带恒等式之外的信息（本项的核心判据）。
3. **机制**：lp_old 是否预测**操纵代价** (b-d) 与**闭卷顺从残留** c。分解里唯一可动的项是
   (b-d)，若它随 lp_old 单调上升，机制链条（记忆越强 → 越抵抗替换 → 掩盖越大）就闭合。

纪律
----
- 只读：吃冻结 run 的 fourarm 产物 + B3 探针产物，join 键 = question_id；缺题即报错。
- 口径冻结：配对题级 bootstrap B=10000、seed 20260903（与主文一致）；不做事后口径挑拣，
  三种口径（mean/sum/first）**全部**落盘。
- 「先验证再判读」：本脚本自带 join 覆盖率与 MD5 打印，判读前先看这两行。
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

from .probe_memory_strength import HERE, RUNS

B = 10000
SEED = 20260903


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _find(d: Path, suffix: str) -> Path:
    hits = sorted(d.glob(f"*{suffix}"))
    if len(hits) != 1:
        raise SystemExit(f"{d} 下应有唯一 *{suffix}，实际 {[h.name for h in hits]}")
    return hits[0]


def load_pairs(group: str, ms_dir: Path, fourarm_dir: Path | None = None) -> list[dict]:
    """join 四臂行与强度行；返回逐题记录（含 a/b/c/d 与三种 lp 口径）。"""
    out: list[dict] = []
    for model, dname in RUNS[group]:
        base = (fourarm_dir or HERE) / dname
        rows = {r["question_id"]: r for r in _jsonl(_find(base, "_fourarm.jsonl"))}
        ms_path = ms_dir / f"memstrength_{model.replace('/', '_')}.jsonl"
        ms = {r["question_id"]: r for r in _jsonl(ms_path)}
        miss_f = set(ms) - set(rows)
        miss_m = set(rows) - set(ms)
        if miss_f or miss_m:
            raise SystemExit(f"{model}: join 缺口 四臂缺 {len(miss_f)} 强度缺 {len(miss_m)}")
        print(f"  [join] {model:<22} n={len(rows)}  fourarm={_md5(_find(base, '_fourarm.jsonl'))[:8]}"
              f"  memstrength={_md5(ms_path)[:8]}  dir={dname}")
        for qid, r in rows.items():
            m = ms[qid]
            o, n = m["lp"]["old"], m["lp"]["new"]
            if not o or o["mean_lp"] is None:
                continue
            out.append(dict(
                model=model, question_id=qid, dataset=r.get("dataset"),
                a=r["a"], b=r["b"], c=r["c"], d=r["d"],
                apparent=r["b"] - r["a"], corrected=r["d"] - r["c"],
                masking=(r["d"] - r["c"]) - (r["b"] - r["a"]), cost=r["b"] - r["d"],
                lp_old_mean=o["mean_lp"], lp_old_sum=o["sum_lp"], lp_old_first=o["first_lp"],
                lp_new_mean=n["mean_lp"] if n and n["mean_lp"] is not None else None,
                margin_mean=m.get("margin_mean")))
    return out


# ---------------- 统计工具（numpy 即可，不引入 scipy 依赖） ----------------
def _pearson(x, y) -> float:
    import numpy as np
    x, y = np.asarray(x, float), np.asarray(y, float)
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _rank(x):
    import numpy as np
    x = np.asarray(x, float)
    order = x.argsort()
    r = np.empty(len(x), float)
    r[order] = np.arange(len(x), dtype=float)
    # 并列取平均秩（Spearman 正确性）
    vals, inv, cnt = np.unique(x, return_inverse=True, return_counts=True)
    for k in range(len(vals)):
        if cnt[k] > 1:
            r[inv == k] = r[inv == k].mean()
    return r


def _spearman(x, y) -> float:
    return _pearson(_rank(x), _rank(y))


def _ols(X, y) -> tuple[list[float], float]:
    """返回 (系数(含截距), R²)。X 为 n×k。"""
    import numpy as np
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return [float(v) for v in beta], (1 - ss_res / ss_tot if ss_tot else float("nan"))


def _centre(rows: list[dict], key: str) -> list[float]:
    """组内中心化：减去该模型均值（消掉跨模型规模/家族混杂）。"""
    import numpy as np
    out = np.zeros(len(rows))
    for m in sorted({r["model"] for r in rows}):
        idx = [i for i, r in enumerate(rows) if r["model"] == m]
        v = np.array([rows[i][key] for i in idx], float)
        out[idx] = v - v.mean()
    return list(out)


# ---- bootstrap 统计量：必须是「进函数一次、内部复用」的纯函数 ----
# 反例（本文件初版踩过）：把 _centre(rs, ...) 写在逐元素推导式里，等于每个样本都重算
# 一次全量中心化 → 单次 replicate 从 3ms 涨到 4s（B=10000 时约 11 小时）。性能不是风格问题。
def _stat_lp_uni(rs: list[dict]) -> float:
    return _ols([[v] for v in _centre(rs, "lp_old_mean")], _centre(rs, "masking"))[0][1]


def _stat_cost(rs: list[dict]) -> float:
    return _ols([[v] for v in _centre(rs, "lp_old_mean")], _centre(rs, "cost"))[0][1]


def _stat_bivar(rs: list[dict], which: int) -> float:
    lz, az, mk = _centre(rs, "lp_old_mean"), _centre(rs, "a"), _centre(rs, "masking")
    return _ols([[lz[i], az[i]] for i in range(len(rs))], mk)[0][which]


def _boot(rows: list[dict], stat, b: int | None = None, seed: int = SEED) -> dict:
    """题级配对 bootstrap（重抽 question_id，同题所有模型行一起抽 → 保留配对结构）。

    b 默认取**运行时**全局 B（不能用 `b: int = B` 的默认参数——那会在定义时把 10000 钉死，
    `--boot` 覆盖失效；此处显式在函数体内解析）。
    """
    import numpy as np
    b = B if b is None else b
    rng = np.random.default_rng(seed)
    qids = sorted({r["question_id"] for r in rows})
    by_q: dict[str, list[int]] = {}
    for i, r in enumerate(rows):
        by_q.setdefault(r["question_id"], []).append(i)
    vals = []
    for _ in range(b):
        pick = rng.choice(len(qids), size=len(qids), replace=True)
        idx = [i for k in pick for i in by_q[qids[k]]]
        v = stat([rows[i] for i in idx])
        if v is not None and v == v:
            vals.append(v)
    if not vals:
        return dict(point=None, lo=None, hi=None, n_ok=0)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return dict(point=round(stat(rows), 6), lo=round(float(lo), 6), hi=round(float(hi), 6),
                n_ok=len(vals))


def analyse(rows: list[dict]) -> dict:
    import numpy as np
    res: dict = dict(n=len(rows), models=sorted({r["model"] for r in rows}), per_model={},
                     bootstrap_b=B, seed=SEED)

    # ---- 逐模型描述 + 组内相关（用 mean 口径为主，另两口径并列落盘备查） ----
    for m in res["models"]:
        sub = [r for r in rows if r["model"] == m]
        d = dict(n=len(sub),
                 masking=round(float(np.mean([r["masking"] for r in sub])), 4),
                 a=round(float(np.mean([r["a"] for r in sub])), 4),
                 c=round(float(np.mean([r["c"] for r in sub])), 4),
                 cost=round(float(np.mean([r["cost"] for r in sub])), 4),
                 lp_old_mean=round(float(np.mean([r["lp_old_mean"] for r in sub])), 4),
                 lp_old_first=round(float(np.mean([r["lp_old_first"] for r in sub])), 4))
        for k in ("lp_old_mean", "lp_old_sum", "lp_old_first", "margin_mean"):
            xs = [r[k] for r in sub]
            if any(v is None for v in xs):
                d[f"r_masking_{k}"] = None
                d[f"rho_masking_{k}"] = None
                continue
            d[f"r_masking_{k}"] = round(_pearson(xs, [r["masking"] for r in sub]), 4)
            d[f"rho_masking_{k}"] = round(_spearman(xs, [r["masking"] for r in sub]), 4)
        d["r_masking_a"] = round(_pearson([r["a"] for r in sub], [r["masking"] for r in sub]), 4)
        d["r_lp_a"] = round(_pearson([r["lp_old_mean"] for r in sub], [r["a"] for r in sub]), 4)
        res["per_model"][m] = d

    # ---- 合并：组内中心化后的一元/二元回归 ----
    z = lambda k: _centre(rows, k)  # noqa: E731
    mk, lz, az = z("masking"), z("lp_old_mean"), z("a")
    b1, r1 = _ols([[v] for v in lz], mk)
    b2, r2 = _ols([[v] for v in az], mk)
    b3, r3 = _ols([[lz[i], az[i]] for i in range(len(rows))], mk)
    res["pooled"] = dict(
        univariate_lp=dict(coef=round(b1[1], 4), r2=round(r1, 4)),
        univariate_a=dict(coef=round(b2[1], 4), r2=round(r2, 4)),
        bivariate=dict(coef_lp=round(b3[1], 4), coef_a=round(b3[2], 4), r2=round(r3, 4),
                       note="组内中心化后；coef_lp 在控制二值 a 之后仍为正 = 恒等式之外的信息"),
        boot_lp_univariate=_boot(rows, _stat_lp_uni),
        boot_lp_bivariate=_boot(rows, lambda rs: _stat_bivar(rs, 1)),
        boot_a_bivariate=_boot(rows, lambda rs: _stat_bivar(rs, 2)),
    )

    # ---- 稳健性：换一个连续强度口径再问同样的问题 ----
    # 为什么必须做：B3 的结论（"控制 a 后连续强度无增量"）如果只在一个口径上成立，就不能算结论。
    # `margin_mean = lp_old − lp_new`（旧值相对虚构新值的边际）是另一种同样自然的算子，
    # 且与 a 的相关性更低。两个口径都失败才敢说"是构造的限制，不是我的实现选择造成的"。
    res["alternate_measures"] = {}
    for xk in ("lp_old_mean", "margin_mean"):
        sub = [r for r in rows if r.get(xk) is not None]
        if len(sub) < len(rows):
            res["alternate_measures"][xk] = dict(n=len(sub), note="有 None，已剔除后计算")
        xz = _centre(sub, xk)
        az2 = _centre(sub, "a")
        mz = _centre(sub, "masking")
        czo = _centre(sub, "cost")
        u, _ = _ols([[v] for v in xz], mz)
        bi, _ = _ols([[xz[i], az2[i]] for i in range(len(sub))], mz)
        cu, _ = _ols([[v] for v in xz], czo)
        cb, _ = _ols([[xz[i], az2[i]] for i in range(len(sub))], czo)
        res["alternate_measures"][xk] = dict(
            n=len(sub),
            univariate_masking=round(u[1], 4),
            bivariate_masking_lp=round(bi[1], 4), bivariate_masking_a=round(bi[2], 4),
            univariate_cost=round(cu[1], 4),
            bivariate_cost_lp=round(cb[1], 4), bivariate_cost_a=round(cb[2], 4),
            r_with_a=round(_pearson([r[xk] for r in sub], [r["a"] for r in sub]), 4),
            boot_bivariate_masking_lp=_boot(
                sub, lambda rs, k=xk: _stat_bivar_key(rs, k, 1)),
            boot_bivariate_cost_lp=_boot(
                sub, lambda rs, k=xk: _stat_bivar_key(rs, k, 1, ykey="cost")))
    # ---- 机制：lp_old 是否预测操纵代价 (b-d) 与闭卷残余 c ----
    # 关键补充：一元显著不代表独立——(b−d) 与 a 也强相关，故必须做**控制 a 的二元回归**。
    # 若二元里 lp_old 的 CI 仍排零，才说明连续强度对"可动项"携带恒等式之外的信息。
    cz = _centre(rows, "cost")
    bc, rc = _ols([[v] for v in lz], cz)
    bc2, rc2 = _ols([[lz[i], az[i]] for i in range(len(rows))], cz)
    res["mechanism"] = dict(
        cost_on_lp=dict(coef=round(bc[1], 4), r2=round(rc, 4),
                        boot=_boot(rows, _stat_cost)),
        cost_on_lp_ctrl_a=dict(coef_lp=round(bc2[1], 4), coef_a=round(bc2[2], 4),
                               r2=round(rc2, 4),
                               boot_lp=_boot(rows, lambda rs: _stat_bivar_cost(rs, 1)),
                               boot_a=_boot(rows, lambda rs: _stat_bivar_cost(rs, 2))),
        c_rate_by_lp_quartile=_quartile_table(rows, "lp_old_mean", "c"),
        a_rate_by_lp_quartile=_quartile_table(rows, "lp_old_mean", "a"),
        masking_by_lp_quartile=_quartile_mean(rows, "lp_old_mean", "masking"),
    )
    return res


def _stat_bivar_cost(rs: list[dict], which: int) -> float:
    """二元回归 cost ~ lp_old + a 的第 which 个系数（which=1 → lp_old，2 → a）。"""
    lz, az, cz = _centre(rs, "lp_old_mean"), _centre(rs, "a"), _centre(rs, "cost")
    return _ols([[lz[i], az[i]] for i in range(len(rs))], cz)[0][which]


def _stat_bivar_key(rs: list[dict], xkey: str, which: int, ykey: str = "masking") -> float:
    """任意连续口径 xkey 的二元回归 ykey ~ xkey + a 的第 which 个系数。"""
    xz, az, yz = _centre(rs, xkey), _centre(rs, "a"), _centre(rs, ykey)
    return _ols([[xz[i], az[i]] for i in range(len(rs))], yz)[0][which]


def _quartile_table(rows: list[dict], xkey: str, ykey: str) -> list[dict]:
    import numpy as np
    x = np.array([r[xkey] for r in rows], float)
    qs = np.percentile(x, [25, 50, 75])
    out = []
    for i, (lo, hi) in enumerate([(-np.inf, qs[0]), (qs[0], qs[1]), (qs[1], qs[2]),
                                  (qs[2], np.inf)]):
        sub = [r for r in rows if lo <= r[xkey] < hi]
        out.append(dict(q=f"Q{i+1}", n=len(sub),
                        rate=round(float(np.mean([r[ykey] for r in sub])), 4) if sub else None))
    return out


def _quartile_mean(rows: list[dict], xkey: str, ykey: str) -> list[dict]:
    import numpy as np
    x = np.array([r[xkey] for r in rows], float)
    qs = np.percentile(x, [25, 50, 75])
    out = []
    for i, (lo, hi) in enumerate([(-np.inf, qs[0]), (qs[0], qs[1]), (qs[1], qs[2]),
                                  (qs[2], np.inf)]):
        sub = [r for r in rows if lo <= r[xkey] < hi]
        out.append(dict(q=f"Q{i+1}", n=len(sub),
                        mean=round(float(np.mean([r[ykey] for r in sub])), 4) if sub else None))
    return out


def render(res: dict) -> str:
    L = ["# B3 判读：连续记忆强度 lp_old 与掩盖量", "",
         f"n={res['n']}（{len(res['models'])} 模型）；bootstrap B={res['bootstrap_b']} seed={res['seed']}", "",
         "## 逐模型（组内相关：同一模型跨题）", "",
         "| 模型 | n | masking | a | c | cost | lp_old | r(masking, lp_old) | rho | r(masking, a) | r(lp, a) |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, d in res["per_model"].items():
        L.append(f"| {m} | {d['n']} | {d['masking']:+.4f} | {d['a']:.4f} | {d['c']:.4f} | "
                 f"{d['cost']:+.4f} | {d['lp_old_mean']:+.4f} | "
                 f"{d['r_masking_lp_old_mean']:+.4f} | {d['rho_masking_lp_old_mean']:+.4f} | "
                 f"{d['r_masking_a']:+.4f} | {d['r_lp_a']:+.4f} |")
    p = res["pooled"]
    L += ["", "## 合并回归（组内中心化，去掉跨模型混杂）", "",
          f"- 一元 masking ~ lp_old：coef={p['univariate_lp']['coef']:+.4f}  R²={p['univariate_lp']['r2']:.4f}",
          f"- 一元 masking ~ a（对照，含机械成分）：coef={p['univariate_a']['coef']:+.4f}  R²={p['univariate_a']['r2']:.4f}",
          f"- **二元 masking ~ lp_old + a**：coef_lp={p['bivariate']['coef_lp']:+.4f}  "
          f"coef_a={p['bivariate']['coef_a']:+.4f}  R²={p['bivariate']['r2']:.4f}", "",
          "| 量 | 点估计 | 95% CI | n_ok |", "|---|---|---|---|",
          f"| 一元 coef(lp_old) | {p['boot_lp_univariate']['point']:+.4f} | "
          f"[{p['boot_lp_univariate']['lo']:+.4f}, {p['boot_lp_univariate']['hi']:+.4f}] | "
          f"{p['boot_lp_univariate']['n_ok']} |",
          f"| 二元 coef(lp_old) | {p['boot_lp_bivariate']['point']:+.4f} | "
          f"[{p['boot_lp_bivariate']['lo']:+.4f}, {p['boot_lp_bivariate']['hi']:+.4f}] | "
          f"{p['boot_lp_bivariate']['n_ok']} |",
          f"| 二元 coef(a) | {p['boot_a_bivariate']['point']:+.4f} | "
          f"[{p['boot_a_bivariate']['lo']:+.4f}, {p['boot_a_bivariate']['hi']:+.4f}] | "
          f"{p['boot_a_bivariate']['n_ok']} |", "",
          "## 机制：操纵代价 (b-d) 与闭卷残余 c", "",
          f"- cost ~ lp_old（一元）：coef={res['mechanism']['cost_on_lp']['coef']:+.4f} "
          f"CI[{res['mechanism']['cost_on_lp']['boot']['lo']:+.4f}, "
          f"{res['mechanism']['cost_on_lp']['boot']['hi']:+.4f}]  "
          f"R²={res['mechanism']['cost_on_lp']['r2']:.4f}",
          f"- **cost ~ lp_old + a（控制 a 后）**：coef_lp="
          f"{res['mechanism']['cost_on_lp_ctrl_a']['coef_lp']:+.4f} "
          f"CI[{res['mechanism']['cost_on_lp_ctrl_a']['boot_lp']['lo']:+.4f}, "
          f"{res['mechanism']['cost_on_lp_ctrl_a']['boot_lp']['hi']:+.4f}]；coef_a="
          f"{res['mechanism']['cost_on_lp_ctrl_a']['coef_a']:+.4f} "
          f"CI[{res['mechanism']['cost_on_lp_ctrl_a']['boot_a']['lo']:+.4f}, "
          f"{res['mechanism']['cost_on_lp_ctrl_a']['boot_a']['hi']:+.4f}]", "",
          "## 换连续口径的稳健性（两个算子都失败才算「构造的限制」）", "",
          "| 口径 | n | r(·,a) | 一元 masking | **二元 masking coef** | 95% CI | 一元 cost | **二元 cost coef** | 95% CI |",
          "|---|---|---|---|---|---|---|---|---|"]
    for xk, v in res["alternate_measures"].items():
        bm, bc2 = v["boot_bivariate_masking_lp"], v["boot_bivariate_cost_lp"]
        L.append(f"| {xk} | {v['n']} | {v['r_with_a']:+.4f} | {v['univariate_masking']:+.4f} | "
                 f"**{v['bivariate_masking_lp']:+.4f}** | "
                 f"[{bm['lo']:+.4f}, {bm['hi']:+.4f}] | {v['univariate_cost']:+.4f} | "
                 f"**{v['bivariate_cost_lp']:+.4f}** | [{bc2['lo']:+.4f}, {bc2['hi']:+.4f}] |")
    L += ["", "| lp_old 四分位 | n | mean(masking) | rate(a=1) | rate(c=1) |", "|---|---|---|---|---|"]
    for q, w in zip(res["mechanism"]["masking_by_lp_quartile"],
                    res["mechanism"]["c_rate_by_lp_quartile"]):
        aq = res["mechanism"]["a_rate_by_lp_quartile"][int(q["q"][1]) - 1]
        L.append(f"| {q['q']} | {q['n']} | {q['mean']:+.4f} | {aq['rate']:.4f} | {w['rate']:.4f} |")
    return "\n".join(L)


def main(argv=None) -> int:
    global B  # 必须先于任何对 B 的读取（否则 SyntaxError: used prior to global declaration）
    ap = argparse.ArgumentParser(description="B3 离线判读")
    ap.add_argument("--runs", default="s6trivia", choices=sorted(RUNS))
    ap.add_argument("--ms-dir", default="",
                    help="B3 强度产物目录；空=out_memstrength/<runs>（与探针落盘位置一致）")
    ap.add_argument("--out", default=str(HERE / "out_memstrength_analysis.json"))
    ap.add_argument("--md", default=str(HERE / "out_memstrength_analysis.md"))
    ap.add_argument("--boot", type=int, default=B)
    args = ap.parse_args(argv)
    B = args.boot
    if not args.ms_dir:
        args.ms_dir = str(HERE / "out_memstrength" / args.runs)

    rows = load_pairs(args.runs, Path(args.ms_dir))
    print(f"[B3] join 后 n={len(rows)}")
    res = analyse(rows)
    md = render(res)
    Path(args.md).write_text(md, encoding="utf-8")
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(md)
    print(f"\n[B3] -> {args.out}\n[B3] -> {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
