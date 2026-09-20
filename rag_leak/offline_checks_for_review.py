# -*- coding: utf-8 -*-
"""offline_checks_for_review.py —— 外部评审要求补的三项离线计算（只读产物）。

1. v2 语料上的跨世代闭卷对比（逐题，用于替换正文里的 v0 数字）
2. HotpotQA 的 DiD **等价检验（TOST）**——把"未检出"与"确认为零"分开
3. 各池 DiD 的 95% CI 半宽（评审问"你能排除多大的效应"）

产物：rag_leak/out_review_fixes.json（供写作取数）
"""
import json
import os
import random

R = os.path.dirname(os.path.abspath(__file__))
BOOT = 20000
SEED = 20260903
random.seed(SEED)


def read_fourarm(path):
    rows = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            j = json.loads(line)
            rows[j["question_id"]] = j
    return rows


def q(v):
    s = sorted(v)
    n = len(s)
    lo = s[int(0.025 * n)]
    hi = s[min(n - 1, int(0.975 * n))]
    return lo, hi


def ci(v, alpha=0.05):
    """percentile CI at level 1-alpha (alpha=0.05 -> 95%, alpha=0.10 -> 90%)"""
    s = sorted(v)
    n = len(s)
    lo = s[int((alpha / 2) * n)]
    hi = s[min(n - 1, int((1 - alpha / 2) * n))]
    return lo, hi


def paired_did_boot(rows, keys, B=BOOT, seed_tag=""):
    """逐题 DiD=(b-a)-(d-c) 的配对 bootstrap 分布。

    `seed_tag` 必须传池名：**每个池用独立且由池名派生的随机流**。
    为什么（2026-09-19 实测的隐藏缺陷）：本文件原先把所有池喂给**同一个**全局流
    （模块级 `random.seed(SEED)` + 顺序 `randrange`），于是"在表里插一个池"会平移其后
    所有池的随机数、改变它们的 CI —— 实测插入 HotpotQA_0.6B 后 Qwen3.5-4B 的 CI 从
    [-0.0150,+0.0510] 漂到 [-0.0178,+0.0483]（点估计不变）。CI 依赖表的书写顺序不是统计
    口径的一部分，是纯粹的实现事故。改成按池名派生种子后，增删池不再影响其余池。
    """
    rng = random.Random("%s|%s" % (SEED, seed_tag))
    base = [(rows[k]["b"] - rows[k]["a"]) - (rows[k]["d"] - rows[k]["c"]) for k in keys]
    n = len(base)
    out = []
    for _ in range(B):
        s = 0.0
        for _ in range(n):
            s += base[rng.randrange(n)]
        out.append(s / n)
    return sum(base) / n, out


def tost(ci90, delta):
    """90% CI 落在 ±delta 内 ⇒ 在 alpha=.05 上认定等价"""
    lo, hi = ci90
    return (lo > -delta) and (hi < delta)


def main():
    res = {"seed": SEED, "bootstrap": BOOT}

    # ---------- 1. v2 跨世代闭卷（B 线 v2，同题集） ----------
    p4b = os.path.join(R, "out_b8_fix_k1_4b", "pilot_Qwen3-4B_fourarm.jsonl")
    p35 = os.path.join(R, "out_b8_fix_k1_q35", "pilot_Qwen_Qwen3.5-4B-Base_fourarm.jsonl")
    r4b, r35 = read_fourarm(p4b), read_fourarm(p35)
    keys = sorted(set(r4b) & set(r35))
    a4 = [k for k in keys if r4b[k]["a"] == 1]
    a35 = [k for k in keys if r35[k]["a"] == 1]
    both = [k for k in keys if r4b[k]["a"] == 1 and r35[k]["a"] == 1]
    res["crossgen_v2"] = {
        "n_items": len(keys),
        "a_qwen3_4b": len(a4) / len(keys),
        "a_qwen3p5_4b": len(a35) / len(keys),
        "correct_qwen3_4b": len(a4),
        "correct_qwen3p5_4b": len(a35),
        "overlap": len(both),
        "net_gain": len(a35) - len(a4),
        "generation_gain": len(a35) / len(keys) - len(a4) / len(keys),
    }
    print("1) v2 跨世代闭卷（B 线 v2，n=%d）" % len(keys))
    print("   Qwen3-4B   a=%.4f (%d/%d)" % (len(a4) / len(keys), len(a4), len(keys)))
    print("   Qwen3.5-4B a=%.4f (%d/%d)" % (len(a35) / len(keys), len(a35), len(keys)))
    print("   交集 %d   净增 %+d   世代增益 %+.4f"
          % (len(both), len(a35) - len(a4), len(a35) / len(keys) - len(a4) / len(keys)))

    # ---------- 2/3. DiD 的 CI 半宽 与 TOST ----------
    # ⚠️ 顺序即口径（隐藏缺陷，2026-09-19 实测）：`random.seed(SEED)` 只在模块级播一次，
    # paired_did_boot 顺序消费这**同一个全局流**。因此在表中**插入**一个池会平移其后所有池的
    # 随机数 → CI 改变（实测把 HotpotQA_0.6B 插到最前面，Qwen3.5-4B 的 CI 从
    # [-0.0150,+0.0510] 变成 [-0.0178,+0.0483]，点估计不变）。
    # 为了不动论文里已发表的 CI，规则是：**新池一律追加在末尾**，已有池的相对顺序永不改变。
    # B1 补跑（2026-09-19）：HotpotQA 增加 0.6B / 1.7B 两个小模型，把等价检验从 3 模型扩到 5 模型。
    # 缺产物时下方 isfile 守卫会跳过，故本表可以先行填写。
    pools = {
        "HotpotQA_8B": ("out_s6_hotpot_fix_8b", "pilot_Qwen3-8B_fourarm.jsonl"),
        "HotpotQA_4B": ("out_s6_hotpot_fix_4b", "pilot_Qwen3-4B_fourarm.jsonl"),
        "HotpotQA_Qwen3.5-4B": ("out_s6_hotpot_fix_q35_4b", "pilot_Qwen_Qwen3.5-4B-Base_fourarm.jsonl"),
        "TriviaQA_C_8B": ("out_s6_trivia_fix_8b", "pilot_Qwen3-8B_fourarm.jsonl"),
        # 修正（2026-09-19）：原路径 out_b8_fix_k1_8b **不存在**（B 线 8B 的 k=1 目录是
        # out_b8_fix_k1，无 _8b 后缀），于是这一池一直被 isfile 守卫**静默跳过**——
        # 打印里的"缺产物，跳过"就是它。属于"没报错但也没算"的隐藏缺口，已改正。
        "TriviaQA_B_8B_k1": ("out_b8_fix_k1", "pilot_Qwen3-8B_fourarm.jsonl"),
        # ---- 以下为追加，勿上移 ----
        "HotpotQA_0.6B": ("out_s6_hotpot_fix_06b", "pilot_Qwen3-0.6B_fourarm.jsonl"),
        "HotpotQA_1.7B": ("out_s6_hotpot_fix_17b", "pilot_Qwen3-1.7B_fourarm.jsonl"),
    }
    print()
    print("2/3) DiD 点估计、95%% CI、半宽 与 TOST（δ=3pp / 5pp）")
    res["did"] = {}
    for name, (d, fn) in pools.items():
        path = os.path.join(R, d, fn)
        if not os.path.isfile(path):
            print("   %-22s 缺产物，跳过" % name)
            continue
        rows = read_fourarm(path)
        ks = sorted(rows)
        pt, dist = paired_did_boot(rows, ks, seed_tag=name)
        lo95, hi95 = ci(dist, 0.05)
        lo90, hi90 = ci(dist, 0.10)
        hw = (hi95 - lo95) / 2
        e3, e5 = tost((lo90, hi90), 0.03), tost((lo90, hi90), 0.05)
        res["did"][name] = {
            "n": len(ks), "did": pt, "ci95": [lo95, hi95], "half_width": hw,
            "ci90": [lo90, hi90], "tost_3pp": e3, "tost_5pp": e5,
        }
        print("   %-22s n=%-4d DiD=%+.4f  95%%CI=[%+.4f,%+.4f]  半宽=%.4f  TOST3pp=%s TOST5pp=%s"
              % (name, len(ks), pt, lo95, hi95, hw, "等价" if e3 else "不能", "等价" if e5 else "不能"))

    out = os.path.join(R, "out_review_fixes.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print()
    print("已写 %s" % out)


if __name__ == "__main__":
    main()
