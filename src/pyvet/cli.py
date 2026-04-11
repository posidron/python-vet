"""CLI definition for pyvet using argparse."""

from __future__ import annotations

import argparse
import sys

from pyvet import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyvet",
        description="Supply-chain security for Python (PyPI) packages.",
    )
    parser.add_argument(
        "--version", action="version", version=f"pyvet {__version__}",
    )

    sub = parser.add_subparsers(dest="command")

    # --- init ---
    sub.add_parser("init", help="Bootstrap the supply-chain directory")

    # --- check ---
    sub.add_parser("check", help="Verify all dependencies are vetted")

    # --- certify ---
    certify_p = sub.add_parser(
        "certify", help="Record an audit for a package",
    )
    certify_p.add_argument("package", help="Package name")
    certify_p.add_argument("version", help="Version to certify")
    certify_p.add_argument(
        "old_version", nargs="?", default=None,
        help="Old version for delta audit (optional)",
    )
    certify_p.add_argument(
        "--criteria", "-c", default=None,
        help="Criteria to certify (default: from config)",
    )
    certify_p.add_argument(
        "--who", "-w", default=None,
        help="Auditor identity (default: from git config)",
    )
    certify_p.add_argument(
        "--notes", "-n", default=None,
        help="Notes for the audit entry",
    )

    # --- inspect ---
    inspect_p = sub.add_parser(
        "inspect", help="Download and inspect a package version",
    )
    inspect_p.add_argument("package", help="Package name")
    inspect_p.add_argument("version", help="Version to inspect")
    inspect_p.add_argument(
        "--mode", "-m", choices=["local", "web"], default="local",
        help="Inspection mode (default: local)",
    )

    # --- diff ---
    diff_p = sub.add_parser(
        "diff", help="Show diff between two versions of a package",
    )
    diff_p.add_argument("package", help="Package name")
    diff_p.add_argument("old_version", help="Old version")
    diff_p.add_argument("new_version", help="New version")

    # --- suggest ---
    sub.add_parser(
        "suggest", help="Recommend lowest-effort audits to shrink exemptions",
    )

    # --- trust ---
    trust_p = sub.add_parser(
        "trust", help="Record a trusted publisher entry",
    )
    trust_p.add_argument("package", help="Package name")
    trust_p.add_argument("--user", "-u", required=True, help="PyPI username")
    trust_p.add_argument("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
    trust_p.add_argument("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
    trust_p.add_argument("--criteria", "-c", default=None, help="Criteria")
    trust_p.add_argument("--notes", "-n", default=None, help="Notes")

    # --- prune ---
    sub.add_parser("prune", help="Remove stale audit entries and exemptions")

    # --- fmt ---
    sub.add_parser("fmt", help="Normalize and sort TOML files")

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # Default to 'check'
        args.command = "check"

    command_map = {
        "init": "pyvet.commands.init",
        "check": "pyvet.commands.check",
        "certify": "pyvet.commands.certify",
        "inspect": "pyvet.commands.inspect_cmd",
        "diff": "pyvet.commands.diff",
        "suggest": "pyvet.commands.suggest",
        "trust": "pyvet.commands.trust",
        "prune": "pyvet.commands.prune",
        "fmt": "pyvet.commands.fmt",
    }

    module_name = command_map.get(args.command)
    if not module_name:
        parser.print_help()
        sys.exit(1)

    import importlib
    mod = importlib.import_module(module_name)
    sys.exit(mod.run(args))
