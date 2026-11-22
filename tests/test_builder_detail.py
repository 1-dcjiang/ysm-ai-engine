"""Regression tests for the per-face UV density builder feature."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ysm_engine import YSMModel


class BuilderDetailTests(unittest.TestCase):
    def test_face_uv_scale_increases_selected_face_detail(self):
        m = YSMModel(texture_width=128, texture_height=128, texels_per_unit=2.0)
        m.add_bone("All")
        cube = m.add_cube(
            "All",
            origin=(0, 0, 0),
            size=(4, 4, 4),
            solid_color="#FFFFFF",
            face_uv_scale={"north": 4.0},
        )

        self.assertEqual(cube["uv"]["north"]["uv_size"], [16, 16])
        self.assertEqual(cube["uv"]["south"]["uv_size"], [8, 8])

    def test_mirrored_cube_swaps_face_uv_scales(self):
        m = YSMModel(texture_width=128, texture_height=128, texels_per_unit=2.0)
        m.add_bone("RightArm")
        m.add_bone("LeftArm")
        right, left = m.add_mirrored_cube(
            "RightArm",
            "LeftArm",
            origin=(-4, 0, 0),
            size=(4, 4, 4),
            solid_color="#FFFFFF",
            face_uv_scale={"east": 4.0, "west": 2.0},
        )

        self.assertEqual(right["uv"]["east"]["uv_size"], [16, 16])
        self.assertEqual(left["uv"]["west"]["uv_size"], [16, 16])
        self.assertEqual(left["uv"]["east"]["uv_size"], [8, 8])

    def test_unknown_face_uv_scale_key_is_rejected(self):
        m = YSMModel(texture_width=128, texture_height=128, texels_per_unit=2.0)
        m.add_bone("All")

        with self.assertRaises(ValueError):
            m.add_cube(
                "All",
                origin=(0, 0, 0),
                size=(4, 4, 4),
                solid_color="#FFFFFF",
                face_uv_scale={"front": 4.0},
            )


if __name__ == "__main__":
    unittest.main()
