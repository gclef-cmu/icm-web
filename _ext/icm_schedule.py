"""The ``{schedule}`` directive — the course schedule from a line format.

Each non-blank body line is a week band (no ``|``) or a day row::

    :::{schedule}
    Week 2
    [blue] Mon Aug 31 | [Assignment 1: Hello Pyquist and Synthesis (due)](assignments/01.md)
    Tue Sep 01 | **02A** · Additive synthesis, wavetables, and basic waveforms | [Ch. 3](/book/ch03/index.md)
    :::

Day rows are ``[color] date | topic [| readings]``; topic and readings are
ordinary Markdown — write Markdown links for linked deadlines and chapter
readings. The color tags the row's category — the row gets a tinted
background (``sched-table`` rules in custom.css) and everything but gray is
bolded. ``%`` lines are comments.

The directive expands to the ``{list-table}`` the page used to hand-write
(class ``sched-table``, attrs_inline color classes) and nested-parses it, so
the rendered result is unchanged — only the authoring is different. Each
band also emits a hidden ``sched-anchor`` section so the weeks show up in
the right-hand "On this page" menu; ``_static/page-toc.js`` moves the
anchors onto the band rows at load.
"""
from __future__ import annotations

import re

from docutils import nodes
from docutils.parsers.rst import Directive
from docutils.statemachine import StringList
from sphinx.application import Sphinx

_COLORS = "blue|green|orange|pink|gray"
_TAG_RE = re.compile(r"^\[(%s)\]\s+(.*)$" % _COLORS)
# A topic that is one wrapping Markdown link, e.g. "[Assignment 1 (due)](01.md)".
_LINK_RE = re.compile(r"^\[(?P<text>.+)\]\((?P<href>\S+)\)$")


class ScheduleDirective(Directive):
    """``:::{schedule}`` — expands the line format into the schedule table."""

    has_content = True

    def run(self):
        rows = [("Date", "Topic / Deadline", "Reading")]
        bands = []
        for raw in self.content:
            line = raw.strip()
            if not line or line.startswith("%"):
                continue
            if "|" not in line:
                rows.append(("**%s**" % line, "", ""))
                bands.append(line)
                continue

            segs = [s.strip() for s in line.split("|")]
            color = None
            date = segs[0]
            tag = _TAG_RE.match(date)
            if tag:
                color, date = tag.group(1), tag.group(2).strip()
            topic = segs[1] if len(segs) > 1 else ""
            reading = segs[2] if len(segs) > 2 else ""

            if color:
                link = _LINK_RE.match(topic)
                text, href = (link.group("text"), link.group("href")) if link else (topic, None)
                bold = "**%s**" if color != "gray" else "%s"
                date = "[%s]{.c-%s}" % (bold % date, color)
                topic = ("[%s](%s){.c-%s}" % (bold % text, href, color) if href
                         else "[%s]{.c-%s}" % (bold % text, color))
            rows.append((date, topic, reading))

        text = [":::{list-table}", ":header-rows: 1", ":class: sched-table", ""]
        for row in rows:
            marker = "* -"
            for cell in row:
                text.append("%s %s" % (marker, cell) if cell else marker)
                marker = "  -"
        text.append(":::")

        container = nodes.container()
        self.state.nested_parse(StringList(text), self.content_offset, container)

        anchors = []
        for label in bands:
            section = nodes.section(ids=[nodes.make_id(label)], classes=["sched-anchor"])
            section += nodes.title(text=label)
            anchors.append(section)
        return list(container.children) + anchors


def setup(app: Sphinx) -> dict:
    app.add_directive("schedule", ScheduleDirective)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
