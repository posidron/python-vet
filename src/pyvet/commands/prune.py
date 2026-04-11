"""pyvet prune — remove stale audit entries and exemptions."""

from __future__ import annotations

from pathlib import Path

from pyvet.core.config import (
    load_config, save_config, load_audits, save_audits,
    get_exemptions, get_audits,
)
from pyvet.core.lockfile import detect_and_parse_lockfile, normalize_name
from pyvet.utils.ui import console, print_success, print_info


def run(args: object) -> int:
    project_dir = Path.cwd()
    no_imports: bool = getattr(args, "no_imports", False)
    no_exemptions: bool = getattr(args, "no_exemptions", False)
    no_audits: bool = getattr(args, "no_audits", False)

    try:
        deps = detect_and_parse_lockfile(project_dir)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        return 1

    active_keys = {d.key for d in deps}

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    pruned_exemptions = 0
    pruned_audits = 0

    # Prune exemptions
    if not no_exemptions:
        exemptions = config.get("exemptions")
        if exemptions:
            to_remove = [
                name for name in exemptions
                if normalize_name(name) not in active_keys
            ]
            for name in to_remove:
                del exemptions[name]
                pruned_exemptions += 1

    # Prune audits
    if not no_audits:
        audits = audits_doc.get("audits")
        if audits:
            to_remove = [
                name for name in audits
                if normalize_name(name) not in active_keys
            ]
            for name in to_remove:
                del audits[name]
                pruned_audits += 1

    save_config(project_dir, config)
    save_audits(project_dir, audits_doc)

    if pruned_exemptions or pruned_audits:
        print_success(
            f"Pruned {pruned_exemptions} exemptions and "
            f"{pruned_audits} audit entries."
        )
    else:
        print_info("Nothing to prune. All entries are current.")

    return 0
