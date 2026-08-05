"""Self-host the Pyodide runtime under vendor/pyodide/.

Downloads the core runtime plus the dependency closure (resolved from
pyodide-lock.json) of the packages the live-code bootstrap loads, so widget
pages never touch a CDN at runtime. Also writes warm-manifest.json — the
full file list — which live-cells.js fetches on prose pages to pre-warm the
browser cache before a student reaches a widget page.

Run via `make vendor-pyodide` (skips itself when the .ok stamp exists).
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

VERSION = "0.27.7"
CDN = f"https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/"
DEST = pathlib.Path("vendor/pyodide")

# The runtime itself.
CORE = [
    "pyodide.js",
    "pyodide.asm.js",
    "pyodide.asm.wasm",
    "python_stdlib.zip",
    "pyodide-lock.json",
]

# What the kernel stack needs from the distribution: the bootstrap
# loadPackage list (live-cells.js) plus what the jupyterlite pyodide
# kernel loads at boot (ssl/sqlite3 and the ipython stack). Closures
# come from the lock file.
ROOTS = [
    "numpy", "matplotlib", "soxr", "requests", "tqdm",
    "micropip", "packaging", "ssl", "sqlite3",
    "ipython", "matplotlib-inline",
    # Not preloaded by the bootstrap: the kernel auto-loads these from the
    # vendored distribution when a cell imports them.
    "scipy",
]


def fetch(name: str) -> bytes:
    with urllib.request.urlopen(CDN + name) as r:
        return r.read()


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    lock = json.loads(fetch("pyodide-lock.json"))
    packages = lock["packages"]

    todo, seen = list(ROOTS), set()
    files: set[str] = set(CORE)
    while todo:
        name = todo.pop()
        # lock keys are lowercase with hyphens; depends lists use the same
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        seen.add(key)
        pkg = packages.get(key) or packages.get(key.replace("-", "_"))
        if pkg is None:
            sys.exit(f"vendor_pyodide: {name!r} not in the {VERSION} lock file")
        files.add(pkg["file_name"])
        todo.extend(pkg.get("depends", []))

    total = 0
    for name in sorted(files):
        out = DEST / name
        if not out.exists():
            data = fetch(name)
            out.write_bytes(data)
        total += out.stat().st_size
    (DEST / "warm-manifest.json").write_text(json.dumps(sorted(files)))
    print(f"vendor/pyodide: {len(files)} files, {total / 1e6:.1f} MB "
          f"({len(seen)} packages)")


if __name__ == "__main__":
    main()
