"""单跳 pivot 数据转换器（C10″）：TriviaQA rc validation（本地 parquet）→ 窗口化 DPR json。

为什么从 C10/C10′ 改成窗口化：
- 实测 rc 的 search_context / wiki_context 是**整页抓取 dump**（中位 ~4.3k 字符、有 50 万字符的
  IMDb/Fandom 导航垃圾），不是聚焦片段。把"第一条含答案的整页"当 gold → 大量页里答案出现多次
  → 构集唯一替换几乎全挂；答案常落在 1024-token 截断之外，检索注入反而丢答案。
- 官方 DPR 单跳集的做法正是把 wiki 页面切成短 passage。这里仿照：**窗口化** —— 在候选页里找
  答案 alias 的每个整词出现处，要求【答案出现处 ±prox 内与问题共享 ≥min_overlap 内容词】
  （局部共现，防短数字/日期 alias 命中正文里无关数字），取局部共现最多的一处；金窗口 = 从该
  出现处向两侧扩到【相邻 alias 出现】或【±radius】为止（保证窗口内 alias 恰好一次 → 管线
  build_substituted 的 count==1 断言不炸，主代码零改动）。
- answers 重排：把窗口里字面命中的 alias 放第一位（q.answers[0] 即替换目标表面，保证 span 命中）。
- 干扰候选：同题其它不含 alias 的片段取前 n_pages_max 个（短段落，使检索公平）。

输出：DPR retriever json（list[{question, answers, positive_ctxs:[{title,text}]}]）。
预过滤/落选统计见 stats。

用法（先有本地 parquet；可传多个 shard，依次扫描直到 max_q 条）：
  python -m rag_leak.data.load_trivia_rc --parquet <p1.parquet> [<p2.parquet> ...] \
      --max_q 2000 --out data/trivia-dev.json --eyeball 12
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterator

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    __package__ = "rag_leak"

_STOP = set("""the a an of to in on for and or with at by from as is are was were be been
it its this that these those which who whom whose what when where how why not no do does did
have has had will would can could should may might must etc.""".split())
_PUNCT_RE = re.compile(r"[^0-9a-z]+")
_ALIAS_LEN_CAP = 64  # 超长 alias（整句答案）不做整词匹配，直接放弃


def content_tokens(s: str) -> set[str]:
    return {t for t in _PUNCT_RE.sub(" ", s.lower()).split() if len(t) > 1 and t not in _STOP}


def _wb_spans_lower(low: str, alias: str) -> list[tuple[int, int]]:
    """在已 lower 文本上找整词命中 [start,end)。"""
    a = alias.strip().lower()
    if not a or len(a) > _ALIAS_LEN_CAP:
        return []
    return [(m.start(), m.end())
            for m in re.finditer(r"(?<![0-9a-z])" + re.escape(a) + r"(?![0-9a-z])", low)]


def _clean_aliases(ans: dict) -> list[str]:
    out: list[str] = []
    nv = (ans or {}).get("normalized_value")
    if nv:
        out.append(str(nv).strip())
    for a in (ans or {}).get("aliases", []) or []:
        s = str(a).strip()
        if s and s not in out:
            out.append(s)
    return out


def _candidate_pages(r: dict, n_pages_max: int) -> list[tuple[str, str]]:
    """从一行 rc 抽候选页 [(title, text), ...]：search_results 优先（实际值），entity_pages 兜底。"""
    out: list[tuple[str, str]] = []
    sr = r.get("search_results") or {}
    if isinstance(sr, dict):
        titles = sr.get("title") or []
        ctxs = sr.get("search_context") or []
        for j in range(min(max(len(titles), len(ctxs)), n_pages_max)):
            ti = str(titles[j]) if j < len(titles) else ""
            tx = str(ctxs[j]).strip() if j < len(ctxs) else ""
            if tx:
                out.append((ti, tx))
    ep = r.get("entity_pages") or {}
    if isinstance(ep, dict):
        ep_titles = ep.get("title") or []
        ep_ctxs = ep.get("wiki_context") or []
    else:
        ep_titles = [p.get("title", "") for p in ep]
        ep_ctxs = [(p or {}).get("wiki_context", "") for p in ep]
    if len(out) < n_pages_max:
        for ti, tx in zip(ep_titles, ep_ctxs):
            tx = str(tx).strip()
            if tx:
                out.append((str(ti), tx))
            if len(out) >= n_pages_max:
                break
    return out


def _page_best(text: str, aliases: list[str], qtoks: set[str], radius: int,
               min_overlap: int, prox: int) -> tuple[int, str, str] | None:
    """单页最优金窗口。返回 (score, 命中alias, 窗口文本)，无合格窗口返回 None。

    C10″-p1 局部性修正：min_overlap 改在【答案出现处 ±prox 字符】内统计问题内容词，
    而不是整个 ±radius 窗口。理由：短数字/日期 alias（'13','21','1905'）会整词命中正文里
    无关的数字（"playtime 13 hours"、"Sep. 21, 1998"），窗内宽松共现会把巧合当证据；
    ±prox 局部共现才要求"答案落在包含问题实义词的同一句话里"。

    效率：每页只 lower 一次；命中按文档序，±radius 金窗以相邻 alias 出现为界收紧到恰好一次。
    """
    low = text.lower()
    hits: list[tuple[str, int, int]] = []  # (alias, start, end)
    for a in aliases:
        for s, e in _wb_spans_lower(low, a):
            hits.append((a, s, e))
    if not hits:
        return None
    hits.sort(key=lambda h: h[1])  # 按文档序；同位置边界 = 相邻任何 alias 出现，收紧窗口
    best = None
    for ci, (a, s, e) in enumerate(hits):
        local = content_tokens(text[max(0, s - prox):min(len(text), e + prox)])
        local.discard(a.lower())
        score = len(local & qtoks)
        if score < min_overlap:
            continue
        prev_end = hits[ci - 1][2] if ci > 0 else -1
        next_start = hits[ci + 1][1] if ci < len(hits) - 1 else -1
        # 默认取 ±radius 的聚焦窗；仅当相邻 alias 落在 radius 内才以它为界（收紧到恰好一次）。
        left = max(prev_end + 1, s - radius) if prev_end >= 0 else max(0, s - radius)
        right = min(next_start, e + radius) if next_start >= 0 else min(len(text), e + radius)
        win = text[left:right]
        cand = (score, -len(win))
        if best is None or cand > best[0]:
            best = (cand, a, win)
    if best is None:
        return None
    return (best[0][0], best[1], best[2])


def convert(rows: Iterator[dict], max_q: int = 2000, radius: int = 260,
            min_overlap: int = 2, prox: int = 90, max_cand: int = 5,
            page_cap: int = 150_000, n_pages_max: int = 8) -> dict:
    """rows：rc 行迭代（dict = parquet 行）。返回 {rows, stats}。"""
    out_rows: list[dict] = []
    st = dict(scanned=0, kept=0, no_answer=0, no_page=0, no_gold=0,
              multi_alias_win=0, distractor_total=0)
    for r in rows:
        if len(out_rows) >= max_q:
            break
        st["scanned"] += 1
        aliases = _clean_aliases(r.get("answer"))
        if not aliases:
            st["no_answer"] += 1
            continue
        qtoks = content_tokens(r.get("question") or "")
        pages = _candidate_pages(r, n_pages_max)
        # 去掉病态超长页（纯导航垃圾；极偶尔有用也难在 1024-token 内注入）
        pages = [(ti, tx) for ti, tx in pages if len(tx) <= page_cap]
        if not pages:
            st["no_page"] += 1
            continue
        g: tuple[int, str, str, int] | None = None  # (score, alias, win, page_idx)
        for pi, (ti, tx) in enumerate(pages):
            r_ = _page_best(tx, aliases, qtoks, radius, min_overlap, prox)
            if r_ is None:
                continue
            score, a, win = r_
            if g is None or (score, -len(win)) > (g[0], -len(g[2])):
                g = (score, a, win, pi)
        if g is None:
            st["no_gold"] += 1
            continue
        score, alias, win, pi = g
        # 校验窗口内 alias 恰好一次（保证 build_substituted count==1 断言通过）
        if len(_wb_spans_lower(win.lower(), alias)) != 1:
            st["multi_alias_win"] += 1
            continue
        rest = [a for a in aliases if a.lower() != alias.lower()]
        negs: list[dict] = []
        for j, (ti, tx) in enumerate(pages):
            if j == pi or any(_wb_spans_lower(tx.lower(), a) for a in aliases):
                continue
            negs.append({"title": ti, "text": tx[:900]})
            if len(negs) >= max_cand:
                break
        st["distractor_total"] += len(negs)
        st["kept"] += 1
        out_rows.append({
            "question": str(r.get("question", "")),
            "answers": [alias] + rest,
            "positive_ctxs": [{"title": pages[pi][0], "text": win}],
            "hard_negative_ctxs": [],
            "negative_ctxs": negs,
        })
    return dict(rows=out_rows, stats=st)


def _iter_rows(parquet_path: str) -> Iterator[dict]:
    """惰性逐批读 parquet（不会一次性 materialize 全部巨型行）。"""
    import pyarrow.parquet as pq  # noqa: WPS433  (仅 CLI 路径，selftest 走纯行接口)
    t = pq.read_table(parquet_path)
    for batch in t.to_batches(max_chunksize=200):
        for row in batch.to_pylist():
            yield row


def _iter_files(parquet_paths: list[str]) -> Iterator[dict]:
    for p in parquet_paths:
        pp = Path(p)
        if not pp.exists():
            print(f"[warn] 跳过缺失文件: {p}", file=sys.stderr)
            continue
        yield from _iter_rows(str(pp))


def main(argv=None):
    ap = argparse.ArgumentParser(description="TriviaQA rc(parquet) → 窗口化 DPR json（单跳）")
    ap.add_argument("--parquet", nargs="+", required=True)
    ap.add_argument("--max_q", type=int, default=2000)
    ap.add_argument("--radius", type=int, default=260)
    ap.add_argument("--min_overlap", type=int, default=2)
    ap.add_argument("--prox", type=int, default=90)
    ap.add_argument("--max_cand", type=int, default=5)
    ap.add_argument("--page_cap", type=int, default=150_000)
    ap.add_argument("--n_pages_max", type=int, default=8)
    ap.add_argument("--out", default="data/trivia-dev.json")
    ap.add_argument("--eyeball", type=int, default=0,
                    help="打印前 N 条 问题/答案/金窗口，便于人检")
    args = ap.parse_args(argv)

    res = convert(_iter_files(args.parquet), max_q=args.max_q, radius=args.radius,
                  min_overlap=args.min_overlap, prox=args.prox, max_cand=args.max_cand,
                  page_cap=args.page_cap, n_pages_max=args.n_pages_max)
    st = res["stats"]
    print(f"scanned={st['scanned']} kept={st['kept']} "
          f"(no_answer={st['no_answer']} no_page={st['no_page']} no_gold={st['no_gold']} "
          f"multi_alias_win={st['multi_alias_win']})")
    if st["kept"]:
        print(f"  干扰候选均值 {st['distractor_total']/st['kept']:.1f} 段/题")
    for row in res["rows"][:args.eyeball]:
        print("\nQ:", row["question"][:110])
        print(" A:", row["answers"][:3])
        print(" W:", row["positive_ctxs"][0]["text"][:260].replace("\n", " | "))
        print("   len=", len(row["positive_ctxs"][0]["text"]),
              "n_neg=", len(row["negative_ctxs"]))
    if args.out:
        out = Path(args.out)
        out.write_text(json.dumps(res["rows"], ensure_ascii=False), encoding="utf-8")
        print(f"\n已写 {len(res['rows'])} 条 → {out}（{(out.stat().st_size/1e6):.1f} MB）")


if __name__ == "__main__":
    main()
