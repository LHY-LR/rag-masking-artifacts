"""R3-A 可复现性 manifest：冻结快照 + 输入哈希 + 代码指纹 + 版本化 / 发布后再污染声明。

研究方案 §3.1（语料/分词器冻结并记录）、§5.3（受控子集版本化 + '发布后再污染'声明）、
§9（版本化）都要求把"这份结果是拿什么配置、什么数据、什么代码跑出来的"落成不可篡改的记录。
本模块在 run_pipeline 每个 label 产出 <label>_manifest.json，供审计 / 复现 / 跨版本比对。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def file_sha256(path: str | Path) -> str:
    """输入数据文件的 SHA-256（内容寻址，记录数据集版本）。"""
    p = Path(path)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def code_sha(package_root: str | Path, exclude: frozenset[str] | None = None) -> str:
    """代码指纹：对包内全部 .py 源码做 SHA-256（保证"哪版代码产出这结果"可追溯）。"""
    root = Path(package_root)
    exclude = exclude or frozenset()
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        if p.name in exclude:
            continue
        h.update(str(p.name).encode("utf-8"))
        h.update(p.read_bytes())
    return h.hexdigest()


def _config_snapshot() -> dict:
    """把关键冻结常量显式快照（不盲扫模块，只取实验相关项）。"""
    gates = {k: dict(v) for k, v in config.GATES.items()}
    return dict(
        models=config.MODELS, model_32b=config.MODEL_32B, hf_model_ids=config.HF_MODEL_IDS,
        tokenizer_id=config.TOKENIZER_ID, decode=config.DECODE,
        prompt_template=config.PROMPT_TEMPLATE, prompt_template_noctx=config.PROMPT_TEMPLATE_NOCTX,
        granularities=config.GRANULARITIES, token_block=config.TOKEN_BLOCK,
        budgets=config.BUDGETS, top_k=config.TOP_K, extra_top_k=config.EXTRA_TOP_K,
        gold_recall_k=config.GOLD_RECALL_K, pilot_n=config.PILOT_N, subset_n=config.SUBSET_N,
        mini_n=config.MINI_N, gates=gates, gate_verdict=config.GATE_VERDICT,
        min_n_for_gate=config.MIN_N_FOR_GATE, rng_seed=config.RNG_SEED, bootstrap_b=config.BOOTSTRAP_B,
        effect_deltas=config.EFFECT_DELTAS, power=config.POWER, alpha=config.ALPHA,
        decision_p_flip=config.DECISION_P_FLIP, ci_levels=list(config.CI_LEVELS),
        decision_rule=config.DECISION_RULE, open_index_name=config.OPEN_INDEX_NAME,
        bm25_k1=config.BM25_K1, bm25_b=config.BM25_B,
    )


def build_manifest(package_root: str | Path, mode: str, label: str,
                   data_paths: dict[str, str], models: list[str],
                   config_key: str, gate_verdicts: dict[str, dict[str, str]] | None = None,
                   datasets: list[complex] | None = None) -> dict:
    """构建一次性 manifest（不写盘）。datasets 可选：记录覆盖的数据集与题数。"""
    return dict(
        schema_version="0.3",
        mode=mode, label=label, created_at=datetime.now(timezone.utc).isoformat(),
        config_snapshot=_config_snapshot(),
        dataset_files={name: file_sha256(p) for name, p in data_paths.items()},
        pipeline=dict(code_sha=code_sha(package_root), package="rag_leak"),
        run=dict(models=models, config_key=config_key, datasets=datasets),
        gate_verdicts=gate_verdicts or {},
        # 方案 §5.3 的"发布后再污染"声明 + 版本化
        provenance_note=(
            "受控子集版本化：本 manifest 唯一标识一次运行（输入数据 SHA-256 + 代码指纹 + 冻结配置快照）。"
            "任何改动数据/配置/代码都会改变 code_sha 或 file_sha256，从而与本次运行区分。"
            "发布后再污染：公开受控子集后，应固定本 manifest 作为该子集的发布版本，"
            "并声明从该版本起不再改动其构成（否则视为新版本）。"),
    )


def write_manifest(out_dir: str | Path, label: str, manifest: dict) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"{label}_manifest.json"
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return p
