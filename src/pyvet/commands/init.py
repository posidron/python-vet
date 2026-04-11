"""pyvet init — bootstrap the supply-chain directory."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import (
    supply_chain_path, config_path, audits_path,
    save_config, save_audits,
)
from pyvet.core.lockfile import detect_and_parse_lockfile, normalize_name
from pyvet.core.criteria import SAFE_TO_RUN, SAFE_TO_DEPLOY
from pyvet.utils.toml import ensure_table
from pyvet.utils.ui import console, print_success, print_info, print_warning


def run(args: object) -> int:
    project_dir = Path.cwd()
    sc_path = supply_chain_path(project_dir)

    if sc_path.exists():
        print_warning(f"supply-chain directory already exists at {sc_path}")
        return 1

    sc_path.mkdir(parents=True)

    # --- audits.toml ---
    audits_doc = tomlkit.document()
    audits_doc.add(tomlkit.comment("Audits performed by this project's members."))
    audits_doc.add(tomlkit.nl())

    # Built-in criteria
    criteria = tomlkit.table()
    safe_run = tomlkit.table()
    safe_run["description"] = SAFE_TO_RUN.description
    criteria["safe-to-run"] = safe_run

    safe_deploy = tomlkit.table()
    safe_deploy["description"] = SAFE_TO_DEPLOY.description
    safe_deploy["implies"] = "safe-to-run"
    criteria["safe-to-deploy"] = safe_deploy

    audits_doc["criteria"] = criteria
    audits_doc.add(tomlkit.nl())
    audits_doc["audits"] = tomlkit.table()

    save_audits(project_dir, audits_doc)
    print_success(f"Created {audits_path(project_dir)}")

    # --- config.toml ---
    config_doc = tomlkit.document()
    config_doc.add(tomlkit.comment("pyvet configuration for this project."))
    config_doc.add(tomlkit.nl())

    pyvet_meta = tomlkit.table()
    pyvet_meta["version"] = "0.1"
    config_doc["pyvet"] = pyvet_meta
    config_doc.add(tomlkit.nl())

    config_doc["default-criteria"] = "safe-to-deploy"
    config_doc.add(tomlkit.nl())

    # Detect lockfile and populate exemptions
    try:
        deps = detect_and_parse_lockfile(project_dir)
    except FileNotFoundError as e:
        print_warning(str(e))
        deps = []

    if deps:
        exemptions = tomlkit.table()
        for dep in sorted(deps, key=lambda d: d.key):
            entry = tomlkit.table()
            entry["version"] = dep.version
            entry["criteria"] = "safe-to-deploy"
            entry["suggest"] = True
            entry["notes"] = "Pre-existing dependency, not yet audited"

            aot = tomlkit.aot()
            aot.append(entry)
            exemptions[dep.name] = aot

        config_doc["exemptions"] = exemptions

        print_info(f"Added {len(deps)} dependencies to exemptions")

    config_doc.add(tomlkit.nl())
    config_doc["policy"] = tomlkit.table()
    config_doc["imports"] = tomlkit.table()

    save_config(project_dir, config_doc)
    print_success(f"Created {config_path(project_dir)}")

    console.print()
    console.print(
        "[bold green]pyvet initialized![/] "
        "Run [bold]pyvet check[/] to verify your dependencies."
    )

    return 0
