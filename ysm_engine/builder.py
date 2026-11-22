"""
YSM (Yes Steve Model) Bedrock 1.12.0 Geometry & Pixel-Art Texture Builder.

Coordinate System (Bedrock 1.12.0 JSON space):
  +Y : Up (y = 0 is ground)
  -Z : Front (North face; character looks toward -Z)
  +Z : Back  (South face)
  -X : Character's RIGHT (RightArm, RightLeg; Viewer's LEFT when looking at front)
  +X : Character's LEFT  (LeftArm, LeftLeg; Viewer's RIGHT when looking at front)

Rotation Convention (Bedrock / Blockbench / GeckoLib):
  Bone & cube `rotation = [rx, ry, rz]` in degrees around `pivot`:
    rx > 0 : pitches top forward (-Z) / bottom backward (+Z) -> head nods down, limb swings back
    rx < 0 : pitches top backward (+Z) / bottom forward (-Z) -> head tilts up, limb swings forward
    ry > 0 : turns nose (-Z) toward character's RIGHT (-X_bedrock / +X_rh)
    rz > 0 : tilts bottom limb outward to character's RIGHT (-X_bedrock); rz < 0 tilts outward to LEFT

YSM 2.6.0 UV Standard Compliance:
  - Uses per-face UV on every cube.
  - texture_width == actual PNG width, texture_height == actual PNG height (UV unit = 1.0).
  - Every face's `uv` and `uv_size` are exact non-zero integers (>= 1) packed with zero overlap.
  - Each face owns a 1px atlas gutter filled by edge replication, so linear
    filtering at a face boundary samples that face's own colour, not a neighbour.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from PIL import Image, ImageDraw

ColorLike = Union[str, Tuple[int, int, int], Tuple[int, int, int, int], List[int]]
ALL_FACES = ("north", "south", "east", "west", "up", "down")


def parse_color(c: ColorLike) -> Tuple[int, int, int, int]:
    """Parses hex string (#RRGGBB / #RRGGBBAA) or RGB/RGBA tuple into 4-int RGBA."""
    if isinstance(c, str):
        s = c.strip().lstrip("#")
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)
        if len(s) == 8:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
        raise ValueError(f"Invalid hex color: {c}")
    if len(c) == 3:
        return (int(c[0]), int(c[1]), int(c[2]), 255)
    if len(c) == 4:
        return (int(c[0]), int(c[1]), int(c[2]), int(c[3]))
    raise ValueError(f"Invalid color tuple: {c}")


def lerp_color(c1: ColorLike, c2: ColorLike, t: float) -> Tuple[int, int, int, int]:
    """Linearly interpolates between two colors at t in [0, 1]."""
    a = parse_color(c1)
    b = parse_color(c2)
    t = max(0.0, min(1.0, float(t)))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def shade_color(c: ColorLike, factor: float) -> Tuple[int, int, int, int]:
    """Scales RGB brightness of a color while preserving alpha."""
    r, g, b, a = parse_color(c)
    return (
        max(0, min(255, int(round(r * factor)))),
        max(0, min(255, int(round(g * factor)))),
        max(0, min(255, int(round(b * factor)))),
        a,
    )


def tint_color(c: ColorLike, dr: int = 0, dg: int = 0, db: int = 0) -> Tuple[int, int, int, int]:
    """Offsets RGB channels of a color while preserving alpha."""
    r, g, b, a = parse_color(c)
    return (
        max(0, min(255, r + dr)),
        max(0, min(255, g + dg)),
        max(0, min(255, b + db)),
        a,
    )


class ShelfPacker:
    """
    Deterministic integer 2D shelf rectangle packer.

    `border` reserves a transparent gutter around every rect so the texture
    exporter can replicate edge pixels into it. The gutter belongs to the rect,
    so neighbouring faces never overwrite each other's bleed.
    """

    def __init__(self, width: int, height: int, pad: int = 1, border: int = 0):
        self.width = int(width)
        self.height = int(height)
        self.pad = int(pad)
        self.border = max(0, int(border))
        self.shelves: List[List[int]] = []  # [y, h, next_x]
        self.next_y = 0
        self.allocated: List[Tuple[int, int, int, int, str]] = []

    def alloc(self, w: int, h: int, label: str = "") -> Tuple[int, int]:
        w = max(1, int(w))
        h = max(1, int(h))
        b = self.border
        pw = w + 2 * b + self.pad
        ph = h + 2 * b + self.pad
        # With no gutter, keep the original inner-height shelf metric so legacy
        # layouts stay byte-for-byte identical. With a gutter, the shelf metric
        # must be the full footprint, otherwise neighbouring shelves overlap.
        fit_h = ph if b else h
        best_idx = -1
        best_waste = 10**9
        for idx, (sy, sh, sx) in enumerate(self.shelves):
            if sx + pw <= self.width and fit_h <= sh and sh <= max(fit_h + 4, int(fit_h * 1.6)):
                waste = sh - fit_h
                if waste < best_waste:
                    best_waste = waste
                    best_idx = idx
        if best_idx >= 0:
            sy, sh, sx = self.shelves[best_idx]
            self.shelves[best_idx][2] = sx + pw
            self.allocated.append((sx + b, sy + b, w, h, label))
            return sx + b, sy + b

        if pw > self.width:
            raise RuntimeError(
                f"Texture atlas width {self.width} cannot fit {w}x{h} with border={b} and pad={self.pad} for '{label}'"
            )

        if self.next_y + fit_h > self.height:
            for idx, (sy, sh, sx) in enumerate(self.shelves):
                if sx + pw <= self.width and fit_h <= sh:
                    self.shelves[idx][2] = sx + pw
                    self.allocated.append((sx + b, sy + b, w, h, label))
                    return sx + b, sy + b
            raise RuntimeError(
                f"Texture atlas ({self.width}x{self.height}) out of space allocating {w}x{h} for '{label}'"
            )
        sy = self.next_y
        self.shelves.append([sy, fit_h, pw])
        self.next_y += ph
        self.allocated.append((b, sy + b, w, h, label))
        return b, sy + b

    def bleed(self, atlas: np.ndarray) -> None:
        """Replicates each rect's edge pixels into its reserved gutter."""
        if self.border <= 0:
            return
        h_atlas, w_atlas = atlas.shape[:2]
        b = self.border
        for x, y, w, h, _ in self.allocated:
            # Left/right strips first, then top/bottom across the expanded width
            # so corners inherit the already-bled side strips.
            if x > 0:
                atlas[y:y + h, max(0, x - b):x] = atlas[y:y + h, x:x + 1]
            if x + w < w_atlas:
                atlas[y:y + h, x + w:min(w_atlas, x + w + b)] = atlas[y:y + h, x + w - 1:x + w]
            xs = max(0, x - b)
            xe = min(w_atlas, x + w + b)
            if y > 0:
                atlas[max(0, y - b):y, xs:xe] = atlas[y:y + 1, xs:xe]
            if y + h < h_atlas:
                atlas[y + h:min(h_atlas, y + h + b), xs:xe] = atlas[y + h - 1:y + h, xs:xe]


def make_solid_patch(w: int, h: int, color: ColorLike) -> np.ndarray:
    """Creates a uniform RGBA numpy patch of size (h, w, 4)."""
    rgba = parse_color(color)
    arr = np.empty((h, w, 4), dtype=np.uint8)
    arr[:, :] = rgba
    return arr


def make_vgradient_patch(
    w: int,
    h: int,
    top_color: ColorLike,
    bottom_color: ColorLike,
    dither: int = 0,
    seed: int = 0,
    mid_color: Optional[ColorLike] = None,
) -> np.ndarray:
    """Creates a vertical 2-stop or 3-stop RGBA gradient patch of size (h, w, 4)."""
    arr = np.empty((h, w, 4), dtype=np.uint8)
    rng = np.random.default_rng(seed) if dither else None
    for y in range(h):
        t = y / max(1, h - 1) if h > 1 else 0.5
        if mid_color is not None:
            if t <= 0.5:
                c = lerp_color(top_color, mid_color, t * 2.0)
            else:
                c = lerp_color(mid_color, bottom_color, (t - 0.5) * 2.0)
        else:
            c = lerp_color(top_color, bottom_color, t)
        arr[y, :] = c
    if dither and rng is not None:
        noise = rng.integers(-dither, dither + 1, size=(h, w, 1))
        rgb = np.clip(arr[:, :, :3].astype(np.int16) + noise, 0, 255).astype(np.uint8)
        arr[:, :, :3] = rgb
    return arr


def make_hgradient_patch(w: int, h: int, left_color: ColorLike, right_color: ColorLike) -> np.ndarray:
    """Creates a horizontal RGBA gradient patch of size (h, w, 4)."""
    arr = np.empty((h, w, 4), dtype=np.uint8)
    for x in range(w):
        t = x / max(1, w - 1) if w > 1 else 0.5
        arr[:, x] = lerp_color(left_color, right_color, t)
    return arr


class YSMModel:
    """Authoring helper for Bedrock 1.12.0 YSM geometry and pixel-art atlas."""

    def __init__(
        self,
        identifier: str = "geometry.model",
        texture_width: int = 512,
        texture_height: int = 512,
        texels_per_unit: float = 2.0,
        visible_bounds_width: float = 3.0,
        visible_bounds_height: float = 3.5,
        visible_bounds_offset: Tuple[float, float, float] = (0.0, 1.25, 0.0),
        atlas_bleed: int = 1,
    ):
        self.identifier = identifier
        self.texture_width = int(texture_width)
        self.texture_height = int(texture_height)
        self.texels_per_unit = float(texels_per_unit)
        self.visible_bounds_width = float(visible_bounds_width)
        self.visible_bounds_height = float(visible_bounds_height)
        self.visible_bounds_offset = [float(v) for v in visible_bounds_offset]
        self.atlas_bleed = max(0, int(atlas_bleed))

        self.bones: Dict[str, dict] = {}
        self.bone_order: List[str] = []
        # `border` keeps every face's gutter private; without it a neighbour's
        # bleed would land inside the same 1px gap and tint the opposite edge.
        self.packer = ShelfPacker(
            self.texture_width,
            self.texture_height,
            pad=0 if self.atlas_bleed else 1,
            border=self.atlas_bleed,
        )
        self.atlas = np.zeros((self.texture_height, self.texture_width, 4), dtype=np.uint8)
        self._cube_count = 0

    def add_bone(
        self,
        name: str,
        parent: Optional[str] = None,
        pivot: Sequence[float] = (0.0, 0.0, 0.0),
        rotation: Optional[Sequence[float]] = None,
        never_render: bool = False,
    ) -> str:
        """Adds a bone to the Bedrock skeleton hierarchy."""
        if name in self.bones:
            raise ValueError(f"Duplicate bone name: {name}")
        if parent is not None and parent not in self.bones:
            raise ValueError(f"Parent bone '{parent}' does not exist when adding '{name}'")
        bone: dict = {
            "name": name,
            "pivot": [round(float(v), 4) for v in pivot],
            "cubes": [],
        }
        if parent is not None:
            bone["parent"] = parent
        if rotation is not None and any(abs(float(r)) > 1e-6 for r in rotation):
            bone["rotation"] = [round(float(v), 4) for v in rotation]
        if never_render:
            bone["neverRender"] = True
        self.bones[name] = bone
        self.bone_order.append(name)
        return name

    def _face_pixel_dims(self, size: Sequence[float], face: str, uv_scale: float) -> Tuple[int, int]:
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        if face in ("north", "south"):
            w, h = sx, sy
        elif face in ("east", "west"):
            w, h = sz, sy
        elif face in ("up", "down"):
            w, h = sx, sz
        else:
            raise ValueError(f"Unknown face: {face}")
        pw = max(1, int(round(w * uv_scale)))
        ph = max(1, int(round(h * uv_scale)))
        return pw, ph

    def add_cube(
        self,
        bone: str,
        origin: Sequence[float],
        size: Sequence[float],
        pivot: Optional[Sequence[float]] = None,
        rotation: Optional[Sequence[float]] = None,
        inflate: float = 0.0,
        name: Optional[str] = None,
        solid_color: Optional[ColorLike] = None,
        vgradient: Optional[Tuple[ColorLike, ColorLike]] = None,
        vgradient3: Optional[Tuple[ColorLike, ColorLike, ColorLike]] = None,
        dither: int = 0,
        face_colors: Optional[Dict[str, ColorLike]] = None,
        face_patches: Optional[Dict[str, np.ndarray]] = None,
        face_painter: Optional[Callable[[str, int, int], np.ndarray]] = None,
        face_dims_override: Optional[Dict[str, Tuple[int, int]]] = None,
        uv_scale: Optional[float] = None,
        share_sides: bool = False,
    ) -> dict:
        """
        Adds a cube with strict YSM 2.6.0 integer per-face UV packing and texture painting.
        If share_sides=True and no custom per-face patches/painter/face_colors are provided,
        uses compact 2x2 or shared gradient UVs for small detail cubes to save atlas space.
        """
        if bone not in self.bones:
            raise ValueError(f"Unknown bone '{bone}'")
        self._cube_count += 1
        label = name or f"{bone}_c{self._cube_count}"
        scale = float(uv_scale) if uv_scale is not None else self.texels_per_unit

        ox, oy, oz = (round(float(origin[0]), 4), round(float(origin[1]), 4), round(float(origin[2]), 4))
        sx, sy, sz = (round(float(size[0]), 4), round(float(size[1]), 4), round(float(size[2]), 4))

        uv_dict: Dict[str, dict] = {}
        shared_slot: Optional[Tuple[int, int, int, int]] = None

        for fi, face in enumerate(ALL_FACES):
            if face_patches and face in face_patches:
                patch = np.asarray(face_patches[face], dtype=np.uint8)
                ph, pw = patch.shape[0], patch.shape[1]
            else:
                if face_dims_override and face in face_dims_override:
                    pw, ph = face_dims_override[face]
                else:
                    pw, ph = self._face_pixel_dims((sx, sy, sz), face, scale)

                if share_sides and face_painter is None and face_colors is None and face_patches is None:
                    if solid_color is not None:
                        if shared_slot is None:
                            u, v = self.packer.alloc(2, 2, f"{label}_solid")
                            self.atlas[v:v + 2, u:u + 2] = parse_color(solid_color)
                            shared_slot = (u, v, 2, 2)
                        u, v, sw, sh = shared_slot
                        uv_dict[face] = {"uv": [u, v], "uv_size": [sw, sh]}
                        continue
                    elif (vgradient or vgradient3) and face in ("north", "south", "east", "west"):
                        if shared_slot is None:
                            gh = max(2, ph)
                            u, v = self.packer.alloc(2, gh, f"{label}_vgrad")
                            if vgradient3:
                                patch = make_vgradient_patch(
                                    2, gh, vgradient3[0], vgradient3[2],
                                    dither=dither, seed=self._cube_count, mid_color=vgradient3[1]
                                )
                            else:
                                patch = make_vgradient_patch(
                                    2, gh, vgradient[0], vgradient[1],
                                    dither=dither, seed=self._cube_count
                                )
                            self.atlas[v:v + gh, u:u + 2] = patch
                            shared_slot = (u, v, 2, gh)
                        u, v, sw, sh = shared_slot
                        uv_dict[face] = {"uv": [u, v], "uv_size": [sw, sh]}
                        continue

                if face_painter is not None:
                    patch = np.asarray(face_painter(face, pw, ph), dtype=np.uint8)
                    ph, pw = patch.shape[0], patch.shape[1]
                elif face_colors and face in face_colors:
                    patch = make_solid_patch(pw, ph, face_colors[face])
                elif vgradient3 is not None:
                    if face == "up":
                        patch = make_solid_patch(pw, ph, vgradient3[0])
                    elif face == "down":
                        patch = make_solid_patch(pw, ph, vgradient3[2])
                    else:
                        patch = make_vgradient_patch(
                            pw, ph, vgradient3[0], vgradient3[2],
                            dither=dither, seed=self._cube_count * 13 + fi, mid_color=vgradient3[1]
                        )
                elif vgradient is not None:
                    if face == "up":
                        patch = make_solid_patch(pw, ph, vgradient[0])
                    elif face == "down":
                        patch = make_solid_patch(pw, ph, vgradient[1])
                    else:
                        patch = make_vgradient_patch(
                            pw, ph, vgradient[0], vgradient[1],
                            dither=dither, seed=self._cube_count * 13 + fi
                        )
                elif solid_color is not None:
                    patch = make_solid_patch(pw, ph, solid_color)
                else:
                    patch = make_solid_patch(pw, ph, (240, 236, 250, 255))

            pw = max(1, int(pw))
            ph = max(1, int(ph))
            u, v = self.packer.alloc(pw, ph, f"{label}_{face}")
            self.atlas[v:v + ph, u:u + pw] = patch[:ph, :pw]
            uv_dict[face] = {"uv": [int(u), int(v)], "uv_size": [int(pw), int(ph)]}

        cube: dict = {
            "origin": [ox, oy, oz],
            "size": [sx, sy, sz],
            "uv": uv_dict,
        }
        if abs(float(inflate)) > 1e-6:
            cube["inflate"] = round(float(inflate), 4)
        if pivot is not None:
            cube["pivot"] = [round(float(p), 4) for p in pivot]
        if rotation is not None and any(abs(float(r)) > 1e-6 for r in rotation):
            cube["rotation"] = [round(float(r), 4) for r in rotation]
            if "pivot" not in cube:
                cube["pivot"] = [
                    round(ox + sx * 0.5, 4),
                    round(oy + sy * 0.5, 4),
                    round(oz + sz * 0.5, 4),
                ]

        self.bones[bone]["cubes"].append(cube)
        return cube

    def add_mirrored_cube(
        self,
        right_bone: str,
        left_bone: str,
        origin: Sequence[float],
        size: Sequence[float],
        pivot: Optional[Sequence[float]] = None,
        rotation: Optional[Sequence[float]] = None,
        **kwargs,
    ) -> Tuple[dict, dict]:
        """
        Adds a cube on `right_bone` (negative X in Bedrock) and its exact X=0 mirror on
        `left_bone` (positive X in Bedrock), flipping Y/Z rotation signs and swapping
        east/west face textures cleanly.
        """
        c_right = self.add_cube(
            right_bone, origin=origin, size=size, pivot=pivot, rotation=rotation, **kwargs
        )

        ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
        sx, sy, sz = float(size[0]), float(size[1]), float(size[2])
        m_origin = [-(ox + sx), oy, oz]
        m_pivot = [-float(pivot[0]), float(pivot[1]), float(pivot[2])] if pivot is not None else None
        m_rot = [float(rotation[0]), -float(rotation[1]), -float(rotation[2])] if rotation is not None else None

        m_kwargs = dict(kwargs)
        if "name" in m_kwargs and m_kwargs["name"]:
            m_kwargs["name"] = m_kwargs["name"] + "_L"
        if "face_colors" in m_kwargs and m_kwargs["face_colors"]:
            fc = dict(m_kwargs["face_colors"])
            e_col, w_col = fc.get("east"), fc.get("west")
            if e_col is not None:
                fc["west"] = e_col
            elif "west" in fc:
                del fc["west"]
            if w_col is not None:
                fc["east"] = w_col
            elif "east" in fc:
                del fc["east"]
            m_kwargs["face_colors"] = fc
        if "face_patches" in m_kwargs and m_kwargs["face_patches"]:
            fp = {}
            for k, arr in m_kwargs["face_patches"].items():
                if k == "east":
                    fp["west"] = np.ascontiguousarray(arr[:, ::-1, :])
                elif k == "west":
                    fp["east"] = np.ascontiguousarray(arr[:, ::-1, :])
                else:
                    fp[k] = np.ascontiguousarray(arr[:, ::-1, :])
            m_kwargs["face_patches"] = fp
        if "face_painter" in m_kwargs and m_kwargs["face_painter"] is not None:
            orig_painter = m_kwargs["face_painter"]

            def mirrored_painter(face: str, w: int, h: int) -> np.ndarray:
                src_face = "west" if face == "east" else ("east" if face == "west" else face)
                p = np.asarray(orig_painter(src_face, w, h), dtype=np.uint8)
                return np.ascontiguousarray(p[:, ::-1, :])

            m_kwargs["face_painter"] = mirrored_painter

        c_left = self.add_cube(
            left_bone, origin=m_origin, size=size, pivot=m_pivot, rotation=m_rot, **m_kwargs
        )
        return c_right, c_left

    def build_geo_dict(self, bones_list: Optional[List[dict]] = None) -> dict:
        """Serializes the current model into a Bedrock 1.12.0 geometry dictionary."""
        if bones_list is None:
            bones_list = []
            for name in self.bone_order:
                b = copy.deepcopy(self.bones[name])
                if not b["cubes"]:
                    del b["cubes"]
                bones_list.append(b)
        return {
            "format_version": "1.12.0",
            "minecraft:geometry": [
                {
                    "description": {
                        "identifier": self.identifier,
                        "texture_width": self.texture_width,
                        "texture_height": self.texture_height,
                        "visible_bounds_width": self.visible_bounds_width,
                        "visible_bounds_height": self.visible_bounds_height,
                        "visible_bounds_offset": self.visible_bounds_offset,
                    },
                    "bones": bones_list,
                }
            ],
        }

    def export_main_json(self, path: Union[str, Path]) -> Path:
        """Writes main.json (UTF-8 without BOM)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.build_geo_dict()
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return p

    def export_arm_json(self, path: Union[str, Path]) -> Path:
        """
        Extracts LeftArm and RightArm hierarchies to root for YSM first-person rendering,
        zeroing LeftArm / RightArm root rotations per YSM spec.
        """
        arm_roots = {"LeftArm", "RightArm"}
        selected: List[dict] = []

        def is_under_arm(bname: str) -> bool:
            cur: Optional[str] = bname
            while cur is not None:
                if cur in arm_roots:
                    return True
                cur = self.bones[cur].get("parent")
            return False

        for name in self.bone_order:
            if is_under_arm(name):
                b = copy.deepcopy(self.bones[name])
                if name in arm_roots:
                    b.pop("parent", None)
                    b["rotation"] = [0.0, 0.0, 0.0]
                if not b["cubes"]:
                    del b["cubes"]
                selected.append(b)

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self.build_geo_dict(selected)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return p

    def export_texture(self, path: Union[str, Path]) -> Path:
        """Writes the packed RGBA texture atlas PNG, with edge bleed applied."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.packer.bleed(self.atlas)
        Image.fromarray(self.atlas, mode="RGBA").save(p)
        return p

    def export_uv_debug(self, path: Union[str, Path]) -> Path:
        """Writes an annotated UV atlas allocation preview image."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        self.packer.bleed(self.atlas)
        bg = np.full((self.texture_height, self.texture_width, 4), (30, 32, 44, 255), dtype=np.uint8)
        alpha = self.atlas[:, :, 3:4].astype(np.float32) / 255.0
        comp = (self.atlas[:, :, :3] * alpha + bg[:, :, :3] * (1.0 - alpha)).astype(np.uint8)
        img = Image.fromarray(comp, mode="RGB")
        draw = ImageDraw.Draw(img)
        for x, y, w, h, _ in self.packer.allocated:
            draw.rectangle([x, y, x + w - 1, y + h - 1], outline=(255, 90, 140))
        img.save(p)
        return p

    def stats(self) -> dict:
        """Returns geometry and atlas utilization summary statistics.

        ``atlas_fill_pct`` counts painted face pixels only; ``atlas_footprint_pct``
        also counts the private bleed gutters, so it is the value that fills up
        first when ``atlas_bleed`` is enabled.
        """
        used_px = sum(w * h for _, _, w, h, _ in self.packer.allocated)
        footprint_px = sum(
            (w + 2 * self.packer.border) * (h + 2 * self.packer.border)
            for _, _, w, h, _ in self.packer.allocated
        )
        total_px = self.texture_width * self.texture_height
        return {
            "bones": len(self.bone_order),
            "cubes": self._cube_count,
            "uv_rects": len(self.packer.allocated),
            "atlas_bleed": self.packer.border,
            "atlas_used_y": self.packer.next_y,
            "atlas_fill_pct": round(100.0 * used_px / total_px, 2),
            "atlas_footprint_pct": round(100.0 * footprint_px / total_px, 2),
        }
