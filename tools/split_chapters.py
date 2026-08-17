#!/usr/bin/env python3
"""Split each icm-text/{n}-{slug}/index.md into per-section files under content/ch{nn}/.

icm-text/ (a pinned submodule) is the ground truth. For each chapter this
strips the frontmatter, splits the body on `## ` headings (ignoring fenced
code blocks), demotes headings one level, copies assets/code/figures across,
and regenerates the chapter part of _toc.yml. A section that embeds a
companion notebook via `{interactive}`/`{animation}` is emitted as a .ipynb
instead of .md; `{animation}` companions are additionally rendered — here,
not at book build time — into committed clips under content/chNN/anim/
(unchanged clips are reused byte-for-byte, so only new or edited scenes
cost a manim render). It also mirrors the icm-f26/ course-website submodule
into content/course/, copies book front matter (about.md, errata.md) from
icm-text/ to content/, and copies icm-text/refs.bib to content/references.bib.

Everything is authored in MyST already, so nothing is translated — only
restructured. Run via `make split` (or `--page` for a standalone template
folder). WARNING: wipes content/ch*/ and content/course/, dropping any local
overrides; review `git diff content/` afterward.
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import NamedTuple

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "icm-text"  # ground-truth prose submodule
CONTENT = REPO / "content"
TOC = REPO / "_toc.yml"
REFS_SRC = SOURCE / "refs.bib"
REFS_DEST = CONTENT / "references.bib"  # what _config.yml's bibtex_bibfiles points at
FRONT_MATTER_FILES = ("about.md", "errata.md")  # authored upstream, copied verbatim

COURSE_SOURCE = REPO / "icm-f26"  # course-website submodule
COURSE_DEST = CONTENT / "course"
COURSE_SKIP_FILES = {"README.md"}  # contributor placeholder, not a course page
COURSE_CAPTION = "- caption: Course Information"
# Sidebar order for course pages/sections; anything not listed sorts after.
COURSE_ORDER = ("home", "about", "schedule", "assignments", "resources", "showcase")

CHAPTER_FOLDER_RE = re.compile(r"^(\d+)-(.+)$")
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")

# `:::{interactive}[notebooks/foo.ipynb]` / `:::{animation}[...]` — opening
# fence is 3+ colons, path in [brackets] or bare. A section containing either
# is emitted as a notebook (see build_section_notebook).
DIRECTIVE_OPEN_RE = re.compile(r"^(:{3,})\{(interactive|animation)\}[ \t]*(.*?)[ \t]*$")


def parse_directive_arg(arg: str) -> str:
    """Notebook path from a directive argument: `[path]` or a bare path.

    Kept in lockstep with _ext/icm_interactive.py and _ext/icm_animation.py.
    """
    arg = arg.strip()
    if arg.startswith("[") and arg.endswith("]"):
        arg = arg[1:-1].strip()
    return arg


# Companion notebooks reference chapter data as ../assets/ etc., correct
# from their notebooks/ dir; flattening hoists their cells one level up,
# so those prefixes become chapter-root ./assets/ etc. Kept in lockstep
# with _ext/icm_interactive.py.
FLATTEN_PATH_REWRITES = (
    ("../assets/", "./assets/"),
    ("../code/", "./code/"),
    ("../figures/", "./figures/"),
)


def rewrite_flattened_paths(source: str) -> str:
    for old, new in FLATTEN_PATH_REWRITES:
        source = source.replace(old, new)
    return source


# ---- {animation} pre-rendering ---------------------------------------------
# Animation clips are rendered here, at split time, and committed as small
# mp4 files under content/.../anim/ — the book build (and CI) never runs
# manim. Each filename carries a content hash, so an unchanged companion
# reuses its stashed file byte-for-byte and only new hashes render.
ANIM_DIR = "anim"

# Bumping this re-renders every clip (the hash can't see icm_anim internals
# or palette changes). Escape hatch: rm -rf content/*/anim && make split.
ANIM_SCHEME = "1"

# Hashed into every filename AND passed to icm_anim.render_to_file, so an
# encode-settings change re-renders everything by itself.
ANIM_ENCODE = {"crf": "28", "preset": "veryslow", "tune": "animation"}

# merge_chapters' round-trip re-split flips this off: filenames are a pure
# function of the sources, so verifying bytes needs no manim.
RENDER_ANIMATIONS = True

# Mirrors icm_anim.show()'s keyword defaults.
ANIM_SHOW_DEFAULTS = {"theme": "auto", "quality": "medium", "loop": True, "max_mb": 8.0}


class AnimShow(NamedTuple):
    """One show() call in a companion notebook, read statically."""

    scene: str  # the Scene class name
    theme: str
    quality: str
    loop: bool
    max_mb: float
    cell_index: int  # which companion code cell it sits in
    ordinal: int  # 0-based across the companion


class AnimRequest(NamedTuple):
    """One mp4 a generated page references and materialize must provide."""

    companion: Path  # absolute path to the companion notebook
    filename: str  # hash-stamped name under anim/
    show: AnimShow
    dark: bool


def parse_anim_shows(code_cells: list[str], src: Path) -> list[AnimShow]:
    """Every show() call in a companion's code cells, without running manim.

    Clip filenames must be computable statically (the merge round-trip
    re-splits without rendering), so show() calls have a contract: top-level
    statements of the form ``anim.show(SceneCls, theme=..., ...)`` — the
    Scene class as a bare name, kwargs as literals.
    """
    shows: list[AnimShow] = []
    for idx, source in enumerate(code_cells):
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            sys.exit(f"{src}: code cell {idx} does not parse: {e}")
        for node in tree.body:
            if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)):
                continue
            call = node.value
            func = call.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else func.id if isinstance(func, ast.Name) else None
            )
            if name != "show":
                continue
            if len(call.args) != 1 or not isinstance(call.args[0], ast.Name):
                sys.exit(
                    f"{src}: show() needs the Scene class as its only "
                    "positional argument, as a bare name"
                )
            kwargs = dict(ANIM_SHOW_DEFAULTS)
            for kw in call.keywords:
                if kw.arg not in ANIM_SHOW_DEFAULTS:
                    sys.exit(f"{src}: show() got unsupported keyword {kw.arg!r}")
                try:
                    kwargs[kw.arg] = ast.literal_eval(kw.value)
                except ValueError:
                    sys.exit(
                        f"{src}: show() keyword {kw.arg} must be a literal "
                        "(the splitter reads it without running the cell)"
                    )
            if kwargs["theme"] not in ("auto", "light", "dark"):
                sys.exit(f"{src}: show() theme must be auto/light/dark")
            if kwargs["quality"] not in ("low", "medium", "high"):
                sys.exit(f"{src}: show() quality must be low/medium/high")
            shows.append(
                AnimShow(
                    scene=call.args[0].id,
                    cell_index=idx,
                    ordinal=len(shows),
                    **kwargs,
                )
            )
    if not shows:
        sys.exit(f"{src}: no show() call found in animation companion")
    return shows


def anim_variants(theme: str) -> list[tuple[str, str, bool]]:
    """(css_class, variant_name, dark) per rendered file.

    Mirrors icm_anim.show(): auto bakes light+dark siblings the custom.css
    mode rules switch between; a pinned theme gets one bare-class clip.
    """
    if theme == "auto":
        return [
            ("icm-anim icm-anim-light", "light", False),
            ("icm-anim icm-anim-dark", "dark", True),
        ]
    return [("icm-anim", theme, theme == "dark")]


def anim_clip_name(code_cells: list[str], show: AnimShow, variant: str, stem: str) -> str:
    """Deterministic mp4 name: any input that changes the pixels changes it.

    Hashes the raw companion code (kwarg edits re-render), the scene
    identity, and the encode settings. Light/dark variants of one show
    share the hash — the variant lives in the name.
    """
    key = "\x00".join(
        [
            ANIM_SCHEME,
            json.dumps(ANIM_ENCODE, sort_keys=True),
            show.scene,
            str(show.ordinal),
            *code_cells,
        ]
    )
    digest = hashlib.sha256(key.encode()).hexdigest()[:12]
    return f"{stem}-{show.scene}-{variant}-{digest}.mp4"


# Cross-chapter links are authored against the icm-text layout, where
# chapters are sibling {n}-{slug}/ folders. Flattening renames those to
# content/ch{nn}/, so link targets are rewritten to the chapter's index
# page, which Sphinx can resolve. tools/merge_chapters.py applies the
# exact inverse when reconstructing chapters for upstream PRs.
CHAPTER_LINK_RE = re.compile(r"\]\(\.\./(\d+)-[\w-]+(#[^)]*)?\)")


def rewrite_chapter_links(text: str) -> str:
    def repl(m):
        return f"](../ch{int(m.group(1)):02d}/index.md{m.group(2) or ''})"

    return CHAPTER_LINK_RE.sub(repl, text)


def section_directives(text: str):
    """All directives in section text, as (open_idx, close_idx, kind, path).

    Indexes into ``text.splitlines(keepends=True)``. A directive has no body,
    so its closing fence is the next line equal to the opening colon run.
    Directive lines inside fenced code blocks are ignored — those are
    documentation examples, not real embeds.
    """
    lines = text.splitlines(keepends=True)
    out: list[tuple[int, int, str, str]] = []
    fence: str | None = None
    i, n = 0, len(lines)
    while i < n:
        if fence is not None:
            stripped = lines[i].strip()
            if (
                stripped
                and set(stripped) == {fence[0]}
                and len(stripped) >= len(fence)
            ):
                fence = None
            i += 1
            continue
        fm = FENCE_RE.match(lines[i])
        if fm:
            fence = fm.group(1)
            i += 1
            continue
        m = DIRECTIVE_OPEN_RE.match(lines[i])
        if not m:
            i += 1
            continue
        colons = m.group(1)
        kind = m.group(2)
        path = parse_directive_arg(m.group(3))
        close = i
        for j in range(i + 1, n):
            if lines[j].strip() == colons:
                close = j
                break
        out.append((i, close, kind, path))
        i = close + 1
    return out


# Visibility marker in an interactive notebook's code cell: a whole line
# `# hide` (source removed from view), `# collapse` ("Show setup" bar) or
# `# show`. Case-insensitive, first one wins, and the marker stays in the
# emitted source — it's an ordinary comment.
VISIBILITY_MARKER_RE = re.compile(r"^#\s*(hide|collapse|show)\s*$", re.IGNORECASE)

# `# no-output` drops the cell's baked output from the page (myst-nb's
# `remove-output` tag); the cell still executes at build and in the browser.
NO_OUTPUT_MARKER_RE = re.compile(r"^#\s*no-output\s*$", re.IGNORECASE)

# `# autorun` makes the live layer run the cell (and its setup chain) on
# page load instead of waiting for the reader's first Run — for widget
# cells whose output must be interactive without a button press.
AUTORUN_MARKER_RE = re.compile(r"^#\s*autorun\s*$", re.IGNORECASE)


def cell_visibility(source: str) -> str:
    """Return "hide", "collapse" or "show" for a notebook code cell."""
    for line in source.splitlines():
        m = VISIBILITY_MARKER_RE.match(line.strip())
        if m:
            return m.group(1).lower()
    return "show"


def cell_no_output(source: str) -> bool:
    """True if the cell carries a whole-line ``# no-output`` marker."""
    return any(
        NO_OUTPUT_MARKER_RE.match(line.strip()) for line in source.splitlines()
    )


def cell_autorun(source: str) -> bool:
    """True if the cell carries a whole-line ``# autorun`` marker."""
    return any(
        AUTORUN_MARKER_RE.match(line.strip()) for line in source.splitlines()
    )


def build_section_notebook(
    section_md: str,
    chapter_folder: Path,
    chapter_num: int,
    sec_index: int,
    anim_requests: list[AnimRequest] | None = None,
):
    """Turn a section that embeds companion notebooks into a notebook.

    The section text is segmented at each directive: the prose around them
    becomes Markdown cells, and each directive expands via add_notebook —
    ``{interactive}`` to the companion's cells (not ``skip-execution``, so
    the build bakes their output into the page), ``{animation}`` to a
    Markdown cell of ``<video>`` tags referencing pre-rendered clips in
    ./anim/. The mp4s each video cell needs are appended to
    ``anim_requests`` for the caller to materialize. The notebook is stamped
    to execute with its own directory as CWD (not the global run_in_temp
    temp dir) so rewritten ./assets/ paths resolve at build time.

    Cell ids derive from chapter/section/ordinal, keeping the output
    byte-for-byte deterministic — tools/merge_chapters.py relies on that for
    its round-trip check. Each expanded cell stashes the directive's kind and
    path in its metadata so merge can collapse the run back into one
    directive line.
    """
    if anim_requests is None:
        anim_requests = []
    lines = section_md.splitlines(keepends=True)
    base = f"ch{chapter_num:02d}s{sec_index:02d}"
    cells: list = []
    k = 0  # running cell ordinal, for deterministic ids

    def add_markdown(seg_lines: list[str]) -> None:
        nonlocal k
        text = "".join(seg_lines).strip("\n")
        if not text:
            return
        cell = new_markdown_cell(text)
        cell["id"] = f"{base}m{k}"
        cell["metadata"] = {}
        cells.append(cell)
        k += 1

    def add_animation(src: Path, rel: str) -> None:
        """Expand an ``{animation}`` directive to pre-rendered video cells.

        The companion's code never reaches the page — it runs only at render
        time (see materialize_animations). Each code cell with a show() call
        becomes one Markdown cell of ``<video>`` tags pointing at the
        hash-named clips in ./anim/; code cells without one are dropped, and
        Markdown cells pass through. Every referenced clip is appended to
        ``anim_requests``.
        """
        nonlocal k
        nb_cells = nbformat.read(str(src), as_version=4).cells
        code_cells = [c.source for c in nb_cells if c.cell_type == "code"]
        shows_by_cell: dict[int, list[AnimShow]] = {}
        for s in parse_anim_shows(code_cells, src):
            shows_by_cell.setdefault(s.cell_index, []).append(s)
        code_idx = 0
        for c in nb_cells:
            meta = {"animation": {"path": rel}}
            if c.cell_type == "markdown":
                cell = new_markdown_cell(rewrite_flattened_paths(c.source))
                cell["id"] = f"{base}m{k}"
                cell["metadata"] = meta
                cells.append(cell)
                k += 1
                continue
            if c.cell_type != "code":
                continue
            cell_shows = shows_by_cell.get(code_idx, [])
            code_idx += 1
            if not cell_shows:
                continue
            videos: list[str] = []
            for s in cell_shows:
                for css, variant, dark in anim_variants(s.theme):
                    fname = anim_clip_name(code_cells, s, variant, src.stem)
                    loop_attr = " loop" if s.loop else ""
                    # Attribute-for-attribute what icm_anim.show() emits,
                    # with a file src instead of a data URI; layout lives on
                    # .icm-anim in custom.css.
                    videos.append(
                        f'<video class="{css}" autoplay muted playsinline'
                        f'{loop_attr} style="max-width:100%;" '
                        f'src="./{ANIM_DIR}/{fname}"></video>'
                    )
                    anim_requests.append(
                        AnimRequest(src.resolve(), fname, s, dark)
                    )
            cell = new_markdown_cell("\n".join(videos))
            cell["id"] = f"{base}m{k}"
            cell["metadata"] = meta
            cells.append(cell)
            k += 1

    def add_notebook(src: Path, rel: str, kind: str, group: int) -> None:
        """Expand a companion notebook in place as section cells.

        Cell sources are copied with ../assets|code|figures/ rewritten to
        ./… (rewrite_flattened_paths), since flattening hoists the cells
        out of notebooks/ into the chapter root.

        ``{interactive}`` code cells stay runnable. The `# hide` marker maps
        to our ``icm-hide-input`` tag (CSS-hidden but still in the DOM, so
        the live run chain can execute it — myst-nb's ``remove-input`` would
        strip it and break cells below); `# collapse` maps to ``hide-input``.
        Each also gets an ``icm-run-group-{group}`` tag, one group per
        directive, so a Run's setup chain covers only its own notebook.

        ``{animation}`` directives take the watch-only path instead: see
        add_animation.
        """
        nonlocal k
        if kind == "animation":
            add_animation(src, rel)
            return
        for c in nbformat.read(str(src), as_version=4).cells:
            source = rewrite_flattened_paths(c.source)
            meta = {kind: {"path": rel}}
            if c.cell_type == "markdown":
                cell = new_markdown_cell(source)
                cell["id"] = f"{base}m{k}"
                cell["metadata"] = meta
                cells.append(cell)
                k += 1
            elif c.cell_type == "code":
                cc = new_code_cell(source)
                cc["id"] = f"{base}c{k}"
                visibility = cell_visibility(source)
                tags = [f"icm-run-group-{group}"]
                if visibility == "hide":
                    tags.append("icm-hide-input")
                elif visibility == "collapse":
                    tags.append("hide-input")
                if cell_no_output(source):
                    tags.append("remove-output")
                if cell_autorun(source):
                    tags.append("icm-autorun")
                meta["tags"] = tags
                cc["metadata"] = meta
                cells.append(cc)
                k += 1

    cursor = 0
    for group, (open_idx, close_idx, kind, rel) in enumerate(
        section_directives(section_md)
    ):
        add_markdown(lines[cursor:open_idx])
        src = chapter_folder / rel
        if src.suffix != ".ipynb":
            sys.exit(f"{{{kind}}} expects a .ipynb notebook, got {rel!r}")
        add_notebook(src, rel, kind, group)
        cursor = close_idx + 1
    add_markdown(lines[cursor:])

    nb = new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {"name": "python"},
        # myst-nb file-level override: execute with CWD = the notebook's own
        # content/chNN/ dir so ./assets/ paths resolve; safe because chapter
        # dirs never contain a pyquist/ child (see run_in_temp in _config.yml).
        "mystnb": {"execution_in_temp": False},
    }
    nb["nbformat"] = 4
    nb["nbformat_minor"] = 5
    return nb


def split_body(body: str):
    """Split the body on `## ` headings outside fenced code blocks.

    Returns (intro_block_lines, [(section_title, section_content_lines), ...]).
    The intro block still contains the chapter `# ` heading.
    """
    lines = body.splitlines(keepends=True)
    intro_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    cur_title: str | None = None
    cur_lines: list[str] = []
    fence: str | None = None

    def flush():
        nonlocal cur_title, cur_lines
        if cur_title is None:
            intro_lines.extend(cur_lines)
        else:
            sections.append((cur_title, cur_lines))
        cur_title = None
        cur_lines = []

    for line in lines:
        if fence is None:
            fm = FENCE_RE.match(line)
            if fm:
                fence = fm.group(1)
                cur_lines.append(line)
                continue
            hm = HEADING_RE.match(line)
            if hm and len(hm.group(1)) == 2:
                flush()
                cur_title = hm.group(2).strip()
                continue
            cur_lines.append(line)
        else:
            cur_lines.append(line)
            stripped = line.strip()
            # A fence closes on a line of only fence chars, at least as long
            # as the opener.
            if (
                stripped
                and set(stripped) == {fence[0]}
                and len(stripped) >= len(fence)
            ):
                fence = None

    flush()
    return intro_lines, sections


def demote_headings(lines: list[str]) -> list[str]:
    """Demote headings one level (## -> #, ...), skipping fenced code blocks."""
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        if fence is None:
            fm = FENCE_RE.match(line)
            if fm:
                fence = fm.group(1)
                out.append(line)
                continue
            hm = HEADING_RE.match(line)
            if hm and 2 <= len(hm.group(1)) <= 6:
                out.append(f"{hm.group(1)[1:]} {hm.group(2)}\n")
                continue
            out.append(line)
        else:
            out.append(line)
            stripped = line.strip()
            if (
                stripped
                and set(stripped) == {fence[0]}
                and len(stripped) >= len(fence)
            ):
                fence = None
    return out


def import_icm_anim():
    """Import the installed (editable) icm_anim, dodging the tools/ shadow.

    Running tools/split_chapters.py as a script puts tools/ first on
    sys.path, where the icm_anim and icm_widgets package DIRS shadow their
    installed modules as empty namespace packages. Import with tools/
    off the path — and purge any shadow already in sys.modules — so the
    companions' own `import icm_anim` lands on the real thing too.
    """
    import os

    tools_dir = os.path.dirname(os.path.abspath(__file__))
    orig_path = list(sys.path)
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != tools_dir]
    try:
        for name in ("icm_anim", "icm_widgets"):
            mod = sys.modules.get(name)
            if mod is not None and getattr(mod, "__file__", None) is None:
                del sys.modules[name]
        import icm_anim

        return icm_anim
    finally:
        sys.path[:] = orig_path


def stash_anim_files(out_dir: Path) -> dict[str, bytes]:
    """Existing anim/ clip bytes by name, read before out_dir is wiped."""
    anim_dir = out_dir / ANIM_DIR
    if not anim_dir.exists():
        return {}
    return {p.name: p.read_bytes() for p in anim_dir.glob("*.mp4")}


def capture_companion_shows(companion: Path, icm_anim) -> list:
    """Exec a companion's code cells, recording show() calls unrendered.

    Gives materialize the actual Scene classes; runs with CWD at the
    companion's dir so any ../assets/ reads resolve.
    """
    nb = nbformat.read(str(companion), as_version=4)
    code_cells = [c.source for c in nb.cells if c.cell_type == "code"]
    namespace = {"__name__": "__icm_split_render__"}
    with icm_anim.capture_shows() as captured:
        for i, source in enumerate(code_cells):
            exec(compile(source, f"{companion}:cell{i}", "exec"), namespace)
    parsed = parse_anim_shows(code_cells, companion)
    matches = len(captured) == len(parsed) and all(
        c.scene_cls.__name__ == p.scene
        and (c.theme, c.quality, c.loop, c.max_mb)
        == (p.theme, p.quality, p.loop, p.max_mb)
        for c, p in zip(captured, parsed)
    )
    if not matches:
        sys.exit(
            f"{companion}: show() calls at run time don't match the static "
            "parse — keep each one a top-level anim.show(SceneCls, ...) with "
            "literal kwargs"
        )
    return captured


def check_anim_budgets(requests: list[AnimRequest], anim_dir: Path) -> None:
    """Enforce each show()'s max_mb on its committed files (all variants)."""
    by_show: dict[tuple[Path, int], list[AnimRequest]] = {}
    for r in requests:
        by_show.setdefault((r.companion, r.show.ordinal), []).append(r)
    for reqs in by_show.values():
        show = reqs[0].show
        sizes = {r.filename: (anim_dir / r.filename).stat().st_size / 1e6 for r in reqs}
        weight = sum(sizes.values())
        if weight > show.max_mb:
            for r in reqs:
                (anim_dir / r.filename).unlink(missing_ok=True)
            detail = ", ".join(f"{mb:.2f}" for mb in sizes.values())
            sys.exit(
                f"{show.scene} weighs {weight:.2f} MB as committed video "
                f"({detail}) against a {show.max_mb:.2f} MB budget — shorten "
                "the clip, calm the motion, or check the quality flag"
            )


def materialize_animations(
    requests: list[AnimRequest], anim_dir: Path, stash: dict[str, bytes]
) -> None:
    """Provide every clip the generated pages reference.

    Known hashes are rewritten from the stash byte-for-byte (so an unchanged
    split is a no-op for git); only new hashes render, and stashed files no
    page references anymore simply never come back. Skips rendering when
    RENDER_ANIMATIONS is off (merge's round-trip re-split).
    """
    wanted: dict[str, AnimRequest] = {}
    for r in requests:
        wanted.setdefault(r.filename, r)
    if not wanted:
        return
    anim_dir.mkdir(parents=True, exist_ok=True)
    misses: list[AnimRequest] = []
    for fname, r in wanted.items():
        if fname in stash:
            (anim_dir / fname).write_bytes(stash[fname])
        else:
            misses.append(r)
    if misses:
        if not RENDER_ANIMATIONS:
            return
        try:
            icm_anim = import_icm_anim()
        except ImportError as e:
            names = "\n".join(f"    {ANIM_DIR}/{r.filename}" for r in misses)
            sys.exit(
                f"animation clips need rendering:\n{names}\n"
                f"  but icm_anim is not importable ({e}) — install manim "
                "and `pip install -e tools/icm_anim`, or restore the "
                "committed anim/ files"
            )
        by_companion: dict[Path, list[AnimRequest]] = {}
        for r in misses:
            by_companion.setdefault(r.companion, []).append(r)
        for companion, reqs in sorted(by_companion.items()):
            with contextlib.chdir(companion.parent):
                captured = capture_companion_shows(companion, icm_anim)
                for r in reqs:
                    size = icm_anim.render_to_file(
                        captured[r.show.ordinal].scene_cls,
                        dark=r.dark,
                        quality=r.show.quality,
                        dest=anim_dir / r.filename,
                        **ANIM_ENCODE,
                    )
                    print(f"  rendered {ANIM_DIR}/{r.filename} ({size / 1e6:.2f} MB)")
    check_anim_budgets(requests, anim_dir)


def split_chapter(folder: Path) -> dict | None:
    m = CHAPTER_FOLDER_RE.match(folder.name)
    if not m:
        return None
    chapter_num = int(m.group(1))
    src = folder / "index.md"
    if not src.exists():
        print(f"  skip {folder.name}: no index.md", file=sys.stderr)
        return None

    raw = src.read_text()
    body = rewrite_chapter_links(FRONTMATTER_RE.sub("", raw, count=1))
    intro_lines, sections = split_body(body)

    # Chapter title = the first `# ` heading in the intro block.
    chapter_title = ""
    intro_after_title: list[str] = []
    seen_title = False
    for line in intro_lines:
        if not seen_title:
            hm = HEADING_RE.match(line)
            if hm and len(hm.group(1)) == 1:
                chapter_title = hm.group(2).strip()
                seen_title = True
                continue
            if line.strip() == "":
                continue
            # Anything else before the title is unexpected; drop it.
            continue
        intro_after_title.append(line)
    intro_text = "".join(intro_after_title).strip("\n")

    out_dir = CONTENT / f"ch{chapter_num:02d}"
    anim_stash = stash_anim_files(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    index_md = f"# {chapter_num}. {chapter_title}\n"
    if intro_text:
        index_md += f"\n{intro_text}\n"
    (out_dir / "index.md").write_text(index_md)

    section_refs: list[str] = []
    anim_requests: list[AnimRequest] = []
    for i, (title, content_lines) in enumerate(sections):
        body_text = "".join(demote_headings(content_lines)).strip("\n")
        section_md = f"# {chapter_num}.{i} {title}\n"
        if body_text:
            section_md += f"\n{body_text}\n"
        # A section that embeds a companion notebook becomes a notebook; every
        # other section stays Markdown. The TOC entry is extensionless either
        # way, so Jupyter Book resolves NN.ipynb or NN.md unchanged.
        if section_directives(section_md):
            nb = build_section_notebook(
                section_md, folder, chapter_num, i, anim_requests
            )
            (out_dir / f"{i:02d}.ipynb").write_text(nbformat.writes(nb) + "\n")
        else:
            (out_dir / f"{i:02d}.md").write_text(section_md)
        section_refs.append(f"ch{chapter_num:02d}/{i:02d}")

    for sub in ("assets", "code", "figures"):
        src_sub = folder / sub
        if src_sub.exists():
            shutil.copytree(src_sub, out_dir / sub)

    materialize_animations(anim_requests, out_dir / ANIM_DIR, anim_stash)

    return {
        "chapter_num": chapter_num,
        "index": f"ch{chapter_num:02d}/index",
        "sections": section_refs,
        "slug": folder.name,
        "title": chapter_title,
        "section_count": len(sections),
    }


def regenerate_toc(results: list[dict]) -> None:
    """Rewrite the chapter entries (ch*/) of _toc.yml in place.

    Replaces only the contiguous run of `- file: chNN/index` entries
    (with their nested `sections:`) inside the "Textbook" part; the hand-
    maintained scaffold around it (captions, templates, reference subtree)
    is preserved.
    """
    text = TOC.read_text()
    lines = text.splitlines()

    def indent(line: str) -> int:
        return len(line) - len(line.lstrip())

    starts = [
        i for i, l in enumerate(lines)
        if l.lstrip().startswith("- file: ch") and l.rstrip().endswith("/index")
    ]
    if not starts:
        sys.exit("could not locate chapter entries (ch*/index) in _toc.yml")
    start = starts[0]
    base = indent(lines[start])

    end = len(lines)
    for j in range(start + 1, len(lines)):
        l = lines[j]
        if not l.strip():
            continue  # blank lines inside the run are dropped
        ind = indent(l)
        is_sibling_file = ind == base and l.lstrip().startswith("- file:")
        if ind < base or (is_sibling_file and not l.lstrip().startswith("- file: ch")):
            end = j
            break

    pad = " " * base
    new_block: list[str] = []
    for r in sorted(results, key=lambda r: r["chapter_num"]):
        new_block.append(f"{pad}- file: {r['index']}")
        if r["sections"]:
            new_block.append(f"{pad}  sections:")
            for s in r["sections"]:
                new_block.append(f"{pad}    - file: {s}")

    new_lines = lines[:start] + new_block + lines[end:]
    TOC.write_text("\n".join(new_lines) + "\n")


def natural_key(name: str):
    """Sort key so 1.md, 2.md, ... order numerically and names order lexically."""
    stem = Path(name).stem
    return (0, int(stem), "") if stem.isdigit() else (1, 0, stem.lower())


def _toc_ref(path: Path) -> str:
    """content/course/assignments/01.md -> 'course/assignments/01' (TOC file ref)."""
    return path.relative_to(CONTENT).with_suffix("").as_posix()


def course_order_key(path: Path):
    """Sort course pages/subdirs by COURSE_ORDER, then naturally for the rest."""
    rank = COURSE_ORDER.index(path.stem) if path.stem in COURSE_ORDER else len(COURSE_ORDER)
    return (rank, natural_key(path.name))


def _short_title(md_path: Path) -> str | None:
    """Sidebar label for a course page: its H1 truncated at the first colon.

    "Assignment 3\\*: Exploring timbre and scores" -> "Assignment 3*";
    an H1 without a colon (already short) gets no override -> None.
    """
    try:
        text = md_path.read_text()
    except OSError:
        return None
    for line in text.splitlines():
        m = HEADING_RE.match(line)
        if m and len(m.group(1)) == 1:
            h1 = m.group(2).strip()
            if ":" not in h1:
                return None
            return h1.split(":", 1)[0].replace("\\*", "*").strip()
    return None


def _toc_entry(path: Path, indent: str) -> list[str]:
    """`- file:` line for a course page, plus a `title:` override when the
    page's H1 truncates at a colon (keeps the sidebar to short labels)."""
    lines = [f"{indent}- file: {_toc_ref(path)}"]
    title = _short_title(path)
    if title:
        lines.append(f'{indent}  title: "{title}"')
    return lines


def regenerate_course_toc() -> None:
    """Replace the "Course Information" part of _toc.yml from content/course/.

    One captioned part: top-level pages become flat `file:` entries; a
    subdirectory's index.md becomes a `file:` with its remaining pages nested
    under `sections:` (a subdir without an index.md is listed flat). A
    second-level subdirectory with an index.md (e.g. assignments/05/) nests
    its remaining pages one level deeper under that index. Every entry whose
    H1 contains a colon gets a `title:` override truncated at that colon, so
    the sidebar shows short labels ("Assignment 6") while pages keep their
    full titles. The part spans from the caption to the next `- caption:`;
    other parts are untouched.
    """
    entries = sorted(
        (p for p in COURSE_DEST.iterdir() if p.is_dir() or p.suffix == ".md"),
        key=course_order_key,
    )

    body = ["  - caption: Course Information", "    chapters:"]
    for p in entries:
        if not p.is_dir():
            body += _toc_entry(p, "      ")
            continue
        mds = list(p.glob("*.md"))
        index = next((q for q in mds if q.stem == "index"), None)
        sections = [q for q in mds if q.stem != "index"]
        sections += [
            d / "index.md"
            for d in p.iterdir()
            if d.is_dir() and (d / "index.md").exists()
        ]
        sections.sort(
            key=lambda q: natural_key(q.parent.name if q.stem == "index" else q.name)
        )
        if index is not None:
            body += _toc_entry(index, "      ")
            if sections:
                body.append("        sections:")
                for s in sections:
                    body += _toc_entry(s, "          ")
                    # a subdir's remaining pages nest one level deeper under its index
                    if s.stem == "index":
                        children = sorted(
                            (q for q in s.parent.glob("*.md") if q.stem != "index"),
                            key=lambda q: natural_key(q.name),
                        )
                        if children:
                            body.append("            sections:")
                            for c in children:
                                body += _toc_entry(c, "              ")
        else:
            for s in sections:
                body += _toc_entry(s, "      ")

    lines = TOC.read_text().splitlines()
    try:
        cap_idx = next(i for i, l in enumerate(lines) if l.strip() == COURSE_CAPTION)
    except StopIteration:
        sys.exit(f'could not locate "{COURSE_CAPTION}" in _toc.yml')
    end = next(
        (j for j in range(cap_idx + 1, len(lines))
         if lines[j].lstrip().startswith("- caption:")),
        len(lines),
    )
    new_lines = lines[:cap_idx] + body + lines[end:]
    TOC.write_text("\n".join(new_lines) + "\n")


def mirror_course() -> None:
    """Mirror the icm-f26/ course-website submodule verbatim into content/course/.

    icm-f26 pages are already MyST, so nothing is split or demoted — files
    are copied with their layout preserved, skipping the README placeholder
    and dotfiles/dirs. Wipes content/course/ first, then regenerates its
    part of _toc.yml.
    """
    if not COURSE_SOURCE.exists() or not any(COURSE_SOURCE.iterdir()):
        print(
            f"  skip course: no {COURSE_SOURCE.relative_to(REPO)}/ "
            "(run: git submodule update --init icm-f26)",
            file=sys.stderr,
        )
        return
    if COURSE_DEST.exists():
        shutil.rmtree(COURSE_DEST)
    COURSE_DEST.mkdir(parents=True)

    copied = 0
    for src in sorted(COURSE_SOURCE.rglob("*")):
        rel = src.relative_to(COURSE_SOURCE)
        if any(part.startswith(".") for part in rel.parts):
            continue  # skip .git and any other dotfiles/dirs
        if src.is_dir() or rel.name in COURSE_SKIP_FILES:
            continue
        dest = COURSE_DEST / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1

    print(f"  course  {copied} file(s)  <- icm-f26/")
    print_course_tree()
    regenerate_course_toc()
    print(f"  updated {TOC.relative_to(REPO)} (Course Information)")


def print_course_tree() -> None:
    """Print the mirrored content/course/ directory structure, so nesting
    (assignment subfolders, per-assignment assets) is visible at a glance."""

    def walk(d: Path, prefix: str) -> None:
        entries = sorted(
            (p for p in d.iterdir() if not p.name.startswith(".")),
            key=lambda p: (p.is_file(), natural_key(p.name)),
        )
        for i, p in enumerate(entries):
            tee = "└── " if i == len(entries) - 1 else "├── "
            print(f"  {prefix}{tee}{p.name}{'/' if p.is_dir() else ''}")
            if p.is_dir():
                walk(p, prefix + ("    " if i == len(entries) - 1 else "│   "))

    print(f"  {COURSE_DEST.relative_to(REPO)}/")
    walk(COURSE_DEST, "")


def sync_references() -> None:
    """Copy icm-text/refs.bib to content/references.bib (a generated file).

    The professor maintains the bibliography upstream; a leading @comment
    marks the copy as generated (bibtex ignores @comment entries).
    """
    if not REFS_SRC.exists():
        print(f"  skip references.bib: no {REFS_SRC.relative_to(REPO)}", file=sys.stderr)
        return
    header = (
        "@comment{\n"
        "  GENERATED FILE -- do not edit by hand.\n"
        "  Synced from icm-text/refs.bib by tools/split_chapters.py (`make split`).\n"
        "  Edit the bibliography in the icm-text submodule instead.\n"
        "}\n\n"
    )
    REFS_DEST.write_text(header + REFS_SRC.read_text())
    print(f"  synced {REFS_DEST.relative_to(REPO)}  <- icm-text/refs.bib")


def sync_front_matter() -> None:
    """Copy book front-matter pages verbatim from icm-text/ to content/.

    A missing source means a stale submodule checkout; fail rather than
    silently leaving a divergent copy in content/.
    """
    for name in FRONT_MATTER_FILES:
        src = SOURCE / name
        if not src.exists():
            sys.exit(
                f"icm-text/{name} not found — update the icm-text submodule"
            )
        shutil.copyfile(src, CONTENT / name)
        print(f"  synced content/{name}  <- icm-text/{name}")


def split_standalone_page(folder: Path, chapter_num: int, sec_index: int) -> None:
    """Regenerate folder/index.ipynb from folder/main.md + notebooks/.

    The template pages' entry point: the same expansion split_chapter runs
    on chapter sections, including the anim/ stash-and-materialize pass.
    Nothing else in the folder is touched.
    """
    main_md = folder / "main.md"
    if not main_md.exists():
        sys.exit(f"{main_md} not found")
    anim_stash = stash_anim_files(folder)
    anim_dir = folder / ANIM_DIR
    if anim_dir.exists():
        shutil.rmtree(anim_dir)
    anim_requests: list[AnimRequest] = []
    nb = build_section_notebook(
        main_md.read_text(), folder, chapter_num, sec_index, anim_requests
    )
    (folder / "index.ipynb").write_text(nbformat.writes(nb) + "\n")
    materialize_animations(anim_requests, anim_dir, anim_stash)
    print(f"  wrote {folder / 'index.ipynb'}")


def main() -> int:
    if not SOURCE.exists() or not any(SOURCE.iterdir()):
        sys.exit(
            f"icm-text/ not found or empty at {SOURCE}\n"
            "  run: git submodule update --init icm-text"
        )
    folders = sorted(
        p for p in SOURCE.iterdir() if p.is_dir() and CHAPTER_FOLDER_RE.match(p.name)
    )
    results: list[dict] = []
    for folder in folders:
        r = split_chapter(folder)
        if r:
            print(
                f"  ch{r['chapter_num']:02d}  {r['section_count']} section(s)  "
                f"<- icm-text/{r['slug']}"
            )
            results.append(r)
    if not results:
        sys.exit("no chapters found in icm-text/")
    regenerate_toc(results)
    print(f"  updated {TOC.relative_to(REPO)}")
    mirror_course()
    sync_front_matter()
    sync_references()
    return 0


def cli() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--page",
        type=Path,
        help="regenerate one standalone page folder (main.md + notebooks/) "
        "instead of splitting icm-text",
    )
    ap.add_argument(
        "--chapter",
        type=int,
        default=99,
        help="chapter number for --page cell ids (default: 99)",
    )
    ap.add_argument(
        "--section",
        type=int,
        default=0,
        help="section index for --page cell ids (default: 0)",
    )
    args = ap.parse_args()
    if args.page:
        split_standalone_page(args.page.resolve(), args.chapter, args.section)
        return 0
    return main()


if __name__ == "__main__":
    raise SystemExit(cli())
