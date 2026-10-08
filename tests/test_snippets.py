"""The website snippets: the hub's ``scripts/embed-snippets.mjs --check`` passes for this SDK
(regions in examples/, examples/snippets.manifest.json, README blocks). See CONTRIBUTING.md.

The hub is ``QBITFLOW_HUB_DIR``, or two directories up (this SDK's place in the hub). A standalone
clone, or a machine without ``node``, skips the test; an invalid ``QBITFLOW_HUB_DIR`` fails it."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SDK_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path("scripts") / "embed-snippets.mjs"
CATALOG = Path("snippets") / "catalog.json"


def _is_hub(path: Path) -> bool:
    return (path / SCRIPT).is_file() and (path / CATALOG).is_file()


def test_snippets_match_the_hub_catalog() -> None:
    configured = os.environ.get("QBITFLOW_HUB_DIR", "")
    if configured:
        hub = Path(configured).resolve()
        assert _is_hub(hub), f"QBITFLOW_HUB_DIR={configured} has no {SCRIPT} and {CATALOG}"
    else:
        hub = SDK_ROOT.parent.parent
        if not _is_hub(hub):
            pytest.skip(f"no hub checkout at {hub}: set QBITFLOW_HUB_DIR to run the snippet check")
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed: the snippet check needs Node 18+")

    result = subprocess.run(
        [node, str(hub / SCRIPT), "--check", str(SDK_ROOT)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"embed-snippets --check failed:\n{result.stdout}{result.stderr}"
