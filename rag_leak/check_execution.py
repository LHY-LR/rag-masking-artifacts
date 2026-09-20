"""执行结果验收自检（第四轮，离线读回，不加载模型）。

对 run_pipeline/grid.py 产出的 out/ 目录做读回校验：
  1) 聚焦 8 格（模型×预算）是否都有 *_fourarm.jsonl + *_manifest.json；
  2) 每格行数、config_key 是否与预期一致、四臂值 a/b/c/d 是否合法；
  3) 每格 表观/校正 增益 + 记忆掩盖量，并逐模型跑 B1 敏感带判定；
  4) T3 出口非全 INSUFFICIENT（n≥30 才有意义）、无退化格（全 0/全 1）。

用法（在 论文/ 下）：
  python -m rag_leak.check_execution --results_dir rag_leak/out_grid
退出码 0=通过（可能有 warning），1=存在硬伤。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .schemas import FourArmRow
from .cli import load_rows
from .stats.did import apparent_gain, corrected_gain, did_mean, masking_magnitude, paired_bootstrap
from .stats.decision import gain_bootstrap_replicates, ranking_flip_probability, judge_sensitive
from .grid import FOCUSED_MODELS, FOCUSED_BUDGETS, FOCUSED_GRANULARITY, FOCUSED_K


def _row_valid(r: FourArmRow) -> bool:
    return all(v in (0, 1) for v in (r.a, r.b, r.c, r.d))


def check_cell(result_dir: Path, model: str, budget: int, k: int = FOCUSED_K) -> tuple[list[FourArmRow], dict, list[str]]:
    """返回 (rows, manifest, issues)。缺文件即抛，由调用方 catch。

    k 由调用方传入（默认取 FOCUSED_K）；第二轮执行用 k=20 重跑预算敏感度子实验时，
    expect_key 必须跟随实际检索池大小，否则会把合法的 k20 配置误判为 config_key 不匹配。"""
    label = f"focused_{model}_{budget}"
    fa = result_dir / f"{label}_fourarm.jsonl"
    ma = result_dir / f"{label}_manifest.json"
    issues: list[str] = []
    rows = load_rows(result_dir) if fa.exists() else []
    rows = [r for r in rows if r.model == model and f"b{budget}" in r.config_key]
    manifest = None
    if ma.exists():
        manifest = json.loads(ma.read_text(encoding="utf-8"))
    if not fa.exists():
        issues.append(f"缺文件 {fa.name}")
    if not ma.exists():
        issues.append(f"缺 manifest {ma.name}")
    if not rows:
        issues.append(f"{label}: 无匹配行（model={model}, b{budget}）")
    else:
        expect_key = f"{FOCUSED_GRANULARITY}|b{budget}|k{k}|rr0"
        bad_key = [r.config_key for r in rows if r.config_key != expect_key]
        if bad_key:
            issues.append(f"{label}: config_key≠{expect_key}，出现 {set(bad_key)}")
        if not all(_row_valid(r) for r in rows):
            issues.append(f"{label}: 存在非法四臂值(应为0/1)")
    return rows, manifest, issues


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--results_dir", required=True)
    ap.add_argument("--models", default=",".join(FOCUSED_MODELS))
    ap.add_argument("--budgets", default=",".join(str(b) for b in FOCUSED_BUDGETS))
    ap.add_argument("--granularity", default=FOCUSED_GRANULARITY)
    ap.add_argument("--k", type=int, default=FOCUSED_K)
    ap.add_argument("--fail_on_mask_negative", action="store_true",
                    help="把'掩盖量为负'当硬伤（默认仅警告，因为它可能真实代表该格无记忆）")
    args = ap.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]
    result_dir = Path(args.results_dir)
    hard_issues: list[str] = []
    warnings: list[str] = []

    # ---------- 1) 每格文件/行数/合法性 ----------
    rows_by_cell: dict[tuple[str, int], list[FourArmRow]] = {}
    manifests: dict[tuple[str, int], dict] = {}
    for m in models:
        for b in budgets:
            rows, man, iss = check_cell(result_dir, m, b, k=args.k)
            rows_by_cell[(m, b)] = rows
            manifests[(m, b)] = man
            for s in iss:
                hard_issues.append(s)
            if rows and man:
                gv = man.get("gate_verdicts", {})
                gatestr = "; ".join(f"{k.replace(m+'::','')}={v}" for k, v in gv.items()) or "(无)"
                if "INSUFFICIENT" in gatestr and all("INSUFFICIENT" == v for v in gv.values()):
                    warnings.append(f"{m}×b{b}: T3 全 INSUFFICIENT（n={len(rows)}<{config.MIN_N_FOR_GATE[2]}，样本不足不判）")
                else:
                    print(f"  T3({m}×b{b}): {gatestr}")

    # ---------- 2) 每格指标 + 逐模型敏感带 ----------
    print("\n[逐格 DiD 指标]")
    print(f"  {'模型':<14}{'预算':<6}{'n':<4}{'表观增益':<9}{'校正增益':<9}{'记忆掩盖量':<9}{'DiD':<8}")
    model_rows: dict[str, dict[str, list[FourArmRow]]] = {}
    for (m, b), rows in sorted(rows_by_cell.items()):
        if not rows:
            continue
        app, cor, mu, mask = (apparent_gain(rows), corrected_gain(rows),
                              did_mean(rows), masking_magnitude(rows))
        print(f"  {m:<14}{b:<6}{len(rows):<4}{app:+.3f}    {cor:+.3f}    {mask:+.3f}    {mu:+.3f}")
        if mu > 0:  # DiD>0 => 校正<表观，方向与假设相反
            warnings.append(f"{m}×b{b}: DiD>0（记忆掩盖量为负），与'记忆顶高闭卷地板'假设相反，请核查该格")
        model_rows.setdefault(m, {})[rows[0].config_key] = rows

    # ---------- 3) 逐模型敏感带（B1：两竞争配置校正增益 CI） ----------
    print("\n[敏感带判定（B1：比较两竞争配置的校正增益 CI，P>0.8 且 CI 分离）]")
    for m in models:
        by_cfg = model_rows.get(m, {})
        if len(by_cfg) < 2:
            warnings.append(f"{m}: 只有 {len(by_cfg)} 个配置，无法做双配置敏感带对比")
            continue
        app = {ck: apparent_gain(rs) for ck, rs in by_cfg.items()}
        cg = {ck: corrected_gain(rs) for ck, rs in by_cfg.items()}
        app_best = max(app, key=app.get); cor_best = max(cg, key=cg.get)
        # B1：P(排序改变) 用 bootstrap 重采样（与 cli.py 一致）；CI 用各配置校正增益 bootstrap
        app_rep = gain_bootstrap_replicates(by_cfg, "apparent_gain", B=2000)
        cor_rep = gain_bootstrap_replicates(by_cfg, "corrected_gain", B=2000)
        p_flip, rep_app_best, rep_cor_best = ranking_flip_probability(app_rep, cor_rep)
        ci = {ck: paired_bootstrap(by_cfg[ck], corrected_gain, B=2000)[1] for ck in by_cfg}
        verdict = judge_sensitive(p_flip, ci[rep_app_best], ci[rep_cor_best])
        print(f"  {m}: 表观最优={app_best}({app[app_best]:+.3f})  校正最优={cor_best}({cg[cor_best]:+.3f})  "
              f"P(翻转)={p_flip:.2f}  校正增益CI分离={verdict['corrected_ci_separated']}  判定={verdict['verdict']}")
        if rep_app_best == rep_cor_best:
            warnings.append(f"{m}: 表观==校正最优（该格不敏感）——负控格特征，正常")

    # ---------- 4) 退化格检查 ----------
    for (m, b), rows in rows_by_cell.items():
        if rows and all(r.a == r.c and r.b == r.d for r in rows):
            warnings.append(f"{m}×b{b}: 每题 b==d 且 a==c（表观==校正，无记忆也无效应），疑似生成器恒输出/证据缺失")

    print("\n======= check_execution 结论 =======")
    for s in hard_issues:
        print(f"  [FAIL] {s}")
    for w in warnings:
        print(f"  [WARN] {w}")
    if hard_issues:
        print(f">> {len(hard_issues)} 处硬伤 → 退出码 1")
        return 1
    print(f">> 硬伤 0；{len(warnings)} 条警告（多为样本不足/负控格/方向提示，需人工判定）→ 退出码 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
