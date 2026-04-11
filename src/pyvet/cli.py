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

    # --- Global options ---
    parser.add_argument(
        "--locked", action="store_true",
        help="Do not fetch new imported audits",
    )
    parser.add_argument(
        "--frozen", action="store_true",
        help="Avoid the network entirely (implies --locked)",
    )
    parser.add_argument(
        "--output-format", choices=["human", "json"], default="human",
        help="Output format (default: human)",
    )
    parser.add_argument(
        "--store-path", default=None,
        help="Path to the supply-chain directory",
    )

    sub = parser.add_subparsers(dest="command")

    # Global options parent for subcommands
    global_parent = argparse.ArgumentParser(add_help=False)
    global_parent.add_argument("--locked", action="store_true", default=argparse.SUPPRESS)
    global_parent.add_argument("--frozen", action="store_true", default=argparse.SUPPRESS)
    global_parent.add_argument("--output-format", choices=["human", "json"], default=argparse.SUPPRESS)
    global_parent.add_argument("--store-path", default=argparse.SUPPRESS)

    # --- init ---
    sub.add_parser("init", help="Bootstrap the supply-chain directory", parents=[global_parent])

    # --- check ---
    sub.add_parser("check", help="Verify all dependencies are vetted", parents=[global_parent])

    # --- certify ---
    certify_p = sub.add_parser(
        "certify", help="Record an audit for a package", parents=[global_parent],
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
    certify_p.add_argument(
        "--wildcard", default=None, metavar="USER",
        help="Certify a wildcard audit for the given PyPI user",
    )
    certify_p.add_argument(
        "--start-date", default=None,
        help="Start date for wildcard audit (YYYY-MM-DD)",
    )
    certify_p.add_argument(
        "--end-date", default=None,
        help="End date for wildcard audit (YYYY-MM-DD)",
    )
    certify_p.add_argument(
        "--force", action="store_true",
        help="Skip validation of package/version",
    )

    # --- inspect ---
    inspect_p = sub.add_parser(
        "inspect", help="Download and inspect a package version", parents=[global_parent],
    )
    inspect_p.add_argument("package", help="Package name")
    inspect_p.add_argument("version", help="Version to inspect")
    inspect_p.add_argument(
        "--mode", "-m", choices=["local", "web"], default="local",
        help="Inspection mode (default: local)",
    )

    # --- diff ---
    diff_p = sub.add_parser(
        "diff", help="Show diff between two versions of a package", parents=[global_parent],
    )
    diff_p.add_argument("package", help="Package name")
    diff_p.add_argument("old_version", help="Old version")
    diff_p.add_argument("new_version", help="New version")

    # --- suggest ---
    sub.add_parser(
        "suggest", help="Recommend lowest-effort audits to shrink exemptions", parents=[global_parent],
    )

    # --- trust ---
    trust_p = sub.add_parser(
        "trust", help="Record a trusted publisher entry", parents=[global_parent],
    )
    trust_p.add_argument("package", help="Package name")
    trust_p.add_argument("--user", "-u", required=True, help="PyPI username")
    trust_p.add_argument("--start", "-s", required=True, help="Start date (YYYY-MM-DD)")
    trust_p.add_argument("--end", "-e", required=True, help="End date (YYYY-MM-DD)")
    trust_p.add_argument("--criteria", "-c", default=None, help="Criteria")
    trust_p.add_argument("--notes", "-n", default=None, help="Notes")

    # --- import ---
    import_p = sub.add_parser(
        "import", help="Manage trusted import sources", parents=[global_parent],
    )
    import_sub = import_p.add_subparsers(dest="imports_command")
    import_add = import_sub.add_parser("add", help="Add a new import source")
    import_add.add_argument("name", help="Name for the import")
    import_add.add_argument("--url", required=True, help="URL of the audits.toml")
    import_sub.add_parser("fetch", help="Fetch/refresh all imports")
    import_sub.add_parser("list", help="List configured imports")

    # --- add-exemption ---
    add_exempt_p = sub.add_parser(
        "add-exemption", help="Mark a package as exempted from review", parents=[global_parent],
    )
    add_exempt_p.add_argument("package", help="Package name")
    add_exempt_p.add_argument("version", help="Version to exempt")
    add_exempt_p.add_argument("--criteria", "-c", default=None, help="Criteria")
    add_exempt_p.add_argument("--notes", "-n", default=None, help="Notes")
    add_exempt_p.add_argument(
        "--no-suggest", action="store_true",
        help="Suppress suggesting this exemption for review",
    )

    # --- record-violation ---
    violation_p = sub.add_parser(
        "record-violation",
        help="Declare that versions violate certain criteria", parents=[global_parent],
    )
    violation_p.add_argument("package", help="Package name")
    violation_p.add_argument("versions", help="Version requirement (e.g. '>=1.0,<2.0' or '*')")
    violation_p.add_argument("--criteria", "-c", default=None, help="Violated criteria")
    violation_p.add_argument("--who", "-w", default=None, help="Auditor identity")
    violation_p.add_argument("--notes", "-n", default=None, help="Notes")

    # --- regenerate ---
    regen_p = sub.add_parser(
        "regenerate", help="Regenerate exemptions or imports", parents=[global_parent],
    )
    regen_sub = regen_p.add_subparsers(dest="regen_command")
    regen_sub.add_parser(
        "exemptions",
        help="Regenerate exemptions to make check pass minimally",
    )
    regen_sub.add_parser(
        "imports", help="Re-fetch all imports and update imports.lock",
    )

    # --- explain-audit ---
    explain_p = sub.add_parser(
        "explain-audit",
        help="Show the audit path for a package", parents=[global_parent],
    )
    explain_p.add_argument("package", help="Package name")
    explain_p.add_argument("version", nargs="?", default=None, help="Version")
    explain_p.add_argument("criteria", nargs="?", default=None, help="Criteria")

    # --- aggregate ---
    agg_p = sub.add_parser(
        "aggregate",
        help="Merge audits from multiple sources into one file", parents=[global_parent],
    )
    agg_p.add_argument("sources", help="Path to file with list of URLs")
    agg_p.add_argument(
        "--output-file", "-o", default=None,
        help="Write output to file instead of stdout",
    )

    # --- prune ---
    prune_p = sub.add_parser(
        "prune", help="Remove stale audit entries and exemptions", parents=[global_parent],
    )
    prune_p.add_argument("--no-imports", action="store_true", help="Don't prune imports")
    prune_p.add_argument("--no-exemptions", action="store_true", help="Don't prune exemptions")
    prune_p.add_argument("--no-audits", action="store_true", help="Don't prune audits")

    # --- fmt ---
    sub.add_parser("fmt", help="Normalize and sort TOML files", parents=[global_parent])

    # --- gc ---
    gc_p = sub.add_parser("gc", help="Clean up old packages from the cache", parents=[global_parent])
    gc_p.add_argument(
        "--max-age-days", type=int, default=30,
        help="Remove items older than this many days (default: 30)",
    )
    gc_p.add_argument(
        "--clean", action="store_true",
        help="Remove the entire cache directory",
    )

    # --- renew ---
    renew_p = sub.add_parser(
        "renew", help="Renew wildcard audit expirations", parents=[global_parent],
    )
    renew_p.add_argument("crate", nargs="?", default=None, help="Package to renew")
    renew_p.add_argument(
        "--expiring", action="store_true",
        help="Renew all wildcard audits expiring within 6 weeks",
    )

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        # Default to 'check'
        args.command = "check"

    # --frozen implies --locked
    if getattr(args, "frozen", False):
        args.locked = True

    command_map = {
        "init": "pyvet.commands.init",
        "check": "pyvet.commands.check",
        "certify": "pyvet.commands.certify",
        "inspect": "pyvet.commands.inspect_cmd",
        "diff": "pyvet.commands.diff",
        "suggest": "pyvet.commands.suggest",
        "trust": "pyvet.commands.trust",
        "import": "pyvet.commands.imports",
        "add-exemption": "pyvet.commands.add_exemption",
        "record-violation": "pyvet.commands.record_violation",
        "regenerate": "pyvet.commands.regenerate",
        "explain-audit": "pyvet.commands.explain_audit",
        "aggregate": "pyvet.commands.aggregate",
        "prune": "pyvet.commands.prune",
        "fmt": "pyvet.commands.fmt",
        "gc": "pyvet.commands.gc",
        "renew": "pyvet.commands.renew",
    }

    module_name = command_map.get(args.command)
    if not module_name:
        parser.print_help()
        sys.exit(1)

    import importlib
    mod = importlib.import_module(module_name)
    sys.exit(mod.run(args))
