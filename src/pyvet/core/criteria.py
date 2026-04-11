"""Criteria definitions and implication graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CriteriaDef:
    name: str
    description: str
    implies: list[str] = field(default_factory=list)


# Built-in criteria matching cargo-vet, adapted for Python.
SAFE_TO_RUN = CriteriaDef(
    name="safe-to-run",
    description=(
        "This package can be installed and executed on a local workstation or "
        "in controlled automation without surprising consequences, such as:\n"
        "- Reading or writing data from sensitive or unrelated parts of the filesystem\n"
        "- Installing software or reconfiguring the device\n"
        "- Connecting to untrusted network endpoints\n"
        "- Misuse of system resources (e.g. cryptocurrency mining)"
    ),
)

SAFE_TO_DEPLOY = CriteriaDef(
    name="safe-to-deploy",
    description=(
        "This package will not introduce a serious security vulnerability to "
        "production software exposed to untrusted input.\n\n"
        "Auditors must review enough to fully reason about the behavior of any "
        "native extensions (C/C++/Rust via FFI), use of eval/exec, dynamic "
        "imports, and usage of powerful stdlib modules (os, subprocess, socket, "
        "ctypes). For any reasonable usage, an attacker must not be able to "
        "manipulate runtime behavior in an exploitable or surprising way."
    ),
    implies=["safe-to-run"],
)

BUILTIN_CRITERIA = {
    "safe-to-run": SAFE_TO_RUN,
    "safe-to-deploy": SAFE_TO_DEPLOY,
}


class CriteriaGraph:
    """Manages criteria and their implication relationships."""

    def __init__(self) -> None:
        self._criteria: dict[str, CriteriaDef] = dict(BUILTIN_CRITERIA)

    def add(self, criteria: CriteriaDef) -> None:
        self._criteria[criteria.name] = criteria

    def load_from_audits(self, criteria_table: dict[str, Any]) -> None:
        """Load custom criteria from the [criteria] table in audits.toml."""
        for name, entry in criteria_table.items():
            if name in BUILTIN_CRITERIA:
                continue
            implies_raw = entry.get("implies", [])
            if isinstance(implies_raw, str):
                implies_raw = [implies_raw]
            self.add(CriteriaDef(
                name=name,
                description=entry.get("description", ""),
                implies=implies_raw,
            ))

    def expands_to(self, criteria: str) -> set[str]:
        """Return the full set of criteria implied by the given criteria (inclusive)."""
        result: set[str] = set()
        stack = [criteria]
        while stack:
            c = stack.pop()
            if c in result:
                continue
            result.add(c)
            defn = self._criteria.get(c)
            if defn:
                stack.extend(defn.implies)
        return result

    def satisfies(self, provided: str | list[str], required: str) -> bool:
        """Check whether the provided criteria satisfy the required criteria."""
        if isinstance(provided, str):
            provided = [provided]
        expanded: set[str] = set()
        for p in provided:
            expanded |= self.expands_to(p)
        return required in expanded

    def get(self, name: str) -> CriteriaDef | None:
        return self._criteria.get(name)

    @property
    def all_names(self) -> list[str]:
        return list(self._criteria.keys())
