"""Write _static/wheels/widgets/manifest.json for live-cells.js.

Each entry names a self-hosted wheel and, when PyPI knows the file, its
canonical files.pythonhosted.org URL (a global CDN with immutable caching).
live-cells.js installs from the CDN URL when it answers and falls back to
the self-hosted copy — the book's web host is slow per request, and the
widget stack is ~12 MB on every plotly page. Pure-Python wheels only, so
the PyPI file is byte-identical to what `make wheels` downloaded.
"""

import glob
import json
import os
import sys
import urllib.request

DIR = "_static/wheels/widgets"


def pypi_url(wheel):
    name, version = wheel.split("-")[:2]
    api = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(api, timeout=20) as r:
            files = json.load(r)["urls"]
    except Exception as exc:  # noqa: BLE001 - offline build keeps working
        print(f"  {wheel}: no PyPI URL ({exc})", file=sys.stderr)
        return None
    for f in files:
        if f["filename"] == wheel:
            return f["url"]
    return None


def main():
    wheels = sorted(os.path.basename(p) for p in glob.glob(f"{DIR}/*.whl"))
    entries = [{"name": w, "url": pypi_url(w)} for w in wheels]
    with open(f"{DIR}/manifest.json", "w") as f:
        json.dump(entries, f, indent=1)
    linked = sum(1 for e in entries if e["url"])
    print(f"widget wheel manifest: {len(entries)} wheels, {linked} with PyPI URLs")


if __name__ == "__main__":
    main()
