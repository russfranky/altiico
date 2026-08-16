#!/usr/bin/env python3
"""Verify lightweight, credential-free Altiico Catalog repository invariants."""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


REQUIRED_FILES = (
    "README.md",
    "SCOPE.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "ROADMAP.md",
    "CITATION.cff",
    "Makefile",
    "pyproject.toml",
    ".editorconfig",
    ".gitattributes",
    ".python-version",
    ".github/CODEOWNERS",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    ".github/workflows/dependency-review.yml",
    "docs/ARCHITECTURE.md",
    "docs/DEVELOPMENT.md",
    "docs/RELEASING.md",
    "data/catalog_acceptance.json",
    "static/data/build-info.json",
    "static/data/hubzz-prealpha-staging.json",
    "static/index.html",
)


class Verification:
    def __init__(self) -> None:
        self.checks = 0
        self.errors: list[str] = []

    def require(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)


def load_json(path: Path, verification: Verification) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        verification.require(False, f"cannot read valid JSON from {path}: {exc}")
        return {}
    verification.require(isinstance(value, dict), f"{path} must contain a JSON object")
    return value if isinstance(value, dict) else {}


def integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root, default: inferred from this script",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    verification = Verification()

    for relative in REQUIRED_FILES:
        verification.require((root / relative).is_file(), f"missing required file: {relative}")

    try:
        pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        verification.require(False, f"invalid pyproject.toml: {exc}")
        pyproject = {}
    verification.require("tool" in pyproject, "pyproject.toml must define tool configuration")

    python_version = (root / ".python-version").read_text(encoding="utf-8").strip()
    verification.require(python_version == "3.11", ".python-version must be 3.11")

    acceptance = load_json(root / "data" / "catalog_acceptance.json", verification)
    for key in ("collections", "passing", "failing"):
        verification.require(integer(acceptance.get(key)), f"acceptance.{key} must be an integer")
    if all(integer(acceptance.get(key)) for key in ("collections", "passing", "failing")):
        verification.require(
            acceptance["passing"] + acceptance["failing"] == acceptance["collections"],
            "acceptance passing and failing counts must equal collections",
        )

    staging = load_json(
        root / "static" / "data" / "hubzz-prealpha-staging.json", verification
    )
    summary = staging.get("summary")
    verification.require(isinstance(summary, dict), "staging.summary must be an object")
    if isinstance(summary, dict):
        required = (
            "catalogSets",
            "stageableSets",
            "deferredSets",
            "sourceAvatars",
            "binaryValidatedSourceAvatars",
        )
        for key in required:
            verification.require(integer(summary.get(key)), f"staging.summary.{key} must be an integer")
        if all(integer(summary.get(key)) for key in required):
            verification.require(
                summary["stageableSets"] + summary["deferredSets"] == summary["catalogSets"],
                "staging stageable and deferred counts must equal catalog sets",
            )
            verification.require(
                summary["binaryValidatedSourceAvatars"] <= summary["sourceAvatars"],
                "binary-validated source count cannot exceed source avatar count",
            )

    build_info = load_json(root / "static" / "data" / "build-info.json", verification)
    files = build_info.get("files")
    verification.require(isinstance(files, dict), "build-info.files must be an object")
    if isinstance(files, dict):
        collections_file = files.get("collections")
        verification.require(
            isinstance(collections_file, str) and bool(collections_file),
            "build-info.files.collections must be a non-empty string",
        )
        if isinstance(collections_file, str) and collections_file:
            verification.require(
                (root / "static" / "data" / collections_file).is_file(),
                f"build-info references missing file: static/data/{collections_file}",
            )

    index = (root / "static" / "index.html").read_text(encoding="utf-8")
    verification.require("<title>Altiico Catalog</title>" in index, "public title must use Altiico Catalog")
    verification.require("<h1>Altiico</h1>" in index, "public heading must use Altiico")
    verification.require(
        'name="description"' in index, "public HTML must include a meta description"
    )

    readme = (root / "README.md").read_text(encoding="utf-8")
    for marker in ("Project maturity: alpha", "CONTRIBUTING.md", "SECURITY.md", "make verify"):
        verification.require(marker in readme, f"README is missing required marker: {marker}")

    if verification.errors:
        print(f"repository verification failed with {len(verification.errors)} error(s):", file=sys.stderr)
        for error in verification.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(f"repository verification passed ({verification.checks} checks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
