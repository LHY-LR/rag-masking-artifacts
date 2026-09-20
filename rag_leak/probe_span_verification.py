"""答案 span 复核探针（需 GPU，交执行方跑）：让冻结模型自己去挑"哪一处数值是这道题的答案"。

**为什么需要**：管线用的是 `RuleBasedProposer` 的判定——"答案字面命中且全段唯一 ⇒ 那就是答案"，
**唯一命中时不调 LLM**（`LLMProposer.propose` 原话）。C32 的 90 条人工审计证明这个假设不成立：
22 条构造缺陷里 17 条是"改错位置"，改动点落在日期（`(August 4, 2002)`）、引文编号（`42 , 43`）、
别的实体的数值（`Jaguar 3.4`、`won the Rugby World Cup the most (3 times)`）上。

本探针把**设计里本该有的消歧步骤**补上，并用**人类审计当金标准**量它值不值得做。

**只读**：不写任何既有 run 目录；产物只写 --out / --report。

用法（在 论文/ 目录执行；需与既有 run 相同的离线 cache 环境）：
  python -m rag_leak.probe_span_verification \
      --subs rag_leak/out_b8_full_k1/pilot_Qwen3-8B_substituted.jsonl \
      --trivia data/trivia_dn.json --model Qwen3-8B --bits 4 \
      --anno rag_leak/anno_defects_90.json \
      --out rag_leak/out_span_verify_8b.json --report rag_leak/out_span_verify_8b.md

判读门槛（**先看这两条再决定要不要重跑**）：
  - 修复率 = 22 条人审缺陷里被本探针改判（换位置或判 none）的比例，**要求 ≥ 10/22**；
  - 误伤率 = 68 条人审好样本里被改判的比例，**要求 ≤ 5/68**（≈7%）。
  两条都过 → 才值得做"全量重构集 + 重跑 c/d 臂"；任一不过 → 停，写进 limitation。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "rag_leak"

from .metrics.normalize import normalize_answer
from .run_pipeline import build_generator

PROMPT = (
    "You are given a QUESTION and a PASSAGE. A specific value string appears in the passage. "
    "Decide WHICH occurrence of that value is the answer to the question.\n"
    "Output ONLY one JSON object, no prose.\n"
    'Schema: {{"char_span":[start,end],"reason":"..."}} or {{"none":true,"reason":"..."}}\n'
    "- start/end are absolute character offsets in the PASSAGE (end exclusive).\n"
    "- If no occurrence of the value actually answers the question, output {{\"none\":true,...}}.\n"
    "VALUE: {val}\nQUESTION: {q}\nPASSAGE:\n{pas}\nJSON:"
)


def _read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def _question_text(trivia: str) -> dict[str, str]:
    out: dict[str, str] = {}
    tp = Path(trivia)
    if tp.exists():
        from .data.load_raw import load_dpr_file
        for q in load_dpr_file(str(tp), "trivia"):
            out[str(q.id)] = q.text
    return out


def _overlaps(a, b) -> bool:
    """两个 span 是否**有交叠**（容忍 off-by-one）。

    判"改判"必须用交叠而不是**逐位相等**：模型返回的 offset 常有 ±1 边界差（或按 1-based 数），
    逐位相等会把几乎每条好样本都判成"改判"——E1 第二次运行"解析成功 86/90、改判 86 条、
    误伤 66/68" 正是这个假象。真正的改判是**换到了另一处出现**（两 span 不相交）或**判 none**。
    """
    if not a or not b:
        return False
    return max(a[0], b[0]) < min(a[1], b[1])


PROMPT_VERIFY = (
    "Read the QUESTION and the PASSAGE. In the PASSAGE text below, exactly one value is wrapped in [[ ]].\n"
    "Decide ONE thing: is THAT WRAPPED occurrence the piece of information that answers the QUESTION, "
    "or is it something else (a date, a reference number, another thing's value)?\n"
    "QUESTION: {q}\n"
    "PASSAGE:\n{pas}\n"
    "The value you must judge is the one inside [[ ]] in the PASSAGE above.\n"
    "Reply with EXACTLY these two lines and nothing else. Replace the placeholder with YES or NO.\n"
    "VERDICT: <YES or NO>\n"
    "REASON: <one short sentence>"
)

_YES = {"yes", "y", "true", "same", "a"}
_NO = {"no", "n", "false", "different", "b"}


def _parse_verdict(raw: str) -> dict:
    """**只认显式判定**，认不出就判 unparsed——绝不从自由文本里猜。

    三轮踩过的坑（每一轮都是"从散文里猜词"造成的）：
      ① tok=32 时模型写 `"NO. …which directly answers the question.\\nAnswer: YES"`——取**第一个**词错；
      ② 改取**最后一个**词后，模型又在推理中途提过 no，把 274/386/430 判反——取**最后一个**词也错。
    根因：base 模型会"先表态、再论证、偶尔自我推翻"，正文里的任何 yes/no 都可能不是它的结论。
    所以现在要求它按固定两行模板输出，只解析 `VERDICT:` 行；解析不到就是 unparsed（如实计入未解析，
    不当成"未改判"充数）。
    """
    m = re.search(r"VERDICT\s*[\*`\"']*\s*[:：]\s*[\*`\"']*\s*([A-Za-z]+)", raw, re.I)
    if m:
        t = m.group(1).lower()
        if t in _YES:
            return {"ok": True, "verdict": "yes", "why": "verdict_line"}
        if t in _NO:
            return {"ok": True, "verdict": "no", "why": "verdict_line"}
    bare = raw.strip().strip("*`\"'. \n").lower()
    if bare in _YES:
        return {"ok": True, "verdict": "yes", "why": "bare_word"}
    if bare in _NO:
        return {"ok": True, "verdict": "no", "why": "bare_word"}
    return {"ok": False, "why": "no_explicit_verdict"}


def _first_json_object(raw: str) -> str | None:
    """从模型输出里抠出**第一个配平的** JSON 对象（比贪婪正则稳：不会被后面的 `}` 或截断搞坏）。"""
    start = raw.find("{")
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(raw)):
            c = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return raw[start:i + 1]
        start = raw.find("{", start + 1)
    return None


def _parse(raw: str, passage: str) -> dict:
    blob = _first_json_object(raw)
    if blob is None:
        return {"ok": False, "why": "no_json"}
    try:
        obj = json.loads(blob)
    except Exception:
        return {"ok": False, "why": "bad_json"}
    if not isinstance(obj, dict):
        return {"ok": False, "why": "not_object"}
    if obj.get("none") is True:
        return {"ok": True, "none": True, "span": None, "reason": str(obj.get("reason", ""))}
    try:
        s, e = int(obj["char_span"][0]), int(obj["char_span"][1])
    except Exception:
        return {"ok": False, "why": "bad_schema"}
    if not (0 <= s < e <= len(passage)):
        return {"ok": False, "why": "span_out_of_range"}
    return {"ok": True, "none": False, "span": [s, e], "text": passage[s:e],
            "reason": str(obj.get("reason", ""))}


def _generate(gen, prompt: str, max_new_tokens: int) -> str:
    """优先走 `generate_raw`（原样 prompt + 完整输出）。

    **绝不退回 `generate()`**：它的位置参数语义是"问题"，会把 prompt 套进 `Q: … A: The answer is`
    模板并只返回首行，必然解析失败——C34 E1 首次运行解析成功 1/90 就是栽在这里。
    """
    if not hasattr(gen, "generate_raw"):
        raise SystemExit(f"{type(gen).__name__} 没有 generate_raw；本探针不能走 generate()")
    return str(gen.generate_raw(prompt, max_new_tokens=max_new_tokens))



def _score(rec: dict) -> dict:
    """给一条记录打上判据字段。

    - `verify` 模式：`changed = (verdict == "no")`（模型判"这处不是在回答这道题"）。
    - `span` 模式：`changed` 用**交叠**，不用逐位相等。
    """
    if "llm_verdict" in rec:
        rec["changed"] = bool(rec.get("llm_ok") and rec.get("llm_verdict") == "no")
        rec["span_overlap"] = bool(rec.get("llm_ok") and rec.get("llm_verdict") == "yes")
        rec.setdefault("offset_delta", None)
        rec.setdefault("exact_span", None)
        return rec
    sp, ps = rec.get("llm_span"), rec.get("pipeline_span")
    rec["span_overlap"] = _overlaps(sp, ps)
    rec["offset_delta"] = (sp[0] - ps[0]) if sp else None
    rec["exact_span"] = bool(sp and ps and list(sp) == list(ps))
    rec["changed"] = bool(rec.get("llm_ok") and (rec.get("llm_none") or not rec["span_overlap"]))
    return rec


def _audit(recs: list[dict], anno: dict) -> dict:
    bad, sample = set(anno["exclude_ids"]), set(anno["sample_ids"])
    idx = {r["question_id"]: r for r in recs}
    unparsed = [q for q in sorted(sample) if not idx.get(q, {}).get("llm_ok")]
    sb = [q for q in sorted(sample) if q in bad and idx.get(q, {}).get("changed")]
    sg = [q for q in sorted(sample) if q not in bad and idx.get(q, {}).get("changed")]
    n_bad_ok = len([q for q in sorted(sample) if q in bad and idx.get(q, {}).get("llm_ok")])
    n_good_ok = len([q for q in sorted(sample) if q not in bad and idx.get(q, {}).get("llm_ok")])
    return {
        "n_sample": len(sample), "n_bad": len(bad), "n_good": len(sample) - len(bad),
        "n_bad_scored": n_bad_ok, "n_good_scored": n_good_ok, "unparsed": unparsed,
        "repaired": sb, "n_repaired": len(sb),
        "false_alarm": sg, "n_false_alarm": len(sg),
        "gate_repair_ok": len(sb) >= 10, "gate_false_alarm_ok": len(sg) <= 5,
        "note": "判据=span 不相交或判 none；分母是**可解析**的条数，未解析单列 unparsed",
    }


def _reanalyze(src: str, anno_path: str, out_path: str, report: str) -> int:
    """**零 GPU**：用已落盘的 records 重算判据（`changed` 由逐位相等改为交叠）。

    为什么需要：E1 第二次运行的 records 里已存了 `llm_span` / `pipeline_span` / `llm_text` / `llm_none`，
    足以离线重判；不必再花 17 分钟 GPU 重跑。
    """
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    recs = [_score(r) for r in data["records"]]
    data["records"] = recs
    if anno_path:
        data["audit"] = _audit(recs, json.loads(Path(anno_path).read_text(encoding="utf-8")))
    Path(out_path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    from collections import Counter
    deltas = Counter(r["offset_delta"] for r in recs if r.get("llm_ok") and r["offset_delta"] is not None)
    n_ok = sum(1 for r in recs if r.get("llm_ok"))
    n_exact = sum(1 for r in recs if r.get("exact_span"))
    n_ov = sum(1 for r in recs if r.get("span_overlap"))
    n_ch = sum(1 for r in recs if r.get("changed"))
    print(f"[重判] 可解析 {n_ok}/{len(recs)}；逐位相等 {n_exact}；有交叠 {n_ov}；改判 {n_ch}")
    print(f"[重判] offset_delta 最常见的 10 个值：{deltas.most_common(10)}")
    if "audit" in data:
        a = data["audit"]
        print(f"[重判] 修复 {a['n_repaired']}/{a['n_bad_scored']}（可解析分母）: {a['repaired']}")
        print(f"[重判] 误伤 {a['n_false_alarm']}/{a['n_good_scored']}: {a['n_false_alarm']}")
        print(f"[重判] 未解析 {len(a['unparsed'])} 条: {a['unparsed']}")
        print(f"[重判] 门槛：修复={'过' if a['gate_repair_ok'] else '不过'} "
              f"误伤={'过' if a['gate_false_alarm_ok'] else '不过'}")
    if report:
        lines = [f"# 答案 span 复核 · 离线重判（{data.get('model','?')}）", "",
                 f"- 源：`{src}`", f"- 可解析 {n_ok}/{len(recs)}；**逐位相等 {n_exact}**；"
                 f"**有交叠 {n_ov}**；改判 {n_ch}",
                 f"- `offset_delta` 最常见：{deltas.most_common(10)}", ""]
        if "audit" in data:
            a = data["audit"]
            lines += [f"- **修复 {a['n_repaired']}/{a['n_bad_scored']}**（门槛 ≥10）：{'过' if a['gate_repair_ok'] else '不过'}",
                      f"- **误伤 {a['n_false_alarm']}/{a['n_good_scored']}**（门槛 ≤5）：{'过' if a['gate_false_alarm_ok'] else '不过'}",
                      f"- 未解析：{a['unparsed']}",
                      f"- 被修复：{a['repaired']}", f"- 被误伤：{a['false_alarm']}", ""]
        for r in recs:
            if r.get("changed"):
                lines.append(f"- `{r['question_id']}` old=`{r['old']}` 管线={r.get('pipeline_span')} "
                             f"模型={r.get('llm_span')}（none={r.get('llm_none')}）理由：{str(r.get('llm_reason'))[:90]}")
        Path(report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"[重判] 已写报告：{report}")
    print(f"[重判] 已写：{out_path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="答案 span 复核探针（只读；需 GPU）")
    ap.add_argument("--subs", default="", help="substituted.jsonl（取 old_passage 与 proposal）")
    ap.add_argument("--trivia", default="data/trivia_dn.json", help="题池，用于还原题目文本")
    ap.add_argument("--anno", default="", help="anno_defects_90.json；给了就算修复率/误伤率")
    ap.add_argument("--model", default="Qwen3-8B")
    ap.add_argument("--bits", type=int, default=4)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--generator", default="hf", choices=["hf", "stub", "remote"])
    ap.add_argument("--vllm-url", default="")
    ap.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全部；冒烟用 10）")
    ap.add_argument("--sample-only", action="store_true",
                    help="只跑 --anno 里的 sample_ids（人审的 90 条，50 分钟内可完成）；"
                         "E1 阶段用这个把 GPU 成本压到 ~90 次生成")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report", default="")
    ap.add_argument("--max-new-tokens", type=int, default=192,
                    help="generate_raw 的输出上限（默认 192；JSON 含 offset+理由，64 一定截断）")
    ap.add_argument("--mode", default="verify", choices=["verify", "span"],
                    help="verify（默认，推荐）= 让模型对**标记处**回一个字 YES/NO；"
                         "span = 让模型自己给 char_span（base 模型数不准偏移，E1 实测失效）")
    ap.add_argument("--reanalyze", default="",
                    help="**零 GPU**：读一份已落盘的 out json，用交叠判据重算 changed/修复/误伤并另存。"
                         "给了它就忽略 --subs 等跑批参数")
    args = ap.parse_args(argv)

    if args.reanalyze:
        return _reanalyze(args.reanalyze, args.anno, args.out, args.report)

    rows = _read_jsonl(Path(args.subs))
    if not rows:
        raise SystemExit(f"{args.subs} 为空")
    anno = json.loads(Path(args.anno).read_text(encoding="utf-8")) if args.anno else None
    if args.sample_only:
        if not anno:
            raise SystemExit("--sample-only 需要同时给 --anno")
        keep = set(anno["sample_ids"])
        rows = [r for r in rows if r["question_id"] in keep]
        print(f"--sample-only：筛选出 {len(rows)} 条")
    if args.limit:
        rows = rows[:args.limit]
    qtext = _question_text(args.trivia)
    gen = build_generator(args.generator, args.model, args.bits, args.device, args.vllm_url)

    recs = []
    for i, r in enumerate(rows, 1):
        pr = r.get("proposal") or {}
        old, span = str(pr.get("old") or ""), pr.get("char_span")
        pas = str(r.get("old_passage") or "")
        q = qtext.get(r["question_id"], "")
        if not (old and span and pas and q):
            recs.append({"question_id": r["question_id"], "status": "skipped_input"})
            continue
        if args.mode == "verify":
            i1, i2 = int(span[0]), int(span[1])
            # C39：标记必须**画在段落正文里**。旧版只在 `MARKED:` 行画 << >>、正文没有，
            # 而提示词又写着"in the passage, one value is marked"——模型于是在正文里找标记，
            # 找不到就自己瞎认一个（trivia-223 认成 "size"、trivia-274 认成 1826、
            # trivia-430 认成 "costumes"），3 条"误伤"全部由此而来。
            marked = pas[:i1] + "[[" + old + "]]" + pas[i2:]
            prompt = PROMPT_VERIFY.format(q=q, val=old, pas=marked)
            raw = _generate(gen, prompt, args.max_new_tokens)
            v = _parse_verdict(str(raw))
            recs.append(_score({
                "question_id": r["question_id"], "old": old, "pipeline_span": list(span),
                "llm_ok": v.get("ok", False), "llm_why": v.get("why", ""),
                "llm_verdict": v.get("verdict"), "raw": str(raw)[:800],
            }))
        else:
            raw = _generate(gen, PROMPT.format(val=old, q=q, pas=pas), args.max_new_tokens)
            got = _parse(str(raw), pas)
            same_text = (got.get("ok") and not got.get("none")
                         and normalize_answer(got.get("text", "")) == normalize_answer(old))
            recs.append(_score({
                "question_id": r["question_id"], "old": old, "pipeline_span": list(span),
                "llm_ok": got.get("ok", False), "llm_why": got.get("why", ""),
                "llm_none": bool(got.get("none")),
                "llm_span": got.get("span"), "llm_text": got.get("text"),
                "llm_reason": got.get("reason", ""),
                "same_text": bool(same_text),
                "raw": str(raw)[:600],
            }))
        if i % 25 == 0:
            print(f"  ...{i}/{len(rows)}")

    out = {"model": args.model, "subs": args.subs, "n": len(recs), "records": recs}
    if anno:
        out["audit"] = _audit(recs, anno)
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    n_ok = sum(1 for r in recs if r.get("llm_ok"))
    n_ch = sum(1 for r in recs if r.get("changed"))
    n_exact = sum(1 for r in recs if r.get("exact_span"))
    n_ov = sum(1 for r in recs if r.get("span_overlap"))
    fails = [r for r in recs if not r.get("llm_ok")]
    print(f"\n解析成功 {n_ok}/{len(recs)}；改判 {n_ch} 条")
    if args.mode == "verify":
        from collections import Counter
        print("判定分布：", dict(Counter(r.get("llm_verdict") or "unparsed" for r in recs)))
    else:
        print(f"逐位相等 {n_exact}；有交叠 {n_ov}")
        from collections import Counter
        deltas = Counter(r["offset_delta"] for r in recs
                         if r.get("llm_ok") and r.get("offset_delta") is not None)
        print("offset_delta 最常见 10 个值：", deltas.most_common(10))
    if fails:
        from collections import Counter
        print("解析失败原因分布：", dict(Counter(r.get("llm_why") or r.get("status") or "?" for r in fails)))
        print("失败样本原始输出（前 5 条，各 200 字）：")
        for r in fails[:5]:
            print(f"  [{r.get('question_id')}] {str(r.get('raw'))[:200]!r}")
    if "audit" in out:
        a = out["audit"]
        print(f"修复 {a['n_repaired']}/{a['n_bad']}（门槛≥10）: {a['repaired']}")
        print(f"误伤 {a['n_false_alarm']}/{a['n_good']}（门槛≤5）: {a['n_false_alarm']}")
        print(f"门槛：修复={'过' if a['gate_repair_ok'] else '不过'} "
              f"误伤={'过' if a['gate_false_alarm_ok'] else '不过'}")
    if args.report:
        lines = [f"# 答案 span 复核探针（{args.model}）", "",
                 f"- 输入：`{args.subs}`；条目 {len(recs)}",
                 f"- 解析成功 {n_ok}；改判 {n_ch}", ""]
        if "audit" in out:
            a = out["audit"]
            lines += [f"- **修复 {a['n_repaired']}/{a['n_bad']}**（门槛 ≥10）：{'过' if a['gate_repair_ok'] else '不过'}",
                      f"- **误伤 {a['n_false_alarm']}/{a['n_good']}**（门槛 ≤5）：{'过' if a['gate_false_alarm_ok'] else '不过'}",
                      f"- 被修复的题：{a['repaired']}", f"- 被误伤的题：{a['false_alarm']}", ""]
        if fails:
            from collections import Counter
            lines += ["## 解析失败诊断", "",
                      f"- 原因分布：{dict(Counter(r.get('llm_why') or r.get('status') or '?' for r in fails))}",
                      "- 原始输出样本（前 5 条）："]
            for r in fails[:5]:
                lines.append(f"  - `{r.get('question_id')}`: {str(r.get('raw'))[:200]}")
            lines.append("")
        for r in recs:
            if r.get("changed"):
                lines.append(f"- `{r['question_id']}` old=`{r['old']}` 管线={r.get('pipeline_span')} "
                             f"模型={r.get('llm_span')}（none={r.get('llm_none')}）理由：{r.get('llm_reason','')[:90]}")
        Path(args.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"已写报告：{args.report}")
    print(f"已写：{args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
