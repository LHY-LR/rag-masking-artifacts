# -*- coding: utf-8 -*-
"""offline_review_round2.py —— 一次性跑完三件离线分析（零 GPU，全部只读产物）。

目的（对应主控自评 R1/R2 与外部评审的②③④）：
  1. **v2 语料上的清洗消融，覆盖全部模型**：
     用审计点出的缺陷 ID（人审 22 条 / 模型标记 43 条）从 v2 里剔除，看结论动不动。
     → 回答"主结果建立在有残留缺陷的语料上"。
  2. **题级条件分析**：把题按闭卷 `a` 分成 a=1 / a=0，分别算 masking。
     → 直接检验"效应只出现在模型本来就会的题上"，不依赖跨世代模型对。
  3. **模型选择翻转 + P(flip)**：C 线 5 模型，按表观增益选 vs 按校正增益选，
     配对 bootstrap 求 argmax 翻转概率。
     → 换掉"12/12 为正"这个构造性近同义反复的头条。

产物：rag_leak/out_review_round2.json
"""
import json
import os
import random
from pathlib import Path

R = Path(os.path.dirname(os.path.abspath(__file__)))
B = 10000
SEED = 20260903

CLINE = [("Qwen3-0.6B", "out_s6_trivia_fix_06b", "pilot_Qwen3-0.6B_"),
         ("Qwen3-1.7B", "out_s6_trivia_fix_17b", "pilot_Qwen3-1.7B_"),
         ("Qwen3-4B", "out_s6_trivia_fix_4b", "pilot_Qwen3-4B_"),
         ("Qwen3-4B-Instruct", "out_s6_trivia_fix_4bi", "pilot_Qwen3-4B-Instruct_"),
         ("Qwen3-8B", "out_s6_trivia_fix_8b", "pilot_Qwen3-8B_")]
BLINE = [("Qwen3-0.6B", "_06b", "pilot_Qwen3-0.6B_"),
         ("Qwen3-1.7B", "_17b", "pilot_Qwen3-1.7B_"),
         ("Qwen3-4B", "_4b", "pilot_Qwen3-4B_"),
         ("Qwen3-4B-Instruct", "_4bi", "pilot_Qwen3-4B-Instruct_"),
         ("Qwen3-8B", "", "pilot_Qwen3-8B_"),
         ("Qwen3.5-4B-Base", "_q35", "pilot_Qwen_Qwen3.5-4B-Base_")]
HOTPOT = [("Qwen3-8B", "out_s6_hotpot_fix_8b", "pilot_Qwen3-8B_"),
          ("Qwen3-4B", "out_s6_hotpot_fix_4b", "pilot_Qwen3-4B_"),
          ("Qwen3.5-4B-Base", "out_s6_hotpot_fix_q35_4b", "pilot_Qwen_Qwen3.5-4B-Base_")]


def fourarm(d, nf):
    p = R / d / (nf + "fourarm.jsonl")
    out = {}
    with open(p, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                j = json.loads(line)
                out[j["question_id"]] = j
    return out


def ci(v, a=0.05):
    s = sorted(v)
    n = len(s)
    return s[int(a / 2 * n)], s[min(n - 1, int((1 - a / 2) * n))]


def boot_stat(keys, fn, rng, B=B):
    n = len(keys)
    return [fn([keys[rng.randrange(n)] for _ in range(n)]) for _ in range(B)]


def masking_of(rows, keys):
    m = 0.0
    for k in keys:
        r = rows[k]
        m += (r["a"] - r["c"]) - (r["b"] - r["d"])
    return m / len(keys)


def apparent_of(rows, keys):
    return sum(rows[k]["b"] - rows[k]["a"] for k in keys) / len(keys)


def corrected_of(rows, keys):
    return sum(rows[k]["d"] - rows[k]["c"] for k in keys) / len(keys)


# ---------------- 缺陷 ID ----------------
d90 = json.loads((R / "anno_defects_90.json").read_text(encoding="utf-8"))
human_ids = {it["task_id"] for it in d90["defects"]}
model_ids = set(json.loads((R / "anno_defects_full_model.json").read_text(encoding="utf-8"))["exclude_ids"])
print("缺陷 ID：人审 %d 条，模型标记 %d 条，并集 %d 条"
      % (len(human_ids), len(model_ids), len(human_ids | model_ids)))
both_ids = human_ids | model_ids

res = {"human_ids": sorted(human_ids), "model_ids": sorted(model_ids), "B": B}
rng = random.Random(SEED)

# ================= 1. v2 清洗消融（全模型） =================
print()
print("=" * 96)
print("1) v2 语料上的清洗消融（剔除审计点名的题），全模型")
print("=" * 96)
print("%-24s %-6s %6s %10s %10s %10s %s" % ("model", "k", "n", "masking", "剔后", "Δ", "结论变了吗"))
print("-" * 96)
res["cleaning"] = {}
runs = [("C:" + n, d, nf, None) for n, d, nf in CLINE] + \
       [("B:" + n, "out_b8_fix_k%d%s" % (k, s), nf, k) for n, s, nf in BLINE for k in (1, 5)] + \
       [("H:" + n, d, nf, None) for n, d, nf in HOTPOT]
for tag, d, nf, k in runs:
    try:
        rows = fourarm(d, nf)
    except FileNotFoundError:
        print("%-24s  缺产物，跳过" % tag)
        continue
    ks = sorted(rows)
    keep = [q for q in ks if q not in both_ids]
    m_all, m_cln = masking_of(rows, ks), masking_of(rows, keep)
    lo, hi = ci(boot_stat(ks, lambda s: masking_of(rows, s), rng, 2000))
    lo2, hi2 = ci(boot_stat(keep, lambda s: masking_of(rows, s), rng, 2000))
    sig_all = (lo > 0 or hi < 0)
    sig_cln = (lo2 > 0 or hi2 < 0)
    flag = "不变" if sig_all == sig_cln else "**显著性变了**"
    if (m_all > 0) != (m_cln > 0):
        flag = "**符号变了**"
    res["cleaning"][tag + ("_k%d" % k if k else "")] = dict(
        n=len(ks), removed=len(ks) - len(keep), masking=m_all, masking_clean=m_cln,
        ci=[lo, hi], ci_clean=[lo2, hi2], sig=sig_all, sig_clean=sig_cln)
    print("%-24s %-6s %6d %+10.4f %+10.4f %+10.4f %s"
          % (tag, k if k else "-", len(ks), m_all, m_cln, m_cln - m_all, flag))

# ================= 2. 题级条件分析 =================
print()
print("=" * 96)
print("2) 题级条件分析：masking 只在『模型本来就会』的题上出现吗？")
print("=" * 96)
print("%-26s %6s %10s %8s %10s | %6s %10s" % ("model", "a=1,n", "masking", "a=0,n", "masking", "差", "结论"))
print("-" * 96)
res["conditional"] = {}
for tag, d, nf, k in runs:
    try:
        rows = fourarm(d, nf)
    except FileNotFoundError:
        continue
    ks = sorted(rows)
    k1 = [q for q in ks if rows[q]["a"] == 1]
    k0 = [q for q in ks if rows[q]["a"] == 0]
    if not k1 or not k0:
        continue
    m1, m0 = masking_of(rows, k1), masking_of(rows, k0)
    key = tag + ("_k%d" % k if k else "")
    res["conditional"][key] = dict(n_a1=len(k1), n_a0=len(k0), masking_a1=m1, masking_a0=m0)
    print("%-26s %6d %+10.4f %8d %+10.4f | %+6.4f  %s"
          % (tag, len(k1), m1, len(k0), m0, m1 - m0,
             "a=1 明显更大" if m1 - m0 > 0.05 else ("相差不大" if abs(m1 - m0) <= 0.05 else "a=0 更大")))

# ================= 3. 模型选择翻转 + P(flip) =================
print()
print("=" * 96)
print("3) C 线：按表观增益选模型 vs 按校正增益选模型（全样本，无分层）")
print("=" * 96)
cline_rows = {}
for n, d, nf in CLINE:
    cline_rows[n] = fourarm(d, nf)
common = sorted(set.intersection(*[set(r) for r in cline_rows.values()]))
print("共同题数 =", len(common))
app = {n: apparent_of(cline_rows[n], common) for n, _ in [(x[0], 0) for x in CLINE]}
cor = {n: corrected_of(cline_rows[n], common) for n, _ in [(x[0], 0) for x in CLINE]}
ma, mc = max(app, key=app.get), max(cor, key=cor.get)
print("  表观增益排序:", " > ".join("%s %.3f" % (n, app[n]) for n in sorted(app, key=app.get, reverse=True)))
print("  校正增益排序:", " > ".join("%s %.3f" % (n, cor[n]) for n in sorted(cor, key=cor.get, reverse=True)))
print("  表观最优 = %s ；校正最优 = %s" % (ma, mc))
disagree = 0
names = [n for n, _ in [(x[0], 0) for x in CLINE]]
for _ in range(B):
    s = [common[rng.randrange(len(common))] for _ in range(len(common))]
    a2 = {n: apparent_of(cline_rows[n], s) for n in names}
    c2 = {n: corrected_of(cline_rows[n], s) for n in names}
    if max(a2, key=a2.get) != max(c2, key=c2.get):
        disagree += 1
print("  **P(argmax 不同) = %.4f**  (B=%d)" % (disagree / B, B))
# 名次变化
rank_app = {n: sorted(app, key=app.get, reverse=True).index(n) + 1 for n in names}
rank_cor = {n: sorted(cor, key=cor.get, reverse=True).index(n) + 1 for n in names}
print("  名次变化:", ", ".join("%s %d→%d" % (n, rank_app[n], rank_cor[n]) for n in names))
res["selection_flip"] = dict(n_common=len(common), apparent=app, corrected=cor,
                             argmax_apparent=ma, argmax_corrected=mc,
                             p_flip=disagree / B, rank_apparent=rank_app, rank_corrected=rank_cor)

out = R / "out_review_round2.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print()
print("已写 %s" % out)
