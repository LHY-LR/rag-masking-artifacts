r"""B5：无替换（substitution-free）证据交换 pilot —— 检验"操纵代价"不是伪造文本的产物。

要回答的质疑
------------
主文的操纵代价 (b-d) 是**构造**出来的：把语料里的答案值换成虚构新值。审稿人可以说
"代价来自那句假话读起来怪 / 模型被自相矛盾的文本搞晕"，而不是来自参数记忆。
B5 把同一件事在**没有任何伪造文本**的条件下重做一遍：

    条件 A（证据在场）  = ora_orig：上下文只放金证据段（真实原文），对**原始答案**评分。
                          —— 已冻结在产物里（oracle_rows.em_orig），零新增计算。
    条件 B（证据缺席）  = ora_nogold（本脚本新增）：把金证据段**逐段替换成同篇文章的
                          干扰段**（真实原文，段数相同、预算相同），问题与答案口径不变。

    reliance = em_orig - em_nogold     "答案有多依赖证据"
    cost_oracle = em_orig - em_sub     （对照：同口径但把证据换成虚构新值）——也已冻结。

若 reliance 随记忆强度上升而**下降**（= cost_oracle / (b-d) 上升的镜像），则"记忆替证据
作答"这一机制在**无伪造文本**条件下复现 → (b-d) 的剂量-反应不是替换动作本身的产物。

为什么用 oracle 上下文而不是检索上下文：把"检索是否召回到金段"这个噪声源摘掉，
两条件只差**证据在不在**这一个变量。

局限（必须随结果一起报）
------------------------
无替换 ⇒ 没有"新真值" ⇒ **算不出 corrected 臂与 masking**。故 B5 只能复现**机制方向**，
不能复现决策反转。这是 pilot，不是主结果。

用法
----
    & venv\Scripts\python.exe -m rag_leak.probe_evidence_swap --dataset trivia   # 跑生成（主用）
    & venv\Scripts\python.exe -m rag_leak.probe_evidence_swap --dataset hotpot
    & venv\Scripts\python.exe -m rag_leak.probe_evidence_swap --dataset trivia --analyze-only
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .data.build_gold import build_gold
from .data.load_raw import load_dpr_file, load_hotpot_file
from .generation.model import HFGenerator
from .metrics.normalize import em_any_alias, whole_occurrence_count
from .retrieval.bm25_distractor import DistractorBM25

HERE = Path(__file__).parent
DATA = HERE.parent / "data"
# manifest 核对：out_s6_hotpot_fix_* 的 dataset_files.hotpot ==
# 46711121d250803f28a2c6b110c5eb2d3d7f25cfaf5ce82f76d31397cd5802cc，与 data/hotpot_dn.json 一致
# （不是 hotpot_dev_distractor_v1.json）。这两行是"先验证再判读"的一部分：数据文件错了，
# 下面所有 join 都会错配且悄无声息。
#
# 数据集选择：**只有 HotpotQA 能做无替换交换**（离线自检结论，2026-09-19）。
# trivia_dn 的 C 线切片每题候选池通常只有 1 段（就是金段）→ 实测 432 题里 **381 题没有任何
# 非金段落**，只有 51 题可交换。故无替换协议在 TriviaQA C 线上**不可构造**，本脚本不提供该选项
# （免得跑出一个 51 题的伪结论）。这条本身是方法学结论，值得写进论文的"构集约束"。
# HotpotQA distractor 版每题 10 段（2 金 + 8 干扰），392/393 题可交换，是本 pilot 的唯一可行域。
#
# 强度变量用 B3 的**连续** lp_old（若 out_memstrength/ 下已有对应产物则自动 join），而不是二值 a：
# HotpotQA 的 a 只有 0.051–0.056，二值剂量几乎没有变异；而且 reliance 与 a 都含"闭卷答对"成分，
# 用 a 做剂量有近乎同义反复的风险。lp_old 是连续、模型内部、且不参与任何 EM 计算的量。
DATASETS: dict[str, dict] = {
    "hotpot": dict(
        path=DATA / "hotpot_dn.json", loader="hotpot", label="hotpot", ms_group="hotpot_s6",
        runs=[("Qwen3-4B", "out_s6_hotpot_fix_4b"),
              ("Qwen3-8B", "out_s6_hotpot_fix_8b"),
              ("Qwen/Qwen3.5-4B-Base", "out_s6_hotpot_fix_q35_4b")]),
}
B = 10000
SEED = 20260903


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _find(d: Path, suffix: str) -> Path:
    hits = sorted(d.glob(f"*{suffix}"))
    if len(hits) != 1:
        raise SystemExit(f"{d} 下应有唯一 *{suffix}，实际 {[h.name for h in hits]}")
    return hits[0]


def build_swap_contexts(q) -> tuple[str, str, list[str], int]:
    """返回 (金证据上下文, 替换段上下文, 替换段 doc_id 列表, 其中"干净"段数)。

    替换规则：非金段落按与问题的 BM25 相似度排序，取**前 len(gold.passages) 段**，
    段数与金段严格相等 → 上下文规模可比，唯一变量是"这段文字是否含答案"。

    **干净性守卫（离线自检发现的缺陷）**：HotpotQA 同篇文章的干扰段经常也提到答案实体
    （首版实测 31/392 = 7.9% 的"替换"段里仍含金别名 → "证据缺席"条件被污染）。故优先取
    **不含任何金别名**（整词边界 + 数字严格，见 metrics.normalize.whole_occurrence_count）
    的候选；不足时用剩下的补齐，并把干净的段数落盘，判读时可切干净子集。
    """
    gold = build_gold(q)
    if not gold.passages:
        return "", "", [], 0
    gold_ids = {p.doc_id for p in gold.passages}
    others = [p for p in (q.paragraphs or []) if p.doc_id not in gold_ids]
    if not others:
        return "", "", [], 0
    k = len(gold.passages)
    eng = DistractorBM25(others)
    rank = {d: i for i, (d, _) in enumerate(eng.search(q.text, len(others)))}
    ranked = sorted(others, key=lambda p: rank.get(p.doc_id, 10 ** 6))

    def _dirty(p) -> bool:
        return any(whole_occurrence_count(p.text, a, numeric_strict=True) > 0
                   for a in (q.answers or []) if a)

    clean = [p for p in ranked if not _dirty(p)]
    picked = clean[:k]
    n_clean = len(picked)
    if len(picked) < k:
        picked += [p for p in ranked if _dirty(p)][:k - len(picked)]
    picked = sorted(picked, key=lambda p: rank.get(p.doc_id, 10 ** 6))
    gold_text = "\n".join(p.text for p in gold.passages)
    repl_text = "\n".join(p.text for p in picked)
    return gold_text, repl_text, [p.doc_id for p in picked], n_clean


def _load_questions(ds: dict) -> dict:
    if ds["loader"] == "dpr":
        qs = load_dpr_file(str(ds["path"]), ds["label"])
    else:
        qs = load_hotpot_file(str(ds["path"]))
    return {q.id: q for q in qs}


def run(args) -> int:
    ds = DATASETS[args.dataset]
    qs = _load_questions(ds)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    for model, dname in ds["runs"]:
        if args.models and model not in args.models.split(","):
            continue
        ref = _jsonl(_find(HERE / dname, "_oracle_rows.jsonl"))
        ids = [r["question_id"] for r in ref]
        missing = [i for i in ids if i not in qs]
        if missing:
            raise SystemExit(f"{model}: {len(missing)} 题在 {ds['path'].name} 中找不到（题集错配）")
        print(f"[B5:{args.dataset}] {model}: {len(ids)} 题（来自 {dname}）")
        gen = HFGenerator(model, bits=args.bits, device=args.device)
        rows = []
        for n, r in enumerate(ref, 1):
            q = qs[r["question_id"]]
            gold_text, repl_text, repl_ids, n_clean = build_swap_contexts(q)
            if not repl_text:
                print(f"  [skip] {q.id}: 无可用非金段落")
                continue
            raw = gen.generate(q.text, repl_text, q.answers[0], q.id, "ora_nogold")
            rows.append(dict(
                question_id=q.id, model=model, question=q.text, gold=r["gold"],
                gold_ctx_tokens=len(gen.tok(gold_text, add_special_tokens=False)["input_ids"]),
                repl_ctx_tokens=len(gen.tok(repl_text, add_special_tokens=False)["input_ids"]),
                repl_doc_ids=repl_ids, n_repl_clean=n_clean,
                n_gold_paras=len(build_gold(q).passages),
                raw_nogold=raw, em_nogold=em_any_alias(raw, q.answers),
                # 冻结参照（同口径：ora_orig 上下文 = 仅金证据段）
                em_gold=r["em_orig"], em_sub=r["em_sub"], cls_sub=r["cls_sub"]))
            if n % 50 == 0:
                print(f"  [{model}] {n}/{len(ids)}")
        p = out_dir / f"evswap_{model.replace('/', '_')}.jsonl"
        p.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n",
                     encoding="utf-8")
        print(f"[B5] {model}: {len(rows)} 题 -> {p.name}")
        del gen
    return 0


# ---------------- 判读（离线，只读） ----------------
def _ols(X, y) -> tuple[list[float], float]:
    import numpy as np
    X, y = np.asarray(X, float), np.asarray(y, float)
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return [float(v) for v in beta], (1 - ss_res / ss_tot if ss_tot else float("nan"))


def analyse(args) -> int:
    import numpy as np
    ds = DATASETS[args.dataset]
    out_dir = Path(args.out)
    ms_dir = Path(args.ms_dir)
    recs: list[dict] = []
    lp_missing: list[str] = []
    for model, dname in ds["runs"]:
        p = out_dir / f"evswap_{model.replace('/', '_')}.jsonl"
        if not p.exists():
            print(f"[B5] 缺 {p.name}，跳过")
            continue
        # 连续强度（B3 产物）：有则 join，无则该模型的 lp 相关量留空（不阻断主分析）
        ms_p = ms_dir / f"memstrength_{model.replace('/', '_')}.jsonl"
        ms = {r["question_id"]: r for r in _jsonl(ms_p)} if ms_p.exists() else {}
        if not ms:
            lp_missing.append(model)
        four = {r["question_id"]: r for r in _jsonl(_find(HERE / dname, "_fourarm.jsonl"))}
        for r in _jsonl(p):
            f = four.get(r["question_id"])
            if f is None:
                continue
            o = (ms.get(r["question_id"]) or {}).get("lp", {}).get("old") or {}
            recs.append(dict(model=model, qid=r["question_id"], a=f["a"], b=f["b"],
                             c=f["c"], d=f["d"],
                             em_gold=r["em_gold"], em_nogold=r["em_nogold"], em_sub=r["em_sub"],
                             reliance=r["em_gold"] - r["em_nogold"],      # 无替换：证据在场 - 缺席
                             cost_oracle=r["em_gold"] - r["em_sub"],      # 有替换：对照
                             masking=(f["d"] - f["c"]) - (f["b"] - f["a"]),
                             cost_retr=f["b"] - f["d"],
                             lp_old=o.get("mean_lp"),
                             contam=int(r.get("n_repl_clean", 0) < r.get("n_gold_paras", 0)),
                             tok_ratio=(r["repl_ctx_tokens"] / max(r["gold_ctx_tokens"], 1))))
    if not recs:
        raise SystemExit("没有任何 evswap 产物可判读")
    has_lp = sum(1 for r in recs if r["lp_old"] is not None)
    print(f"[B5] 判读 n={len(recs)}（{len({r['model'] for r in recs})} 模型）；"
          f"含连续强度 lp_old 的 {has_lp}/{len(recs)}")
    if lp_missing:
        print(f"[B5] 缺 B3 强度产物（lp 相关量置空）：{lp_missing}")

    def slope(rs, ykey):
        a = np.array([r["a"] for r in rs], float)
        y = np.array([r[ykey] for r in rs], float)
        if a.std() == 0 or y.std() == 0:
            return float("nan")
        return _ols([[v] for v in a], y)[0][1]

    def slope_lp(rs, ykey, ctrl_a: bool = False):
        """连续强度斜率。ctrl_a=True 时做二元回归（控制二值 a）→ 剥离"闭卷答对"这个共线成分。"""
        sub = [r for r in rs if r["lp_old"] is not None]
        if not sub:
            return float("nan")
        x = np.array([r["lp_old"] for r in sub], float)
        y = np.array([r[ykey] for r in sub], float)
        if x.std() == 0 or y.std() == 0:
            return float("nan")
        X = [[v, float(sub[i]["a"])] for i, v in enumerate(x)] if ctrl_a else [[v] for v in x]
        return _ols(X, y)[0][1]

    def boot(rs, ykey, b=None, seed=SEED, fn=None):
        """题级**聚类** bootstrap：重抽 question_id，同题的所有模型行一起进出。

        为什么必须聚类：同一道题在 3 个模型里各出现一次，按**行**重抽会把三行拆散
        （同一题被抽到 1 次或 3 次、且不保证跨模型配对），标准误被低估、CI 假性变窄。
        这与主文及 B3 的口径一致（`analyze_memstrength._boot` 同样按 question_id 聚类）。
        """
        import numpy as np
        b = B if b is None else b
        fn = fn or slope
        rng = np.random.default_rng(seed)
        by_q: dict[str, list[int]] = {}
        for i, r in enumerate(rs):
            by_q.setdefault(r["qid"], []).append(i)
        qids = sorted(by_q)
        vals = []
        for _ in range(b):
            pick = rng.integers(0, len(qids), len(qids))
            idx = [i for k in pick for i in by_q[qids[k]]]
            v = fn([rs[i] for i in idx], ykey)
            if v == v:
                vals.append(v)
        if not vals:
            return dict(point=None, lo=None, hi=None, n_ok=0)
        lo, hi = np.percentile(vals, [2.5, 97.5])
        return dict(point=round(fn(rs, ykey), 4), lo=round(float(lo), 4),
                    hi=round(float(hi), 4), n_ok=len(vals))

    res: dict = dict(n=len(recs), bootstrap_b=B, seed=SEED, per_model={},
                     pooled={}, dataset=args.dataset)
    for m in sorted({r["model"] for r in recs}):
        sub = [r for r in recs if r["model"] == m]
        res["per_model"][m] = dict(
            n=len(sub), a=round(float(np.mean([r["a"] for r in sub])), 4),
            em_gold=round(float(np.mean([r["em_gold"] for r in sub])), 4),
            em_nogold=round(float(np.mean([r["em_nogold"] for r in sub])), 4),
            reliance=round(float(np.mean([r["reliance"] for r in sub])), 4),
            cost_oracle=round(float(np.mean([r["cost_oracle"] for r in sub])), 4),
            cost_retr=round(float(np.mean([r["cost_retr"] for r in sub])), 4),
            slope_reliance_on_a=round(slope(sub, "reliance"), 4),
            slope_costoracle_on_a=round(slope(sub, "cost_oracle"), 4),
            slope_reliance_on_lp=round(slope_lp(sub, "reliance"), 4),
            slope_reliance_on_lp_ctrl_a=round(slope_lp(sub, "reliance", ctrl_a=True), 4),
            slope_costoracle_on_lp=round(slope_lp(sub, "cost_oracle"), 4),
            slope_costretr_on_lp=round(slope_lp(sub, "cost_retr"), 4))
    for k in ("reliance", "cost_oracle", "cost_retr"):
        res["pooled"][f"slope_{k}_on_a"] = boot(recs, k)
        res["pooled"][f"mean_{k}"] = round(float(np.mean([r[k] for r in recs])), 4)
    for k in ("reliance", "cost_oracle", "cost_retr"):
        res["pooled"][f"slope_{k}_on_lp"] = boot(recs, k, fn=slope_lp)
        res["pooled"][f"slope_{k}_on_lp_ctrl_a"] = boot(
            recs, k, fn=lambda rs, y: slope_lp(rs, y, ctrl_a=True))

    # 稳健性切片：①去掉"替换段仍含金别名"的污染题；②再去掉上下文规模相差过大的题。
    # 为什么必须有切片：em_nogold 是"无证据也能答对"的率，污染题会让它虚高 → reliance 被低估。
    slices = {"all": recs,
              "clean": [r for r in recs if not r["contam"]],
              "clean_size_matched": [r for r in recs if not r["contam"]
                                     and 0.5 <= r["tok_ratio"] <= 2.0]}
    res["slices"] = {}
    for name, rs in slices.items():
        if not rs:
            continue
        res["slices"][name] = dict(
            n=len(rs),
            mean_reliance=round(float(np.mean([r["reliance"] for r in rs])), 4),
            mean_em_nogold=round(float(np.mean([r["em_nogold"] for r in rs])), 4),
            slope_reliance_on_a=boot(rs, "reliance"),
            slope_cost_oracle_on_a=boot(rs, "cost_oracle"),
            slope_cost_retr_on_a=boot(rs, "cost_retr"),
            slope_reliance_on_lp=boot(rs, "reliance", fn=slope_lp),
            slope_reliance_on_lp_ctrl_a=boot(
                rs, "reliance", fn=lambda s, y: slope_lp(s, y, ctrl_a=True)),
            slope_cost_retr_on_lp=boot(rs, "cost_retr", fn=slope_lp))
    res["contamination_rate"] = round(float(np.mean([r["contam"] for r in recs])), 4)

    L = [f"# B5 判读：无替换证据交换 pilot（{args.dataset}）", "",
         f"n={len(recs)}，B={B}，seed={SEED}；reliance = em_gold − em_nogold（无伪造文本）",
         f"污染率（替换段仍含金别名的题占比）= {res['contamination_rate']:.4f}；"
         f"含连续强度 lp_old 的样本 {has_lp}/{len(recs)}", "",
         "## 逐模型（lp 列为连续强度 B3 口径）", "",
         "| 模型 | n | a | em_gold | em_nogold | reliance | cost_oracle | cost_retr | "
         "slope(reliance~a) | slope(reliance~lp) | slope(reliance~lp|a) | slope(cost_retr~lp) |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, d in res["per_model"].items():
        L.append(f"| {m} | {d['n']} | {d['a']:.4f} | {d['em_gold']:.4f} | {d['em_nogold']:.4f} | "
                 f"{d['reliance']:+.4f} | {d['cost_oracle']:+.4f} | {d['cost_retr']:+.4f} | "
                 f"{d['slope_reliance_on_a']:+.4f} | {d['slope_reliance_on_lp']:+.4f} | "
                 f"{d['slope_reliance_on_lp_ctrl_a']:+.4f} | {d['slope_costretr_on_lp']:+.4f} |")
    L += ["", "## 合并（题级 bootstrap B=%d）" % B, "",
          "| 量 | 点估计 | 95% CI |", "|---|---|---|"]
    for k in ("reliance", "cost_oracle", "cost_retr"):
        s = res["pooled"][f"slope_{k}_on_a"]
        L.append(f"| slope({k} ~ a) | {s['point']:+.4f} | [{s['lo']:+.4f}, {s['hi']:+.4f}] |")
    for k in ("reliance", "cost_oracle", "cost_retr"):
        s = res["pooled"][f"slope_{k}_on_lp"]
        s2 = res["pooled"][f"slope_{k}_on_lp_ctrl_a"]
        L.append(f"| slope({k} ~ lp_old) | {s['point']:+.4f} | [{s['lo']:+.4f}, {s['hi']:+.4f}] |")
        L.append(f"| slope({k} ~ lp_old \\| a) | {s2['point']:+.4f} | "
                 f"[{s2['lo']:+.4f}, {s2['hi']:+.4f}] |")
    L += ["", "## 稳健性切片（题级 bootstrap）", "",
          "| 切片 | n | mean(reliance) | mean(em_nogold) | slope(reliance~lp) | slope(cost_retr~lp) |",
          "|---|---|---|---|---|---|"]
    for name, d in res["slices"].items():
        a = d["slope_reliance_on_lp"]
        c = d["slope_cost_retr_on_lp"]
        L.append(f"| {name} | {d['n']} | {d['mean_reliance']:+.4f} | {d['mean_em_nogold']:.4f} | "
                 f"{a['point']:+.4f} [{a['lo']:+.4f}, {a['hi']:+.4f}] | "
                 f"{c['point']:+.4f} [{c['lo']:+.4f}, {c['hi']:+.4f}] |")
    L += ["", "读法：reliance 斜率显著为负 = 记忆越强、答案越不依赖证据（无伪造文本复现机制方向）；",
          "cost_oracle / cost_retr 斜率显著为正 = 替换造成的代价随记忆增强（与主文 tab:strength 同向）。",
          "", "**局限**：无替换 ⇒ 无 corrected 臂 ⇒ 本 pilot 不能复现 masking / 决策反转，只复现机制方向。"]
    md = "\n".join(L)
    # 产物写在 --out 目录内，**不写回 rag_leak/ 根**。
    # 为什么（2026-09-19 自查踩到的污染事故）：初版把分析结果写到 `HERE/out_evswap_analysis_*.json`，
    # 于是**用合成数据做接线自检**时，把"看起来像真实 B5 结果"的文件写进了产物目录
    # （其中的 a/b/c/d 与 em_gold 是真的、em_nogold/lp_old 是造的，最容易误读）。已删并改到此。
    out_p = Path(args.out)
    out_p.mkdir(parents=True, exist_ok=True)
    (out_p / "evswap_analysis.json").write_text(json.dumps(res, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
    (out_p / "evswap_analysis.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"[B5] -> {out_p / 'evswap_analysis.json'}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B5 无替换证据交换 pilot")
    ap.add_argument("--dataset", default="trivia", choices=sorted(DATASETS),
                    help="trivia=C 线 5 模型（a 变异大，主用）；hotpot=3 模型（pilot）")
    ap.add_argument("--out", default="", help="产物目录；空=out_evswap_<dataset>")
    ap.add_argument("--ms-dir", default="",
                    help="B3 连续强度产物目录；空=out_memstrength/<dataset>（缺则 lp 量置空）")
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4])
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--models", default="", help="逗号分隔的模型子集；空=全部")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args(argv)
    if not args.out:
        args.out = str(HERE / f"out_evswap_{args.dataset}")
    if not args.ms_dir:
        args.ms_dir = str(HERE / "out_memstrength" / DATASETS[args.dataset]["ms_group"])
    if args.analyze_only:
        return analyse(args)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
