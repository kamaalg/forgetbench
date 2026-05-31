"""`python -m forgetbench` — run the bundled reference adapters and print scores.

This is the 10-second demo: it shows a faithful store scoring ~1.0 and an
extraction-style store leaking deleted facts (~0.0), so you can see what the
benchmark rewards before wiring in your own system.
"""

from __future__ import annotations

import forgetbench
from forgetbench.adapters import KeywordMemory, LeakyMemory


def main() -> None:
    for label, system in [
        ("KeywordMemory (faithful store)", KeywordMemory()),
        ("LeakyMemory (extraction-style)", LeakyMemory()),
    ]:
        print(f"\n### {label}")
        report = forgetbench.run(system)
        print(forgetbench.format_report(report))


if __name__ == "__main__":
    main()
