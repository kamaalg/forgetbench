"""Letta (MemGPT) adapter for ForgetBench (import-guarded, offline-safe).

Benchmark a Letta server's forgetting behaviour:

    from forgetbench.adapters.letta_adapter import build_letta
    import forgetbench
    forgetbench.run(build_letta())   # needs a Letta server + `pip install letta-client`
                                     # LETTA_BASE_URL (default http://localhost:8283)
                                     # and optionally LETTA_API_KEY for Letta Cloud.

Letta stores memory as archival-memory passages attached to an agent. A fact is a
passage; ``delete`` removes the passage by id — but if the agent's *core memory*
or a summary already absorbed the fact, it can still surface. ForgetBench measures
that. Each case uses a fresh agent so cases are isolated; ``reset`` deletes the
agent it created.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

from ..core import Document, QueryResult


class _LettaSystem:
    name = "letta"

    def __init__(self, client: Any, top_k: int = 5) -> None:
        self._client = client
        self.top_k = top_k
        self._agent_id: str | None = None
        self._doc_to_passage: dict[str, list[str]] = {}
        self._new_agent()

    # --- helpers ----------------------------------------------------------- #
    def _new_agent(self) -> None:
        # Create a minimal agent to hold archival memory. SDK shapes vary; try the
        # common ones. We do not attach an LLM persona beyond defaults — we only
        # read back archival passages, so generation config is irrelevant here.
        for call in (
            lambda: self._client.agents.create(name=None, memory_blocks=[]),
            lambda: self._client.agents.create(),
        ):
            try:
                agent = call()
                self._agent_id = getattr(agent, "id", None) or (agent.get("id") if isinstance(agent, dict) else None)
                if self._agent_id:
                    return
            except Exception:
                continue

    @staticmethod
    def _passage_id(res: Any) -> str | None:
        # insert returns the created passage(s)
        if res is None:
            return None
        item = res[0] if isinstance(res, list) and res else res
        for attr in ("id", "uuid"):
            v = getattr(item, attr, None)
            if v:
                return str(v)
        if isinstance(item, dict):
            for k in ("id", "uuid"):
                if item.get(k):
                    return str(item[k])
        return None

    # --- MemorySystem protocol -------------------------------------------- #
    def ingest(self, documents: Iterable[Document]) -> None:
        if not self._agent_id:
            self._new_agent()
        for d in documents:
            res = None
            for call in (
                lambda: self._client.agents.passages.create(agent_id=self._agent_id, text=d.text),
                lambda: self._client.agents.archival_memory.insert(agent_id=self._agent_id, memory=d.text),
            ):
                try:
                    res = call()
                    break
                except Exception:
                    continue
            pid = self._passage_id(res)
            self._doc_to_passage[d.id] = [pid] if pid else []

    def delete(self, doc_id: str) -> None:
        for pid in self._doc_to_passage.get(doc_id, []):
            for call in (
                lambda: self._client.agents.passages.delete(agent_id=self._agent_id, memory_id=pid),
                lambda: self._client.agents.archival_memory.delete(agent_id=self._agent_id, memory_id=pid),
            ):
                try:
                    call()
                    break
                except Exception:
                    continue
        self._doc_to_passage.pop(doc_id, None)

    def query(self, query: str) -> QueryResult:
        passages: list[str] = []
        for call in (
            lambda: self._client.agents.passages.list(agent_id=self._agent_id, search=query, limit=self.top_k),
            lambda: self._client.agents.archival_memory.search(agent_id=self._agent_id, query=query, count=self.top_k),
            lambda: self._client.agents.passages.list(agent_id=self._agent_id, limit=self.top_k),
        ):
            try:
                res = call()
            except Exception:
                continue
            for p in (res or []):
                txt = getattr(p, "text", None) or getattr(p, "content", None) or (
                    p.get("text") if isinstance(p, dict) else None
                )
                if txt:
                    passages.append(str(txt))
            if passages:
                break
        return QueryResult(retrieved=passages[: self.top_k], answer=passages[0] if passages else "")

    def reset(self) -> None:
        if self._agent_id:
            try:
                self._client.agents.delete(agent_id=self._agent_id)
            except Exception:
                pass
        self._doc_to_passage.clear()
        self._agent_id = None
        self._new_agent()


def build_letta(top_k: int = 5) -> _LettaSystem:
    """Construct a live Letta adapter, or raise with a clear message."""
    try:
        from letta_client import Letta  # type: ignore
    except Exception as e:  # pragma: no cover - needs SDK
        raise RuntimeError("letta adapter needs `pip install letta-client`.") from e
    base_url = os.environ.get("LETTA_BASE_URL", "http://localhost:8283")
    api_key = os.environ.get("LETTA_API_KEY")
    try:
        client = Letta(token=api_key, base_url=base_url) if api_key else Letta(base_url=base_url)
    except Exception as e:  # pragma: no cover - needs server
        raise RuntimeError(
            f"could not connect to Letta at {base_url} (set LETTA_BASE_URL / LETTA_API_KEY): {e}"
        ) from e
    return _LettaSystem(client, top_k=top_k)
