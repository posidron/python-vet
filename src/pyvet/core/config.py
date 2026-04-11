"""Load and save config.toml and audits.toml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from tomlkit import TOMLDocument

from pyvet.utils.toml import load_toml, save_toml, ensure_table


SUPPLY_CHAIN_DIR = "supply-chain"
CONFIG_FILE = "config.toml"
AUDITS_FILE = "audits.toml"
IMPORTS_LOCK_FILE = "imports.lock"


def supply_chain_path(project_dir: Path) -> Path:
    return project_dir / SUPPLY_CHAIN_DIR


def config_path(project_dir: Path) -> Path:
    return supply_chain_path(project_dir) / CONFIG_FILE


def audits_path(project_dir: Path) -> Path:
    return supply_chain_path(project_dir) / AUDITS_FILE


def imports_lock_path(project_dir: Path) -> Path:
    return supply_chain_path(project_dir) / IMPORTS_LOCK_FILE


def load_config(project_dir: Path) -> TOMLDocument:
    return load_toml(config_path(project_dir))


def save_config(project_dir: Path, doc: TOMLDocument) -> None:
    save_toml(config_path(project_dir), doc)


def load_audits(project_dir: Path) -> TOMLDocument:
    return load_toml(audits_path(project_dir))


def save_audits(project_dir: Path, doc: TOMLDocument) -> None:
    save_toml(audits_path(project_dir), doc)


def get_default_criteria(config: TOMLDocument) -> str:
    return config.get("default-criteria", "safe-to-deploy")  # type: ignore[return-value]


def get_exemptions(config: TOMLDocument) -> dict[str, list[dict[str, Any]]]:
    """Return the exemptions table as {pkg_name: [entries]}."""
    return dict(config.get("exemptions", {}))


def get_policy(config: TOMLDocument) -> dict[str, dict[str, Any]]:
    """Return the policy table as {pkg_name_or_pattern: {settings}}."""
    return dict(config.get("policy", {}))


def get_imports_config(config: TOMLDocument) -> dict[str, dict[str, Any]]:
    """Return the imports table as {name: {url, criteria-map, ...}}."""
    return dict(config.get("imports", {}))


def get_audits(audits_doc: TOMLDocument) -> dict[str, list[dict[str, Any]]]:
    """Return the audits table as {pkg_name: [audit_entries]}."""
    return dict(audits_doc.get("audits", {}))


def get_criteria_table(audits_doc: TOMLDocument) -> dict[str, Any]:
    """Return the criteria table from audits.toml."""
    return dict(audits_doc.get("criteria", {}))


def get_trusted(audits_doc: TOMLDocument) -> dict[str, list[dict[str, Any]]]:
    """Return the trusted table as {pkg_name: [entries]}."""
    return dict(audits_doc.get("trusted", {}))
