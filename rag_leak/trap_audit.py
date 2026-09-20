r"""`tab:trap`（"无操作替换"陷阱）的可复现重算 —— 此前只有论文里的一张表，没有脚本。

定义（与论文表注逐字一致）
--------------------------
一个植入值是 **no-op（无操作）** ⟺ 它规范化后是**目标题自己答案表**里的另一种写法：
    normalize(new_key) ∈ { normalize(a) : a ∈ q.answers }
这正是项目里发现的"自借"构造缺陷（E-N3 / C54）；后果是 `c`、`d` 两臂一起被抬高，
把 masking 往正方向推。表的最后一列就是它在各语料上的发生率。

"substitutions examined" 的口径
-------------------------------
- HotpotQA numeric/date：**每个 run 393 条**；表里 1179 = 当时存在的 3 个 run × 393。
- TriviaQA numeric/date：**每个格 432 条**；表里 7344 = 17 个 model×line×depth 格 × 432。
- 实体线：**每格 363 条**；表里 726 = 2 个模型 × 363（三行分别是 old / new / new2 两模型）。

为什么值得单独脚本化：这张表是论文"构集陷阱"这条贡献的直接证据，而它此前的数字
只有散文/表格，没有可复跑的实现。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .metrics.normalize import normalize_answer

HERE = Path(__file__).parent

HOTPOT_NUMERIC = ["out_s6_hotpot_fix_4b", "out_s6_hotpot_fix_8b", "out_s6_hotpot_fix_q35_4b",
                  "out_s6_hotpot_fix_06b", "out_s6_hotpot_fix_17b"]
TRIVIA_NUMERIC = ["out_s6_trivia_fix_06b", "out_s6_trivia_fix_17b", "out_s6_trivia_fix_4b",
                  "out_s6_trivia_fix_4bi", "out_s6_trivia_fix_8b",
                  "out_b8_fix_k1_06b", "out_b8_fix_k1_17b", "out_b8_fix_k1_4b",
                  "out_b8_fix_k1_4bi", "out_b8_fix_k1", "out_b8_fix_k1_q35",
                  "out_b8_fix_k5_06b", "out_b8_fix_k5_17b", "out_b8_fix_k5_4b",
                  "out_b8_fix_k5_4bi", "out_b8_fix_k5", "out_b8_fix_k5_q35"]
ENTITY = {"unconstrained (out_ent_old)": ["out_ent_old_4bi", "out_ent_old_8b"],
          "domain constraint, before guard (out_ent_new)": ["out_ent_new_4bi", "out_ent_new_8b"],
          "domain constraint, after guard (out_ent_new2)": ["out_ent_new2_4bi", "out_ent_new2_8b"]}


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _one(dname: str) -> dict:
    d = HERE / dname
    subs = sorted(d.glob("*_substituted.jsonl"))
    orc = sorted(d.glob("*_oracle_rows.jsonl"))
    if not subs or not orc:
        return dict(dir=dname, ok=False)
    alias = {r["question_id"]: [normalize_answer(a) for a in (r.get("old_aliases") or [])]
             for r in _jsonl(orc[0])}
    n = noop = 0
    forms: list[int] = []
    for s in _jsonl(subs[0]):
        qid = s["question_id"]
        if qid not in alias:
            continue
        n += 1
        forms.append(len([a for a in alias[qid] if a]))
        nk = normalize_answer(s.get("new_key") or "")
        if nk and nk in set(alias[qid]):
            noop += 1
    return dict(dir=dname, ok=True, n=n, noop=noop, rate=(noop / n if n else 0.0),
                median_forms=statistics.median(forms) if forms else None, forms=forms)


def _group(dirs: list[str], label: str) -> dict:
    per = [_one(d) for d in dirs]
    per = [p for p in per if p.get("ok")]
    n = sum(p["n"] for p in per)
    noop = sum(p["noop"] for p in per)
    # 中位数按**合并后的全部条目**算（表里那一列是"每题答案数"的中位数，不是"每文件中位数"的中位数；
    # 两者在本数据上相同，但合并口径才是可辩护的写法）。
    pooled = [v for p in per for v in p["forms"]]
    return dict(label=label, dirs=[p["dir"] for p in per], n=n, noop=noop,
                rate=(noop / n if n else 0.0),
                median_forms=statistics.median(pooled) if pooled else None,
                median_forms_per_file=[p["median_forms"] for p in per],
                mean_forms=round(statistics.mean(pooled), 2) if pooled else None,
                per_run_range=[min(p["noop"] for p in per), max(p["noop"] for p in per)] if per else None,
                per_dir=[{k: v for k, v in p.items() if k != "forms"} for p in per])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="tab:trap 重算")
    ap.add_argument("--out", default=str(HERE / "out_trap_audit.json"))
    args = ap.parse_args(argv)
    groups = [_group(HOTPOT_NUMERIC, "HotpotQA, numeric/date"),
              _group(TRIVIA_NUMERIC, "TriviaQA, numeric/date")]
    for label, dirs in ENTITY.items():
        groups.append(_group(dirs, "TriviaQA, entity (%s)" % label))
    print(f"{'corpus':<48} {'ans/q(med)':>10} {'subs':>6} {'no-op':>6} {'rate':>8} per-run")
    for g in groups:
        print(f"{g['label']:<48} {g['median_forms']:>10} {g['n']:>6} {g['noop']:>6} "
              f"{100*g['rate']:>7.2f}% {g['per_run_range']}")
    res = dict(groups=groups)
    Path(args.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n已写 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
