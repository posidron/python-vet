"""pyvet fmt — normalize and sort TOML files."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import (
    load_config, save_config, load_audits, save_audits,
)
from pyvet.utils.ui import print_success


def run(args: object) -> int:
    project_dir = Path.cwd()

    config = load_config(project_dir)
    audits_doc = load_audits(project_dir)

    # Sort exemptions by package name
    exemptions = config.get("exemptions")
    if exemptions:
        sorted_exemptions = tomlkit.table()
        for key in sorted(exemptions.keys()):
            sorted_exemptions[key] = exemptions[key]
        config["exemptions"] = sorted_exemptions

    # Sort audits by package name
    audits = audits_doc.get("audits")
    if audits:
        sorted_audits = tomlkit.table()
        for key in sorted(audits.keys()):
            sorted_audits[key] = audits[key]
        audits_doc["audits"] = sorted_audits

    save_config(project_dir, config)
    save_audits(project_dir, audits_doc)

    print_success("Formatted config.toml and audits.toml")
    return 0
