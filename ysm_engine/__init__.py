"""
ysm-ai-engine: Procedural Minecraft YSM (Yes Steve Model) 2.6.0 modeling,
SSAO 3D software rendering, and validation toolkit designed for AI agents.
"""
from __future__ import annotations

from .builder import (
    ALL_FACES,
    ShelfPacker,
    YSMModel,
    lerp_color,
    make_hgradient_patch,
    make_solid_patch,
    make_vgradient_patch,
    parse_color,
    shade_color,
    tint_color,
)
from .export_bbmodel import export_bbmodel
from .package import package_all
from .renderer import (
    BedrockScene,
    compare_silhouettes,
    evaluate_animation,
    render_clay_turnaround,
    render_closeups,
    render_overlay_compare,
    render_poses,
    render_skeleton_pivots,
    render_turnaround_compare,
    render_view,
)
from .validate import REQUIRED_BONES, REQUIRED_MAIN_ANIMS, validate_pack

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "ALL_FACES",
    "BedrockScene",
    "compare_silhouettes",
    "REQUIRED_BONES",
    "REQUIRED_MAIN_ANIMS",
    "ShelfPacker",
    "YSMModel",
    "evaluate_animation",
    "export_bbmodel",
    "lerp_color",
    "make_hgradient_patch",
    "make_solid_patch",
    "make_vgradient_patch",
    "package_all",
    "parse_color",
    "render_clay_turnaround",
    "render_closeups",
    "render_overlay_compare",
    "render_poses",
    "render_skeleton_pivots",
    "render_turnaround_compare",
    "render_view",
    "shade_color",
    "tint_color",
    "validate_pack",
]
