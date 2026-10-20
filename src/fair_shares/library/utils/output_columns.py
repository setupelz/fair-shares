"""Column dictionary of the fair-shares outputs.

The dictionary lives in ``conf/output_columns.yaml``. Outputs write the entries
of their own columns to ``columns.csv`` beside them, and the docs page
``docs/user-guide/output-columns.md`` is generated from the same file:

    python -m fair_shares.library.utils.output_columns > docs/user-guide/output-columns.md
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import cache
from importlib import resources
from pathlib import Path

import pandas as pd
import yaml

YEAR_KEY = "<year>"


@cache
def _sections() -> dict[str, dict[str, dict[str, str]]]:
    text = resources.files("fair_shares.conf").joinpath("output_columns.yaml")
    return yaml.safe_load(text.read_text(encoding="utf-8"))["sections"]


def column_entries() -> dict[str, dict[str, str]]:
    """Return every documented column, ``{name: {"meaning", "unit"?}}``."""
    return {
        name: entry
        for section in _sections().values()
        for name, entry in section.items()
    }


def _key(column: object) -> str:
    return YEAR_KEY if str(column).isdigit() else str(column)


def describe_columns(columns: Iterable[object]) -> pd.DataFrame:
    """Return ``column``, ``meaning`` and ``unit`` for ``columns``, in order.

    Year columns collapse into one ``<year>`` row.

    Raises
    ------
    KeyError
        If a column has no entry in the dictionary
    """
    entries = column_entries()
    keys = list(dict.fromkeys(_key(c) for c in columns))
    missing = [k for k in keys if k not in entries]
    if missing:
        raise KeyError(
            f"Columns without an entry in conf/output_columns.yaml: {missing}"
        )
    return pd.DataFrame(
        [
            {
                "column": k,
                "meaning": entries[k]["meaning"],
                "unit": entries[k].get("unit", ""),
            }
            for k in keys
        ]
    )


def write_column_dictionary(files: Mapping[str, Iterable[object]], path: Path) -> Path:
    """Write ``columns.csv``, one row per file and column.

    The columns are ``file``, ``column``, ``meaning`` and ``unit``.

    ``files`` maps each output file name to its columns.

    Raises
    ------
    KeyError
        As :func:`describe_columns`
    """
    frames = [describe_columns(cols).assign(file=name) for name, cols in files.items()]
    table = pd.concat(frames, ignore_index=True)[["file", "column", "meaning", "unit"]]
    path = Path(path)
    table.to_csv(path, index=False)
    return path


def markdown() -> str:
    """Return the docs page of the dictionary, one table per section."""
    lines = [
        "---",
        "title: Output columns",
        "description: What every column of the fair-shares outputs holds",
        "---",
        "",
        "<!-- Generated from src/fair_shares/conf/output_columns.yaml by",
        "     python -m fair_shares.library.utils.output_columns. Do not edit. -->",
        "",
        "# Output columns",
        "",
        "Every output folder also holds `columns.csv` with the entries of its own columns.",
        "`<year>` stands for every year column.",
    ]
    for section, entries in _sections().items():
        lines += [
            "",
            f"## {section}",
            "",
            "| Column | Meaning | Unit |",
            "| --- | --- | --- |",
        ]
        for name, entry in entries.items():
            meaning = entry["meaning"].replace("|", "\\|")
            lines.append(f"| `{name}` | {meaning} | {entry.get('unit', '')} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    print(markdown(), end="")
