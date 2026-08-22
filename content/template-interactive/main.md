# Template - Interactive

This page is a **living template** for **interactive widget** sections —
pages where the reader drags sliders and a plotly figure answers, live, in
their browser. It is also a **tutorial**: by the end you should be able to
write a fun widget from scratch that looks native to the book.

Use it three ways:

1. **As a tutorial** — Section 2 is the quick start: the anatomy of a widget
   notebook and the steps from blank file to built page.
2. **As a starting point** — copy `notebooks/starter.ipynb` (Section 3) and
   grow it.
3. **As a worked example** — every cell on this page runs: Section 6 shows the
   same cell under all three visibility modes and Section 7 is a finished
   widget. Compare the page against its sources in
   `content/template-interactive/` (`main.md` plus the `notebooks/` folder).

:::{seealso}
For prose-only pages see the {doc}`Markdown template <../template-md>`; for
ordinary executable pages (code discussed *as code*, no widget) see the
{doc}`notebook template <../template-notebook>`; for **baked narrative
animations** (a video the page plays, no reader input) see the
{doc}`Animation template <../template-animation/index>`.
:::

## 1. How an interactive section works

A chapter's interactive section is authored as **two pieces, side by side**:

- the chapter's Markdown — the prose, with a one-line directive where the
  widget belongs:

  ````markdown
  :::{interactive}[notebooks/my-widget.ipynb]
  :::
  ````

- the companion notebook in the chapter's `notebooks/` folder — Markdown
  cells and code cells, written and tested like any notebook (VS Code's
  "Run All" is the fastest loop).

The split pipeline (`tools/split_chapters.py`) then emits the section as a
Jupyter notebook page: the surrounding prose becomes Markdown cells and the
companion notebook's cells are spliced in where the directive was. From
there, what the reader experiences:

1. **At build time** the cells execute (`execute_notebooks: auto`). Ordinary
   outputs — an audio card, a print — are baked into the HTML, and so is the
   widget's **figure**: `icm_plotly.show` runs only the `figure()` half and
   bakes the result as inert JSON. The sliders and their Python callback
   are *not* baked — a static page has no Python to run them on (and any
   ipywidgets model instantiated at build bakes megabytes of inert
   widget-state JSON instead).
2. **At page load** the baked figure renders **immediately** (the book's
   vendored plotly.js draws it — no kernel, no wait). Meanwhile, because
   the widget cell carries the `# autorun` marker, the live-code layer
   (`_static/live-cells.js`) **starts the in-browser Python kernel**
   (Pyodide + the book's packages, ~45 MB on a first visit — all served by
   the book itself, cached after, and pre-warmed in the background while
   the reader is on other pages);
   when it's up — roughly ten seconds on a fast connection — the sliders
   appear and the figure goes live. The reader never presses anything.
3. **On ▶ Run** any cell can be edited and re-run: the clicked cell's
   not-yet-run setup — the cells above it **from the same companion notebook
   only** (each is self-contained, so the rest of the page never runs on its
   behalf) — then the cell itself. Reloading the page restores the built
   page — that is the reset button. One caution: the page's notebooks all
   execute in **one shared Python kernel**, so their top-level names can
   collide — the capture rule in Section 2 exists because of this.

Because the same cells run at build, in the reader's browser, and in
VS Code, **write every cell against the browser kernel** (Section 4); the
build environment is a superset of it.

:::{note}
This page itself is built by that pipeline. Its sources live in
`content/template-interactive/`: `main.md` (the prose you are reading, plus
its `{interactive}` directives) and the `notebooks/` folder beside it.
`make template-interactive` expands them into the `index.ipynb` that
`_toc.yml` points at — the same expansion `make split` performs for chapter
sections. Edit the sources, regenerate, rebuild.
:::

## 2. Quick start: your first widget

Every widget notebook is the same **two cells** — learn this shape once and
every example on this page reads instantly:

1. **Dependencies** (`# hide` + `# no-output`) — the `%pip install` line
   (inside a `with capture_output():` block) and every import. Copy it
   verbatim from Section 4.
2. **The widget** (`# autorun`; add `# hide` when the code is beside the
   point) — a `figure()` that builds the visual and a `controls(fig)` that
   wires the sliders, handed to the book's plumbing:

   ```python
   def figure():
       fig = go.Figure()
       fig.add_scatter(x=t, y=y0, mode="lines")
       return fig

   def controls(fig):
       amp = widgets.FloatSlider(description="Amplitude", min=0, max=2, value=1)

       def update(a, y0=y0):
           fig.data[0].y = a * y0

       widgets.interactive_output(update, {"a": amp})

       out = widgets.Output()            # the audio card, always current
       pending = []

       def render():
           out.outputs = ()
           out.append_display_data(Audio(amp.value * y0, rate=sr, normalize=False))

       async def settle():
           await asyncio.sleep(0.25)
           pending.clear()
           render()

       def on_change(_):
           if pending:
               pending.pop().cancel()
           else:
               out.outputs = ()
           pending.append(asyncio.ensure_future(settle()))

       amp.observe(on_change, names="value")
       if not os.environ.get("ICM_BOOK_BUILD"):
           render()
       return widgets.VBox([amp, out])

   icm_plotly.show(figure, controls)
   ```

**The mental model.** `figure()` is the part that can exist without Python —
at build it runs once and the resulting figure is baked into the page, so
the reader sees it **the moment the page opens**. `controls(fig)` is the
part that can't: it receives the figure as a live plotly `FigureWidget`,
and its `update(...)` callback runs in **Python** on every slider move —
on the book page, that is the in-browser kernel that `# autorun` boots at
page load. When the kernel is up, the sliders appear and the baked figure
is swapped for the live one. Sound lives in `controls(fig)` too: an
audio card in a `widgets.Output` under the sliders that clears on the first
move of a drag and re-renders itself a moment after the sliders settle, so
whatever the reader plays is always the settings on screen. Importing `icm_plotly` also applies
the house figure style, so neither function contains styling code
(Section 5).

The rules of the pattern — each one earned by a real failure:

- **`figure()` returns a plain `go.Figure` and touches no ipywidgets** — it
  runs at build time, and any ipywidgets model instantiated there (a
  `FigureWidget` counts) bakes megabytes of dead widget-state JSON into the
  page. Everything slider-shaped lives in `controls(fig)`, which never runs
  at build.
- **Precompute outside, mutate inside** — arrays the callback needs are
  computed once at the top of the cell; `update(...)` only assigns to
  `fig.data[i].x/y` (and `marker.color` etc.), never rebuilds the figure.
  Wrap multi-trace updates in `with fig.batch_update():` so they repaint
  as one frame.
- **Capture what the callback reads** — snapshot every top-level name
  `update(...)` uses as a default argument: `def update(a, y0=y0):`. The
  callback fires long after its cell ran, and **all of a page's notebooks
  share one Python kernel** — self-contained means each runs on its own,
  not that its names are private. Without the capture, the moment another
  notebook on the page rebinds `t` or `y0`, the sliders silently compute
  from the wrong array (this page's starter once drew a flat line on the
  first drag because Section 7's widget had rebound `t` behind its back).
- **Fix the axes** — `fixedrange=True` and explicit ranges, so the view
  doesn't jump while data moves (the page hides plotly's toolbar; sliders
  are the interface).
- **Sound is a card that follows the sliders, not a cell and not a
  button** — put a `widgets.Output()` in `controls(fig)` and a `render()`
  that synthesizes from the sliders' `.value`s and writes the card through
  the Output's synced `outputs` trait: `out.outputs = ()` then
  `out.append_display_data(Audio(x, rate=sr, normalize=False))`
  (`IPython.display.Audio`, the element `pq.play` shows; the book's chip
  wraps it). `observe` every slider: the first change of a drag clears the
  card and a short `asyncio` timer, cancelled and rescheduled per change,
  re-renders it about 0.25 s after the last one. Call `render()` once at
  the end, guarded by `if not os.environ.get("ICM_BOOK_BUILD")` so the
  build bakes no card (the ghost reserves the card's height). The result:
  there is never a stale clip to press. A separate "hear it" cell makes
  the reader retype parameters, and a render button lets them play a clip
  that no longer matches the sliders. Two details earned by failures:
  write through the `outputs` trait, never `with out:` (that block only
  routes output while a kernel message is being handled, and the timer
  fires outside one); and scale the signal yourself, since the card is
  built with `normalize=False` (`x *= 0.125 / abs(x).max()` is about
  -18 dBFS, `pq.play`'s own safe ceiling; `0.125 * a` when loudness itself
  is the lesson). Needs `import asyncio`, `import os`, and
  `from IPython.display import Audio` in the dependencies cell.

From blank file to built page:

1. **Copy the starter** — `notebooks/starter.ipynb` (rendered in Section 3) —
   into your chapter's `notebooks/` folder and rename it
   (`notebooks/my-widget.ipynb`).
2. **Get the figure right first** — layout, ranges, axis labels with units,
   palette colors — before wiring any slider.
3. **Add the sliders and the `update`** — precompute what you can outside
   `update`; the callback should be cheap enough to run on every drag tick.
4. **Add sound where it earns its place** — the self-refreshing audio
   card in `controls(fig)` (the rule above; Section 7's demo has one)
   always plays the current settings.
5. **Mark the cells** (Section 6) — `# hide` + `# no-output` on the setup
   cell; `# autorun` on the widget cell (its baked output *is* the figure —
   no `# no-output` there), plus `# hide` if readers shouldn't see the code.
6. **Test the notebook on its own** — "Run All" in VS Code; drag every
   slider.
7. **Drop the directive into the prose** where the widget belongs, with a
   lead-in paragraph above and a "try changing…" prompt below:

   ````markdown
   :::{interactive}[notebooks/my-widget.ipynb]
   :::
   ````

8. **Regenerate and build** — `make split` emits the section notebook (for
   this template page it is `make template-interactive`), then `make book`;
   open the built page and watch the widget arrive on its own.

If something looks wrong on the page, check Section 8 — the common mistakes
all have one-line fixes.

## 3. A minimal starter

The whole pattern at its smallest — one hidden setup cell, one widget cell
(code left visible here on purpose). The figure below is on screen from the
moment the page opened; the sliders arrive when the kernel does. This is
the file the quick start copies. Drag the sliders, or edit the cell and
**▶ Run** it:

:::{interactive}[notebooks/starter.ipynb]
:::

## 4. The libraries a widget may use

| Library | What it powers | At build | In the browser |
| ------- | -------------- | -------- | -------------- |
| `numpy` | arrays, signal math | ✓ | ✓ preloaded (Pyodide build) |
| `plotly`, `anywidget`, `ipywidgets` | the `FigureWidget` + sliders | ✓ (conda) | ✓ auto-installed when the page's code uses them |
| `icm_plotly` | the house figure style, the palette, and `show()` (Sections 2, 5) | ✓ | ✓ self-hosted wheel, installed at kernel start |
| `pyquist` (`pq`) | `pq.Audio`, `pq.play(...)` → the book's audio card | ✓ | ✓ self-hosted wheel, installed at kernel start |
| `browseraudio` | `pq.record(...)` microphone capture | – | ✓ auto-installed when the page's code uses it |
| `soxr`, `requests`, `tqdm` | pyquist's dependencies | ✓ | ✓ preloaded |
| `soundfile` / `sounddevice` | WAV I/O, playback plumbing | real | stub wheels (WAV only; playback renders as an audio card) |

Two conventions keep the same cell runnable in both environments:

- Install with `%pip install -q plotly anywidget` **inside a
  `with capture_output():` block**, so pip's chatter stays off the page while
  a genuine install failure still raises loudly. Do **not** wrap the whole
  cell in a bare `%%capture` — it swallows the traceback too, and a
  silently-failed setup resurfaces cells later as a baffling `NameError`.
  The install is a no-op wherever the packages already exist (both
  environments) and documents what the notebook needs. Two packages are
  deliberately **not** in the install line: `icm_plotly` and `pyquist` ship
  with the book (the build uses the repo's editable installs and the browser
  pre-installs the book's own wheels, so a PyPI fetch would fight both).
- Import everything in that one cell, `# hide` + `# no-output` it
  (Section 6), and let the teaching cells stay free of plumbing.

The standard first cell, in full:

```python
# hide
# no-output
from IPython.utils.capture import capture_output
with capture_output():
    %pip install -q plotly anywidget

import numpy as np
import plotly.graph_objects as go
import ipywidgets as widgets
import pyquist as pq
import icm_plotly
from icm_plotly import RED, GOLD, STEEL
```

Every companion notebook on this page opens with a cell like it — that is
what keeps each one runnable on its own ("Run All" in VS Code) *and* lets
the notebooks run in any order on the page.

## 5. The house style

Widgets should look like the book drew them, and the styling is not the
author's job: **importing `icm_plotly` registers the book's "icm" plotly
template and makes it the default** — open spines in iron gray, outside
ticks, no grid, white figure surfaces, the palette as the colorway, and the
zoom/select tools trimmed (the page hides the toolbar entirely; sliders are
the interface). A widget cell contains no styling code at all.

Color is meaning. The palette imports from `icm_plotly` (re-exported from
its single source of truth, shared with the book's manim animations) —
Carnegie red is both the university's color and the book's accent, so a
widget colored this way reads as part of the course:

| Swatch | Hex | Role |
| ------ | --- | ---- |
| <span style="color:#C41230">■</span> Carnegie red | `#C41230` | the primary object — the thing being built or measured |
| <span style="color:#007BC0">■</span> Highlands blue | `#007BC0` | a contrasting second series |
| <span style="color:#FDB515">■</span> gold thread | `#FDB515` | the moving part — a probe, the newest addition |
| <span style="color:#6D6E71">■</span> iron gray | `#6D6E71` | a composite or total signal |
| <span style="color:#008F91">■</span> teal thread | `#008F91` | a second component when red and blue are taken |
| <span style="color:#E0E0E0">■</span> steel gray | `#E0E0E0` | static guides: reference curves, unit circles |

Layout conventions, all visible in the demo widget below:

- **Two panels via `make_subplots`** when the widget shows a thing and its
  recipe side by side; weight the panels with `column_widths`.
- **Label everything** — axes carry units (`"Time (ms)"`, `"Amplitude"`);
  the slider's `description` is the moving quantity's name.
- **Fixed ranges** on every axis (Section 2's rules) — the data moves, the
  frame doesn't.
- **Sliders above the figure** — `controls(fig)` returns a
  `widgets.VBox([…sliders…, out])`, which the page displays above the
  figure, where the reader's eye lands first; the panel's card, equal
  slider tracks, and audio-card styling come from `live-cells.css` and
  `icm_plotly`, never from the notebook.

## 6. Hide, collapse, show — and autorun

Every code cell in a companion notebook chooses how much of itself the page
shows, with a whole-line marker:

| Marker | On the page | Use it for |
| ------ | ----------- | ---------- |
| `# hide` | source removed entirely; the output stands alone as native page content (no `output` tag) | boilerplate — or a widget whose code is beside the point |
| `# collapse` | source behind a collapsed **Show setup** bar | setup a curious reader might expand: constants, helpers |
| `# show` (or no marker) | source visible and editable | the code you are teaching |
| `# no-output` (additional) | the cell's **baked output** is dropped from the page (it still runs, at build and in the browser) | setup cells — and any kernel-only cell whose output is dead page weight. NOT the widget cell: its baked output is the figure |
| `# autorun` (additional) | the live layer runs the cell (and its setup chain) **on page load** — the baked figure holds the spot while the kernel boots | every widget cell: the sliders arrive without the reader pressing ▶ Run |

The marker must be a line of its own (conventionally the first line of the
cell), it is case-insensitive, and the first one wins. It is an ordinary
comment: the split pipeline reads it to tag the cell (`# hide` →
`icm-hide-input`, `# collapse` → `hide-input`) and leaves the line in
place — expand any **Show setup** bar on this page and the `# collapse`
that put it there is the first thing you read, and a cell copied off the
page keeps its behavior in your own notebook. By convention visible cells
carry no marker: `# show` exists, but visible is the default. Hidden and
collapsed cells still **run**, both at build time and in the browser —
when a student runs a visible cell, the setup cells above it execute
first, in order.

To see the modes side by side, the rest of this section embeds
`notebooks/three-modes.ipynb`: the **same cell three times** — it renders
half a second of the 220 Hz sawtooth the widget in Section 7 builds, as the
book's audio card — and nothing differs between the copies but the marker
line. (The notebook also opens with a hidden setup cell, which outputs
nothing.) The mode labels below are Markdown cells inside that notebook,
rendered as prose.

:::{interactive}[notebooks/three-modes.ipynb]
:::

## 7. The demo widget

Now the payoff: a full widget in the house style, from
`notebooks/harmonics-builder.ipynb`. Its dependencies cell is hidden; the
widget cell's code is visible on purpose — in a chapter you would usually
add `# hide` (Section 5.2 of the book, "The phasor", is this pattern in the
wild with the code hidden, so only the widget shows).

:::{interactive}[notebooks/harmonics-builder.ipynb]
:::

Try it live: change `f0` to 110 in the widget cell and press **▶ Run**, or
flip the recipe to odd harmonics only (a square wave) with
`k = np.arange(1, 2 * n_max, 2)` — then press play on the card under the
slider to hear the difference.

## 8. When something looks wrong

| Symptom | Cause and fix |
| ------- | ------------- |
| pip chatter printed on the page | The `%pip install` line isn't inside the `with capture_output():` block |
| Code shows on the page that shouldn't | The marker isn't on a whole line of its own, or isn't the cell's first line |
| The widget is missing from the built page | The directive path doesn't match the notebook, or you edited the generated `.ipynb` instead of the source and re-split |
| No figure at page load | The widget cell carries `# no-output` (which strips the baked figure), or `make wheels` hasn't vendored plotly.js (`vendor/plotly-dist/`), or `figure()` raised at build — check the build log |
| The figure shows but the sliders never arrive | The widget cell is missing its `# autorun` marker — without it the reader must press ▶ Run for the live upgrade |
| The page bakes megabytes of inert widget-state JSON | ipywidgets (a `FigureWidget` counts) leaked into `figure()` or the top of the cell — everything slider-shaped goes inside `controls(fig)`, which never runs at build |
| The sliders take a while to arrive | Expected only on a first visit — the kernel + packages are ~45 MB, served by the book itself, downloaded once, cached, and pre-warmed while the reader is on other pages; the figure is already on screen and the status pill bottom-right shows progress |
| A slider draws garbage after another widget on the page has run, and re-running its own cell cures it | The callback reads a top-level name (`t`, `y0`, …) that another notebook on the page rebound — every notebook shares the one kernel. Capture the name as a default argument: `def update(a, f, t=t):` (Section 2's capture rule) |
| The audio card plays at the same loudness whatever the amplitude slider says | The card is built with `normalize=False`, so scale the signal yourself: `0.125 * a` keeps full amplitude at -18 dBFS |
| The card clears on a drag but never comes back | `render()` writes with `with out:`; write through the Output's `outputs` trait (`out.outputs = ()` then `append_display_data`), which works from the timer task |
| The whole widget vanishes once `controls()` returns an `Output` | The empty-output rule in `live-cells.css` must read `:has(> .jp-OutputArea:empty)` (the cell's own area only); an `Output` widget renders a nested area that the unscoped form mistook for "this cell printed nothing" |
| Slider drags feel laggy | The `update` callback is doing real work per tick — precompute arrays outside it and only assign precomputed data (see the demo's `sums`/`partials`) |
| The figure repaints in visible stages | Multiple trace assignments per tick — wrap them in `with fig.batch_update():` |
| `ModuleNotFoundError: icm_plotly` on your own machine | Outside this repo it isn't installed — `pip install -e tools/icm_plotly tools/icm_widgets`; never add them to the `%pip` line |

:::{admonition} Before publishing
:class: warning
Remove this **Interactive Template** page from `_toc.yml` — it is an author
reference, not course content.
:::
