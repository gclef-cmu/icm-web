"""The ``{pyquist}`` role — link prose to the Pyquist API reference.

Authors write the same spelling students use in code:

    {pyquist}`Score`              -> pq.Score                     (top-level export)
    {pyquist}`Audio.segment`      -> pq.Audio.segment             (method of an export)
    {pyquist}`frequency_to_pitch` -> pq.helper.frequency_to_pitch (submodule symbol)
    {pyquist}`score.Score`        -> pq.score.Score               (explicit module)
    {pyquist}`audio`              -> pq.audio                     (a submodule)

Renders as inline code linked into the API pages; the displayed text is
always importable as written (bare submodule-only names get qualified). An
unresolved symbol warns at build time. If Pyquist can't be introspected the
role degrades to verbatim display plus a fuzzy link.
"""
from __future__ import annotations

import ast
import importlib
from functools import lru_cache
from pathlib import Path

from docutils import nodes
from sphinx import addnodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxRole

# Submodules documented under content/pyquist/api/; a name starting with one
# of these is treated as already qualified by the author.
_SUBMODULES = ("audio", "score", "device", "plot", "helper", "web")


@lru_cache(maxsize=1)
def _index() -> tuple[frozenset[str], dict[str, object]] | tuple[None, None]:
    """Return ``(top_level_exports, {submodule: module})`` for Pyquist, cached.

    Returns ``(None, None)`` if Pyquist cannot be imported, which makes the role
    fall back to verbatim display.
    """
    try:
        modules: dict[str, object] = {}
        for name in _SUBMODULES:
            try:
                modules[name] = importlib.import_module(f"pyquist.{name}")
            except Exception:
                pass  # an absent/optional submodule should not break the role
        if not modules:
            return None, None
        # Read __all__ from the real __init__.py on disk: at the book root the
        # pyquist/ checkout shadows the install as an empty namespace package.
        any_mod = next(iter(modules.values()))
        init = Path(any_mod.__file__).with_name("__init__.py")
        top: set[str] = set()
        for node in ast.walk(ast.parse(init.read_text())):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
            ):
                top = {
                    el.value
                    for el in node.value.elts
                    if isinstance(el, ast.Constant) and isinstance(el.value, str)
                }
        top.discard("__version__")
        return frozenset(top), modules
    except Exception:
        return None, None


def _defining_submodule(name: str, modules: dict[str, object]) -> str | None:
    """Module suffix that defines ``name`` (e.g. ``"helper"``), or None.

    Prefers the object's ``__module__`` so a symbol re-imported into another
    submodule is still attributed to where it is defined.
    """
    for short, mod in modules.items():
        obj = getattr(mod, name, None)
        if obj is None:
            continue
        defined_in = getattr(obj, "__module__", None)
        if isinstance(defined_in, str) and defined_in.startswith("pyquist."):
            return defined_in[len("pyquist.") :]
        return short
    return None


def _resolve(text: str) -> tuple[str, str, str, bool]:
    """Map a ``{pyquist}`` argument to ``(display, target, reftype, fuzzy)``.

    - display: inline-code text to show, e.g. ``pq.helper.frequency_to_pitch``
    - target:  py-domain xref target, e.g. ``pyquist.helper.frequency_to_pitch``
    - reftype: ``"mod"`` for a bare submodule, else ``"obj"``
    - fuzzy:   set ``node['refspecific']`` so the py-domain searches by suffix
               (used only when we could not resolve the module ourselves)
    """
    top, modules = _index()
    first = text.split(".", 1)[0]

    # 1) Author already qualified with a submodule: show/verify verbatim.
    if first in _SUBMODULES:
        reftype = "mod" if text == first else "obj"
        return f"pq.{text}", f"pyquist.{text}", reftype, False

    # Without introspection we cannot tell a top-level name from a submodule
    # symbol; show it verbatim and let the py-domain search by suffix.
    if top is None or modules is None:
        return f"pq.{text}", text, "obj", True

    # 2) Top-level export (pq.<name> is importable): show as the author typed it.
    if first in top:
        sub = _defining_submodule(first, modules)
        target = f"pyquist.{sub}.{text}" if sub else f"pyquist.{text}"
        return f"pq.{text}", target, "obj", sub is None

    # 3) Bare symbol that lives only in a submodule: qualify it (pq.helper.…).
    sub = _defining_submodule(first, modules)
    if sub:
        return f"pq.{sub}.{text}", f"pyquist.{sub}.{text}", "obj", False

    # 4) Unknown: best-effort fuzzy link; refwarn flags it at build time.
    return f"pq.{text}", text, "obj", True


class PyquistRole(SphinxRole):
    """``{pyquist}`symbol``` — inline-code cross-reference into the Pyquist API."""

    def run(self):
        text = self.text.strip()
        display, target, reftype, fuzzy = _resolve(text)
        inner = nodes.literal(self.rawtext, display, classes=["pyquist-ref"])
        refnode = addnodes.pending_xref(
            self.rawtext,
            inner,
            refdomain="py",
            reftype=reftype,
            reftarget=target,
            refexplicit=True,
            refwarn=True,
        )
        if fuzzy:
            refnode["refspecific"] = True
        self.set_source_info(refnode)
        return [refnode], []


def setup(app: Sphinx) -> dict:
    app.add_role("pyquist", PyquistRole())
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
