# CMU Intro to Computer Music

Source for **CMU Intro to Computer Music**, the 15-322 / 15-622 textbook and
course site at Carnegie Mellon University, built with
[Jupyter Book](https://jupyterbook.org).

This repo is **public** and stays public. The site's pages are generated at
build time from submodules and are not committed here.

## Submodules

- **`icm-text/`** (public) — chapter prose, the source of truth
  ([`chrisdonahue/pcm`](https://github.com/chrisdonahue/pcm); the submodule
  path keeps the pre-rename name). `make split` derives `content/ch*/` from it.
- **`icm-f26/`** (private) — the course website (schedule, assignments,
  resources). `make split` mirrors it into `content/course/`.
- **`pyquist/`** (public) — the course audio library
  ([`gclef-cmu/pyquist`](https://github.com/gclef-cmu/pyquist)); the Pyquist
  Overview and API pages are generated from it.

## Build

```sh
git clone --recurse-submodules <repo-url>   # icm-f26 is private, needs access
conda env create -f environment.yml         # installs pyquist from ./pyquist
conda activate icmbook

make split     # generate content/ from the submodules (required before book)
make book      # build HTML into _build/html/
make serve     # build + serve at http://localhost:8000
make pdf       # PDF build (needs a LaTeX toolchain)
make clean     # remove build outputs
```

Every target assumes the `icmbook` env is active. After creating or
recreating the env, force-install the TeachBooks sphinx-thebe fork —
`make book` checks this and prints the exact command (see **The fork trap**).

## How content flows

The site has two URL trees: `course/` (from icm-f26) and `book/` — the
textbook's canonical home. The site root redirects to the course home page.

`make split` regenerates `content/book/ch*/` (from icm-text),
`content/course/` (from icm-f26), `book/index.md` (the About cover page) /
`book/errata.md` / `book/references.bib`, and the generated regions of
`_toc.yml`. All of that is **gitignored**; the only committed part of the
generated tree is the pre-rendered animation clips
(`content/book/chNN/anim/*.mp4`). Hand-authored pages (`book/appendix/`,
`book/pyquist/`, `book/reference/`, `index.md`, the templates) stay
committed.

Releasing content is a pin bump — CI runs `make split` itself:

```sh
git submodule update --remote icm-text   # or icm-f26; fetch what you want to release
make split                               # optional: preview locally
git add icm-text _toc.yml && git commit && git push
```

Pins must point at commits pushed to the submodule remotes, or CI can't
fetch them. After pulling someone else's pin bump, run `make split` to
refresh your working tree.

`{animation}` clips render at **split** time, not build time. Unchanged clips
are reused byte-for-byte (their filenames are content hashes), so only new or
edited scenes need the authoring stack locally (`pip install manim==0.20.1 &&
pip install -e tools/icm_anim`, plus TeX for `MathTex`) — commit the new mp4s
together with the pin bump, or CI fails the split asking for them.

`make merge` is the inverse: reassembles `content/ch*/` into icm-text-shaped
files (under `icm-text-merged/`) for PR'ing edits upstream, and self-checks
the round-trip.

## Authoring

Pages are **MyST Markdown** (`.md`) or notebooks (`.ipynb`). Live references
for every feature: `content/template-md.md` (prose) and
`content/template-notebook.ipynb` (runnable code, audio, plots). Chapters are
folders `content/chNN/` with one file per section; the section number lives
in each H1.

## Pyquist docs

All Pyquist pages are generated — no hand-written API docs.
`content/book/pyquist/Overview.md` mirrors the submodule README each build; the
`api/*.md` autodoc shells introspect the **installed** module (the editable
install from `conda env create`). A failed import renders them silently
empty (see Troubleshooting). Update by bumping the pin:
`git submodule update --remote pyquist && git add pyquist && git commit`.

## Live code (in-browser Python)

Notebook pages are live: cells become editors on page load, and the first
▶ Run boots a Python kernel **in the browser** via Pyodide — no server. The
pipeline: `make book` builds wheels (`_static/wheels/`, including sounddevice
and soundfile stubs for WASM) and vendors the thebe + Pyodide runtimes under
`vendor/` (self-hosted; the kernel worker must be same-origin — never move
them into `_static/`, where every `.js` auto-loads on each page). Page glue
is `_static/live-cells.{js,css}`.

### The version matrix (these move together — don't bump one alone)

| Pin | Where | Why |
|---|---|---|
| Pyodide **0.27.7** | `pyodideUrl` in `_static/live-cells.js` | pyquist needs numpy ≥ 2; bundled pyodide_kernel 0.4.7 crashes on ≥ 0.28 |
| thebe-lite **0.5.0**, thebe **0.9.3** | `Makefile` (`vendor-thebe`) | newest released; embeds pyodide_kernel 0.4.7 |
| sphinx-thebe fork @ `1f3a809` | `environment.yml` | fork publishes no tags |
| soundfile stub | `tools/soundfile_stub/` | Pyodide < 0.28 ships no WASM soundfile |

Blocked upgrade: Pyodide 0.28 needs a thebe-lite release embedding
pyodide-kernel ≥ 0.6. When it ships: bump both in `vendor-thebe`,
`rm -rf vendor/thebe-dist`, bump `pyodideUrl` + `pipliteWheelUrl` in
`live-cells.js`, delete the soundfile stub, smoke-test.

**The fork trap**: the TeachBooks sphinx-thebe fork shares upstream's dist
name *and* version, so a fresh env silently keeps upstream and deployed
pages break. Guards: `make book` refuses to build with upstream, and CI
force-installs the fork. After recreating an env, run the
`pip install --force-reinstall --no-deps "sphinx-thebe @ git+…"` command
from `environment.yml`.

**Smoke test** after touching any of this: `make serve`, open
`http://localhost:8000/template-notebook.html` (must be `http://`, not
`file://`). Cells should be editable immediately with no layout shift; ▶ Run
on the `pq.play(tone)` cell should boot the kernel and produce a working
audio card. `pq.record(...)` records from the mic via the browser (needs the
pyquist `browser-recording` branch until it merges to main). §5 of the
template notebook is the deliberate test surface for clear error messages on
unsupported operations (mp3 read, device access) — the messages live in the
stubs under `tools/`.

## Color palette

One palette serves prose, figures, widgets, and animations — import the
named constants from `icm_widgets` / `icm_anim`, never paste hex codes.

| Name | Hex | Use |
|---|---|---|
| RED | `#C41230` | Carnegie red — primary accent, links |
| BLUE | `#007BC0` | plot series |
| GOLD | `#FDB515` | plot series, accents |
| TEAL | `#008F91` | plot series |
| IRON | `#6D6E71` | muted accents |
| STEEL | `#E0E0E0` | light strokes / fills |
| INK / INK_DARK | `#3B3B3B` / `#ECECEC` | figure text, light/dark |
| page light / dark | `#FFFFFF` / `#101010` | `--pst-color-background`; baked into animations |

The page backgrounds live in `_static/custom.css` **and**
`tools/icm_anim/icm_anim.py` and must stay in sync. The dark page is
`#101010` (not the theme's `#121212`) because grey 18 has no exact code in
limited-range H.264 video — if it ever changes, pick a grey that round-trips
through video and update both definitions.

## Troubleshooting

- **`make: jupyter-book: No such file or directory`** — the `icmbook` env
  isn't active.
- **Pyquist API pages are empty** — autodoc's import failed silently. Check
  `python -c "import pyquist; print(pyquist.__file__)"` points inside this
  repo; if not, `pip install -e ./pyquist`, then `make clean && make book`.
- **Live code crashes with a JSON error** — the site was built with upstream
  sphinx-thebe (see The fork trap). Force-install the fork and rebuild.
- **Cells never become editable / Run hangs** — check the browser console
  for `[live-cells]`; serve over `http://`, hard-reload (the service worker
  caches aggressively), and re-fetch a half-downloaded runtime with
  `rm -rf vendor/thebe-dist && make book`.

## Deploy

Pushing to `main` triggers `.github/workflows/deploy-book.yml` (GitHub
Pages) and `deploy-scs.yaml` (SCS mirror); both can also be run from the
Actions tab. CI fetches pyquist and icm-text anonymously (both public) and
icm-f26 at its **pinned SHA** using the `ICM_F26_READ_TOKEN` secret (a
fine-grained read PAT — it expires, which breaks the fetch step until
renewed), then runs `make split` and `make book`. CI installs no
manim/TeX: it reuses the committed animation clips. All live-code artifacts
are built in CI too — nothing generated is committed except those clips.

Both jobs time out after 20 minutes (a hung runner otherwise burns the 6 h
default). Before its scp, deploy-scs resolves the SCS hostname with retries
and public-resolver fallbacks and pins it in `/etc/hosts` — runners
intermittently fail DNS lookups to CMU. Never re-run a **failed deploy-book
run**: the duplicate Pages artifact breaks the deploy step; dispatch a fresh
run instead (`gh workflow run deploy-book.yml`).

## Layout

```
icm-text/    chapter prose (public pcm submodule, source of truth)
icm-f26/     course website (private submodule; mirrored to content/course/)
pyquist/     audio library (public submodule)
tools/       split/merge scripts, icm_anim, icm_widgets, browser stubs
content/     site sources — course/ + book/ (textbook, the /book URL tree),
             generated by `make split` (gitignored) except hand-authored
             pages and committed book/chNN/anim/ clips
_static/     book JS/CSS — custom.css, live-cells.{js,css}, wheels/ (generated)
_ext/        local Sphinx extensions — {audio}, figures, glossary, roles
vendor/      vendored thebe/Pyodide runtimes (generated, gitignored)
_config.yml  Jupyter Book config
_toc.yml     table of contents (generated regions rewritten by make split)
Makefile     split / book / serve / pdf / merge / clean
```
