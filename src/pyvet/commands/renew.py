"""pyvet renew — renew wildcard audit expirations."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from pyvet.core.config import load_audits, save_audits
from pyvet.utils.ui import console, print_success, print_error, print_info


def run(args: object) -> int:
    project_dir = Path.cwd()

    crate: str | None = getattr(args, "crate", None)
    expiring: bool = getattr(args, "expiring", False)

    audits_doc = load_audits(project_dir)

    wildcards = audits_doc.get("wildcard-audits")
    if not wildcards:
        print_info("No wildcard audits found.")
        return 0

    today = date.today()
    one_year = today + timedelta(days=365)
    six_weeks = today + timedelta(weeks=6)
    new_end = one_year.isoformat()
    renewed = 0

    if crate:
        # Renew a specific crate
        entries = wildcards.get(crate)
        if not entries:
            print_error(f"No wildcard audits found for {crate}")
            return 1
        for entry in entries:
            entry["end"] = new_end
            renewed += 1
    elif expiring:
        # Renew all that expire within 6 weeks
        for pkg_name, entries in wildcards.items():
            for entry in entries:
                end_str = entry.get("end", "")
                renew_flag = entry.get("renew", True)
                if not renew_flag:
                    continue
                try:
                    end_date = date.fromisoformat(end_str)
                except (ValueError, TypeError):
                    continue
                if end_date <= six_weeks:
                    entry["end"] = new_end
                    renewed += 1
    else:
        print_error("Specify a crate name or use --expiring.")
        return 1

    save_audits(project_dir, audits_doc)
    print_success(f"Renewed {renewed} wildcard audit(s) until {new_end}")
    return 0
