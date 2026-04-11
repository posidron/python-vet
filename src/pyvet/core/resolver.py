"""Audit graph resolution algorithm.

Determines whether each dependency is vetted according to the required criteria.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import LockedDep, normalize_name


@dataclass
class VetResult:
    """Result for a single dependency."""
    package: str
    version: str
    vetted: bool
    reason: str  # e.g. "full-audit", "delta-chain", "exemption", "trusted", "unvetted"
    required_criteria: str = "safe-to-deploy"
    missing_criteria: list[str] = field(default_factory=list)


@dataclass
class CheckResult:
    """Aggregated result of checking all dependencies."""
    results: list[VetResult]

    @property
    def success(self) -> bool:
        return all(r.vetted for r in self.results)

    @property
    def failures(self) -> list[VetResult]:
        return [r for r in self.results if not r.vetted]

    @property
    def vetted_count(self) -> int:
        return sum(1 for r in self.results if r.vetted)


def resolve(
    deps: list[LockedDep],
    audits: dict[str, list[dict[str, Any]]],
    exemptions: dict[str, list[dict[str, Any]]],
    trusted: dict[str, list[dict[str, Any]]],
    imported_audits: dict[str, dict[str, Any]],
    criteria_graph: CriteriaGraph,
    policy: dict[str, dict[str, Any]],
    default_criteria: str,
) -> CheckResult:
    """Check all dependencies against audits, exemptions, trusted entries, and imports."""

    # Merge imported audits into a unified view
    all_audits = _merge_audits(audits, imported_audits)

    results: list[VetResult] = []
    for dep in deps:
        key = dep.key
        required = _get_required_criteria(key, policy, default_criteria)

        result = _check_single(
            dep, required, all_audits, exemptions, trusted, criteria_graph
        )
        results.append(result)

    return CheckResult(results=results)


def _merge_audits(
    local: dict[str, list[dict[str, Any]]],
    imported: dict[str, dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Merge local and imported audits into a single dict."""
    merged: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for pkg, entries in local.items():
        merged[normalize_name(pkg)].extend(entries)

    for _source_name, source_data in imported.items():
        for pkg, entries in source_data.get("audits", {}).items():
            merged[normalize_name(pkg)].extend(entries)

    return dict(merged)


def _get_required_criteria(
    pkg_key: str,
    policy: dict[str, dict[str, Any]],
    default_criteria: str,
) -> str:
    """Determine the required criteria for a given package."""
    pkg_policy = policy.get(pkg_key, {})
    return pkg_policy.get("criteria", default_criteria)


def _check_single(
    dep: LockedDep,
    required_criteria: str,
    all_audits: dict[str, list[dict[str, Any]]],
    exemptions: dict[str, list[dict[str, Any]]],
    trusted: dict[str, list[dict[str, Any]]],
    criteria_graph: CriteriaGraph,
) -> VetResult:
    """Check a single dependency."""
    key = dep.key

    entries = all_audits.get(key, [])

    # 1. Check violations first
    for entry in entries:
        violation = entry.get("violation")
        if violation and _version_matches_req(dep.version, violation):
            return VetResult(
                package=dep.name, version=dep.version,
                vetted=False, reason="violation",
                required_criteria=required_criteria,
                missing_criteria=[required_criteria],
            )

    # 2. Check full audits
    for entry in entries:
        entry_version = entry.get("version")
        entry_criteria = _normalize_criteria(entry.get("criteria"))
        if entry_version == dep.version and not entry.get("violation"):
            if _criteria_satisfied(entry_criteria, required_criteria, criteria_graph):
                return VetResult(
                    package=dep.name, version=dep.version,
                    vetted=True, reason="full-audit",
                    required_criteria=required_criteria,
                )

    # 3. Check trusted publishers
    trusted_entries = trusted.get(key, [])
    for t in trusted_entries:
        t_criteria = _normalize_criteria(t.get("criteria"))
        if _criteria_satisfied(t_criteria, required_criteria, criteria_graph):
            return VetResult(
                package=dep.name, version=dep.version,
                vetted=True, reason="trusted",
                required_criteria=required_criteria,
            )

    # 4. Check exemptions (before delta chains — simpler explanation)
    exempt_entries = exemptions.get(key, [])
    if dep.name in exemptions and key != dep.name:
        exempt_entries = exempt_entries + exemptions.get(dep.name, [])
    for ex in exempt_entries:
        if ex.get("version") == dep.version:
            ex_criteria = _normalize_criteria(ex.get("criteria"))
            if _criteria_satisfied(ex_criteria, required_criteria, criteria_graph):
                return VetResult(
                    package=dep.name, version=dep.version,
                    vetted=True, reason="exemption",
                    required_criteria=required_criteria,
                )

    # 5. Check delta chains
    if _check_delta_chain(dep, entries, exemptions, criteria_graph, required_criteria):
        return VetResult(
            package=dep.name, version=dep.version,
            vetted=True, reason="delta-chain",
            required_criteria=required_criteria,
        )

    # 6. Unvetted
    return VetResult(
        package=dep.name, version=dep.version,
        vetted=False, reason="unvetted",
        required_criteria=required_criteria,
        missing_criteria=[required_criteria],
    )


def _check_delta_chain(
    dep: LockedDep,
    entries: list[dict[str, Any]],
    exemptions: dict[str, list[dict[str, Any]]],
    criteria_graph: CriteriaGraph,
    required_criteria: str,
) -> bool:
    """Check if a delta chain exists from an audited/exempted version to dep.version."""
    key = dep.key

    # Collect all "anchored" versions (full audits or exemptions)
    anchored: set[str] = set()
    for entry in entries:
        v = entry.get("version")
        if v and not entry.get("violation") and not entry.get("delta"):
            if _criteria_satisfied(
                _normalize_criteria(entry.get("criteria")),
                required_criteria, criteria_graph
            ):
                anchored.add(v)

    for ex in exemptions.get(key, []):
        v = ex.get("version")
        if v:
            if _criteria_satisfied(
                _normalize_criteria(ex.get("criteria")),
                required_criteria, criteria_graph
            ):
                anchored.add(v)

    if not anchored:
        return False

    # Build adjacency graph from delta entries
    graph: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        delta = entry.get("delta")
        if delta and not entry.get("violation"):
            entry_criteria = _normalize_criteria(entry.get("criteria"))
            if _criteria_satisfied(entry_criteria, required_criteria, criteria_graph):
                parts = delta.split("->")
                if len(parts) == 2:
                    from_v = parts[0].strip()
                    to_v = parts[1].strip()
                    graph[from_v].add(to_v)
                    graph[to_v].add(from_v)  # deltas are bidirectional in cargo-vet

    # BFS from anchored versions to dep.version
    visited: set[str] = set()
    queue = list(anchored)
    while queue:
        current = queue.pop(0)
        if current == dep.version:
            return True
        if current in visited:
            continue
        visited.add(current)
        for neighbor in graph.get(current, set()):
            if neighbor not in visited:
                queue.append(neighbor)

    return False


def _normalize_criteria(criteria: Any) -> list[str]:
    """Normalize criteria to a list of strings."""
    if criteria is None:
        return []
    if isinstance(criteria, str):
        return [criteria]
    return list(criteria)


def _criteria_satisfied(
    provided: list[str],
    required: str,
    criteria_graph: CriteriaGraph,
) -> bool:
    """Check if provided criteria satisfy the required criteria."""
    for p in provided:
        if criteria_graph.satisfies(p, required):
            return True
    return False


def _version_matches_req(version: str, version_req: str) -> bool:
    """Simple version requirement matching.

    Supports: exact ("1.0.0"), wildcard ("*"), range (">=1.0.0"),
    and comma-separated combinations.
    """
    version_req = version_req.strip()
    if version_req == "*":
        return True

    # Handle comma-separated requirements (all must match)
    if "," in version_req:
        parts = [p.strip() for p in version_req.split(",")]
        return all(_version_matches_single(version, p) for p in parts)

    return _version_matches_single(version, version_req)


def _version_matches_single(version: str, req: str) -> bool:
    """Match a single version requirement."""
    req = req.strip()
    if req.startswith(">="):
        return _compare_versions(version, req[2:].strip()) >= 0
    elif req.startswith("<="):
        return _compare_versions(version, req[2:].strip()) <= 0
    elif req.startswith(">"):
        return _compare_versions(version, req[1:].strip()) > 0
    elif req.startswith("<"):
        return _compare_versions(version, req[1:].strip()) < 0
    elif req.startswith("==") or req.startswith("="):
        clean = req.lstrip("=").strip()
        return version == clean
    else:
        return version == req


def _compare_versions(a: str, b: str) -> int:
    """Compare two version strings numerically."""
    def parts(v: str) -> list[int]:
        result = []
        for p in v.split("."):
            try:
                result.append(int(p))
            except ValueError:
                result.append(0)
        return result

    pa, pb = parts(a), parts(b)
    # Pad to same length
    max_len = max(len(pa), len(pb))
    pa.extend([0] * (max_len - len(pa)))
    pb.extend([0] * (max_len - len(pb)))

    for x, y in zip(pa, pb):
        if x < y:
            return -1
        if x > y:
            return 1
    return 0
