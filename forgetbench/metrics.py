"""ForgetBench scoring.

Two complementary rates, then one headline number that cannot be gamed:

  - forget_recall      : of the facts that should be GONE, the fraction the
                         system actually removed from retrieval. (Delete nothing
                         -> 0.0.)
  - utility_preservation: of the facts that should SURVIVE, the fraction still
                         retrievable. (Delete everything -> 0.0.)
  - forget_score       : harmonic mean (F1) of the two. High only when the
                         system forgets the right things AND keeps the rest.

A "fact is present in retrieval" test uses keyword coverage: the fact's
keywords must appear (normalized substring) in the concatenated retrieved
passages above a threshold. This is intentionally lenient about phrasing and
strict about the fact — a forgotten fact that paraphrases back is still a leak.
"""

from __future__ import annotations

import re
from statistics import harmonic_mean


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def keywords_present(retrieved: list[str], keywords: list[str], threshold: float = 0.6) -> bool:
    """True if >= threshold of keywords appear (normalized) in retrieved text."""
    if not keywords:
        return False
    hay = normalize(" ".join(retrieved))
    if not hay:
        return False
    hits = sum(1 for k in keywords if normalize(k) in hay)
    return hits / len(keywords) >= threshold


def aggregate(case_results: list[dict]) -> dict:
    """Aggregate per-case probe outcomes into the headline ForgetBench numbers.

    Each entry in ``case_results`` is the dict produced by runner._score_case:
      {forget_total, forget_removed, preserve_total, preserve_kept, axis, ...}
    """
    f_total = sum(r["forget_total"] for r in case_results)
    f_removed = sum(r["forget_removed"] for r in case_results)
    p_total = sum(r["preserve_total"] for r in case_results)
    p_kept = sum(r["preserve_kept"] for r in case_results)

    forget_recall = f_removed / f_total if f_total else 0.0
    utility_preservation = p_kept / p_total if p_total else 0.0
    if forget_recall > 0 and utility_preservation > 0:
        forget_score = harmonic_mean([forget_recall, utility_preservation])
    else:
        forget_score = 0.0

    by_axis: dict[str, dict] = {}
    for r in case_results:
        a = r["axis"]
        d = by_axis.setdefault(
            a, {"forget_total": 0, "forget_removed": 0, "preserve_total": 0, "preserve_kept": 0, "n_cases": 0}
        )
        d["forget_total"] += r["forget_total"]
        d["forget_removed"] += r["forget_removed"]
        d["preserve_total"] += r["preserve_total"]
        d["preserve_kept"] += r["preserve_kept"]
        d["n_cases"] += 1
    for a, d in by_axis.items():
        d["forget_recall"] = d["forget_removed"] / d["forget_total"] if d["forget_total"] else 0.0
        d["utility_preservation"] = (
            d["preserve_kept"] / d["preserve_total"] if d["preserve_total"] else 0.0
        )

    return {
        "forget_score": round(forget_score, 4),
        "forget_recall": round(forget_recall, 4),
        "utility_preservation": round(utility_preservation, 4),
        "n_cases": len(case_results),
        "by_axis": {
            a: {
                "forget_recall": round(d["forget_recall"], 4),
                "utility_preservation": round(d["utility_preservation"], 4),
                "n_cases": d["n_cases"],
            }
            for a, d in by_axis.items()
        },
    }
