"""MkDocs hooks for the fair-shares documentation build.

mkdocs-jupyter checks every Markdown page for a notebook kernel by reading it
with jupytext, before it applies its ``include`` patterns. jupytext takes a
line starting with ``:::`` for a pandoc div, so where pandoc is installed every
API page (the mkdocstrings ``::: fair_shares...`` directives) goes through
pandoc, which warns that the div is never closed. No docs page is a Markdown
notebook, so the plugin is limited to ``.py`` and ``.ipynb`` files.
"""

from __future__ import annotations

from typing import Any

from mkdocs_jupyter.plugin import Plugin


def on_config(config: Any) -> Any:
    """Keep mkdocs-jupyter off the Markdown pages."""
    Plugin._supported_extensions = [".ipynb", ".py"]
    return config
