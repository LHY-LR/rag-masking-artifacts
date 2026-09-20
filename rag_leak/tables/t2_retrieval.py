"""T2 闸门①：原/替换金证据 recall@k、joint hit、条件保留率、降幅。"""
from __future__ import annotations


def build(records: list[dict]) -> dict:
    """records: [{retriever,dataset,orig_hit,sub_hit}]。

    `joint_hit_rate` 是两臂同时召回 gold 的绝对比例；`conditional_retain` 才是
    替换没有破坏检索的条件保留率 P(sub_hit | orig_hit)。C 线历史表保留前者的
    render 名称以维持冻结呈现；B 线共享语料模式显式显示两者，不能把低-k recall
    误判为替换不等价。
    """
    out: dict[str, dict] = {}
    for r in records:
        key = f"{r['retriever']}|{r['dataset']}"
        d = out.setdefault(key, dict(n=0, orig=0, sub=0, retained=0))
        d["n"] += 1
        d["orig"] += int(r["orig_hit"])
        d["sub"] += int(r["sub_hit"])
        d["retained"] += int(r["orig_hit"] and r["sub_hit"])
    for d in out.values():
        d["recall_orig"] = d["orig"] / d["n"]
        d["recall_sub"] = d["sub"] / d["n"]
        d["joint_hit_rate"] = d["retained"] / d["n"]
        # backward-compatible data key for historical C-line render/consumers
        d["retain_rate"] = d["joint_hit_rate"]
        d["conditional_retain"] = d["retained"] / d["orig"] if d["orig"] else None
        d["drop"] = d["recall_orig"] - d["recall_sub"]
    return out


def render(t: dict, retention_mode: str = "joint") -> str:
    """Render C-line historical joint rate, or B-line conditional retention explicitly."""
    if retention_mode not in ("joint", "conditional"):
        raise ValueError(f"未知 T2 retention_mode: {retention_mode}")
    lines = ["[T2 闸门① 检索等价]"]
    for k, d in sorted(t.items()):
        if retention_mode == "conditional":
            cond = "n/a" if d["conditional_retain"] is None else f"{d['conditional_retain']:.3f}"
            lines.append(
                f"  {k}: conditional_retain={cond} ({d['retained']}/{d['orig']}) "
                f"joint_hit={d['joint_hit_rate']:.3f} recall "
                f"{d['recall_orig']:.3f}->{d['recall_sub']:.3f} "
                f"(drop {d['drop']:+.3f}) n={d['n']}")
        else:
            lines.append(f"  {k}: retain={d['retain_rate']:.3f} "
                         f"recall {d['recall_orig']:.3f}->{d['recall_sub']:.3f} "
                         f"(drop {d['drop']:+.3f}) n={d['n']}")
    return "\n".join(lines)
