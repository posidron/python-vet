"""TOML read/write helpers using tomlkit (preserves formatting/comments)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument


def load_toml(path: Path) -> TOMLDocument:
    """Load a TOML file, returning a tomlkit document."""
    if not path.exists():
        return tomlkit.document()
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def save_toml(path: Path, doc: TOMLDocument) -> None:
    """Write a tomlkit document to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(doc), encoding="utf-8")


def ensure_table(doc: TOMLDocument, *keys: str) -> Any:
    """Ensure a nested table exists in the document, creating it if needed."""
    current = doc
    for key in keys:
        if key not in current:
            current[key] = tomlkit.table()
        current = current[key]
    return current


def ensure_aot(doc: TOMLDocument, *keys: str) -> tomlkit.items.AoT:
    """Ensure an array-of-tables exists at the given nested key path."""
    parent = doc
    for key in keys[:-1]:
        if key not in parent:
            parent[key] = tomlkit.table()
        parent = parent[key]

    last_key = keys[-1]
    if last_key not in parent:
        parent[last_key] = tomlkit.aot()
    return parent[last_key]
