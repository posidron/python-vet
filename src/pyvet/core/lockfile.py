"""Lockfile parsing for uv.lock and requirements.txt."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LockedDep:
    """A dependency pinned in a lockfile."""
    name: str
    version: str
    is_dev: bool = False

    @property
    def key(self) -> str:
        """Normalized name for lookup."""
        return normalize_name(self.name)


def normalize_name(name: str) -> str:
    """Normalize a Python package name (PEP 503)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_uv_lock(path: Path) -> list[LockedDep]:
    """Parse a uv.lock file and return third-party locked dependencies.

    uv.lock is a TOML file with [[package]] entries. First-party packages
    have source = { editable = "." } or similar local paths.
    """
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    text = path.read_text(encoding="utf-8")
    data = tomllib.loads(text)

    deps: list[LockedDep] = []
    for pkg in data.get("package", []):
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        source = pkg.get("source", {})

        # Skip first-party / editable / path / workspace deps
        if _is_first_party(source):
            continue

        if name and version:
            deps.append(LockedDep(name=name, version=version))

    return deps


def _is_first_party(source: Any) -> bool:
    """Check if a uv.lock source is first-party (editable, path, workspace)."""
    if isinstance(source, dict):
        if source.get("editable"):
            return True
        if source.get("virtual"):
            return True
        # registry sources are third-party
        if source.get("registry"):
            return False
    return False


def parse_requirements_txt(path: Path) -> list[LockedDep]:
    """Parse a pinned requirements.txt (pkg==version lines)."""
    deps: list[LockedDep] = []
    pattern = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9_.]+)")

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        m = pattern.match(line)
        if m:
            deps.append(LockedDep(name=m.group(1), version=m.group(2)))

    return deps


def detect_and_parse_lockfile(project_dir: Path) -> list[LockedDep]:
    """Auto-detect and parse the lockfile in a project directory."""
    uv_lock = project_dir / "uv.lock"
    if uv_lock.exists():
        return parse_uv_lock(uv_lock)

    req_txt = project_dir / "requirements.txt"
    if req_txt.exists():
        return parse_requirements_txt(req_txt)

    raise FileNotFoundError(
        "No lockfile found. Expected uv.lock or requirements.txt in "
        f"{project_dir}"
    )


def get_first_party_names(project_dir: Path) -> set[str]:
    """Get first-party package names from pyproject.toml."""
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.exists():
        return set()

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    names: set[str] = set()

    # [project].name
    project_name = data.get("project", {}).get("name")
    if project_name:
        names.add(normalize_name(project_name))

    return names
