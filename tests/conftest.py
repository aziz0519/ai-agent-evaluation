"""Pytest configuration and fixtures for the test suite."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The repo root must come first so ``agent`` and ``evaluations`` resolve as
# packages. ``agent/`` on sys.path ahead of the root would bind top-level
# ``agent`` to ``agent/agent.py`` (a plain module) and shadow the package,
# which breaks ``from agent.tools import ...``.
for entry in (
    REPO_ROOT,
    REPO_ROOT / "evaluations",
    REPO_ROOT / "agent",
):
    entry_str = str(entry)
    if entry_str in sys.path:
        sys.path.remove(entry_str)
    sys.path.append(entry_str)
