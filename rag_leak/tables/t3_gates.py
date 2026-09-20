"""T3 闸门②③④ × 规模。"""
from __future__ import annotations


def build(per_model: dict[str, dict]) -> dict:
    return per_model


def render(t: dict) -> str:
    lines = ["[T3 闸门②③④ × 规模]", "  （GO/REVISE/ABANDON 为三档诊断出口，INSUFFICIENT=样本不足）"]
    for model, d in sorted(t.items()):
        lines.append(f"  {model}:")
        for gate_name, gate in d.items():
            v = (getattr(gate, "verdict", None)
                 or ("INSUFFICIENT" if gate.passed is None else ("PASS" if gate.passed else "FAIL")))
            lines.append(f"    {gate_name}: {v} value={gate.value:.3f} | {gate.detail}")
    return "\n".join(lines)
