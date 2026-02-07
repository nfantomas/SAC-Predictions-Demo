from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ValidationIssue:
    message: str
    code: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    errors: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)
    clamps: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def summarize_warnings(
    warnings: Iterable[str],
    clamps: Iterable[str],
    normalizations: Iterable[str],
    max_items: int = 5,
) -> Tuple[List[str], List[str]]:
    """
    Return (summary, details) with stable deduplication.
    Summary is capped for UI readability; details keep all deduped items.
    """
    details: List[str] = []
    seen = set()
    for group in (normalizations, clamps, warnings):
        for raw in group:
            msg = (raw or "").strip()
            if not msg:
                continue
            if msg in seen:
                continue
            seen.add(msg)
            details.append(msg)
    return details[:max_items], details
