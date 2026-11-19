"""
Export Bedrock 1.12.0 main.json + PNG texture + animations/*.animation.json to Blockbench .bbmodel.
"""
from __future__ import annotations

import argparse
import base64
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Union


def _uid() -> str:
    return str(uuid.uuid4())


def _convert_anim_keyframes(anim_name: str, anim_data: dict, bone_uuids: Dict[str, str]) -> dict:
    animators = {}
    for bname, channels in anim_data.get("bones", {}).items():
        if bname not in bone_uuids or not isinstance(channels, dict):
            continue
        kfs = []
        for ch_name in ("rotation", "position", "scale"):
            raw = channels.get(ch_name)
            if raw is None:
                continue
            entries = []
            if isinstance(raw, list):
                entries.append((0.0, raw, "linear"))
            elif isinstance(raw, dict):
                if "vector" in raw:
                    entries.append((0.0, raw["vector"], raw.get("lerp_mode", "linear")))
                else:
                    for tk, tv in sorted(raw.items(), key=lambda kv: float(kv[0])):
                        t = float(tk)
                        if isinstance(tv, dict):
                            vec = tv.get("post", tv.get("vector", [0, 0, 0]))
                            interp = tv.get("lerp_mode", "linear")
                        else:
                            vec = tv
                            interp = "linear"
                        entries.append((t, vec, interp))
            for t, vec, interp in entries:
                if not isinstance(vec, list):
                    vec = [vec, vec, vec]
                kfs.append({
                    "channel": ch_name,
                    "data_points": [{
                        "x": str(vec[0]),
                        "y": str(vec[1]),
                        "z": str(vec[2]),
                    }],
                    "uuid": _uid(),
                    "time": t,
                    "color": -1,
                    "interpolation": "catmullrom" if interp == "catmullrom" else "linear",
                })
        animators[bone_uuids[bname]] = {
            "name": bname,
            "type": "bone",
            "keyframes": kfs,
        }

    loop_raw = anim_data.get("loop", False)
    if loop_raw is True:
        loop_str = "loop"
    elif loop_raw == "hold_on_last_frame":
        loop_str = "hold"
    else:
        loop_str = "once"

    return {
        "uuid": _uid(),
        "name": anim_name,
        "loop": loop_str,
        "override": False,
        "length": float(anim_data.get("animation_length", 1.0) or 1.0),
        "snapping": 24,
        "selected": False,
        "anim_time_update": "",
        "blend_weight": "",
        "start_delay": "",
        "loop_delay": "",
        "animators": animators,
    }


def export_bbmodel(
    geo_path: Union[str, Path],
    tex_path: Union[str, Path],
    out_path: Union[str, Path],
    anim_paths: Optional[List[Union[str, Path]]] = None,
    model_name: str = "ysm_model",
) -> Path:
    """Exports a Bedrock 1.12.0 model, texture, and optional animations to a Blockbench .bbmodel file."""
    with open(geo_path, "r", encoding="utf-8") as f:
        geo = json.load(f)
    g0 = geo["minecraft:geometry"][0]
    desc = g0["description"]
    tw = int(desc["texture_width"])
    th = int(desc["texture_height"])

    tex_bytes = Path(tex_path).read_bytes()
    tex_b64 = "data:image/png;base64," + base64.b64encode(tex_bytes).decode("ascii")
    tex_uuid = _uid()

    elements: List[dict] = []
    group_nodes: Dict[str, dict] = {}
    bone_uuids: Dict[str, str] = {}
    root_outliner: List[dict] = []

    for b in g0["bones"]:
        bname = b["name"]
        buuid = _uid()
        bone_uuids[bname] = buuid
        bp = b.get("pivot", [0.0, 0.0, 0.0])
        brot = b.get("rotation", [0.0, 0.0, 0.0])
        gnode = {
            "name": bname,
            "origin": [-float(bp[0]), float(bp[1]), float(bp[2])],
            "rotation": [-float(brot[0]), -float(brot[1]), float(brot[2])],
            "color": 0,
            "uuid": buuid,
            "export": True,
            "mirror_uv": False,
            "isOpen": False,
            "locked": False,
            "visibility": not b.get("neverRender", False),
            "autouv": 0,
            "children": [],
        }
        group_nodes[bname] = gnode

        for ci, cube in enumerate(b.get("cubes", [])):
            cuuid = _uid()
            ox, oy, oz = [float(v) for v in cube["origin"]]
            sx, sy, sz = [float(v) for v in cube["size"]]
            cp = cube.get("pivot", [ox + sx * 0.5, oy + sy * 0.5, oz + sz * 0.5])
            crot = cube.get("rotation", [0.0, 0.0, 0.0])
            inf = float(cube.get("inflate", 0.0))

            faces_bb = {}
            uv_obj = cube.get("uv", {})
            if isinstance(uv_obj, dict):
                for fname in ("north", "east", "south", "west", "up", "down"):
                    if fname in uv_obj:
                        u, v = uv_obj[fname]["uv"]
                        uw, vh = uv_obj[fname]["uv_size"]
                        faces_bb[fname] = {
                            "uv": [float(u), float(v), float(u + uw), float(v + vh)],
                            "texture": 0,
                        }
                    else:
                        faces_bb[fname] = {"uv": [0, 0, 1, 1], "texture": None}

            elem = {
                "name": f"{bname}_{ci}",
                "box_uv": False,
                "rescale": False,
                "locked": False,
                "from": [round(-(ox + sx), 4), round(oy, 4), round(oz, 4)],
                "to": [round(-ox, 4), round(oy + sy, 4), round(oz + sz, 4)],
                "inflate": inf,
                "autouv": 0,
                "color": 0,
                "origin": [-float(cp[0]), float(cp[1]), float(cp[2])],
                "rotation": [-float(crot[0]), -float(crot[1]), float(crot[2])],
                "faces": faces_bb,
                "type": "cube",
                "uuid": cuuid,
            }
            elements.append(elem)
            gnode["children"].append(cuuid)

    for b in g0["bones"]:
        bname = b["name"]
        pname = b.get("parent")
        if pname and pname in group_nodes:
            group_nodes[pname]["children"].append(group_nodes[bname])
        else:
            root_outliner.append(group_nodes[bname])

    bb_animations = []
    for ap in anim_paths or []:
        ap = Path(ap)
        if not ap.exists():
            continue
        with open(ap, "r", encoding="utf-8") as f:
            adata = json.load(f)
        for aname, acfg in adata.get("animations", {}).items():
            bb_animations.append(_convert_anim_keyframes(aname, acfg, bone_uuids))

    bbmodel = {
        "meta": {
            "format_version": "4.10",
            "model_format": "bedrock",
            "box_uv": False,
        },
        "name": model_name,
        "model_identifier": desc.get("identifier", "geometry.model"),
        "visible_box": [
            desc.get("visible_bounds_width", 3.0),
            desc.get("visible_bounds_height", 3.5),
            desc.get("visible_bounds_offset", [0, 1.25, 0])[1],
        ],
        "variable_placeholders": "",
        "variable_placeholder_buttons": [],
        "timeline_setups": [],
        "unhandled_root_fields": {},
        "resolution": {"width": tw, "height": th},
        "elements": elements,
        "outliner": root_outliner,
        "textures": [
            {
                "path": str(Path(tex_path).name),
                "name": Path(tex_path).name,
                "folder": "textures",
                "namespace": "",
                "id": "0",
                "particle": False,
                "render_mode": "default",
                "render_sides": "auto",
                "frame_time": 1,
                "frame_order_type": "loop",
                "frame_order": "",
                "frame_interpolate": False,
                "visible": True,
                "mode": "bitmap",
                "saved": True,
                "uuid": tex_uuid,
                "source": tex_b64,
            }
        ],
        "animations": bb_animations,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bbmodel, f, indent=2, ensure_ascii=False)
    return out


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Export Bedrock 1.12.0 model to Blockbench .bbmodel.")
    parser.add_argument("geo", type=Path, help="Path to main.json geometry file")
    parser.add_argument("tex", type=Path, help="Path to texture PNG")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Output .bbmodel path")
    parser.add_argument("-a", "--anims", type=Path, nargs="*", default=[], help="Animation JSON paths")
    parser.add_argument("-n", "--name", type=str, default="ysm_model", help="Blockbench model name")
    args = parser.parse_args(argv)
    out = export_bbmodel(args.geo, args.tex, args.out, anim_paths=args.anims, model_name=args.name)
    print(f"Exported Blockbench project: {out}")


if __name__ == "__main__":
    main()
