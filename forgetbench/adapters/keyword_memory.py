"""KeywordMemory — a faithful reference store with real per-document deletion.

This is the "well-behaved" reference: it stores each Document verbatim and a
``delete(doc_id)`` truly removes it, so a deleted fact is unrecoverable. It
exists to (a) give users a working example of the MemorySystem protocol and
(b) anchor the top of the ForgetBench scale — a system that stores facts
atomically and deletes them atomically should score near 1.0.

Retrieval is lexical: return the documents whose tokens overlap the query
most, top-k. No LLM, no network — runs anywhere.
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


class KeywordMemory:
    name = "keyword_memory"

    def __init__(self, top_k: int = 3) -> None:
        self.top_k = top_k
        self._docs: dict[str, Document] = {}

    def ingest(self, documents: Iterable[Document]) -> None:
        for d in documents:
            self._docs[d.id] = d

    def delete(self, doc_id: str) -> None:
        self._docs.pop(doc_id, None)  # real, atomic removal

    def query(self, query: str) -> QueryResult:
        q = _tokens(query)
        scored = []
        for d in self._docs.values():
            overlap = len(q & _tokens(d.text))
            if overlap:
                scored.append((overlap, d))
        scored.sort(key=lambda x: -x[0])
        top = [d.text for _, d in scored[: self.top_k]]
        return QueryResult(retrieved=top, answer=top[0] if top else "")

    def reset(self) -> None:
        self._docs.clear()
