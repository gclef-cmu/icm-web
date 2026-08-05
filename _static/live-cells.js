// live-cells.js — live code on notebook pages, no launch button.
//
// At page load (idle-time, silent) the vendored thebe bundle swaps each code
// cell's static <pre> for a CodeMirror editor. The heavy stack — thebe-lite
// server, Pyodide, the wheels in _static/wheels — loads only on the first
// Run, which executes the clicked cell after any unrun setup cells above it.
// Baked outputs stay in place until their cell first re-executes; reloading
// the page is the reset. Pages without code cells exit immediately.
//
// Also swaps <audio> outputs (baked or live) for the book's audio-chip card.
// Self-contained on purpose: no globals from the sphinx-thebe page glue, and
// the config tag is parsed leniently (see readThebeConfig), so the layer
// survives a page built with upstream sphinx-thebe instead of the fork.
(function () {
  "use strict";

  // Owned here so the layer doesn't depend on the fork's loadScriptAsync.
  function loadScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement("script");
      s.src = src;
      s.async = true;
      s.onload = resolve;
      s.onerror = function () {
        reject(new Error("failed to load " + src));
      };
      document.head.appendChild(s);
    });
  }

  var SEL_CELL = typeof thebe_selector !== "undefined" ? thebe_selector : ".thebe,.cell";
  var SEL_INPUT = typeof thebe_selector_input !== "undefined" ? thebe_selector_input : "pre";
  var SEL_OUTPUT = typeof thebe_selector_output !== "undefined" ? thebe_selector_output : ".output, .cell_output";

  // thebe-lite 0.5.0 / thebe 0.9.3, self-hosted under vendor/thebe-dist
  // (`make vendor-thebe`) — the kernel web worker must be same-origin.

  var thebeConfig = null; // parsed + patched text/x-thebe-config
  var mountPromise = null; // single-flight: editors mounted into the DOM
  var bootPromise = null; // thebelab.bootstrap() result (resolves kernel-up)
  var kernelPromise = null; // single-flight: first Run -> kernel ready
  var kernelRequested = false; // gates status UI (mount itself is silent)
  var openGate = null; // releases the JupyterLite server start
  var runQueue = Promise.resolve(); // serializes run requests
  var ranIds = new Set(); // thebe cell ids executed since kernel start
  var nbRef = null; // ThebeNotebook from bootstrap
  var sessionRef = null; // ThebeSession from bootstrap
  var activationDone = false; // silences boot narration after connect
  var pendingFocus = null; // cell clicked before its editor existed
  var pageCodeSnapshot = ""; // cell sources captured BEFORE editors mount

  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);

  function init() {
    var cells = codeCells();
    if (!cells.length) {
      // Prose page: nothing to mount — but quietly pre-warm the browser
      // cache with the kernel runtime, so the widget page the student
      // reaches next boots without downloading anything.
      warmCaches();
      return;
    }
    // Snapshot the page's code NOW, from the static <pre>s: once CodeMirror
    // mounts it renders text lazily, so hidden or off-screen editors expose
    // no textContent and any later scrape misses what the page uses.
    pageCodeSnapshot = Array.prototype.map
      .call(document.querySelectorAll(".cell_input"), function (e) {
        return e.textContent;
      })
      .join("\n");
    cells.forEach(addChip);
    beautifyOutputs(document); // baked audio outputs -> book audio chips
    watchDynamicAudio(); // catch the recorder's player (added on click) too
    watchRecordButtons(); // turn pq.record()'s button into a ring + countdown
    // Covers a click in the brief window before the idle mount finishes
    // (these listeners die with the static pre they're attached to).
    cells.forEach(function (cell) {
      var pre = cell.querySelector(".cell_input " + SEL_INPUT);
      if (!pre) return;
      pre.addEventListener("pointerdown", function () {
        pendingFocus = cell;
        ensureMounted().then(focusPending).catch(function () {});
      });
    });
    // Third-party widget frontends (anywidget, for FigureWidget) load from
    // a CDN by default; point thebe's loader (patched overridable by
    // make vendor-thebe) at the book's own copy (make wheels →
    // vendor/widgets-cdn/).
    (function () {
      var me = document.querySelector('script[src*="live-cells.js"]');
      var prefix = me ? me.getAttribute("src").replace(/_static\/live-cells\.js.*$/, "") : "";
      var root = prefix ? prefix.replace(/\/$/, "") : ".";
      window.__icmWidgetsCdn = new URL(
        root + "/widgets-cdn/", document.baseURI).href;
    })();
    // Baked plotly figures (icm_plotly.show at build) render immediately —
    // the real figure, no kernel — from the inert JSON in the page.
    renderBakedPlotly();
    // Cells tagged `icm-autorun` (the splitter's `# autorun` marker) run on
    // page load: their widget must be interactive without a button press.
    // A placeholder holds the spot while the kernel starts — unless the
    // cell has a baked figure, which IS the placeholder (the live widget
    // replaces it via the usual baked-output swap).
    var autorun = cells.filter(function (c) {
      return c.classList.contains("tag_icm-autorun");
    });
    autorun.forEach(function (cell) {
      if (!cell.querySelector(".icm-plotly-fig")) addAutorunPlaceholder(cell);
    });
    // Mount once the page settles. A mount failure leaves the static page
    // intact, so it only reports to the console. Autorun pages skip the
    // idle wait — their widgets need the kernel as soon as possible, so
    // the boot chain starts at t=0 instead of ~2 s in.
    var kick = function () {
      ensureMounted()
        .then(function () {
          schedulePrewarm();
          autorun.forEach(function (cell) {
            enqueueRun(cell, { auto: true });
          });
        })
        .catch(function () {});
    };
    if (autorun.length) kick();
    else if ("requestIdleCallback" in window) requestIdleCallback(kick, { timeout: 1500 });
    else setTimeout(kick, 250);
  }

  // The spot where an autorun cell's widget will land: a quiet output-shaped
  // card so the page doesn't jump when the widget arrives. Removed when the
  // cell's run settles (success or failure — errors surface via the status
  // pill and the cell's own error card).
  function addAutorunPlaceholder(cell) {
    var wait = document.createElement("div");
    wait.className = "cell_output docutils container live-autorun-wait";
    wait.textContent = "Interactive demo — starting Python…";
    cell.appendChild(wait);
  }

  function removeAutorunPlaceholder(cell) {
    var wait = cell.querySelector(".live-autorun-wait");
    if (wait) wait.remove();
  }

  // ----- baked plotly figures ---------------------------------------------

  // icm_plotly.show bakes each figure as inert JSON in an .icm-plotly-fig
  // div. Render them with the book's vendored plotly.js (copied from the
  // build's plotly package by `make wheels`, served from vendor/ like the
  // thebe bundles) — the figure appears the moment the page opens, and the
  // cell's first live execution swaps it for the interactive widget.
  function renderBakedPlotly() {
    var nodes = document.querySelectorAll(".icm-plotly-fig");
    if (!nodes.length) return;
    var me = document.querySelector('script[src*="live-cells.js"]');
    var prefix = me ? me.getAttribute("src").replace(/_static\/live-cells\.js.*$/, "") : "";
    var root = prefix ? prefix.replace(/\/$/, "") : ".";
    loadScript(root + "/plotly-dist/plotly.min.js")
      .then(function () {
        nodes.forEach(function (node) {
          var spec = node.querySelector(
            'script[type="application/vnd.icm-plotly+json"]'
          );
          if (!spec) return;
          var fig = JSON.parse(spec.textContent);
          window.Plotly.newPlot(node, fig.data, fig.layout, {
            displayModeBar: false,
            responsive: true,
          });
        });
      })
      .catch(function (e) {
        console.error("[live] baked plotly", e);
      });
  }

  // ----- cross-page cache warming -----------------------------------------

  // Fetch the kernel runtime into the browser's HTTP cache from prose pages,
  // so a later widget page boots with zero downloads. Pure fetch(): nothing
  // executes, nothing mounts. Once per session; respects data-saver.
  function warmCaches() {
    if (navigator.connection && navigator.connection.saveData) return;
    try {
      if (sessionStorage.getItem("icm-live-warmed")) return;
    } catch (e) {
      return; // storage blocked: skip rather than re-warm every page
    }
    var me = document.querySelector('script[src*="live-cells.js"]');
    var prefix = me ? me.getAttribute("src").replace(/_static\/live-cells\.js.*$/, "") : "";
    var root = prefix ? prefix.replace(/\/$/, "") : ".";
    var grab = function (url) {
      return fetch(new URL(url, document.baseURI).href, { priority: "low" })
        .then(function (r) { return r.ok ? r.blob() : null; })
        .catch(function () {});
    };
    var run = function () {
      var jobs = [
        grab(root + "/thebe-dist/core/index.js"),
        grab(root + "/thebe-dist/lite/thebe-lite.min.js"),
        grab(root + "/thebe-dist/lite/pypi/all.json"),
        grab(root + "/plotly-dist/plotly.min.js"),
      ];
      // pyodide runtime + package closure (list written by make vendor-pyodide)
      jobs.push(
        fetch(new URL(root + "/pyodide/warm-manifest.json", document.baseURI).href)
          .then(function (r) { return r.json(); })
          .then(function (names) {
            return Promise.all(names.map(function (n) {
              return grab(root + "/pyodide/" + n);
            }));
          })
          .catch(function () {})
      );
      // the book's wheels + the plotly widget stack
      ["/_static/wheels/", "/_static/wheels/widgets/"].forEach(function (dir) {
        jobs.push(
          fetch(new URL(root + dir + "manifest.json", document.baseURI).href)
            .then(function (r) { return r.json(); })
            .then(function (names) {
              return Promise.all(names.map(function (n) {
                return grab(root + dir + n);
              }));
            })
            .catch(function () {})
        );
      });
      Promise.all(jobs).then(function () {
        try { sessionStorage.setItem("icm-live-warmed", "1"); } catch (e) {}
      });
    };
    var idle = function () {
      if ("requestIdleCallback" in window) requestIdleCallback(run, { timeout: 8000 });
      else setTimeout(run, 4000);
    };
    if (document.readyState === "complete") idle();
    else window.addEventListener("load", idle, { once: true });
  }

  function focusPending() {
    if (!pendingFocus) return;
    // thebe 0.9.3 mounts CodeMirror 5: the instance hangs off the wrapper.
    var el = pendingFocus.querySelector(".CodeMirror");
    pendingFocus = null;
    if (el && el.CodeMirror) el.CodeMirror.focus();
  }

  // Real, runnable cells only: skip the extension's hidden init cell and
  // anything tagged non-executable. A cell holds a static `pre` before the
  // mount and a data-thebe-id editor after — accept either form.
  function codeCells() {
    return Array.prototype.slice
      .call(document.querySelectorAll(SEL_CELL))
      .filter(function (c) {
        return (
          (c.querySelector(".cell_input " + SEL_INPUT) ||
            c.querySelector("[data-thebe-id]")) &&
          !c.classList.contains("tag_thebe-remove-input-init") &&
          !c.classList.contains("tag_disable-execution-cell")
        );
      });
  }

  // ----- per-cell Run chips ---------------------------------------------

  function addChip(cell) {
    var input = cell.querySelector(".cell_input");
    var chip = document.createElement("button");
    chip.className = "live-run-chip";
    chip.type = "button";
    chip.title = "Run this cell (its setup cells above run first) — Shift-Enter works too";
    chip.textContent = "▶ Run";
    chip.addEventListener("click", function () {
      enqueueRun(cell);
    });
    input.appendChild(chip);
  }

  function setChip(cell, state) {
    var chip = cell.querySelector(".live-run-chip");
    if (!chip) return;
    chip.classList.toggle("live-busy", state !== "idle");
    chip.textContent =
      state === "starting" ? "starting…" : state === "running" ? "running…" : "▶ Run";
  }

  // ----- per-cell execution state + timing (VSCode-notebook style) --------
  // A run cell gets a colored left bar (amber running, green ok, red error)
  // and a time badge that ticks up and freezes at the final duration.

  var cellTimers = new WeakMap(); // cell -> { start, iv }

  function execBadge(cell) {
    var input = cell.querySelector(".cell_input");
    if (!input) return null;
    var el = input.querySelector(".live-exec-time");
    if (!el) {
      el = document.createElement("span");
      el.className = "live-exec-time";
      input.appendChild(el);
    }
    return el;
  }

  function fmtSecs(ms) {
    var s = ms / 1000;
    return (s < 10 ? s.toFixed(1) : Math.round(s)) + "s";
  }

  // idle | running | ran | failed — drives the left-bar color (live-cells.css).
  function setCellState(cell, state) {
    cell.classList.remove("live-running", "live-ran", "live-failed");
    if (state === "running") cell.classList.add("live-running");
    else if (state === "ran") cell.classList.add("live-ran");
    else if (state === "failed") cell.classList.add("live-failed");
  }

  function clearTimerInterval(cell) {
    var t = cellTimers.get(cell);
    if (t) {
      clearInterval(t.iv);
      cellTimers.delete(cell);
    }
    return t;
  }

  // Amber bar, ticking badge, and a live elapsed readout in the Run chip.
  function startTimer(cell) {
    clearTimerInterval(cell);
    setCellState(cell, "running");
    var badge = execBadge(cell);
    var chip = cell.querySelector(".live-run-chip");
    var start = Date.now();
    if (badge) badge.textContent = "0.0s";
    var iv = setInterval(function () {
      var txt = fmtSecs(Date.now() - start);
      if (badge) badge.textContent = txt;
      if (chip && chip.classList.contains("live-busy")) chip.textContent = "running " + txt;
    }, 100);
    cellTimers.set(cell, { start: start, iv: iv });
  }

  // Freeze the timer at the final duration and record the outcome.
  function stopTimer(cell, errored) {
    var t = clearTimerInterval(cell);
    var badge = execBadge(cell);
    if (badge && t) badge.textContent = fmtSecs(Date.now() - t.start);
    setCellState(cell, errored ? "failed" : "ran");
  }

  // Errored = a traceback (tagged by freshenOutput) or a Jupyter error mime.
  function cellErrored(cell) {
    return !!cell.querySelector(
      '.cell_output .live-error, .cell_output [data-mime-type="application/vnd.jupyter.error"]'
    );
  }

  // ----- status pill / connected badge ----------------------------------

  var statusEl = null;
  var startedAt = 0;
  var ticker = null;
  var lastMsg = "";
  var lastKind = null;
  var leaveGuardArmed = false;

  function elapsed() {
    return Math.round((Date.now() - startedAt) / 1000);
  }

  function status(msg, kind) {
    lastMsg = msg;
    lastKind = kind || null;
    // The background prewarm is silent — the pill appears only for things a
    // student asked for. ensureKernel replays the latest state on first Run.
    if (!kernelRequested) return;
    if (!statusEl) {
      statusEl = document.createElement("div");
      statusEl.className = "live-status";
      document.body.appendChild(statusEl);
    }
    statusEl.className = "live-status live-status-" + (kind || "busy");
    if (kind === "busy" || !kind) {
      statusEl.textContent = msg + " · " + elapsed() + " s";
      if (!ticker) {
        ticker = setInterval(function () {
          statusEl.textContent = lastMsg + " · " + elapsed() + " s";
        }, 1000);
      }
    } else {
      if (ticker) {
        clearInterval(ticker);
        ticker = null;
      }
      statusEl.textContent = msg;
    }
  }

  function reportError(err) {
    console.error("[live-cells]", err);
    status(
      "Live code failed: " + (err && err.message ? err.message : err) + " — reload the page to try again.",
      "error"
    );
  }

  // ----- editor mount (page load, silent) --------------------------------

  function ensureMounted() {
    if (!mountPromise) {
      mountPromise = mountEditors().catch(function (err) {
        console.error("[live-cells] editor mount failed:", err);
        throw err;
      });
    }
    return mountPromise;
  }

  // The text/x-thebe-config tag. The TeachBooks fork emits strict JSON, but
  // upstream sphinx-thebe (same dist name and version — see check-thebe-fork
  // in the Makefile) emits a JS object literal that JSON.parse rejects. So
  // parse leniently, then force every setting our self-hosted runtime needs:
  // a no-op on fork-built pages, a repair on upstream-built ones.
  function readThebeConfig() {
    var tag = document.querySelector('script[type="text/x-thebe-config"]');
    var config = {};
    if (tag) {
      try {
        config = JSON.parse(tag.text);
      } catch (e) {
        try {
          config = new Function("return (" + tag.text + ");")() || {};
        } catch (e2) {
          console.warn("[live-cells] unparseable thebe config tag:", e2);
        }
      }
    }
    config.useJupyterLite = true;
    config.useBinder = false;
    config.requestKernel = true;
    config.kernelOptions = Object.assign({}, config.kernelOptions, { path: "/" });
    if (!config.rootPath) {
      // Derive the docs root from our own script tag. Root-level pages get
      // "." — "" would resolve "/thebe-dist/…" against the domain root.
      var me = document.querySelector('script[src*="live-cells.js"]');
      var prefix = me ? me.getAttribute("src").replace(/_static\/live-cells\.js.*$/, "") : "";
      config.rootPath = prefix ? prefix.replace(/\/$/, "") : ".";
    }
    return config;
  }

  async function mountEditors() {
    var config = readThebeConfig();
    // The chips are the single execution path, so suppress thebe's own
    // buttons. Restart keys in both spellings: the extension writes
    // "mountRestartallButton" but thebe 0.9.3 reads camel-case "All".
    config.mountRunButton = false;
    config.mountRunAllButton = false;
    config.mountRestartButton = false;
    config.mountRestartallButton = false;
    config.mountRestartAllButton = false;
    // Match the static code blocks: no gutters, default theme.
    config.codeMirrorConfig = Object.assign({}, config.codeMirrorConfig, {
      lineNumbers: false,
      theme: "default",
      mode: "python",
    });
    thebeConfig = config;

    // The gate. bootstrap() calls window.thebeLite.startJupyterLiteServer
    // right away; this stand-in parks that call on a promise released on the
    // first Run, keeping the mount free of Pyodide and all network weight.
    // The real bundle later Object.assign()s itself over this object — fine,
    // the parked call already captured the gate.
    var gate = new Promise(function (resolve) {
      openGate = resolve;
    });
    window.thebeLite = {
      startJupyterLiteServer: function (cfg) {
        return gate.then(function (start) {
          return start(cfg);
        });
      },
    };

    await loadScript(config.rootPath + "/thebe-dist/core/index.js");

    prepareCells();
    // Gates the editor-parity styling in live-cells.css.
    document.body.classList.add("live-active");

    thebelab.on("status", function (evt, data) {
      // Only narrate while a student is actually waiting for the runtime;
      // mount-time and steady-state kernel events stay silent.
      if (!kernelRequested || activationDone) return;
      if (data.status === "ready" || data.status === "attached") return;
      status("Starting Python (" + data.status + ") — a first visit downloads ~45 MB");
    });

    // bootstrap renders the editors right away, then awaits the gated
    // server — so its promise resolves only after the first Run.
    bootPromise = thebelab.bootstrap(config);
    bootPromise.catch(function (err) {
      if (kernelRequested) reportError(err);
      else console.error("[live-cells]", err);
    });

    await waitForEditors();
    relocateLiveOutputs();
    bindEditors();
    focusPending();
  }

  function waitForEditors() {
    var want = codeCells().length;
    return new Promise(function (resolve, reject) {
      var t0 = Date.now();
      (function poll() {
        if (document.querySelectorAll(".thebe-cell .CodeMirror").length >= want)
          return resolve();
        if (Date.now() - t0 > 10000)
          return reject(new Error("editors did not mount"));
        setTimeout(poll, 50);
      })();
    });
  }

  // Per-editor wiring: notebook keybindings, copy buttons, and a refresh
  // for editors revealed by <details> (they mount collapsed, at zero width).
  function bindEditors() {
    codeCells().forEach(function (cell) {
      var el = cell.querySelector(".CodeMirror");
      if (!el || !el.CodeMirror) return;
      var cm = el.CodeMirror;
      var run = function () {
        enqueueRun(cell);
      };
      cm.setOption(
        "extraKeys",
        Object.assign({}, cm.getOption("extraKeys") || {}, {
          "Shift-Enter": run,
          "Cmd-Enter": run,
          "Ctrl-Enter": run,
        })
      );
      // Re-point the copy button at the editor's current text — it still
      // reads the static <pre> the editor replaced (clone drops handlers).
      cell.querySelectorAll("button.copybtn").forEach(function (b) {
        var fresh = b.cloneNode(true);
        b.parentNode.replaceChild(fresh, b);
        fresh.addEventListener("click", function (e) {
          e.preventDefault();
          navigator.clipboard.writeText(cm.getValue()).then(function () {
            var was = fresh.innerHTML;
            fresh.innerHTML =
              '<span style="font-size:0.9em;color:var(--live-ok);">✓</span>';
            setTimeout(function () {
              fresh.innerHTML = was;
            }, 1200);
          });
        });
      });
    });
    document.querySelectorAll("details").forEach(function (d) {
      d.addEventListener("toggle", function () {
        d.querySelectorAll(".CodeMirror").forEach(function (el) {
          if (el.CodeMirror) el.CodeMirror.refresh();
        });
      });
    });
  }

  // Mark inputs executable for thebe. Baked outputs never get data-output,
  // so thebe leaves them alone; each is tagged so the cell's first
  // re-execution removes it.
  function prepareCells() {
    codeCells().forEach(function (cell, i) {
      if (!cell.id) cell.id = "livecell" + i;
      var input = cell.querySelector(".cell_input " + SEL_INPUT);
      input.setAttribute("data-language", "python");
      input.setAttribute("data-executable", "true");
      var output = cell.querySelector(SEL_OUTPUT);
      if (output) output.classList.add("live-baked-output");
    });
  }

  function dropBakedOutput(cell) {
    var baked = cell.querySelector(".live-baked-output");
    if (baked) baked.remove();
  }

  // Thebe renders live output areas INSIDE .cell_input; move each into a
  // .cell_output container so live results are styled like baked ones (and
  // hide-input cells' output isn't stuck inside the collapsed <details>).
  // Moving the node is safe: thebe keeps a reference to the same element.
  function relocateLiveOutputs() {
    codeCells().forEach(function (cell) {
      var area = cell.querySelector(".cell_input .jp-OutputArea");
      if (!area) return;
      var wrap = document.createElement("div");
      wrap.className = "cell_output docutils container live-output";
      wrap.appendChild(area);
      cell.appendChild(wrap);
    });
  }

  // ----- kernel start (first Run) ----------------------------------------

  function ensureKernel() {
    if (!kernelRequested) {
      kernelRequested = true;
      // A prewarm may already be underway (or done): surface its state.
      if (lastMsg) status(lastMsg, lastKind);
    }
    if (!kernelPromise) {
      startedAt = Date.now();
      kernelPromise = startKernel().catch(function (err) {
        reportError(err);
        throw err;
      });
    }
    return kernelPromise;
  }

  // Pre-boot the kernel in the background once the page goes idle, so the
  // first ▶ Run pays only for its own cells. Silent, runs no user code,
  // skipped for save-data readers; on failure Run just boots normally.
  function schedulePrewarm() {
    if (navigator.connection && navigator.connection.saveData) return;
    var warm = function () {
      if (kernelPromise) return;
      startedAt = Date.now();
      kernelPromise = startKernel().catch(function (err) {
        console.warn("[live-cells] kernel prewarm failed; Run will retry:", err);
        if (kernelRequested) reportError(err);
        kernelPromise = null;
        throw err;
      });
      kernelPromise.catch(function () {}); // nobody awaits a prewarm
    };
    if ("requestIdleCallback" in window) requestIdleCallback(warm, { timeout: 6000 });
    else setTimeout(warm, 3000);
  }

  async function startKernel() {
    await ensureMounted();
    status("Starting Python — a first visit downloads ~45 MB");
    await loadScript(thebeConfig.rootPath + "/thebe-dist/lite/thebe-lite.min.js");

    // Pin the runtime. Pyodide 0.27.7: pyquist needs numpy>=2.0 (so >=0.27)
    // and the bundled pyodide_kernel 0.4.7 crashes on >=0.28. 0.27 has no
    // WASM soundfile — that's why tools/soundfile_stub exists; bump this URL
    // and delete the stub when the kernel stack reaches 0.28. The piplite
    // URLs self-host the kernel wheels instead of thebe-lite's unpkg
    // defaults, and must go through startJupyterLiteServer's own config
    // merge — thebe never forwards a lite config, and thebe-lite overwrites
    // the page-level litePluginSettings unconditionally.
    var liteSettings = {
      "@jupyterlite/pyodide-kernel-extension:kernel": {
        // Self-hosted (make vendor-pyodide → vendor/pyodide, served at
        // /pyodide/): no CDN at runtime. Same 0.27.7 pin as before.
        pyodideUrl: new URL(
          thebeConfig.rootPath + "/pyodide/pyodide.js",
          document.baseURI
        ).href,
        pipliteUrls: [
          new URL(thebeConfig.rootPath + "/thebe-dist/lite/pypi/all.json", document.baseURI).href,
        ],
        pipliteWheelUrl: new URL(
          thebeConfig.rootPath + "/thebe-dist/lite/pypi/piplite-0.4.7-py3-none-any.whl",
          document.baseURI
        ).href,
      },
    };
    // The lite bundle just replaced our placeholder; release the gate with a
    // wrapper that injects the pinned settings into the real start.
    var realStart = window.thebeLite.startJupyterLiteServer;
    openGate(function (cfg) {
      cfg = Object.assign({}, cfg);
      cfg.litePluginSettings = Object.assign({}, cfg.litePluginSettings, liteSettings);
      return realStart.call(window.thebeLite, cfg);
    });

    // thebe 0.9.x resolves bootstrap with { server, session, notebook }.
    var boot = await bootPromise;
    nbRef = boot.notebook;
    sessionRef = boot.session;

    // One message covers the whole install phase — the book's wheels plus
    // any per-page extras (plotly is ~10 MB of it on widget pages).
    status("Installing packages…");
    await installWheels(thebeConfig);
    await runInitCells_();

    activationDone = true;
    status("● Python connected — ready in " + elapsed() + " s. Reload page to reset.", "connected");
  }

  async function installWheels(config) {
    var base = new URL(config.rootPath + "/_static/wheels/", document.baseURI);
    var manifest = await (await fetch(new URL("manifest.json", base))).json();
    var lines = [
      // Load the compiled dependencies from the Pyodide distribution FIRST,
      // pinning them to the WASM builds — micropip might otherwise resolve
      // a newer PyPI wheel that needs native libraries the browser lacks.
      // (soundfile is absent from 0.27; the manifest's stub stands in.)
      "import pyodide_js",
      "from pyodide.ffi import to_js",
      'await pyodide_js.loadPackage(to_js(["numpy", "matplotlib", "soxr", "requests", "tqdm"]))',
      "import micropip",
    ];
    manifest.forEach(function (name) {
      lines.push('await micropip.install("' + new URL(name, base).href + '")');
    });
    // Extras installed only when a cell on THIS page uses them, so other
    // pages don't pay for them. Keyed on strings in the pre-mount code
    // snapshot (post-mount DOM scrapes miss lazily-rendered editors).
    var pageCode = pageCodeSnapshot;
    // The plotly widget stack, self-hosted under wheels/widgets/ (`make
    // wheels`) so widget pages never touch PyPI at runtime — a stalled
    // 10 MB PyPI fetch used to hang the whole boot at "installing".
    // deps=False: the manifest IS the dependency closure. The baked-figure
    // div is the second signal, in case the code scrape ever misses.
    if (pageCode.indexOf("plotly") !== -1 || document.querySelector(".icm-plotly-fig")) {
      var wbase = new URL(config.rootPath + "/_static/wheels/widgets/", document.baseURI);
      var widgets = await (await fetch(new URL("manifest.json", wbase))).json();
      var urls = widgets.map(function (name) {
        return '"' + new URL(name, wbase).href + '"';
      });
      lines.push(
        "await micropip.install([" + urls.join(", ") + "], deps=False)"
      );
    }
    // browseraudio (pq.record mic capture) stays on PyPI: small, and only
    // recording pages use it.
    if (["browseraudio", "pq.record"].some(function (s) { return pageCode.indexOf(s) !== -1; })) {
      lines.push('await micropip.install("browseraudio")');
    }
    // Browser-kernel shims: a no-op myst_nb.glue (build-time-only library)
    // and the RcParams patch the TeachBooks extension applies for matplotlib.
    lines.push(
      "import sys, types",
      'if "myst_nb" not in sys.modules:',
      '    _m = types.ModuleType("myst_nb"); _m.glue = lambda *a, **k: None; sys.modules["myst_nb"] = _m',
      "import matplotlib",
      'if not hasattr(matplotlib.RcParams, "_get"):',
      "    matplotlib.RcParams._get = dict.get",
      // Build the font cache now, during setup, so its "this may take a
      // moment" stderr lands here instead of in the first cell's output.
      "import matplotlib.font_manager"
    );
    // Students copy `!pip install x` from the wider internet, but WASM has
    // no shell — the raw result is a bare OSError. Rewrite !pip installs
    // to micropip (works for pure-Python wheels and anything vendored),
    // and give every other !command a plain explanation.
    lines.push(
      "async def _icm_pip_install(_spec):",
      "    import shlex, micropip",
      '    _pkgs = [_a for _a in shlex.split(_spec) if not _a.startswith("-")]',
      "    if not _pkgs:",
      '        raise OSError("usage: !pip install <package>")',
      "    try:",
      "        await micropip.install(_pkgs)",
      '        print("Installed:", ", ".join(_pkgs))',
      "    except Exception as _e:",
      '        raise OSError(", ".join(_pkgs) + " is not installable in the browser kernel (pure-Python packages only). Ask course staff to add it to the book.") from None',
      '_icm_shell_msg = "{0} does not work here: the browser kernel has no shell. To add packages, use !pip install <name>."',
      "def _icm_no_shell(_lines):",
      "    _out = []",
      "    for _l in _lines:",
      "        _s = _l.lstrip()",
      '        if not _s.startswith("!"):',
      "            _out.append(_l); continue",
      "        _ind = _l[: len(_l) - len(_s)]",
      "        _cmd = _s[1:].strip()",
      "        _p = _cmd.split()",
      '        if _p and _p[0] in ("pip", "pip3") and len(_p) > 1 and _p[1] == "install":',
      '            _out.append(_ind + "await _icm_pip_install({0!r})\\n".format(_cmd.split("install", 1)[1].strip()))',
      "        else:",
      '            _out.append(_ind + "raise OSError(_icm_shell_msg.format({0!r}))\\n".format("!" + (_p[0] if _p else "")))',
      "    return _out",
      "get_ipython().input_transformers_cleanup.append(_icm_no_shell)"
    );
    // The inlined chapter scripts locate their output folder via __file__,
    // which a notebook cell doesn't have — they'd NameError on Run. Define
    // one under the kernel's CWD so their WAV writes land harmlessly in the
    // in-memory FS (readers hear the chapter audio through the {audio}
    // chips). Guarded so a genuine __file__ always wins.
    lines.push(
      "import os as _os",
      'if "__file__" not in globals():',
      '    __file__ = _os.path.join(_os.getcwd(), "code", "inlined_script.py")'
    );
    // Data files the page's code reads by relative path (./assets/... after
    // the splitter's rewrite) don't exist in the kernel's in-memory FS.
    // Fetch each one a code cell mentions and write it at that exact
    // relative path — the kernel CWD is the same for setup and user cells,
    // so open()/pq.Audio.from_file() then just work. A 404 or fetch error
    // only skips that file; the cell fails with the same FileNotFoundError
    // it would have raised anyway.
    var assetRefs = pageCode.match(/\.\/(?:assets|code|figures)\/[\w.\-/]+/g) || [];
    var seenRefs = new Set();
    assetRefs = assetRefs.filter(function (rel) {
      if (seenRefs.has(rel)) return false;
      seenRefs.add(rel);
      return true;
    });
    if (assetRefs.length) {
      lines.push("from pyodide.http import pyfetch as _icm_pyfetch");
      assetRefs.forEach(function (rel) {
        var url = new URL(rel, document.baseURI).href;
        lines.push(
          "try:",
          "    _r = await _icm_pyfetch(" + JSON.stringify(url) + ")",
          "    if _r.status == 200:",
          "        _os.makedirs(_os.path.dirname(" + JSON.stringify(rel) + '), exist_ok=True)',
          "        _b = await _r.bytes()",
          "        open(" + JSON.stringify(rel) + ', "wb").write(_b)',
          "except Exception as _e:",
          '    print("[icm] asset prefetch failed:", ' + JSON.stringify(rel) + ", _e)"
        );
      });
    }
    var fut = sessionRef.kernel.requestExecute({ code: lines.join("\n") });
    var kernelErr = null;
    fut.onIOPub = function (m) {
      var c = m.content || {};
      if (c.ename) {
        kernelErr = c.ename + ": " + c.evalue;
        console.error("[live-cells] kernel:", kernelErr);
      }
    };
    var reply = await fut.done;
    var st = reply && reply.content && reply.content.status;
    if (st && st !== "ok") {
      throw new Error("environment setup failed — " + (kernelErr || "see browser console"));
    }
  }

  // The extension injects hidden thebe-init cells (e.g. its matplotlib
  // patch) that expect to run right after the kernel is up. They're never
  // thebe-mounted, so run their source directly on the kernel.
  async function runInitCells_() {
    var initCells = document.querySelectorAll(".thebe-init, .tag_thebe-init");
    for (var i = 0; i < initCells.length; i++) {
      var pre = initCells[i].querySelector("pre");
      if (pre && pre.textContent.trim()) {
        await sessionRef.kernel.requestExecute({ code: pre.textContent }).done;
      }
    }
  }

  // The thebe notebook cell backing a DOM cell; null for unmounted cells.
  function nbCellOf(cell) {
    var marked = cell.querySelector("[data-thebe-id]");
    if (!marked || !nbRef) return null;
    var id = marked.getAttribute("data-thebe-id");
    return nbRef.cells.find(function (c) {
      return c.id === id;
    }) || null;
  }

  // ----- execution --------------------------------------------------------

  // Serialize runs: several clicked chips queue instead of interleaving.
  function enqueueRun(cell, opts) {
    var auto = opts && opts.auto;
    if (!leaveGuardArmed && !auto) {
      leaveGuardArmed = true;
      // Leaving loses the kernel state the student built by running cells.
      // Armed on the first explicit Run, not at boot or autorun — state the
      // page rebuilds by itself isn't worth nagging about.
      window.addEventListener("beforeunload", function (e) {
        e.preventDefault();
        e.returnValue = "";
      });
    }
    setChip(cell, kernelPromise ? "running" : "starting");
    runQueue = runQueue
      .then(function () {
        return runChain(cell);
      })
      .catch(function () {
        /* reported by the pipeline; keep the queue alive */
      })
      .then(function () {
        removeAutorunPlaceholder(cell);
        // Live FigureWidgets can render at a stale width; they're
        // responsive (icm_plotly sets it), so resize kicks snap them to
        // their real container. Delayed: execution settling is not view
        // rendering — the widget's DOM appears a beat later.
        [400, 1200, 2500].forEach(function (ms) {
          setTimeout(function () {
            window.dispatchEvent(new Event("resize"));
          }, ms);
        });
      });
  }

  // A split page interleaves several self-contained companion notebooks,
  // each tagged `icm-run-group-N` by the splitter. Scope a Run's setup
  // chain to the clicked cell's group; pages without groups keep the
  // whole-page chain.
  function runGroupOf(cell) {
    for (var i = 0; i < cell.classList.length; i++) {
      if (cell.classList[i].indexOf("tag_icm-run-group-") === 0)
        return cell.classList[i];
    }
    return null;
  }

  async function runChain(target) {
    try {
      await ensureKernel();
      var chain = codeCells();
      var group = runGroupOf(target);
      if (group) {
        chain = chain.filter(function (c) {
          return c.classList.contains(group);
        });
      }
      for (var i = 0; i < chain.length; i++) {
        var cell = chain[i];
        var isTarget = cell === target;
        var nb = nbCellOf(cell);
        if (!nb) continue;
        if (isTarget || !ranIds.has(nb.id)) {
          dropBakedOutput(cell);
          setChip(cell, "running");
          startTimer(cell);
          try {
            await nb.execute();
          } catch (e) {
            stopTimer(cell, true); // kernel-level failure → red bar
            throw e;
          }
          ranIds.add(nb.id);
          freshenOutput(cell);
          stopTimer(cell, cellErrored(cell)); // green, or red on a Python traceback
          if (!isTarget) setChip(cell, "idle");
        }
        if (isTarget) break;
      }
    } finally {
      setChip(target, "idle");
    }
  }

  // Post-run polish: audio → chip cards, tracebacks tagged, and a gentle
  // pulse on the output rail so the fresh result is findable.
  function freshenOutput(cell) {
    beautifyOutputs(cell);
    // thebe emits tracebacks under the same stderr mime type tqdm uses, so
    // the red error treatment can't hang off the mime type alone.
    cell
      .querySelectorAll('[data-mime-type="application/vnd.jupyter.stderr"]')
      .forEach(function (el) {
        if (el.textContent.indexOf("Traceback (most recent call last)") !== -1) {
          el.classList.add("live-error");
        }
      });
    var out = cell.querySelector(".cell_output.live-output");
    if (!out) return;
    out.classList.remove("live-fresh");
    void out.offsetWidth; // restart the rail-pulse animation
    out.classList.add("live-fresh");
  }

  // ----- output beautifier ------------------------------------------------
  // Swap each bare <audio> output — baked or live — for the same chip card
  // the {audio} directive renders (markup mirrors _ext/icm_audio.py; wiring
  // via the hook audio-chip.js exposes). The WAV header is parsed for a
  // "1.00 s · 44.1 kHz · mono" caption.

  var CHIP_MARKUP =
    '<svg class="audio-chip-ring" viewBox="0 0 36 36" aria-hidden="true">' +
    '<circle class="acr-track" cx="18" cy="18" r="15.9155"></circle>' +
    '<circle class="acr-fill" cx="18" cy="18" r="15.9155"></circle>' +
    "</svg>" +
    '<svg class="audio-chip-icon" viewBox="0 0 24 24" aria-hidden="true">' +
    '<path class="ac-play" d="M8 5v14l11-7z"></path>' +
    '<g class="ac-pause"><rect x="7" y="5" width="3.5" height="14"></rect>' +
    '<rect x="13.5" y="5" width="3.5" height="14"></rect></g>' +
    "</svg>";

  // Download icon matching the {audio} directive's control.
  var DOWNLOAD_MARKUP =
    '<svg class="audio-download-icon" viewBox="0 0 24 24" aria-hidden="true">' +
    '<path d="M12 16l-5-5h3V4h4v7h3l-5 5zm-7 2h14v2H5z"></path></svg>';

  function beautifyOutputs(root) {
    root.querySelectorAll(".cell_output audio").forEach(function (audio) {
      var src = audio.getAttribute("src");
      if (!src) {
        var sourceEl = audio.querySelector("source");
        src = sourceEl && sourceEl.getAttribute("src");
      }
      if (!src) return; // nothing playable; leave the native element

      var card = document.createElement("div");
      card.className = "audio-block audio-output";
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "audio-chip audio-chip-lg";
      chip.setAttribute("data-audio-src", src);
      chip.setAttribute("aria-label", "Play audio output");
      chip.title = "Play audio output";
      chip.innerHTML = CHIP_MARKUP;
      var body = document.createElement("div");
      body.className = "audio-block-body";
      var name = document.createElement("span");
      name.className = "audio-output-name";
      name.textContent = "Audio output";
      body.appendChild(name);
      card.appendChild(chip);
      card.appendChild(body);
      // Trailing download control (data:/blob: URLs honor `download`).
      var dl = document.createElement("a");
      dl.className = "audio-download";
      dl.href = src;
      dl.setAttribute("download", "audio-output.wav");
      dl.setAttribute("aria-label", "Download audio output");
      dl.title = "Download audio output";
      dl.innerHTML = DOWNLOAD_MARKUP;
      card.appendChild(dl);
      audio.replaceWith(card);
      setAudioMeta(body, src); // "1.00 s · 44.1 kHz · mono"
      if (window.icmWireAudioChip) window.icmWireAudioChip(chip);
    });
  }

  // The recorder's player appears only when the student clicks Record —
  // after freshenOutput ran — so watch for late <audio> nodes and give them
  // the chip card too.
  function watchDynamicAudio() {
    new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i++) {
        var nodes = records[i].addedNodes;
        for (var j = 0; j < nodes.length; j++) {
          var n = nodes[j];
          if (n.nodeType !== 1) continue;
          if (n.tagName === "AUDIO" || (n.querySelector && n.querySelector("audio"))) {
            beautifyOutputs(document);
            return;
          }
        }
      }
    }).observe(document.body, { childList: true, subtree: true });
  }

  // Wrap pq.record()'s plain ipywidgets button in an audio-output-style
  // card: a round record control with a draining ring and a countdown
  // caption. Driven by the widget's own labels; the widget stays untouched.
  function enhanceRecordButton(origBtn) {
    if (origBtn.dataset.baRing) return; // idempotent
    var text = origBtn.textContent || "";
    if (!/Record/i.test(text)) return; // only the record button
    var m = text.match(/([\d.]+)\s*s/);
    var duration = m ? parseFloat(m[1]) : 3;
    var durLabel = (duration % 1 === 0 ? duration.toFixed(0) : duration.toFixed(1)) + " s";
    origBtn.dataset.baRing = "1";

    // Hide the widget's button + status span and render our own card,
    // forwarding clicks.
    origBtn.style.display = "none";
    var status = origBtn.nextElementSibling;
    if (status && status.tagName === "SPAN") status.style.display = "none";

    // Reuse the audio-chip ring geometry (viewBox 36, r=15.9155,
    // dasharray 100) so the control matches a pq.play() output chip.
    var NS = "http://www.w3.org/2000/svg";
    function circle(cls) {
      var c = document.createElementNS(NS, "circle");
      c.setAttribute("class", cls);
      c.setAttribute("cx", "18");
      c.setAttribute("cy", "18");
      c.setAttribute("r", "15.9155");
      return c;
    }
    var ring = document.createElementNS(NS, "svg");
    ring.setAttribute("class", "audio-chip-ring");
    ring.setAttribute("viewBox", "0 0 36 36");
    var fill = circle("acr-fill"); // dasharray 100, offset 100 (empty) via custom.css
    fill.style.transition = "stroke-dashoffset 0.1s linear";
    ring.append(circle("acr-track"), fill);
    var dot = document.createElement("span");
    dot.className = "ba-dot";

    var ctrl = document.createElement("button");
    ctrl.type = "button";
    ctrl.className = "audio-chip audio-chip-lg ba-record";
    ctrl.title = "Record " + durLabel;
    ctrl.append(ring, dot);

    var card = document.createElement("div");
    card.className = "audio-block audio-output";
    var body = document.createElement("div");
    body.className = "audio-block-body";
    var label = document.createElement("span");
    label.className = "audio-output-name";
    body.append(label);
    card.append(ctrl, body);
    origBtn.parentNode.insertBefore(card, origBtn);

    function setLabel(main, sub) {
      label.textContent = main + " ";
      var s = document.createElement("span");
      s.className = "ba-sub";
      s.textContent = "· " + sub;
      label.append(s);
    }
    setLabel("Record", durLabel);

    var timer = null;
    function stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
      fill.style.strokeDashoffset = "100"; // empty ring
    }

    ctrl.addEventListener("click", function () {
      if (timer) return;
      origBtn.click(); // trigger the widget's capture, within this user gesture
      var startedAt = performance.now();
      fill.style.strokeDashoffset = "0"; // full ring at the start
      timer = setInterval(function () {
        var elapsed = (performance.now() - startedAt) / 1000;
        var left = Math.max(0, duration - elapsed);
        fill.style.strokeDashoffset = String(100 * Math.min(1, elapsed / duration));
        setLabel("Recording", left.toFixed(1) + " s left");
        // Stop when the widget reports done or failed, or as a safety a
        // couple seconds past the requested duration.
        var s = status ? status.textContent : "";
        if (/error/i.test(s)) {
          stop();
          setLabel("Couldn't record", "check mic access");
        } else if (/recorded/i.test(s) || elapsed > duration + 2) {
          stop();
          setLabel("Recorded", durLabel);
        }
      }, 100);
    });
  }

  function watchRecordButtons() {
    function scan(root) {
      if (!root || root.nodeType !== 1) return;
      if (root.matches && root.matches(".jupyter-button")) enhanceRecordButton(root);
      if (root.querySelectorAll) {
        root.querySelectorAll(".jupyter-button").forEach(enhanceRecordButton);
      }
    }
    new MutationObserver(function (records) {
      for (var i = 0; i < records.length; i++) {
        var nodes = records[i].addedNodes;
        for (var j = 0; j < nodes.length; j++) scan(nodes[j]);
      }
    }).observe(document.body, { childList: true, subtree: true });
    document.querySelectorAll(".jupyter-button").forEach(enhanceRecordButton);
  }

  // Append the "1.00 s · 44.1 kHz · mono" caption. data: URIs parse
  // synchronously; blob: URLs are fetched, so the caption fills in later.
  function setAudioMeta(body, src) {
    function append(text) {
      if (!text) return;
      var line = document.createElement("span");
      line.className = "audio-output-meta";
      line.textContent = text;
      body.appendChild(line);
    }
    var dataPrefix = "data:audio/wav;base64,";
    if (src.indexOf(dataPrefix) === 0) {
      try {
        var head = atob(src.substr(dataPrefix.length, 96));
        var bytes = new Uint8Array(head.length);
        for (var i = 0; i < head.length; i++) bytes[i] = head.charCodeAt(i);
        append(captionFromWavBytes(bytes));
      } catch (e) {
        /* no caption */
      }
    } else if (src.indexOf("blob:") === 0) {
      fetch(src)
        .then(function (r) { return r.arrayBuffer(); })
        .then(function (buf) { append(captionFromWavBytes(new Uint8Array(buf))); })
        .catch(function () {});
    }
  }

  // Parse a canonical 44-byte RIFF/WAV header into the caption string.
  // Any surprise -> null (no caption), never an error.
  function captionFromWavBytes(bytes) {
    if (bytes.length < 44) return null;
    var str = function (i, n) {
      var r = "";
      for (var k = 0; k < n; k++) r += String.fromCharCode(bytes[i + k]);
      return r;
    };
    if (str(0, 4) !== "RIFF" || str(8, 4) !== "WAVE") return null;
    var u16 = function (i) { return bytes[i] | (bytes[i + 1] << 8); };
    var u32 = function (i) { return u16(i) + u16(i + 2) * 65536; };
    var channels = u16(22);
    var rate = u32(24);
    var bytesPerSecond = u32(28);
    var dataBytes = str(36, 4) === "data" ? u32(40) : bytes.length - 44;
    if (!bytesPerSecond || !rate || !channels) return null;
    var dur = dataBytes / bytesPerSecond;
    var durTxt =
      dur >= 60
        ? Math.floor(dur / 60) + ":" + String(Math.round(dur % 60)).padStart(2, "0") + " min"
        : dur.toFixed(2) + " s";
    var rateTxt = (rate % 1000 === 0 ? rate / 1000 : (rate / 1000).toFixed(1)) + " kHz";
    var chTxt = channels === 1 ? "mono" : channels === 2 ? "stereo" : channels + " channels";
    return durTxt + " · " + rateTxt + " · " + chTxt;
  }
})();
