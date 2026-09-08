#!/usr/bin/env python3
"""Serve the built site with HTTP Range support.

`python -m http.server` answers every Range request with the whole file, so
Chrome treats audio and video as unseekable and every seek snaps back to the
start. Production (Apache) serves ranges; this does too, for local previews.

    python3 tools/serve.py 8774 _build/html
"""
import functools
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

_RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


class RangeHandler(SimpleHTTPRequestHandler):
    range_length = None  # bytes left to copy for a 206 response

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        self.range_length = None
        path = self.translate_path(self.path)
        m = _RANGE.match(self.headers.get("Range", ""))
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        if m.group(1):
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
        else:  # suffix range: the last N bytes
            start = max(0, size - int(m.group(2)))
            end = size - 1
        end = min(end, size - 1)
        if start > end or start >= size:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header(
            "Last-Modified", self.date_time_string(os.fstat(f.fileno()).st_mtime)
        )
        self.end_headers()
        self.range_length = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        if self.range_length is None:
            return super().copyfile(source, outputfile)
        remaining = self.range_length
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self.range_length = None


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8774
    directory = sys.argv[2] if len(sys.argv) > 2 else "_build/html"
    handler = functools.partial(RangeHandler, directory=directory)
    print(f"Serving {directory} on http://localhost:{port}/ (Range-capable)")
    ThreadingHTTPServer(("", port), handler).serve_forever()


if __name__ == "__main__":
    main()
