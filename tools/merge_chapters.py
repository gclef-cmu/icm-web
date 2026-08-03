#!/usr/bin/env python3
"""Combine content/ch{nn}/ section files back into {n}-{slug}/index.md chapters.

The inverse of tools/split_chapters.py, for PRing edits back up to icm-text.
By design `split(merge(content)) == content` byte for byte; the round-trip is
verified after writing and fails loudly if the rendered tree would change.

Output goes to icm-text-merged/ (override with --out) so it can be diffed
against the submodule before opening a PR.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

import nbformat

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "icm-text"  # ground-truth prose submodule
CONTENT = REPO / "content"

from split_chapters import (  # noqa: E402
    CHAPTER_FOLDER_RE,
    FENCE_RE,
    HEADING_RE,
    split_chapter as split_one_chapter,
)

INDEX_TITLE_RE = re.compile(r"^#\s+(\d+)\.\s+(.+)$")
SECTION_TITLE_RE = re.compile(r"^#\s+\d+\.\d+\s+(.+)$")
# Sections are NN.md, or NN.ipynb when they embed a companion notebook.
SECTION_FILE_RE = re.compile(r"^\d{2}\.(md|ipynb)$")

# Directive kinds a section notebook's cells can come from; each such cell
# stashes metadata[kind] = {"path": ...}. Matches split_chapters.DIRECTIVE_OPEN_RE.
DIRECTIVE_KINDS = ("interactive", "animation")


def reconstruct_section_md(path: Path) -> str:
    """Rebuild the ``NN.md``-equivalent section text from a section notebook.

    Inverse of ``split_chapters.build_section_notebook``: prose Markdown cells
    are emitted verbatim, and each run of cells expanded from the same
    directive collapses back into the one directive line the author wrote,
    reproducing the exact string the splitter parsed.
    """
    nb = nbformat.read(str(path), as_version=4)
    parts: list[str] = []
    last: tuple[str, str] | None = None  # (kind, path) of the previous embed cell
    seen_directive = False
    for c in nb.cells:
        meta = c.metadata or {}
        kind = next((kd for kd in DIRECTIVE_KINDS if meta.get(kd)), None)
        if kind is not None:
            # The run key is the (kind, path) pair — path alone would wrongly
            # merge an {interactive} directly followed by an {animation} over
            # the same companion notebook.
            rel = meta[kind]["path"]
            if (kind, rel) != last:
                parts.append(f":::{{{kind}}}[{rel}]\n:::")
                seen_directive = True
            last = (kind, rel)
        elif c.cell_type == "markdown":
            parts.append(c.source)
            last = None  # section prose ends a run
        else:
            sys.exit(f"{path}: unexpected cell in section notebook")
    if not seen_directive:
        sys.exit(f"{path}: notebook section has no directive cell")
    return "\n\n".join(parts) + "\n"


def section_source(path: Path) -> str:
    """Section text in ``NN.md`` form, rebuilding it from a notebook if needed."""
    if path.suffix == ".ipynb":
        return reconstruct_section_md(path)
    return path.read_text()


def promote_headings(text: str) -> str:
    """Promote headings one level (# -> ##, ...), skipping fenced code blocks.

    Inverse of split_chapters.demote_headings; level-6 headings stay put.
    """
    lines = text.splitlines(keepends=True)
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
            if hm and 1 <= len(hm.group(1)) <= 5:
                out.append(f"#{hm.group(1)} {hm.group(2)}\n")
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
    return "".join(out)


def find_slug_for_chapter(chapter_num: int) -> str | None:
    """Reuse icm-text/{n}-{slug}/ folder name if one already exists upstream.

    Matched numerically so zero-padded folder names (08-dft) work too.
    """
    if not SOURCE.exists():
        return None
    for p in SOURCE.iterdir():
        m = CHAPTER_FOLDER_RE.match(p.name)
        if p.is_dir() and m and int(m.group(1)) == chapter_num:
            return p.name
    return None


# Inverse of split_chapters.rewrite_chapter_links: flattened ../ch{nn}/
# index-page links go back to the upstream {n}-{slug}/ folder form so the
# merged tree diffs cleanly against icm-text. Unresolvable numbers are
# left alone (the forward rewrite ignores ../ch{nn} forms, so the
# round-trip stays byte-identical either way).
CHAPTER_LINK_INDEX_RE = re.compile(r"\]\(\.\./ch(\d{2})/index\.md(#[^)]*)?\)")


def restore_chapter_links(text: str) -> str:
    def repl(m):
        slug = find_slug_for_chapter(int(m.group(1)))
        if slug is None:
            return m.group(0)
        return f"](../{slug}{m.group(2) or ''})"

    return CHAPTER_LINK_INDEX_RE.sub(repl, text)


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "chapter"


def merge_chapter(content_chapter: Path, out_root: Path) -> dict:
    idx_path = content_chapter / "index.md"
    idx_text = idx_path.read_text()
    first_line, _, idx_rest = idx_text.partition("\n")
    m = INDEX_TITLE_RE.match(first_line)
    if not m:
        sys.exit(f"unexpected index.md heading in {idx_path}: {first_line!r}")
    chapter_num = int(m.group(1))
    title = m.group(2).strip()
    intro = idx_rest.strip("\n")

    section_files = sorted(
        f for f in content_chapter.iterdir() if SECTION_FILE_RE.match(f.name)
    )
    sections: list[tuple[str, str]] = []
    for f in section_files:
        text = section_source(f)
        first, _, body = text.partition("\n")
        sm = SECTION_TITLE_RE.match(first)
        if not sm:
            sys.exit(f"unexpected section heading in {f}: {first!r}")
        sec_title = sm.group(1).strip()
        sec_body = promote_headings(body.strip("\n"))
        sections.append((sec_title, sec_body))

    parts: list[str] = [f'---\ntitle: "Chapter {chapter_num}: {title}"\n---\n']
    parts.append(f"\n# {title}\n")
    if intro:
        parts.append(f"\n{intro}\n")
    for sec_title, sec_body in sections:
        parts.append(f"\n## {sec_title}\n")
        if sec_body:
            parts.append(f"\n{sec_body}\n")
    merged_text = restore_chapter_links("".join(parts))

    slug = find_slug_for_chapter(chapter_num) or f"{chapter_num}-{slugify(title)}"
    out_dir = out_root / slug
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "index.md").write_text(merged_text)

    # Copy auxiliary subdirs so the merged tree is self-contained and the
    # round-trip check can re-copy them back into content/.
    for sub in ("assets", "code", "figures"):
        src_sub = content_chapter / sub
        if src_sub.exists():
            shutil.copytree(src_sub, out_dir / sub)

    # Carry over top-level files that live upstream but aren't managed through
    # content/ (e.g. OUTLINE); rsync --delete would otherwise wipe them.
    upstream_chapter = SOURCE / slug
    if upstream_chapter.exists():
        managed = {"index.md", "assets", "code", "figures"}
        for item in upstream_chapter.iterdir():
            if item.name in managed:
                continue
            dest = out_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)

    return {
        "chapter_num": chapter_num,
        "slug": slug,
        "section_count": len(sections),
        "out_dir": out_dir,
    }


def roundtrip_check(merged_root: Path, results: list[dict]) -> None:
    """Re-run the splitter on the merged tree and diff against content/ch*/."""
    print("\nverifying round-trip (split(merge(content)) == content)...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_content = Path(tmp) / "content"
        tmp_content.mkdir()
        # Temporarily redirect the splitter's CONTENT and SOURCE globals.
        import split_chapters as sp

        orig_source, orig_content = sp.SOURCE, sp.CONTENT
        sp.SOURCE, sp.CONTENT = merged_root, tmp_content
        try:
            for r in results:
                folder = merged_root / r["slug"]
                sp.split_chapter(folder)
        finally:
            sp.SOURCE, sp.CONTENT = orig_source, orig_content

        any_diff = False
        for r in results:
            n = r["chapter_num"]
            orig = CONTENT / f"ch{n:02d}"
            roundtripped = tmp_content / f"ch{n:02d}"
            files_to_check = sorted(
                p.name
                for p in orig.iterdir()
                if p.is_file() and p.suffix in (".md", ".ipynb")
            )
            for name in files_to_check:
                a = (orig / name).read_text()
                b_path = roundtripped / name
                if not b_path.exists():
                    print(f"  ch{n:02d}/{name}: MISSING after round-trip")
                    any_diff = True
                    continue
                b = b_path.read_text()
                if a != b:
                    print(f"  ch{n:02d}/{name}: DIFFERS")
                    any_diff = True
                    for i, (la, lb) in enumerate(
                        zip(a.splitlines(), b.splitlines()), 1
                    ):
                        if la != lb:
                            print(f"    line {i}:")
                            print(f"      orig:  {la!r}")
                            print(f"      round: {lb!r}")
                            break
            # Also flag any extra files that appeared after round-trip.
            extra = sorted(
                p.name
                for p in roundtripped.iterdir()
                if p.is_file()
                and p.suffix in (".md", ".ipynb")
                and p.name not in files_to_check
            )
            for name in extra:
                print(f"  ch{n:02d}/{name}: EXTRA (not in original content)")
                any_diff = True

        if any_diff:
            sys.exit(
                "\nround-trip check failed: split(merge(content)) != content.\n"
                "The merged output would change the rendered site."
            )
        print("  round-trip OK — rendered site will be byte-identical.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=REPO / "icm-text-merged",
        help="output directory for merged chapter folders (default: icm-text-merged/)",
    )
    ap.add_argument(
        "--skip-verify",
        action="store_true",
        help="skip the round-trip self-check",
    )
    args = ap.parse_args()

    if not CONTENT.exists():
        sys.exit(f"content/ not found at {CONTENT}")
    chapter_dirs = sorted(
        p
        for p in CONTENT.iterdir()
        if p.is_dir() and re.match(r"^ch\d+$", p.name) and (p / "index.md").exists()
    )
    if not chapter_dirs:
        sys.exit("no content/ch{nn}/ chapters found")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    results: list[dict] = []
    for cd in chapter_dirs:
        r = merge_chapter(cd, args.out)
        out_disp = r["out_dir"]
        if out_disp.is_relative_to(REPO):
            out_disp = out_disp.relative_to(REPO)
        print(f"  {cd.name} -> {out_disp}  ({r['section_count']} section(s))")
        results.append(r)

    if not args.skip_verify:
        roundtrip_check(args.out, results)

    out_disp = args.out
    if out_disp.is_relative_to(REPO):
        out_disp = out_disp.relative_to(REPO)
    print(f"\nmerged tree written to {out_disp}/")
    print("compare with upstream:  diff -ruN icm-text/ icm-text-merged/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
