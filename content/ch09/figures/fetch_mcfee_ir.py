"""Fetch Brian McFee's room impulse-response animation and save it as a GIF.

The animation lives in the built HTML of the _Digital Signals Theory_ site
(chapter 3, Convolution) as a matplotlib jshtml animation whose frames are
embedded as base64 PNGs. We download that page, decode the frames, subsample
for size, and assemble ../assets/fig-room-ir.gif.

This figure is reproduced from _Digital Signals Theory_ by Brian McFee and is
credited to that book in the chapter. Run only to (re)generate the asset:
    ../../../.venv/bin/python fetch_mcfee_ir.py
"""

import base64
import io
import re
import urllib.request
from pathlib import Path

from PIL import Image

SRC = ("https://raw.githubusercontent.com/bmcfee/dstbook-site/main/"
       "content/ch03-convolution/IR.html")
ASSETS = Path(__file__).resolve().parent.parent / "assets"


def main() -> None:
    html = urllib.request.urlopen(SRC).read().decode("utf-8", "replace")
    b64 = re.findall(r'frames\[\d+\] = "data:image/png;base64,([^"]+)"', html)
    if not b64:
        raise RuntimeError("no animation frames found in IR.html")
    frames = [Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB") for b in b64]
    print(f"decoded {len(frames)} frames at {frames[0].size}")

    sub = frames[::5] + [frames[-1]] * 12          # subsample + hold on the end

    # Build one rich 256-colour palette from a montage of colour-heavy frames
    # (wavefront + reflections present), so anti-aliased edges are preserved.
    W, H = frames[0].size
    picks = [frames[i] for i in (100, 180, 256, 340, 420)]
    montage = Image.new("RGB", (W, H * len(picks)))
    for j, im in enumerate(picks):
        montage.paste(im, (0, H * j))
    pal = montage.convert("P", palette=Image.ADAPTIVE, colors=256)
    sub_p = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in sub]

    out = ASSETS / "fig-room-ir.gif"
    sub_p[0].save(out, save_all=True, append_images=sub_p[1:], duration=65,
                  loop=0, disposal=1)
    print(f"wrote {out} ({out.stat().st_size // 1024} kB, {len(sub_p)} frames)")


if __name__ == "__main__":
    main()
