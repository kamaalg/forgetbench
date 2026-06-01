# ForgetBench

[![License: Apache-2.0](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![tests](https://img.shields.io/badge/tests-15%20passing-brightgreen.svg)](tests/)
[![data](https://img.shields.io/badge/data-synthetic%20(no%20licensed%20text)-green.svg)](forgetbench/cases/cases.json)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![adapters](https://img.shields.io/badge/adapters-Mem0%20%C2%B7%20Zep%20%C2%B7%20Letta-8b5cff.svg)](forgetbench/adapters/)

**A pip-installable benchmark for *selective forgetting* in LLM memory systems.**

> **TL;DR** — Memory systems are good at *remembering*; almost none are tested on *forgetting*.
> ForgetBench gives you one number (`forget_score`, 0–1) for whether a system can **delete a fact so
> it stops surfacing** without wrecking the facts that should stay — across 4 failure axes, in ~10
> lines, $0, offline.

### Reference scores (bundled, runs offline, $0)

| System | forget_score | forget_recall | utility_preservation |
|---|---:|---:|---:|
| `KeywordMemory` — faithful store, real per-doc deletion | **1.000** | 1.000 | 1.000 |
| `LeakyMemory` — extraction-style, keeps a distilled profile | **0.000** | 0.000 | 1.000 |

`LeakyMemory` is the cautionary pattern: it keeps everything answerable (utility 1.0) but **leaks
every deleted fact** (recall 0.0) — exactly how summarization/extraction memory tends to fail, and
exactly what the benchmark surfaces. 20 cases, balanced 5 per axis; `forget_score` is the harmonic
mean of the two rates, so deleting everything can't game it.

---

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

### Benchmarking Mem0

A real adapter for the Mem0 hosted platform ships in the box (handles Mem0's
*asynchronous* extraction by polling until memories are queryable, not a blind
sleep — the lack of which makes naive runs silently score everything empty):

```python
from forgetbench.adapters.mem0_adapter import build_mem0
import forgetbench

report = forgetbench.run(build_mem0())   # needs MEM0_API_KEY + `pip install mem0ai`
print(report["forget_score"])
```

Adapters for **Zep** and **Letta** ship too, with the same one-call factory pattern:

```python
from forgetbench.adapters.zep_adapter import build_zep        # needs zep-cloud + ZEP_API_KEY
from forgetbench.adapters.letta_adapter import build_letta    # needs letta-client + a Letta server
forgetbench.run(build_zep())
forgetbench.run(build_letta())
```

All three live adapters are import-guarded (safe to import with no SDK/keys) and
handle each vendor's quirks — async graph/extraction ingest is polled until
queryable, deletion uses the vendor's real deletion path, and each case runs in a
fresh namespace/agent so cases don't contaminate one another.

## Contributing cases

Cases are plain JSON (`forgetbench/cases/cases.json`) and are **validated on
load** — `forgetbench.validate_cases(...)` (raises `CaseValidationError`) enforces
that every case has a known axis, real `delete_ids`, and **both** an "absent"
probe (something to forget) and a "present" probe (something to preserve), so a
contributed case can't accidentally make the score gameable. PRs adding cases
are welcome; run `python -m pytest -q` and they'll be checked automatically.

## Install

```bash
pip install -e .          # from a clone
python -m pytest -q       # 7 tests, runs offline
python -m forgetbench     # run the bundled reference demo
```

## Status & roadmap

v0.1 — 20 hand-authored cases (5 per axis), two reference adapters + live Mem0,
Zep, and Letta adapters, a case validator, the scoring contract, and a 15-test
suite. Cases are synthetic (no licensed data). Planned: a larger
community-contributable case set, a published cross-vendor comparison table, and
an LLM-judged retrieval check (beyond keyword coverage) for paraphrase-robust
leak detection.

Companion to the [LoCoMo memory-evaluation audit](https://github.com/kamaalg/locomo-audit).

## License

Apache-2.0. See `LICENSE`.
