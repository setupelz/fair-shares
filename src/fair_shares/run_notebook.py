"""
Execute Jupyter notebooks with Papermill.

"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import papermill as pm

from fair_shares.library.exceptions import DataProcessingError


def run_notebook(
    notebook_path: Path | str,
    output_path: Path | str,
    parameters: dict[str, Any],
    **papermill_kwargs: Any,
) -> None:
    """
    Execute a Jupyter notebook with Papermill.

    This function executes a notebook with injected parameters using Papermill.
    The parameters are already validated upstream (by Pydantic or other means).

    Parameters
    ----------
    notebook_path : Path | str
        Path to the input notebook to execute
    output_path : Path | str
        Path where the executed notebook will be saved
    parameters : dict[str, Any]
        Dictionary of parameters to inject into the notebook
    **papermill_kwargs : Any
        Additional keyword arguments to pass to papermill.execute_notebook()

    Raises
    ------
    DataProcessingError
        If notebook execution fails
    """
    try:
        # Convert to string paths for papermill
        notebook_path_str = str(notebook_path)
        output_path_str = str(output_path)

        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Execute notebook with papermill
        pm.execute_notebook(
            notebook_path_str,
            output_path_str,
            parameters=parameters,
            **papermill_kwargs,
        )

    except Exception as e:
        # Papermill exceptions already contain the full error details
        raise DataProcessingError(
            f"Notebook execution failed: {notebook_path}\n"
            f"{'-' * 80}\n"
            f"Exception Type: {type(e).__name__}\n"
            f"Exception Message: {e!s}\n"
        ) from e


def main() -> None:
    """
    Command-line interface for running notebooks.

    This is a simplified CLI that expects parameters to be passed as a JSON string
    or via environment variables. For complex workflows, use the run_notebook()
    function directly from Python.

    Usage
    -----
    From command line with simple parameters::

        python -m fair_shares.run_notebook
            --notebook notebooks/example.ipynb
            --output output/executed.ipynb
            --param data_tag=data_primap_co2-ffi
            --param emission_category=co2-ffi

    Or from Snakemake/Python code, call run_notebook() directly.
    """
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Execute Jupyter notebook with Papermill"
    )
    parser.add_argument("--notebook", required=True, help="Input notebook path")
    parser.add_argument("--output", required=True, help="Output notebook path")
    parser.add_argument(
        "--param",
        action="append",
        dest="params",
        help="Parameter in key=value format (can be specified multiple times)",
    )
    parser.add_argument(
        "--params-json",
        help="Parameters as JSON string",
    )

    args = parser.parse_args()

    # Build parameters dict
    parameters = {}

    # Add parameters from --param flags
    if args.params:
        for param in args.params:
            if "=" not in param:
                print(f"Error: Invalid parameter format: {param}")
                print("Expected format: key=value")
                sys.exit(1)
            key, value = param.split("=", 1)
            # Try to parse as JSON (for booleans, numbers, etc.)
            # Otherwise treat as string
            try:
                parameters[key] = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                parameters[key] = value

    # Add parameters from JSON string
    if args.params_json:
        try:
            json_params = json.loads(args.params_json)
            parameters.update(json_params)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in --params-json: {e}")
            sys.exit(1)

    # Execute notebook
    try:
        run_notebook(
            notebook_path=args.notebook,
            output_path=args.output,
            parameters=parameters,
        )
        print(f"Successfully executed notebook: {args.notebook}")
        print(f"Output saved to: {args.output}")
    except DataProcessingError as e:
        sep_line = "=" * 80
        print(f"\n{sep_line}", file=sys.stderr)
        print("NOTEBOOK EXECUTION FAILED", file=sys.stderr)
        print(sep_line, file=sys.stderr)
        print(f"\nNotebook: {args.notebook}", file=sys.stderr)
        print("\nError Details:", file=sys.stderr)
        print(str(e), file=sys.stderr)
        print(f"\n{sep_line}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
