"""
Fast Vectorized NumPy + PIL Z-Buffered 3D Software Renderer for Bedrock 1.12.0 / YSM Models.

Features:
  - Exact Bedrock <-> Right-Handed Blockbench/GeckoLib math:
      x_rh = -x_bedrock, y_rh = y_bedrock, z_rh = z_bedrock
      rotation [rx, ry, rz] (deg) -> R = Rz(+rz) @ Ry(-ry) @ Rx(-rx) around pivot_rh
  - Both Perspective (fov_deg) and Strict Orthographic (ortho_scale) cameras
  - Tangent-plane-corrected Screen-Space Ambient Occlusion (SSAO) + 3-point studio lighting
  - Automatic bounding-box camera framing for arbitrary model heights
  - Built-in Turnaround Compare, Clay Check, 50/50 Overlay Alignment, Closeups, Animation Poses & Skeleton Pivots
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union
import numpy as np
from PIL import Image, ImageDraw


def _rot_x(rad: float) -> np.ndarray:
    c, s = math.cos(rad), math.sin(rad)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def _rot_y(rad: float) -> np.ndarray:
    c, s = math.cos(rad), math.sin(rad)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def _rot_z(rad: float) -> np.ndarray:
    c, s = math.cos(rad), math.sin(rad)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def bedrock_rot_matrix(rot_deg: Sequence[float]) -> np.ndarray:
    rx, ry, rz = float(rot_deg[0]), float(rot_deg[1]), float(rot_deg[2])
    ax = -math.radians(rx)
    ay = -math.radians(ry)
    az = math.radians(rz)
    return _rot_z(az) @ _rot_y(ay) @ _rot_x(ax)


def _eval_molang(val, anim_time: float) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if not isinstance(val, str):
        return 0.0
    expr = val.strip()
    expr = expr.replace("query.anim_time", str(anim_time))
    expr = expr.replace("q.anim_time", str(anim_time))
    expr = expr.replace("query.life_time", str(anim_time))
    expr = expr.replace("q.life_time", str(anim_time))
    expr = expr.replace("query.modified_distance_moved", str(anim_time * 4.5))
    expr = expr.replace("query.modified_move_speed", "1.0")
    expr = expr.replace("math.sin", "_dsin")
    expr = expr.replace("math.cos", "_dcos")
    expr = expr.replace("math.abs", "abs")
    expr = expr.replace("math.clamp", "_clamp")
    expr = expr.replace("math.max", "max")
    expr = expr.replace("math.min", "min")
    expr = expr.replace("math.pi", str(math.pi))
    env = {
        "__builtins__": {},
        "_dsin": lambda d: math.sin(math.radians(d)),
        "_dcos": lambda d: math.cos(math.radians(d)),
        "_clamp": lambda x, lo, hi: max(lo, min(hi, x)),
        "abs": abs,
        "max": max,
        "min": min,
    }
    try:
        return float(eval(expr, env, {}))
    except Exception:
        return 0.0


def _eval_vec3(raw, anim_time: float, default=(0.0, 0.0, 0.0)) -> np.ndarray:
    if raw is None:
        return np.array(default, dtype=np.float64)
    if isinstance(raw, (int, float, str)):
        v = _eval_molang(raw, anim_time)
        return np.array([v, v, v], dtype=np.float64)
    if isinstance(raw, list):
        return np.array([_eval_molang(x, anim_time) for x in raw[:3]], dtype=np.float64)
    if isinstance(raw, dict):
        if "vector" in raw:
            return _eval_vec3(raw["vector"], anim_time, default)
        if "post" in raw:
            return _eval_vec3(raw["post"], anim_time, default)
        kfs = []
        for k, v in raw.items():
            try:
                t = float(k)
            except ValueError:
                continue
            kfs.append((t, v))
        if not kfs:
            return np.array(default, dtype=np.float64)
        kfs.sort(key=lambda kv: kv[0])
        if anim_time <= kfs[0][0]:
            return _eval_vec3(kfs[0][1], anim_time, default)
        if anim_time >= kfs[-1][0]:
            return _eval_vec3(kfs[-1][1], anim_time, default)
        for i in range(len(kfs) - 1):
            t0, v0 = kfs[i]
            t1, v1 = kfs[i + 1]
            if t0 <= anim_time <= t1:
                p0 = _eval_vec3(v0["post"] if isinstance(v0, dict) and "post" in v0 else v0, anim_time, default)
                p1 = _eval_vec3(v1["pre"] if isinstance(v1, dict) and "pre" in v1 else v1, anim_time, default)
                dt = max(1e-6, t1 - t0)
                u = (anim_time - t0) / dt
                if isinstance(v0, dict) and v0.get("lerp_mode") == "catmullrom":
                    u = u * u * (3.0 - 2.0 * u)
                return p0 * (1.0 - u) + p1 * u
    return np.array(default, dtype=np.float64)


def evaluate_animation(anim_json: dict, anim_name: str, t: float) -> Dict[str, dict]:
    """Evaluates a Bedrock animation dictionary at time `t` seconds."""
    anims = anim_json.get("animations", {})
    if anim_name not in anims:
        return {}
    anim = anims[anim_name]
    length = float(anim.get("animation_length", 0.0) or 0.0)
    if anim.get("loop") and length > 1e-6:
        t = t % length
    out: Dict[str, dict] = {}
    for bname, tracks in anim.get("bones", {}).items():
        if not isinstance(tracks, dict):
            continue
        out[bname] = {
            "rotation": _eval_vec3(tracks.get("rotation"), t, (0.0, 0.0, 0.0)),
            "position": _eval_vec3(tracks.get("position"), t, (0.0, 0.0, 0.0)),
            "scale": _eval_vec3(tracks.get("scale"), t, (1.0, 1.0, 1.0)),
        }
    return out


class BedrockScene:
    """Loads Bedrock 1.12.0 JSON + RGBA texture and builds world-space triangles."""

    def __init__(self, geo_path: Union[str, Path], tex_path: Union[str, Path]):
        with open(geo_path, "r", encoding="utf-8") as f:
            self.geo = json.load(f)
        with Image.open(tex_path) as tex_im:
            self.tex = np.array(tex_im.convert("RGBA"), dtype=np.uint8)
        self.tex_h, self.tex_w = self.tex.shape[:2]

        g0 = self.geo["minecraft:geometry"][0]
        desc = g0["description"]
        self.uv_w = float(desc["texture_width"])
        self.uv_h = float(desc["texture_height"])
        self.bones_list = g0["bones"]
        self.bones_map = {b["name"]: b for b in self.bones_list}

    def compute_bone_transforms(
        self, anim_pose: Optional[Dict[str, dict]] = None
    ) -> Dict[str, Tuple[np.ndarray, np.ndarray, bool]]:
        """Returns {bone_name: (M_4x4, world_pivot_rh, visible)}."""
        anim_pose = anim_pose or {}
        cache: Dict[str, Tuple[np.ndarray, np.ndarray, bool]] = {}

        def get_xform(bname: str) -> Tuple[np.ndarray, np.ndarray, bool]:
            if bname in cache:
                return cache[bname]
            b = self.bones_map[bname]
            parent_name = b.get("parent")
            if parent_name and parent_name in self.bones_map:
                p_mat, _, p_vis = get_xform(parent_name)
            else:
                p_mat = np.eye(4, dtype=np.float64)
                p_vis = True

            vis = p_vis and (not b.get("neverRender", False))

            bp = b.get("pivot", [0.0, 0.0, 0.0])
            piv_rh = np.array([-float(bp[0]), float(bp[1]), float(bp[2])], dtype=np.float64)

            base_rot = np.array(b.get("rotation", [0.0, 0.0, 0.0]), dtype=np.float64)
            pose = anim_pose.get(bname, {})
            anim_rot = pose.get("rotation", np.zeros(3))
            anim_pos = pose.get("position", np.zeros(3))
            anim_scale = pose.get("scale", np.ones(3))

            if np.any(np.abs(anim_scale) < 1e-4):
                vis = False

            R = bedrock_rot_matrix(base_rot + anim_rot)
            S = np.diag([float(anim_scale[0]), float(anim_scale[1]), float(anim_scale[2])])
            RS = R @ S
            pos_rh = np.array([-float(anim_pos[0]), float(anim_pos[1]), float(anim_pos[2])], dtype=np.float64)

            M_local = np.eye(4, dtype=np.float64)
            M_local[:3, :3] = RS
            M_local[:3, 3] = piv_rh + pos_rh - RS @ piv_rh

            M_world = p_mat @ M_local
            wp = (M_world @ np.array([piv_rh[0], piv_rh[1], piv_rh[2], 1.0]))[:3]
            cache[bname] = (M_world, wp, vis)
            return cache[bname]

        for b in self.bones_list:
            get_xform(b["name"])
        return cache

    def build_triangles(self, anim_pose: Optional[Dict[str, dict]] = None):
        """Returns arrays: verts (N,3,3), uvs (N,3,2), normals (N,3)."""
        xforms = self.compute_bone_transforms(anim_pose)
        tri_verts = []
        tri_uvs = []
        tri_normals = []

        sx_uv = self.tex_w / self.uv_w
        sy_uv = self.tex_h / self.uv_h

        for b in self.bones_list:
            bname = b["name"]
            M_bone, _, vis = xforms[bname]
            if not vis:
                continue
            for cube in b.get("cubes", []):
                ox, oy, oz = [float(v) for v in cube["origin"]]
                sx, sy, sz = [float(v) for v in cube["size"]]
                inf = float(cube.get("inflate", 0.0))

                fx = -(ox + sx) - inf
                tx = -ox + inf
                fy = oy - inf
                ty = oy + sy + inf
                fz = oz - inf
                tz = oz + sz + inf

                M_cube = np.eye(4, dtype=np.float64)
                if "rotation" in cube and any(abs(float(r)) > 1e-6 for r in cube["rotation"]):
                    cp = cube.get("pivot", [ox + sx * 0.5, oy + sy * 0.5, oz + sz * 0.5])
                    cp_rh = np.array([-float(cp[0]), float(cp[1]), float(cp[2])], dtype=np.float64)
                    Rc = bedrock_rot_matrix(cube["rotation"])
                    M_cube[:3, :3] = Rc
                    M_cube[:3, 3] = cp_rh - Rc @ cp_rh

                M = M_bone @ M_cube
                R3 = M[:3, :3]
                t3 = M[:3, 3]

                uv_obj = cube.get("uv", {})
                if not isinstance(uv_obj, dict):
                    continue

                faces_spec = {
                    "north": (
                        np.array([[tx, ty, fz], [fx, ty, fz], [fx, fy, fz], [tx, fy, fz]], dtype=np.float64),
                        np.array([0.0, 0.0, -1.0]),
                    ),
                    "south": (
                        np.array([[fx, ty, tz], [tx, ty, tz], [tx, fy, tz], [fx, fy, tz]], dtype=np.float64),
                        np.array([0.0, 0.0, 1.0]),
                    ),
                    "east": (
                        np.array([[tx, ty, tz], [tx, ty, fz], [tx, fy, fz], [tx, fy, tz]], dtype=np.float64),
                        np.array([1.0, 0.0, 0.0]),
                    ),
                    "west": (
                        np.array([[fx, ty, fz], [fx, ty, tz], [fx, fy, tz], [fx, fy, fz]], dtype=np.float64),
                        np.array([-1.0, 0.0, 0.0]),
                    ),
                    "up": (
                        np.array([[tx, ty, tz], [fx, ty, tz], [fx, ty, fz], [tx, ty, fz]], dtype=np.float64),
                        np.array([0.0, 1.0, 0.0]),
                    ),
                    "down": (
                        np.array([[tx, fy, fz], [fx, fy, fz], [fx, fy, tz], [tx, fy, tz]], dtype=np.float64),
                        np.array([0.0, -1.0, 0.0]),
                    ),
                }

                for fname, (pts, nrm) in faces_spec.items():
                    fuv = uv_obj.get(fname)
                    if not fuv:
                        continue
                    u0, v0 = float(fuv["uv"][0]) * sx_uv, float(fuv["uv"][1]) * sy_uv
                    uw, vh = float(fuv["uv_size"][0]) * sx_uv, float(fuv["uv_size"][1]) * sy_uv
                    if abs(uw) < 1e-6 or abs(vh) < 1e-6:
                        continue

                    wpts = pts @ R3.T + t3
                    wnrm = R3 @ nrm
                    nlen = np.linalg.norm(wnrm)
                    if nlen > 1e-8:
                        wnrm = wnrm / nlen

                    q_uv = np.array(
                        [[u0, v0], [u0 + uw, v0], [u0 + uw, v0 + vh], [u0, v0 + vh]],
                        dtype=np.float64,
                    )
                    tri_verts.append(wpts[[0, 2, 1]])
                    tri_uvs.append(q_uv[[0, 2, 1]])
                    tri_normals.append(wnrm)

                    tri_verts.append(wpts[[0, 3, 2]])
                    tri_uvs.append(q_uv[[0, 3, 2]])
                    tri_normals.append(wnrm)

        if not tri_verts:
            return (
                np.zeros((0, 3, 3), dtype=np.float64),
                np.zeros((0, 3, 2), dtype=np.float64),
                np.zeros((0, 3), dtype=np.float64),
            )
        return np.array(tri_verts), np.array(tri_uvs), np.array(tri_normals)

    def compute_bounds(self, anim_pose: Optional[Dict[str, dict]] = None) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (min_xyz, max_xyz) bounding box of the visible model in RH space."""
        verts, _, _ = self.build_triangles(anim_pose)
        if len(verts) == 0:
            return np.array([-4.0, 0.0, -4.0]), np.array([4.0, 32.0, 4.0])
        pts = verts.reshape(-1, 3)
        return pts.min(axis=0), pts.max(axis=0)


def _auto_framing(
    scene: BedrockScene,
    target_y: Optional[float] = None,
    ortho_scale: Optional[float] = None,
) -> Tuple[float, float, float]:
    """Automatically computes centered Y, orthographic height, and perspective distance from bounds."""
    bmin, bmax = scene.compute_bounds()
    h = max(8.0, float(bmax[1] - bmin[1]))
    cy = float(0.5 * (bmin[1] + bmax[1])) if target_y is None else float(target_y)
    oscale = (h * 1.055) if ortho_scale is None else float(ortho_scale)
    dist = max(40.0, h * 2.68)
    return cy, oscale, dist


def _compute_ssao(
    zbuf: np.ndarray,
    nbuf_cam: np.ndarray,
    px_per_unit: float,
    clay: bool = False,
) -> np.ndarray:
    """
    Tangent-plane-corrected Screen-Space Ambient Occlusion (SSAO).
    Uses camera-space normals to cancel depth slope on tilted flat planes so 3/4 perspective
    views have zero self-shadowing artifacts while producing soft studio contact & crevice AO.
    """
    H, W = zbuf.shape
    valid = np.isfinite(zbuf)
    if not np.any(valid):
        return np.zeros((H, W), dtype=np.float32)

    z = np.where(valid, zbuf, 1e6).astype(np.float32)
    nx = nbuf_cam[:, :, 0]
    ny = nbuf_cam[:, :, 1]
    nz_abs = np.maximum(0.35, np.abs(nbuf_cam[:, :, 2]))
    inv_ppu = 1.0 / max(1.0, float(px_per_unit))
    slope_x = (nx / nz_abs) * inv_ppu
    slope_y = (-ny / nz_abs) * inv_ppu

    max_range = 2.4 if not clay else 2.8
    bias = 0.08

    r1 = max(1, int(round(px_per_unit * 0.22)))
    r2 = max(2, int(round(px_per_unit * 0.52)))
    r3 = max(4, int(round(px_per_unit * 0.95)))

    angles = [0.0, 0.7854, 1.5708, 2.3562, 3.1416, 3.9270, 4.7124, 5.4978]
    offsets = []
    for rad, weight in ((r1, 1.25), (r2, 1.0), (r3, 0.55)):
        for ang in angles:
            dy = int(round(math.sin(ang) * rad))
            dx = int(round(math.cos(ang) * rad))
            if dy != 0 or dx != 0:
                offsets.append((dy, dx, weight))

    occ = np.zeros((H, W), dtype=np.float32)
    w_sum = 0.0

    for dy, dx, wt in offsets:
        y0_src, y1_src = max(0, dy), min(H, H + dy)
        x0_src, x1_src = max(0, dx), min(W, W + dx)
        y0_dst, y1_dst = max(0, -dy), min(H, H - dy)
        x0_dst, x1_dst = max(0, -dx), min(W, W - dx)

        zn = z[y0_src:y1_src, x0_src:x1_src]
        zc = z[y0_dst:y1_dst, x0_dst:x1_dst]
        vn = valid[y0_src:y1_src, x0_src:x1_src]
        vc = valid[y0_dst:y1_dst, x0_dst:x1_dst]

        z_plane = zc + slope_x[y0_dst:y1_dst, x0_dst:x1_dst] * dx + slope_y[y0_dst:y1_dst, x0_dst:x1_dst] * dy
        dz = z_plane - zn
        in_range = vc & vn & (dz > bias) & (dz < max_range)
        falloff = np.clip(1.0 - dz / max_range, 0.0, 1.0)
        contrib = np.where(in_range, falloff ** 1.25, 0.0)
        if dy < 0:
            contrib *= 1.25
        occ[y0_dst:y1_dst, x0_dst:x1_dst] += contrib * wt
        w_sum += wt

    if w_sum > 0:
        occ /= (w_sum * 0.44)
    ao = np.clip(occ, 0.0, 1.0)

    ao_pad = np.pad(ao, 1, mode="edge")
    z_pad = np.pad(z, 1, mode="edge")
    v_pad = np.pad(valid, 1, mode="constant", constant_values=False)
    acc = np.zeros((H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            sub_z = z_pad[1 + oy:1 + oy + H, 1 + ox:1 + ox + W]
            sub_v = v_pad[1 + oy:1 + oy + H, 1 + ox:1 + ox + W]
            same_surf = valid & sub_v & (np.abs(sub_z - z) < 0.70)
            w_k = 2.0 if (oy == 0 and ox == 0) else 1.0
            acc += np.where(same_surf, ao_pad[1 + oy:1 + oy + H, 1 + ox:1 + ox + W] * w_k, 0.0)
            cnt += np.where(same_surf, w_k, 0.0)
    ao = np.where(cnt > 0, acc / np.maximum(cnt, 1e-5), 0.0)
    return ao


def render_view(
    scene: BedrockScene,
    width: int = 440,
    height: int = 700,
    yaw_deg: float = 0.0,
    pitch_deg: float = 4.0,
    target: Sequence[float] = (0.0, 16.5, 0.0),
    distance: float = 78.0,
    fov_deg: float = 26.0,
    ortho_scale: Optional[float] = None,
    anim_pose: Optional[Dict[str, dict]] = None,
    bg_color: Tuple[int, int, int] = (255, 255, 255),
    ground_shadow: bool = True,
    clay: bool = False,
    ssao: bool = True,
) -> Image.Image:
    """
    Camera orbit convention in Right-Handed Blockbench space:
      yaw_deg = 0   : Straight Front (camera at -Z looking toward +Z)
      yaw_deg = -24 : 3/4 Front (camera toward character's right-front)
      yaw_deg = +90 : Straight Left-Side profile (camera at -X_rh, character faces LEFT)
      yaw_deg = 180 : Straight Back (camera at +Z looking toward -Z)
    """
    verts, uvs, normals = scene.build_triangles(anim_pose)
    tgt = np.array(target, dtype=np.float64)

    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    dir_x = -math.sin(yaw) * math.cos(pitch)
    dir_y = math.sin(pitch)
    dir_z = -math.cos(yaw) * math.cos(pitch)
    cam_pos = tgt + np.array([dir_x, dir_y, dir_z], dtype=np.float64) * distance

    forward = tgt - cam_pos
    forward /= np.linalg.norm(forward)
    world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
    cam_right = np.cross(forward, world_up)
    if np.linalg.norm(cam_right) < 1e-6:
        cam_right = np.array([1.0, 0.0, 0.0])
    else:
        cam_right /= np.linalg.norm(cam_right)
    cam_up = np.cross(cam_right, forward)

    img = np.empty((height, width, 3), dtype=np.uint8)
    img[:, :] = bg_color
    zbuf = np.full((height, width), np.inf, dtype=np.float64)
    nbuf = np.zeros((height, width, 3), dtype=np.float32)

    if ortho_scale is not None:
        ppu_cam = height / ortho_scale
    else:
        ppu_cam = (height * 0.5) / (max(1.0, distance) * math.tan(math.radians(fov_deg * 0.5)))

    if ground_shadow and pitch_deg >= -5.0:
        yy, xx = np.mgrid[0:height, 0:width]
        rel0 = np.array([0.0, 0.0, 0.0]) - cam_pos
        cz0 = float(np.dot(rel0, forward))
        if cz0 > 1.0:
            if ortho_scale is not None:
                px_per_unit = height / ortho_scale
            else:
                px_per_unit = (height * 0.5) / (cz0 * math.tan(math.radians(fov_deg * 0.5)))
            cx_s = width * 0.5 + float(np.dot(rel0, cam_right)) * px_per_unit
            cy_s = height * 0.5 - float(np.dot(rel0, cam_up)) * px_per_unit
            rx = max(6.0, 5.2 * px_per_unit)
            ry = max(2.0, 1.4 * px_per_unit)
            d2 = ((xx - cx_s) / rx) ** 2 + ((yy - cy_s) / ry) ** 2
            sh = np.clip(1.0 - d2, 0.0, 1.0) ** 1.6 * 0.08
            img = np.clip(img.astype(np.float32) * (1.0 - sh[:, :, None]), 0, 255).astype(np.uint8)

    if len(verts) == 0:
        return Image.fromarray(img, mode="RGB")

    rel = verts - cam_pos[None, None, :]
    cx = np.einsum("ijk,k->ij", rel, cam_right)
    cy = np.einsum("ijk,k->ij", rel, cam_up)
    cz = np.einsum("ijk,k->ij", rel, forward)

    light_key = cam_up * 0.62 - cam_right * 0.42 - forward * 0.66
    light_key /= np.linalg.norm(light_key)
    light_fill = cam_up * 0.25 + cam_right * 0.68 - forward * 0.45
    light_fill /= np.linalg.norm(light_fill)

    ndotl1 = np.clip(np.einsum("ik,k->i", normals, light_key), 0.0, 1.0)
    ndotl2 = np.clip(np.einsum("ik,k->i", normals, light_fill), 0.0, 1.0)
    up_boost = np.clip(normals[:, 1], -1.0, 1.0) * (0.14 if clay else 0.09)
    if clay:
        shade = np.clip(0.50 + 0.40 * ndotl1 + 0.14 * ndotl2 + up_boost, 0.36, 1.04)
    else:
        shade = np.clip(0.78 + 0.20 * ndotl1 + 0.08 * ndotl2 + up_boost, 0.68, 1.05)

    if ortho_scale is not None:
        scale = height / ortho_scale
        sx = width * 0.5 + cx * scale
        sy = height * 0.5 - cy * scale
        inv_z = np.ones_like(cz)
    else:
        f = (height * 0.5) / math.tan(math.radians(fov_deg * 0.5))
        safe_cz = np.maximum(cz, 0.1)
        inv_z = 1.0 / safe_cz
        sx = width * 0.5 + cx * f * inv_z
        sy = height * 0.5 - cy * f * inv_z

    normals_cam = np.stack([
        np.einsum("ik,k->i", normals, cam_right),
        np.einsum("ik,k->i", normals, cam_up),
        np.einsum("ik,k->i", normals, forward),
    ], axis=1).astype(np.float32)

    tex = scene.tex
    tw, th = scene.tex_w, scene.tex_h

    for i in range(len(verts)):
        if cz[i, 0] <= 0.2 or cz[i, 1] <= 0.2 or cz[i, 2] <= 0.2:
            continue
        x0, x1, x2 = sx[i, 0], sx[i, 1], sx[i, 2]
        y0, y1, y2 = sy[i, 0], sy[i, 1], sy[i, 2]

        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area <= 1e-6:
            tri_center = verts[i].mean(axis=0)
            if np.dot(normals[i], cam_pos - tri_center) <= 0.0:
                continue
            if abs(area) <= 1e-6:
                continue
            x1, x2 = x2, x1
            y1, y2 = y2, y1
            area = -area
            iz0, iz1, iz2 = inv_z[i, 0], inv_z[i, 2], inv_z[i, 1]
            z0, z1, z2 = cz[i, 0], cz[i, 2], cz[i, 1]
            u0, u1, u2 = uvs[i, 0, 0], uvs[i, 2, 0], uvs[i, 1, 0]
            v0, v1, v2 = uvs[i, 0, 1], uvs[i, 2, 1], uvs[i, 1, 1]
        else:
            tri_center = verts[i].mean(axis=0)
            if np.dot(normals[i], cam_pos - tri_center) <= 0.0:
                continue
            iz0, iz1, iz2 = inv_z[i, 0], inv_z[i, 1], inv_z[i, 2]
            z0, z1, z2 = cz[i, 0], cz[i, 1], cz[i, 2]
            u0, u1, u2 = uvs[i, 0, 0], uvs[i, 1, 0], uvs[i, 2, 0]
            v0, v1, v2 = uvs[i, 0, 1], uvs[i, 1, 1], uvs[i, 2, 1]

        min_x = max(0, int(math.floor(min(x0, x1, x2))))
        max_x = min(width - 1, int(math.ceil(max(x0, x1, x2))))
        min_y = max(0, int(math.floor(min(y0, y1, y2))))
        max_y = min(height - 1, int(math.ceil(max(y0, y1, y2))))
        if min_x > max_x or min_y > max_y:
            continue

        xs = np.arange(min_x, max_x + 1, dtype=np.float64) + 0.5
        ys = np.arange(min_y, max_y + 1, dtype=np.float64) + 0.5
        px, py = np.meshgrid(xs, ys)

        inv_a = 1.0 / area
        w0 = ((x1 - px) * (y2 - py) - (x2 - px) * (y1 - py)) * inv_a
        w1 = ((x2 - px) * (y0 - py) - (x0 - px) * (y2 - py)) * inv_a
        w2 = 1.0 - w0 - w1

        inside = (w0 >= -1e-5) & (w1 >= -1e-5) & (w2 >= -1e-5)
        if not np.any(inside):
            continue

        sub_z = zbuf[min_y:max_y + 1, min_x:max_x + 1]
        if ortho_scale is not None:
            depth = w0 * z0 + w1 * z1 + w2 * z2
            mask = inside & (depth < sub_z)
            if not np.any(mask):
                continue
            uu = w0[mask] * u0 + w1[mask] * u1 + w2[mask] * u2
            vv = w0[mask] * v0 + w1[mask] * v1 + w2[mask] * v2
        else:
            iw = w0 * iz0 + w1 * iz1 + w2 * iz2
            depth = 1.0 / np.maximum(iw, 1e-8)
            mask = inside & (depth < sub_z)
            if not np.any(mask):
                continue
            inv_iw = depth[mask]
            uu = (w0[mask] * u0 * iz0 + w1[mask] * u1 * iz1 + w2[mask] * u2 * iz2) * inv_iw
            vv = (w0[mask] * v0 * iz0 + w1[mask] * v1 * iz1 + w2[mask] * v2 * iz2) * inv_iw

        u_lo, u_hi = min(u0, u1, u2), max(u0, u1, u2)
        v_lo, v_hi = min(v0, v1, v2), max(v0, v1, v2)
        tx_i = np.clip(np.floor(np.clip(uu, u_lo, u_hi - 1e-4)).astype(np.int32), 0, tw - 1)
        ty_i = np.clip(np.floor(np.clip(vv, v_lo, v_hi - 1e-4)).astype(np.int32), 0, th - 1)

        rgba = tex[ty_i, tx_i]
        alpha_ok = rgba[:, 3] >= 128
        if not np.any(alpha_ok):
            continue

        my, mx = np.where(mask)
        my = my[alpha_ok]
        mx = mx[alpha_ok]
        sub_z[my, mx] = depth[mask][alpha_ok]
        nbuf[min_y + my, min_x + mx] = normals_cam[i]
        base_rgb = np.full((len(my), 3), 238.0, dtype=np.float32) if clay else rgba[alpha_ok, :3].astype(np.float32)
        rgb_lit = np.clip(base_rgb * shade[i], 0, 255).astype(np.uint8)
        img[min_y + my, min_x + mx] = rgb_lit

    if ssao:
        ao = _compute_ssao(zbuf, nbuf, ppu_cam, clay=clay)
        valid = np.isfinite(zbuf)
        strength = 0.32 if clay else 0.21
        ao_r = 1.0 - ao * strength * 1.04
        ao_g = 1.0 - ao * strength * 1.04
        ao_b = 1.0 - ao * strength * 0.88
        ao_rgb = np.stack([ao_r, ao_g, ao_b], axis=2)
        shaded = np.clip(img.astype(np.float32) * ao_rgb, 0, 255).astype(np.uint8)
        img = np.where(valid[:, :, None], shaded, img)

    return Image.fromarray(img, mode="RGB")


def _fit_panel(im: Image.Image, tw: int, th: int, bg=(255, 255, 255)) -> Image.Image:
    canvas = Image.new("RGB", (tw, th), bg)
    w, h = im.size
    s = min((tw - 12) / max(1, w), (th - 12) / max(1, h))
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((tw - nw) // 2, (th - nh) // 2))
    return canvas


def _label_box(im: Image.Image, text: str) -> Image.Image:
    out = im.copy()
    draw = ImageDraw.Draw(out)
    draw.rectangle([0, 0, out.width, 24], fill=(242, 240, 250))
    draw.text((8, 6), text, fill=(60, 68, 105))
    draw.rectangle([0, 0, out.width - 1, out.height - 1], outline=(215, 212, 232))
    return out


def render_turnaround_compare(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    crops_dir: Optional[Union[str, Path]],
    out_path: Union[str, Path],
    target_y: Optional[float] = None,
    ortho_scale: Optional[float] = None,
) -> Path:
    """Renders Front (0), Left Side (+90), Back (180) ortho views + 3/4 view, optionally paired with reference crops."""
    scene = BedrockScene(geo_path, tex_path)
    cy, oscale, dist = _auto_framing(scene, target_y, ortho_scale)
    pw, ph = 360, 620

    r_front0  = render_view(scene, pw, ph, yaw_deg=0,   pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False)
    r_side    = render_view(scene, pw, ph, yaw_deg=90,  pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False)
    r_back    = render_view(scene, pw, ph, yaw_deg=180, pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False)
    r_front34 = render_view(scene, pw, ph, yaw_deg=-24, pitch_deg=4.0, target=(0, cy, 0), distance=dist, fov_deg=23.0, ground_shadow=True)

    ren_panels = [
        ("MODEL Front (0 deg ortho)", r_front0),
        ("MODEL Left Side (+90 deg ortho)", r_side),
        ("MODEL Back (180 deg ortho)", r_back),
        ("MODEL 3/4 Front (-24 deg)", r_front34),
    ]

    if crops_dir is not None and Path(crops_dir).is_dir():
        cdir = Path(crops_dir)
        sheet = Image.new("RGB", (pw * 4, ph * 2), (255, 255, 255))
        ref_files = [
            ("REF Front (0 deg)", cdir / "ref_front.png"),
            ("REF Left Side (+90 deg)", cdir / "ref_side.png"),
            ("REF Back (180 deg)", cdir / "ref_back.png"),
            ("REF Front (3/4 ref)", cdir / "ref_front.png"),
        ]
        for idx, (lbl, p) in enumerate(ref_files):
            if p.exists():
                with Image.open(p) as rim:
                    panel = _fit_panel(rim.convert("RGB"), pw, ph)
            else:
                panel = Image.new("RGB", (pw, ph), (248, 248, 252))
            sheet.paste(_label_box(panel, lbl), (idx * pw, 0))
        for idx, (lbl, im) in enumerate(ren_panels):
            sheet.paste(_label_box(im, lbl), (idx * pw, ph))
    else:
        sheet = Image.new("RGB", (pw * 4, ph), (255, 255, 255))
        for idx, (lbl, im) in enumerate(ren_panels):
            sheet.paste(_label_box(im, lbl), (idx * pw, 0))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def render_clay_turnaround(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    out_path: Union[str, Path],
    target_y: Optional[float] = None,
    ortho_scale: Optional[float] = None,
) -> Path:
    """Renders untextured SSAO clay turnaround (0, +90, 180, 3/4) to inspect pure 3D volume & depth."""
    scene = BedrockScene(geo_path, tex_path)
    cy, oscale, dist = _auto_framing(scene, target_y, ortho_scale)
    pw, ph = 360, 620
    panels = [
        ("CLAY Front (0 deg)", render_view(scene, pw, ph, yaw_deg=0, pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False, clay=True)),
        ("CLAY Left Side (+90 deg)", render_view(scene, pw, ph, yaw_deg=90, pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False, clay=True)),
        ("CLAY Back (180 deg)", render_view(scene, pw, ph, yaw_deg=180, pitch_deg=0.0, target=(0, cy, 0), distance=120, ortho_scale=oscale, ground_shadow=False, clay=True)),
        ("CLAY 3/4 Front (-24 deg)", render_view(scene, pw, ph, yaw_deg=-24, pitch_deg=5.0, target=(0, cy, 0), distance=dist, fov_deg=23.0, ground_shadow=True, clay=True)),
    ]
    sheet = Image.new("RGB", (pw * 4, ph), (255, 255, 255))
    for idx, (lbl, im) in enumerate(panels):
        sheet.paste(_label_box(im, lbl), (idx * pw, 0))
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def _detect_fg_span(arr: np.ndarray, row_y: int, thresh: float = 12.0) -> Optional[float]:
    d = np.linalg.norm(255.0 - arr[row_y].astype(np.float32), axis=1)
    xs = np.where(d > thresh)[0]
    if len(xs) == 0:
        return None
    return 0.5 * float(xs[0] + xs[-1])


def render_overlay_compare(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    ref_img_path: Union[str, Path],
    out_path: Union[str, Path],
    yaw_deg: float = 0.0,
    y_min: Optional[float] = None,
    y_max: Optional[float] = None,
    half_w_u: float = 6.5,
    title: str = "Region",
    panel_h: int = 460,
) -> Path:
    """
    Renders a pixel-matched [REF | MODEL | 50/50 Overlay] comparison sheet at exact orthographic scale!
    Automatically aligns reference crop scale to the model's vertical height & horizontal center axis.
    """
    scene = BedrockScene(geo_path, tex_path)
    bmin, bmax = scene.compute_bounds()
    model_y0, model_y1 = float(bmin[1]), float(bmax[1])
    model_h = max(1.0, model_y1 - model_y0)

    ymin = model_y0 + model_h * 0.64 if y_min is None else float(y_min)
    ymax = model_y1 + model_h * 0.02 if y_max is None else float(y_max)
    h_u = max(1.0, ymax - ymin)
    cy = 0.5 * (ymin + ymax)

    with Image.open(ref_img_path) as rim:
        ref_full = rim.convert("RGB")
    arr = np.array(ref_full)
    dist_bg = np.linalg.norm(255.0 - arr.astype(np.float32), axis=2)
    ys, xs = np.where(dist_bg > 10.0)
    if len(ys) == 0:
        ref_y_top, ref_y_bot = 0.0, float(ref_full.height)
        cx = 0.5 * ref_full.width
    else:
        ref_y_top, ref_y_bot = float(ys.min()), float(ys.max() + 1)
        # Prefer lower-leg / torso center around 24% height if visible, else median fg center
        yr = int(round(ref_y_bot - 0.24 * (ref_y_bot - ref_y_top)))
        cx = _detect_fg_span(arr, max(0, min(arr.shape[0] - 1, yr))) or 0.5 * float(xs.min() + xs.max() + 1)

    ppu = (ref_y_bot - ref_y_top) / model_h
    pad = max(120, int(round(half_w_u * ppu)))
    ref_pad = Image.new("RGB", (ref_full.width + pad * 2, ref_full.height + pad * 2), (255, 255, 255))
    ref_pad.paste(ref_full, (pad, pad))

    y_top_px = int(round(ref_y_bot - (ymax - model_y0) * ppu)) + pad
    y_bot_px = int(round(ref_y_bot - (ymin - model_y0) * ppu)) + pad
    x_l_px = int(round(cx - half_w_u * ppu)) + pad
    x_r_px = int(round(cx + half_w_u * ppu)) + pad

    pw = max(120, int(round(panel_h * (2.0 * half_w_u / h_u))))
    ref_crop = ref_pad.crop((x_l_px, y_top_px, x_r_px, y_bot_px)).resize((pw, panel_h), Image.Resampling.LANCZOS)
    mod_crop = render_view(scene, pw, panel_h, yaw_deg=yaw_deg, pitch_deg=0.0, target=(0.0, cy, 0.0), distance=110, ortho_scale=h_u, ground_shadow=False)
    blend = Image.blend(ref_crop, mod_crop, 0.5)

    sheet = Image.new("RGB", (pw * 3, panel_h), (255, 255, 255))
    sheet.paste(_label_box(ref_crop, f"REF {title}"), (0, 0))
    sheet.paste(_label_box(mod_crop, f"MODEL {title}"), (pw, 0))
    sheet.paste(_label_box(blend, f"50/50 Overlay {title}"), (pw * 2, 0))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def render_closeups(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    crops_dir: Optional[Union[str, Path]],
    out_path: Union[str, Path],
) -> Path:
    """
    Generic 5-panel close-up inspection sheet automatically scaled to the model's height:
      1. Head Front  2. Head Left Side  3. Back Upper/Hair  4. Torso & Arms  5. Legs & Shoes
    Automatically pairs with matching reference crops if `crops_dir` is provided.
    """
    scene = BedrockScene(geo_path, tex_path)
    bmin, bmax = scene.compute_bounds()
    y0, y1 = float(bmin[1]), float(bmax[1])
    h = max(10.0, y1 - y0)
    pw, ph = 340, 340

    # Automatic proportional zones valid across standard & chibi proportions
    specs = [
        ("Head Front",       0.0,   y0 + 0.835 * h, 0.40 * h),
        ("Head Left Side",   90.0,  y0 + 0.835 * h, 0.40 * h),
        ("Back Upper/Hair",  180.0, y0 + 0.670 * h, 0.68 * h),
        ("Torso & Sleeves",  0.0,   y0 + 0.545 * h, 0.43 * h),
        ("Legs & Shoes",     0.0,   y0 + 0.175 * h, 0.37 * h),
    ]
    mod_panels = [
        (lbl, render_view(scene, pw, ph, yaw_deg=yaw, pitch_deg=0.0, target=(0.0, ty, 0.0), distance=90, ortho_scale=os_u, ground_shadow=False))
        for lbl, yaw, ty, os_u in specs
    ]

    if crops_dir is not None and Path(crops_dir).is_dir():
        cdir = Path(crops_dir)
        # Prefer explicit zoom_*.png if present, else automatically slice ref_front / ref_side / ref_back
        ref_defs = [
            ("REF Head Front",      cdir / "zoom_front_head.png", cdir / "ref_front.png", (0.00, 0.40)),
            ("REF Head Left Side",  cdir / "zoom_side_head.png",  cdir / "ref_side.png",  (0.00, 0.42)),
            ("REF Back Upper/Hair", cdir / "zoom_back_hair.png",  cdir / "ref_back.png",  (0.00, 0.68)),
            ("REF Torso & Sleeves", cdir / "zoom_front_body.png", cdir / "ref_front.png", (0.28, 0.70)),
            ("REF Legs & Shoes",    cdir / "zoom_front_legs.png", cdir / "ref_front.png", (0.64, 1.00)),
        ]
        sheet = Image.new("RGB", (pw * 5, ph * 2), (255, 255, 255))
        for idx, (lbl, zoom_p, full_p, (f0, f1)) in enumerate(ref_defs):
            if zoom_p.exists():
                with Image.open(zoom_p) as rim:
                    im = rim.convert("RGB")
                panel = _fit_panel(im, pw, ph)
            elif full_p.exists():
                with Image.open(full_p) as rim:
                    im = rim.convert("RGB")
                im = im.crop((0, int(im.height * f0), im.width, int(im.height * f1)))
                panel = _fit_panel(im, pw, ph)
            else:
                panel = Image.new("RGB", (pw, ph), (248, 248, 252))
            sheet.paste(_label_box(panel, lbl), (idx * pw, 0))
        for idx, (lbl, im) in enumerate(mod_panels):
            sheet.paste(_label_box(im, f"MODEL {lbl}"), (idx * pw, ph))
    else:
        sheet = Image.new("RGB", (pw * 5, ph), (255, 255, 255))
        for idx, (lbl, im) in enumerate(mod_panels):
            sheet.paste(_label_box(im, f"MODEL {lbl}"), (idx * pw, 0))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def render_poses(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    main_anim_path: Union[str, Path],
    extra_anim_path: Optional[Union[str, Path]],
    out_path: Union[str, Path],
    target_y: Optional[float] = None,
) -> Path:
    """Renders 6 animation key-poses (idle, walk, run, sneaking, jump/extra0, sit/extra1) in 3x2 grid."""
    scene = BedrockScene(geo_path, tex_path)
    cy, _, dist = _auto_framing(scene, target_y)
    with open(main_anim_path, "r", encoding="utf-8") as f:
        main_anim = json.load(f)
    extra_anim = None
    if extra_anim_path is not None and Path(extra_anim_path).exists():
        with open(extra_anim_path, "r", encoding="utf-8") as f:
            extra_anim = json.load(f)

    pw, ph = 320, 460
    specs = [
        ("idle (t=0.5s)", main_anim, "idle", 0.5, -22, 4),
        ("walk (t=0.25s)", main_anim, "walk", 0.25, -35, 5),
        ("run (t=0.20s)", main_anim, "run", 0.20, -40, 6),
        ("sneaking", main_anim, "sneaking", 0.3, -35, 6),
    ]
    if extra_anim and "extra0" in extra_anim.get("animations", {}):
        specs.append(("extra0", extra_anim, "extra0", 0.6, -20, 4))
    else:
        specs.append(("jump (t=0.25s)", main_anim, "jump", 0.25, -28, 6))

    if extra_anim and "extra1" in extra_anim.get("animations", {}):
        specs.append(("extra1", extra_anim, "extra1", 0.5, -30, 10))
    else:
        specs.append(("sit (t=0.3s)", main_anim, "sit", 0.3, -32, 10))

    sheet = Image.new("RGB", (pw * 3, ph * 2), (255, 255, 255))
    for idx, (lbl, aj, aname, t, yaw, pitch) in enumerate(specs):
        pose = evaluate_animation(aj, aname, t)
        tgt_y = cy - 4.0 if aname in ("sit", "extra1") else cy
        im = render_view(scene, pw, ph, yaw_deg=yaw, pitch_deg=pitch, target=(0, tgt_y, 0), distance=dist, fov_deg=24, anim_pose=pose)
        r, c = divmod(idx, 3)
        sheet.paste(_label_box(im, lbl), (c * pw, r * ph))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def render_skeleton_pivots(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    out_path: Union[str, Path],
    target_y: Optional[float] = None,
) -> Path:
    """Renders front and side views overlaid with bone pivots & parent-child links."""
    scene = BedrockScene(geo_path, tex_path)
    cy, _, dist = _auto_framing(scene, target_y)
    xforms = scene.compute_bone_transforms()
    pw, ph = 420, 640
    views = [
        ("Skeleton Pivots - Front (0 deg)", 0.0, 2.0),
        ("Skeleton Pivots - Left Side (+90 deg)", 90.0, 2.0),
    ]
    sheet = Image.new("RGB", (pw * 2, ph), (255, 255, 255))

    for idx, (lbl, yaw_deg, pitch_deg) in enumerate(views):
        base = render_view(scene, pw, ph, yaw_deg=yaw_deg, pitch_deg=pitch_deg, target=(0, cy, 0), distance=dist, fov_deg=25)
        arr = np.clip(np.array(base).astype(np.float32) * 0.65 + 255.0 * 0.35, 0, 255).astype(np.uint8)
        im = Image.fromarray(arr, mode="RGB")
        draw = ImageDraw.Draw(im)

        tgt = np.array([0.0, cy, 0.0])
        yaw = math.radians(yaw_deg)
        pitch = math.radians(pitch_deg)
        cam_pos = tgt + np.array([-math.sin(yaw) * math.cos(pitch), math.sin(pitch), -math.cos(yaw) * math.cos(pitch)]) * dist
        forward = (tgt - cam_pos) / np.linalg.norm(tgt - cam_pos)
        cam_right = np.cross(forward, np.array([0.0, 1.0, 0.0]))
        cam_right /= np.linalg.norm(cam_right)
        cam_up = np.cross(cam_right, forward)
        f = (ph * 0.5) / math.tan(math.radians(25.0 * 0.5))

        def proj(pt3):
            rel = pt3 - cam_pos
            cz = float(np.dot(rel, forward))
            sx = pw * 0.5 + float(np.dot(rel, cam_right)) * f / max(0.1, cz)
            sy = ph * 0.5 - float(np.dot(rel, cam_up)) * f / max(0.1, cz)
            return sx, sy

        for b in scene.bones_list:
            bname = b["name"]
            pname = b.get("parent")
            if pname and pname in xforms:
                x0, y0 = proj(xforms[pname][1])
                x1, y1 = proj(xforms[bname][1])
                is_loc = "Locator" in bname
                col = (50, 180, 120) if is_loc else (220, 60, 110)
                draw.line([x0, y0, x1, y1], fill=col, width=2)

        key_labels = {
            "Head", "Body", "Waist", "RightArm", "LeftArm",
            "RightHandLocator", "LeftHandLocator", "RightLeg", "LeftLeg",
            "Skirt", "HairBack", "ViewLocator"
        }
        for b in scene.bones_list:
            bname = b["name"]
            x1, y1 = proj(xforms[bname][1])
            is_loc = "Locator" in bname
            col = (20, 150, 90) if is_loc else (210, 30, 80)
            r = 4 if bname in key_labels else 2
            draw.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=col, outline=(255, 255, 255))
            if bname in key_labels:
                draw.text((x1 + 5, y1 - 6), bname, fill=(30, 30, 60))

        sheet.paste(_label_box(im, lbl), (idx * pw, 0))

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="YSM 3D Software Renderer CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_turn = sub.add_parser("turnaround", help="Render ortho 3-view + 3/4 comparison sheet")
    p_turn.add_argument("geo", type=Path)
    p_turn.add_argument("tex", type=Path)
    p_turn.add_argument("-o", "--out", type=Path, required=True)
    p_turn.add_argument("--crops", type=Path, default=None)

    p_clay = sub.add_parser("clay", help="Render untextured SSAO clay turnaround")
    p_clay.add_argument("geo", type=Path)
    p_clay.add_argument("tex", type=Path)
    p_clay.add_argument("-o", "--out", type=Path, required=True)

    p_close = sub.add_parser("closeups", help="Render 5-panel close-ups")
    p_close.add_argument("geo", type=Path)
    p_close.add_argument("tex", type=Path)
    p_close.add_argument("-o", "--out", type=Path, required=True)
    p_close.add_argument("--crops", type=Path, default=None)

    p_ov = sub.add_parser("overlay", help="Render 50/50 overlay alignment check against reference")
    p_ov.add_argument("geo", type=Path)
    p_ov.add_argument("tex", type=Path)
    p_ov.add_argument("ref", type=Path)
    p_ov.add_argument("-o", "--out", type=Path, required=True)
    p_ov.add_argument("--yaw", type=float, default=0.0)
    p_ov.add_argument("--ymin", type=float, default=None)
    p_ov.add_argument("--ymax", type=float, default=None)
    p_ov.add_argument("--half-w", type=float, default=6.5)
    p_ov.add_argument("--title", type=str, default="Region")

    p_pose = sub.add_parser("poses", help="Render animation pose grid")
    p_pose.add_argument("geo", type=Path)
    p_pose.add_argument("tex", type=Path)
    p_pose.add_argument("main_anim", type=Path)
    p_pose.add_argument("-o", "--out", type=Path, required=True)
    p_pose.add_argument("--extra", type=Path, default=None)

    p_skel = sub.add_parser("skeleton", help="Render skeleton pivots & locators")
    p_skel.add_argument("geo", type=Path)
    p_skel.add_argument("tex", type=Path)
    p_skel.add_argument("-o", "--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "turnaround":
        p = render_turnaround_compare(args.geo, args.tex, args.crops, args.out)
    elif args.cmd == "clay":
        p = render_clay_turnaround(args.geo, args.tex, args.out)
    elif args.cmd == "closeups":
        p = render_closeups(args.geo, args.tex, args.crops, args.out)
    elif args.cmd == "overlay":
        p = render_overlay_compare(args.geo, args.tex, args.ref, args.out, yaw_deg=args.yaw, y_min=args.ymin, y_max=args.ymax, half_w_u=args.half_w, title=args.title)
    elif args.cmd == "poses":
        p = render_poses(args.geo, args.tex, args.main_anim, args.extra, args.out)
    elif args.cmd == "skeleton":
        p = render_skeleton_pivots(args.geo, args.tex, args.out)
    print(f"Rendered: {p}")


if __name__ == "__main__":
    main()
