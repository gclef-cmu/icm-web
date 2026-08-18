"""Tag bare-URL links so CSS can style them apart from prose links.

Justified lines need long bare URLs (auto-linkified or written verbatim) to
break anywhere, but the same rule on a prose-text link breaks its words
mid-word. CSS cannot compare a link's text to its target, so mark the bare
ones here: a reference whose visible text is its own URI gets the class
``bare-url``, and custom.css scopes ``word-break: break-all`` to that.
"""
from __future__ import annotations

from docutils import nodes
from sphinx.application import Sphinx


def tag_bare_links(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    for ref in doctree.findall(nodes.reference):
        uri = ref.get("refuri")
        if not uri:
            continue
        text = ref.astext().strip()
        if uri in (text, f"{text}/", f"mailto:{text}"):
            ref["classes"].append("bare-url")


def setup(app: Sphinx) -> dict:
    app.connect("doctree-resolved", tag_bare_links)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
