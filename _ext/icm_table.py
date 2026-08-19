"""Headerless tables: pipe rows with no delimiter line.

A run of ``| … |`` rows with no ``|---|`` line is not a table in Markdown,
so MyST would render it as prose. A ``source-read`` substitution prefixes
such a run with an empty header row plus a delimiter so the parser builds a
real table, and a ``doctree-read`` pass then removes any table head whose
cells are all empty — hand-written ``| | |`` headers included — so nothing
renders where the header would sit. Fenced code blocks are skipped so
examples render literally.
"""
from __future__ import annotations

import json
import re

from docutils import nodes
from sphinx.application import Sphinx

# A pipe row must start and end with `|`; docutils line blocks have no
# trailing pipe, so they stay out of reach.
ROW_RE = re.compile(r"^\|.*\|$")
# A delimiter cell: dashes with optional alignment colons.
DELIM_CELL_RE = re.compile(r"^\s*:?-+:?\s*$")
# Cell separators are pipes that aren't escaped.
PIPE_RE = re.compile(r"(?<!\\)\|")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def _cells(row: str) -> list[str]:
    return PIPE_RE.split(row.strip())[1:-1]


def _is_delimiter(row: str) -> bool:
    cells = _cells(row)
    return bool(cells) and all(DELIM_CELL_RE.match(c) for c in cells)


def _expand_block(block: list[str]) -> list[str]:
    """Prefix a headerless run with an empty header and a delimiter row."""
    ncols = max(len(_cells(line)) for line in block)
    indent = block[0][: len(block[0]) - len(block[0].lstrip())]
    header = indent + "|" + "  |" * ncols + "\n"
    delim = indent + "|" + " --- |" * ncols + "\n"
    return [header, delim] + block


def _expand_text(text: str) -> str:
    """Expand headerless pipe runs in Markdown, outside code fences."""
    out: list[str] = []
    block: list[str] = []
    fence: str | None = None

    def flush() -> None:
        if not block:
            return
        # A run containing a delimiter row is an ordinary table; hands off.
        if any(_is_delimiter(line) for line in block):
            out.extend(block)
        else:
            out.extend(_expand_block(block))
        block.clear()

    for line in text.splitlines(keepends=True):
        if fence is not None:
            out.append(line)
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
            continue
        fm = FENCE_RE.match(line)
        if fm:
            flush()
            fence = fm.group(1)
            out.append(line)
            continue
        if ROW_RE.match(line.strip()):
            block.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return "".join(out)


def substitute_tables(app: Sphinx, docname: str, source: list[str]) -> None:
    """``source-read`` handler; notebooks get the same JSON round-trip as
    icm_roles so myst-nb's second decode sees valid cell sources."""
    text = source[0]
    if str(app.env.doc2path(docname)).endswith(".ipynb"):
        try:
            nb = json.loads(text)
        except ValueError:
            source[0] = _expand_text(text)
            return
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "markdown":
                continue
            cell_src = cell.get("source", "")
            joined = "".join(cell_src) if isinstance(cell_src, list) else cell_src
            cell["source"] = _expand_text(joined)
        source[0] = json.dumps(nb)
    else:
        source[0] = _expand_text(text)


def strip_empty_theads(app: Sphinx, doctree: nodes.document) -> None:
    """Drop any table head whose cells are all empty."""
    for thead in list(doctree.findall(nodes.thead)):
        if any(entry.astext().strip() for entry in thead.findall(nodes.entry)):
            continue
        tgroup = thead.parent
        tgroup.parent["classes"].append("headerless")
        tgroup.remove(thead)


def setup(app: Sphinx) -> dict:
    app.connect("source-read", substitute_tables)
    app.connect("doctree-read", strip_empty_theads)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
