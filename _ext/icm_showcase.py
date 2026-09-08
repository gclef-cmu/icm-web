"""The ``{showcase}`` directive — one card per featured piece on the course
Showcase page.

The body's first line is a Markdown link whose text is the student's name
(``Anonymous`` for an unattributed piece) and whose target is the clip; the
rest is the composer's notes::

    :::{showcase}
    [Arisa Okamura](./A1/Arisa_Okamura.mp3)

    A few sentences from the composer about the piece.
    :::

Reuses icm_audio's play/pause chip and download control; the seek bar and
time readout are driven by _static/audio-chip.js through the card's
``audio-track`` row. Only the player chrome is raw HTML, so the PDF build
still gets the name and the notes.
"""
from __future__ import annotations

from html import escape

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.application import Sphinx

from icm_audio import _LINK_RE, _chip_button, _download_link

ANONYMOUS = "Anonymous"
NOTES_LABEL = "Composer's notes"


class ShowcaseDirective(Directive):
    """``:::{showcase}`` — a ``showcase-card``: the chip beside the name and
    a seek bar, the download icon on the trailing edge, notes below."""

    has_content = True

    def run(self):
        content = self.content
        # Locate the link line (the first non-blank line of the body).
        link_index = next(
            (i for i, line in enumerate(content) if line.strip()), None
        )
        if link_index is None:
            return [self._error("`showcase` directive requires a link to the clip.")]

        match = _LINK_RE.match(content[link_index])
        if match is None:
            return [
                self._error(
                    "`showcase` directive's first line must be a Markdown link "
                    "whose text is the student's name, e.g. "
                    "`[Arisa Okamura](./A1/Arisa_Okamura.mp3)`."
                )
            ]
        name, src = match.group("text").strip(), match.group("href").strip()

        card = _div("showcase-card")

        # The player row. audio-chip.js treats one `.audio-track` as one
        # player: the chip in it also drives the row's seek bar.
        head = _div("showcase-head", "audio-track")
        head += nodes.raw(
            "", _chip_button(src, name, "audio-chip-lg audio-chip-xl"), format="html"
        )
        title = _div("showcase-title")
        heading = nodes.paragraph("", name, classes=["showcase-name"])
        if name == ANONYMOUS:
            heading["classes"].append("showcase-anon")
        title += heading
        title += nodes.raw("", _scrub_bar(name), format="html")
        head += title
        head += nodes.raw("", _download_link(src, name), format="html")
        card += head

        # The notes, parsed as Markdown; a card with no notes has no block.
        body = content[link_index + 1 :]
        if any(line.strip() for line in body):
            notes = _div("showcase-notes")
            notes += nodes.paragraph("", NOTES_LABEL, classes=["showcase-notes-label"])
            self.state.nested_parse(body, self.content_offset + link_index + 1, notes)
            card += notes

        return [card]

    def _error(self, message: str):
        return self.state_machine.reporter.error(
            message,
            nodes.literal_block(self.block_text, self.block_text),
            line=self.lineno,
        )


def _div(*classes: str) -> nodes.container:
    """A plain ``<div>`` with these classes. ``is_div`` makes MyST's writer
    drop Bootstrap's ``container`` class (see ClassContainerDirective in
    icm_audio), so no padding override is needed."""
    node = nodes.container(is_div=True)
    node["classes"] = list(classes)
    return node


# Seek bar + time readout. `--p` is the played fraction: the CSS paints the
# track red up to it and audio-chip.js updates it per frame.
def _scrub_bar(name: str) -> str:
    name = escape(name, quote=True)
    return (
        '<div class="audio-scrub">'
        '<input type="range" class="audio-seek" min="0" max="1000" value="0" '
        f'step="1" aria-label="Seek: {name}" style="--p:0%">'
        '<span class="audio-time">'
        '<span class="audio-time-cur">0:00</span>'
        '<span class="audio-time-sep"> / </span>'
        '<span class="audio-time-dur">–:––</span>'
        "</span></div>"
    )


def setup(app: Sphinx) -> dict:
    app.setup_extension("icm_audio")  # the chip and download controls
    app.add_directive("showcase", ShowcaseDirective)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
