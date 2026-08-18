.PHONY: book clean spotless all serve check pdf sync-pyquist-readme split merge wheels check-thebe-fork check-split vendor-pyodide template-interactive template-animation

PYQUIST_SUBMODULE  := pyquist
PYQUIST_README_SRC := $(PYQUIST_SUBMODULE)/README.md
PYQUIST_README     := content/book/pyquist/_pyquist_readme.md

all: book

# Regenerate the gitignored book sources from the pinned submodules:
# icm-text/ -> content/book/ch{nn}/ (+ the chapter part of _toc.yml),
# icm-f26/ -> content/course/ (minus unreleased staging dirs), and about/
# errata/refs.bib into content/book/. CI runs this before every `make book`;
# run it locally after cloning or bumping a pin. Only content/book/chNN/
# anim/*.mp4 is committed — unchanged clips are reused byte-identically, so
# the split needs no manim unless a scene changed (then install manim +
# icm_anim and commit the new mp4s with the pin bump).
# WARNING: wipes content/book/ch*/ and content/course/ entirely.
split:
	python3 tools/split_chapters.py

# Inverse of split: reassembles content/ch{nn}/ into icm-text-merged/ for a
# PR up to icm-text. Self-checks that the round-trip is byte-identical.
merge:
	python3 tools/merge_chapters.py

# Regenerate the "Template - Interactive" page: index.ipynb is GENERATED from
# main.md + the notebooks/ folder next to it, the same expansion `make split`
# performs for chapters. Edit the sources, then re-run this. Untouched by
# `make split`.
template-interactive:
	@python3 tools/split_chapters.py --page content/template-interactive --chapter 99 --section 0

# Regenerate the "Template - Animation" page — same model as above, with
# manim companions in notebooks/ pre-rendered into anim/ (commit those mp4s
# too). sec_index=1 keeps its cell ids (ch99s01…) clear of
# template-interactive's (ch99s00…). Untouched by `make split`.
template-animation:
	@python3 tools/split_chapters.py --page content/template-animation --chapter 99 --section 1

# Mirror the Pyquist README from the pinned submodule; runs on every
# `make book`. The sed step rewrites `examples/…` relative links to absolute
# GitHub URLs so they resolve from the book site.
sync-pyquist-readme:
	@test -f $(PYQUIST_README_SRC) || { \
		echo "ERROR: $(PYQUIST_README_SRC) not found — is the submodule initialized?"; \
		echo "  run: git submodule update --init $(PYQUIST_SUBMODULE)"; \
		exit 1; \
	}
	@cp $(PYQUIST_README_SRC) $(PYQUIST_README)
	@sed -i.bak 's|](examples/|](https://github.com/gclef-cmu/pyquist/blob/main/examples/|g' $(PYQUIST_README)
	@rm -f $(PYQUIST_README).bak

# Fetch the pinned thebe runtime bundles for the live-code layer. Self-hosted
# because the kernel web worker must be same-origin. This stack embeds
# pyodide_kernel 0.4.7, which caps the runtime at Pyodide 0.27.x (the pin
# lives in _static/live-cells.js; tools/soundfile_stub fills the gap).
# Cached and gitignored; `rm -rf vendor/thebe-dist` to force a re-fetch.
# IMPORTANT: lives under vendor/ (html_extra_path), NOT _static/ — Jupyter
# Book registers every _static .js as a page script, which would eagerly
# execute the bundle's worker-only chunks and ship ~4 MB on every page. The
# service worker must sit at the site root to get root scope.
THEBE_DIST := vendor/thebe-dist
vendor-thebe:
	@if [ ! -f $(THEBE_DIST)/.ok ]; then \
		echo "Fetching thebe-lite 0.5.0 + thebe 0.9.3 bundles..."; \
		rm -rf $(THEBE_DIST); mkdir -p $(THEBE_DIST)/tmp1 $(THEBE_DIST)/tmp2; \
		curl -sL https://registry.npmjs.org/thebe-lite/-/thebe-lite-0.5.0.tgz | tar xz -C $(THEBE_DIST)/tmp1; \
		curl -sL https://registry.npmjs.org/thebe/-/thebe-0.9.3.tgz | tar xz -C $(THEBE_DIST)/tmp2; \
		mv $(THEBE_DIST)/tmp1/package/dist/lib $(THEBE_DIST)/lite; \
		mv $(THEBE_DIST)/tmp2/package/lib $(THEBE_DIST)/core; \
		rm -rf $(THEBE_DIST)/tmp1 $(THEBE_DIST)/tmp2 $(THEBE_DIST)/lite/*.map $(THEBE_DIST)/core/*.map; \
		cp $(THEBE_DIST)/lite/service-worker.js vendor/service-worker.js; \
		python3 -c "import pathlib; \
			p = pathlib.Path('$(THEBE_DIST)/core/index.js'); \
			s = p.read_text(); \
			cdn = '\"https://cdn.jsdelivr.net/npm/\"'; \
			p.write_text(s.replace(cdn, '(window.__icmWidgetsCdn||' + cdn + ')'))"; \
		touch $(THEBE_DIST)/.ok; \
	fi
	@# ^ the python step patches thebe's widget-frontend loader: its CDN base
	@# (jsdelivr, hardcoded — no config path) becomes overridable so
	@# live-cells.js can point it at the book's own /widgets-cdn/ mirror.

# Self-hosted Pyodide runtime (core + the kernel stack's package closure),
# so widget pages never touch a CDN at runtime. Served at /pyodide/ via
# html_extra_path; version pinned in tools/vendor_pyodide.py, and the
# pyodideUrl in _static/live-cells.js points here.
PYODIDE_DIST := vendor/pyodide
vendor-pyodide:
	@if [ ! -f $(PYODIDE_DIST)/.ok ]; then \
		python3 tools/vendor_pyodide.py && touch $(PYODIDE_DIST)/.ok; \
	fi

# Build the wheels the in-browser kernel installs: pyquist from the pinned
# submodule, icm-widgets, and the browser stubs. Output is gitignored and
# rebuilt on every `make book` so it always matches the submodule pin.
wheels:
	rm -rf _static/wheels
	python3 -m pip wheel --no-deps -q -w _static/wheels ./tools/sounddevice_stub
	python3 -m pip wheel --no-deps -q -w _static/wheels ./tools/soundfile_stub
	python3 -m pip wheel --no-deps -q -w _static/wheels ./tools/icm_widgets
	python3 -m pip wheel --no-deps -q -w _static/wheels ./tools/icm_plotly
	python3 -m pip wheel --no-deps -q -w _static/wheels ./pyquist
	@# plotly.js for baked figures, copied from the installed plotly package
	@# so the JS always matches the build's figure schema. Under vendor/
	@# (html_extra_path), NOT _static — any .js there loads on every page.
	python3 -c "import pathlib, shutil, plotly; \
		src = pathlib.Path(plotly.__file__).parent / 'package_data' / 'plotly.min.js'; \
		dst = pathlib.Path('vendor/plotly-dist'); dst.mkdir(parents=True, exist_ok=True); \
		shutil.copy(src, dst / 'plotly.min.js')"
	@# The plotly widget stack (dependency closure included), self-hosted in
	@# wheels/widgets/ with its own manifest so widget pages never fetch
	@# from PyPI at runtime. live-cells.js installs it per-page, deps=False.
	@# In a subdir on purpose: the main manifest globs _static/wheels/*.whl
	@# and installs on EVERY live page — these only on plotly pages.
	python3 -m pip download -q --no-deps --only-binary=:all: \
		--implementation py --abi none --platform any \
		-d _static/wheels/widgets \
		plotly anywidget ipywidgets narwhals psygnal typing-extensions \
		comm widgetsnbextension jupyterlab-widgets
	python3 -c "import glob, json, os; \
		ws = sorted(os.path.basename(p) for p in glob.glob('_static/wheels/widgets/*.whl')); \
		open('_static/wheels/widgets/manifest.json', 'w').write(json.dumps(ws))"
	@# anywidget's FRONTEND: the widget manager fetches it from a CDN at
	@# render time (npm/anywidget@~X.Y.*/dist/index.js). Serve it ourselves —
	@# live-cells.js points data-jupyter-widgets-cdn at /widgets-cdn/, and the
	@# AMD build ships inside the wheel we just downloaded.
	python3 -c "import glob, pathlib, zipfile; \
		w = glob.glob('_static/wheels/widgets/anywidget-*.whl')[0]; \
		ver = pathlib.Path(w).name.split('-')[1]; \
		major, minor = ver.split('.')[:2]; \
		dst = pathlib.Path('vendor/widgets-cdn/anywidget@~%s.%s.*/dist' % (major, minor)); \
		dst.mkdir(parents=True, exist_ok=True); \
		(dst / 'index.js').write_bytes(zipfile.ZipFile(w).read('anywidget/nbextension/index.js'))"
	@# Install-order manifest for live-cells.js: the stubs must install
	@# before pyquist so micropip treats those dependencies as satisfied and
	@# never fetches the real packages.
	python3 -c "import glob, json, os; \
		ws = sorted(os.path.basename(p) for p in glob.glob('_static/wheels/*.whl')); \
		ws.sort(key=lambda w: 0 if w.startswith(('sounddevice', 'soundfile')) else 1); \
		open('_static/wheels/manifest.json', 'w').write(json.dumps(ws))"

# The live-code page glue needs the TeachBooks sphinx-thebe FORK, but
# upstream ships the same dist name AND version, so a fresh env silently
# keeps upstream — the build succeeds and the deployed pages break in the
# browser. Detect the fork by a file only it ships and fail loudly with the
# fix. (CI force-installs the fork for the same reason.)
check-thebe-fork:
	@python3 -c "import pathlib, sphinx_thebe; \
		raise SystemExit(0 if (pathlib.Path(sphinx_thebe.__file__).parent \
		/ '_static' / 'sphinx-thebe-lite.js').exists() else 1)" || { \
		echo "ERROR: upstream sphinx-thebe is installed; the book needs the TeachBooks fork:"; \
		echo "  pip install --force-reinstall --no-deps 'sphinx-thebe @ git+https://github.com/TeachBooks/Sphinx-Thebe@1f3a80969622b7d63f48f05d8769f5cb933202a0'"; \
		exit 1; }

# content/ is generated (gitignored except anim clips); fail early with the
# fix instead of a confusing missing-toc-file error from jupyter-book.
check-split:
	@test -f content/book/ch00/index.md || { \
		echo "ERROR: generated book sources missing (content/book/ch00/index.md)."; \
		echo "  run: make split   (needs icm-text + icm-f26 submodules initialized)"; \
		exit 1; \
	}

book: check-split check-thebe-fork sync-pyquist-readme wheels vendor-thebe vendor-pyodide
	@# PIP_DISABLE_PIP_VERSION_CHECK: keeps pip's "new release" notice out of
	@# baked %pip cell output. ICM_BOOK_BUILD: kernel-only preview cells
	@# guard on this and build nothing.
	@# content/ is the sourcedir so published URLs carry no content/ prefix;
	@# --toc must be absolute because sphinx-external-toc resolves relative
	@# paths against the sourcedir.
	PIP_DISABLE_PIP_VERSION_CHECK=1 ICM_BOOK_BUILD=1 jupyter-book build content/ \
		--path-output "$(CURDIR)" --config "$(CURDIR)/_config.yml" --toc "$(CURDIR)/_toc.yml"
	@# Sphinx doesn't track files referenced by raw <img>/<audio>/<video>
	@# HTML tags, so copy each chapter's assets and pre-rendered anim clips
	@# into the build output ourselves (dest drops the content/ prefix).
	@for d in content/book/ch*/assets content/book/ch*/anim content/template-animation/anim; do \
		[ -d "$$d" ] || continue; \
		dest="_build/html/$$(dirname "$${d#content/}")"; \
		mkdir -p "$$dest"; \
		cp -R "$$d" "$$dest/"; \
	done

clean:
	jupyter-book clean ./

spotless:
	jupyter-book clean ./ --all

serve: book
	python -m http.server --directory _build/html/

check: check-split
	jupyter-book build content/ --path-output "$(CURDIR)" --config "$(CURDIR)/_config.yml" \
		--toc "$(CURDIR)/_toc.yml" --builder linkcheck

pdf: check-split
	jupyter-book build content/ --path-output "$(CURDIR)" --config "$(CURDIR)/_config.yml" \
		--toc "$(CURDIR)/_toc.yml" --builder pdflatex
