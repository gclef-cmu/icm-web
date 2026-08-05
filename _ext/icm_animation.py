"""The ``{animation}`` directive — embed a build-rendered manim clip in a section.

Authors write::

    :::{animation}[notebooks/phasor-unrolled.ipynb]
    :::

The watch-only counterpart to ``{interactive}``: the companion's cells define
manim ``Scene``s ending with ``icm_anim.show(...)``. Normally
``tools/split_chapters.py`` expands the directive into a pre-rendered video
cell — bare looping ``<video>`` tags referencing committed anim/*.mp4 clips —
before Sphinx sees the page; this Sphinx directive is only a fallback that
validates the argument, warns, and renders nothing — the warning is a
tripwire for a splitter regression. No cell source is ever emitted here, so
the ../assets/ path rewrite lives only in the splitter and
_ext/icm_interactive.py.
"""
from __future__ import annotations

from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx
from sphinx.util import logging

logger = logging.getLogger(__name__)


def parse_directive_arg(arg: str) -> str:
    """Notebook path from the argument: `[path]` or a bare path.

    Kept in lockstep with tools/split_chapters.py and _ext/icm_interactive.py.
    """
    arg = arg.strip()
    if arg.startswith("[") and arg.endswith("]"):
        arg = arg[1:-1].strip()
    return arg


class AnimationDirective(Directive):
    """``:::{animation}[notebooks/foo.ipynb]`` — embed a baked manim clip."""

    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = False

    def run(self):
        rel = parse_directive_arg(self.arguments[0])
        source = self.state.document.get("source")
        if not source:
            return [self._error("`animation` could not locate the page source.")]
        target = (Path(source).parent / rel).resolve()
        if target.suffix != ".ipynb":
            return [self._error(f"`animation` expects a .ipynb notebook, got `{rel}`.")]
        if not target.is_file():
            return [self._error(f"`animation` cannot find `{rel}`.")]
        # Valid directive, wrong layer: the splitter should have expanded it
        # already. Warn — silence here would hide a split regression.
        logger.warning(
            "{animation} reached Sphinx unsplit — no clip will render for %s "
            "(did `make split` emit this section as .md instead of .ipynb?)",
            rel,
            location=(self.state.document.settings.env.docname, self.lineno),
        )
        return []

    def _error(self, message: str):
        return self.state_machine.reporter.error(
            message,
            nodes.literal_block(self.block_text, self.block_text),
            line=self.lineno,
        )


def setup(app: Sphinx) -> dict:
    app.add_directive("animation", AnimationDirective)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
