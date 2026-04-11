"""pyvet import — manage trusted import sources."""

from __future__ import annotations

from pathlib import Path

import tomlkit

from pyvet.core.config import (
    load_config, save_config, get_imports_config,
)
from pyvet.core.imports import refresh_imports
from pyvet.utils.ui import console, print_success, print_error, print_info, make_table


def run(args: object) -> int:
    subcmd: str = getattr(args, "imports_command", "")

    if subcmd == "add":
        return _add(args)
    elif subcmd == "fetch":
        return _fetch(args)
    elif subcmd == "list":
        return _list(args)
    else:
        print_error("Usage: pyvet import {add,fetch,list}")
        return 1


def _add(args: object) -> int:
    project_dir = Path.cwd()
    name: str = getattr(args, "name", "")
    url: str = getattr(args, "url", "")

    if not name or not url:
        print_error("--name and --url are required.")
        return 1

    config = load_config(project_dir)
    if "imports" not in config:
        config["imports"] = tomlkit.table()

    entry = tomlkit.table()
    entry["url"] = url
    config["imports"][name] = entry

    save_config(project_dir, config)
    print_success(f"Added import [bold]{name}[/] from {url}")
    print_info("Run [bold]pyvet import fetch[/] to download the audits.")
    return 0


def _fetch(args: object) -> int:
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
        audit_count = sum(len(v) for v in data.get("audits", {}).values())
        print_success(f"[bold]{name}[/]: {audit_count} audit entries cached")

    return 0


def _list(args: object) -> int:
    project_dir = Path.cwd()
    config = load_config(project_dir)
    imports_config = get_imports_config(config)

    if not imports_config:
        print_info("No imports configured.")
        return 0

    table = make_table(
        "Configured Imports",
        [("Name", "cyan"), ("URL", ""), ("Exclude", "dim")],
    )
    for name, cfg in imports_config.items():
        exclude = ", ".join(cfg.get("exclude", []))
        table.add_row(name, cfg.get("url", ""), exclude or "—")

    console.print(table)
    return 0
