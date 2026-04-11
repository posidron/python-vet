"""pyvet certify — record an audit."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import load_config, load_audits, save_audits, get_default_criteria
from pyvet.utils.git import get_user_info
from pyvet.utils.toml import ensure_aot
from pyvet.utils.ui import console, print_success, print_error, print_info


def run(args: object) -> int:
    project_dir = Path.cwd()

    package: str = getattr(args, "package", "")
    version: str = getattr(args, "version", "")
    old_version: str | None = getattr(args, "old_version", None)
    criteria: str | None = getattr(args, "criteria", None)
    notes: str | None = getattr(args, "notes", None)
    who: str | None = getattr(args, "who", None)

    if not package or not version:
        print_error("Package name and version are required.")
        return 1

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    if not audits_doc:
        print_error("No audits.toml found. Run [bold]pyvet init[/] first.")
        return 1

    # Determine criteria
    if not criteria:
        criteria = get_default_criteria(config)

    # Determine who
    if not who:
        who = get_user_info()
    if not who:
        who = console.input("[bold]Your name and email:[/] ")

    # Build the audit entry
    entry = tomlkit.table()
    entry["who"] = who
    entry["criteria"] = criteria

    if old_version:
        # Delta audit
        entry["delta"] = f"{old_version} -> {version}"
        audit_type = "delta"
    else:
        # Full audit
        entry["version"] = version
        audit_type = "full"

    if notes:
        entry["notes"] = notes
    else:
        user_notes = console.input("[dim]Notes (optional, press Enter to skip):[/dim] ")
        if user_notes.strip():
            entry["notes"] = user_notes.strip()

    # Append to audits.toml
    if "audits" not in audits_doc:
        audits_doc["audits"] = tomlkit.table()

    aot = ensure_aot(audits_doc, "audits", package)
    aot.append(entry)

    save_audits(project_dir, audits_doc)

    if audit_type == "delta":
        print_success(
            f"Recorded {audit_type} audit of [bold]{package}[/] "
            f"({old_version} → {version}) for [bold]{criteria}[/]"
        )
    else:
        print_success(
            f"Recorded {audit_type} audit of [bold]{package}=={version}[/] "
            f"for [bold]{criteria}[/]"
        )

    return 0
