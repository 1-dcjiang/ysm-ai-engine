"""
Procedural YSM 2.6.0 Model Builder for Skull Hoodie Girl (skull_hoodie_girl).
Phase 3.5: Front-Head Fidelity Overhaul — Dedicated Separate Eye Layer (exact 3x2 pixel eyes),
           Flush-Sculpted Rounded Skull Hood, and Broad Overlapping Sheet Hair ("一片一片的").

Coordinate System (Bedrock 1.12.0):
  +Y : Up (y = 0 ground, crown = 34.0u)
  -Z : Front (character faces -Z)
  +Z : Back
  -X : Character's RIGHT (Viewer's LEFT in front view)
  +X : Character's LEFT  (Viewer's RIGHT in front view)
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ysm_engine import (
    YSMModel,
    lerp_color,
    make_solid_patch,
    make_vgradient_patch,
    parse_color,
)

# ==============================================================================
# Color Palette (Calibrated directly against reference_3view.jpg & superzooms)
# ==============================================================================
HOOD_TOP = "#FBF9FF"
HOOD_LIGHT = "#F6F4FC"
HOOD_MID = "#ECE9F5"
HOOD_SHADE = "#DCD8EA"
HOOD_DEEP = "#C6C1D8"
HOOD_INNER = "#B8B2CC"

# Airy Milky-White with Ultra-Light Pale Lavender Tint ("白色带特别浅的淡紫色" matching reference_3view!)
HAIR_BRIGHT = "#F7F4FD"
HAIR_HIGHLIGHT = "#F2EEFA"
HAIR_LIGHT = "#EBE6F7"
HAIR_MID = "#E3DDF2"
HAIR_SHADE = "#D7D0EB"
HAIR_DEEP = "#C9C0E2"
HAIR_SHADOW = "#B9AED8"

DARK_BLACK = "#3E3B4D"
DARK_SOCKET_TOP = "#3C394B"
DARK_SOCKET_BOT = "#58546A"
DARK_CHARCOAL = "#4D4A5D"
DARK_MID = "#5D596E"
DARK_PLEAT = "#434052"

SKIN_LIGHT = "#FCF1F2"
SKIN_MID = "#F8E7EB"
SKIN_BLUSH = "#EECCD7"
SKIN_SHADE = "#DDB9C5"

# Exact superzoom_face.png MC pixel colors for the dedicated 3x2 Eye Layer
EYE_LASH = "#49465B"
EYE_IRIS_OUT_T = "#7D7996"  # upper outer iris pixel
EYE_IRIS_IN_T = "#8B87A4"   # upper inner iris pixel
EYE_IRIS_OUT_B = "#B5B1CA"  # lower outer iris pixel
EYE_IRIS_IN_B = "#CCC8DF"   # lower inner iris pixel
EYE_SCLERA_T = "#B8B3C9"    # upper sclera pixel (shaded by lash)
EYE_SCLERA_B = "#F4F2FA"    # lower sclera pixel (bright white)

CLOTH_WHITE = "#F5F3FA"
CLOTH_SHADE = "#E6E3F0"
SLEEVE_GREY = "#CCC8DA"
SOCK_WHITE = "#F3F0F8"
SOCK_SHADE = "#E3E0ED"
SOLE_LIGHT = "#DFDCE9"
SOLE_SHADE = "#C9C5D6"


# ==============================================================================
# Dedicated Separate Eye Layer Parameters (Calibrated to 50/50 Overlay!)
# ==============================================================================
EYE_INNER_X = 0.94      # Exact wider eye spacing matching ref_front 50/50 overlay!
EYE_WIDTH = 1.72        # Total width of 3-pixel eye (0.573u per MC pixel!)
EYE_BOTTOM_Y = 26.08    # Bottom edge of 3x2 eye
EYE_HEIGHT = 1.24       # Crisp horizontal 3x2 aspect ratio (2 rows of 0.62u)
EYE_LASH_H = 0.34       # Crisp straight dark upper eyelash bar
EYE_BROW_H = 0.28       # Subtle 1px eyebrow peak above middle column
EYE_Z = -3.435          # Cleanly floating 0.035u in front of Head front face (z=-3.40)


# ==============================================================================
# Texture Painters
# ==============================================================================
def paint_leg_column(is_right_leg: bool):
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "up":
            return make_solid_patch(w, h, SKIN_MID)
        if face == "down":
            return make_solid_patch(w, h, SOCK_SHADE)

        arr = np.empty((h, w, 4), dtype=np.uint8)
        y_bot, y_top = 4.50, 13.00
        for row in range(h):
            y = y_top - (row + 0.5) / h * (y_top - y_bot)
            if y >= 9.90:
                if y > 12.15:
                    col = lerp_color(SKIN_MID, SKIN_SHADE, (y - 12.15) / 0.85)
                else:
                    t = (12.15 - y) / (12.15 - 9.90)
                    col = lerp_color(SKIN_MID, SKIN_LIGHT, t * 0.65)
            elif y >= 9.28:
                col = parse_color(DARK_CHARCOAL)
            elif y >= 8.60:
                col = parse_color(SOCK_WHITE)
            elif y >= 8.00 and is_right_leg:
                col = parse_color(DARK_CHARCOAL)
            else:
                t = max(0.0, min(1.0, (8.60 - y) / (8.60 - 4.50)))
                col = lerp_color(SOCK_WHITE, SOCK_SHADE, t * 0.50)
            arr[row, :] = col

        if face in ("north", "south", "east", "west"):
            for col_i in range(w):
                gx = int(col_i * 4 / max(1, w))
                if gx == 0 or gx == 3:
                    arr[:, col_i, :3] = np.clip(arr[:, col_i, :3].astype(np.float32) * 0.965, 0, 255).astype(np.uint8)
        return arr

    return painter


def paint_upper_arm():
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "up":
            return make_solid_patch(w, h, CLOTH_WHITE)
        if face == "down":
            return make_solid_patch(w, h, CLOTH_SHADE)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        y_bot, y_top = 19.50, 24.45
        for row in range(h):
            y = y_top - (row + 0.5) / h * (y_top - y_bot)
            if 22.15 <= y <= 22.92:
                col = parse_color(CLOTH_SHADE)
            elif 19.50 <= y <= 20.32:
                col = parse_color(SLEEVE_GREY)
            else:
                col = parse_color(CLOTH_WHITE)
            arr[row, :] = col
        return arr
    return painter


def paint_forearm_sleeve():
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "up":
            return make_solid_patch(w, h, CLOTH_WHITE)
        if face == "down":
            return make_solid_patch(w, h, CLOTH_SHADE)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        y_bot, y_top = 12.90, 19.65
        for row in range(h):
            y = y_top - (row + 0.5) / h * (y_top - y_bot)
            if 14.68 <= y <= 15.32:
                col = parse_color(DARK_CHARCOAL)
            elif 13.48 <= y <= 14.14:
                col = parse_color(DARK_CHARCOAL)
            elif y > 18.90:
                col = parse_color(CLOTH_WHITE)
            elif y < 13.48:
                col = lerp_color(CLOTH_WHITE, CLOTH_SHADE, 0.35)
            else:
                t = max(0.0, min(1.0, (18.90 - y) / (18.90 - 15.32)))
                col = lerp_color(CLOTH_WHITE, CLOTH_SHADE, t * 0.25)
            arr[row, :] = col
        return arr
    return painter


def paint_shoe_lower():
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face in ("up", "down"):
            return make_solid_patch(w, h, DARK_CHARCOAL)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        y_bot, y_top = 1.05, 2.95
        for row in range(h):
            y = y_top - (row + 0.5) / h * (y_top - y_bot)
            if face in ("east", "west") and 1.92 <= y <= 2.60:
                col = parse_color(CLOTH_WHITE)
            else:
                col = parse_color(DARK_CHARCOAL)
            arr[row, :] = col
        return arr
    return painter


def paint_pleated_skirt(y_bot: float, y_top: float):
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face in ("up", "down"):
            return make_solid_patch(w, h, DARK_CHARCOAL)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        for row in range(h):
            ty = row / max(1, h - 1)
            base = lerp_color(DARK_MID, DARK_CHARCOAL, ty)
            for col_i in range(w):
                pleat_idx = int(col_i * 6 / max(1, w))
                if face in ("north", "south") and pleat_idx in (1, 4):
                    col = lerp_color(base, DARK_PLEAT, 0.55)
                elif face in ("north", "south") and pleat_idx in (2, 3):
                    col = lerp_color(base, DARK_MID, 0.25)
                else:
                    col = base
                arr[row, col_i] = col
        return arr
    return painter


def paint_head_skin_only():
    """
    Pure clean skin base on Head cube (eyes are now on a dedicated separate layer!).
    Paints creamy pale peach skin, crisp 1-MC-px rosy blush on outer cheeks directly under the eyes,
    and soft forehead shadow above the eye line.
    """
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "down":
            return make_solid_patch(w, h, SKIN_SHADE)
        if face != "north":
            return make_vgradient_patch(w, h, HAIR_MID, HAIR_SHADE)

        # Head front: x = -2.85 .. +2.85 (5.70w), y = 25.15 .. 31.95 (6.80h)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        for r in range(h):
            y = 31.95 - (r + 0.5) / h * 6.80
            for c in range(w):
                x = -2.85 + (c + 0.5) / w * 5.70
                ax = abs(x)
                if y >= 28.65:
                    col = parse_color(HAIR_MID)
                elif y >= 27.85:
                    # Subtle peach-shadow forehead strip peeking above eyebrows
                    col = parse_color(SKIN_SHADE) if ax >= 1.15 else parse_color(SKIN_MID)
                elif y >= 26.02:
                    col = parse_color(SKIN_LIGHT)
                else:
                    # Cheek & chin row (y = 25.15 .. 26.02): crisp rosy blush directly beneath outer sclera!
                    if ax >= EYE_INNER_X + EYE_WIDTH * (2.0 / 3.0) - 0.05:
                        col = parse_color(SKIN_BLUSH)
                    elif ax >= EYE_INNER_X + EYE_WIDTH * (1.0 / 3.0):
                        col = parse_color(SKIN_MID)
                    else:
                        col = parse_color(SKIN_LIGHT)
                arr[r, c] = col
        return arr
    return painter


def paint_eye_3x2(is_right_eye: bool):
    """
    EXACT 3x2 Pixel-Art Eye Texture for the dedicated separate Eye Layer!
    Strictly 3 columns x 2 rows (rendered at 6x4 exact integer texels -> razor-sharp MC pixels!):
      - For Right Eye (viewer's left):  Col 0 = Sclera (outer), Col 1..2 = 2x2 Iris (inner)
      - For Left Eye  (viewer's right): Col 0..1 = 2x2 Iris (inner), Col 2 = Sclera (outer)
    """
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face != "north":
            return make_solid_patch(w, h, (0, 0, 0, 0))
        grid = np.empty((4, 6, 4), dtype=np.uint8)
        if is_right_eye:
            # Top row (rows 0..1)
            grid[0:2, 0:2] = parse_color(EYE_SCLERA_T)    # Outer sclera
            grid[0:2, 2:4] = parse_color(EYE_IRIS_OUT_T)  # Outer iris
            grid[0:2, 4:6] = parse_color(EYE_IRIS_IN_T)   # Inner iris
            # Bottom row (rows 2..3)
            grid[2:4, 0:2] = parse_color(EYE_SCLERA_B)    # Outer bright sclera
            grid[2:4, 2:4] = parse_color(EYE_IRIS_OUT_B)  # Outer lower iris
            grid[2:4, 4:6] = parse_color(EYE_IRIS_IN_B)   # Inner lower iris
        else:
            # Exact mirror for Left Eye
            grid[0:2, 0:2] = parse_color(EYE_IRIS_IN_T)
            grid[0:2, 2:4] = parse_color(EYE_IRIS_OUT_T)
            grid[0:2, 4:6] = parse_color(EYE_SCLERA_T)
            grid[2:4, 0:2] = parse_color(EYE_IRIS_IN_B)
            grid[2:4, 2:4] = parse_color(EYE_IRIS_OUT_B)
            grid[2:4, 4:6] = parse_color(EYE_SCLERA_B)
        return grid
    return painter


def paint_torso_dress():
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face in ("up", "down"):
            return make_solid_patch(w, h, DARK_CHARCOAL)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        y_bot, y_top = 16.50, 24.20
        for row in range(h):
            y = y_top - (row + 0.5) / h * (y_top - y_bot)
            for col_i in range(w):
                nx = (col_i + 0.5) / w
                dx = abs(nx - 0.5)
                if face == "north":
                    if y >= 23.15 and dx <= 0.36:
                        col = parse_color(CLOTH_WHITE)
                    else:
                        t = max(0.0, min(1.0, (23.15 - y) / 6.65))
                        col = lerp_color(DARK_MID, DARK_CHARCOAL, t)
                else:
                    t = max(0.0, min(1.0, (24.20 - y) / 7.70))
                    col = lerp_color(DARK_MID, DARK_CHARCOAL, t)
                arr[row, col_i] = col
        return arr
    return painter


def paint_hood_eye_socket():
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face != "north":
            return make_vgradient_patch(w, h, DARK_SOCKET_TOP, DARK_SOCKET_BOT)
        arr = np.empty((h, w, 4), dtype=np.uint8)
        for r in range(h):
            ty = r / max(1, h - 1)
            for c in range(w):
                tx = c / max(1, w - 1)
                t = 0.65 * ty + 0.35 * tx
                arr[r, c] = lerp_color(DARK_SOCKET_TOP, DARK_SOCKET_BOT, t)
        return arr
    return painter


def paint_hood_dome_panel(top_col: str = HOOD_TOP, bot_col: str = HOOD_MID):
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "up":
            return make_solid_patch(w, h, HOOD_TOP)
        if face == "down":
            return make_solid_patch(w, h, HOOD_DEEP)
        if face in ("east", "west"):
            return make_vgradient_patch(w, h, top_col, lerp_color(bot_col, HOOD_SHADE, 0.40))
        return make_vgradient_patch(w, h, top_col, bot_col)
    return painter


def paint_hair_sheet(top_col: str, bot_col: str, subtle_stripes: bool = True):
    """
    Soft silky anime hair-sheet texture ("一片一片的"):
    Clean smooth pale silver-lavender vertical gradient with very subtle MC pixel sheen
    and soft bottom feathering (NO harsh dark gaps!).
    """
    def painter(face: str, w: int, h: int) -> np.ndarray:
        if face == "up":
            return make_solid_patch(w, h, top_col)
        if face == "down":
            return make_solid_patch(w, h, lerp_color(bot_col, HAIR_SHADE, 0.35))
        arr = make_vgradient_patch(w, h, top_col, bot_col)
        if subtle_stripes and face in ("north", "south") and w >= 4:
            # Very gentle 3% soft ribbon sheen across the sheet width (reads like silky flat hair plane!)
            for col_i in range(w):
                t = abs((col_i + 0.5) / w - 0.5) * 2.0  # 0 center, 1 edge
                factor = 1.015 - 0.045 * (t ** 1.5)
                arr[:, col_i, :3] = np.clip(arr[:, col_i, :3].astype(np.float32) * factor, 0, 255).astype(np.uint8)
        elif face in ("east", "west"):
            arr[:, :, :3] = np.clip(arr[:, :, :3].astype(np.float32) * 0.96, 0, 255).astype(np.uint8)
        return arr
    return painter


# ==============================================================================
# Sculpting Modules
# ==============================================================================
def build_separate_eye_layer(m: YSMModel):
    """
    Dedicated Separate Eye & Eyebrow Layer (child of Head bone).
    Allows 0.01u independent fine-tuning of eye position, spacing, and scale!
    Matches superzoom_face.png: crisp 3x2 pixel eye + horizontal lash + inner eyebrow step.
    """
    for is_right, bone in ((True, "EyeRight"), (False, "EyeLeft")):
        # Right eye occupies [-EYE_INNER_X - EYE_WIDTH .. -EYE_INNER_X]
        # Left eye occupies  [+EYE_INNER_X .. +EYE_INNER_X + EYE_WIDTH]
        ex0 = -(EYE_INNER_X + EYE_WIDTH) if is_right else EYE_INNER_X
        col_w = EYE_WIDTH / 3.0  # Exact width of 1 MC pixel!

        # 1. Exact 3x2 Eye Plane (floating cleanly at z = EYE_Z, 0.03u thick)
        m.add_cube(
            bone,
            origin=(ex0, EYE_BOTTOM_Y, EYE_Z),
            size=(EYE_WIDTH, EYE_HEIGHT, 0.03),
            face_painter=paint_eye_3x2(is_right),
            face_dims_override={"north": (6, 4)},
            name=f"{bone}_3x2_iris_sclera",
        )
        # 2. Crisp Straight Dark Upper Eyelash across all 3 columns
        m.add_cube(
            bone,
            origin=(ex0, EYE_BOTTOM_Y + EYE_HEIGHT, EYE_Z - 0.005),
            size=(EYE_WIDTH, EYE_LASH_H, 0.03),
            solid_color=EYE_LASH,
            share_sides=True,
            name=f"{bone}_lash",
        )
        # 3. Subtle 1-pixel Eyebrow Step sitting directly above the middle column of the eye
        brow_x0 = (ex0 + col_w) if is_right else (ex0 + col_w)
        m.add_cube(
            bone,
            origin=(brow_x0, EYE_BOTTOM_Y + EYE_HEIGHT + EYE_LASH_H, EYE_Z - 0.005),
            size=(col_w, EYE_BROW_H, 0.03),
            solid_color=EYE_LASH,
            share_sides=True,
            name=f"{bone}_brow_step",
        )


def build_skull_hood(m: YSMModel):
    """
    Phase 3.6 Sculpt: 360-Degree Precision 3D Voxel Skull Hood (y = 25.3 .. 34.0u).
    - Front Face (Z_FRONT = -4.55): 100% preserved from approved 50/50 Front-Head overlay!
    - Left/Right Side Profile: Smooth tall vertical white cheek/dome surface (NO pancake lines!),
      larger & properly placed front eye socket, exact calibrated mid-side L-notch (z=-1.95..-0.35),
      sculpted multi-stepped rounded back dome extending to z=+4.82 matching diag_side_focus 50/50 overlay!
    - Back Dome: Smooth unified bright white center back panel + 4 delicate stepped outer contour ribs
      + sculpted corner lower puffs matching diag_back_focus 50/50 overlay!
    """
    Z_FRONT = -4.55  # Unified flush front plane of the skull mask (PRESERVED!)

    # --- 1. CROWN & UPPER ROUNDED DOME (y = 32.00 .. 34.00u) ---
    # Tier 1: Top crown cap (y = 33.42 .. 34.00u, 7.0w x 7.1d — reaches z=+3.90 cleanly!)
    m.add_cube(
        "SkullHood", origin=(-3.50, 33.42, -3.20), size=(7.00, 0.58, 7.10),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_TOP), name="hood_crown_tier1",
    )
    # Tier 2: Upper rounded dome (y = 32.72 .. 33.50u, 8.10w, extends smoothly back to z=+4.38!)
    m.add_cube(
        "SkullHood", origin=(-4.05, 32.72, -3.95), size=(8.10, 0.78, 8.33),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_crown_tier2",
    )
    # Tier 3: Flush Upper Forehead above eye sockets (y = 32.00 .. 32.92u, exact Z_FRONT to z=+4.58!)
    m.add_cube(
        "SkullHood", origin=(-4.18, 32.00, Z_FRONT), size=(8.36, 0.92, 9.13),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_brow_top_slab",
    )
    # Smooth outer upper-temple bevels (steps front silhouette to ±4.80 while blending cleanly into side wall!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.80, 31.35, -2.75), size=(0.82, 1.55, 7.15),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_upper_temple_step",
    )

    # --- 2. SKULL EYE SOCKET ZONE (y = 30.48 .. 32.02u — Front PRESERVED, Side deepened to z=-2.78!) ---
    # Deep skull core behind eye sockets (starts at z = -2.78 so Side view reveals generous bold eye socket!)
    m.add_cube(
        "SkullHood", origin=(-4.48, 30.48, -2.78), size=(8.96, 1.56, 7.36),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_eye_zone_core",
    )
    # Center white nasal bridge FLUSH at Z_FRONT (x = -1.30 .. +1.30)
    m.add_cube(
        "SkullHood", origin=(-1.30, 30.48, Z_FRONT), size=(2.60, 1.56, 1.82),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_nasal_bridge",
    )
    # Recessed Dark Skull Eye Sockets (x = ±1.30 .. ±3.38, y = 30.48 .. 32.02, z = -4.22 .. -2.75)
    # Deeper Z back to -2.75 makes the Side-view eye socket wider & dead-on with diag_side_focus 50/50 overlay!
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-3.38, 30.48, -4.22), size=(2.08, 1.54, 1.48),
        face_painter=paint_hood_eye_socket(), name="hood_eye_socket",
    )
    # Outer white brow rim beside eye sockets FLUSH at Z_FRONT (thin Z=-4.55..-4.20 so Side eye stays wide open!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.30, 30.48, Z_FRONT), size=(0.92, 1.56, 0.35),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_eye_outer_rim",
    )
    # Outer cheek-temple wall BEHIND eye socket corner (z = -2.78 .. +4.38, flush at x = ±5.14 with lower side wall!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.14, 30.28, -2.78), size=(1.70, 2.38, 7.16),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_eye_outer_temple",
    )

    # --- 3. LOWER BROW RIDGE & SKULL NOSE (y = 29.40 .. 30.50u — FLUSH at Z_FRONT, PRESERVED!) ---
    m.add_cube(
        "SkullHood", origin=(-4.35, 29.40, Z_FRONT), size=(8.70, 1.10, 1.80),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_lower_brow_bar",
    )
    m.add_cube(
        "SkullHood", origin=(-0.44, 30.08, Z_FRONT - 0.14), size=(0.88, 0.44, 0.18),
        vgradient=(DARK_SOCKET_TOP, DARK_BLACK), share_sides=True, name="hood_skull_nose",
    )
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-2.82, 28.62, -3.86), size=(1.12, 0.80, 0.56),
        vgradient=(DARK_MID, HAIR_SHADOW), share_sides=True, name="hood_arch_corner_shadow",
    )

    # --- 4. SCULPTED SIDE SKULL WALLS + CALIBRATED L-NOTCH & CURVED REAR DOME (y = 25.3 .. 33.0u) ---
    # Calibrated directly to diag_side_focus.png 50/50 overlay:
    #   - Mid-side L-notch horizontal leg: z = -2.02 .. -1.08, y = 29.38 .. 30.28
    #   - Mid-side L-notch vertical drop:  z = -1.16 .. -0.32, y = 28.12 .. 30.28
    #   - Lower-front jaw shadow recess:   z = -3.00 .. -2.02, y = 26.25 .. 27.95
    #   - Smooth tall vertical white rear-side skull wall from y=25.60 ALL THE WAY UP to y=32.75!
    #     (Flush at x = ±5.16 so there are ZERO ugly horizontal pancake lines across the side!)

    # Recessed dark backing behind the L-notch & lower jaw recess (strictly inside x = ±4.88 -> ZERO Front dots!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.88, 26.55, -3.02), size=(0.42, 3.76, 2.85),
        vgradient=(DARK_SOCKET_TOP, DARK_CHARCOAL), share_sides=True, name="hood_side_recess_dark",
    )
    # Inner face-arch cheek drop FLUSH with front brow (PRESERVED!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.05, 28.32, Z_FRONT), size=(1.25, 1.12, 1.65),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_arch_cheek_inner",
    )
    # Front cheek bar in front of L-notch (z = -4.35 .. -2.02, y = 27.95 .. 30.42, flush at x = ±5.14)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.14, 27.95, -4.35), size=(1.18, 2.47, 2.33),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_front_cheek_pillar",
    )
    # Lower outer cheek flared sheet on front edge (x = ±4.35 .. ±5.34, z = -3.85 .. -3.02 -> keeps jaw opening crisp!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.34, 26.45, -3.85), size=(0.98, 1.75, 0.83),
        face_painter=paint_hood_dome_panel(HOOD_MID, HOOD_SHADE), name="hood_front_cheek_lower_lip",
    )
    # Soft pale-lavender inner cheek cushion behind front hair
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.48, 25.55, -3.48), size=(0.94, 2.75, 1.22),
        vgradient=(HOOD_SHADE, HOOD_INNER), share_sides=True, name="hood_inner_cheek_cushion",
    )
    # White cheek wall UNDER horizontal leg of L-notch (z = -2.02 .. -1.14, y = 25.60 .. 29.38, flush at x = ±5.16)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.16, 25.60, -2.02), size=(0.76, 3.78, 0.88),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_side_under_notch_front",
    )
    # White cheek wall UNDER vertical leg of L-notch (z = -1.16 .. -0.30, y = 25.60 .. 28.12, flush at x = ±5.16)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.16, 25.60, -1.16), size=(0.76, 2.52, 0.86),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_side_under_notch_rear",
    )
    # TALL UNIFIED SMOOTH REAR-SIDE SKULL WALL behind L-notch (z = -0.32 .. +2.95, y = 25.55 .. 32.78!)
    # Ends cleanly at z=+2.95 so the rear dome curves INWARD smoothly in vertical steps (ZERO sticker patch!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-5.16, 25.55, -0.32), size=(1.22, 7.23, 3.27),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_rear_side_wall",
    )
    # Sculpted rear-side curved step 1 (steps gently inward in X to ±4.84, extends back to z=+4.15!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.84, 25.75, 2.75), size=(1.15, 6.75, 1.40),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_rear_curve_step1",
    )
    # Sculpted rear-side curved step 2 (curves further inward to ±4.32, extends plushly back to z=+4.75!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.32, 25.95, 3.65), size=(1.15, 6.05, 1.10),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_rear_curve_step2",
    )
    # Flared bottom-back hood hem lip (kept flush at z=+4.58 so Back dome stays sleek with ZERO corner bumps!)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.48, 25.65, 3.35), size=(1.15, 2.35, 1.22),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_back_corner_lip",
    )
    # Inner pale-lavender hood lining closing underside seamlessly above shoulder
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.55, 25.25, -2.10), size=(1.10, 2.20, 5.40),
        vgradient=(HOOD_SHADE, HOOD_INNER), share_sides=True, name="hood_inner_lining",
    )

    # --- 5. SMOOTH STEPPED BACK DOME OF SKULL HOOD (ZERO floating blocks — sleek rounded dome!) ---
    # Broad smooth bright white central back dome (x = -3.55 .. +3.55, y = 26.05 .. 33.42, flush z=+4.72)
    m.add_cube(
        "SkullHood", origin=(-3.55, 26.05, 3.65), size=(7.10, 7.37, 1.07),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_back_smooth_center",
    )
    # Smooth outer-back vertical rounding step (blends seamlessly from ±3.55 to ±4.35, y = 26.05 .. 32.72)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.35, 26.05, 3.55), size=(0.90, 6.67, 1.02),
        face_painter=paint_hood_dome_panel(HOOD_TOP, HOOD_LIGHT), name="hood_back_step_mid",
    )
    # Far-outer back vertical rounding step (blends seamlessly to ±4.92, y = 25.95 .. 31.90)
    m.add_mirrored_cube(
        "SkullHood", "SkullHood", origin=(-4.92, 25.95, 2.80), size=(0.68, 5.95, 1.36),
        face_painter=paint_hood_dome_panel(HOOD_LIGHT, HOOD_MID), name="hood_back_step_outer",
    )
    # Crisp rolled bottom hem across back of skull hood (y = 25.45 .. 26.15)
    m.add_cube(
        "SkullHood", origin=(-4.55, 25.45, 2.45), size=(9.10, 0.72, 2.02),
        vgradient=(HOOD_MID, HOOD_SHADE), name="hood_back_lower_hem",
    )


def build_bangs_and_front_hair(m: YSMModel):
    """
    SHEET-BASED HAIR ARCHITECTURE ("一片一片的") — NO MORE VERTICAL BARS ("一条一条的")!
    - Bangs: One cohesive broad silky flat sheet across the forehead with a delicate stepped center tongue
      (tiny 0.07u..0.12u Z-step -> clean soft anime depth, ZERO black vertical trenches!).
    - Front Side Hair: Broad, thin, gently tilted overlapping hair sheets draping softly over
      cheek -> chest -> skirt like layered fabric/anime hair planes!
    """
    # --- 1. COHESIVE SHEET BANGS (matching superzoom_face.png!) ---
    # Main wide flat bangs sheet across center forehead (x = -1.68 .. +1.68, y = 28.05 .. 29.42, flush at z = -3.76)
    m.add_cube(
        "HairBangs", origin=(-1.68, 28.05, -3.76), size=(3.36, 1.37, 0.36),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT, subtle_stripes=False),
        name="bangs_main_sheet",
    )
    # Gentle center stepped tongue (2 subtle overlapping thin tabs matching superzoom_face!)
    # Left-of-center tab (x = -0.82 .. +0.02, drops to y = 27.18, only 0.08u proud of main sheet!)
    m.add_cube(
        "HairBangs", origin=(-0.82, 27.18, -3.84), size=(0.84, 2.22, 0.38),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT, subtle_stripes=False),
        name="bangs_center_tab_R",
    )
    # Right-of-center slightly longer tab (x = -0.02 .. +0.62, drops to y = 26.86, only 0.07u proud!)
    m.add_cube(
        "HairBangs", origin=(-0.02, 26.86, -3.91), size=(0.64, 2.54, 0.40),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT, subtle_stripes=False),
        name="bangs_center_tab_L",
    )
    # Outer corner temple tabs (x = ±2.18 .. ±2.95, y = 28.05 .. 29.42, flush at z = -3.76)
    # Leaves the adorable small warm peach skin peek right above the eyebrow peaks at x = ±1.68..±2.18!
    m.add_mirrored_cube(
        "HairBangs", "HairBangs", origin=(-2.95, 28.05, -3.76), size=(0.78, 1.37, 0.36),
        face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID, subtle_stripes=False),
        name="bangs_outer_corner_tab",
    )

    # --- 2. BROAD OVERLAPPING FRONT HAIR SHEETS ("一片一片的") ---
    # Each side is composed of broad, thin (0.38..0.52u thick!), gently angled overlapping hair planes
    # that drape smoothly from the cheek down across the chest & skirt hem!
    def add_front_sheet_side(bone: str, sign: float):
        def ox(x_inner: float, width: float) -> float:
            return -(x_inner + width) if sign < 0 else x_inner

        # Slight gentle outward/inward sheet tilt (creates natural anime drape instead of vertical poles!)
        # Note: in Bedrock, rz > 0 tilts bottom toward -X (Right); rz < 0 tilts bottom toward +X (Left).
        # So `sign * (-deg)` tilts bottom OUTWARD away from centerline; `sign * (+deg)` tilts bottom INWARD!
        dy = 0.0 if sign < 0 else 0.35

        # SHEET 1 (PRIMARY FACE-FRAMING SHEET): Crisp vertical thin sheet right along cheek & jaw (PRESERVED!)
        m.add_cube(
            bone,
            origin=(ox(2.66, 1.00), 21.80, -3.66),
            size=(1.00, 7.55, 0.46),
            face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
            name=f"{bone}_sheet_cheek_main",
        )
        # SHEET 1B (LOWER FLOWING CONTINUATION SHEET): Broad gently-waving sheet overlapping Sheet 1 smoothly!
        m.add_cube(
            bone,
            origin=(ox(2.12, 1.32), 13.30 + dy * 0.5, -3.38),
            size=(1.32, 9.00, 0.46),
            pivot=(sign * 2.78, 22.30, -3.15),
            rotation=(2.2, 0.0, sign * (-1.2)),
            face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
            name=f"{bone}_sheet_chest_flow",
        )
        # Sculpted Side-Profile Front Hair Wave Accents (adds graceful layered depth in Left Side view!)
        m.add_cube(
            bone,
            origin=(ox(2.55, 0.85), 16.50, -3.56),
            size=(0.85, 4.40, 0.42),
            pivot=(sign * 2.95, 20.90, -3.35),
            rotation=(4.5, 0.0, sign * (-1.8)),
            face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID),
            name=f"{bone}_sheet_side_wave_mid",
        )
        m.add_cube(
            bone,
            origin=(ox(2.80, 0.78), 12.60, -3.38),
            size=(0.78, 4.10, 0.40),
            pivot=(sign * 3.20, 16.70, -3.18),
            rotation=(-3.0, 0.0, sign * (-2.2)),
            face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE),
            name=f"{bone}_sheet_side_wave_low",
        )
        # Soft tapered flat tip tab at bottom of Sheet 1B
        m.add_cube(
            bone,
            origin=(ox(2.18, 0.82), 12.10 if sign < 0 else 12.30, -2.98),
            size=(0.82, 1.80, 0.40),
            face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE, subtle_stripes=False),
            name=f"{bone}_sheet_inner_tip",
        )

        # SHEET 2 (BROAD OUTER SHOULDER-TO-HIP SHEET): Wider 1.85u thin overlapping sheet behind Sheet 1!
        # Gently angled outward (fanning softly along the inner sleeve edge — pure "一片一片" silhouette!)
        m.add_cube(
            bone,
            origin=(ox(2.90, 1.55), 18.20, -3.15),
            size=(1.55, 10.20, 0.52),
            pivot=(sign * 3.65, 28.40, -2.90),
            rotation=(2.0, 0.0, sign * (-2.2)),
            face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID),
            name=f"{bone}_sheet_outer_upper",
        )
        # SHEET 2B (LOWER OUTER FLARED SHEET): Broad soft hip drape overlapping smoothly down to skirt hem
        m.add_cube(
            bone,
            origin=(ox(2.65, 1.58), 12.75 - dy * 0.4, -2.86),
            size=(1.58, 6.80, 0.48),
            pivot=(sign * 3.45, 19.50, -2.62),
            rotation=(1.0, 0.0, sign * (-3.2)),
            face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_SHADE),
            name=f"{bone}_sheet_outer_lower",
        )
        # Delicate flat outer dangling wisp tab beside sleeve cuff
        m.add_cube(
            bone,
            origin=(ox(3.55, 0.72), 11.75 if sign > 0 else 11.95, -2.55),
            size=(0.72, 2.15, 0.38),
            face_painter=paint_hair_sheet(HAIR_SHADE, HAIR_DEEP, subtle_stripes=False),
            name=f"{bone}_sheet_outer_tip",
        )

        # SHEET 3 (SOFT RECESSED INNER SHADOW SHEET): Broad flat backing plane closing gaps cleanly!
        m.add_cube(
            bone,
            origin=(ox(2.15, 1.80), 14.20, -2.42),
            size=(1.80, 13.80, 0.58),
            face_painter=paint_hair_sheet(HAIR_SHADE, HAIR_DEEP, subtle_stripes=False),
            name=f"{bone}_sheet_inner_backing",
        )

    add_front_sheet_side("HairFrontRight", -1.0)
    add_front_sheet_side("HairFrontLeft", +1.0)


def build_back_hair(m: YSMModel):
    r"""
    Phase 3.10 Hero Sculpt: Full-Volume Multi-Tier Layered Back Hair Sheets!
    Solves BOTH Back-View richness AND Side-View 3D thickness simultaneously:
      - Full sculpted 3D side-thickness volume (z = +2.0 .. +4.35u, zero hollow paper slits!)
      - Preserves the exact User Diagram surface flow:
            |      |   |      |     <- 3-sheet stepped bright center waterfall (|  |)
           /       |   |       \    <- Multi-tier upper flank sheets flaring gently outward
            [mid-back pocket]       <- Delicate symmetrical curved wave pocket
           \       |   |       /    <- Plush multi-tier lower flank sheets & staggered curl petals
            |      |   |      |     <- 4-step staggered hem tips + dark charcoal skirt hem peek
      - Airy milky-white with ultra-light pale lavender tint ("白色带特别浅的淡紫色")!
    """
    # ==================================================================
    # 1. FULL-VOLUME TAPERED INNER CORE (gives rich solid 3D thickness in Left Side view!)
    # ==================================================================
    # Upper-to-lower plush hair body directly behind torso (z = +1.95 .. +3.25 -> 1.30u solid base depth!)
    # Stops cleanly at y=13.25 so dark charcoal skirt hem peeks out cleanly underneath in Back view!
    m.add_cube(
        "HairBack", origin=(-3.85, 13.25, 1.95), size=(7.70, 12.40, 1.28),
        pivot=(0.0, 25.65, 2.55), rotation=(-2.2, 0.0, 0.0),
        face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE, subtle_stripes=False),
        name="hb_core_volume",
    )
    # Recessed vertical shadow channels flanking center waterfall (x = ±1.42 .. ±2.35, sits cleanly at z=+3.20..+3.50)
    m.add_mirrored_cube(
        "HairBack", "HairBack",
        origin=(-2.35, 13.35, 2.85), size=(0.98, 12.25, 0.65),
        pivot=(-1.86, 25.60, 3.18), rotation=(-2.8, 0.0, 0.0),
        face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE, subtle_stripes=False),
        name="hb_inner_groove_channel",
    )
    # Plush outer shoulder-to-hip under-volume (solid 1.15u depth directly behind upper sleeve in Side view!)
    m.add_mirrored_cube(
        "HairBack", "HairBack",
        origin=(-4.32, 13.00, 2.15), size=(1.42, 12.60, 1.15),
        pivot=(-3.61, 25.60, 2.72), rotation=(-2.6, 0.0, 2.4),
        face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID),
        name="hb_outer_volume_drape",
    )
    # Upper-back plush root thickness tucked strictly INSIDE the vertical surface sheets (z=+2.10..+3.22!)
    # Keeps Left Side root plush while letting ALL vertical back strands emerge cleanly from the hood hem!
    m.add_cube(
        "HairBack", origin=(-3.95, 23.00, 2.10), size=(7.90, 2.75, 1.12),
        face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE, subtle_stripes=False),
        name="hb_hood_root_volume",
    )

    # ==================================================================
    # 2. THREE-SHEET STEPPED VERTICAL CENTER WATERFALL (|    |, rich detail + clean silhouette!)
    # ==================================================================
    # Center-Base broad silky sheet (x = -1.52 .. +1.52, y = 13.10 .. 25.70, z = +3.18 .. +3.72)
    m.add_cube(
        "HairBack", origin=(-1.52, 13.10, 3.18), size=(3.04, 12.60, 0.56),
        pivot=(0.0, 25.70, 3.46), rotation=(-3.2, 0.0, 0.0),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_center_base_sheet",
    )
    # Center-Mid bright foreground sheet (overlapping cleanly in center, +0.16u proud -> subtle stepped sheen!)
    m.add_cube(
        "HairBack", origin=(-0.78, 12.95, 3.36), size=(1.58, 12.70, 0.52),
        pivot=(0.0, 25.65, 3.62), rotation=(-3.5, 0.0, 0.0),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_center_mid_ribbon",
    )
    # Asymmetric delicate left-center overlapping secondary strand (breaks stiffness like REF Back!)
    m.add_cube(
        "HairBack", origin=(-1.62, 12.75, 3.32), size=(0.95, 9.20, 0.44),
        pivot=(-1.15, 21.95, 3.54), rotation=(-4.2, 0.0, 1.2),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_center_accent_R",
    )
    # Asymmetric delicate right-center overlapping secondary strand
    m.add_cube(
        "HairBack", origin=(0.68, 13.20, 3.32), size=(0.92, 8.60, 0.44),
        pivot=(1.14, 21.80, 3.54), rotation=(-4.0, 0.0, -1.2),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_center_accent_L",
    )
    # Lower center-flank bridging curls filling the lower half cleanly above the skirt hem
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-2.42, 12.65, 3.18), size=(1.05, 5.45, 0.56),
        pivot=(-1.90, 18.10, 3.46), rotation=(-4.8, 0.0, 1.8),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_lower_inner_bridge",
    )

    # ==================================================================
    # 3. MULTI-TIER CURVED SURFACE FLANK SHEETS (EXACT  | /  \ |  CONTOUR + REAL SIDE DEPTH!)
    # ==================================================================
    # UPPER FLANK MAIN SHEET: plush 0.62u-thick continuous sheet flaring gently outward (rz = +4.8 deg)
    m.add_mirrored_cube(
        "HairBack", "HairBack",
        origin=(-3.50, 18.55, 3.22), size=(1.50, 7.15, 0.62),
        pivot=(-2.75, 25.70, 3.53), rotation=(-3.8, 0.0, 4.8),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_flank_upper_main",
    )
    # UPPER FLANK INNER HIGHLIGHT STEP: thinner layered ribbon riding on outer-upper edge for crisp detail!
    m.add_mirrored_cube(
        "HairBack", "HairBack",
        origin=(-3.65, 19.35, 3.48), size=(0.86, 6.20, 0.44),
        pivot=(-3.22, 25.55, 3.70), rotation=(-4.6, 0.0, 5.2),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_flank_upper_layer2",
    )
    # ICONIC MID-BACK BACKWARD-FLICKING STEP LOCK (exact pointed outward tip at y=16.2..21.5, z=+4.40 in Side view!)
    m.add_mirrored_cube(
        "HairBack", "HairBack",
        origin=(-3.38, 16.35, 3.30), size=(1.08, 5.45, 0.58),
        pivot=(-2.84, 21.80, 3.59), rotation=(-9.8, 0.0, 4.0),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_side_mid_flick",
    )

    # --- [Delicate Symmetrical Mid-Back Curved Break at y = 17.85 .. 18.55u!] ---

    # LOWER FLANK MAIN SHEET: plush 0.64u-thick sheet curving smoothly back INWARD (rz = -3.8 deg)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-4.06, 12.00, 3.28), size=(1.58, 6.00, 0.64),
        pivot=(-3.27, 18.00, 3.60), rotation=(-4.2, 0.0, -3.8),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_flank_lower_main",
    )
    # LOWER FLANK SCULPTED OVERLAY PETAL: starts tucked cleanly inside lower flank top (ZERO shelf!) and flares out smoothly!
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-3.86, 12.35, 3.22), size=(1.14, 5.55, 0.48),
        pivot=(-3.29, 17.90, 3.46), rotation=(-6.0, 0.0, -2.8),
        face_painter=paint_hair_sheet(HAIR_BRIGHT, HAIR_HIGHLIGHT),
        name="hb_flank_lower_petal2",
    )

    # ==================================================================
    # 4. LUSH LOWER-SIDE VOLUME, TRAILING CURLS & 4-STEP STAGGERED HEM TIPS
    # ==================================================================
    # Plush outer hip wave sheet (solid 0.68u depth directly behind forearm cuff in Side view!)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-4.62, 12.10, 2.58), size=(1.32, 6.05, 0.72),
        pivot=(-3.96, 18.15, 2.94), rotation=(-4.5, 0.0, 2.8),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_outer_hip_sheet",
    )
    # Thick lush lower-back inner-trailing volume (fills lower Side view z=+2.15..+3.55 down to y=11.0u!)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-3.55, 11.15, 2.38), size=(1.55, 5.10, 0.98),
        pivot=(-2.78, 16.25, 2.87), rotation=(-4.2, 0.0, 1.5),
        face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID),
        name="hb_lower_side_volume",
    )
    # Airy rear-most trailing curl sheet (sweeps cleanly back to z=+4.42 at y=11.8..16.8 in Side view!)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-3.05, 11.75, 3.45), size=(1.28, 5.20, 0.56),
        pivot=(-2.41, 16.95, 3.73), rotation=(-7.8, 0.0, 1.2),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT),
        name="hb_lower_rear_sweep",
    )
    # 4-Step Staggered Tapered Hem Tips (matches REF Back & REF Side lowest silhouette!)
    # (a) Lowest hip curl tip (reaches y = 10.90u, thick & rounded like REF Left Side!)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-3.58, 10.90, 2.88), size=(0.94, 1.85, 0.68),
        face_painter=paint_hair_sheet(HAIR_LIGHT, HAIR_MID, subtle_stripes=False),
        name="hb_tip_lowest_hip",
    )
    # (b) Secondary mid-hip tip (y = 11.40u)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-2.58, 11.45, 3.25), size=(0.86, 1.65, 0.52),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT, subtle_stripes=False),
        name="hb_tip_mid_hip",
    )
    # (c) Outer sleeve-edge stray tip (y = 11.65u)
    m.add_mirrored_cube(
        "HairBackLower", "HairBackLower",
        origin=(-4.68, 11.65, 2.68), size=(0.66, 1.55, 0.48),
        face_painter=paint_hair_sheet(HAIR_MID, HAIR_SHADE, subtle_stripes=False),
        name="hb_tip_outer_edge",
    )
    # (d) Delicate center-lower wisps framing the dark charcoal skirt hem cleanly
    m.add_cube(
        "HairBackLower", origin=(-1.48, 12.20, 3.38), size=(0.74, 1.40, 0.44),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT, subtle_stripes=False),
        name="hb_tip_center_R",
    )
    m.add_cube(
        "HairBackLower", origin=(0.74, 12.35, 3.38), size=(0.72, 1.30, 0.44),
        face_painter=paint_hair_sheet(HAIR_HIGHLIGHT, HAIR_LIGHT, subtle_stripes=False),
        name="hb_tip_center_L",
    )


def build_chest_mini_skull(m: YSMModel):
    """3D Voxel White Mini-Skull Chest Charm matching superzoom_chest_skull.png!"""
    m.add_cube(
        "ChestDecor", origin=(-0.82, 22.18, -1.96), size=(1.64, 0.88, 0.36),
        vgradient=(DARK_MID, DARK_BLACK), share_sides=True, name="chest_tie_knot",
    )
    m.add_cube(
        "ChestDecor", origin=(-0.74, 21.34, -1.92), size=(1.48, 0.86, 0.30),
        vgradient=(CLOTH_WHITE, CLOTH_SHADE), share_sides=True, name="chest_skull_center",
    )
    m.add_mirrored_cube(
        "ChestDecor", "ChestDecor", origin=(-1.32, 21.36, -2.22), size=(0.62, 0.86, 0.56),
        vgradient=(HOOD_TOP, CLOTH_WHITE), share_sides=True, name="chest_skull_cheek",
    )
    m.add_cube(
        "ChestDecor", origin=(-0.72, 20.62, -2.18), size=(1.44, 0.76, 0.52),
        vgradient=(HOOD_TOP, CLOTH_SHADE), share_sides=True, name="chest_skull_jaw",
    )
    m.add_mirrored_cube(
        "ChestDecor", "ChestDecor", origin=(-0.72, 20.34, -2.20), size=(0.38, 0.38, 0.52),
        solid_color=CLOTH_WHITE, share_sides=True, name="chest_skull_tooth",
    )


def build_shoes_with_3d_skull(m: YSMModel):
    """Chunky Stepped Shoes with 3D Sculpted White Pixel-Skull Buckles matching superzoom_shoe_skull.png."""
    for is_right, bone, x0 in ((True, "RightLeg", -3.32), (False, "LeftLeg", 0.02)):
        m.add_cube(
            bone, origin=(x0, 4.50, -1.73), size=(3.30, 8.50, 3.46),
            face_painter=paint_leg_column(is_right), name=f"{bone}_column",
        )
        sx0 = x0 - 0.20 if is_right else x0 - 0.04
        cx = sx0 + 1.77

        m.add_cube(
            bone, origin=(sx0, 0.00, -2.48), size=(3.54, 1.04, 4.44),
            vgradient=(SOLE_LIGHT, SOLE_SHADE), name=f"{bone}_shoe_sole",
        )
        m.add_cube(
            bone, origin=(sx0 - 0.06, 1.02, -2.66), size=(3.66, 0.52, 4.62),
            solid_color=DARK_CHARCOAL, share_sides=True, name=f"{bone}_shoe_bumper",
        )
        m.add_cube(
            bone, origin=(sx0 - 0.04, 1.50, -2.52), size=(3.62, 1.48, 4.48),
            face_painter=paint_shoe_lower(), name=f"{bone}_shoe_lower",
        )
        m.add_cube(
            bone, origin=(sx0, 2.95, -2.28), size=(3.54, 1.20, 4.24),
            solid_color=DARK_CHARCOAL, name=f"{bone}_shoe_upper",
        )
        m.add_cube(
            bone, origin=(sx0 + 0.04, 4.15, -1.88), size=(3.46, 0.62, 3.80),
            solid_color=DARK_CHARCOAL, name=f"{bone}_shoe_cuff",
        )

        # 3D Sculpted Pixel-Skull Buckle
        m.add_cube(
            bone, origin=(cx - 0.94, 3.04, -2.62), size=(1.88, 0.88, 0.42),
            vgradient=(HOOD_TOP, CLOTH_WHITE), share_sides=True, name=f"{bone}_skull_forehead",
        )
        m.add_cube(
            bone, origin=(cx - 1.54, 2.16, -2.72), size=(0.62, 0.88, 0.34),
            vgradient=(HOOD_TOP, CLOTH_WHITE), share_sides=True, name=f"{bone}_skull_cheek_R",
        )
        m.add_cube(
            bone, origin=(cx + 0.92, 2.16, -2.72), size=(0.62, 0.88, 0.34),
            vgradient=(HOOD_TOP, CLOTH_WHITE), share_sides=True, name=f"{bone}_skull_cheek_L",
        )
        m.add_cube(
            bone, origin=(cx - 0.92, 2.66, -2.58), size=(0.64, 0.38, 0.14),
            solid_color=HAIR_MID, share_sides=True, name=f"{bone}_skull_eye_hi_R",
        )
        m.add_cube(
            bone, origin=(cx + 0.28, 2.66, -2.58), size=(0.64, 0.38, 0.14),
            solid_color=HAIR_MID, share_sides=True, name=f"{bone}_skull_eye_hi_L",
        )
        m.add_cube(
            bone, origin=(cx - 0.29, 2.56, -2.64), size=(0.58, 0.48, 0.22),
            solid_color=DARK_BLACK, share_sides=True, name=f"{bone}_skull_bridge",
        )
        m.add_cube(
            bone, origin=(cx - 0.92, 2.16, -2.56), size=(0.64, 0.52, 0.14),
            solid_color=DARK_BLACK, share_sides=True, name=f"{bone}_skull_eye_R",
        )
        m.add_cube(
            bone, origin=(cx + 0.28, 2.16, -2.56), size=(0.64, 0.52, 0.14),
            solid_color=DARK_BLACK, share_sides=True, name=f"{bone}_skull_eye_L",
        )
        m.add_cube(
            bone, origin=(cx - 0.30, 2.16, -2.68), size=(0.60, 0.40, 0.26),
            solid_color=HOOD_TOP, share_sides=True, name=f"{bone}_skull_nose",
        )
        m.add_cube(
            bone, origin=(cx - 0.94, 1.50, -2.68), size=(1.88, 0.66, 0.30),
            vgradient=(CLOTH_WHITE, CLOTH_SHADE), share_sides=True, name=f"{bone}_skull_jaw",
        )


# ==============================================================================
# Build Model
# ==============================================================================
def build_model() -> YSMModel:
    m = YSMModel(
        identifier="geometry.model",
        texture_width=512,
        texture_height=512,
        texels_per_unit=3.0,
        visible_bounds_width=3.0,
        visible_bounds_height=3.5,
        visible_bounds_offset=(0.0, 1.35, 0.0),
    )

    # 1. YSM 2.6.0 Standard Bone Hierarchy + Dedicated Eye Layer Bones!
    m.add_bone("All", pivot=(0.0, 0.0, 0.0))
    m.add_bone("Waist", parent="All", pivot=(0.0, 13.0, 0.0))
    m.add_bone("Body", parent="Waist", pivot=(0.0, 13.0, 0.0))

    m.add_bone("Skirt", parent="Body", pivot=(0.0, 17.0, 0.0))
    m.add_bone("ChestDecor", parent="Body", pivot=(0.0, 21.8, -1.7))

    m.add_bone("ElytraLocator", parent="Body", pivot=(0.0, 23.0, 1.8))
    m.add_bone("BackpackLocator", parent="Body", pivot=(0.0, 20.0, 2.0))
    m.add_bone("LeftShoulderLocator", parent="Body", pivot=(4.4, 24.0, 0.0))
    m.add_bone("RightShoulderLocator", parent="Body", pivot=(-4.4, 24.0, 0.0))

    m.add_bone("AllHead", parent="Body", pivot=(0.0, 25.15, 0.0))
    m.add_bone("Head", parent="AllHead", pivot=(0.0, 25.15, 0.0))
    m.add_bone("ViewLocator", parent="Head", pivot=(0.0, 28.0, 0.0))
    # Dedicated Separate Eye Layer bones (makes eye position/scale micro-tuning effortless!)
    m.add_bone("EyeRight", parent="Head", pivot=(-1.78, 26.80, -3.43))
    m.add_bone("EyeLeft", parent="Head", pivot=(1.78, 26.80, -3.43))
    m.add_bone("SkullHood", parent="Head", pivot=(0.0, 29.5, 0.0))
    m.add_bone("HairBangs", parent="Head", pivot=(0.0, 29.4, -3.45))
    m.add_bone("HairFrontRight", parent="Head", pivot=(-2.9, 27.5, -2.2))
    m.add_bone("HairFrontLeft", parent="Head", pivot=(2.9, 27.5, -2.2))
    m.add_bone("HairBack", parent="Head", pivot=(0.0, 26.2, 2.8))
    m.add_bone("HairBackLower", parent="HairBack", pivot=(0.0, 19.0, 3.0))

    m.add_bone("RightArm", parent="Body", pivot=(-4.35, 23.5, 0.0), rotation=(0.0, 0.0, 5.8))
    m.add_bone("RightHand", parent="RightArm", pivot=(-5.0, 13.8, 0.0))
    m.add_bone("RightHandLocator", parent="RightHand", pivot=(-5.0, 13.4, -0.5))

    m.add_bone("LeftArm", parent="Body", pivot=(4.35, 23.5, 0.0), rotation=(0.0, 0.0, -5.8))
    m.add_bone("LeftHand", parent="LeftArm", pivot=(5.0, 13.8, 0.0))
    m.add_bone("LeftHandLocator", parent="LeftHand", pivot=(5.0, 13.4, -0.5))

    m.add_bone("RightLeg", parent="Waist", pivot=(-1.66, 13.0, 0.0))
    m.add_bone("LeftLeg", parent="Waist", pivot=(1.66, 13.0, 0.0))

    # 2. Legs, Socks & 3D Pixel-Skull Shoes
    build_shoes_with_3d_skull(m)

    # 3. Torso, Neck, Pleated Mini-Skirt & 3D Chest Mini-Skull
    m.add_cube(
        "Body", origin=(-3.10, 16.50, -1.65), size=(6.20, 7.70, 3.30),
        face_painter=paint_torso_dress(), name="torso_core",
    )
    m.add_cube(
        "Body", origin=(-1.05, 24.15, -1.05), size=(2.10, 1.20, 2.10),
        vgradient=(SKIN_SHADE, SKIN_MID), name="neck",
    )
    m.add_mirrored_cube(
        "Body", "Body", origin=(-2.45, 24.20, -1.55), size=(1.40, 0.95, 0.72),
        solid_color=DARK_BLACK, share_sides=True, name="neck_collar_shadow",
    )
    m.add_cube(
        "Skirt", origin=(-3.55, 14.80, -1.95), size=(7.10, 2.30, 3.90),
        face_painter=paint_pleated_skirt(14.80, 17.10), name="skirt_upper",
    )
    m.add_cube(
        "Skirt", origin=(-3.88, 12.68, -2.14), size=(7.76, 2.18, 4.28),
        face_painter=paint_pleated_skirt(12.68, 14.86), name="skirt_lower",
    )
    m.add_cube(
        "Skirt", origin=(-1.55, 12.56, -2.24), size=(3.10, 1.90, 0.22),
        vgradient=(DARK_CHARCOAL, DARK_PLEAT), share_sides=True, name="skirt_center_pleat_F",
    )
    m.add_mirrored_cube(
        "Skirt", "Skirt", origin=(-3.75, 12.58, -2.22), size=(1.05, 1.75, 4.44),
        vgradient=(DARK_CHARCOAL, DARK_BLACK), share_sides=True, name="skirt_side_pleat",
    )
    m.add_mirrored_cube(
        "Skirt", "Skirt", origin=(-2.85, 12.48, -2.02), size=(1.32, 0.55, 4.04),
        solid_color=CLOTH_WHITE, share_sides=True, name="skirt_petticoat_peek",
    )
    build_chest_mini_skull(m)

    # 4. Oversized Stepped White Sleeves (shoulder top raised cleanly to 24.85 to meet hood seamlessly in Side view!)
    m.add_mirrored_cube(
        "RightArm", "LeftArm", origin=(-5.85, 19.50, -1.78), size=(3.20, 5.35, 3.56),
        face_painter=paint_upper_arm(), name="sleeve_upper",
    )
    m.add_mirrored_cube(
        "RightArm", "LeftArm", origin=(-6.15, 12.90, -1.96), size=(3.70, 6.75, 3.92),
        face_painter=paint_forearm_sleeve(), name="sleeve_forearm",
    )
    m.add_mirrored_cube(
        "RightHand", "LeftHand", origin=(-5.50, 13.05, -1.30), size=(2.40, 1.50, 2.60),
        solid_color=CLOTH_SHADE, share_sides=True, name="sleeve_inner_hand",
    )

    # 5. Clean Skin Head Base + Dedicated Separate Eye Layer
    m.add_cube(
        "Head", origin=(-2.85, 25.15, -3.40), size=(5.70, 6.80, 6.40),
        face_painter=paint_head_skin_only(), face_dims_override={"north": (32, 32)},
        name="head_base",
    )
    build_separate_eye_layer(m)

    # 6. Flush-Front Skull Hood & Broad Overlapping Sheet Hair ("一片一片的")
    build_skull_hood(m)
    build_bangs_and_front_hair(m)
    build_back_hair(m)

    return m


def main():
    pack_dir = ROOT / "out" / "skull_hoodie_girl"
    m = build_model()
    m.export_main_json(pack_dir / "models" / "main.json")
    m.export_arm_json(pack_dir / "models" / "arm.json")
    m.export_texture(pack_dir / "textures" / "default.png")
    m.export_uv_debug(ROOT / "renders" / "uv_debug.png")
    print("Exported skull_hoodie_girl example:", m.stats())


if __name__ == "__main__":
    main()
