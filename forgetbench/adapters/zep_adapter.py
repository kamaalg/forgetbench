"""Zep adapter for ForgetBench (import-guarded, offline-safe).

Benchmark a real Zep Cloud account's forgetting behaviour:

    from forgetbench.adapters.zep_adapter import build_zep
    import forgetbench
    forgetbench.run(build_zep())          # needs ZEP_API_KEY + `pip install zep-cloud`

Why Zep is interesting for a *forgetting* benchmark: Zep distills messages into a
temporal knowledge graph (entity/edge facts), so a fact lives as graph edges, not
as the original sentence. Deleting "the document" is ambiguous — the adapter
deletes the graph episode it created for that document, but edges the graph
already derived may persist. ForgetBench measures that consequence rather than
hiding it.

Design notes mirroring the failure modes the benchmark targets:
  * Graph ingestion is asynchronous; ``ingest`` polls ``graph.search`` until the
    just-added episodes are queryable (bounded by ZEP_INGEST_POLL_CAP_S).
  * Each case uses a fresh graph_id namespace so cases don't contaminate.
  * ``delete`` removes the episodes this adapter created for a doc id.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable

from ..core import Document, QueryResult


class _ZepSystem:
    name = "zep"

    def __init__(self, client: Any, top_k: int = 5, graph_prefix: str = "fb") -> None:
        self._client = client
        self.top_k = top_k
        self._graph_prefix = graph_prefix
        self._epoch = 0
        self._graph_id = f"{graph_prefix}-0"
        self._doc_to_episode: dict[str, list[str]] = {}
        self._ensure_graph()

    # --- helpers ----------------------------------------------------------- #
    def _ensure_graph(self) -> None:
        # Zep Cloud groups facts under a graph_id (a.k.a. group_id in some SDK
        # versions). Create it if the SDK exposes a create call; ignore if it
        # already exists or the call shape differs across versions.
        for attempt in (
            lambda: self._client.graph.create(graph_id=self._graph_id),
            lambda: self._client.graph.create(group_id=self._graph_id),
        ):
            try:
                attempt()
                return
            except Exception:
                continue

    @staticmethod
    def _episode_id(res: Any) -> str | None:
        if res is None:
            return None
        for attr in ("uuid", "uuid_", "id"):
            v = getattr(res, attr, None)
            if v:
                return str(v)
        if isinstance(res, dict):
            for k in ("uuid", "uuid_", "id"):
                if res.get(k):
                    return str(res[k])
        return None

    def _add_with_retry(self, text: str) -> Any:
        attempts = int(os.environ.get("ZEP_ADD_RETRIES", "3"))
        last: Exception | None = None
        for i in range(attempts):
            try:
                return self._client.graph.add(graph_id=self._graph_id, type="text", data=text)
            except TypeError:
                try:
                    return self._client.graph.add(group_id=self._graph_id, type="text", data=text)
                except Exception as e:
                    last = e
            except Exception as e:
                last = e
            time.sleep(min(2.0 ** i, 8.0))
        if last is not None:
            print(f"  [zep] graph.add failed after {attempts} attempts: {last}")
        return None

    def _search(self, query: str) -> list[str]:
        for call in (
            lambda: self._client.graph.search(graph_id=self._graph_id, query=query, limit=self.top_k),
            lambda: self._client.graph.search(group_id=self._graph_id, query=query, limit=self.top_k),
        ):
            try:
                res = call()
            except Exception:
                continue
            return self._facts(res)
        return []

    @staticmethod
    def _facts(res: Any) -> list[str]:
        out: list[str] = []
        edges = getattr(res, "edges", None)
        if edges:
            for e in edges:
                f = getattr(e, "fact", None) or (e.get("fact") if isinstance(e, dict) else None)
                if f:
                    out.append(str(f))
        nodes = getattr(res, "nodes", None)
        if nodes:
            for n in nodes:
                s = getattr(n, "summary", None) or (n.get("summary") if isinstance(n, dict) else None)
                if s:
                    out.append(str(s))
        return out

    def _wait_queryable(self, sentinel: str) -> None:
        cap = float(os.environ.get("ZEP_INGEST_POLL_CAP_S", "300"))
        interval = float(os.environ.get("ZEP_INGEST_POLL_INTERVAL_S", "5"))
        deadline = time.perf_counter() + cap
        while time.perf_counter() < deadline:
            if self._search(sentinel):
                return
            time.sleep(interval)

    # --- MemorySystem protocol -------------------------------------------- #
    def ingest(self, documents: Iterable[Document]) -> None:
        docs = list(documents)
        for d in docs:
            res = self._add_with_retry(d.text)
            eid = self._episode_id(res)
            self._doc_to_episode[d.id] = [eid] if eid else []
        if docs:
            # Poll on a distinctive token from the last document so we wait for the
            # async graph build, not a blind sleep.
            self._wait_queryable(docs[-1].text)

    def delete(self, doc_id: str) -> None:
        for eid in self._doc_to_episode.get(doc_id, []):
            for call in (
                lambda: self._client.graph.episode.delete(uuid_=eid),
                lambda: self._client.graph.episode.delete(uuid=eid),
                lambda: self._client.graph.delete_episode(uuid_=eid),
            ):
                try:
                    call()
                    break
                except Exception:
                    continue
        self._doc_to_episode.pop(doc_id, None)

    def query(self, query: str) -> QueryResult:
        passages = self._search(query)
        return QueryResult(retrieved=passages, answer=passages[0] if passages else "")

    def reset(self) -> None:
        self._doc_to_episode.clear()
        self._epoch += 1
        self._graph_id = f"{self._graph_prefix}-{self._epoch}"
        self._ensure_graph()


def build_zep(top_k: int = 5) -> _ZepSystem:
    """Construct a live Zep adapter, or raise with a clear message."""
    api_key = os.environ.get("ZEP_API_KEY")
    if not api_key:
        raise RuntimeError("zep adapter needs ZEP_API_KEY in the environment.")
    try:
        from zep_cloud.client import Zep  # type: ignore
    except Exception:
        try:
            from zep_cloud import Zep  # type: ignore
        except Exception as e:  # pragma: no cover - needs SDK
            raise RuntimeError("zep adapter needs `pip install zep-cloud`.") from e
    return _ZepSystem(Zep(api_key=api_key), top_k=top_k)
