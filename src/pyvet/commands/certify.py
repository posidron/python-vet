"""pyvet certify — record an audit."""

from __future__ import annotations

from datetime import date, timedelta
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
    wildcard: str | None = getattr(args, "wildcard", None)
    start_date: str | None = getattr(args, "start_date", None)
    end_date: str | None = getattr(args, "end_date", None)

    if not package:
        print_error("Package name is required.")
        return 1

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    if not audits_doc:
        print_error("No audits.toml found. Run [bold]pyvet init[/] first.")
        return 1

    if not criteria:
        criteria = get_default_criteria(config)

    if not who:
        who = get_user_info()
    if not who:
        who = console.input("[bold]Your name and email:[/] ")

    # Wildcard audit
    if wildcard:
        return _certify_wildcard(
            project_dir, audits_doc, package, wildcard,
            criteria, who, notes, start_date, end_date,
        )

    # Regular audit requires version
    if not version:
        print_error("Version is required (or use --wildcard).")
        return 1

    # Build the audit entry
    entry = tomlkit.table()
    entry["who"] = who
    entry["criteria"] = criteria

    if old_version:
        entry["delta"] = f"{old_version} -> {version}"
        audit_type = "delta"
    else:
        entry["version"] = version
        audit_type = "full"

    if notes:
        entry["notes"] = notes
    else:
        user_notes = console.input("[dim]Notes (optional, press Enter to skip):[/dim] ")
        if user_notes.strip():
            entry["notes"] = user_notes.strip()

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


def _certify_wildcard(
    project_dir: Path,
    audits_doc,
    package: str,
    user_login: str,
    criteria: str,
    who: str,
    notes: str | None,
    start_date: str | None,
    end_date: str | None,
) -> int:
    """Record a wildcard audit entry."""
    today = date.today()

    if not start_date:
        start_date = today.isoformat()
    if not end_date:
        end_date = (today + timedelta(days=365)).isoformat()

    entry = tomlkit.table()
    entry["who"] = who
    entry["criteria"] = criteria
    entry["user-login"] = user_login
    entry["start"] = start_date
    entry["end"] = end_date
    if notes:
        entry["notes"] = notes

    if "wildcard-audits" not in audits_doc:
        audits_doc["wildcard-audits"] = tomlkit.table()

    aot = ensure_aot(audits_doc, "wildcard-audits", package)
    aot.append(entry)

    save_audits(project_dir, audits_doc)
    print_success(
        f"Recorded wildcard audit for [bold]{package}[/] "
        f"by user [bold]{user_login}[/] ({start_date} to {end_date})"
    )
    return 0
