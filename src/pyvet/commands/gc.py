"""pyvet gc — clean up old packages from the download cache."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from pyvet.utils.ui import print_success, print_info


CACHE_DIR_NAME = ".pyvet-cache"


def get_cache_dir() -> Path:
    """Get the global pyvet cache directory."""
    cache = Path.home() / CACHE_DIR_NAME
    cache.mkdir(exist_ok=True)
    return cache


def run(args: object) -> int:
    max_age_days: int = getattr(args, "max_age_days", 30)
    clean: bool = getattr(args, "clean", False)

    cache_dir = get_cache_dir()

    if clean:
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            print_success(f"Removed entire cache directory: {cache_dir}")
        else:
            print_info("No cache directory to clean.")
        return 0

    if not cache_dir.exists():
        print_info("No cache directory found.")
        return 0

    cutoff = time.time() - (max_age_days * 86400)
    removed = 0

    for item in cache_dir.iterdir():
        if item.stat().st_mtime < cutoff:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
            removed += 1

    print_success(
        f"Cleaned {removed} item(s) older than {max_age_days} days "
        f"from {cache_dir}"
    )
    return 0
