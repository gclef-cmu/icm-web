"""``figure`` directive that also accepts the upstream simple form.

Besides the standard ``:::{figure} path`` + options form, a figure can be
just an image line and a caption (matching the icm-text source)::

    :::{figure}
    ![alt text](./assets/x.png)

    The caption.
    :::

Registered with ``override=True``, replacing the stock figure directive.
"""
from __future__ import annotations

import re

from sphinx.application import Sphinx
from sphinx.directives.patches import Figure  # Sphinx's Figure: adds :name:/numfig

# The simple form's image line: ``![alt](path)`` or upstream's
# ``:figure![alt](path)``. The alt match is greedy so it tolerates square
# brackets inside the text (e.g. "on [a,b]").
_IMAGE_RE = re.compile(
    r"^\s*(?::figure)?!\[(?P<alt>.*)\]\(\s*(?P<path>\S+?)\s*\)\s*$"
)


class SimpleFigure(Figure):
    """``figure`` that also accepts an image as its first body line."""

    required_arguments = 0
    optional_arguments = 1

    def run(self):
        if not self.arguments:
            # No path argument → expect the image as the first body line.
            index = next(
                (i for i, line in enumerate(self.content) if line.strip()), None
            )
            match = _IMAGE_RE.match(self.content[index]) if index is not None else None
            if match is None:
                return [
                    self.state_machine.reporter.error(
                        "`figure` directive needs a path argument or a Markdown "
                        "image as its first line, e.g. `![alt](./assets/x.png)`.",
                        line=self.lineno,
                    )
                ]
            self.arguments = [match.group("path")]
            if match.group("alt"):
                self.options.setdefault("alt", match.group("alt"))
            # Drop the image line (and the blank line after it) so the rest of
            # the content becomes the caption.
            del self.content[index]
            while index < len(self.content) and not self.content[index].strip():
                del self.content[index]
        return super().run()


def setup(app: Sphinx) -> dict:
    app.add_directive("figure", SimpleFigure, override=True)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
