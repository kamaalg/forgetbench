# ForgetBench

**A pip-installable benchmark for *selective forgetting* in LLM memory systems.**

Memory products (Mem0, Zep, Letta, and home-grown stores) are tuned to *remember*.
The hard, under-tested skill is the opposite: when you tell a memory system to
**delete a fact**, does it actually disappear from future retrieval — *without*
collateral damage to the facts that should stay? This matters for staleness
(old values resurfacing), and for "right to be forgotten" / GDPR deletion, where
"we removed the row" is not the same as "it no longer surfaces."

ForgetBench gives you one number for that, in about 10 lines:

```python
import forgetbench
from forgetbench.adapters import KeywordMemory

report = forgetbench.run(KeywordMemory())   # swap in your own system
print(forgetbench.format_report(report))
print(report["forget_score"])               # 0.0 – 1.0
```

## What it measures

For each case ForgetBench ingests a small set of facts, issues a delete, then
probes two things at once:

- **forget_recall** — of the facts that should be *gone*, how many the system
  actually removed from retrieval. (Delete nothing → 0.0.)
- **utility_preservation** — of the facts that should *survive*, how many are
  still retrievable. (Delete everything → 0.0.)
- **forget_score** — the harmonic mean (F1) of the two. **High only when a
  system forgets the right things AND keeps the rest** — so you can't game it by
  deleting everything (a delete-all system scores ~0).

Across four failure axes that real memory systems get wrong:

| Axis | What it tests |
|---|---|
| `direct` | Delete fact F, probe F directly. The floor competency. |
| `multi_hop` | Delete F that another fact is *derived from*; F's content must not leak via the derived fact. |
| `conditional` | "Delete X but keep Y" — selective deletion of an obsolete value while the current one survives. |
| `cross_domain` | Delete F, then probe an *unrelated* topic; F must not resurface (no collateral leakage). |

## Reference results (bundled, runs offline, $0)

Two reference adapters anchor the scale and ship with the package:

| System | forget_score | forget_recall | utility_preservation |
|---|---:|---:|---:|
| `KeywordMemory` (faithful store, real per-doc deletion) | **1.000** | 1.000 | 1.000 |
| `LeakyMemory` (extraction-style; keeps a distilled profile) | **0.000** | 0.000 | 1.000 |

`LeakyMemory` is the cautionary pattern: it distills facts into a per-entity
profile at ingest, and `delete()` removes the source document but **not** the
profile — so everything stays answerable (utility 1.0) while every deleted fact
leaks (forget_recall 0.0). This is how extraction/summarization-based memory
tends to fail, and it's exactly what ForgetBench is built to surface.

## Benchmarking your own system

Implement four methods (no subclassing required — it's a runtime-checkable
`Protocol`):

```python
from forgetbench import Document, QueryResult, run

class MyMemory:
    def ingest(self, documents): ...        # iterable[Document]
    def delete(self, doc_id): ...           # your REAL deletion path
    def query(self, query) -> QueryResult:  # QueryResult(retrieved=[...])
        ...
    def reset(self): ...                     # wipe between cases

print(run(MyMemory())["forget_score"])
```

The only rule: `delete` must perform your system's *real* deletion. Faking it
(filtering just the exact string) is precisely the behavior the multi-hop and
cross-domain axes are designed to catch.

## Install

```bash
pip install -e .          # from a clone
python -m pytest -q       # 7 tests, runs offline
python -m forgetbench     # run the bundled reference demo
```

## Status & roadmap

v0.1 — 12 hand-authored cases (3 per axis), two reference adapters, the scoring
contract, and a test suite. Cases are synthetic (no licensed data). Planned:
adapters for Mem0/Zep/Letta, a larger community-contributable case set, and an
LLM-judged retrieval check (beyond keyword coverage) for paraphrase-robust
leak detection.

Companion to the [LoCoMo memory-evaluation audit](https://github.com/kamaalg/locomo-audit).

## License

Apache-2.0. See `LICENSE`.
