# Reproduction guide

Every command is run from the repository root. GPU commands are marked **[GPU]**; all of
them need `torch` + `transformers` from `requirements.txt` and, for Qwen3.5, the separate
`transformers==5.17.0` environment.

## 0. Environment

```bash
pip install -r requirements.txt
python -m rag_leak.selftest
```

## 1. Main tables (offline, from the frozen artifacts)

| Paper item | Command |
|---|---|
| Table `tab:corpora` (pool sizes) | `python -m rag_leak.entity_experiment validate --n 60` (pool integrity) |
| Table `tab:cline` / Fig. 3 (C-line, five models) | `python -m rag_leak.offline_rescore --oracle_rows rag_leak/out_s6_trivia_fix_8b/pilot_Qwen3-8B_oracle_rows.jsonl` |
| Table `tab:bline` / Fig. 5 (B-line, six models, both k) | `python -m rag_leak.analyze_bline` |
| Holm correction, C-line | `python -m rag_leak.cline_holm` → `rag_leak/out_cline_holm.json` |
| Holm correction, B-line stratum | `python -m rag_leak.holm_stratum` → `rag_leak/out_stratum_holm.json` |
| Cleaning ablation, all 20 cells | `python -m rag_leak.offline_review_round2` → `rag_leak/out_review_round2.json` |
| Appendix tables + `appendix.tex` | `python -m rag_leak.make_appendix` |
| Table `tab:app-kaxis5` (B-line $k$ axis, five depths, v2) | `python -m rag_leak.analyze_kaxis --root rag_leak --ks 1 3 5 10 20 --dir-pattern "out_b8_fix_k{k}" --out rag_leak/out_b8_fix_kaxis_analysis.json` |
| HotpotQA five-model equivalence test (TOST) | `python -m rag_leak.offline_checks_for_review` → `rag_leak/out_review_fixes.json` |
| Dose--response slope + `tab:strength` | `python -m rag_leak.dose_strength` → `rag_leak/out_dose_strength.json` |
| Decision-reversal $P(	ext{flip})$ | `python -m rag_leak.flip_decision` → `rag_leak/out_flip_decision.json` |
| `tab:trap` (no-op substitution rates) | `python -m rag_leak.trap_audit` → `rag_leak/out_trap_audit.json` |
| Residual defect rate (capture--recapture) | `python -m rag_leak.residual_rate` → `rag_leak/out_residual_rate.json` |
| Entity-line alias-aware rescoring | `python -m rag_leak.entity_alias_rescore` → `rag_leak/out_entity_alias_rescore_v2.json` |
| B3 continuous memory strength (probe $	o$ analysis) | `python -m rag_leak.probe_memory_strength --runs s6trivia` then `python -m rag_leak.analyze_memstrength --runs s6trivia --boot 10000` |
| B5 substitution-free protocol (pilot; ledger only, not in the paper) | `python -m rag_leak.probe_evidence_swap --dataset hotpot` then `... --analyze-only` |

## 2. Figures

```bash
python paper/make_figures.py          # writes paper/figures/*.pdf and *.png
python paper/check_figures.py         # no CJK, no clipping
python paper/check_tex.py             # labels, refs, table column counts
python paper/make_overleaf_zip.py     # packaged submission zip
```

## 3. Re-running the experiments from scratch [GPU]

```bash
# C-line (oracle-context), TriviaQA numeric/date pool, both construction fixes on
RAGLEAK_STRICT_DATE_ERA=1 RAGLEAK_STRICT_NUMERIC=1 python -m rag_leak.run_pipeline \
  --mode=pilot --trivia data/trivia_dn.json --nq data/empty_nq.json \
  --hotpot data/empty_hotpot.json --generator hf --proposer rule --models Qwen3-8B \
  --bits 4 --device cuda --granularity paragraph --budget 1024 --k 5 --out rag_leak/out_s6_trivia_fix_8b

# B-line (shared-corpus retrieval, k axis)
RAGLEAK_STRICT_DATE_ERA=1 RAGLEAK_STRICT_NUMERIC=1 python -m rag_leak.run_bline \
  --models Qwen3-8B --k 1,5

# Entity line (the domain-consistency constraint)
python -m rag_leak.entity_experiment build            # writes data/trivia_name.json
RAGLEAK_STRICT_ENTITY_DOMAIN=1 python -m rag_leak.run_pipeline \
  --mode=pilot --trivia data/trivia_name.json --nq data/empty_nq.json \
  --hotpot data/empty_hotpot.json --generator hf --proposer rule --models Qwen3-8B \
  --bits 4 --device cuda --granularity paragraph --budget 1024 --k 5 \
  --pilot-n 400 --out rag_leak/out_ent_new2_8b
```

Construction fixes are opt-in environment switches, and all of them default to **off**, so
that the pre-fix artifacts remain reproducible: `RAGLEAK_STRICT_DATE_ERA` (era-bucketed year
borrowing), `RAGLEAK_STRICT_NUMERIC` (numeric boundary), `RAGLEAK_STRICT_ENTITY_DOMAIN`
(domain signature + self-borrow and same-value guards, entity branch only).

## 4. Checking a re-run against the frozen artifacts

`CHECKSUMS.md` lists the MD5 of every artifact file. A re-run of the same configuration with
the same seed should reproduce the corresponding `*_substituted.jsonl` byte for byte
(the arm accuracies `*_fourarm.jsonl` are also deterministic given the same GPU and library
versions, with the one documented exception of a single TriviaQA item under 4-bit CUDA).
