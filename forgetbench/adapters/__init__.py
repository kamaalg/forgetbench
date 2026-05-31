"""Reference adapters bundled with ForgetBench.

- ``KeywordMemory``: faithful store with real deletion (anchors the high end).
- ``LeakyMemory``: extraction-style memory that leaks deleted facts via a
  distilled profile (anchors the low end).
"""

from .keyword_memory import KeywordMemory
from .leaky_memory import LeakyMemory

__all__ = ["KeywordMemory", "LeakyMemory"]
