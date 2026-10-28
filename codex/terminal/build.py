"""Extend the checksum-pinned ttyd client at build time, without external assets.

Keep ttyd's own authentication, ingress paths, reconnect and flow control. Fail
the image build if a future ttyd release no longer exposes its terminal API.
"""
import re
import sys
import zlib
from pathlib import Path


def build(binary, destination):
    content = Path(binary).read_bytes()
    for match in re.finditer(b"\x1f\x8b\x08", content):
        try:
            html = zlib.decompress(content[match.start():], 31).decode("utf-8")
        except (zlib.error, UnicodeDecodeError):
            continue
        if "</body>" in html and "window.term=" in html:
            break
    else:
        raise RuntimeError("Pinned ttyd HTML / window.term API not found")
    root = Path(__file__).parent
    # ttyd's bundled page omits this, leaving phones with a ~980px layout.
    if not re.search(r'<meta\s+[^>]*name=["\']viewport["\']', html, re.I):
        html = html.replace('</head>', '<meta name="viewport" content="width=device-width, initial-scale=1"></head>')
    extension = ("<style>" + (root / "toolbar.css").read_text() + "</style>"
                 "<script>" + (root / "toolbar.js").read_text() + "</script>")
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html.replace("</body>", extension + "</body>"), encoding="utf-8")


if __name__ == "__main__":
    build(*sys.argv[1:])
