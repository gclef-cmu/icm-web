"""Render manim scenes into the book as chrome-less looping video.

This backs the ``{animation}`` directive: an animation cell defines a manim
``Scene`` and ends with ``anim.show(SceneCls)``. In a notebook that renders
headless and returns autoplaying, looping ``<video>`` elements with the mp4
inlined — no player controls, no JavaScript. The book itself never renders:
``make split`` records each show() call via capture_shows(), renders once
through render_to_file() (tuned re-encode, much smaller than show()'s crf-23
inline payload), and commits the mp4s under content/.../anim/, so the built
page just references files.
"""

from __future__ import annotations

import base64
import contextlib
import io
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import av
from av.bitstream import BitStreamFilterContext
from IPython.display import HTML
from manim import DecimalNumber, MathTex, Scene, Tex, Text, tempconfig

# Book palette, re-exported: `from manim import *` rebinds RED/BLUE/GOLD/TEAL
# to manim's neon colors, so scenes use anim.RED etc.
from icm_widgets import BLUE, GOLD, IRON, RED, STEEL, TEAL  # noqa: F401

__all__ = [
    "show",
    "capture_shows",
    "render_to_file",
    "RED",
    "BLUE",
    "GOLD",
    "IRON",
    "TEAL",
    "STEEL",
    "INK",
    "INK_DARK",
]

INK = "#3B3B3B"  # house label/axis grey
INK_DARK = "#ECECEC"
_PAGE = "#FFFFFF"  # the theme's light page background
# Must match --pst-color-background in custom.css, and both must be a grey
# that survives the mp4's limited-range YUV round trip exactly (the theme's
# stock #121212 does not — it decodes one step darker and the clip shows as
# a darker rectangle on the page).
_PAGE_DARK = "#101010"

# Quality words mapped to manim's presets.
_QUALITIES = {
    "low": "low_quality",  # 480p15 — for iterating
    "medium": "medium_quality",  # 720p30 — the default
    "high": "high_quality",  # 1080p60 — heavy, needs a reason
}

# Only text-like classes get a themed default ink; geometry (Line, Dot, ...)
# takes explicit colors in scenes.
_THEMED = (Text, Tex, MathTex, DecimalNumber)

# Manim writes mp4s without color metadata, so browsers guess: Safari
# gamma-shifts every color (the background stops matching the page) and the
# others assume a bt709 matrix at 720p while the encoder used bt601 (house
# colors drift). Stamping sRGB transfer + the bt601 matrix actually used
# makes browsers decode clip colors like page colors. Metadata-only —
# pixels aren't re-encoded.
_SRGB_TAG = (
    "h264_metadata=colour_primaries=1:transfer_characteristics=13:"
    "matrix_coefficients=6:video_full_range_flag=0"
)


# Split-time recorder: while capture_shows() is active, show() appends its
# call here instead of rendering.
_capture: list[ShowCall] | None = None


@dataclass
class ShowCall:
    """One recorded show() call: everything render_to_file needs later."""

    scene_cls: type[Scene]
    theme: str
    quality: str
    loop: bool
    max_mb: float


@contextlib.contextmanager
def capture_shows():
    """Record show() calls instead of rendering them.

    The splitter execs a companion notebook under this to get the Scene
    classes and their show() kwargs without paying for a render; yields the
    list the calls land in.
    """
    global _capture
    if _capture is not None:
        raise RuntimeError("capture_shows() does not nest")
    _capture = []
    try:
        yield _capture
    finally:
        _capture = None


def _tag_srgb(movie: Path, *, faststart: bool = False) -> Path:
    """Remux ``movie`` with sRGB color metadata; returns the tagged file.

    ``faststart`` puts the moov atom first so committed clips start playing
    before the file finishes downloading.
    """
    tagged = movie.with_name(movie.stem + "-srgb.mp4")
    mux_opts = {"movflags": "+faststart"} if faststart else {}
    with av.open(str(movie)) as inp, av.open(str(tagged), "w", options=mux_opts) as outp:
        in_v = inp.streams.video[0]
        out_v = outp.add_stream_from_template(in_v)
        bsf = BitStreamFilterContext(_SRGB_TAG, in_v, out_v)
        for packet in inp.demux(in_v):
            if packet.dts is None:  # demuxer's end-of-stream flush
                continue
            for out in bsf.filter(packet) or []:
                out.stream = out_v
                outp.mux(out)
        for out in bsf.flush() or []:
            out.stream = out_v
            outp.mux(out)
    return tagged


def _apply_theme(dark: bool) -> None:
    ink = INK_DARK if dark else INK
    for cls in _THEMED:
        cls.set_default()  # clear any previous default first
        cls.set_default(color=ink)


def _reset_theme() -> None:
    for cls in _THEMED:
        cls.set_default()  # bare call restores the original


def _render_raw(scene_cls: type[Scene], dark: bool, quality: str, media: Path) -> Path:
    """One headless render of ``scene_cls`` into ``media``; returns the mp4."""
    # The caller shows no source (hidden cell or split log), so any render
    # chatter would be noise. Capture everything; replay only on failure.
    out, err = io.StringIO(), io.StringIO()
    try:
        with tempconfig(
            {
                "quality": quality,
                "media_dir": str(media),
                "background_color": _PAGE_DARK if dark else _PAGE,
                "progress_bar": "none",
                "verbosity": "WARNING",
                "disable_caching": True,  # the cache dies with the temp dir anyway
            }
        ):
            _apply_theme(dark)
            try:
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    scene = scene_cls()
                    scene.render()
            except BaseException:
                sys.stdout.write(out.getvalue())
                sys.stderr.write(err.getvalue())
                raise
            return Path(scene.renderer.file_writer.movie_file_path)
    finally:
        _reset_theme()


def _render(scene_cls: type[Scene], dark: bool, quality: str) -> str:
    """One headless render of ``scene_cls`` -> base64 mp4."""
    media = Path(tempfile.mkdtemp(prefix="icm-anim-"))
    try:
        movie = _tag_srgb(_render_raw(scene_cls, dark, quality, media))
        return base64.b64encode(movie.read_bytes()).decode("ascii")
    finally:
        shutil.rmtree(media, ignore_errors=True)


def _reencode(movie: Path, *, crf: str, preset: str, tune: str | None = None) -> Path:
    """Transcode ``movie`` to a much smaller H.264; returns the new file.

    Decode and encode share the yuv420p pixel format, so the planes pass
    through untouched — no colorspace conversion, and the limited-range-safe
    _PAGE_DARK background survives exactly.
    """
    small = movie.with_name(movie.stem + "-small.mp4")
    with av.open(str(movie)) as inp, av.open(str(small), "w") as outp:
        in_v = inp.streams.video[0]
        out_v = outp.add_stream("libx264", rate=in_v.average_rate)
        out_v.width = in_v.codec_context.width
        out_v.height = in_v.codec_context.height
        out_v.pix_fmt = "yuv420p"
        options = {"crf": crf, "preset": preset}
        if tune:
            options["tune"] = tune
        out_v.options = options
        frames_written = 0
        for frame in inp.decode(in_v):
            # Re-time frames against the new stream and clear the decoded
            # I/P/B types so x264 decides keyframes itself.
            if out_v.codec_context.time_base is not None:
                frame.time_base = out_v.codec_context.time_base
            frame.pts = frames_written
            frames_written += 1
            frame.pict_type = 0
            for packet in out_v.encode(frame):
                outp.mux(packet)
        for packet in out_v.encode():
            outp.mux(packet)
    return small


def render_to_file(
    scene_cls: type[Scene],
    *,
    dark: bool,
    quality: str,
    dest: Path,
    crf: str = "28",
    preset: str = "veryslow",
    tune: str | None = None,
) -> int:
    """Render ``scene_cls`` and write a compressed, sRGB-tagged mp4 at ``dest``.

    The split-time path behind the {animation} directive: same render as
    show(), then a tuned re-encode instead of base64 inlining. Returns the
    byte size of the written file; writes via a sibling temp name so an
    interrupted run never leaves a truncated clip behind.
    """
    if quality not in _QUALITIES:
        raise ValueError(
            f"quality must be one of {sorted(_QUALITIES)} — got {quality!r}"
        )
    dest = Path(dest)
    media = Path(tempfile.mkdtemp(prefix="icm-anim-"))
    try:
        movie = _render_raw(scene_cls, dark, _QUALITIES[quality], media)
        tagged = _tag_srgb(
            _reencode(movie, crf=crf, preset=preset, tune=tune), faststart=True
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        shutil.copyfile(tagged, tmp)
        tmp.replace(dest)
        return dest.stat().st_size
    finally:
        shutil.rmtree(media, ignore_errors=True)


def show(
    scene_cls: type[Scene],
    *,
    theme: str = "auto",
    quality: str = "medium",
    loop: bool = True,
    max_mb: float = 8.0,
) -> HTML:
    """Render a manim Scene and return it as chrome-less looping video.

    Call as the last expression of the cell — the returned HTML is what
    myst-nb bakes into the page. The clip autoplays muted and loops like an
    embedded figure; there are no player controls.

    Parameters
    ----------
    scene_cls:
        The ``Scene`` subclass to render (the class itself, not an instance).
    theme:
        ``"auto"`` (the default) bakes a light and a dark render; the page
        shows the one matching the reader's light/dark toggle. ``"dark"``
        pins the 3Blue1Brown look in both modes; ``"light"`` pins the
        house-light render. Ink and background are reset after each render.
    quality:
        ``"low"`` (480p15) to iterate, ``"medium"`` (720p30, the default) to
        publish, ``"high"`` (1080p60) only with a reason.
    loop:
        Play forever. ``False`` plays once.
    max_mb:
        Weight budget for the clip (``theme="auto"`` counts both renders).
        In a notebook that's the inline base64 payload; at split time the
        splitter enforces it on the committed files instead. Exceeding it
        raises rather than quietly shipping a heavy page.
    """
    if not (isinstance(scene_cls, type) and issubclass(scene_cls, Scene)):
        raise TypeError("show() wants the Scene subclass itself, e.g. show(MyScene)")
    if quality not in _QUALITIES:
        raise ValueError(
            f"quality must be one of {sorted(_QUALITIES)} — got {quality!r}"
        )
    if theme not in ("auto", "light", "dark"):
        raise ValueError(f'theme must be "auto", "light" or "dark" — got {theme!r}')

    if _capture is not None:
        _capture.append(ShowCall(scene_cls, theme, quality, loop, max_mb))
        return HTML("")

    if os.environ.get("ICM_BOOK_BUILD"):
        raise RuntimeError(
            "icm_anim.show() executed during a book build — animation cells "
            "are pre-rendered at split time now; re-run `make split` (or "
            "`make template-animation`) and commit the regenerated page plus "
            "its anim/ files."
        )

    # Fixed-look clips carry only the bare class, which the custom.css mode
    # rules never hide.
    if theme == "auto":
        variants = [("icm-anim icm-anim-light", False), ("icm-anim icm-anim-dark", True)]
    else:
        variants = [("icm-anim", theme == "dark")]

    loop_attr = " loop" if loop else ""
    videos: list[str] = []
    weights: list[float] = []
    for css, dark in variants:
        data = _render(scene_cls, dark, _QUALITIES[quality])
        weights.append(len(data) / 1e6)
        # Layout lives on .icm-anim in custom.css — an inline `display` here
        # would override the stylesheet's light/dark rules and show both
        # renders. Only max-width stays inline, for VS Code previews.
        videos.append(
            f'<video class="{css}" autoplay muted playsinline{loop_attr} '
            f'style="max-width:100%;" '
            f'src="data:video/mp4;base64,{data}"></video>'
        )

    weight = sum(weights)
    if weight > max_mb:
        split = (
            f" ({weights[0]:.2f} light + {weights[1]:.2f} dark)"
            if len(weights) == 2
            else ""
        )
        raise ValueError(
            f"{scene_cls.__name__} weighs {weight:.2f} MB as page payload{split} "
            f"(budget {max_mb:.2f} MB) — shorten the clip, calm the motion, "
            f"or check the quality flag"
        )

    return HTML("\n".join(videos))
