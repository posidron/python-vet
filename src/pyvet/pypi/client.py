"""PyPI JSON API client."""

from __future__ import annotations

import hashlib
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import httpx


PYPI_BASE = "https://pypi.org/pypi"


@dataclass
class PackageInfo:
    name: str
    version: str
    summary: str
    sdist_url: str | None
    sdist_sha256: str | None
    upload_time: str | None


def get_package_info(name: str, version: str) -> PackageInfo:
    """Fetch package metadata from PyPI."""
    url = f"{PYPI_BASE}/{name}/{version}/json"
    resp = httpx.get(url, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    info = data.get("info", {})
    urls = data.get("urls", [])

    sdist_url = None
    sdist_sha256 = None
    upload_time = None

    for u in urls:
        if u.get("packagetype") == "sdist":
            sdist_url = u.get("url")
            sdist_sha256 = u.get("digests", {}).get("sha256")
            upload_time = u.get("upload_time")
            break

    return PackageInfo(
        name=info.get("name", name),
        version=info.get("version", version),
        summary=info.get("summary", ""),
        sdist_url=sdist_url,
        sdist_sha256=sdist_sha256,
        upload_time=upload_time,
    )


def download_sdist(name: str, version: str, dest_dir: Path) -> Path:
    """Download and verify the sdist for a package version.

    Returns path to the extracted directory.
    """
    info = get_package_info(name, version)
    if not info.sdist_url:
        raise ValueError(f"No sdist available for {name}=={version}")

    resp = httpx.get(info.sdist_url, follow_redirects=True, timeout=120)
    resp.raise_for_status()
    content = resp.content

    # Verify hash
    actual_sha = hashlib.sha256(content).hexdigest()
    if info.sdist_sha256 and actual_sha != info.sdist_sha256:
        raise ValueError(
            f"SHA-256 mismatch for {name}=={version}: "
            f"expected {info.sdist_sha256}, got {actual_sha}"
        )

    # Determine archive type and extract
    sdist_url = info.sdist_url
    archive_path = dest_dir / sdist_url.rsplit("/", 1)[-1]
    archive_path.write_bytes(content)

    extract_dir = dest_dir / f"{name}-{version}"
    extract_dir.mkdir(exist_ok=True)

    if archive_path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(extract_dir, filter="data")
    elif archive_path.name.endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(extract_dir)
    else:
        raise ValueError(f"Unknown archive format: {archive_path.name}")

    return extract_dir


def download_two_versions(
    name: str, old_version: str, new_version: str,
) -> tuple[Path, Path]:
    """Download two versions of a package for diffing.

    Returns (old_path, new_path) tuples of extracted directories.
    """
    tmp = Path(tempfile.mkdtemp(prefix="pyvet-diff-"))
    old_dir = tmp / "old"
    new_dir = tmp / "new"
    old_dir.mkdir()
    new_dir.mkdir()

    old_path = download_sdist(name, old_version, old_dir)
    new_path = download_sdist(name, new_version, new_dir)

    return old_path, new_path
