"""Custom inline primitives: ``{vocab}``, ``{unit}``, ``:{color}[…]``,
and ``{icon-ai}``/``{icon-noai}``.

``{vocab}`term``` italicizes a term and links it to its glossary entry.

``{unit}`num``` / ``{unit}`num,denom``` typesets a unit or a unit fraction
(comma or slash both separate). It is not a docutils role — it expands to raw
LaTeX as a ``source-read`` substitution, because MyST never processes roles
inside ``$…$``/``$$…$$`` math. Wrap it in ``$…$`` inline or drop it into a
math block; fenced code blocks are skipped so examples render literally.

``{icon-ai}`` / ``{icon-noai}`` drop in the AI-policy badges: "AI" ringed
in green, and "AI" ringed in red with a slash through it. Both are written
bare (no backticks), and both are sized in ``em`` — an icon in a ``#``
heading comes out heading-sized, one in a paragraph text-sized. The bare
form is a ``source-read`` substitution onto the matching role, which also
takes an accessible label: ``{icon-noai}`no AI on the exam```.

``:{blue}[text]`` / ``:{blue}[text](url)`` colors inline text or a whole
link; ``:{blue-highlight}[text]`` renders it as a highlighter chip on the
matching tint instead. Also a ``source-read`` substitution, not a role —
roles cannot nest the bold and links this needs. It expands to the MyST
``attrs_inline`` form (``[text]{.c-blue}`` / ``[text]{.c-blue-highlight}``,
classes in ``_static/custom.css``), so that form works too. Fenced code
blocks and inline code spans are left alone.
"""
from __future__ import annotations

import json
import re
from html import escape

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxRole


class VocabRole(SphinxRole):
    """``{vocab}`term``` — an italic link to the term's glossary entry.

    An unknown term warns at build time, keeping glossary and prose in sync.
    """

    def run(self):
        term = self.text.strip()
        inner = nodes.emphasis(self.rawtext, term, classes=["vocab"])
        refnode = addnodes.pending_xref(
            self.rawtext,
            inner,
            refdomain="std",
            reftype="term",
            reftarget=term,
            refexplicit=False,
            refwarn=True,
        )
        self.set_source_info(refnode)
        return [refnode], []


class IconRole(SphinxRole):
    """``{icon-ai}`` / ``{icon-noai}`` — the inline AI-policy badges.

    Emits the SVG inline (rather than an ``<img>``) so the glyph inherits the
    surrounding text color rules and needs no asset path, and sizes itself in
    ``em`` from ``.icm-icon`` in custom.css. Role content, when given,
    replaces the default screen-reader label. LaTeX has no SVG here, so the
    PDF gets a short bracketed word instead of a silently missing icon.
    """

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind

    def run(self):
        label = self.text.strip() or _ICON_LABELS[self.kind]
        return [
            nodes.raw("", _icon_svg(self.kind, label), format="html"),
            nodes.raw("", _ICON_LATEX[self.kind], format="latex"),
        ], []


# A bare ``{icon-ai}``. The lookahead, plus the ``at_end`` check in
# ``_expand_outside_code``, keep the authored role form ``{icon-ai}`label```
# out — that form is already what the expansion produces.
ICON_RE = re.compile(r"\{icon-(ai|noai)\}(?!`)")
_ICON_LABELS = {"ai": "AI allowed", "noai": "AI not allowed"}
_ICON_LATEX = {"ai": r"\textbf{[AI]}", "noai": r"\textbf{[no AI]}"}
# Match the body font's own fallbacks: the glyphs are lettering, not a logo.
_ICON_FONT = ("system-ui, -apple-system, 'Segoe UI', Roboto, "
              "'Helvetica Neue', Arial, sans-serif")
# Ring endpoints of a 45-degree slash across a circle of r=9.4 at (12, 12).
_SLASH = (
    '<line class="icm-icon-halo" x1="5.4" y1="5.4" x2="18.6" y2="18.6"'
    ' stroke-width="4.2" stroke-linecap="round"/>'
    '<line x1="5.4" y1="5.4" x2="18.6" y2="18.6" stroke="currentColor"'
    ' stroke-width="2" stroke-linecap="round"/>'
)


def _icon_svg(kind: str, label: str) -> str:
    """The badge as inline SVG: a ring around "AI", plus a slash for noai.

    ``dy`` centers the lettering instead of ``dominant-baseline``, which
    older WebKit ignores — a baseline-shifted "AI" would sit low in the ring.
    """
    return (
        f'<svg class="icm-icon icm-icon-{kind}" viewBox="0 0 24 24" role="img"'
        f' aria-label="{escape(label, quote=True)}" focusable="false">'
        '<circle cx="12" cy="12" r="9.4" fill="none" stroke="currentColor"'
        ' stroke-width="2"/>'
        '<text x="12" y="12" dy="0.36em" text-anchor="middle" fill="currentColor"'
        f' font-family="{_ICON_FONT}" font-size="11" font-weight="700">AI</text>'
        f'{_SLASH if kind == "noai" else ""}'
        "</svg>"
    )


# ``{unit}`…``` with an argument; a bare ``{unit}`` mention (as in docs about
# the feature) is left untouched.
UNIT_RE = re.compile(r"\{unit\}`([^`]+)`")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")

# ``:{color}[text]`` plus an optional ``(url)`` right after the bracket;
# a ``-highlight`` suffix picks the chip class instead of the text color.
COLOR_RE = re.compile(
    r":\{((?:blue|green|orange|pink|gray)(?:-highlight)?)\}\[([^\[\]]*)\](\([^()]*\))?")
CODE_RE = re.compile(r"`+[^`]*`+")


def _unit_latex(arg: str) -> str:
    """Render a ``{unit}`` argument as raw LaTeX (no surrounding math mode)."""
    parts = [p.strip() for p in re.split(r"[,/]", arg)]
    if len(parts) >= 2 and parts[1]:
        return r"\frac{\text{%s}}{\text{%s}}" % (parts[0], parts[1])
    return r"\text{%s}" % parts[0]


def _expand_outside_code(text: str) -> str:
    """Expand ``:{color}[…]`` and the bare ``{icon-*}``, skipping inline code.

    Inline code is skipped so a line documenting the syntax (``` `{icon-ai}` ```)
    still shows it literally.
    """
    def icon(m: re.Match, at_end: bool) -> str:
        # A trailing ``{icon-*}`` is the head of an authored role, whose label
        # is the code span that follows; only the bare form expands, and it
        # expands to that same role form carrying the default label.
        if at_end:
            return m.group(0)
        return "{icon-%s}`%s`" % (m.group(1), _ICON_LABELS[m.group(1)])

    def sub(segment: str, before_code: bool = False) -> str:
        segment = COLOR_RE.sub(
            lambda m: "[%s]%s{.c-%s}" % (m.group(2), m.group(3) or "", m.group(1)),
            segment)
        return ICON_RE.sub(
            lambda m: icon(m, before_code and m.end() == len(segment)), segment)

    out: list[str] = []
    pos = 0
    for m in CODE_RE.finditer(text):
        out.append(sub(text[pos:m.start()], before_code=True))
        out.append(m.group(0))
        pos = m.end()
    out.append(sub(text[pos:]))
    return "".join(out)


def _expand_text(text: str) -> str:
    """Expand ``{unit}``, ``:{color}[…]`` and ``{icon-*}``, outside code fences."""
    out: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        if fence is None:
            fm = FENCE_RE.match(line)
            if fm:
                fence = fm.group(1)
                out.append(line)
                continue
            out.append(
                _expand_outside_code(
                    UNIT_RE.sub(lambda m: _unit_latex(m.group(1)), line)))
        else:
            out.append(line)
            stripped = line.strip()
            if stripped and set(stripped) == {fence[0]} and len(stripped) >= len(fence):
                fence = None
    return "".join(out)


def substitute_inline(app: Sphinx, docname: str, source: list[str]) -> None:
    """``source-read`` handler: expand ``{unit}``, ``:{color}[…]``, ``{icon-*}``.

    Markdown pages are rewritten directly. Notebooks arrive as raw .ipynb
    JSON that myst-nb decodes again after us — splicing LaTeX into the JSON
    text would let that second decode mangle the backslashes (``\\frac`` →
    form-feed + ``rac``). So decode, expand each Markdown cell, re-encode,
    and let ``json.dumps`` escape the LaTeX correctly.
    """
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


def setup(app: Sphinx) -> dict:
    app.add_role("vocab", VocabRole())
    app.add_role("icon-ai", IconRole("ai"))
    app.add_role("icon-noai", IconRole("noai"))
    app.connect("source-read", substitute_inline)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
