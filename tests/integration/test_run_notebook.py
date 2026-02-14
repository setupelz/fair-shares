"""
Tests for the run_notebook module for the fair-shares library.

"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fair_shares.library.exceptions import DataProcessingError
from fair_shares.run_notebook import run_notebook


class TestRunNotebook:
    """Test the run_notebook function."""

    @patch("fair_shares.run_notebook.pm.execute_notebook")
    def test_run_notebook_basic(self, mock_execute):
        """Test basic notebook execution."""
        mock_execute.return_value = MagicMock()

        run_notebook(
            notebook_path=Path("test.ipynb"),
            output_path=Path("output.ipynb"),
            parameters={"key": "value"},
        )

        # The function converts Path objects to strings before calling papermill
        mock_execute.assert_called_once_with(
            "test.ipynb", "output.ipynb", parameters={"key": "value"}
        )

    @patch("fair_shares.run_notebook.pm.execute_notebook")
    def test_run_notebook_with_kwargs(self, mock_execute):
        """Test notebook execution with additional kwargs."""
        mock_execute.return_value = MagicMock()

        run_notebook(
            notebook_path=Path("test.ipynb"),
            output_path=Path("output.ipynb"),
            parameters={"key": "value"},
            kernel_name="python3",
        )

        # The function converts Path objects to strings before calling papermill
        mock_execute.assert_called_once_with(
            "test.ipynb",
            "output.ipynb",
            parameters={"key": "value"},
            kernel_name="python3",
        )

    @patch("fair_shares.run_notebook.pm.execute_notebook")
    def test_run_notebook_execution_error(self, mock_execute):
        """Test handling of notebook execution errors."""
        mock_execute.side_effect = Exception("Execution failed")

        with pytest.raises(DataProcessingError, match="Execution failed"):
            run_notebook(
                notebook_path=Path("test.ipynb"),
                output_path=Path("output.ipynb"),
                parameters={},
            )


class TestCLI:
    """Test the CLI interface."""

    @patch("fair_shares.run_notebook.run_notebook")
    def test_cli_basic_args(self, mock_run):
        """Test CLI with basic arguments."""
        import sys

        test_args = [
            "run-notebook",
            "--notebook",
            "input.ipynb",
            "--output",
            "output.ipynb",
            "--param",
            "key=value",
        ]

        with patch.object(sys, "argv", test_args):
            from fair_shares.run_notebook import main

            main()

        mock_run.assert_called_once()
        call_args = mock_run.call_args
        # CLI now passes strings, not Path objects
        assert call_args[1]["notebook_path"] == "input.ipynb"
        assert call_args[1]["output_path"] == "output.ipynb"
        assert call_args[1]["parameters"] == {"key": "value"}

    def test_cli_missing_required_args(self):
        """Test CLI with missing required arguments."""
        import sys

        test_args = ["run-notebook", "--param", "key=value"]

        with patch.object(sys, "argv", test_args):
            from fair_shares.run_notebook import main

            with pytest.raises(SystemExit):
                main()
