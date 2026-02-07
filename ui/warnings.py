from __future__ import annotations

from typing import Iterable, Tuple


def summarize_warnings(
    warnings: Iterable[str],
    clamps: Iterable[str],
    normalizations: Iterable[str],
    max_items: int = 5,
) -> Tuple[list[str], list[str]]:
    details: list[str] = []
    for group in (warnings, clamps, normalizations):
        for msg in group:
            if msg and msg not in details:
                details.append(msg)
    summary = details[:max_items]
    return summary, details
