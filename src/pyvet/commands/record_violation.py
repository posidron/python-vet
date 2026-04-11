"""pyvet record-violation — declare that versions violate certain criteria."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import load_config, load_audits, save_audits, get_default_criteria
from pyvet.utils.git import get_user_info
from pyvet.utils.toml import ensure_aot
from pyvet.utils.ui import console, print_success, print_error


def run(args: object) -> int:
    project_dir = Path.cwd()

    package: str = getattr(args, "package", "")
    versions: str = getattr(args, "versions", "")
    criteria: str | None = getattr(args, "criteria", None)
    who: str | None = getattr(args, "who", None)
    notes: str | None = getattr(args, "notes", None)

    if not package or not versions:
        print_error("Package name and version requirement are required.")
        return 1

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    if not criteria:
        criteria = get_default_criteria(config)

    if not who:
        who = get_user_info()
    if not who:
        who = console.input("[bold]Your name and email:[/] ")

    entry = tomlkit.table()
    entry["who"] = who
    entry["criteria"] = criteria
    entry["violation"] = versions
    if notes:
        entry["notes"] = notes

    if "audits" not in audits_doc:
        audits_doc["audits"] = tomlkit.table()

    aot = ensure_aot(audits_doc, "audits", package)
    aot.append(entry)

    save_audits(project_dir, audits_doc)
    print_success(
        f"Recorded violation for [bold]{package}[/] versions "
        f"[bold]{versions}[/] ({criteria})"
    )
    return 0
