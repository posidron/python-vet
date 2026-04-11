"""Fetch and cache external audit sets (imports)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import tomlkit
from tomlkit import TOMLDocument

from pyvet.core.config import imports_lock_path
from pyvet.utils.toml import load_toml, save_toml


def fetch_import(url: str) -> tuple[str, str]:
    """Fetch an audits.toml from a URL. Returns (content, sha256)."""
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    content = resp.text
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return content, digest


def load_imports_lock(project_dir: Path) -> TOMLDocument:
    return load_toml(imports_lock_path(project_dir))


def save_imports_lock(project_dir: Path, doc: TOMLDocument) -> None:
    save_toml(imports_lock_path(project_dir), doc)


def refresh_imports(
    project_dir: Path,
    imports_config: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Fetch all configured imports and update imports.lock.

    Returns a dict of {name: parsed_audits_doc} for use by the resolver.
    """
    lock = tomlkit.document()
    imported_audits: dict[str, dict[str, Any]] = {}

    for name, cfg in imports_config.items():
        url = cfg.get("url", "")
        if not url:
            continue

        content, sha = fetch_import(url)
        parsed = tomlkit.parse(content)

        entry = tomlkit.table()
        entry["url"] = url
        entry["sha256"] = sha
        entry["fetched"] = datetime.now(timezone.utc).isoformat()
        lock[name] = entry

        imported_audits[name] = {
            "audits": dict(parsed.get("audits", {})),
            "criteria": dict(parsed.get("criteria", {})),
            "trusted": dict(parsed.get("trusted", {})),
        }

    save_imports_lock(project_dir, lock)
    return imported_audits
