# What Apparent Gains Hide — code, corpora and audit materials

This repository accompanies the paper *What Apparent Gains Hide: Measuring, Validating,
and Localising Parametric-Memory Contamination in RAG Evaluation*.

## What is here

| Path | Contents |
|---|---|
| `rag_leak/` | All experiment code: four-arm pipeline (`run_pipeline.py`), B-line retrieval line, scoring (`metrics/normalize.py`), the borrowing pool (`data/value_pool.py`), corpus builders, the audit tooling, and the offline re-analyses. |
| `rag_leak/out_*/` | Frozen run artifacts. Each run directory holds `*_metrics.json` (the four arm accuracies), `*_fourarm.jsonl` (per-item a/b/c/d), `*_oracle_rows.jsonl` (per-item raw model output plus oracle scoring), `*_substituted.jsonl` (the substitution actually applied), `*_manifest.json` and `*_summary.txt`. These are the artifacts every number in the paper is recomputed from. |
| `rag_leak/anno_*` | Human-audit materials: the 90-item sample, both annotators' sheets, the agreed labels, the defect list, and the kappa computation. |
| `data/` | Derived pools used by the paper (TriviaQA numeric/date pool, entity pool, HotpotQA numeric/date pool). **Raw third-party datasets are not redistributed**; see `DATA_LICENSES.md`. |
| `paper/` | LaTeX source, bibliography and figure scripts for the paper. |
| `Claims_Ledger.md` | The single source of truth for every number quoted in the paper. |

## Environment

Python 3.12; see `requirements.txt`. The Qwen3.5-4B-Base run additionally needs
`transformers==5.17.0` in a separate environment (that model is a vision-language
architecture). All runs in the paper used 4-bit weights (bitsandbytes 0.45.5) on a single
NVIDIA RTX 4060 Laptop GPU with 8 GB. Question sampling and every bootstrap use the fixed
seed `20260903` with `B=10,000` resamples.

## Quick verification (no GPU)

```bash
python -m rag_leak.selftest        # expect: ALL SELFTESTS OK
python -m rag_leak.check_round2    # expect: ALL ROUND2 CHECKS OK
python -m rag_leak.check_round3    # expect: ALL ROUND3 CHECKS OK
python -m rag_leak.cline_holm      # recomputes the C-line Holm correction
```

## Reproducing the paper

See `REPRODUCE.md` for a table-by-table / figure-by-figure command list, and
`CHECKSUMS.md` for MD5 checksums of every artifact so that a re-run can be compared
against the frozen files byte for byte.

## Licence

Code: MIT (`LICENSE`). Derived pools and artifact files: see `DATA_LICENSES.md`, which also
records the licences of the upstream datasets (TriviaQA, HotpotQA) that the pools are
derived from.
