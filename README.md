# CMU Intro to Computer Music

Source for **CMU Intro to Computer Music**, the 15-322 / 15-622 textbook at Carnegie
Mellon University, built with [Jupyter Book](https://jupyterbook.org).

Two pinned git submodules keep builds reproducible:

- **`icm-text/`** — ground-truth chapter prose (a private fork). `make split`
  derives the rendered chapters under `content/ch*/` from it.
- **`pyquist/`** — the course audio library
  ([`gclef-cmu/pyquist`](https://github.com/gclef-cmu/pyquist)); the Pyquist
  Overview and API pages are generated from it.

## Build

```sh
git clone --recurse-submodules <repo-url>
# already cloned? plain builds need only the public pyquist submodule:
git submodule update --init pyquist

conda env create -f environment.yml   # first time (installs pyquist from ./pyquist)
conda activate icmbook

make book      # build HTML into _build/html/
make serve     # build + serve at http://localhost:8000
make pdf       # PDF build (needs a LaTeX toolchain)
make clean     # remove build outputs
```

Every `make` target assumes the `icmbook` env is active — it provides
`jupyter-book` and the `python` that `make serve` uses.

After **creating or recreating** the env, force-install the TeachBooks
sphinx-thebe fork (same name/version as upstream, so the env solver silently
keeps upstream — see **The fork trap** under Live code). `make book` checks
this and prints the exact command if it's missing.

`make book` reads the **committed** `content/`, so it doesn't need `icm-text/`.
You only need that (private) submodule to run `make split` / `make merge`.

## Authoring

The book is written in **MyST-native Markdown**. For a live reference of every
directive and feature — admonitions, margin notes, definitions, figures, audio,
citations — see **`content/template-md.md`** (prose) and
**`content/template-notebook.ipynb`** (runnable code, audio, plots).

Each chapter is a folder `content/chNN/` with one file per section (`00.md`,
`01.md`, …); the section number lives in each H1 (e.g. `# 1.2 …`).

## Chapter prose: `icm-text` → `content/`

Chapter prose lives in the **`icm-text/`** submodule (the source of truth).
`make split` regenerates the rendered chapters from it:

```sh
git submodule update --remote icm-text   # pull the latest prose
make split                               # regenerate content/ch*/ and _toc.yml
git add content/ && git commit && git push
```

`content/ch*/` is **committed** to this repo — the build and CI read those files
directly and never fetch the private `icm-text/`. So after a split, commit the
regenerated `content/` for changes to reach the deploy.

`{animation}` clips render during the split, not the build: the splitter runs
each changed companion under manim once and writes small crf-28 mp4s into
`content/chNN/anim/` (commit those too). Unchanged clips are reused
byte-for-byte via the content hash in their filenames, so a split only needs
the authoring stack (`pip install manim==0.20.1 && pip install -e
tools/icm_anim`, plus TeX for `MathTex`) when a scene actually changed.

`make merge` is the inverse: it re-assembles `content/ch*/` into icm-text-shaped
files (under `icm-text-merged/`) for PR'ing edits upstream, and self-checks that
the rendered site is unchanged.

## Pyquist docs

Everything the book shows about Pyquist is generated from the pinned `pyquist/`
submodule — there are no hand-written API docs:

- `content/pyquist/Overview.md` mirrors `pyquist/README.md` (refreshed each build).
- `content/pyquist/api/*.md` are autodoc shells that introspect the **installed**
  module — the editable install (`-e ./pyquist`) that `conda env create` performs,
  not the `pyquist/` folder itself. If the import fails at build time, these pages
  silently render empty (see Troubleshooting).

Bump the pinned version and push to update:

```sh
git submodule update --remote pyquist
git add pyquist && git commit -m "Bump pyquist" && git push
```

## Live code (in-browser Python)

Notebook pages are **live**: every code cell is an editor the moment the page
opens, and a ▶ Run chip (or Shift-Enter) executes it — Python runs entirely in
the browser via [Pyodide](https://pyodide.org), no server, no Binder. The page
renders exactly like the static build (baked outputs stay until a cell re-runs;
running a cell first runs the not-yet-run cells above it). Prose pages load
none of this.

### How it's achieved

The pipeline has three stages — two at build time, one in the browser:

1. **`make book` builds the runtime artifacts** (both targets are `book`
   prerequisites and run automatically):
   - `make wheels` → `_static/wheels/` + `manifest.json`: a pyquist wheel from
     the pinned submodule, plus two stand-ins from `tools/`: a **sounddevice
     stub** (PortAudio can't exist in WASM; raises a friendly error) and a
     **soundfile stub** (WAV-only via stdlib `wave`; temporary, see below).
     Rebuilt every build so the wheel always matches the submodule pin.
   - `make vendor-thebe` → `vendor/thebe-dist/`: downloads the pinned
     **thebe-lite 0.5.0** and **thebe 0.9.3** npm bundles (the in-browser
     Jupyter server + frontend). Self-hosted because the kernel web worker
     must be **same-origin** — a CDN copy is blocked by the browser. Served
     verbatim via `html_extra_path` (`_config.yml`); it must **never move into
     `_static/`**, where Jupyter Book auto-registers every `.js` as a page
     script and would execute worker-only chunks on page load. Cached behind a
     `.ok` sentinel; `rm -rf vendor/thebe-dist` forces a re-fetch.
2. **Page load — editors, no kernel** (`_static/live-cells.js`): on pages with
   code cells it adds Run chips, restyles outputs (audio → the book's chip
   cards), and at browser idle loads the thebe core bundle and mounts a
   CodeMirror editor into every cell, pixel-matched to the static `<pre>`
   (`_static/live-cells.css`). The kernel does **not** start: bootstrap's
   server connection is parked on a gated `window.thebeLite` stand-in.
3. **First Run — kernel**: loads the thebe-lite server bundle, injects the
   pinned Pyodide URL + self-hosted kernel-wheel URLs (this *must* happen by
   wrapping `startJupyterLiteServer` — thebe forwards no lite config, and
   thebe-lite overwrites the page-level `litePluginSettings`), then releases
   the gate. Pyodide boots in a web worker (~25 MB from the CDN, first visit
   only), the wheels install in manifest order (stubs first, so micropip never
   fetches the real sounddevice/soundfile from PyPI), and the run executes.
   Reload = reset; a floating badge shows kernel state.

The TeachBooks **sphinx-thebe fork** (pinned by commit in `environment.yml`)
supplies the page glue (`text/x-thebe-config` tag, helper script). It has the
same dist name/version as upstream, so pip needs
`--force-reinstall --no-deps` to replace an already-installed upstream copy.

### The version matrix (why each pin exists)

| Pin | Where | Why |
|---|---|---|
| Pyodide **0.27.7** | `pyodideUrl` in `_static/live-cells.js` | pyquist needs numpy ≥ 2 (so Pyodide ≥ 0.27); the bundled pyodide_kernel **0.4.7 crashes on ≥ 0.28** |
| thebe-lite **0.5.0**, thebe **0.9.3** | `Makefile` (`vendor-thebe`) | newest released; embeds pyodide_kernel 0.4.7 (the piplite wheel URL in live-cells.js carries that version too) |
| sphinx-thebe fork @ `1f3a809` | `environment.yml` | fork publishes no tags |
| soundfile stub | `tools/soundfile_stub/` | Pyodide < 0.28 ships no WASM soundfile; PyPI's pure-Python one needs a native lib |

These move **together** — don't bump one alone. The blocked upgrade: Pyodide
0.28 (real soundfile, mp3 decode) needs a thebe-lite release embedding
jupyterlite pyodide-kernel ≥ 0.6. When that ships:

1. Bump both versions in `Makefile` `vendor-thebe`; `rm -rf vendor/thebe-dist`.
2. In `_static/live-cells.js`: bump `pyodideUrl`, and match `pipliteWheelUrl`
   to the piplite wheel inside the new bundle (`vendor/thebe-dist/lite/pypi/`).
3. Delete `tools/soundfile_stub/` and its line in the `wheels` target.
4. `make serve` and smoke-test (below) — expect `Audio.from_file` to handle
   mp3 now.

### Maintaining / testing

- Routine builds need nothing: wheels track the pyquist pin automatically;
  vendor bundles are cached (first build fetches them from npm).
- **The fork trap**: the TeachBooks fork shares upstream's dist name *and*
  version, so a fresh `conda env create` silently keeps upstream sphinx-thebe
  (conda's jupyter-book pulls it in; pip skips the git pin as satisfied) —
  this shipped a broken deploy once (live code crashed on a JS-literal config
  tag). Guards now: `make book` refuses to build with upstream
  (`check-thebe-fork`, prints the fix), the deploy workflow force-installs
  the fork, and `live-cells.js` parses either tag format as a last resort.
  After recreating a local env, run the `pip install --force-reinstall
  --no-deps "sphinx-thebe @ git+…"` command from `environment.yml`.
- **Smoke test** after touching any of this: `make serve`, open
  `http://localhost:8000/content/template-notebook.html` (must be `http://` —
  the worker won't start from `file://`). Check: cells are editable
  immediately with no layout shift; ▶ Run on the `pq.play(tone)` cell boots
  the kernel (badge: "● Python connected") and replaces the baked output with
  a working audio card.
- **Microphone recording (§4 of the template, "Record your own audio").**
  `pq.record(duration)` captures from the mic in the browser via the
  [browseraudio](https://pypi.org/project/browseraudio/) package (a small
  anywidget Web Audio bridge). `record()` **auto-detects the runtime** (via
  `device._in_browser()`, which checks `sys.platform == "emscripten"`): in the
  browser it delegates to browseraudio, and everywhere else it is the native
  PortAudio path — no flag. Either way it **returns an `Audio`** (so
  `record()`'s `-> Audio` contract holds): in the browser it shows a Record
  button and returns an `Audio` immediately that is filled in place when the
  user clicks Record (a kernel-idle widget-comm message). `live-cells.js`
  installs browseraudio **lazily from PyPI** — only on pages whose code
  mentions `pq.record` or `browseraudio` — so prose/plotting pages don't pull
  anywidget. Usage is two cells: `clip = pq.record(3)` + click Record, then
  read `clip` (now filled) in the next cell. The capture is interactive, so the
  `Audio` is empty until the click — a blocking `record()` that returns the
  finished audio in one call is impossible here (verified: `await` and
  `run_sync` both hang, since the worker kernel can't process the recording
  while a cell is blocked waiting for it).
  **Deploy dependency:** in-browser recording ships in the pyquist
  `browser-recording` branch, which the deploy fetches via
  `git submodule update --init --remote pyquist` (`.gitmodules` pins
  `branch = browser-recording`). That branch must be pushed to
  gclef-cmu/pyquist; revert `.gitmodules`/`deploy-book.yml` to a plain pinned
  `--init` once it merges to `main`.
- **Unsupported operations must fail clearly, not silently.** §5 of the
  template notebook ("Browser limits") is the deliberate test surface — four
  `skip-execution` cells that each Run into a clear error in the browser:
  reading an MP3 and writing a non-WAV file raise `LibsndfileError` ("…WAV
  only…"); `pq.play(..., force_sounddevice=True)` and `sd.query_devices` raise
  `PortAudioError` ("…needs a sound card…"). (`pq.record` is no longer here —
  it auto-detects the browser and records via the Web Audio API; see §4.) The
  messages live in the browser stubs (`tools/soundfile_stub/`,
  `tools/sounddevice_stub/`), **not** pyquist — no pyquist change is needed to
  keep them clear. If you add a pyquist call that touches the filesystem or a
  device, add a matching §5 cell and confirm the message reads well. (These
  cells are `skip-execution` so the build neither runs them — which would fail
  CI or bake a misleading success — nor leaves them un-runnable live.)
- The editors are **CodeMirror 5**; their look (and scroll behavior) is
  pixel-matched against the built static page in `live-cells.css` — if the
  theme or pygments style changes, re-measure. Output styling lives in
  `custom.css` ("response rail") and fights some `!important` rules in the
  fork's `code.css`; keep both in view when restyling outputs.
- `thebe_config.exclude_patterns` in `_config.yml` keeps book sources (and
  dotfiles — `**` alone misses `.git/`!) out of `_build/html`. Don't loosen it.

## Color palette

One palette serves prose, figures, widgets, and animations. Tools should
import the named constants (from `icm_widgets` / `icm_anim`), never paste hex
codes.

| Name | Hex | Use |
|---|---|---|
| RED | `#C41230` | Carnegie red — primary accent, links |
| BLUE | `#007BC0` | plot series |
| GOLD | `#FDB515` | plot series, accents |
| TEAL | `#008F91` | plot series |
| IRON | `#6D6E71` | iron gray — muted accents |
| STEEL | `#E0E0E0` | light strokes / fills |
| INK | `#3B3B3B` | figure/animation text on light pages |
| INK_DARK | `#ECECEC` | figure/animation text on dark pages |
| page (light) | `#FFFFFF` | `--pst-color-background`; baked into animations (`icm_anim._PAGE`) |
| page (dark) | `#101010` | `--pst-color-background` override in `custom.css`; baked into animations (`icm_anim._PAGE_DARK`) |

Source of truth: `RED…STEEL` live in `tools/icm_widgets/icm_widgets.py`
(re-exported by `icm_anim`); the page backgrounds live in `_static/custom.css`
and `tools/icm_anim/icm_anim.py` and **must stay in sync**.

The dark page color is `#101010`, not the theme's stock `#121212`, because
animations bake the page color into H.264 video and grey 18 has no exact code
in limited-range YUV — it always decodes one step darker (grey 16 round-trips
exactly; so do 15, 17, 22, while 18–21 do not). For the same reason `icm_anim`
stamps sRGB color metadata into every clip (`_tag_srgb`): browsers disagree on
how to decode untagged video — Safari gamma-shifts every color, and at 720p
Chrome/Firefox assume a bt709 matrix while the encoder uses bt601, drifting
saturated colors. If the dark background ever changes, pick a grey that
round-trips through video and update both definitions.

## Troubleshooting

- **`make: jupyter-book: No such file or directory`** — the `icmbook` conda env
  isn't active. Run `conda activate icmbook` (create it first if needed; see
  Build).

- **Pyquist API pages build, but show no classes or functions** — autodoc
  imports `pyquist` from the environment, and a failed import doesn't fail the
  build. The editable install records an **absolute path**, so it goes stale if
  the repo is moved or re-cloned. Check it, then re-point and rebuild:

  ```sh
  python -c "import pyquist; print(pyquist.__file__)"
  # healthy: a path inside this repo's pyquist/pyquist/
  # stale:   None, an ImportError, or a path elsewhere

  pip install -e ./pyquist
  make clean && make book   # clean first — Sphinx caches the empty pages
  ```

- **Notebook build fails with `module 'pyquist' has no attribute 'Audio'`**
  (or baked outputs vanish) — a notebook executed with its CWD set to a
  directory that contains a `pyquist/` subdir (the repo root, or `content/`
  with its `content/pyquist/` docs), so `import pyquist` resolved to that
  empty namespace directory instead of the editable install (setuptools'
  editable finder sits after `PathFinder` on `sys.meta_path`, so CWD wins).
  Fixed by `execute: run_in_temp: true` in `_config.yml` (notebooks run in a
  temp dir with no sibling `pyquist/`); leave it on.

- **Live code crashes with `Expected property name or '}' in JSON`** — that
  site was built with **upstream** sphinx-thebe instead of the TeachBooks
  fork (see "The fork trap" under Live code). Force-install the fork and
  rebuild/redeploy; current `live-cells.js` also tolerates the upstream tag,
  so a redeploy fixes it even before the env is corrected.

- **Live code: cells never become editable, or Run hangs at "Starting
  Python"** — open the browser console and look for `[live-cells]` lines,
  then check in order: the page is served over `http://` (not `file://`);
  a stale `python -m http.server` isn't serving an old build; hard-reload
  (the JupyterLite service worker caches kernel files); `vendor/thebe-dist/`
  isn't half-fetched (`rm -rf vendor/thebe-dist && make book`). First-ever
  Run downloads ~25 MB from the Pyodide CDN — give it time on slow networks.

## Deploy

Pushing to `main` triggers `.github/workflows/deploy-book.yml`, which builds and
deploys to GitHub Pages. CI fetches only the public `pyquist/` submodule (over
HTTPS) and builds from the committed `content/` — it never runs `make split` or
fetches `icm-text/`, and it never renders animations (no manim or TeX Live in
CI; the committed `content/**/anim/` mp4s are served as-is). Because CI runs
`make book`, the live-code artifacts (wheels, vendored thebe bundles from the
npm registry) are built there too — nothing live-code-related is committed
except the sources under `tools/` and `_static/`.

## Layout

```
icm-text/    chapter prose (private submodule, source of truth)
pyquist/     audio library (public submodule)
tools/       split_chapters.py / merge_chapters.py + browser-kernel stubs
             (sounddevice_stub/, soundfile_stub/ — see Live code)
content/     rendered book — chNN/, appendix/, pyquist/, reference/, templates
_static/     book JS/CSS — custom.css, audio-chip.js, live-cells.{js,css}
             (live code), wheels/ (generated, gitignored)
_ext/        local Sphinx extensions — {audio}, figures, glossary, roles
vendor/      thebe runtime bundles (generated by make vendor-thebe, gitignored)
_config.yml  Jupyter Book config
_toc.yml     table of contents
Makefile     book / serve / pdf / clean / split / merge / wheels / vendor-thebe
```
