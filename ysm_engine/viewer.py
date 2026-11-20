"""
Zero-dependency local HTTP server for the YSM WebGL2 3D Viewer.

Usage:
  ysm-viewer                              # Launch viewer (auto-detects local example out/ if built)
  ysm-viewer path/to/unpacked_ysm_pack    # Launch viewer preloaded with a specific YSM pack directory
  python -m ysm_engine.viewer --port 8765 --no-browser
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import mimetypes
import socketserver
import threading
import webbrowser
from pathlib import Path
from typing import Optional

STATIC_DIR = Path(__file__).resolve().parent / "viewer_static"

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("text/css", ".css")


def _discover_model_dir(explicit: Optional[str]) -> Optional[Path]:
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if (p / "models" / "main.json").is_file() or (p / "ysm.json").is_file():
            return p
        raise FileNotFoundError(f"Model directory does not look like an unpacked YSM pack: {p}")

    # Optional convenience: auto-detect locally built example if user already ran run_all.py
    candidates = [
        Path.cwd() / "examples" / "skull_hoodie_girl" / "out" / "skull_hoodie_girl",
        Path(__file__).resolve().parent.parent / "examples" / "skull_hoodie_girl" / "out" / "skull_hoodie_girl",
    ]
    for c in candidates:
        if (c / "models" / "main.json").is_file():
            return c.resolve()
    return None


def _collect_pack_files(model_dir: Path) -> list[str]:
    files: list[str] = []
    for f in sorted(model_dir.rglob("*")):
        if f.is_file():
            files.append(f.relative_to(model_dir).as_posix())
    return files


class _ViewerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, model_dir: Optional[Path] = None, **kwargs):
        self.model_dir = model_dir
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def translate_path(self, path: str) -> str:
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/demo/model/") and self.model_dir is not None:
            rel = clean[len("/demo/model/"):].lstrip("/")
            candidate = (self.model_dir / rel).resolve()
            if self.model_dir == candidate or self.model_dir in candidate.parents:
                return str(candidate)
        rel = clean.lstrip("/") or "index.html"
        return str((STATIC_DIR / rel).resolve())

    def do_GET(self):
        clean = self.path.split("?", 1)[0].split("#", 1)[0]
        if clean == "/api/demo-info":
            if self.model_dir is not None and self.model_dir.is_dir():
                payload = {
                    "available": True,
                    "name": self.model_dir.name,
                    "files": _collect_pack_files(self.model_dir),
                }
            else:
                payload = {"available": False, "name": None, "files": []}
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args):
        # Keep console output clean unless debugging
        pass


def create_server(
    model_dir: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> socketserver.TCPServer:
    socketserver.TCPServer.allow_reuse_address = True
    handler = functools.partial(_ViewerHandler, model_dir=model_dir)
    return socketserver.TCPServer((host, port), handler)


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(
        prog="ysm-viewer",
        description="Launch the local WebGL2 3D YSM Model Viewer & Pose Studio.",
    )
    parser.add_argument(
        "model_dir",
        nargs="?",
        default=None,
        help="Optional unpacked YSM model directory to preload on startup.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8765, help="Bind port (default: 8765)")
    parser.add_argument("--no-browser", action="store_true", help="Do not auto-open the web browser")
    args = parser.parse_args(argv)

    model_dir = _discover_model_dir(args.model_dir)
    httpd = create_server(model_dir=model_dir, host=args.host, port=args.port)
    actual_port = httpd.server_address[1]
    url = f"http://{args.host}:{actual_port}/"

    print(f"YSM 3D Studio Viewer running at {url}", flush=True)
    if model_dir:
        print(f"Preloaded local model directory: {model_dir}", flush=True)
    else:
        print("No preloaded model directory; drag & drop any .zip / .bbmodel / folder in the browser.", flush=True)

    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
