"""五档 k 轴配对统计（只读）：以 k=1 为基线的多档配对 + 表观/校正最优是否翻转。

输入 = run_bline 产出的五个 out_b8_kaxis_k* 目录；复用项目既有 v3 重评与配对 bootstrap
（offline_rescore.rescore_row / stats.did / stats.decision），不新造统计口径。

用法（在 论文/ 目录执行）：
  python -m rag_leak.analyze_kaxis --root rag_leak --ks 1 3 5 10 20 \
      --out rag_leak/out_b8_kaxis_analysis.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .offline_rescore import rescore_row
from .schemas import FourArmRow
from .stats.decision import gain_bootstrap_replicates, judge_sensitive, ranking_flip_probability
from .stats.did import apparent_gain, corrected_gain, did_mean, masking_magnitude, paired_bootstrap

_TABLE_ARMS = ("cb_orig", "cb_sub", "open_orig", "open_sub")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _one(dir_path: Path, suffix: str, name_filter: str = "") -> Path:
    """取唯一匹配的产物文件。

    name_filter 非空时只在该子集里找（如 `pilot_Qwen_Qwen3.5-4B-Base_`）——
    因为两代模型可能写进**同一 out 目录**，`*_metrics.json` 这类通配会同时命中多份，
    不加过滤就会静默取错模型（或直接报"需要恰好一个"）。
    """
    if name_filter:
        # 过滤前缀自身以 '_' 结尾（如 'pilot_Qwen_Qwen3.5-4B-Base_'），而 suffix 也以 '_' 开头，
        # 直接拼接会出现双下划线，故去掉 suffix 的前导 '_'。
        pat = f"{name_filter}{suffix.lstrip('_')}"
    else:
        pat = f"*{suffix}"
    m = sorted(dir_path.glob(pat))
    if len(m) != 1:
        raise ValueError(f"{dir_path}: 需要恰好一个 {pat}，实际 {len(m)} 个：{[p.name for p in m]}")
    return m[0]


def load_arm(root: Path, k: int, pattern: str = "out_b8_kaxis_k{k}", name_filter: str = "") -> dict:
    d = root / pattern.format(k=k)
    if not d.is_dir():
        raise SystemExit(f"{d} 不存在；用 --dir-pattern 指定命名（默认 {{k}} 形式：out_b8_kaxis_k{{k}}）")
    oracle = {r["question_id"]: r for r in _read_jsonl(_one(d, "_oracle_rows.jsonl", name_filter))}
    fourarm = {r["question_id"]: r for r in _read_jsonl(_one(d, "_fourarm.jsonl", name_filter))}
    subs = {r["question_id"]: r for r in _read_jsonl(_one(d, "_substituted.jsonl", name_filter))}
    if len(oracle) != len(fourarm) or set(oracle) != set(fourarm):
        raise ValueError(f"{d}: oracle/fourarm question_id 不一致")
    if set(oracle) != set(subs):
        raise ValueError(f"{d}: oracle/substituted question_id 不一致")
    return dict(k=k, dir=str(d), oracle=oracle, fourarm=fourarm, subs=subs)


def _rows(arm: dict, ids: list[str]) -> list[FourArmRow]:
    out = []
    for qid in ids:
        s = rescore_row(arm["oracle"][qid])["v3"]
        out.append(FourArmRow(qid, "B-line", f"k={arm['k']}",
                              a=s["cb_orig"], b=s["open_orig"], c=s["cb_sub"], d=s["open_sub"],
                              passed_gates=True))
    return out


def _mean(v: list[float]) -> float:
    return sum(v) / len(v) if v else float("nan")


def _sign_test(values: list[float]) -> dict:
    pos = sum(v > 0 for v in values)
    neg = sum(v < 0 for v in values)
    n = pos + neg
    tail = min(pos, neg)
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(tail + 1)) / (2 ** n)) if n else 1.0
    return dict(positive=pos, negative=neg, zero=len(values) - n, sign_test_two_sided=p)


def _scalar_bootstrap(values: list[float], B: int) -> dict:
    from types import SimpleNamespace
    rows = [SimpleNamespace(value=v) for v in values]
    point, ci, _ = paired_bootstrap(rows, lambda rs: _mean([r.value for r in rs]), B=B)
    return dict(mean=point, ci=list(ci), **_sign_test(values))


def _block(rows: list[FourArmRow], B: int) -> dict:
    did, did_ci, _ = paired_bootstrap(rows, did_mean, B=B)
    cor, cor_ci, _ = paired_bootstrap(rows, corrected_gain, B=B)
    return dict(n=len(rows), a=_mean([r.a for r in rows]), b=_mean([r.b for r in rows]),
                c=_mean([r.c for r in rows]), d=_mean([r.d for r in rows]),
                apparent_gain=apparent_gain(rows), corrected_gain=cor, corrected_ci=list(cor_ci),
                did=did, did_ci=list(did_ci), masking=masking_magnitude(rows))


def _subsets(arms: list[dict], ids: list[str], audit: dict | None = None) -> dict[str, list[str]]:
    """全部题 + 结构子集 + 机制分层子集（C23/C24 判读用）+ 人审子集（C32）。

    - oracle_ok：③ 闸门同题过滤，逐题在【所有档】上 oracle 替换后都答出新值（可答主集）。
    - compliance_new：④ 顺从题（oracle_sub 判 new）。用于"以冲突顺从为条件"的 DiD 分层。
    - compliance_old：④ 不顺从且复读旧值（真冲突抵抗）。
    - audited_sample / audited_clean：κ 人审的确定性等距抽样（n=90）及其剔除坏样本后的部分。
      `all_minus_excluded` 只剔被点名的题（远少于真实缺陷数），故其清洗效应是**下界**。
    """
    def ok(a: dict, qid: str) -> bool:
        g = (a["subs"][qid].get("gates") or {})
        return all((g.get(x) or {}).get("passed") is True for x in ("5", "6", "7"))

    def cls(a: dict, qid: str) -> str:
        return str(a["oracle"][qid].get("cls_sub") or "")

    structural = [q for q in ids if all(ok(a, q) for a in arms)]
    tp = [q for q in structural if all(a["oracle"][q].get("term_present") for a in arms)]
    oracle_ok = [q for q in tp if all(cls(a, q).lower() == "new" for a in arms)]
    comp_new = [q for q in tp if all(cls(a, q).lower() == "new" for a in arms)]
    comp_old = [q for q in tp if all(cls(a, q).lower() == "old" for a in arms)]
    out = {"all": ids, "structural_gate567": structural, "structural_term_present": tp,
           "term_present_oracle_ok": oracle_ok, "term_present_compliance_new": comp_new,
           "term_present_compliance_old": comp_old}
    if audit:
        sample = set(audit.get("sample_ids") or [])
        excl = set(audit.get("exclude_ids") or [])
        out["audited_sample"] = [q for q in ids if q in sample]
        out["audited_clean"] = [q for q in ids if q in sample and q not in excl]
        out["all_minus_excluded"] = [q for q in ids if q not in excl]
    return out


def _run_one(args) -> dict:
    root = Path(args.root)
    arms = sorted((load_arm(root, k, args.dir_pattern, args.name_filter) for k in args.ks), key=lambda a: a["k"])
    ids = sorted(set(arms[0]["oracle"]))
    for a in arms[1:]:
        if set(a["oracle"]) != set(ids):
            raise SystemExit(f"k={a['k']} 的 question_id 集与 k={arms[0]['k']} 不一致")
    # 构集必须与 k 无关（substituted 正文逐题一致）
    for qid in ids:
        base = arms[0]["subs"][qid]["new_passage"]
        for a in arms[1:]:
            if a["subs"][qid]["new_passage"] != base:
                raise SystemExit(f"{qid}: k={a['k']} 的 new_passage 与 k={arms[0]['k']} 不同，拒绝配对")

    audit = json.loads(Path(args.audit_json).read_text(encoding="utf-8")) if args.audit_json else None
    subset_ids = _subsets(arms, ids, audit)
    if args.subset not in subset_ids:
        raise SystemExit(f"--subset {args.subset} 不存在；可选：{sorted(subset_ids)}")
    sel = subset_ids[args.subset]
    if len(sel) < 2:
        raise SystemExit(f"--subset {args.subset} 只有 {len(sel)} 题，无法配对")
    # 选定非 all 子集时，把**所有**子集都限制在它内部——否则 per_k 里的顺从/抵抗分层
    # 仍是全量的那一批题，清洗敏感性就看不到分层内部的变化。
    if args.subset != "all":
        selset = set(sel)
        subset_ids = {name: [q for q in v if q in selset] for name, v in subset_ids.items()}
    per_k = {a["k"]: _rows(a, sel) for a in arms}
    result = dict(
        protocol="bline-kaxis-paired-v3",
        note=("只读配对；主口径=全部题，结构子集作稳健性对照。Δ 一律以最小 k 为基线，masking=-DiD。"),
        subset_used=args.subset,
        ks=[a["k"] for a in arms],
        subsets={name: len(q) for name, q in subset_ids.items()},
        per_k={}, paired_vs_k1={}, formal_vs_k1={}, monotonicity={},
    )
    for a in arms:
        k = a["k"]
        result["per_k"][f"k={k}"] = {name: _block(_rows(a, q), args.bootstrap)
                                     for name, q in subset_ids.items()}
        if k == arms[0]["k"]:
            continue
        base = arms[0]
        b_rows, k_rows = per_k[base["k"]], per_k[k]
        by_b, by_k = {r.question_id: r for r in b_rows}, {r.question_id: r for r in k_rows}
        fields = {
            "delta_apparent": [by_k[q].apparent_gain - by_b[q].apparent_gain for q in by_b],
            "delta_corrected": [by_k[q].corrected_gain - by_b[q].corrected_gain for q in by_b],
            "delta_masking": [(-by_k[q].did) - (-by_b[q].did) for q in by_b],
            "delta_d": [by_k[q].d - by_b[q].d for q in by_b],
        }
        result["paired_vs_k1"][f"k={k}"] = {n: _scalar_bootstrap(v, args.bootstrap)
                                            for n, v in fields.items()}
        cfg = {f"k={base['k']}": b_rows, f"k={k}": k_rows}
        app = gain_bootstrap_replicates(cfg, "apparent_gain", B=args.bootstrap)
        cor = gain_bootstrap_replicates(cfg, "corrected_gain", B=args.bootstrap)
        p_flip, app_best, cor_best = ranking_flip_probability(app, cor)
        _, app_ci, _ = paired_bootstrap(cfg[app_best], corrected_gain, B=args.bootstrap)
        _, cor_ci, _ = paired_bootstrap(cfg[cor_best], corrected_gain, B=args.bootstrap)
        result["formal_vs_k1"][f"k={k}"] = dict(
            apparent_best=app_best, corrected_best=cor_best,
            corrected_ci_apparent_best=list(app_ci), corrected_ci_corrected_best=list(cor_ci),
            **judge_sensitive(p_flip, app_ci, cor_ci))

    # 全局 argmax：表观最优 vs 校正最优
    app_means = {f"k={a['k']}": apparent_gain(per_k[a["k"]]) for a in arms}
    cor_means = {f"k={a['k']}": corrected_gain(per_k[a["k"]]) for a in arms}
    result["argmax"] = dict(
        apparent=dict(argmax=max(app_means, key=app_means.get), means=app_means),
        corrected=dict(argmax=max(cor_means, key=cor_means.get), means=cor_means),
    )
    result["argmax"]["flipped"] = (max(app_means, key=app_means.get) != max(cor_means, key=cor_means.get))
    # 用全部五档的 bootstrap 副本算"表观最优≠校正最优"的概率。
    # gain_bootstrap_replicates 返回 {配置: [每副本的均值]}（不是按副本的列表），
    # 同一副本索引跨配置可比（共用 RNG 种子），故按索引比对 argmax。
    cfg_all = {f"k={a['k']}": per_k[a["k"]] for a in arms}
    app_all = gain_bootstrap_replicates(cfg_all, "apparent_gain", B=args.bootstrap)
    cor_all = gain_bootstrap_replicates(cfg_all, "corrected_gain", B=args.bootstrap)
    n_rep = min(len(v) for v in app_all.values())
    n_flip = 0
    for i in range(n_rep):
        a_best = max(app_all, key=lambda name: app_all[name][i])
        c_best = max(cor_all, key=lambda name: cor_all[name][i])
        n_flip += int(a_best != c_best)
    result["argmax"]["p_flip_all_ks"] = n_flip / max(1, n_rep)
    result["argmax"]["bootstrap_replicates"] = n_rep
    result["monotonicity"] = _monotone_report([a["k"] for a in arms], app_means, cor_means)
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="k 轴配对统计（只读；支持多模型分组）")
    ap.add_argument("--root", default="rag_leak", help="包含 out_b8_* 的目录")
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 3, 5, 10, 20])
    ap.add_argument("--out", required=True)
    ap.add_argument("--dir-pattern", default="out_b8_kaxis_k{k}",
                    help="run 目录命名模板，须含 {k}，可用 {tag}；全量单模型用 out_b8_full_k{k}")
    ap.add_argument("--tags", default="",
                    help="多模型分组：逗号分隔（如 06b,17b,4b,4bi）；pattern 里需含 {tag}。"
                         "给出时输出为 {tag: 结果} 的合并 JSON")
    ap.add_argument("--name-filter", default="",
                    help="产物文件名前缀过滤（如 pilot_Qwen_Qwen3.5-4B-Base_）。"
                         "同一 out 目录里并存多代模型产物时必须给，否则 _one() 报'需要恰好一个'")
    ap.add_argument("--bootstrap", type=int, default=config.BOOTSTRAP_B)
    ap.add_argument("--audit-json", default="",
                    help="人审缺陷清单 JSON（含 sample_ids / exclude_ids），用于构造 "
                         "audited_sample / audited_clean / all_minus_excluded 子集（见 C32）")
    ap.add_argument("--subset", default="all",
                    help="用哪个子集做配对与正式判定（默认 all；清洗敏感性分析用 audited_clean）")
    args = ap.parse_args(argv)
    if args.bootstrap < 100:
        raise SystemExit("--bootstrap 至少为 100")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    if not tags:
        result = _run_one(args)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
        _print(result)
        print(f"\n已写：{args.out}")
        return 0

    pattern = args.dir_pattern
    if "{tag}" not in pattern:
        raise SystemExit("--tags 需要 --dir-pattern 含 {tag} 占位符")
    combined: dict[str, dict] = {}
    for tag in tags:
        sub = argparse.Namespace(**{**vars(args), "dir_pattern": pattern})
        sub.tag = tag
        # 让 load_arm 的 pattern.format(k=..., tag=...) 生效
        try:
            res = _run_one_typed(sub)
        except SystemExit as e:
            print(f"[skip] tag={tag}: {e}")
            continue
        combined[tag] = res
        print(f"\n########## tag = {tag} ##########")
        _print(res)
    Path(args.out).write_text(json.dumps(combined, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写合并结果（{len(combined)} 个模型）：{args.out}")
    return 0


def _run_one_typed(args) -> dict:
    """多模型分支：把 tag 注入 pattern 后跑单组分析（只替换 {tag}，保留 {k} 给 load_arm）。"""
    args.dir_pattern = args.dir_pattern.replace("{tag}", str(args.tag))
    return _run_one(args)


def _monotone_report(ks: list[int], app: dict, cor: dict) -> dict:
    def shape(vals: list[float]) -> str:
        ups = [vals[i + 1] > vals[i] for i in range(len(vals) - 1)]
        if all(ups):
            return "单调升"
        if not any(ups):
            return "单调降"
        return "非单调"

    av = [app[f"k={k}"] for k in ks]
    cv = [cor[f"k={k}"] for k in ks]
    gap = [av[i] - cv[i] for i in range(len(ks))]
    return dict(apparent_shape=shape(av), corrected_shape=shape(cv),
                apparent_values=dict(zip([str(k) for k in ks], av)),
                corrected_values=dict(zip([str(k) for k in ks], cv)),
                gap_apparent_minus_corrected=dict(zip([str(k) for k in ks], gap)),
                corrected_trough_k=ks[cv.index(min(cv))])


def _print(r: dict) -> None:
    tag = r.get("subset_used", "all")
    print(f"=== 每档（子集 {tag}；题数见下）===")
    print(f"  子集题数：{r['subsets']}")
    for name, blk in r["per_k"].items():
        b = blk["all"]
        print(f"  {name:>6} n={b['n']:>3}: a={b['a']:.3f} b={b['b']:.3f} c={b['c']:.3f} d={b['d']:.3f} | "
              f"表观={b['apparent_gain']:+.4f} 校正={b['corrected_gain']:+.4f} "
              f"DiD={b['did']:+.4f} CI=[{b['did_ci'][0]:+.4f},{b['did_ci'][1]:+.4f}] masking={b['masking']:.4f}")
    for kname, blk in r["per_k"].items():
        for sub in ("term_present_compliance_new", "term_present_compliance_old",
                    "structural_term_present"):
            z = blk.get(sub)
            if z and z["n"]:
                print(f"  [分层 {kname} · {sub}] n={z['n']:>3} 表观={z['apparent_gain']:+.4f} "
                      f"校正={z['corrected_gain']:+.4f} masking={z['masking']:.4f}")
    print(f"\n=== 配对差（相对最小 k，子集 {tag}）===")
    for name, d in r["paired_vs_k1"].items():
        a, c, m = d["delta_apparent"], d["delta_corrected"], d["delta_masking"]
        print(f"  {name:>6}: Δ表观={a['mean']:+.4f} CI[{a['ci'][0]:+.4f},{a['ci'][1]:+.4f}] sign-p={a['sign_test_two_sided']:.3g} | "
              f"Δ校正={c['mean']:+.4f} CI[{c['ci'][0]:+.4f},{c['ci'][1]:+.4f}] | "
              f"Δmasking={m['mean']:+.4f} CI[{m['ci'][0]:+.4f},{m['ci'][1]:+.4f}]")
    print("\n=== 相对 k=1 的 B1（两两）===")
    for name, v in r["formal_vs_k1"].items():
        print(f"  {name:>6}: 表观最优={v['apparent_best']} 校正最优={v['corrected_best']} "
              f"P(flip)={v['p_flip']:.3f} CI分离={v['corrected_ci_separated']} -> {v['verdict']}")
    ax = r["argmax"]
    print("\n=== 全局 argmax（五档）===")
    print(f"  表观最优={ax['apparent']['argmax']}  校正最优={ax['corrected']['argmax']}  翻转={ax['flipped']}")
    print(f"  P(表观argmax != 校正argmax) = {ax['p_flip_all_ks']:.3f}（B={ax.get('bootstrap_replicates')} 副本）")
    print(f"  表观均值={ {k: round(v,4) for k,v in ax['apparent']['means'].items()} }")
    print(f"  校正均值={ {k: round(v,4) for k,v in ax['corrected']['means'].items()} }")
    mo = r["monotonicity"]
    print(f"\n=== 形状 ===\n  表观={mo['apparent_shape']}  校正={mo['corrected_shape']}  "
          f"校正谷底=k{mo['corrected_trough_k']}")


if __name__ == "__main__":
    sys.exit(main())
