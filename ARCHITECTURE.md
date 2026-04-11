# Architecture

This document describes the internal architecture of pyvet, its design principles, and how the pieces fit together.

## Philosophy

pyvet is an audit **tracking** and **enforcement** tool, not a scanner.

- **Humans are the auditors.** pyvet never analyzes, scans, or executes package source code. It records the fact that a human reviewed a package and attested that it meets certain criteria.
- **No central authority.** All audit data lives in plain TOML files checked into your repository. There is no server, no database, and no central infrastructure to compromise.
- **Low friction above all else.** The tool should be trivial to adopt, unobtrusive in daily workflows, and guide developers through each step. If auditing is too painful, people won't do it.
- **Trust is explicit and direct.** When you import audits from another organization, you are trusting *their* judgment directly. Trust is never transitive — you cannot import someone else's imports.
- **Violations are hard stops.** A violation entry overrides everything, including exemptions. Known-bad packages cannot be accidentally allowed.

## High-Level Flow

```
 Developer's project
 ┌─────────────────────────────────────────────────────┐
 │  pyproject.toml          uv.lock                    │
 │                                                     │
 │  supply-chain/                                      │
 │  ├── config.toml     (exemptions, policy, imports)  │
 │  ├── audits.toml     (audits, criteria, violations) │
 │  └── imports.lock    (cached external audit sets)   │
 └──────────────────────────┬──────────────────────────┘
                            │
                    pyvet check
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        Parse lockfile   Load audits   Fetch imports
        (uv.lock)        (local)       (if not --locked)
              │             │             │
              └──────┬──────┘─────────────┘
                     ▼
              ┌─────────────┐
              │   Resolver  │  For each third-party dep:
              │             │  violation? full audit? wildcard?
              │             │  trusted? exemption? delta chain?
              └──────┬──────┘
                     │
              ┌──────┴──────┐
              ▼             ▼
          PASS (0)      FAIL (1)
```

## Module Structure

```
src/pyvet/
├── __init__.py          Package version
├── __main__.py          python -m pyvet entry point
├── cli.py               argparse CLI definition, command dispatch
│
├── core/                Core logic (no I/O to terminal)
│   ├── config.py        Load/save config.toml and audits.toml
│   ├── audits.py        Audit data accessors
│   ├── lockfile.py      Parse uv.lock / requirements.txt → LockedDep list
│   ├── resolver.py      Audit graph resolution algorithm
│   ├── criteria.py      Criteria definitions, implication graph
│   └── imports.py       Fetch & cache external audit sets
│
├── commands/            One module per CLI command
│   ├── init.py          pyvet init
│   ├── check.py         pyvet check
│   ├── certify.py       pyvet certify (full, delta, wildcard)
│   ├── inspect_cmd.py   pyvet inspect
│   ├── diff.py          pyvet diff
│   ├── suggest.py       pyvet suggest
│   ├── trust.py         pyvet trust
│   ├── imports.py       pyvet import {add, fetch, list}
│   ├── add_exemption.py pyvet add-exemption
│   ├── record_violation.py  pyvet record-violation
│   ├── regenerate.py    pyvet regenerate {exemptions, imports}
│   ├── explain_audit.py pyvet explain-audit
│   ├── aggregate.py     pyvet aggregate
│   ├── prune.py         pyvet prune
│   ├── fmt.py           pyvet fmt
│   ├── gc.py            pyvet gc
│   └── renew.py         pyvet renew
│
├── pypi/                PyPI API interaction
│   └── client.py        Download sdists, verify SHA-256, fetch metadata
│
└── utils/               Shared utilities
    ├── ui.py            Rich console helpers
    ├── git.py           Read git config for auditor identity
    └── toml.py          TOML read/write via tomlkit
```

## The Resolver

The resolver is the heart of pyvet. Given a list of locked dependencies and the audit/config data, it determines whether each dependency is vetted.

### Resolution Order

For each third-party dependency at a specific version, the resolver checks the following in order:

1. **Violations** — If any violation entry matches this version, the dependency **fails immediately**, regardless of any audits or exemptions. This is an integrity constraint.

2. **Full audits** — If a full audit exists for this exact version with criteria that satisfy the requirement, the dependency passes.

3. **Wildcard audits** — If a wildcard audit exists for this package (matching a PyPI user and date range) with sufficient criteria, the dependency passes.

4. **Trusted publishers** — If a trusted publisher entry exists with sufficient criteria, the dependency passes.

5. **Exemptions** — If this exact version is listed in the exemptions table with sufficient criteria, the dependency passes. Exemptions represent "not yet audited but allowed."

6. **Delta chains** — Build a graph from all delta audit entries. If there exists a path from any anchored version (a fully-audited or exempted version) to the target version, and all edges on that path carry sufficient criteria, the dependency passes. Delta edges are bidirectional (going from 1.1→1.0 is valid).

7. **Unvetted** — If none of the above apply, the dependency fails.

### Criteria Resolution

Criteria have an `implies` relationship that forms a directed graph:

```
safe-to-deploy ──implies──▶ safe-to-run
```

A dependency that requires `safe-to-run` is satisfied by an audit for `safe-to-deploy`. The criteria graph supports arbitrary custom criteria with arbitrary implication chains.

The `expands_to()` method computes the transitive closure: all criteria implied by a given criteria name. This is computed once and used for all comparisons.

### Policy

The resolver determines the required criteria per-package through the policy table:

- **Top-level packages** default to `safe-to-deploy`
- **Dev-only dependencies** default to `safe-to-run`
- **`dependency-criteria`** overrides allow relaxing or tightening criteria for specific transitive dependencies
- An empty `dependency-criteria` list (`[]`) means "no audit required"

## Data Files

### `audits.toml`

Owned by the project. Contains:

| Section | Purpose |
|---|---|
| `[criteria.*]` | Custom criteria definitions with `description` and `implies` |
| `[[audits.*]]` | Full audits, delta audits, and violation entries |
| `[[wildcard-audits.*]]` | Wildcard audits (trust all versions by a user within a date range) |
| `[[trusted.*]]` | Trusted publisher entries |

This file can be imported by other projects. It should never be pruned — even audits for packages you no longer use may be valuable to others.

### `config.toml`

Project-specific, not importable. Contains:

| Section | Purpose |
|---|---|
| `[pyvet]` | Tool version metadata |
| `default-criteria` | Default criteria for `certify` (default: `safe-to-deploy`) |
| `[policy.*]` | Per-package criteria overrides, dependency-criteria |
| `[[exemptions.*]]` | Packages allowed without audits (the "backlog") |
| `[imports.*]` | External audit sources to trust |

### `imports.lock`

Auto-generated by `pyvet import fetch` and `pyvet check` (unless `--locked`). Caches fetched audit data with SHA-256 hashes for integrity. Treat as an implementation detail.

## Security Properties

- **Hash verification.** Every sdist downloaded from PyPI is verified against the SHA-256 digest from PyPI's metadata before extraction.
- **No code execution.** pyvet never runs `setup.py`, `pip install`, or any package code. Only sdist extraction (tar/zip) and text inspection.
- **HTTPS only.** All remote fetches (PyPI API, import sources) use HTTPS.
- **Import integrity.** `imports.lock` stores SHA-256 of fetched audit files. Tampering between fetches is detectable.
- **Violation = hard block.** A violation entry cannot be overridden by an exemption or audit. If someone records a violation for a package, every project that imports those audits will be blocked from using it.
- **No transitive trust.** You cannot import another project's imports. Trust relationships are always one hop deep and explicitly configured.

## Key Design Decisions

| Decision | Rationale |
|---|---|
| TOML format | Human-readable, supports comments, parity with cargo-vet |
| tomlkit for writing | Preserves comments, formatting, and key ordering across edits |
| `supply-chain/` directory | Same convention as cargo-vet; lives next to lockfile; easy CODEOWNERS |
| sdist for inspection | Contains actual source code; wheels are compiled artifacts |
| `uv.lock` as primary lockfile | Fully pinned with hashes; uv is the project's package manager |
| httpx for HTTP | Modern, well-maintained, async-capable |
| No database | Everything is flat files in version control — auditable and diffable |
| argparse for CLI | Standard library, no extra dependency, user-requested |
| rich for output | Tables, colors, progress — worth the single dependency |

## Differences from cargo-vet

pyvet is a faithful port of cargo-vet's design to the Python ecosystem. Key adaptations:

| cargo-vet (Rust) | pyvet (Python) | Reason |
|---|---|---|
| Reads `Cargo.lock` | Reads `uv.lock` | Different package manager |
| `unsafe` blocks as risk signal | `eval`/`exec`/`ctypes`/`subprocess` as risk signals | Different language risk model |
| `crates.io` user-id (numeric) | PyPI user-login (string) | Different registry API |
| Sourcegraph links for inspection | Direct PyPI sdist download | Sourcegraph doesn't index PyPI |
| `audit-as-crates-io` | Not applicable | No equivalent of Cargo patches in Python |
| `filter-graph` | Not applicable | No Cargo feature flags |
| `dump-graph` | Not applicable | No `cargo metadata` equivalent needed |
