"""pyvet explain-audit — show the audit path for a package."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from pyvet.core.config import (
    load_config, load_audits,
    get_default_criteria, get_exemptions, get_policy,
    get_audits, get_criteria_table, get_trusted,
)
from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import normalize_name
from pyvet.core.resolver import _normalize_criteria, _criteria_satisfied
from pyvet.utils.ui import console, print_success, print_error, print_info


def run(args: object) -> int:
    project_dir = Path.cwd()

    package: str = getattr(args, "package", "")
    version: str | None = getattr(args, "version", None)
    criteria: str | None = getattr(args, "criteria", None)

    if not package:
        print_error("Package name is required.")
        return 1

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    criteria_graph = CriteriaGraph()
    criteria_graph.load_from_audits(get_criteria_table(audits_doc))

    default_criteria = get_default_criteria(config)
    if not criteria:
        criteria = default_criteria

    audits = get_audits(audits_doc)
    exemptions = get_exemptions(config)
    trusted = get_trusted(audits_doc)
    policy = get_policy(config)

    key = normalize_name(package)
    entries = audits.get(key, []) + audits.get(package, [])

    console.print()
    console.print(
        f"[bold]Audit path for {package}"
        + (f"=={version}" if version else "")
        + f" (criteria: {criteria})[/]"
    )
    console.print()

    # Show full audits
    full_audits = [
        e for e in entries
        if e.get("version") and not e.get("violation") and not e.get("delta")
    ]
    if full_audits:
        console.print("[bold]Full audits:[/]")
        for a in full_audits:
            c = a.get("criteria", "?")
            v = a.get("version", "?")
            who = a.get("who", "unknown")
            satisfies = _criteria_satisfied(
                _normalize_criteria(c), criteria, criteria_graph
            )
            mark = "[green]✓[/]" if satisfies else "[dim]○[/]"
            console.print(f"  {mark} {v} — {c} (by {who})")
    else:
        console.print("[dim]No full audits.[/]")

    # Show delta audits
    deltas = [e for e in entries if e.get("delta") and not e.get("violation")]
    if deltas:
        console.print()
        console.print("[bold]Delta audits:[/]")
        for d in deltas:
            c = d.get("criteria", "?")
            delta = d.get("delta", "?")
            who = d.get("who", "unknown")
            satisfies = _criteria_satisfied(
                _normalize_criteria(c), criteria, criteria_graph
            )
            mark = "[green]✓[/]" if satisfies else "[dim]○[/]"
            console.print(f"  {mark} {delta} — {c} (by {who})")

    # Show wildcard audits
    wildcards = audits_doc.get("wildcard-audits", {}).get(key, [])
    if not wildcards:
        wildcards = audits_doc.get("wildcard-audits", {}).get(package, [])
    if wildcards:
        console.print()
        console.print("[bold]Wildcard audits:[/]")
        for w in wildcards:
            c = w.get("criteria", "?")
            user = w.get("user-login", w.get("user-id", "?"))
            start = w.get("start", "?")
            end = w.get("end", "?")
            console.print(f"  ● {c} — by user {user} ({start} to {end})")

    # Show exemptions
    exempt = exemptions.get(key, []) + exemptions.get(package, [])
    if exempt:
        console.print()
        console.print("[bold]Exemptions:[/]")
        for ex in exempt:
            v = ex.get("version", "?")
            c = ex.get("criteria", "?")
            console.print(f"  ⊘ {v} — {c}")

    # Show trusted
    trust = trusted.get(key, []) + trusted.get(package, [])
    if trust:
        console.print()
        console.print("[bold]Trusted publishers:[/]")
        for t in trust:
            user = t.get("user-login", "?")
            c = t.get("criteria", "?")
            start = t.get("start", "?")
            end = t.get("end", "?")
            console.print(f"  ★ {user} — {c} ({start} to {end})")

    # Show violations
    violations = [e for e in entries if e.get("violation")]
    if violations:
        console.print()
        console.print("[bold red]Violations:[/]")
        for v in violations:
            vr = v.get("violation", "?")
            c = v.get("criteria", "?")
            who = v.get("who", "unknown")
            console.print(f"  [red]✗ {vr} — {c} (by {who})[/]")

    # Build and show the delta chain path if version is specified
    if version:
        console.print()
        path = _find_delta_path(entries, exemptions, key, version, criteria, criteria_graph)
        if path:
            console.print("[bold green]Resolved path:[/]")
            console.print(f"  {' → '.join(path)}")
        else:
            # Check if directly vetted
            for a in full_audits:
                if a.get("version") == version:
                    if _criteria_satisfied(
                        _normalize_criteria(a.get("criteria")), criteria, criteria_graph
                    ):
                        console.print("[bold green]Directly vetted via full audit.[/]")
                        return 0
            for ex in exempt:
                if ex.get("version") == version:
                    console.print("[bold yellow]Vetted via exemption.[/]")
                    return 0
            if trust:
                console.print("[bold green]Vetted via trusted publisher.[/]")
                return 0
            console.print("[bold red]No audit path found![/]")

    console.print()
    return 0


def _find_delta_path(
    entries: list[dict[str, Any]],
    exemptions: dict[str, list[dict[str, Any]]],
    key: str,
    target_version: str,
    criteria: str,
    criteria_graph: CriteriaGraph,
) -> list[str] | None:
    """Find and return the delta chain path from an anchor to the target version."""
    anchored: set[str] = set()
    for entry in entries:
        v = entry.get("version")
        if v and not entry.get("violation") and not entry.get("delta"):
            if _criteria_satisfied(
                _normalize_criteria(entry.get("criteria")), criteria, criteria_graph
            ):
                anchored.add(v)
    for ex in exemptions.get(key, []):
        v = ex.get("version")
        if v and _criteria_satisfied(
            _normalize_criteria(ex.get("criteria")), criteria, criteria_graph
        ):
            anchored.add(v)

    if not anchored:
        return None

    graph: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        delta = entry.get("delta")
        if delta and not entry.get("violation"):
            if _criteria_satisfied(
                _normalize_criteria(entry.get("criteria")), criteria, criteria_graph
            ):
                parts = delta.split("->")
                if len(parts) == 2:
                    from_v, to_v = parts[0].strip(), parts[1].strip()
                    graph[from_v].add(to_v)
                    graph[to_v].add(from_v)

    # BFS with path tracking
    from collections import deque
    for anchor in anchored:
        visited: set[str] = set()
        queue: deque[list[str]] = deque([[anchor]])
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == target_version:
                return path
            if current in visited:
                continue
            visited.add(current)
            for neighbor in graph.get(current, set()):
                if neighbor not in visited:
                    queue.append(path + [neighbor])

    return None
