"""Mem0 adapter for ForgetBench (import-guarded, offline-safe).

This lets you benchmark a real Mem0 hosted account:

    from forgetbench.adapters.mem0_adapter import build_mem0
    import forgetbench
    forgetbench.run(build_mem0())          # needs MEM0_API_KEY + `pip install mem0ai`

Design notes (these are exactly the failure modes ForgetBench is built to find):

  * Mem0 extraction is ASYNCHRONOUS. A search issued immediately after ingest
    finds nothing, so ``ingest`` polls ``get_all`` until memories are queryable
    (bounded by MEM0_INGEST_POLL_CAP_S) instead of a blind sleep.
  * ``delete`` removes the Mem0 memory ids that Mem0 derived from the deleted
    document. But Mem0 may have *consolidated* a fact into a memory that also
    carries other facts — deleting that memory id can either over- or
    under-delete. ForgetBench measures the consequence; the adapter does not
    paper over it.
  * The module imports with no SDK and no key (so it's safe to import offline);
    ``build_mem0`` raises a clear error if the key/SDK are missing.

Each ForgetBench case uses a fresh Mem0 ``user_id`` (namespace) so cases do not
contaminate each other, and ``reset`` deletes everything this adapter created.
"""

from __future__ import annotations

import os
import time
from typing import Any, Iterable

from ..core import Document, QueryResult


class _Mem0System:
    name = "mem0"

    def __init__(self, client: Any, top_k: int = 5, user_prefix: str = "fb") -> None:
        self._client = client
        self.top_k = top_k
        self._user_prefix = user_prefix
        self._epoch = 0
        self._user_id = f"{user_prefix}-0"
        self._doc_to_mem: dict[str, list[str]] = {}

    # --- helpers ----------------------------------------------------------- #
    @staticmethod
    def _ids(add_result: Any) -> list[str]:
        if add_result is None:
            return []
        items = add_result
        if isinstance(add_result, dict):
            items = add_result.get("results", add_result.get("memories", []))
        out: list[str] = []
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict) and it.get("id"):
                    out.append(str(it["id"]))
        return out

    def _add_with_retry(self, messages: Any, metadata: dict) -> Any:
        attempts = int(os.environ.get("MEM0_ADD_RETRIES", "3"))
        last: Exception | None = None
        for i in range(attempts):
            try:
                return self._client.add(messages, user_id=self._user_id, metadata=metadata)
            except Exception as e:  # transient network/5xx
                last = e
                if i == attempts - 1:
                    break
                time.sleep(min(2.0 ** i, 8.0))
        if last is not None:
            print(f"  [mem0] add() failed after {attempts} attempts: {last}")
        return None

    def _wait_queryable(self) -> None:
        cap = float(os.environ.get("MEM0_INGEST_POLL_CAP_S", "300"))
        interval = float(os.environ.get("MEM0_INGEST_POLL_INTERVAL_S", "5"))
        deadline = time.perf_counter() + cap
        while time.perf_counter() < deadline:
            try:
                got = self._client.get_all(
                    version="v2", filters={"user_id": self._user_id}, page=1, page_size=1
                )
            except TypeError:
                try:
                    got = self._client.get_all(user_id=self._user_id)
                except Exception:
                    got = None
            except Exception:
                got = None
            items = got.get("results", got) if isinstance(got, dict) else got
            if isinstance(items, list) and items:
                return
            time.sleep(interval)

    # --- MemorySystem protocol -------------------------------------------- #
    def ingest(self, documents: Iterable[Document]) -> None:
        n = 0
        for d in documents:
            messages = [{"role": "user", "content": d.text}]
            res = self._add_with_retry(messages, {"doc_id": d.id, **d.metadata})
            self._doc_to_mem[d.id] = self._ids(res)
            n += 1
        if n:
            self._wait_queryable()

    def delete(self, doc_id: str) -> None:
        for mem_id in self._doc_to_mem.get(doc_id, []):
            try:
                self._client.delete(memory_id=mem_id)
            except Exception:
                pass
        self._doc_to_mem.pop(doc_id, None)

    def query(self, query: str) -> QueryResult:
        try:
            res = self._client.search(
                query, version="v2", filters={"user_id": self._user_id}, limit=self.top_k
            )
        except TypeError:
            res = self._client.search(query, user_id=self._user_id, limit=self.top_k)
        mems = res.get("results", res) if isinstance(res, dict) else res
        passages = [
            m.get("memory", m.get("text", "")) for m in (mems or []) if isinstance(m, dict)
        ]
        passages = [p for p in passages if p]
        return QueryResult(retrieved=passages, answer=passages[0] if passages else "")

    def reset(self) -> None:
        # Best-effort wipe of everything this adapter created in the current
        # namespace, then advance to a fresh namespace so the next case starts
        # from an empty store even if server-side deletes lag.
        for mem_ids in self._doc_to_mem.values():
            for mem_id in mem_ids:
                try:
                    self._client.delete(memory_id=mem_id)
                except Exception:
                    pass
        self._doc_to_mem.clear()
        self._epoch += 1
        self._user_id = f"{self._user_prefix}-{self._epoch}"


def build_mem0(top_k: int = 5) -> _Mem0System:
    """Construct a live Mem0 adapter, or raise with a clear message."""
    api_key = os.environ.get("MEM0_API_KEY")
    if not api_key:
        raise RuntimeError("mem0 adapter needs MEM0_API_KEY in the environment.")
    try:
        from mem0 import MemoryClient  # type: ignore
    except Exception as e:  # pragma: no cover - needs SDK
        raise RuntimeError("mem0 adapter needs `pip install mem0ai`.") from e
    return _Mem0System(MemoryClient(api_key=api_key), top_k=top_k)
