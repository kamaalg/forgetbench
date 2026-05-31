"""LeakyMemory — a reference that models how extraction-based memory leaks.

Real LLM memory products (Mem0/Zep-style) do not store your sentences verbatim;
they distill facts into a consolidated per-entity representation. The failure
this models: ``delete(doc_id)`` removes the *source document*, but the distilled
profile that already absorbed the fact is left untouched — so the "forgotten"
fact still surfaces through the profile.

LeakyMemory builds a per-entity profile string at ingest by concatenating every
fact about that entity, and retrieval returns that profile. Deleting a document
removes it from the raw store but NOT from the profile. It therefore preserves
utility (everything is still answerable) while *failing to forget* — which is
exactly the pattern ForgetBench is built to expose. It anchors the low end of
the scale.
"""

from __future__ import annotations

import re
from typing import Iterable

from ..core import Document, QueryResult

_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "what", "who", "where", "when",
    "does", "do", "did", "of", "for", "to", "in", "on", "at", "his", "her", "their",
    "and", "or", "any", "give", "me", "tell", "about", "you", "know", "with",
    "including", "general", "profile", "summarize", "everything", "background",
}


def _tokens(text: str) -> set[str]:
    return {t for t in re.sub(r"[^\w\s]", " ", text.lower()).split() if t not in _STOP}


def _entity_of(doc: Document) -> str:
    return str(doc.metadata.get("entity", doc.id))


class LeakyMemory:
    name = "leaky_memory"

    def __init__(self, top_k: int = 3) -> None:
        self.top_k = top_k
        self._docs: dict[str, Document] = {}
        # The distilled, consolidated profile per entity — never pruned on delete.
        self._profiles: dict[str, list[str]] = {}

    def ingest(self, documents: Iterable[Document]) -> None:
        for d in documents:
            self._docs[d.id] = d
            self._profiles.setdefault(_entity_of(d), []).append(d.text)

    def delete(self, doc_id: str) -> None:
        # Removes the raw doc but leaves the distilled profile intact — the leak.
        self._docs.pop(doc_id, None)

    def query(self, query: str) -> QueryResult:
        q = _tokens(query)
        scored = []
        for entity, facts in self._profiles.items():
            blob = " ".join(facts)
            overlap = len(q & (_tokens(blob) | _tokens(entity)))
            if overlap:
                scored.append((overlap, blob))
        scored.sort(key=lambda x: -x[0])
        top = [blob for _, blob in scored[: self.top_k]]
        return QueryResult(retrieved=top, answer=top[0] if top else "")

    def reset(self) -> None:
        self._docs.clear()
        self._profiles.clear()
