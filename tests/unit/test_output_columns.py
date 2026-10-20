"""Tests for the output column dictionary."""

from pathlib import Path

import pandas as pd
import pytest

from fair_shares.library.utils.output_columns import (
    column_entries,
    describe_columns,
    markdown,
    write_column_dictionary,
)

DOCS_PAGE = Path(__file__).parents[2] / "docs" / "user-guide" / "output-columns.md"


def test_every_entry_has_a_meaning():
    for name, entry in column_entries().items():
        assert entry.get("meaning"), name


def test_year_columns_collapse_into_one_row():
    out = describe_columns(["iso3c", "2020", "2030", "unit"])
    assert out["column"].tolist() == ["iso3c", "<year>", "unit"]


def test_undocumented_column_stops_the_description():
    with pytest.raises(KeyError, match="not-a-column"):
        describe_columns(["iso3c", "not-a-column"])


def test_dictionary_file_lists_each_file_and_column(tmp_path):
    path = write_column_dictionary(
        {"a.csv": ["iso3c", "co2-budget"], "b.csv": ["land-share"]},
        tmp_path / "columns.csv",
    )
    table = pd.read_csv(path, keep_default_na=False)
    assert table[["file", "column"]].values.tolist() == [
        ["a.csv", "iso3c"],
        ["a.csv", "co2-budget"],
        ["b.csv", "land-share"],
    ]
    assert table.loc[1, "unit"] == "Mt CO2"


def test_docs_page_is_generated_from_the_dictionary():
    assert DOCS_PAGE.read_text(encoding="utf-8") == markdown(), (
        "Regenerate: python -m fair_shares.library.utils.output_columns "
        "> docs/user-guide/output-columns.md"
    )
