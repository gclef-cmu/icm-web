# CMU Intro to Computer Music

Source for **CMU Intro to Computer Music**, the 15-322 / 15-622 textbook and
course site at Carnegie Mellon University, built with
[Jupyter Book](https://jupyterbook.org).

This repo is **public** and stays public. The site's pages are generated at
build time from submodules and are not committed here.

## Submodules

- **`icm-text/`** (public) — chapter prose, the source of truth
  ([`chrisdonahue/pcm`](https://github.com/chrisdonahue/pcm); the submodule
  path keeps the pre-rename name). `make split` derives `content/book/ch*/` from it.
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
`book/reference/`, `pyquist/`, `index.md`, the templates) stay committed.

The Pyquist docs live at `content/pyquist/` (URL `/pyquist/`) and are listed
as the last Course Information sidebar entry — `make split` appends that TOC
tail. The Templates part stays in `_toc.yml` (Sphinx numbering needs it) but
is hidden from the sidebar and pagination by rules in `_static/custom.css`;
authors enter through the unlinked `/templates/` page.

Unreleased assignments (icm-f26's `assignments/harry/`) mirror to the
unlinked **`/course/harry/`** URL for instructor preview. The pages build as
orphans (`orphan` + `nosearch` front matter injected at split; they never
enter `_toc.yml`), so no page HTML, sidebar, pagination, or search result
references them, and `make book` scrubs their names from `searchindex.js` —
knowing the URL is the only way in. The pages are still public, and this
paragraph names the URL: that trade-off is deliberate.

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

`make merge` is the inverse: reassembles `content/book/ch*/` into icm-text-shaped
files (under `icm-text-merged/`) for PR'ing edits upstream, and self-checks
the round-trip.

## Authoring

Pages are **MyST Markdown** (`.md`) or notebooks (`.ipynb`). Live references
for every feature: `content/template-md.md` (prose) and
`content/template-notebook.ipynb` (runnable code, audio, plots). Chapters are
folders `content/book/chNN/` with one file per section; the section number lives
in each H1.

## Pyquist docs

All Pyquist pages are generated — no hand-written API docs.
`content/pyquist/Overview.md` mirrors the submodule README each build; the
`api/*.md` autodoc shells introspect the **installed** module (the editable
install from `conda env create`). A failed import renders them silently
empty (see Troubleshooting). Update by bumping the pin:
`git submodule update --remote pyquist && git add pyquist && git commit`.

## Live code (in-browser Python)

Notebook pages are live: cells become editors on page load, and a Python
kernel boots **in the browser** via Pyodide — no server — on the first ▶ Run,
or at page load on pages with an `# autorun` widget. Everything below is
shared infrastructure: it applies to every page with code cells and to every
widget built with `icm_plotly.show(figure, controls)`, never to one widget.
Page glue is `_static/live-cells.{js,css}`; the kernel worker and the patched
thebe bundle must stay same-origin under `vendor/` (never `_static/`, where
every `.js` auto-loads on each page).

### The pipeline, end to end

**Build (`make book`)**
1. `wheels`: builds the book wheels (`_static/wheels/`: pyquist from the
   submodule, icm_plotly, icm_widgets, the sounddevice/soundfile WASM
   stubs) and downloads the plotly widget stack (`_static/wheels/widgets/`);
   writes both manifests — the widgets one carries each wheel's exact
   `files.pythonhosted.org` URL (`tools/widget_wheel_manifest.py`). Copies
   the build env's `plotly.min.js` to `vendor/plotly-dist/`, and vendors
   anywidget's frontend, patched to import widget ESM in the page realm,
   under a content-hash directory `vendor/widgets-cdn/<hash>/` named by
   `vendor/widgets-cdn/manifest.json` (`tools/vendor_anywidget.py`).
2. `vendor-thebe`, `vendor-pyodide`: the thebe/thebe-lite bundles (thebe's
   CDN base patched overridable) and a full Pyodide 0.27.7 mirror under
   `vendor/` — the self-hosted **fallbacks** for the CDNs below.
3. `jupyter-book build`: executes notebooks. `icm_plotly.show()` bakes each
   widget as the figure's JSON (height fixed to the FigureWidget default,
   `data-plotlyjs` = the exact plotly.js version) plus an inert **ghost** of
   its controls — `controls()` runs once with ipywidgets comms switched
   off, so nothing widget-shaped reaches the page — so the page shows the
   finished layout with no kernel, and the live widget later lands in the
   same pixels.

**Page load (no Python yet)**
- The baked figure renders immediately from jsDelivr's `plotly.js-dist-min`
  at the baked version (fallback: `vendor/plotly-dist/`); the ghost sits
  above it, pixel-identical to the live controls (its CSS rules are paired
  with the live ones in `live-cells.css`).
- Editors mount; `window.__icmWidgetsCdn` resolves from the hashed
  widgets-cdn manifest (fetched `no-store`) before thebe loads, because thebe
  bakes that base into a module constant.
- Prose pages (no code cells) quietly prefetch the kernel runtime from the
  origin the kernel will use, so the next widget page boots from cache.

**Kernel boot (`startKernel` → `installWheels`)**
1. `pyodideBase()` HEAD-probes jsDelivr's `pyodide-lock.json` (8 s); Pyodide
   and its packages load from `cdn.jsdelivr.net/pyodide/v0.27.7/full/`, else
   from `/pyodide/`. Prose-page prefetch uses the same decision.
2. Compiled packages come from the Pyodide distribution first (WASM builds,
   so micropip never picks a native PyPI wheel): **numpy always**; matplotlib
   only if the page's code mentions matplotlib/icm_widgets/pyquist; soxr,
   requests, tqdm only with pyquist. `pageWants()` reads the page's own
   cells (the extension's hidden matplotlib-patch init cell excluded).
3. Book wheels, each only where used: stubs + pyquist with pyquist;
   icm_widgets with icm_plotly (it imports its palette from it); icm_plotly
   on plotly pages. Never `!pip`/PyPI for these.
4. Plotly pages: the widget stack installs `deps=False` from PyPI's CDN by
   exact file URL (probe, 8 s), else from `/_static/wheels/widgets/`.
5. Shims and patches (myst_nb.glue no-op; the matplotlib RcParams patch and
   font-cache warm-up only where matplotlib is wanted), then the page's init
   cells, then the `# autorun` chain. A cell failing with
   `No module named 'pyquist'` on a page that skipped it installs pyquist
   on demand and re-runs once.
6. The baked output stays on screen while the cell runs; the live output
   renders out of flow and the two are exchanged atomically once it exists
   (`stageOutputSwap`) — zero layout shift.

**Origins at a glance**

| Asset | Primary origin | Fallback | Cache key |
|---|---|---|---|
| Pyodide runtime + packages (~13–30 MB) | jsDelivr `pyodide/v0.27.7/full/` | `/pyodide/` | versioned path |
| plotly widget stack (~12 MB) | PyPI CDN, exact file URLs | `/_static/wheels/widgets/` | version-named files |
| `plotly.min.js` for baked figures (4.6 MB) | jsDelivr `plotly.js-dist-min@<ver>` | `/plotly-dist/` | versioned path |
| thebe + thebe-lite (2.7 MB, core patched) | self-hosted `/thebe-dist/` | — | 7-day cache |
| book wheels (1.7 MB) | self-hosted `/_static/wheels/` | — | version-named files |
| anywidget frontend (36 KB, patched) | self-hosted `/widgets-cdn/<hash>/` | — | content hash |

A cold plotly-only page now pulls ~25 MB (numpy + the widget stack + the
runtime), almost all of it from CDNs over HTTP/2; a pyquist page adds
matplotlib and friends (~15 MB). Repeat visits hit the browser cache.

**Cache-busting rules (a changed file must be a new URL)** — bump
`tools/icm_plotly/pyproject.toml` (and icm_widgets') whenever the module
changes: the kernel installs wheels by filename, and a same-named wheel was
served stale from browser caches once. The anywidget bundle is content-
hashed automatically. All `manifest.json` files are fetched `no-store`.
Sphinx adds `?v=<hash>` to `_static/*.js|css`. The deploy's `.htaccess`
(`deploy-scs.yaml`) marks version-named/hashed payloads `immutable` for a
year, the runtime mirrors 7 days, manifests `no-cache`, and gzips
wasm/json/js/css/html.

**Diagnosing**: `?icm-local` on a page URL forces every self-hosted copy,
`?icm-cdn` forces the CDNs without probing. In the kernel,
`micropip.list()[name].source`, `pyodide_js._api.config.indexURL` and
`pyodide_js.loadedPackages.to_py()` show where things came from; the
`[live-cells]` console lines name fallbacks.

### The version matrix (these move together — don't bump one alone)

| Pin | Where | Why |
|---|---|---|
| Pyodide **0.27.7** | `PYODIDE_VERSION` in `_static/live-cells.js` (jsDelivr URL) + `tools/vendor_pyodide.py` (mirror) | pyquist needs numpy ≥ 2; bundled pyodide_kernel 0.4.7 crashes on ≥ 0.28 |
| thebe-lite **0.5.0**, thebe **0.9.3** | `Makefile` (`vendor-thebe`) | newest released; embeds pyodide_kernel 0.4.7 |
| sphinx-thebe fork @ `1f3a809` | `environment.yml` | fork publishes no tags |
| soundfile stub | `tools/soundfile_stub/` | Pyodide < 0.28 ships no WASM soundfile |

Blocked upgrade: Pyodide 0.28 needs a thebe-lite release embedding
pyodide-kernel ≥ 0.6. When it ships: bump both in `vendor-thebe`,
`rm -rf vendor/thebe-dist`, bump `PYODIDE_VERSION` + `pipliteWheelUrl` in
`live-cells.js` and `VERSION` in `tools/vendor_pyodide.py` (then
`rm -rf vendor/pyodide`), delete the soundfile stub, smoke-test.

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
- **A widget page is slow or loads stale code** — measure the origin first
  (`curl -o /dev/null -w '%{time_starttransfer} %{speed_download}' <url>`);
  compare `?icm-cdn` vs `?icm-local` on the page; if a just-changed Python
  module behaves old in the kernel, its wheel version wasn't bumped (see
  Cache-busting rules).

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

deploy-scs also writes the site's `.htaccess` (404 page, URL redirects, and
the cache/compression policy from "Cache-busting rules"); every directive
block is guarded by `IfModule`, so a host without the module simply serves
as before. The SCS host is slow per request (seconds of first byte, tens of
KB/s), which is why the kernel payload comes from CDNs with the self-hosted
copies as fallbacks — keep both in sync when bumping versions.

## Layout

```
icm-text/    chapter prose (public pcm submodule, source of truth)
icm-f26/     course website (private submodule; mirrored to content/course/)
pyquist/     audio library (public submodule)
tools/       split/merge scripts, icm_anim, icm_widgets, browser stubs
content/     site sources — course/ + book/ (textbook, the /book URL tree),
             generated by `make split` (gitignored) except hand-authored
             pages and committed book/chNN/anim/ clips
_static/     book JS/CSS — custom.css, live-cells.{js,css}, wheels/ (generated:
             book wheels + wheels/widgets/ with manifests naming PyPI URLs)
_ext/        local Sphinx extensions — {audio}, figures, glossary, roles
vendor/      vendored thebe/Pyodide runtimes, plotly.min.js, hashed anywidget
             frontend (generated, gitignored) — the self-hosted fallbacks
_config.yml  Jupyter Book config
_toc.yml     table of contents (generated regions rewritten by make split)
Makefile     split / book / serve / pdf / merge / clean
```
