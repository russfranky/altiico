"""Regression tests for D-082: the gate CLIs must run as documented.

`python scripts/<name>.py` puts `scripts/` — not the repo root — on
sys.path, so any gate script importing `scripts.*` crashed with
ModuleNotFoundError until each script bootstrapped the repo root onto
sys.path (AGENTS.md convention, D-080 fix pattern). These tests run the
CLIs exactly as the research workflow invokes them, with PYTHONPATH
scrubbed from the child environment so the bootstrap — not the
environment — is what makes the imports resolve.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

GATE_SCRIPTS = (
    "scripts/audit_avatar_completeness.py",
    "scripts/enforce_avatar_acceptance.py",
    "scripts/audit_curated_identity_bindings.py",
    "scripts/audit_catalog_completeness.py",
    "scripts/enforce_catalog_acceptance.py",
    "scripts/build_catalog_research_queue.py",
)


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_gate_clis_start_as_documented() -> None:
    for script in GATE_SCRIPTS:
        proc = run_cli(script, "--help")
        assert proc.returncode == 0, (
            f"{script} --help exited {proc.returncode}: {proc.stderr[-300:]}"
        )
        assert "ModuleNotFoundError" not in proc.stderr, script


def test_curated_audit_real_run_resolves_lazy_import(tmp_path: Path) -> None:
    # --help alone cannot prove the curated audit works: its scripts.*
    # import is lazy inside parse_registry(), so only a real run exercises it.
    out = tmp_path / "curated_identity_audit.json"
    proc = run_cli("scripts/audit_curated_identity_bindings.py", "--output", str(out))
    assert proc.returncode == 0, proc.stderr[-300:]
    assert "ModuleNotFoundError" not in proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "findings" in payload
