"""pyvet check — verify all dependencies are vetted."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pyvet.core.config import (
    load_config, load_audits,
    get_default_criteria, get_exemptions, get_policy,
    get_audits, get_criteria_table, get_trusted,
    get_imports_config, get_wildcard_audits,
)
from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import detect_and_parse_lockfile
from pyvet.core.resolver import resolve, VetResult
from pyvet.core.imports import load_imports_lock, refresh_imports
from pyvet.utils.ui import (
    console, print_success, print_error, print_info, make_table,
)


def run(args: object) -> int:
    project_dir = Path.cwd()
    locked: bool = getattr(args, "locked", False)
    frozen: bool = getattr(args, "frozen", False)
    output_format: str = getattr(args, "output_format", "human")

    # Load config and audits
    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    if not config and not audits_doc:
        print_error(
            "No supply-chain directory found. Run [bold]pyvet init[/] first."
        )
        return 1

    # Parse lockfile
    try:
        deps = detect_and_parse_lockfile(project_dir)
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    if not deps:
        print_success("No third-party dependencies to vet.")
        return 0

    # Build criteria graph
    criteria_graph = CriteriaGraph()
    criteria_table = get_criteria_table(audits_doc)
    criteria_graph.load_from_audits(criteria_table)

    # Load audit data
    audits = get_audits(audits_doc)
    exemptions = get_exemptions(config)
    trusted = get_trusted(audits_doc)
    policy = get_policy(config)
    default_criteria = get_default_criteria(config)
    imports_config = get_imports_config(config)
    wildcard_audits = get_wildcard_audits(audits_doc)

    # Load imported audits — refresh unless --locked/--frozen
    if frozen or locked:
        imported_audits = _load_cached_imports(project_dir, imports_config)
    elif imports_config:
        try:
            imported_audits = refresh_imports(project_dir, imports_config)
        except Exception:
            imported_audits = _load_cached_imports(project_dir, imports_config)
    else:
        imported_audits = {}

    # Resolve
    result = resolve(
        deps=deps,
        audits=audits,
        exemptions=exemptions,
        trusted=trusted,
        imported_audits=imported_audits,
        criteria_graph=criteria_graph,
        policy=policy,
        default_criteria=default_criteria,
        wildcard_audits=wildcard_audits,
    )

    # JSON output
    if output_format == "json":
        return _output_json(result)

    # Human output
    console.print()
    if result.success:
        print_success(
            f"Vetting passed! All {result.vetted_count} dependencies are vetted."
        )
        _show_summary_table(result.results)
        return 0
    else:
        print_error("Vetting Failed!")
        console.print()
        console.print(
            f"  [bold]{len(result.failures)}[/] unvetted dependencies "
            f"(out of {len(result.results)} total):"
        )
        console.print()

        for f in result.failures:
            console.print(
                f"    [red]✗[/] {f.package}=={f.version} "
                f"missing [bold]{f.required_criteria}[/]"
            )

        console.print()
        console.print(
            "  Use [bold]pyvet certify[/] to record audits, "
            "or [bold]pyvet suggest[/] for recommendations."
        )

        _show_summary_table(result.results)
        return 1


def _output_json(result) -> int:
    data = {
        "success": result.success,
        "vetted_count": result.vetted_count,
        "failure_count": len(result.failures),
        "results": [
            {
                "package": r.package,
                "version": r.version,
                "vetted": r.vetted,
                "reason": r.reason,
                "required_criteria": r.required_criteria,
                "missing_criteria": r.missing_criteria,
            }
            for r in result.results
        ],
    }
    print(json.dumps(data, indent=2))
    return 0 if result.success else 1


def _show_summary_table(results: list[VetResult]) -> None:
    console.print()
    table = make_table(
        "Dependency Audit Status",
        [("Package", "cyan"), ("Version", ""), ("Status", ""), ("Reason", "dim")],
    )

    for r in sorted(results, key=lambda x: (x.vetted, x.package)):
        status = "[green]✓ vetted[/]" if r.vetted else "[red]✗ UNVETTED[/]"
        table.add_row(r.package, r.version, status, r.reason)

    console.print(table)


def _load_cached_imports(
    project_dir: Path,
    imports_config: dict,
) -> dict:
    """Load imported audits from the imports.lock cache.

    This doesn't re-fetch; it just reads whatever is cached.
    For a full refresh, use `pyvet import fetch`.
    """
    # If there's an imports.lock, try to parse it for cached audit data.
    # The current lock format only stores metadata, not the full audits.
    # For Phase 3 we'll store the actual audit data in the lock file.
    # For now, return empty.
    return {}
