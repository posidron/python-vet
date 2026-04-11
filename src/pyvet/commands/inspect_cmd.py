"""pyvet inspect — download and inspect a package version."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from pyvet.pypi.client import download_sdist, get_package_info
from pyvet.utils.ui import console, print_success, print_error, print_info


def run(args: object) -> int:
    package: str = getattr(args, "package", "")
    version: str = getattr(args, "version", "")
    mode: str = getattr(args, "mode", "local")

    if not package or not version:
        print_error("Package name and version are required.")
        return 1

    try:
        info = get_package_info(package, version)
    except Exception as e:
        print_error(f"Failed to fetch package info: {e}")
        return 1

    console.print()
    console.print(f"[bold]Package:[/] {info.name} {info.version}")
    console.print(f"[bold]Summary:[/] {info.summary}")
    console.print(
        f"[bold]PyPI:[/] https://pypi.org/project/{info.name}/{info.version}/"
    )

    if mode == "local":
        if not info.sdist_url:
            print_error(f"No sdist available for {package}=={version}")
            return 1

        print_info("Downloading and extracting sdist...")
        try:
            tmp = Path(tempfile.mkdtemp(prefix="pyvet-inspect-"))
            extract_dir = download_sdist(package, version, tmp)
            print_success(f"Source extracted to: {extract_dir}")
            console.print()
            console.print(
                "[dim]Opening a subshell in the extracted source. "
                "Type 'exit' when done.[/]"
            )
            console.print()
            os.chdir(extract_dir)
            shell = os.environ.get("SHELL", "/bin/sh")
            os.system(shell)  # noqa: S605 — intentional interactive shell
        except Exception as e:
            print_error(f"Failed to download/extract: {e}")
            return 1
    else:
        console.print()
        console.print(
            f"View source at: "
            f"https://pypi.org/project/{info.name}/{info.version}/#files"
        )

    return 0
