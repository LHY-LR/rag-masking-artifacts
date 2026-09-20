r"""B3：闭卷 token 对数概率 —— 连续版「参数记忆强度」探针（只读，纯增量）。

动机（为什么要连续强度）
------------------------
主文的分解

    masking = (d - c) - (b - a) = (a - c) + (d - b)

是**恒等式**：等号右边**逐字**含二值指示 a（= cb_orig 的 EM）。所以"masking 随 a 上升"
（H4 剂量-反应，17 格斜率 0.503）在机械层面**部分是自己解释自己**——a 同时出现在被解释量
和解释量里。想把这条证据从"恒等式的重述"升级成"独立经验事实"，必须换一个**不出现在恒等式
里的记忆强度量**。本探针就是这个量：

    lp_old(m, i) = 闭卷 prompt 下模型 m 对**旧（真）答案串**的 teacher-forced 平均对数概率
    margin       = lp_old - lp_new   （旧值相对虚构新值的边际）

lp_old / margin 不参与 a/b/c/d 的任何计算，故"masking 随 lp_old 上升"不是恒等式的重述。

设计要点
--------
1. **不重跑四臂、不生成**：每题只做两次前向（旧串、新串），再与冻结产物按 question_id join。
   因此不触碰任何冻结指标，定位与 C7/C8 诊断一致（纯增量）。
2. **量化位数必须与冻结 run 一致**（默认 4bit）：4bit 与 16bit 的 logits 有系统差，混位数会
   让"强度"与被解释量口径不一致。(a,b,c,d) 全部来自 4bit run，故强度也取 4bit。
3. **prompt 构造走同一条路**：直接复用 `generation.model` 的 `render_prompt` /
   `render_chat_messages` / `is_instruct`，chat 模板的 `enable_thinking` 回退逻辑照抄
   `HFGenerator.generate`（见 `_chat_prompt` 注释）。保证强度是在**四臂真正看到的 prompt** 上测的。
4. **可离线自检**：`--dry-run` 只加载 tokenizer（CPU、离线、KB 级），打印 prompt 与 token 数，
   不发一次 GPU 前向——用于在 GPU 被占时验证数据接线。

用法
----
    set HF_ENDPOINT=https://hf-mirror.com
    set HF_HOME=...\论文\.hf_cache
    set HF_HUB_CACHE=D:\1
    & venv\Scripts\python.exe -m rag_leak.probe_memory_strength --dry-run
    & venv\Scripts\python.exe -m rag_leak.probe_memory_strength --runs s6trivia

产物：`rag_leak/out_memstrength/memstrength_<label>.jsonl`（逐题）+ `_meta.json`。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许直接 python probe_memory_strength.py 运行
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .generation.model import HFGenerator, is_instruct, render_chat_messages, render_prompt

HERE = Path(__file__).parent

# C 线 v2 语料（n=432）冻结 run：5 个模型，题集逐字相同（构集与模型无关）。
# label -> (模型短名, 产物目录)。判读时按本表 join 四臂行。
RUNS: dict[str, list[tuple[str, str]]] = {
    "s6trivia": [
        ("Qwen3-0.6B", "out_s6_trivia_fix_06b"),
        ("Qwen3-1.7B", "out_s6_trivia_fix_17b"),
        ("Qwen3-4B", "out_s6_trivia_fix_4b"),
        ("Qwen3-4B-Instruct", "out_s6_trivia_fix_4bi"),
        ("Qwen3-8B", "out_s6_trivia_fix_8b"),
    ],
    # 跨世代（Qwen3.5，VL 结构）：C 线 v2 无 run，但闭卷臂 a/c 与检索无关，
    # 其 a/c 可取 B 线同一模型的四臂行；本组只用来给"强度 vs 掩盖"补一个独立世代点。
    "q35_bline": [
        ("Qwen/Qwen3.5-4B-Base", "out_b8_fix_k1_q35"),
        ("Qwen/Qwen3.5-4B-Base", "out_b8_fix_k5_q35"),
    ],
    "hotpot_s6": [
        ("Qwen3-4B", "out_s6_hotpot_fix_4b"),
        ("Qwen3-8B", "out_s6_hotpot_fix_8b"),
        ("Qwen/Qwen3.5-4B-Base", "out_s6_hotpot_fix_q35_4b"),
    ],
}


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def _find(d: Path, suffix: str) -> Path:
    hits = sorted(d.glob(f"*{suffix}"))
    if len(hits) != 1:
        raise SystemExit(f"{d} 下应有唯一 *{suffix}，实际 {[h.name for h in hits]}")
    return hits[0]


def _chat_prompt(tok, msgs: list[dict]) -> str:
    """与 HFGenerator.generate（model.py L134-147）逐字同构的 chat prompt 构造。

    为什么照抄而不抽公共函数：model.py 属四臂生成路径，正被长跑 run 依赖；在跑动期间改动它
    收益为零而风险非零。此处 8 行重复 + 本注释即等价性凭证。
    """
    try:
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                       chat_template_kwargs={"enable_thinking": False})
    except (TypeError, ValueError):
        return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)


def build_prompt(tok, model_name: str, question: str) -> tuple[str, str]:
    """返回 (prompt, cont_style)；cont_style ∈ {"space","plain"} 决定续写串前缀。"""
    if is_instruct(model_name):
        return _chat_prompt(tok, render_chat_messages(question, None)), "plain"
    return render_prompt(question, None), "space"


def continuation_lp(gen: HFGenerator, prompt: str, cont: str) -> dict:
    """teacher-forced 续写对数概率（精确：只对续写段取 log_softmax 后 gather）。

    返回 sum/mean/first 三种口径。为什么要 first：mean 会被答案串长度与分词粒度稀释
    （"2006" 是 1 个 token，"New York City" 是 3 个），而"首 token 对不对"是最稳的
    单点强度信号；两者同时落盘，判读时可对比，避免事后挑口径。
    """
    import torch
    tok, model = gen.tok, gen.model
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    full = tok(prompt + cont, add_special_tokens=False)["input_ids"]
    if len(full) <= len(p_ids) or full[:len(p_ids)] != p_ids:
        # 边界不可靠（BPE 跨边界合并，罕见）：退化为把续写单独编码后拼接。
        alt = tok(cont, add_special_tokens=False)["input_ids"]
        if not alt:
            return dict(sum_lp=None, mean_lp=None, first_lp=None, n_tok=0, boundary="empty")
        full = list(p_ids) + list(alt)
        n = len(alt)
        boundary = "resplit"
    else:
        n = len(full) - len(p_ids)
        boundary = "prefix"
    ids = torch.tensor([full], device=model.device)
    with torch.no_grad():
        logits = model(ids).logits[0].float()
    lp = torch.log_softmax(logits, dim=-1)
    tgt = ids[0, len(full) - n:]
    vals = lp[len(full) - n - 1:len(full) - 1].gather(1, tgt[:, None]).squeeze(1)
    return dict(sum_lp=round(float(vals.sum()), 6), mean_lp=round(float(vals.mean()), 6),
                first_lp=round(float(vals[0]), 6), n_tok=int(n), boundary=boundary)


def _items_for(group: str, out_dir: Path, per_dir_limit: int = 0) -> list[dict]:
    """把 group 里各 run 目录的 oracle_rows 合并为「题集 × 模型」任务表。

    题面/旧值/新值都是构集产物、与模型无关，故以**第一个目录**为准建题集，
    其余目录只用于确认 question_id 覆盖率（缺题即报错，不允许静默少跑）。
    """
    tasks: list[dict] = []
    ref_ids: set[str] | None = None
    for model, dname in RUNS[group]:
        d = out_dir / dname
        rows = _jsonl(_find(d, "_oracle_rows.jsonl"))
        ids = [r["question_id"] for r in rows]
        if ref_ids is None:
            ref_ids = set(ids)
        elif set(ids) != ref_ids:
            raise SystemExit(f"{dname} 题集与参照不一致：缺 {len(ref_ids - set(ids))} 题")
        for r in rows[:per_dir_limit] if per_dir_limit else rows:
            new = (r.get("new_aliases") or [None])[0]
            tasks.append(dict(model=model, dir=dname, question_id=r["question_id"],
                              question=r["question"], old=r["gold"], new=new,
                              dataset=r.get("dataset"), answer_type=r.get("answer_type")))
    return tasks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="B3 闭卷 token 对数概率（连续记忆强度）")
    ap.add_argument("--runs", default="s6trivia", choices=sorted(RUNS),
                    help="预注册的 run 组；默认 C 线 v2 五模型")
    ap.add_argument("--out", default=str(HERE / "out_memstrength"))
    ap.add_argument("--bits", type=int, default=4, choices=[16, 8, 4],
                    help="必须与冻结 run 一致（默认 4）")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 题（冒烟用；0=全量）")
    ap.add_argument("--only", default="",
                    help="只跑这些模型（逗号分隔短名）；空=全部。存在的必要性：Qwen3.5 要 venv_next"
                         "（transformers 5.x），Qwen3 文本模型要 venv（4.5x）——同组混着时必须分两次跑。")
    ap.add_argument("--dry-run", action="store_true",
                    help="只加载 tokenizer 打印 prompt/token 数，不做任何模型前向")
    args = ap.parse_args(argv)

    out_dir = Path(args.out)
    tasks = _items_for(args.runs, HERE, per_dir_limit=args.limit)
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        tasks = [t for t in tasks if t["model"] in want]
        if not tasks:
            raise SystemExit(f"--only {sorted(want)} 在本组里没有匹配的模型")
    models = sorted({t["model"] for t in tasks})
    print(f"[B3] run 组={args.runs}  模型={len(models)}  任务={len(tasks)}  bits={args.bits}")
    if args.dry_run:
        from transformers import AutoTokenizer
        from .config import HF_MODEL_IDS
        tok = AutoTokenizer.from_pretrained(HF_MODEL_IDS[models[0]])
        seen = 0
        for t in tasks:
            if t["model"] != models[0]:
                continue
            prompt, style = build_prompt(tok, t["model"], t["question"])
            n_p = len(tok(prompt, add_special_tokens=False)["input_ids"])
            n_o = len(tok(prompt + (t["old"] if style == "plain" else " " + t["old"]),
                          add_special_tokens=False)["input_ids"]) - n_p
            n_n = len(tok(prompt + (t["new"] if style == "plain" else " " + t["new"]),
                          add_special_tokens=False)["input_ids"]) - n_p
            print(f"  {t['question_id']:<18} old={t['old']!r:<22} new={t['new']!r:<22} "
                  f"prompt_tok={n_p} old_tok={n_o} new_tok={n_n} style={style}")
            if seen == 0:
                print("  --- prompt 原文（repr）---")
                print("  " + repr(prompt))
            seen += 1
            if seen >= 5:
                break
        print(f"[dry-run] 未加载模型、未做前向；题集={len(tasks)} 条任务（含全部模型）")
        return 0

    # 产物落在 out_dir/<runs>/ 下：不同 run 组会共用同名模型（如 Qwen3-4B 同时在
    # s6trivia 与 hotpot_s6 里），同目录同名会互相覆盖 → 强度与题集错配且无声。
    dest = out_dir / args.runs
    dest.mkdir(parents=True, exist_ok=True)
    by_model: dict[str, list[dict]] = {}
    for m in models:
        gen = HFGenerator(m, bits=args.bits, device=args.device)
        rows = []
        for t in [x for x in tasks if x["model"] == m]:
            prompt, style = build_prompt(gen.tok, m, t["question"])
            pre = "" if style == "plain" else " "
            lp_old = continuation_lp(gen, prompt, pre + t["old"]) if t["old"] else None
            lp_new = continuation_lp(gen, prompt, pre + t["new"]) if t["new"] else None
            rec = dict(question_id=t["question_id"], model=m, dataset=t["dataset"],
                       answer_type=t["answer_type"], old=t["old"], new=t["new"],
                       cont_style=style, bits=args.bits,
                       lp=dict(old=lp_old, new=lp_new))
            if lp_old and lp_new and lp_old["mean_lp"] is not None and lp_new["mean_lp"] is not None:
                rec["margin_mean"] = round(lp_old["mean_lp"] - lp_new["mean_lp"], 6)
            rows.append(rec)
            if len(rows) % 50 == 0:
                print(f"  [{m}] {len(rows)}/{sum(1 for x in tasks if x['model'] == m)}")
        by_model[m] = rows
        p = dest / f"memstrength_{m.replace('/', '_')}.jsonl"
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
                     encoding="utf-8")
        print(f"[B3] {m}: {len(rows)} 题 -> {p.relative_to(out_dir)}")
        del gen

    meta = dict(runs=args.runs, bits=args.bits, models=models,
                dirs={m: d for m, d in RUNS[args.runs]}, n_per_model={m: len(v) for m, v in by_model.items()},
                definition=("lp_old = 闭卷 prompt 下旧答案串的 teacher-forced 平均对数概率；"
                            "margin_mean = lp_old.mean - lp_new.mean；不参与 a/b/c/d 计算"))
    (dest / f"memstrength_{args.runs}_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[B3] meta -> {(dest / f'memstrength_{args.runs}_meta.json').relative_to(out_dir)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
