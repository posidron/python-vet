"""pyvet trust — record a trusted publisher entry."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import load_config, load_audits, save_audits, get_default_criteria
from pyvet.utils.toml import ensure_aot
from pyvet.utils.ui import print_success, print_error


def run(args: object) -> int:
    project_dir = Path.cwd()

    package: str = getattr(args, "package", "")
    user: str = getattr(args, "user", "")
    start: str = getattr(args, "start", "")
    end: str = getattr(args, "end", "")
    criteria: str | None = getattr(args, "criteria", None)
    notes: str | None = getattr(args, "notes", None)

    if not package or not user or not start or not end:
        print_error("Package, --user, --start, and --end are required.")
        return 1

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    if not criteria:
        criteria = get_default_criteria(config)

    entry = tomlkit.table()
    entry["criteria"] = criteria
    entry["user-login"] = user
    entry["start"] = start
    entry["end"] = end
    if notes:
        entry["notes"] = notes

    aot = ensure_aot(audits_doc, "trusted", package)
    aot.append(entry)

    save_audits(project_dir, audits_doc)
    print_success(
        f"Recorded trust for [bold]{package}[/] published by "
        f"[bold]{user}[/] ({start} to {end})"
    )

    return 0
