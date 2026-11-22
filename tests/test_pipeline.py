"""End-to-end automated regression tests for ysm-ai-engine."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ysm_engine import (
    BedrockScene,
    REQUIRED_BONES,
    REQUIRED_MAIN_ANIMS,
    YSMModel,
    package_all,
    render_clay_turnaround,
    render_closeups,
    render_overlay_compare,
    render_poses,
    render_skeleton_pivots,
    render_turnaround_compare,
    render_view,
    validate_pack,
)


def _make_minimal_pack(root: Path) -> Path:
    pack = root / "minimal_test_pack"
    m = YSMModel(texture_width=256, texture_height=256, texels_per_unit=2.0)

    m.add_bone("All", pivot=(0, 0, 0))
    m.add_bone("Waist", parent="All", pivot=(0, 12, 0))
    m.add_bone("Body", parent="Waist", pivot=(0, 12, 0))
    m.add_bone("ElytraLocator", parent="Body", pivot=(0, 22, 2))
    m.add_bone("BackpackLocator", parent="Body", pivot=(0, 18, 2))
    m.add_bone("LeftShoulderLocator", parent="Body", pivot=(4, 24, 0))
    m.add_bone("RightShoulderLocator", parent="Body", pivot=(-4, 24, 0))

    m.add_bone("AllHead", parent="Body", pivot=(0, 24, 0))
    m.add_bone("Head", parent="AllHead", pivot=(0, 24, 0))
    m.add_bone("ViewLocator", parent="Head", pivot=(0, 28, 0))

    m.add_bone("RightArm", parent="Body", pivot=(-5, 22, 0), rotation=(0, 0, 5))
    m.add_bone("RightHand", parent="RightArm", pivot=(-5, 14, 0))
    m.add_bone("RightHandLocator", parent="RightHand", pivot=(-5, 13, 0))

    m.add_bone("LeftArm", parent="Body", pivot=(5, 22, 0), rotation=(0, 0, -5))
    m.add_bone("LeftHand", parent="LeftArm", pivot=(5, 14, 0))
    m.add_bone("LeftHandLocator", parent="LeftHand", pivot=(5, 13, 0))

    m.add_bone("RightLeg", parent="Waist", pivot=(-2, 12, 0))
    m.add_bone("LeftLeg", parent="Waist", pivot=(2, 12, 0))

    m.add_cube("Body", origin=(-4, 12, -2), size=(8, 12, 4), vgradient=("#F5F3FA", "#5D596E"))
    m.add_cube("Head", origin=(-4, 24, -4), size=(8, 8, 8), solid_color="#FCF1F2")
    m.add_mirrored_cube("RightArm", "LeftArm", origin=(-7, 12, -2), size=(3, 12, 4), solid_color="#EAE4F7")
    m.add_mirrored_cube("RightLeg", "LeftLeg", origin=(-4, 0, -2), size=(4, 12, 4), solid_color="#4D4A5D")

    m.export_main_json(pack / "models" / "main.json")
    m.export_arm_json(pack / "models" / "arm.json")
    m.export_texture(pack / "textures" / "default.png")

    anims = {
        name: {"loop": True, "animation_length": 1.0, "bones": {"Body": {"rotation": [0, 0, 0]}}}
        for name in REQUIRED_MAIN_ANIMS
    }
    (pack / "animations").mkdir(parents=True, exist_ok=True)
    (pack / "animations" / "main.animation.json").write_text(
        json.dumps({"format_version": "1.8.0", "animations": anims}, indent=2),
        encoding="utf-8",
    )
    (pack / "animations" / "arm.animation.json").write_text(
        json.dumps({"format_version": "1.8.0", "animations": {"use_mainhand:eat": {"loop": True, "bones": {"RightArm": {"rotation": [-70, 20, 0]}}}}}, indent=2),
        encoding="utf-8",
    )
    (pack / "ysm.json").write_text(
        json.dumps(
            {
                "spec": 2,
                "metadata": {"name": "Minimal Test Pack"},
                "files": {
                    "player": {
                        "model": {"main": "models/main.json", "arm": "models/arm.json"},
                        "animation": {
                            "main": "animations/main.animation.json",
                            "arm": "animations/arm.animation.json",
                        },
                        "texture": ["textures/default.png"],
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return pack


class PipelineTests(unittest.TestCase):
    def test_build_validate_render_and_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pack = _make_minimal_pack(tmp_path)

            # 1. Validation passes with 0 errors
            errors = validate_pack(pack, quiet=True)
            self.assertEqual(errors, [])

            # 2. arm.json has root arms with [0,0,0] rotation
            arm_geo = json.loads((pack / "models" / "arm.json").read_text(encoding="utf-8"))
            arm_bones = {b["name"]: b for b in arm_geo["minecraft:geometry"][0]["bones"]}
            self.assertIn("RightArm", arm_bones)
            self.assertIn("LeftArm", arm_bones)
            self.assertEqual(arm_bones["RightArm"]["rotation"], [0.0, 0.0, 0.0])
            self.assertNotIn("parent", arm_bones["RightArm"])

            # 3. Renderer functions work cleanly across auto-framing, SSAO, clay, poses, overlay
            geo = pack / "models" / "main.json"
            tex = pack / "textures" / "default.png"
            scene = BedrockScene(geo, tex)
            bmin, bmax = scene.compute_bounds()
            self.assertAlmostEqual(float(bmin[1]), 0.0, delta=0.5)
            self.assertAlmostEqual(float(bmax[1]), 32.0, delta=0.5)

            im_p = render_view(scene, 120, 180, yaw_deg=-24, ortho_scale=None, ssao=True)
            self.assertEqual(im_p.size, (120, 180))

            t_out = render_turnaround_compare(geo, tex, None, tmp_path / "turn.png")
            c_out = render_clay_turnaround(geo, tex, tmp_path / "clay.png")
            z_out = render_closeups(geo, tex, None, tmp_path / "close.png")
            p_out = render_poses(geo, tex, pack / "animations" / "main.animation.json", None, tmp_path / "poses.png")
            s_out = render_skeleton_pivots(geo, tex, tmp_path / "skel.png")
            ov_ref = tmp_path / "ref_dummy.png"
            im_p.save(ov_ref)
            o_out = render_overlay_compare(geo, tex, ov_ref, tmp_path / "ov.png")

            for fpath in (t_out, c_out, z_out, p_out, s_out, o_out):
                self.assertTrue(fpath.exists() and fpath.stat().st_size > 1000)

            # 4. Packaging produces valid zip & bbmodel
            zip_p, bb_p = package_all(pack, out_dir=tmp_path / "out", quiet=True)
            self.assertTrue(zip_p.exists())
            self.assertIsNotNone(bb_p)
            self.assertTrue(bb_p.exists())
            with zipfile.ZipFile(zip_p, "r") as zf:
                names = set(zf.namelist())
                self.assertIn("minimal_test_pack/ysm.json", names)
                self.assertIn("minimal_test_pack/models/main.json", names)
                self.assertIn("minimal_test_pack/models/arm.json", names)


if __name__ == "__main__":
    unittest.main()
