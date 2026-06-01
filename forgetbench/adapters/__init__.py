"""Adapters bundled with ForgetBench.

Reference adapters (offline, no deps — anchor the scale and serve as examples):
- ``KeywordMemory``: faithful store with real deletion (anchors the high end).
- ``LeakyMemory``: extraction-style memory that leaks deleted facts via a
  distilled profile (anchors the low end).

Live vendor adapters (import-guarded; require the vendor SDK + credentials, so
they are imported lazily via their ``build_*`` factories, not re-exported here):
- ``forgetbench.adapters.mem0_adapter.build_mem0``  (needs ``mem0ai`` + MEM0_API_KEY)
- ``forgetbench.adapters.zep_adapter.build_zep``    (needs ``zep-cloud`` + ZEP_API_KEY)
- ``forgetbench.adapters.letta_adapter.build_letta`` (needs ``letta-client`` + a Letta server)
"""

from .keyword_memory import KeywordMemory
from .leaky_memory import LeakyMemory

__all__ = ["KeywordMemory", "LeakyMemory"]
