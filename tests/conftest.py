"""Shared fixtures. Tests that need a run set IM_RUN_DIR (a run's OUT_DIR); the ROR snapshot is the one that run
unzipped (OUT_DIR/work/ror) unless IM_ROR_DIR names another. Without IM_RUN_DIR they are skipped (README, "Testing")."""

import json
import os
from pathlib import Path

import pytest

from institution_mapping.pipeline import CODING


@pytest.fixture(scope="session")
def settings():
    return json.loads((CODING / "coding_rules.json").read_text(encoding="utf-8"))


def _env_dir(name):
    path = os.environ.get(name)
    if not path:
        pytest.skip(f"set {name} to run this test")
    return Path(path)


@pytest.fixture(scope="session")
def run_dir():
    return _env_dir("IM_RUN_DIR")


@pytest.fixture(scope="session")
def ror_dir(run_dir):
    return Path(os.environ.get("IM_ROR_DIR") or run_dir / "work" / "ror")
