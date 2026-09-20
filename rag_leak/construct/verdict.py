"""R3-B 闸门三档诊断出口：GO / REVISE / ABANDON / INSUFFICIENT。

与"严格 pass 谓词"（config.GATES，决定 passed 布尔）分层：
- passed（bool）       = 是否落在严格 GO 带内（论文的闸门通过判据）。
- verdict（诊断归类）  = 给诊断工具/表用，指示偏差是否需要就地去修（REVISE）还是整体废弃（ABANDON）。

对每个聚合闸门取一个【主指标】+ 方向：
  方向 lower（越小越好）：value<=go→GO；<=abandon→REVISE（含 go..revise、revise..abandon 两段）；>abandon→ABANDON。
  方向 higher（越大越好）：value>=go→GO；>=abandon→REVISE；<abandon→ABANDON。
nan 或调用方已判样本不足时 → INSUFFICIENT（不进 GO/REVISE/ABANDON）。
"""
from __future__ import annotations


def decide_verdict(value: float, go: float | None, revise: float | None,
                   abandon: float | None, direction: str, insufficient: bool = False) -> str:
    """返回 'GO'|'REVISE'|'ABANDON'|'INSUFFICIENT'。"""
    if insufficient or value != value:  # insufficient 或 nan
        return "INSUFFICIENT"
    if direction == "lower":
        if go is not None and value <= go:
            return "GO"
        if abandon is not None and value > abandon:
            return "ABANDON"
        return "REVISE"
    if direction == "higher":
        if go is not None and value >= go:
            return "GO"
        if abandon is not None and value < abandon:
            return "ABANDON"
        return "REVISE"
    raise ValueError(f"未知 direction {direction!r}")


def verdict_from_passed(passed: bool | None, value: float, go: float | None,
                        revise: float | None, abandon: float | None, direction: str) -> str:
    """兼容路径：无显式主指标时，用 passed 布尔 + 方向近似分类（仅门控口径回退用）。"""
    if passed is None:
        return "INSUFFICIENT"
    if passed:
        return "GO"
    return decide_verdict(value, go, revise, abandon, direction, insufficient=False)
