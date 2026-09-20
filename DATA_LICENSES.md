# Data provenance and licences

The pools in `data/` are **derived** from public datasets. The raw upstream files are not
redistributed here; please obtain them from the original sources and cite the original
papers when you use the derived pools.

| Dataset | Upstream source | Licence / terms | What we derived |
|---|---|---|---|
| TriviaQA (`joshi2017`) | <https://nlp.cs.washington.edu/triviaqa/> | Apache-2.0 (see upstream) | `data/trivia_dn.json` (numeric/date answer pool), `data/trivia_name.json` (entity answer pool), `data/trivia-dev.json` (windowed passages) |
| HotpotQA (`yang2018`) | <https://hotpotqa.github.io/> | CC BY-SA 4.0 (see upstream) | `data/hotpot_dn.json` (numeric/date answer pool) |

Derived files are distributed for research reproducibility under the same terms as their
upstream dataset. `rag_leak/anno_*` contains human annotations produced by the authors for
this paper and is released for research use.

If you are a dataset owner and would prefer a derived file not to be redistributed, contact
the authors and it will be removed.
