"""Group the glossary into A–Z sections and link each term to its first use.

Post-processes Sphinx's flat ``{glossary}`` definition list at
``doctree-resolved``: entries are grouped under per-letter headings and an
A–Z jump bar is prepended (empty letters greyed out). Term ids are left
alone, so ``{vocab}`` references still resolve.

Each headword also becomes a link (HTML only) to the first ``{vocab}`` use
of the term in reading order, landing on the word itself. The uses and their
anchors are recorded by the ``{vocab}`` role (_ext/icm_roles.py),
and the order is the toctree's, walked depth-first from the root page.

``{vocab}`` targets are matched loosely: case, hyphens vs spaces, and a
trailing plural "s"/"es" are ignored, so ``{vocab}`Envelopes``` and
``{vocab}`signal flow diagrams``` find the ``envelope`` and
``signal-flow diagram`` entries.
"""
from __future__ import annotations

import re
import string

from docutils import nodes
from sphinx import addnodes
from sphinx.addnodes import pending_xref
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.util.nodes import make_refnode

ALPHABET = string.ascii_uppercase
_SYMBOL = "#"  # bucket for terms that don't start with a Latin letter
_MIXED_CASE = re.compile(r"[a-z][A-Z]")


def _norm(term: str) -> str:
    """Case-, hyphen- and quote-insensitive form of a term (smartquotes may
    curl the apostrophe in "Euler's formula" on one side only)."""
    term = term.lower().replace("-", " ").replace("’", "'")
    return " ".join(term.split())


def _candidates(term: str) -> list[str]:
    """Normalized spellings a ``{vocab}`` term may match, most exact first."""
    t = _norm(term)
    out = [t]
    if t.endswith("es"):
        out += [t[:-1], t[:-2]]
    elif t.endswith("s"):
        out.append(t[:-1])
    return out


def _glossary_terms(env: BuildEnvironment) -> dict[str, tuple[str, str]]:
    """Normalized glossary term -> (docname, term id), from the std domain."""
    std = env.get_domain("std")
    return {_norm(term): loc for term, loc in std._terms.items()}


def _lookup(terms: dict[str, tuple[str, str]], term: str) -> tuple[str, str] | None:
    for cand in _candidates(term):
        if cand in terms:
            return terms[cand]
    return None


def resolve_vocab_variant(app: Sphinx, env: BuildEnvironment,
                          node: pending_xref, contnode: nodes.Element):
    """``missing-reference``: retry an unresolved term ref with loose matching."""
    if node.get("refdomain") != "std" or node.get("reftype") != "term":
        return None
    hit = _lookup(_glossary_terms(env), node["reftarget"])
    if hit is None:
        return None
    docname, labelid = hit
    return make_refnode(app.builder, node["refdoc"], docname, labelid, contnode)


def _reading_order(env: BuildEnvironment) -> list[str]:
    """Every document in toctree order, depth-first from the root page."""
    order: list[str] = []
    seen: set[str] = set()

    def visit(doc: str) -> None:
        if doc in seen:
            return
        seen.add(doc)
        order.append(doc)
        for child in env.toctree_includes.get(doc, []):
            visit(child)

    visit(env.config.root_doc)
    return order


def _first_uses(env: BuildEnvironment) -> dict[tuple[str, str], tuple[str, str]]:
    """(glossary docname, term id) -> (docname, anchor) of the term's first use."""
    terms = _glossary_terms(env)
    uses = getattr(env, "icm_vocab_uses", {})
    first: dict[tuple[str, str], tuple[str, str]] = {}
    for doc in _reading_order(env):
        for term, anchor in uses.get(doc, []):
            hit = _lookup(terms, term)
            if hit is not None and hit not in first:
                first[hit] = (doc, anchor)
    return first


def _add_first_uses(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    """Turn each glossary headword into a link to the term's first use."""
    first = _first_uses(app.env)
    for dl in doctree.findall(nodes.definition_list):
        if "glossary" not in dl.get("classes", []):
            continue
        for item in dl.children:
            if not isinstance(item, nodes.definition_list_item):
                continue
            for term in item.findall(nodes.term):
                use = next((first[(docname, i)] for i in term["ids"]
                            if (docname, i) in first), None)
                if use is None:
                    continue
                doc, anchor = use
                uri = app.builder.get_relative_uri(docname, doc) + "#" + anchor
                link = nodes.reference("", "", refuri=uri, internal=True,
                                       classes=["glossary-first-use"])
                # Move the headword text into the link; index nodes stay put.
                for child in list(term.children):
                    if not isinstance(child, addnodes.index):
                        term.remove(child)
                        link += child
                term.insert(0, link)


def _anchor(letter: str) -> str:
    """Stable HTML id for a letter group ('A' -> 'glossary-letter-a')."""
    return "glossary-letter-" + ("symbol" if letter == _SYMBOL else letter.lower())


def _initial(item: nodes.definition_list_item) -> str:
    """Uppercase first letter of an entry's term, or '#' if non-alphabetic."""
    term = item.next_node(nodes.term)
    text = term.astext().strip() if term is not None else ""
    ch = text[0].upper() if text else _SYMBOL
    return ch if ch in ALPHABET else _SYMBOL


def _group_one(dl: nodes.definition_list) -> None:
    """Replace one flat glossary ``<dl>`` with letter-grouped sections + nav."""
    items = [c for c in dl.children if isinstance(c, nodes.definition_list_item)]
    if not items:
        return

    # Bucket items by initial letter, preserving the (already sorted) order.
    groups: dict[str, list[nodes.definition_list_item]] = {}
    for item in items:
        groups.setdefault(_initial(item), []).append(item)
        # CSS capitalizes each headword's first letter; mixed-case terms
        # like "dBFS" opt out so they don't render as "DBFS".
        term = item.next_node(nodes.term)
        if term is not None and _MIXED_CASE.match(term.astext()):
            term["classes"].append("glossary-keep-case")

    # Alphabetical letters first, the '#' (symbol) bucket last if present.
    present = [c for c in ALPHABET if c in groups]
    if _SYMBOL in groups:
        present.append(_SYMBOL)
    present_set = set(present)

    new_nodes: list[nodes.Node] = []

    # A–Z jump bar. Must be a paragraph: the HTML writer asserts that a
    # reference in a block parent wraps a single image.
    nav = nodes.paragraph(classes=["glossary-nav"])
    for letter in list(ALPHABET) + ([_SYMBOL] if _SYMBOL in groups else []):
        if letter in present_set:
            nav += nodes.reference(
                "", letter, refid=_anchor(letter),
                classes=["glossary-nav-letter"],
            )
        else:
            nav += nodes.inline(
                "", letter, classes=["glossary-nav-letter", "is-empty"],
            )
    new_nodes.append(nav)

    # One heading + sub-list per present letter.
    for letter in present:
        heading = nodes.rubric(
            "", letter, ids=[_anchor(letter)],
            classes=["glossary-letter-heading"],
        )
        new_nodes.append(heading)

        sub = nodes.definition_list(
            classes=["simple", "glossary", "glossary-letter-group"]
        )
        for item in groups[letter]:
            sub += item  # reparents; the old dl is discarded below
        new_nodes.append(sub)

    dl.replace_self(new_nodes)


def group_glossary(app: Sphinx, doctree: nodes.document, docname: str) -> None:
    if app.builder.format == "html":
        _add_first_uses(app, doctree, docname)
    for dl in list(doctree.findall(nodes.definition_list)):
        if "glossary" in dl.get("classes", []):
            _group_one(dl)


def refresh_glossary(app: Sphinx, env: BuildEnvironment, added: set[str],
                     changed: set[str], removed: set[str]) -> list[str]:
    """``env-get-outdated``: any page edit may move a term's first use."""
    if not (added or changed or removed):
        return []
    return sorted({doc for doc, _ in env.get_domain("std")._terms.values()})


def setup(app: Sphinx) -> dict:
    app.connect("doctree-resolved", group_glossary)
    app.connect("missing-reference", resolve_vocab_variant)
    app.connect("env-get-outdated", refresh_glossary)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
