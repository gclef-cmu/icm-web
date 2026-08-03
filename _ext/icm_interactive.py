"""The ``{interactive}`` directive — embed a runnable notebook in a section.

Authors write::

    :::{interactive}[notebooks/fourier-winding.ipynb]
    :::

and the companion notebook's cells are embedded inline. A code cell's source
visibility comes from a whole-line ``# hide`` / ``# collapse`` / ``# show``
marker (case-insensitive, first wins, kept in the source).

Normally ``tools/split_chapters.py`` expands the directive into real notebook
cells — build-executed, kept runnable by the live-code layer — before Sphinx
sees the page. This Sphinx directive is only the fallback for unsplit
Markdown pages: it renders the notebook statically (prose + visible code
blocks, no outputs) so the directive never errors as unknown.
"""
from __future__ import annotations

import re
from pathlib import Path

import nbformat
from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import StringList
from sphinx.application import Sphinx


def parse_interactive_arg(arg: str) -> str:
    """Notebook path from the argument: `[path]` or a bare path.

    Kept in lockstep with tools/split_chapters.py.
    """
    arg = arg.strip()
    if arg.startswith("[") and arg.endswith("]"):
        arg = arg[1:-1].strip()
    return arg


# Whole-line `# hide` / `# collapse` / `# show` visibility marker; kept in
# lockstep with tools/split_chapters.py.
VISIBILITY_MARKER_RE = re.compile(r"^#\s*(hide|collapse|show)\s*$", re.IGNORECASE)


def cell_visibility(source: str) -> str:
    """Return ``"hide"``, ``"collapse"`` or ``"show"`` for a notebook code cell."""
    for line in source.splitlines():
        m = VISIBILITY_MARKER_RE.match(line.strip())
        if m:
            return m.group(1).lower()
    return "show"


# Companion notebooks reference chapter data as ../assets/ etc., correct from
# their notebooks/ dir; embedding hoists their cells up next to the page, so
# those prefixes become page-relative ./assets/ etc. Kept in lockstep with
# tools/split_chapters.py.
FLATTEN_PATH_REWRITES = (
    ("../assets/", "./assets/"),
    ("../code/", "./code/"),
    ("../figures/", "./figures/"),
)


def rewrite_flattened_paths(source: str) -> str:
    for old, new in FLATTEN_PATH_REWRITES:
        source = source.replace(old, new)
    return source


class InteractiveDirective(Directive):
    """``:::{interactive}[notebooks/foo.ipynb]`` — embed a runnable notebook in the page."""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = False

    def run(self):
        rel = parse_interactive_arg(self.arguments[0])
        source = self.state.document.get("source")
        if not source:
            return [self._error("`interactive` could not locate the page source.")]
        target = (Path(source).parent / rel).resolve()
        if target.suffix != ".ipynb":
            return [self._error(f"`interactive` expects a .ipynb notebook, got `{rel}`.")]
        return self._render_notebook(target, rel)

    def _render_notebook(self, path: Path, rel: str):
        """Fallback static render: markdown cells as prose, visible code
        cells as static blocks, hidden/collapsed cells skipped, no outputs.
        The split path never reaches this branch.
        """
        try:
            nb = nbformat.read(str(path), as_version=4)
        except OSError as exc:
            return [self._error(f"`interactive` cannot read `{rel}`: {exc}")]

        out: list[nodes.Node] = []
        for c in nb.cells:
            if c.cell_type == "markdown":
                container = nodes.container()
                source = rewrite_flattened_paths(c.source)
                self.state.nested_parse(StringList(source.splitlines()), 0, container)
                out += container.children
            elif c.cell_type == "code":
                code = rewrite_flattened_paths(c.source)
                if cell_visibility(code) != "show" or not code.strip():
                    continue
                block = nodes.literal_block(code, code)
                block["language"] = "python"
                block["classes"].append("interactive-code-block")
                out.append(block)
        return out

    def _error(self, message: str):
        return self.state_machine.reporter.error(
            message,
            nodes.literal_block(self.block_text, self.block_text),
            line=self.lineno,
        )


def setup(app: Sphinx) -> dict:
    app.add_directive("interactive", InteractiveDirective)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
