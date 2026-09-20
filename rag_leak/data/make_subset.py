"""确定性抽样 + train/pilot/eval 切分（互不重叠；最终评测集与 pilot 不重叠）。"""
from __future__ import annotations

import random

from .. import config
from ..schemas import Question


def deterministic_sample(questions: list[Question], n: int,
                         seed: int = config.RNG_SEED,
                         exclude_ids: set[str] | None = None) -> list[Question]:
    exclude = exclude_ids or set()
    pool = [q for q in questions if q.id not in exclude]
    rng = random.Random(seed)
    pool = list(pool)
    rng.shuffle(pool)
    return pool[:n]


def split_disjoint(questions: list[Question], n_pilot: int, n_eval: int,
                   seed: int = config.RNG_SEED) -> dict[str, list[Question]]:
    """pilot 与 eval id 不相交（断言保护）。"""
    pilot = deterministic_sample(questions, n_pilot, seed=seed)
    pilot_ids = {q.id for q in pilot}
    rest = [q for q in questions if q.id not in pilot_ids]
    evals = deterministic_sample(rest, n_eval, seed=seed + 1)
    eval_ids = {q.id for q in evals}
    assert not (pilot_ids & eval_ids), "pilot/eval 出现重叠，违反规格"
    train = [q for q in questions if q.id not in pilot_ids | eval_ids]
    return {"train": train, "pilot": pilot, "eval": evals}
