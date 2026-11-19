"""
Strict YSM 2.5 / 2.6 Model Pack Validator.

Checks:
  1. UTF-8 (no BOM) valid JSON across all pack files.
  2. ysm.json spec=2, metadata, exact-case file references exist.
  3. YSM 2.6.0 UV Standard: texture_width == PNG width, integer non-zero uv & uv_size, in-bounds.
  4. Required YSM bones & locators present and properly nested.
  5. arm.json has root LeftArm & RightArm with zero root rotation and valid UVs.
  6. All animation bone references exist in main.json; all 29 core YSM animations present.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Set
from PIL import Image

REQUIRED_BONES = [
    "All",
    "Waist",
    "Body",
    "AllHead",
    "Head",
    "ViewLocator",
    "RightArm",
    "RightHand",
    "RightHandLocator",
    "LeftArm",
    "LeftHand",
    "LeftHandLocator",
    "RightLeg",
    "LeftLeg",
    "ElytraLocator",
    "BackpackLocator",
    "LeftShoulderLocator",
    "RightShoulderLocator",
]

REQUIRED_MAIN_ANIMS = [
    "empty",
    "gui",
    "idle",
    "walk",
    "run",
    "sneaking",
    "sneak",
    "jump",
    "swim",
    "swim_stand",
    "fly",
    "elytra_fly",
    "sit",
    "boat",
    "ride",
    "ride_pig",
    "sleep",
    "climb",
    "climbing",
    "ladder_up",
    "ladder_stillness",
    "ladder_down",
    "swing_hand",
    "swing_offhand",
    "use_mainhand",
    "use_offhand",
    "attacked",
    "death",
    "parallel0",
]


def _check_exact_case_path(root: Path, rel: str) -> bool:
    cur = root
    for part in Path(rel).parts:
        if not cur.is_dir():
            return False
        names = {p.name for p in cur.iterdir()}
        if part not in names:
            return False
        cur = cur / part
    return cur.exists()


def _load_json_no_bom(path: Path, errors: List[str]):
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append(f"UTF-8 BOM detected (disallowed by YSM): {path}")
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        errors.append(f"Invalid JSON in {path}: {e}")
        return None


def _check_geo_uvs(geo: dict, tex_w: int, tex_h: int, label: str, errors: List[str]) -> Set[str]:
    bone_names: Set[str] = set()
    if geo.get("format_version") != "1.12.0":
        errors.append(f"{label}: format_version should be '1.12.0', got {geo.get('format_version')!r}")
    geos = geo.get("minecraft:geometry")
    if not isinstance(geos, list) or not geos:
        errors.append(f"{label}: missing minecraft:geometry array")
        return bone_names
    g0 = geos[0]
    desc = g0.get("description", {})
    if desc.get("texture_width") != tex_w or desc.get("texture_height") != tex_h:
        errors.append(
            f"{label}: texture_width/height ({desc.get('texture_width')}x{desc.get('texture_height')}) "
            f"must match PNG ({tex_w}x{tex_h}) for YSM 2.6.0 UV unit=1"
        )
    bones = g0.get("bones", [])
    for b in bones:
        bname = b.get("name")
        if bname in bone_names:
            errors.append(f"{label}: duplicate bone '{bname}'")
        bone_names.add(bname)
        for ci, c in enumerate(b.get("cubes", [])):
            uv = c.get("uv")
            if not isinstance(uv, dict):
                errors.append(f"{label}: bone '{bname}' cube {ci} does not use per-face UV dict")
                continue
            for fname, fuv in uv.items():
                u, v = fuv.get("uv", [None, None])
                uw, vh = fuv.get("uv_size", [None, None])
                for val, tag in ((u, "u"), (v, "v"), (uw, "uv_size[0]"), (vh, "uv_size[1]")):
                    if not isinstance(val, int) or isinstance(val, bool):
                        errors.append(f"{label}: {bname}[{ci}].{fname}.{tag}={val!r} must be exact int")
                if isinstance(uw, int) and isinstance(vh, int):
                    if uw == 0 or vh == 0:
                        errors.append(f"{label}: {bname}[{ci}].{fname} has zero uv_size ({uw}, {vh})")
                    if isinstance(u, int) and isinstance(v, int):
                        x0, x1 = min(u, u + uw), max(u, u + uw)
                        y0, y1 = min(v, v + vh), max(v, v + vh)
                        if x0 < 0 or y0 < 0 or x1 > tex_w or y1 > tex_h:
                            errors.append(
                                f"{label}: {bname}[{ci}].{fname} UV [{x0},{y0}]->[{x1},{y1}] out of bounds ({tex_w}x{tex_h})"
                            )
    return bone_names


def validate_pack(pack_dir: Path, quiet: bool = False) -> List[str]:
    """Validates an unpacked YSM 2.5/2.6 model directory and returns a list of error strings."""
    pack_dir = Path(pack_dir)
    errors: List[str] = []
    warnings: List[str] = []

    ysm_path = pack_dir / "ysm.json"
    if not ysm_path.exists():
        return [f"Missing ysm.json in {pack_dir}"]

    ysm = _load_json_no_bom(ysm_path, errors)
    if not isinstance(ysm, dict):
        return errors

    if ysm.get("spec") != 2:
        errors.append(f"ysm.json: spec must be 2, got {ysm.get('spec')!r}")
    if not ysm.get("metadata", {}).get("name"):
        errors.append("ysm.json: metadata.name is required")

    player = ysm.get("files", {}).get("player", {})
    model_cfg = player.get("model", {})
    main_rel = model_cfg.get("main")
    arm_rel = model_cfg.get("arm")
    tex_list = player.get("texture", [])
    anim_cfg = player.get("animation", {})

    for key, rel in [("model.main", main_rel), ("model.arm", arm_rel)]:
        if not rel or not _check_exact_case_path(pack_dir, rel):
            errors.append(f"ysm.json: missing or wrong-case path for {key}: {rel!r}")

    if not tex_list:
        errors.append("ysm.json: files.player.texture must be non-empty")
        tex_w = tex_h = 512
    else:
        first_tex = tex_list[0]["uv"] if isinstance(tex_list[0], dict) else tex_list[0]
        if not _check_exact_case_path(pack_dir, first_tex):
            errors.append(f"ysm.json: missing or wrong-case texture: {first_tex!r}")
            tex_w = tex_h = 512
        else:
            with Image.open(pack_dir / first_tex) as im:
                tex_w, tex_h = im.size
                if im.mode != "RGBA":
                    warnings.append(f"Texture {first_tex} mode is {im.mode}, RGBA recommended")

    main_bones: Set[str] = set()
    main_bones_map = {}
    if main_rel and (pack_dir / main_rel).exists():
        main_geo = _load_json_no_bom(pack_dir / main_rel, errors)
        if main_geo:
            main_bones = _check_geo_uvs(main_geo, tex_w, tex_h, main_rel, errors)
            main_bones_map = {b["name"]: b for b in main_geo["minecraft:geometry"][0]["bones"]}

            for req in REQUIRED_BONES:
                if req not in main_bones:
                    errors.append(f"main.json: missing required YSM bone/locator '{req}'")

            def has_ancestor(bname: str, anc: str) -> bool:
                cur = bname
                seen = set()
                while cur and cur not in seen:
                    seen.add(cur)
                    p = main_bones_map.get(cur, {}).get("parent")
                    if p == anc:
                        return True
                    cur = p
                return False

            parent_checks = [
                ("RightHandLocator", "RightHand"),
                ("RightHand", "RightArm"),
                ("LeftHandLocator", "LeftHand"),
                ("LeftHand", "LeftArm"),
                ("Head", "AllHead"),
                ("ViewLocator", "Head"),
                ("AllHead", "Body"),
            ]
            for child, anc in parent_checks:
                if child in main_bones_map and anc in main_bones_map:
                    if not has_ancestor(child, anc):
                        errors.append(f"main.json: '{child}' must be nested under '{anc}'")

    if arm_rel and (pack_dir / arm_rel).exists():
        arm_geo = _load_json_no_bom(pack_dir / arm_rel, errors)
        if arm_geo:
            arm_bones = _check_geo_uvs(arm_geo, tex_w, tex_h, arm_rel, errors)
            arm_map = {b["name"]: b for b in arm_geo["minecraft:geometry"][0]["bones"]}
            for side in ("LeftArm", "RightArm"):
                if side not in arm_bones:
                    errors.append(f"arm.json: missing root bone '{side}'")
                else:
                    if "parent" in arm_map[side]:
                        errors.append(f"arm.json: '{side}' must be a root bone (no parent)")
                    rot = arm_map[side].get("rotation", [0, 0, 0])
                    if any(abs(float(r)) > 1e-4 for r in rot):
                        errors.append(f"arm.json: '{side}' rotation must be [0,0,0], got {rot}")

    for akey, arel in anim_cfg.items():
        if not _check_exact_case_path(pack_dir, arel):
            errors.append(f"ysm.json: missing animation.{akey}: {arel!r}")
            continue
        adata = _load_json_no_bom(pack_dir / arel, errors)
        if not isinstance(adata, dict):
            continue
        if adata.get("format_version") != "1.8.0":
            warnings.append(f"{arel}: format_version is {adata.get('format_version')!r}, '1.8.0' recommended")
        anims = adata.get("animations", {})
        if akey == "main":
            for req_a in REQUIRED_MAIN_ANIMS:
                if req_a not in anims:
                    errors.append(f"{arel}: missing required YSM main animation '{req_a}'")
        for aname, acfg in anims.items():
            for bname in acfg.get("bones", {}).keys():
                if main_bones and bname not in main_bones:
                    errors.append(f"{arel} -> animation '{aname}' references unknown bone '{bname}'")

    lang_dir = pack_dir / ysm.get("files", {}).get("language_path", "lang")
    if lang_dir.is_dir():
        for lf in lang_dir.glob("*.json"):
            _load_json_no_bom(lf, errors)

    if not quiet:
        print(f"=== YSM Validation Report for {pack_dir} ===")
        print(f"  Bones in main.json: {len(main_bones)} | Texture: {tex_w}x{tex_h}")
        if warnings:
            print(f"  Warnings ({len(warnings)}):")
            for w in warnings:
                print(f"    [WARN] {w}")
        if errors:
            print(f"  ERRORS ({len(errors)}):")
            for e in errors:
                print(f"    [FAIL] {e}")
        else:
            print("  ALL CHECKS PASSED (0 errors)!")
    return errors


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Validate a YSM 2.5/2.6 model pack directory.")
    parser.add_argument("pack_dir", type=Path, help="Path to unpacked YSM model folder containing ysm.json")
    args = parser.parse_args(argv)
    errs = validate_pack(args.pack_dir)
    sys.exit(0 if not errs else 1)


if __name__ == "__main__":
    main()
