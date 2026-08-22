"""Serve anywidget's frontend from the book, patched for thebe.

thebe's widget manager loads third-party widget frontends over RequireJS
running in a hidden iframe. anywidget's AMD build ships inside its wheel
(downloaded by `make wheels`), so copy it to vendor/widgets-cdn/ under the
path the manager requests, and route its import() through the page's
window.__icmImport (live-cells.js): widget ESM has to evaluate in the page
realm, or libraries like plotly get the iframe's display:none document and
never-resizing window.

The bundle lands under a content-hash directory (vendor/widgets-cdn/<hash>/),
named by vendor/widgets-cdn/manifest.json, which live-cells.js fetches
uncached: the manager's module URL carries no version of its own, and a
rebuilt bundle at an unchanged URL kept serving stale from browser caches.
"""

import glob
import hashlib
import json
import pathlib
import shutil
import sys
import zipfile

HELPER = """\
// thebe runs this file through RequireJS inside a hidden iframe; import
// widget ESM via the page's helper (live-cells.js) so it evaluates in the
// page realm, with the real document and window.
var __icmImport = function (u) {
  try {
    var p = window.parent;
    if (p && p !== window && typeof p.__icmImport === "function") return p.__icmImport(u);
  } catch (e) {}
  return import(u);
};

"""


def main():
    wheels = glob.glob("_static/wheels/widgets/anywidget-*.whl")
    if not wheels:
        sys.exit("anywidget wheel missing in _static/wheels/widgets; run the pip download step first")
    wheel = wheels[0]
    ver = pathlib.Path(wheel).name.split("-")[1]
    major, minor = ver.split(".")[:2]
    js = zipfile.ZipFile(wheel).read("anywidget/nbextension/index.js").decode()
    n = js.count("await import(")
    if n != 2:
        sys.exit(
            f"anywidget {ver}: expected 2 'await import(' sites in nbextension/index.js, "
            f"found {n}; re-check the realm patch in tools/vendor_anywidget.py"
        )
    js = HELPER + js.replace("await import(", "await __icmImport(")
    digest = hashlib.sha256(js.encode()).hexdigest()[:10]
    root = pathlib.Path("vendor/widgets-cdn")
    root.mkdir(parents=True, exist_ok=True)
    for stale in root.iterdir():  # previous hashes and the old unhashed layout
        if stale.is_dir() and stale.name != digest:
            shutil.rmtree(stale)
    dst = root / digest / f"anywidget@~{major}.{minor}.*" / "dist"
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "index.js").write_text(js)
    (root / "manifest.json").write_text(json.dumps({"base": digest + "/"}))
    print(f"vendored anywidget {ver} frontend -> {dst}/index.js")


if __name__ == "__main__":
    main()
