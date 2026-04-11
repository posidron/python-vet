"""pyvet add-exemption — mark a package as exempted from review."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import load_config, save_config, get_default_criteria
from pyvet.utils.toml import ensure_aot
from pyvet.utils.ui import print_success, print_error


def run(args: object) -> int:
    project_dir = Path.cwd()

    package: str = getattr(args, "package", "")
    version: str = getattr(args, "version", "")
    criteria: str | None = getattr(args, "criteria", None)
    notes: str | None = getattr(args, "notes", None)
    no_suggest: bool = getattr(args, "no_suggest", False)

    if not package or not version:
        print_error("Package name and version are required.")
        return 1

    config = load_config(project_dir)

    if not criteria:
        criteria = get_default_criteria(config)

    entry = tomlkit.table()
    entry["version"] = version
    entry["criteria"] = criteria
    entry["suggest"] = not no_suggest
    if notes:
        entry["notes"] = notes

    if "exemptions" not in config:
        config["exemptions"] = tomlkit.table()

    aot = ensure_aot(config, "exemptions", package)
    aot.append(entry)

    save_config(project_dir, config)
    print_success(
        f"Added exemption for [bold]{package}=={version}[/] "
        f"([bold]{criteria}[/])"
    )
    return 0
