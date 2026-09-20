"""聚焦格调度器（第四轮执行用）：4 规模 × 2 预算的受控四臂 DiD，每格出一份可复现 manifest。

用法（在论文/ 目录，即 rag_leak/ 父目录下）：
  python -m rag_leak.grid --nq data/nq-dev.json --trivia data/trivia-dev.json \
      --hotpot data/hotpot_dev_distractor_v1.json --out rag_leak/out --proposer rule

背景：
  run_pipeline 原本的 --mode=grid 只是 `return run_pilot(...)`（单配置，不循环）。
  执行规格（执行落地.md M4.1）要求真正的网格调度：规模 × 预算 = 聚焦 8 格，固定
  granularity=paragraph、k=5、rerank=False。本模块兑现这一点。
  --mode=grid 已被 run_pipeline 懒加载路由到本模块（避免循环导入）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config, manifest as mf
from .schemas import FourArmRow
from .stats.did import apparent_gain, corrected_gain, did_mean, masking_magnitude
from .run_pipeline import run_set, _config_key, _t3_verdicts, _dataset_counts
from .data.load_raw import load_dpr_file, load_hotpot_file
from .data.make_subset import deterministic_sample
from .generation.arm import ArmConfig

HERE = Path(__file__).parent

FOCUSED_MODELS = config.MODELS            # 4 本地规模
FOCUSED_BUDGETS = [1024, 4096]            # 2 预算
FOCUSED_GRANULARITY = "paragraph"         # 固定粒度
FOCUSED_K = 5
FOCUSED_RERANK = False


def default_bits(model: str) -> int:
    """4B/8B 需 Q4（8GB 卡放不下 FP16）；0.6B/1.7B 用 FP16。可被 --bits 覆盖。

    Phase C：先剥 "-Instruct" 后缀再判规模，否则 "Qwen3-8B-Instruct" 会误落 FP16→OOM。"""
    base = model[:-len("-Instruct")] if model.endswith("-Instruct") else model
    if base.endswith("4B") or base.endswith("8B"):
        return 4
    return 16


def _make_generator(backend: str, model: str, bits: int, device: str):
    if backend == "stub":
        from .generation.model import StubGenerator
        print("[warn] grid+stub 仅接线冒烟，结果勿入论文（README 禁止 grid 用 stub）。")
        return StubGenerator(set(), set(), {})
    from .generation.model import HFGenerator
    return HFGenerator(model, bits=bits, device=device)


def run_grid(questions, out_dir: Path, data_paths: dict[str, str],
             backend: str = "hf", models: list[str] | None = None,
             budgets: list[int] | None = None, granularity: str = FOCUSED_GRANULARITY,
             k: int = FOCUSED_K, rerank: bool = FOCUSED_RERANK,
             bits_override: dict[str, int] | None = None, device: str = "cuda",
             proposer=None) -> list[dict]:
    """对每一 (模型 × 预算) 格：run_set + 写 manifest；返回每格的指标摘要。"""
    models = models or list(FOCUSED_MODELS)
    budgets = budgets or list(FOCUSED_BUDGETS)
    bits_override = bits_override or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []

    for model in models:
        gen = _make_generator(backend, model, bits_override.get(model, default_bits(model)), device)
        for budget in budgets:
            acfg = ArmConfig(granularity, budget, k, rerank=rerank)
            label = f"focused_{model}_{budget}"
            res = run_set(questions, gen, model, acfg, out_dir, label, proposer=proposer)
            # R3-A：每格一份可复现 manifest（run_set 本身不写 manifest）
            m = mf.build_manifest(HERE, "grid", label, data_paths=data_paths,
                                  models=[model], config_key=_config_key(acfg),
                                  gate_verdicts=_t3_verdicts(res["t3"]),
                                  datasets=_dataset_counts(questions))
            mf.write_manifest(out_dir, label, m)
            rows: list[FourArmRow] = res["rows"]
            mu = did_mean(rows) if rows else float("nan")
            summary.append(dict(model=model, budget=budget, config_key=acfg.key, n=len(rows),
                                apparent=apparent_gain(rows) if rows else float("nan"),
                                corrected=corrected_gain(rows) if rows else float("nan"),
                                diD=mu, masking=masking_magnitude(rows) if rows else float("nan"),
                                manifest=str(out_dir / f"{label}_manifest.json")))
            print(f"  [{model} × b{budget}] n={len(rows)}  表观增益={summary[-1]['apparent']:+.3f}  "
                  f"校正增益={summary[-1]['corrected']:+.3f}  记忆掩盖量={summary[-1]['masking']:.3f}")
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="聚焦 8 格（规模×预算）受控 DiD 调度器")
    ap.add_argument("--nq", required=True)
    ap.add_argument("--trivia", required=True)
    ap.add_argument("--hotpot", required=True)
    ap.add_argument("--out", default=str(HERE / "out"))
    ap.add_argument("--backend", choices=["hf", "stub"], default="hf")
    ap.add_argument("--proposer", choices=["rule", "llm"], default="rule")
    ap.add_argument("--models", default=",".join(FOCUSED_MODELS))
    ap.add_argument("--budgets", default=",".join(str(b) for b in FOCUSED_BUDGETS))
    ap.add_argument("--granularity", default=FOCUSED_GRANULARITY, choices=config.GRANULARITIES)
    ap.add_argument("--k", type=int, default=FOCUSED_K)
    ap.add_argument("--rerank", type=int, default=0, choices=[0, 1])
    ap.add_argument("--bits", default="", help="形如 4B:4,8B:4，覆盖 default_bits；留空自动")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--pilot_n", type=int, default=config.PILOT_N)
    args = ap.parse_args(argv)

    questions = (load_dpr_file(args.nq, "nq") + load_dpr_file(args.trivia, "trivia")
                 + load_hotpot_file(args.hotpot))
    if len(questions) > args.pilot_n:
        questions = deterministic_sample(questions, args.pilot_n, seed=config.RNG_SEED)
    print(f"[grid] 抽样 {len(questions)} 题；模型={args.models}；粒度={args.granularity}；"
          f"k={args.k}；rerank={bool(args.rerank)}")

    bits_override = {}
    for tok in filter(None, args.bits.split(",")):
        if ":" in tok:
            m, b = tok.split(":", 1)
            bits_override[m.strip()] = int(b)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    budgets = [int(b) for b in args.budgets.split(",") if b.strip()]

    out_dir = Path(args.out)
    data_paths = dict(nq=args.nq, trivia=args.trivia, hotpot=args.hotpot)
    summary = run_grid(questions, out_dir, data_paths, backend=args.backend, models=models,
                       budgets=budgets, granularity=args.granularity, k=args.k,
                       rerank=bool(args.rerank), bits_override=bits_override,
                       device=args.device, proposer=None)
    print(f"\n[grid] 完成 {len(summary)} 格，manifest 见 {out_dir}/*_manifest.json。")
    print("[grid] 若要敏感带判定（RQ3），对每个模型跑：\n"
          f"  python -m rag_leak.cli --model <模型名> --results_dir {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
