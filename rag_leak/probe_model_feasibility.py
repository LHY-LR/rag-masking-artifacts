"""当前世代模型可行性探测（需联网下载 + 短暂 GPU，交执行方跑）。

为什么先跑这个：第 3 项"加当前世代模型"要花一晚 GPU。若某型号在 8GB 上装不下、
或经现有 HFGenerator 管线跑不出干净答案，那一晚就白费。本探针**只做三件事**，
对每个型号逐个体检，产出"可跑清单"，再据以免跑全量：

  1. 下载/解析：`AutoConfig` + tokenizer 能否离线前拉取到（记录模型实际大小）；
  2. 装得下吗：Q4 加载 → 报告峰值显存（8GB 卡上限）；
  3. 跑得通吗：用**替换后的金证据**做一次最短生成，报告原文 + 是否命中新 key。

**只读**：不写任何既有 run 目录、不改 config、不下载到仓库外的地方以外。

用法（在 论文/ 目录执行；探测阶段需 **联网**，故先关 OFFLINE 变量）：
  python -m rag_leak.probe_model_feasibility \
      --models "Qwen/Qwen3.5-0.8B,Qwen/Qwen3.5-4B,google/gemma-4-E4B-it" \
      --bits 4 --out rag_leak/out_model_feasibility.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from . import config
from .data.build_gold import build_gold
from .data.load_raw import load_dpr_file

# 探测用的题（取一题 date，替换后的金证据会直给模型）
_PROBE_QID = "trivia-126"


def _vram_report(device: str) -> dict:
    try:
        import torch
        if not torch.cuda.is_available():
            return {"cuda": False}
        props = torch.cuda.get_device_properties(0)
        return {"cuda": True, "name": props.name,
                "total_gb": round(props.total_memory / 1024 ** 3, 2),
                "allocated_gb": round(torch.cuda.memory_allocated() / 1024 ** 3, 3),
                "peak_gb": round(torch.cuda.max_memory_allocated() / 1024 ** 3, 3)}
    except Exception as exc:  # noqa: BLE001
        return {"cuda": "error", "detail": str(exc)}


def probe_one(model_id: str, bits: int, device: str, subs_path: str, trivia: str) -> dict:
    """对一个型号做三级体检；任何一级失败都如实记录，不抛出。"""
    rec: dict = {"model_id": model_id, "bits": bits}

    # ---- 1. 解析 config / tokenizer
    t0 = time.time()
    try:
        from transformers import AutoConfig, AutoTokenizer
        cfg = AutoConfig.from_pretrained(model_id)
        AutoTokenizer.from_pretrained(model_id)
        rec["resolve"] = "ok"
        rec["model_type"] = getattr(cfg, "model_type", "?")
        rec["num_params_b"] = round(
            (getattr(cfg, "num_hidden_layers", 0) or 0) / 1e9, 4)  # 占位，真实规模看权重
        rec["resolve_sec"] = round(time.time() - t0, 1)
    except Exception as exc:  # noqa: BLE001
        rec["resolve"] = "fail"
        rec["resolve_error"] = f"{type(exc).__name__}: {exc}"[:400]
        return rec

    # 若该型号有 Instruct 变体，提示是否需要 chat 模板（HFGenerator 会自动判 -Instruct）
    rec["looks_instruct"] = any(k in model_id.lower() for k in ("instruct", "-it", "chat"))

    # ---- 2. Q4 加载 + 显存
    gen = None
    t0 = time.time()
    try:
        from .run_pipeline import build_generator
        # build_generator 需要 config 里登记的短名；探测阶段直接用 HFGenerator
        from .generation.model import HFGenerator
        gen = HFGenerator(model_id, bits=bits, device=device)
        rec["load"] = "ok"
        rec["load_sec"] = round(time.time() - t0, 1)
        rec["vram_after_load"] = _vram_report(device)
    except Exception as exc:  # noqa: BLE001
        rec["load"] = "fail"
        rec["load_error"] = f"{type(exc).__name__}: {exc}"[:400]
        return rec

    # ---- 3. 最短生成冒烟：用替换后的金证据直给
    try:
        import json as _json
        rows = [_json.loads(l) for l in Path(subs_path).read_text(encoding="utf-8").splitlines() if l.strip()]
        sub = next(r for r in rows if r["question_id"] == _PROBE_QID)
        q = next(q for q in load_dpr_file(trivia, "trivia") if q.id == _PROBE_QID)
        gold = build_gold(q)
        ctx = sub["new_passage"]
        new_surface = sub.get("terminal_key") or sub.get("new_key") or ""
        t0 = time.time()
        raw = gen.generate(q.text, ctx, target_surface=new_surface,
                           question_id=_PROBE_QID, arm="probe")
        rec["smoke"] = "ok"
        rec["smoke_sec"] = round(time.time() - t0, 1)
        rec["smoke_question"] = q.text
        rec["smoke_new_key"] = new_surface
        rec["smoke_raw"] = (raw or "")[:300]
        from .metrics.normalize import em_any_alias
        rec["smoke_em"] = em_any_alias(raw, [new_surface] if new_surface else [])
        rec["vram_peak"] = _vram_report(device)
    except Exception as exc:  # noqa: BLE001
        rec["smoke"] = "fail"
        rec["smoke_error"] = f"{type(exc).__name__}: {exc}"[:400]
        rec["traceback_tail"] = traceback.format_exc().splitlines()[-3:]
    finally:
        try:
            del gen
            import torch
            torch.cuda.empty_cache()
        except Exception:  # noqa: BLE001
            pass
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="当前世代模型可行性探测（只读，需联网）")
    ap.add_argument("--models", required=True, help="逗号分隔的 HF 型号名")
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--subs", default="rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl",
                    help="提供替换后金证据的受控子集")
    ap.add_argument("--trivia", default="data/trivia_dn.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    ids = [m.strip() for m in args.models.split(",") if m.strip()]
    print(f"[probe] 候选 {len(ids)} 个：{ids}")
    print(f"[probe] GPU 现状：{_vram_report(args.device)}")

    out = {"protocol": "model-feasibility-probe-v1",
           "note": "只做体检：解析 / Q4 装得下 / 最短生成跑得通。不跑全量、不改任何既有产物。",
           "bits": args.bits, "device": args.device,
           "probe_question": _PROBE_QID, "gpu_before": _vram_report(args.device),
           "results": []}
    for mid in ids:
        print(f"\n===== 探测 {mid} =====")
        rec = probe_one(mid, args.bits, args.device, args.subs, args.trivia)
        out["results"].append(rec)
        # 逐项打印，便于执行方原样回传
        for k in ("resolve", "load", "smoke", "smoke_em", "smoke_sec", "vram_peak",
                  "resolve_error", "load_error", "smoke_error"):
            if k in rec:
                print(f"  {k:14s} = {rec[k]}")

    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    ok = [r["model_id"] for r in out["results"] if r.get("smoke") == "ok"]
    print(f"\n[结论] 可跑清单（冒烟通过）：{ok if ok else '无'}")
    print(f"已写：{args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
