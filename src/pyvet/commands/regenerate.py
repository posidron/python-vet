"""pyvet regenerate — regenerate exemptions and imports."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import (
    load_config, save_config, load_audits,
    get_default_criteria, get_exemptions, get_policy,
    get_audits, get_criteria_table, get_trusted, get_imports_config,
)
from pyvet.core.criteria import CriteriaGraph
from pyvet.core.lockfile import detect_and_parse_lockfile, normalize_name
from pyvet.core.resolver import resolve
from pyvet.core.imports import refresh_imports
from pyvet.utils.ui import console, print_success, print_error, print_info


def run(args: object) -> int:
    subcmd: str = getattr(args, "regen_command", "")

    if subcmd == "exemptions":
        return _regen_exemptions(args)
    elif subcmd == "imports":
        return _regen_imports(args)
    else:
        print_error("Usage: pyvet regenerate {exemptions,imports}")
        return 1


def _regen_exemptions(args: object) -> int:
    """Regenerate exemptions to make check pass minimally."""
    project_dir = Path.cwd()

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    try:
        deps = detect_and_parse_lockfile(project_dir)
    except FileNotFoundError as e:
        print_error(str(e))
        return 1

    criteria_graph = CriteriaGraph()
    criteria_graph.load_from_audits(get_criteria_table(audits_doc))

    default_criteria = get_default_criteria(config)
    audits = get_audits(audits_doc)
    trusted = get_trusted(audits_doc)
    policy = get_policy(config)

    # First, resolve with empty exemptions to find what's unvetted
    result = resolve(
        deps=deps,
        audits=audits,
        exemptions={},
        trusted=trusted,
        imported_audits={},
        criteria_graph=criteria_graph,
        policy=policy,
        default_criteria=default_criteria,
    )

    # Build minimal exemptions for failures
    new_exemptions = tomlkit.table()
    added = 0
    removed = 0

    old_exemptions = get_exemptions(config)
    old_keys = set()
    for pkg_name, entries in old_exemptions.items():
        for e in entries:
            old_keys.add((normalize_name(pkg_name), e.get("version", "")))

    for f in sorted(result.failures, key=lambda x: x.package):
        entry = tomlkit.table()
        entry["version"] = f.version
        entry["criteria"] = f.required_criteria
        entry["suggest"] = True
        entry["notes"] = "Auto-generated exemption"

        aot = tomlkit.aot()
        aot.append(entry)

        # Check if we already have this
        is_existing = (f.package, f.version) in old_keys or \
                      (normalize_name(f.package), f.version) in old_keys
        if not is_existing:
            added += 1

        new_exemptions[f.package] = aot

    # Count removed
    new_keys = {(normalize_name(f.package), f.version) for f in result.failures}
    for key in old_keys:
        if key not in new_keys:
            removed += 1

    config["exemptions"] = new_exemptions
    save_config(project_dir, config)

    print_success(
        f"Regenerated exemptions: {added} added, {removed} removed, "
        f"{len(result.failures)} total"
    )
    return 0


def _regen_imports(args: object) -> int:
    """Re-fetch all imports and update imports.lock."""
    project_dir = Path.cwd()
    config = load_config(project_dir)
    imports_config = get_imports_config(config)

    if not imports_config:
        print_info("No imports configured.")
        return 0

    print_info(f"Fetching {len(imports_config)} import source(s)...")
    try:
        imported = refresh_imports(project_dir, imports_config)
    except Exception as e:
        print_error(f"Failed to fetch imports: {e}")
        return 1

    for name, data in imported.items():
        n = sum(len(v) for v in data.get("audits", {}).values())
        print_success(f"[bold]{name}[/]: {n} audit entries")

    print_success("imports.lock regenerated.")
    return 0
