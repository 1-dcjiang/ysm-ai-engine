"""Automated tests for the zero-dependency WebGL2 YSM 3D Viewer server."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ysm_engine.viewer import create_server


class TestYsmViewerServer(unittest.TestCase):
    def test_viewer_serves_static_and_demo_info_without_model(self):
        httpd = create_server(model_dir=None, host="127.0.0.1", port=0)
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
                self.assertEqual(resp.status, 200)
                html = resp.read().decode("utf-8")
                self.assertIn("glCanvas", html)

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/js/app.js") as resp:
                self.assertEqual(resp.status, 200)

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/demo-info") as resp:
                self.assertEqual(resp.status, 200)
                info = json.loads(resp.read().decode("utf-8"))
                self.assertFalse(info["available"])
                self.assertEqual(info["files"], [])
        finally:
            httpd.shutdown()
            httpd.server_close()

    def test_viewer_serves_explicit_model_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            pack = Path(tmp) / "demo_pack"
            (pack / "models").mkdir(parents=True)
            (pack / "models" / "main.json").write_text('{"format_version":"1.12.0"}', encoding="utf-8")

            httpd = create_server(model_dir=pack, host="127.0.0.1", port=0)
            port = httpd.server_address[1]
            t = threading.Thread(target=httpd.serve_forever, daemon=True)
            t.start()
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/demo-info") as resp:
                    info = json.loads(resp.read().decode("utf-8"))
                    self.assertTrue(info["available"])
                    self.assertEqual(info["name"], "demo_pack")
                    self.assertIn("models/main.json", info["files"])

                with urllib.request.urlopen(f"http://127.0.0.1:{port}/demo/model/models/main.json") as resp:
                    self.assertEqual(resp.status, 200)
                    self.assertIn("1.12.0", resp.read().decode("utf-8"))
            finally:
                httpd.shutdown()
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
