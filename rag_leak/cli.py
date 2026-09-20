"""§6 CLI 诊断工具：输入(模型,配置) → 输出(校正后建议, 是否落敏感带)。

用法：
  python -m rag_leak.cli --model stub(qwen-sim) --results_dir rag_leak/out
  python -m rag_leak.cli --model Qwen3-8B --granularity paragraph --budget 4096 \
      --k 5 --rerank 0 --results_dir out/
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
from .stats.did import apparent_gain, corrected_gain, paired_bootstrap, did_mean
from .stats.decision import (gain_bootstrap_replicates, ranking_flip_probability,
                             judge_sensitive)


def load_rows(results_dir: Path) -> list[FourArmRow]:
    rows = []
    for f in results_dir.glob("*fourarm.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            rows.append(FourArmRow(d["question_id"], d["model"], d["config_key"],
                                   int(d["a"]), int(d["b"]), int(d["c"]), int(d["d"]),
                                   bool(d.get("passed_gates", True))))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--granularity", default=None)
    ap.add_argument("--budget", type=int, default=None)
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--rerank", type=int, default=None)
    ap.add_argument("--results_dir", required=True)
    args = ap.parse_args(argv)

    rows = [r for r in load_rows(Path(args.results_dir)) if r.model == args.model]
    if not rows:
        print(f"未找到模型 {args.model} 的四臂记录")
        return 1

    by_cfg: dict[str, list[FourArmRow]] = {}
    for r in rows:
        by_cfg.setdefault(r.config_key, []).append(r)

    print(f"模型={args.model}  配置数={len(by_cfg)}  题数={len(rows)}")
    cfg_summary = {}
    for ck, rs in sorted(by_cfg.items()):
        mu, (lo, hi), _ = paired_bootstrap(rs, did_mean, B=2000)
        # B1：决策比较对象 = 各配置【校正增益】CI（非 DiD CI）
        cg, (clo, chi), _ = paired_bootstrap(rs, corrected_gain, B=2000)
        cfg_summary[ck] = dict(apparent=apparent_gain(rs), corrected=cg,
                               did=mu, did_ci=(lo, hi), corrected_ci=(clo, chi))
        print(f"  [{ck}] n={len(rs)}  表观增益={cfg_summary[ck]['apparent']:+.3f}  "
              f"校正增益={cg:+.3f}(CI[{clo:+.3f},{chi:+.3f}])  "
              f"记忆掩盖量={-mu:.3f} DiD_CI=[{lo:+.3f},{hi:+.3f}]")

    if len(by_cfg) >= 2:
        app = gain_bootstrap_replicates(by_cfg, "apparent_gain", B=2000)
        cor = gain_bootstrap_replicates(by_cfg, "corrected_gain", B=2000)
        p_flip, app_best, cor_best = ranking_flip_probability(app, cor)
        # B1：两个竞争配置各自的【校正增益】CI
        ci_app_best = cfg_summary[app_best]["corrected_ci"]
        ci_cor_best = cfg_summary[cor_best]["corrected_ci"]
        verdict = judge_sensitive(p_flip, ci_app_best, ci_cor_best)
        print(f"  表观最优={app_best}  校正后最优={cor_best}")
        print(f"  P(排序改变)={p_flip:.3f}  两配置校正增益CI分离={verdict['corrected_ci_separated']}  "
              f"判定={verdict['verdict']}")
        print(f"  决策口径(B1)：{config.DECISION_RULE}")
    else:
        print("  仅 1 个配置：输出单点校正前后增益；敏感带判定需 ≥2 配置对比。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
