"""One-click showcase pipeline for examples/skull_hoodie_girl."""
from __future__ import annotations

import sys
from pathlib import Path

EXAMPLE_DIR = Path(__file__).resolve().parent
REPO_ROOT = EXAMPLE_DIR.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

from build_animations import main as build_anims_main
from build_model import main as build_model_main
from ysm_engine import (
    package_all,
    render_clay_turnaround,
    render_closeups,
    render_overlay_compare,
    render_poses,
    render_skeleton_pivots,
    render_turnaround_compare,
)
from ysm_engine.analyze_ref import analyze_reference


def main():
    ref_img = EXAMPLE_DIR / "reference" / "reference_3view.jpg"
    ref_dir = EXAMPLE_DIR / "reference"
    crops_dir = ref_dir / "crops"
    pack_dir = EXAMPLE_DIR / "out" / "skull_hoodie_girl"
    renders_dir = EXAMPLE_DIR / "renders"

    analyze_reference(ref_img, ref_dir, target_height_u=34.0, expected_views=3)
    build_model_main()
    build_anims_main()
    package_all(pack_dir, out_dir=EXAMPLE_DIR / "out")

    geo = pack_dir / "models" / "main.json"
    tex = pack_dir / "textures" / "default.png"
    anim = pack_dir / "animations" / "main.animation.json"

    render_turnaround_compare(geo, tex, crops_dir, renders_dir / "turnaround.png")
    render_clay_turnaround(geo, tex, renders_dir / "clay.png")
    render_closeups(geo, tex, crops_dir, renders_dir / "closeups.png")
    render_overlay_compare(
        geo, tex, crops_dir / "ref_front.png", renders_dir / "head_overlay.png",
        yaw_deg=0.0, y_min=22.0, y_max=34.6, half_w_u=6.3, title="Front Head",
    )
    render_poses(geo, tex, anim, None, renders_dir / "poses.png")
    render_skeleton_pivots(geo, tex, renders_dir / "skeleton.png")
    print(f"All outputs ready under {EXAMPLE_DIR / 'out'} and {renders_dir}")


if __name__ == "__main__":
    main()
