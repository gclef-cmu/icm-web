"""House plotly styling and page plumbing for interactive widget cells.

Importing this module registers the book's "icm" plotly template and makes it
the default, so widget cells never carry styling blocks. `show(build)` is the
one display path: it runs the cell's widget-building function everywhere
except the book build, where instantiating any ipywidgets model would bake
inert multi-MB widget-state JSON into the page.

Ships with the book: installed in the build environment (environment.yml) and
in the browser kernel (_static/wheels via `make wheels`), so notebook cells
never pip-install it.
"""

import os

import plotly.graph_objects as go
import plotly.io as pio

# The palette's single source of truth is icm_widgets (icm_anim shares it);
# re-exported here so widget cells import one module. icm_widgets ships
# everywhere this module does (wheels manifest + environment.yml).
from icm_widgets import BLUE, GOLD, IRON, RED, STEEL, TEAL  # noqa: F401

__all__ = ["show", "RED", "BLUE", "GOLD", "IRON", "TEAL", "STEEL"]

# House axis look: single grey spine, outside ticks, no grid — the plotly
# counterpart of the matplotlib house style.
_AXIS = dict(
    showline=True,
    linecolor="#6D6E71",
    linewidth=1,
    ticks="outside",
    tickcolor="#6D6E71",
    tickfont=dict(color="#3b3b3b"),
    title_font_color="#3b3b3b",
    title_font_size=12,
    title_standoff=12,
    zeroline=False,
    mirror=False,
    showgrid=False,
)

pio.templates["icm"] = go.layout.Template(
    layout=go.Layout(
        font=dict(size=12, color="#3b3b3b"),
        margin=dict(l=50, r=50, t=50, b=50),
        # Off by default: the widgets' traces are color-coded and hover
        # shows names; plotly's legends clip or overlap in narrow columns.
        # A figure that opts back in (showlegend=True) gets a horizontal
        # legend above the plot, clear of the right margin.
        showlegend=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1),
        xaxis=_AXIS,
        yaxis=_AXIS,
        xaxis2=_AXIS,
        yaxis2=_AXIS,
        plot_bgcolor="white",
        paper_bgcolor="white",
        # Zoom/select tools are pointless on fixedrange widget axes; the book
        # pages hide the whole modebar via CSS, this trims it elsewhere.
        modebar=dict(remove=["zoom", "select2d", "lasso2d", "autoScale2d"]),
        colorway=[
            "#C41230",  # carnegie red
            "#C41230",  # carnegie red (2x)
            "#007BC0",  # highland blue
            "#FDB515",  # gold thread
        ],
    )
)
pio.templates.default = "icm"


def _normalize_controls(ui):
    """Give every labeled control the same geometry.

    A fixed label width keeps all slider tracks the same length no matter
    how long their descriptions are (description_width="initial" sizes the
    label to its text, so tracks end up unequal). 170px fits the longest
    description in the book; the row is fluid below one house max width.
    """
    stack = [ui]
    while stack:
        w = stack.pop()
        stack.extend(getattr(w, "children", ()))
        style = getattr(w, "style", None)
        if getattr(w, "description", "") and hasattr(style, "description_width"):
            w.style.description_width = "170px"
            w.layout.width = "100%"
            w.layout.max_width = "460px"


# plotly.py's FigureWidget frontend falls back to this height when the layout
# sets none; the baked figure uses the same value so the live swap moves
# nothing on the page.
_WIDGET_DEFAULT_HEIGHT = 360


def show(figure, controls=None):
    """Render a widget everywhere it can exist — including the static page.

    ``figure()`` builds the visual: a plain ``go.Figure`` (never a
    FigureWidget, never ipywidgets — anything ipywidgets opens at build
    time bakes inert multi-MB widget-state JSON into the page).
    ``controls(fig)`` receives the live ``go.FigureWidget``, wires sliders
    to it, and returns the control widget to display above it.

    At book build ``figure()`` runs and is baked into the page as inert JSON
    that live-cells.js renders with the book's vendored plotly.js the moment
    the page opens — no kernel, no wait. ``controls()`` runs once too, with
    ipywidgets' comm channel switched off so nothing reaches the page, only
    to render a same-size inert stand-in ("ghost") of the controls above the
    figure. On the live page (the ``# autorun`` marker boots the kernel) and
    in VS Code, the same figure becomes a FigureWidget with the controls
    wired, replacing ghost and baked figure in place.
    """
    if os.environ.get("ICM_BOOK_BUILD"):
        from IPython.display import HTML, display

        fig = figure()
        if fig.layout.height is None:
            fig.update_layout(height=_WIDGET_DEFAULT_HEIGHT)
        ghost = _ghost_controls(fig, controls) if controls is not None else ""
        # `</` escaped so the JSON can't close its own script tag. The
        # figure's height is reserved up front so the page doesn't grow
        # when plotly.js arrives and draws.
        payload = fig.to_json().replace("</", "<\\/")
        # data-plotlyjs: the exact plotly.js this figure was built for, so
        # live-cells.js can load that version from a CDN (falling back to
        # the book's vendored copy of the same file).
        from plotly.offline import get_plotlyjs_version
        display(HTML(
            '<div class="icm-widget-baked">' + ghost
            + f'<div class="icm-plotly-fig" style="min-height:{fig.layout.height}px"'
            f' data-plotlyjs="{get_plotlyjs_version()}">'
            '<script type="application/vnd.icm-plotly+json">'
            + payload + "</script></div></div>"
        ))
        return
    from IPython.display import display

    fig = go.FigureWidget(figure())
    # _config is private but synced to the frontend by design; responsive
    # turns on plotly.js's ResizeObserver so the figure reflows with its
    # container instead of clipping when the window narrows.
    fig._config = dict(fig._config or {}, responsive=True)
    ui = controls(fig) if controls is not None else None
    if ui is None:
        display(fig)
    else:
        _normalize_controls(ui)
        display(ui, fig)


def _ghost_controls(fig, controls):
    """Inert HTML stand-in for ``controls(fig)``, built at page build.

    Runs ``controls()`` once against a FigureWidget with ipywidgets' comm
    channel switched off: no model is opened toward the build frontend, so
    nothing gets baked, and the returned widget tree can be walked for its
    labels, values and layout. A failure only costs the ghost.
    """
    import gc
    import warnings

    from ipywidgets.widgets.widget import Widget

    real_open = Widget.open
    Widget.open = lambda self: None
    try:
        ui = controls(go.FigureWidget(fig))
        _normalize_controls(ui)
        markup = _ghost_html(ui)
    except Exception as exc:  # noqa: BLE001
        warnings.warn(f"icm_plotly: controls() failed at build, no ghost controls: {exc!r}",
                      stacklevel=2)
        markup = ""
    finally:
        Widget.open = real_open
        gc.collect()  # free the comm-less widgets now, not at kernel teardown
    return markup


def _ghost_html(w):
    """Markup for one widget, recursing through boxes.

    Same boxes and text as @jupyter-widgets/controls (28px rows, 2px margins,
    300px wide, 80px label unless description_width says otherwise, 72px
    readout), styled by live-cells.css, so the real controls land in place.
    """
    import html as _html
    import math

    import ipywidgets as widgets

    esc = _html.escape
    if isinstance(w, widgets.Box):
        orient = "hbox" if isinstance(w, widgets.HBox) else "vbox"
        inner = "".join(_ghost_html(c) for c in w.children)
        return f'<div class="icm-ghost-box icm-ghost-{orient}">{inner}</div>'

    desc = getattr(w, "description", "") or ""
    width = getattr(getattr(w, "style", None), "description_width", "") or ""
    style = f' style="width:{esc(width)}"' if width else ""
    label = f'<span class="icm-ghost-label"{style}>{esc(desc)}</span>' if desc else ""
    lay = getattr(w, "layout", None)
    row_css = "".join(
        f"{prop}:{esc(val)};" for prop, val in (
            ("width", getattr(lay, "width", None)),
            ("max-width", getattr(lay, "max_width", None)))
        if val)
    row = f' style="{row_css}"' if row_css else ""

    sliders = (widgets.IntSlider, widgets.FloatSlider, widgets.FloatLogSlider,
               widgets.IntRangeSlider, widgets.FloatRangeSlider, widgets.SelectionSlider)
    if isinstance(w, sliders):
        if isinstance(w, widgets.SelectionSlider):
            fracs = [w.index / max(len(w.options) - 1, 1)]
            text = str(w.label)
        else:
            vals = w.value if isinstance(w.value, tuple) else (w.value,)
            lo, hi = w.min, w.max
            pos = (lambda v: math.log(v, w.base)) if isinstance(w, widgets.FloatLogSlider) else (lambda v: v)
            fracs = [(pos(v) - lo) / (hi - lo) if hi > lo else 0.0 for v in vals]
            try:
                text = " – ".join(format(v, w.readout_format) for v in vals)
            except (ValueError, TypeError):
                text = " – ".join(str(v) for v in vals)
        handles = "".join(
            f'<span class="icm-ghost-handle" style="left:{100 * min(max(f, 0.0), 1.0):.2f}%"></span>'
            for f in fracs)
        readout = f'<span class="icm-ghost-readout">{esc(text)}</span>' if getattr(w, "readout", True) else ""
        return (f'<div class="icm-ghost-row icm-ghost-slider"{row}>{label}'
                f'<span class="icm-ghost-track">{handles}</span>{readout}</div>')
    if isinstance(w, widgets.Dropdown):
        return (f'<div class="icm-ghost-row icm-ghost-dropdown"{row}>{label}'
                f'<span class="icm-ghost-select">{esc(str(w.label or ""))}</span></div>')
    if isinstance(w, widgets.Checkbox):
        box = "☑" if w.value else "☐"
        return f'<div class="icm-ghost-row icm-ghost-checkbox"{row}><span class="icm-ghost-check">{box}</span>{esc(desc)}</div>'
    if isinstance(w, (widgets.HTML, widgets.HTMLMath)):
        # the author's markup, exactly what the live widget shows
        return f'<div class="icm-ghost-row icm-ghost-html"{row}>{label}<span class="icm-ghost-html-content">{w.value}</span></div>'
    if isinstance(w, widgets.Label):
        return f'<div class="icm-ghost-row icm-ghost-html"{row}>{label}<span class="icm-ghost-html-content">{esc(w.value)}</span></div>'
    if isinstance(w, widgets.Output):
        # an Output holds the widget's audio card on the live page; reserve
        # its height (live-cells.css) so the card arrives without a shift
        return f'<div class="icm-ghost-row icm-ghost-output"{row}></div>'
    return f'<div class="icm-ghost-row icm-ghost-other"{row}>{label}</div>'
