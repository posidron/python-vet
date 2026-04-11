"""pyvet diff — show diff between two versions of a package."""

from __future__ import annotations

import difflib
import os
from pathlib import Path

from pyvet.pypi.client import download_two_versions
from pyvet.utils.ui import console, print_error, print_info, print_success


def run(args: object) -> int:
    package: str = getattr(args, "package", "")
    old_version: str = getattr(args, "old_version", "")
    new_version: str = getattr(args, "new_version", "")

    if not package or not old_version or not new_version:
        print_error("Package name, old version, and new version are required.")
        return 1

    print_info(
        f"Downloading {package} {old_version} and {new_version} for comparison..."
    )

    try:
        old_path, new_path = download_two_versions(package, old_version, new_version)
    except Exception as e:
        print_error(f"Failed to download: {e}")
        return 1

    print_success("Downloaded both versions.")
    console.print()

    # Collect all Python files and show unified diff
    old_files = _collect_files(old_path)
    new_files = _collect_files(new_path)
    all_rel_paths = sorted(set(old_files.keys()) | set(new_files.keys()))

    total_added = 0
    total_removed = 0

    for rel in all_rel_paths:
        old_content = old_files.get(rel, "").splitlines(keepends=True)
        new_content = new_files.get(rel, "").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            old_content, new_content,
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        ))

        if diff:
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    total_added += 1
                    console.print(f"[green]{line.rstrip()}[/]")
                elif line.startswith("-") and not line.startswith("---"):
                    total_removed += 1
                    console.print(f"[red]{line.rstrip()}[/]")
                elif line.startswith("@@"):
                    console.print(f"[cyan]{line.rstrip()}[/]")
                else:
                    console.print(line.rstrip())

    console.print()
    console.print(
        f"[bold]Summary:[/] {total_added} additions, {total_removed} deletions "
        f"across {len(all_rel_paths)} files"
    )
    console.print(f"[bold]Total changed lines:[/] {total_added + total_removed}")

    return 0


def _collect_files(root: Path) -> dict[str, str]:
    """Collect all text files under root as {relative_path: content}."""
    files: dict[str, str] = {}
    # Find the actual source directory (often nested inside one more dir)
    candidates = list(root.iterdir())
    if len(candidates) == 1 and candidates[0].is_dir():
        root = candidates[0]

    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = str(path.relative_to(root))
            try:
                files[rel] = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return files
