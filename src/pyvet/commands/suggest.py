"""pyvet suggest — recommend lowest-effort audits."""

from __future__ import annotations

from pathlib import Path

from pyvet.core.config import (
    load_config, load_audits,
    get_default_criteria, get_exemptions, get_audits, get_criteria_table,
    get_policy, get_trusted, get_imports_config,
)
from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import detect_and_parse_lockfile
from pyvet.core.resolver import resolve
from pyvet.pypi.client import get_package_info
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

    result = resolve(
        deps=deps,
        audits=audits,
        exemptions=exemptions,
        trusted=trusted,
        imported_audits={},
        criteria_graph=criteria_graph,
        policy=policy,
        default_criteria=default_criteria,
    )

    # Find exempted deps (still "pass" but via exemption)
    exempted = [r for r in result.results if r.reason == "exemption"]
    unvetted = result.failures

    if not exempted and not unvetted:
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
            ("Criteria", "dim"),
        ],
    )

    suggestions: list[tuple[int, str, str, str, str]] = []

    for r in sorted(unvetted, key=lambda x: x.package):
        suggestions.append((
            1, r.package, r.version,
            f"pyvet inspect {r.package} {r.version}",
            r.required_criteria,
        ))

    for r in sorted(exempted, key=lambda x: x.package):
        # Check if we can do a delta audit from any existing full audit
        pkg_audits = audits.get(r.package, [])
        audited_versions = [
            a["version"] for a in pkg_audits
            if "version" in a and "violation" not in a
        ]

        if audited_versions:
            closest = audited_versions[-1]
            action = f"pyvet diff {r.package} {closest} {r.version}"
        else:
            action = f"pyvet inspect {r.package} {r.version}"

        suggestions.append((
            2, r.package, r.version, action, r.required_criteria,
        ))

    for priority, pkg, ver, action, criteria in sorted(suggestions):
        priority_str = "[red]HIGH[/]" if priority == 1 else "[yellow]MEDIUM[/]"
        table.add_row(priority_str, pkg, ver, action, criteria)

    console.print(table)

    console.print()
    print_info(
        f"{len(unvetted)} unvetted, {len(exempted)} exempted. "
        "Use [bold]pyvet certify[/] to record audits."
    )

    return 0
