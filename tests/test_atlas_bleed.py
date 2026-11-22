"""Regression tests for the atlas edge-bleed gutter."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from ysm_engine import YSMModel


RED = (220, 40, 40, 255)
BLUE = (40, 80, 220, 255)
GREEN = (40, 200, 80, 255)
YELLOW = (230, 210, 40, 255)
WHITE = (250, 250, 250, 255)
GREY = (150, 150, 150, 255)


def _edge_painter(face: str, w: int, h: int) -> np.ndarray:
    """North face gets one distinct colour per edge; other faces stay grey."""
    if face != "north":
        return np.full((h, w, 4), GREY, dtype=np.uint8)
    patch = np.full((h, w, 4), WHITE, dtype=np.uint8)
    patch[0, :] = GREEN
    patch[-1, :] = YELLOW
    patch[:, 0] = RED
    patch[:, -1] = BLUE
    return patch


class AtlasBleedTests(unittest.TestCase):
    def _directional_model(self, atlas_bleed: int = 1) -> YSMModel:
        m = YSMModel(
            texture_width=64,
            texture_height=64,
            texels_per_unit=1.0,
            atlas_bleed=atlas_bleed,
        )
        m.add_bone("Head")
        m.add_cube(
            "Head",
            origin=(0, 0, 0),
            size=(8, 8, 8),
            face_painter=_edge_painter,
            face_dims_override={"north": (8, 8)},
        )
        return m

    def test_bleed_fills_each_edge_with_its_own_colour(self):
        m = self._directional_model()
        cube = m.bones["Head"]["cubes"][0]
        u, v = cube["uv"]["north"]["uv"]
        uw, vh = cube["uv"]["north"]["uv_size"]

        with tempfile.TemporaryDirectory() as tmp:
            m.export_texture(Path(tmp) / "tex.png")

        atlas = m.atlas
        self.assertEqual(atlas[v + 1, u - 1].tolist(), list(RED))
        self.assertEqual(atlas[v + 1, u + uw].tolist(), list(BLUE))
        self.assertEqual(atlas[v - 1, u + 1].tolist(), list(GREEN))
        self.assertEqual(atlas[v + vh, u + 1].tolist(), list(YELLOW))

        # Corners copy the actual corner pixel, not a neighbour's gutter.
        self.assertEqual(atlas[v - 1, u - 1].tolist(), atlas[v, u].tolist())
        self.assertEqual(atlas[v + vh, u + uw].tolist(), atlas[v + vh - 1, u + uw - 1].tolist())

    def test_neighbouring_faces_do_not_tint_each_other(self):
        m = YSMModel(texture_width=128, texture_height=64, texels_per_unit=2.0)
        m.add_bone("A")
        m.add_bone("B")
        red = m.add_cube("A", origin=(0, 0, 0), size=(4, 4, 4), solid_color="#DC2828")
        blue = m.add_cube("B", origin=(8, 0, 0), size=(4, 4, 4), solid_color="#2850DC")

        with tempfile.TemporaryDirectory() as tmp:
            m.export_texture(Path(tmp) / "tex.png")

        atlas = m.atlas
        for cube, expected in ((red, RED), (blue, BLUE)):
            for rect in cube["uv"].values():
                u, v = rect["uv"]
                uw, vh = rect["uv_size"]
                for du in range(-1, uw + 1):
                    for dv in (-1, vh):
                        y, x = v + dv, u + du
                        if 0 <= y < atlas.shape[0] and 0 <= x < atlas.shape[1]:
                            self.assertEqual(
                                atlas[y, x].tolist(), list(expected),
                                f"bleed at ({x},{y}) leaked a neighbour colour",
                            )
                for dv in range(vh):
                    for du in (-1, uw):
                        y, x = v + dv, u + du
                        if 0 <= y < atlas.shape[0] and 0 <= x < atlas.shape[1]:
                            self.assertEqual(
                                atlas[y, x].tolist(), list(expected),
                                f"bleed at ({x},{y}) leaked a neighbour colour",
                            )

    def test_bleed_can_be_disabled(self):
        m = YSMModel(texture_width=64, texture_height=64, texels_per_unit=1.0, atlas_bleed=0)
        m.add_bone("Head")
        cube = m.add_cube("Head", origin=(0, 0, 0), size=(8, 8, 8), solid_color="#FFFFFF")
        u, v = cube["uv"]["north"]["uv"]
        uw = cube["uv"]["north"]["uv_size"][0]

        with tempfile.TemporaryDirectory() as tmp:
            m.export_texture(Path(tmp) / "tex.png")

        self.assertEqual((u, v), (0, 0))
        self.assertEqual(m.packer.border, 0)
        self.assertEqual(m.atlas[v, u + uw, 3], 0)

    def test_bleed_keeps_atlas_used_height_reported(self):
        m = self._directional_model()
        with tempfile.TemporaryDirectory() as tmp:
            m.export_texture(Path(tmp) / "tex.png")
        self.assertEqual(m.stats()["atlas_bleed"], 1)
        self.assertGreater(m.stats()["atlas_used_y"], 8)


if __name__ == "__main__":
    unittest.main()
