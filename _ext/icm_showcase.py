"""The ``{showcase}`` directive — one card per featured piece on the course
Showcase page.

The body's first line is a Markdown link whose text is the student's name
(``Anonymous`` for an unattributed piece) and whose target is the clip; the
rest is the composer's notes::

    :::{showcase}
    :track: Creative
    [Arisa Okamura](./A1/Arisa_Okamura.mp3)

    A few sentences from the composer about the piece.
    :::

``:track:`` is optional and renders as a tag beside the name. ``Creative``
and ``Technical`` get their own colour; any other value falls back to a
neutral tag, so a future assignment can invent its own track names without
touching this file.

Every card is the same three stacked rows — title, player, notes — so the
name, the player and the notes all start on one leading edge whatever the
medium. Only the middle row differs, and the target's extension picks it.
Audio (``.mp3``, ``.wav``, …) reuses icm_audio's play/pause chip with the
seek bar and time readout driven by _static/audio-chip.js through the
row's ``audio-track`` class. Video (``.mp4``, ``.webm``, ``.mov``,
``.m4v``) gets a native ``<video controls>`` — the Technical directions
submit a narrated demo video rather than a clip. audio-chip.js keeps one
player going at a time across both kinds.

Only the player chrome is raw HTML, so the PDF build still gets the name,
the track tag and the notes.
"""
from __future__ import annotations

import posixpath
import re
from html import escape
from urllib.parse import urlsplit

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.application import Sphinx

from icm_audio import _LINK_RE, _chip_button, _download_link

ANONYMOUS = "Anonymous"
NOTES_LABEL = "Composer's notes"

# Extensions the browser will play in a <video> element. `.mkv` is
# deliberately absent: it is a common submission format but no browser
# plays it, so it should be transcoded rather than silently linked.
VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v")

# Track names with a colour of their own; anything else gets the neutral tag.
KNOWN_TRACKS = ("creative", "technical")


class ShowcaseDirective(Directive):
    """``:::{showcase}`` — a ``showcase-card``. Audio: the chip beside the
    name and a seek bar, the download icon on the trailing edge. Video: the
    name row above a native player. Notes below, either way."""

    has_content = True
    option_spec = {"track": directives.unchanged}

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
        track = self.options.get("track", "").strip()
        is_video = _is_video(src)

        card = _div("showcase-card", *(["showcase-card-video"] if is_video else []))
        card += self._head(name, src, track)
        card += self._media(name, src, is_video)

        # The notes, parsed as Markdown; a card with no notes has no block.
        body = content[link_index + 1 :]
        if any(line.strip() for line in body):
            notes = _div("showcase-notes")
            notes += nodes.paragraph("", NOTES_LABEL, classes=["showcase-notes-label"])
            self.state.nested_parse(body, self.content_offset + link_index + 1, notes)
            card += notes

        return [card]

    def _head(self, name: str, src: str, track: str):
        """The title row: the name and its track tag on the leading edge, the
        download icon on the trailing one. Identical for audio and video, so
        every card's name starts on the same axis."""
        head = _div("showcase-head")
        title = _div("showcase-title")
        heading = nodes.paragraph("", "", classes=["showcase-name"])
        if name == ANONYMOUS:
            heading["classes"].append("showcase-anon")
        heading += nodes.Text(name)
        if track:
            heading += _track_tag(track)
        title += heading
        head += title
        head += nodes.raw("", _download_link(src, name), format="html")
        return head

    def _media(self, name: str, src: str, is_video: bool):
        """The player row, under the title and on the same leading edge as
        it: the chip and the seek bar it drives, or the video."""
        if is_video:
            media = _div("showcase-media", "showcase-media-video")
            media += nodes.raw("", _video_player(src, name), format="html")
            return media
        # audio-chip.js treats one `.audio-track` as one player: the chip in
        # it also drives the row's seek bar.
        media = _div("showcase-media", "audio-track")
        media += nodes.raw(
            "", _chip_button(src, name, "audio-chip-lg audio-chip-xl"), format="html"
        )
        media += nodes.raw("", _scrub_bar(name), format="html")
        return media

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


def _is_video(src: str) -> bool:
    """Does this target point at something a ``<video>`` should play? The
    path is taken off the URL first, so a query string or fragment on a
    remote clip doesn't hide the extension."""
    path = urlsplit(src).path or src
    return posixpath.splitext(path)[1].lower() in VIDEO_EXTS


# A real docutils node, not raw HTML, so the tag survives into the PDF.
def _track_tag(track: str) -> nodes.inline:
    slug = re.sub(r"[^a-z0-9]+", "-", track.lower()).strip("-")
    classes = ["showcase-track"]
    if slug in KNOWN_TRACKS:
        classes.append(f"showcase-track-{slug}")
    return nodes.inline("", track, classes=classes)


def _video_player(src: str, name: str) -> str:
    """The native player. Its own controls are kept rather than rebuilt from
    the audio chip: they carry fullscreen, playback rate, picture-in-picture
    and keyboard support that a hand-rolled transport would lose."""
    label = escape(name, quote=True)
    return (
        '<video class="showcase-video-el" controls preload="metadata" playsinline '
        f'src="{escape(src, quote=True)}" aria-label="Demo video: {label}">'
        "Your browser cannot play this video. Use the download button to save it."
        "</video>"
    )


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
