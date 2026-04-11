"""pyvet suggest — recommend lowest-effort audits."""

from __future__ import annotations

from pathlib import Path

from pyvet.core.config import (
    load_config, load_audits,
    get_default_criteria, get_exemptions, get_audits, get_criteria_table,
    get_policy, get_trusted, get_imports_config, get_wildcard_audits,
)
from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import detect_and_parse_lockfile
from pyvet.core.resolver import resolve
from pyvet.utils.ui import console, print_info, print_warning, make_table


def run(args: object) -> int:
    project_dir = Path.cwd()

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    try:
        deps = detect_and_parse_lockfile(project_dir)
    except FileNotFoundError as e:
        print_warning(str(e))
        return 1

    criteria_graph = CriteriaGraph()
    criteria_graph.load_from_audits(get_criteria_table(audits_doc))

    default_criteria = get_default_criteria(config)
    audits = get_audits(audits_doc)
    exemptions = get_exemptions(config)
    trusted = get_trusted(audits_doc)
    policy = get_policy(config)
    wildcard_audits = get_wildcard_audits(audits_doc)

    # Resolve with exemptions removed (suggest=false entries kept)
    suggestable_exemptions: dict = {}
    kept_exemptions: dict = {}
    for pkg, entries in exemptions.items():
        suggest_entries = [e for e in entries if e.get("suggest", True)]
        no_suggest = [e for e in entries if not e.get("suggest", True)]
        if suggest_entries:
            suggestable_exemptions[pkg] = suggest_entries
        if no_suggest:
            kept_exemptions[pkg] = no_suggest

    # Run resolve without suggestable exemptions to see what's truly unvetted
    result = resolve(
        deps=deps,
        audits=audits,
        exemptions=kept_exemptions,
        trusted=trusted,
        imported_audits={},
        criteria_graph=criteria_graph,
        policy=policy,
        default_criteria=default_criteria,
        wildcard_audits=wildcard_audits,
    )

    unvetted = result.failures

    if not unvetted:
        print_info("All dependencies are fully audited. Nothing to suggest.")
        return 0

    console.print()
    table = make_table(
        "Suggested Audits",
        [
            ("Priority", ""),
            ("Package", "cyan"),
            ("Version", ""),
            ("Action", ""),
            ("Est. Lines", ""),
            ("Criteria", "dim"),
        ],
    )

    suggestions: list[tuple[int, str, str, str, str, str]] = []
    total_lines = 0

    for r in sorted(unvetted, key=lambda x: x.package):
        pkg_audits = audits.get(r.package, [])
        audited_versions = [
            a["version"] for a in pkg_audits
            if "version" in a and "violation" not in a
        ]

        # Was this originally exempted?
        was_exempted = r.package in suggestable_exemptions
        priority = 2 if was_exempted else 1

        if audited_versions:
            closest = audited_versions[-1]
            action = f"pyvet diff {r.package} {closest} {r.version}"
            est = "~delta"
        else:
            action = f"pyvet inspect {r.package} {r.version}"
            est = "—"

        # Try to estimate line count from PyPI
        est_lines = _estimate_lines(r.package, r.version)
        if est_lines is not None:
            est = str(est_lines)
            total_lines += est_lines

        suggestions.append((
            priority, r.package, r.version, action, est, r.required_criteria,
        ))

    for priority, pkg, ver, action, est, criteria in sorted(suggestions):
        priority_str = "[red]HIGH[/]" if priority == 1 else "[yellow]MEDIUM[/]"
        table.add_row(priority_str, pkg, ver, action, est, criteria)

    console.print(table)

    console.print()
    backlog_str = f"  estimated audit backlog: {total_lines} lines" if total_lines else ""
    print_info(
        f"{len(unvetted)} unvetted dependencies need auditing."
        + (f"\n{backlog_str}" if backlog_str else "")
        + "\n  Use [bold]pyvet certify[/] to record audits."
    )

    return 0


def _estimate_lines(package: str, version: str) -> int | None:
    """Try to estimate the number of Python source lines in a package."""
    try:
        from pyvet.pypi.client import get_package_info
        info = get_package_info(package, version)
        # Use sdist size as a rough proxy: ~40 bytes per line of Python
        if info.sdist_url:
            import httpx
            resp = httpx.head(info.sdist_url, follow_redirects=True, timeout=10)
            content_length = resp.headers.get("content-length")
            if content_length:
                size = int(content_length)
                # Compressed, so estimate ~3x expansion, ~40 bytes/line
                return max(1, size * 3 // 40)
    except Exception:
        pass
    return None
