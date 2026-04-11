"""Git config helpers."""

import subprocess


def get_user_info() -> str:
    """Get 'Name <email>' from git config, falling back to empty string."""
    try:
        name = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        email = subprocess.run(
            ["git", "config", "user.email"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return f"{name} <{email}>"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""
