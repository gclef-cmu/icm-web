#!/usr/bin/env python3
"""Split each icm-text/{n}-{slug}/index.md into per-section files under content/ch{nn}/.

icm-text/ (a pinned submodule) is the ground truth. For each chapter this
strips the frontmatter, splits the body on `## ` headings (ignoring fenced
code blocks), demotes headings one level, copies assets/code/figures across,
and regenerates the chapter part of _toc.yml. A section that embeds a
companion notebook via `{interactive}`/`{animation}` is emitted as a .ipynb
instead of .md. It also mirrors the icm-f26/ course-website submodule into
content/course/, copies book front matter (about.md, errata.md) from
icm-text/ to content/, and copies icm-text/refs.bib to content/references.bib.

Everything is authored in MyST already, so nothing is translated — only
restructured. Run via `make split`. WARNING: wipes content/ch*/ and
content/course/, dropping any local overrides; review `git diff content/`
afterward.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

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
    section_md: str, chapter_folder: Path, chapter_num: int, sec_index: int
):
    """Turn a section that embeds companion notebooks into a notebook.

    The section text is segmented at each directive: the prose around them
    becomes Markdown cells, and each directive expands to the referenced
    notebook's cells (see add_notebook). Cells are not ``skip-execution``, so
    the build bakes their output into the page.

    Cell ids derive from chapter/section/ordinal, keeping the output
    byte-for-byte deterministic — tools/merge_chapters.py relies on that for
    its round-trip check. Each expanded cell stashes the directive's kind and
    path in its metadata so merge can collapse the run back into one
    directive line.
    """
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

    def add_notebook(src: Path, rel: str, kind: str, group: int) -> None:
        """Expand a companion notebook in place as section cells.

        ``{interactive}`` code cells stay runnable. The `# hide` marker maps
        to our ``icm-hide-input`` tag (CSS-hidden but still in the DOM, so
        the live run chain can execute it — myst-nb's ``remove-input`` would
        strip it and break cells below); `# collapse` maps to ``hide-input``.
        Each also gets an ``icm-run-group-{group}`` tag, one group per
        directive, so a Run's setup chain covers only its own notebook.

        ``{animation}`` code cells are watch-only: always ``icm-hide-input``
        plus ``disable-execution-cell`` (no editor, no Run chip), no run
        group, and the visibility/no-output markers are ignored.
        """
        nonlocal k
        for c in nbformat.read(str(src), as_version=4).cells:
            meta = {kind: {"path": rel}}
            if c.cell_type == "markdown":
                cell = new_markdown_cell(c.source)
                cell["id"] = f"{base}m{k}"
                cell["metadata"] = meta
                cells.append(cell)
                k += 1
            elif c.cell_type == "code":
                cc = new_code_cell(c.source)
                cc["id"] = f"{base}c{k}"
                if kind == "animation":
                    tags = ["icm-hide-input", "disable-execution-cell"]
                else:
                    visibility = cell_visibility(c.source)
                    tags = [f"icm-run-group-{group}"]
                    if visibility == "hide":
                        tags.append("icm-hide-input")
                    elif visibility == "collapse":
                        tags.append("hide-input")
                    if cell_no_output(c.source):
                        tags.append("remove-output")
                    if cell_autorun(c.source):
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
    body = FRONTMATTER_RE.sub("", raw, count=1)
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
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    index_md = f"# {chapter_num}. {chapter_title}\n"
    if intro_text:
        index_md += f"\n{intro_text}\n"
    (out_dir / "index.md").write_text(index_md)

    section_refs: list[str] = []
    for i, (title, content_lines) in enumerate(sections):
        body_text = "".join(demote_headings(content_lines)).strip("\n")
        section_md = f"# {chapter_num}.{i} {title}\n"
        if body_text:
            section_md += f"\n{body_text}\n"
        # A section that embeds a companion notebook becomes a notebook; every
        # other section stays Markdown. The TOC entry is extensionless either
        # way, so Jupyter Book resolves NN.ipynb or NN.md unchanged.
        if section_directives(section_md):
            nb = build_section_notebook(section_md, folder, chapter_num, i)
            (out_dir / f"{i:02d}.ipynb").write_text(nbformat.writes(nb) + "\n")
        else:
            (out_dir / f"{i:02d}.md").write_text(section_md)
        section_refs.append(f"content/ch{chapter_num:02d}/{i:02d}")

    for sub in ("assets", "code", "figures"):
        src_sub = folder / sub
        if src_sub.exists():
            shutil.copytree(src_sub, out_dir / sub)

    return {
        "chapter_num": chapter_num,
        "index": f"content/ch{chapter_num:02d}/index",
        "sections": section_refs,
        "slug": folder.name,
        "title": chapter_title,
        "section_count": len(sections),
    }


def regenerate_toc(results: list[dict]) -> None:
    """Rewrite the chapter entries (content/ch*/) of _toc.yml in place.

    Replaces only the contiguous run of `- file: content/chNN/index` entries
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
        if l.lstrip().startswith("- file: content/ch") and l.rstrip().endswith("/index")
    ]
    if not starts:
        sys.exit("could not locate chapter entries (content/ch*/index) in _toc.yml")
    start = starts[0]
    base = indent(lines[start])

    end = len(lines)
    for j in range(start + 1, len(lines)):
        l = lines[j]
        if not l.strip():
            continue  # blank lines inside the run are dropped
        ind = indent(l)
        is_sibling_file = ind == base and l.lstrip().startswith("- file:")
        if ind < base or (is_sibling_file and not l.lstrip().startswith("- file: content/ch")):
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
    """content/course/assignments/01.md -> 'content/course/assignments/01' (TOC file ref)."""
    return "content/" + path.relative_to(CONTENT).with_suffix("").as_posix()


def course_order_key(path: Path):
    """Sort course pages/subdirs by COURSE_ORDER, then naturally for the rest."""
    rank = COURSE_ORDER.index(path.stem) if path.stem in COURSE_ORDER else len(COURSE_ORDER)
    return (rank, natural_key(path.name))


def regenerate_course_toc() -> None:
    """Replace the "Course Information" part of _toc.yml from content/course/.

    One captioned part: top-level pages become flat `file:` entries; a
    subdirectory's index.md becomes a `file:` with its remaining pages nested
    under `sections:` (a subdir without an index.md is listed flat). A
    second-level subdirectory with an index.md (e.g. assignments/05/) nests
    its remaining pages one level deeper under that index. The part spans
    from the caption to the next `- caption:`; other parts are untouched.
    """
    entries = sorted(
        (p for p in COURSE_DEST.iterdir() if p.is_dir() or p.suffix == ".md"),
        key=course_order_key,
    )

    body = ["  - caption: Course Information", "    chapters:"]
    for p in entries:
        if not p.is_dir():
            body.append(f"      - file: {_toc_ref(p)}")
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
            body.append(f"      - file: {_toc_ref(index)}")
            if sections:
                body.append("        sections:")
                for s in sections:
                    body.append(f"          - file: {_toc_ref(s)}")
                    # a subdir's remaining pages nest one level deeper under its index
                    if s.stem == "index":
                        children = sorted(
                            (q for q in s.parent.glob("*.md") if q.stem != "index"),
                            key=lambda q: natural_key(q.name),
                        )
                        if children:
                            body.append("            sections:")
                            body += [
                                f"              - file: {_toc_ref(c)}" for c in children
                            ]
        else:
            body += [f"      - file: {_toc_ref(s)}" for s in sections]

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
    regenerate_course_toc()
    print(f"  updated {TOC.relative_to(REPO)} (Course Information)")


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


if __name__ == "__main__":
    raise SystemExit(main())
