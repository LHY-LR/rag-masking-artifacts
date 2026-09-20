r"""决策翻转（argmax flip）的可复现重算 —— §5.3 / 账本 A1′ 的取数脚本。

背景（为什么必须补这个脚本）
----------------------------
A1′（"决策反转"）已写进论文 §5.3 与账本，但**此前没有任何脚本或产物**能复现它——
数字只存在于散文里。这违反本项目"先验证再判读、headline 数字必须能从产物重算"的纪律。
本脚本把当时的算法固化下来，并把口径歧义处**显式写出**（不偷偷选一个）。

口径（按账本原文）
------------------
1. 决策空间三选一：
   - `cline5`  ：C 线 5 模型（`out_s6_trivia_fix_*`，bud=1024，**k=5**）。
                 （账本表里写的是"k=1"，但产物的 config_key 是 k=5 —— 账本该格标注有误，已在 §9.9 更正。）
   - `bline6`  ：B 线 6 模型，每模型取"更好的 k"（表观按表观最大、校正按校正最大）。
   - `bline12` ：B 线 6 模型 × k∈{1,5} 共 12 配置。
2. 逐配置**独立**重采样题（账本原文："逐配置独立重采样"）。同一配置的那一次重采样同时用于
   表观与校正（否则同一次复制里两个 argmax 不可比）。
   同时给出**配对**（同题集跨配置）变体作为稳健性——预注册规则（config.py `decision_rule`）
   并未指明独立/配对，故两种都报，不事后挑一个。
3. P(flip) = P(表观 argmax ≠ 校正 argmax)；B=10000，seed=20260903。
4. 随机流**按配置名派生**（不用全局流）：避免"表顺序影响结果"这类事故（本轮已在 TOST 上踩过）。

不变量（先验证再判读）
----------------------
闭卷臂 a 与 k 无关 ⇒ 同一模型 k=1 与 k=5 的 `a` 必须**逐题相同**；脚本会断言，失败即中止。
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

CLINE5 = [("Qwen3-0.6B", "out_s6_trivia_fix_06b"),
          ("Qwen3-1.7B", "out_s6_trivia_fix_17b"),
          ("Qwen3-4B", "out_s6_trivia_fix_4b"),
          ("Qwen3-4B-Instruct", "out_s6_trivia_fix_4bi"),
          ("Qwen3-8B", "out_s6_trivia_fix_8b")]
BLINE6_K1 = [("Qwen3-0.6B", "out_b8_fix_k1_06b"), ("Qwen3-1.7B", "out_b8_fix_k1_17b"),
             ("Qwen3-4B", "out_b8_fix_k1_4b"), ("Qwen3-4B-Instruct", "out_b8_fix_k1_4bi"),
             ("Qwen3-8B", "out_b8_fix_k1"), ("Qwen3.5-4B-Base", "out_b8_fix_k1_q35")]
BLINE6_K5 = [("Qwen3-0.6B", "out_b8_fix_k5_06b"), ("Qwen3-1.7B", "out_b8_fix_k5_17b"),
             ("Qwen3-4B", "out_b8_fix_k5_4b"), ("Qwen3-4B-Instruct", "out_b8_fix_k5_4bi"),
             ("Qwen3-8B", "out_b8_fix_k5"), ("Qwen3.5-4B-Base", "out_b8_fix_k5_q35")]

SPACES = {
    "cline5": [(m, d, 0) for m, d in CLINE5],
    "bline6": [(m, d1, 1) for (m, d1), (_, d5) in zip(BLINE6_K1, BLINE6_K5)],
    "bline12": [(m, d1, 1) for m, d1 in BLINE6_K1] + [(m, d5, 5) for m, d5 in BLINE6_K5],
}


def _seed_int(tag: str) -> int:
    """把配置名派生成确定性整数种子（不用内建 hash()——它跨进程随机化）。"""
    return int.from_bytes(hashlib.sha256(f"{SEED}|{tag}".encode()).digest()[:8], "big")


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def load_space(name: str) -> tuple[list[dict], list[str]]:
    """返回 (configs, qids)；configs 每项含 label/model/k/四臂逐题数组。"""
    configs = []
    ref_qids = None
    seen_a: dict[str, list[int]] = {}
    for model, dname, k in SPACES[name]:
        d = HERE / dname
        hits = sorted(d.glob("*_fourarm.jsonl"))
        if len(hits) != 1:
            raise SystemExit(f"{d} 下应有唯一 *_fourarm.jsonl")
        rows = {r["question_id"]: r for r in _jsonl(hits[0])}
        qids = sorted(rows)
        if ref_qids is None:
            ref_qids = qids
        elif qids != ref_qids:
            raise SystemExit(f"{dname} 题集与参照不一致（缺 {len(set(ref_qids) - set(qids))} 题）")
        a = [rows[q]["a"] for q in qids]
        # 不变量：闭卷臂与 k 无关 ⇒ 同模型跨 k 的 a 必须逐题相同（失败即中止，别带着坏前提往下算）
        if model in seen_a and seen_a[model] != a:
            n_diff = sum(1 for x, y in zip(seen_a[model], a) if x != y)
            raise SystemExit(f"不变量失败：{model} 的闭卷 a 在不同 k 之间逐题不同（{n_diff} 题）")
        seen_a[model] = a
        configs.append(dict(
            label=f"{model} k={k}" if name == "bline12" else model,
            model=model, k=k, dir=dname,
            a=a, b=[rows[q]["b"] for q in qids],
            c=[rows[q]["c"] for q in qids], d=[rows[q]["d"] for q in qids]))
    return configs, ref_qids


def run_space(name: str, b: int) -> dict:
    import numpy as np
    configs, qids = load_space(name)
    n = len(qids)
    # 逐配置独立随机流（按配置名派生）
    rngs = [np.random.default_rng(_seed_int(f"{name}|{c['dir']}")) for c in configs]
    rng_paired = np.random.default_rng(_seed_int(f"{name}|paired"))

    A = [np.array(c["a"], float) for c in configs]
    Bb = [np.array(c["b"], float) for c in configs]
    C = [np.array(c["c"], float) for c in configs]
    D = [np.array(c["d"], float) for c in configs]

    def point():
        app = [float((Bb[i] - A[i]).mean()) for i in range(len(configs))]
        cor = [float((D[i] - C[i]).mean()) for i in range(len(configs))]
        return app, cor

    app0, cor0 = point()
    ia, ic = int(np.argmax(app0)), int(np.argmax(cor0))

    def flip_rate(paired: bool) -> tuple[float, int]:
        flips = 0
        ties = 0
        idx_paired = None
        for _ in range(b):
            if paired:
                idx_paired = rng_paired.integers(0, n, n)
            app, cor = [], []
            for i in range(len(configs)):
                idx = idx_paired if paired else rngs[i].integers(0, n, n)
                app.append(float((Bb[i] - A[i])[idx].mean()))
                cor.append(float((D[i] - C[i])[idx].mean()))
            ma, mc = max(app), max(cor)
            wa = [i for i, v in enumerate(app) if v == ma]
            wc = [i for i, v in enumerate(cor) if v == mc]
            if len(wa) > 1 or len(wc) > 1:
                ties += 1
            if wa[0] != wc[0]:
                flips += 1
        return flips / b, ties

    p_ind, ties_ind = flip_rate(False)
    p_pair, ties_pair = flip_rate(True)

    a_vec = np.array([float(A[i].mean()) for i in range(len(configs))])
    app_v = np.array(app0)
    cor_v = np.array(cor0)
    res = dict(
        space=name, n_items=n, k_configs=len(configs), bootstrap=b, seed=SEED,
        configs=[dict(label=c["label"], dir=c["dir"], k=c["k"],
                      a=round(float(A[i].mean()), 4),
                      apparent=round(app0[i], 4), corrected=round(cor0[i], 4),
                      masking=round(cor0[i] - app0[i], 4)) for i, c in enumerate(configs)],
        argmax_apparent=configs[ia]["label"], argmax_corrected=configs[ic]["label"],
        p_flip_independent=round(p_ind, 4), p_flip_paired=round(p_pair, 4),
        ties_independent=ties_ind, ties_paired=ties_pair,
        r_apparent_a=round(float(np.corrcoef(app_v, a_vec)[0, 1]), 4),
        r_corrected_a=round(float(np.corrcoef(cor_v, a_vec)[0, 1]), 4),
        note="独立=逐配置各自重采样（账本口径）；配对=同题集跨配置。预注册规则未指明，两者并报。")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="决策翻转重算")
    ap.add_argument("--spaces", default="cline5,bline6,bline12")
    ap.add_argument("--boot", type=int, default=B)
    ap.add_argument("--out", default=str(HERE / "out_flip_decision.json"))
    args = ap.parse_args(argv)
    out = dict(bootstrap=args.boot, seed=SEED, spaces={})
    for s in [x.strip() for x in args.spaces.split(",") if x.strip()]:
        r = run_space(s, args.boot)
        out["spaces"][s] = r
        print(f"\n### {s}  (n={r['n_items']}, {r['k_configs']} 配置, B={r['bootstrap']})")
        for c in r["configs"]:
            print(f"   {c['label']:<22} a={c['a']:.3f} 表观={c['apparent']:+.4f} "
                  f"校正={c['corrected']:+.4f} masking={c['masking']:+.4f}")
        print(f"   表观 argmax = {r['argmax_apparent']}   校正 argmax = {r['argmax_corrected']}")
        print(f"   **P(flip) 独立重采样 = {r['p_flip_independent']:.4f}**"
              f"（并列 {r['ties_independent']}） | 配对变体 = {r['p_flip_paired']:.4f}"
              f"（并列 {r['ties_paired']}）")
        print(f"   r(表观, a) = {r['r_apparent_a']:+.4f}   r(校正, a) = {r['r_corrected_a']:+.4f}")
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
