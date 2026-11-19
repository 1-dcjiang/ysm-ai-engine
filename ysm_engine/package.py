"""
Validate and package a YSM model folder into <pack_name>.zip and <pack_name>.bbmodel.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ysm_engine.export_bbmodel import export_bbmodel
    from ysm_engine.validate import validate_pack
else:
    from .export_bbmodel import export_bbmodel
    from .validate import validate_pack


def package_all(
    pack_dir: Path,
    out_dir: Optional[Path] = None,
    export_bb: bool = True,
    quiet: bool = False,
) -> Tuple[Path, Optional[Path]]:
    """Validates `pack_dir`, then packages `<name>.zip` and `<name>.bbmodel`."""
    pack_dir = Path(pack_dir).resolve()
    errs = validate_pack(pack_dir, quiet=quiet)
    if errs:
        raise SystemExit(f"Packaging aborted: {len(errs)} validation error(s).")

    dest_dir = Path(out_dir).resolve() if out_dir else pack_dir.parent
    dest_dir.mkdir(parents=True, exist_ok=True)

    zip_path = dest_dir / f"{pack_dir.name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(pack_dir.rglob("*")):
            if file_path.is_file():
                arcname = f"{pack_dir.name}/" + file_path.relative_to(pack_dir).as_posix()
                zf.write(file_path, arcname)
    if not quiet:
        print(f"Packaged YSM zip: {zip_path} ({zip_path.stat().st_size:,} bytes)")

    bb_path: Optional[Path] = None
    if export_bb:
        ysm = json.loads((pack_dir / "ysm.json").read_text(encoding="utf-8"))
        player = ysm.get("files", {}).get("player", {})
        main_rel = player.get("model", {}).get("main", "models/main.json")
        tex_list = player.get("texture", ["textures/default.png"])
        first_tex = tex_list[0]["uv"] if isinstance(tex_list[0], dict) else tex_list[0]
        anim_cfg = player.get("animation", {})
        anims = [pack_dir / rel for rel in anim_cfg.values() if (pack_dir / rel).exists()]

        bb_path = dest_dir / f"{pack_dir.name}.bbmodel"
        export_bbmodel(
            geo_path=pack_dir / main_rel,
            tex_path=pack_dir / first_tex,
            out_path=bb_path,
            anim_paths=anims,
            model_name=pack_dir.name,
        )
        if not quiet:
            print(f"Exported Blockbench project: {bb_path} ({bb_path.stat().st_size:,} bytes)")

    return zip_path, bb_path


def main(argv: List[str] | None = None):
    parser = argparse.ArgumentParser(description="Validate and package a YSM model directory.")
    parser.add_argument("pack_dir", type=Path, help="Path to unpacked YSM model folder")
    parser.add_argument("-o", "--out-dir", type=Path, default=None, help="Output directory (defaults to pack_dir parent)")
    parser.add_argument("--no-bbmodel", action="store_true", help="Skip exporting .bbmodel")
    args = parser.parse_args(argv)
    package_all(args.pack_dir, out_dir=args.out_dir, export_bb=not args.no_bbmodel)


if __name__ == "__main__":
    main()
