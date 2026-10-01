"""Each package module imports cleanly as the first import of a fresh interpreter."""

import subprocess
import sys

import pytest

MODULES = [
    "fair_shares",
    "fair_shares.library.config",
    "fair_shares.library.config.models",
    "fair_shares.library.utils",
    "fair_shares.library.utils.data.config",
    "fair_shares.library.validation",
]


@pytest.mark.parametrize("module", MODULES)
def test_module_imports_first(module):
    """A circular import shows up only when the module loads first."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
