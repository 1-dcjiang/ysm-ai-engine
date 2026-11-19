"""
Universal Reference Image Analyzer for YSM Modeling.
Automatically splits 1-, 2-, or 3-view turnaround sheets on white/transparent backgrounds,
aligns unified feet-to-crown scale, generates a Bedrock-unit ruler overlay, samples palette colors,
and exports quantitative silhouette width/depth profiles to `ref_analysis.json`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from PIL import Image, ImageDraw


def rgb_to_hex(rgb) -> str:
    return f"#{int(rgb[0]):02X}{int(rgb[1]):02X}{int(rgb[2]):02X}"


def _foreground_mask(rgba: np.ndarray, bg_thresh: float = 12.0) -> np.ndarray:
    alpha = rgba[:, :, 3] > 25
    rgb = rgba[:, :, :3].astype(np.float32)
    dist = np.linalg.norm(255.0 - rgb, axis=2)
    return alpha & (dist > bg_thresh)


def _find_bbox(mask: np.ndarray) -> Tuple[int, int, int, int]:
    ys = np.where(mask.any(axis=1))[0]
    xs = np.where(mask.any(axis=0))[0]
    if len(ys) == 0 or len(xs) == 0:
        return 0, 0, mask.shape[1], mask.shape[0]
    return int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1


def split_views(rgba: np.ndarray, expected_views: Optional[int] = None, bg_thresh: float = 12.0) -> List[Tuple[int, int, int, int]]:
    """Splits separated horizontal views automatically from foreground masks."""
    mask = _foreground_mask(rgba, bg_thresh=bg_thresh)
    col_fg = mask.any(axis=0)
    xs = np.where(col_fg)[0]
    if len(xs) == 0:
        return [(0, 0, rgba.shape[1], rgba.shape[0])]

    min_gap = max(8, rgba.shape[1] // 80)
    gaps = np.where(np.diff(xs) > min_gap)[0]
    groups = [g for g in np.split(xs, gaps + 1) if len(g) > max(16, rgba.shape[1] // 40)]

    if expected_views and len(groups) != expected_views:
        # Fallback: split evenly if views touch or extra icons appear
        w = rgba.shape[1]
        step = w // expected_views
        boxes = []
        for i in range(expected_views):
            x0, x1 = i * step, (w if i == expected_views - 1 else (i + 1) * step)
            bx0, by0, bx1, by1 = _find_bbox(mask[:, x0:x1])
            boxes.append((x0 + bx0, by0, x0 + bx1, by1))
        return boxes

    boxes = []
    for g in groups:
        x0, x1 = int(g[0]), int(g[-1]) + 1
        bx0, by0, bx1, by1 = _find_bbox(mask[:, x0:x1])
        boxes.append((x0 + bx0, by0, x0 + bx1, by1))
    return boxes


def analyze_reference(
    ref_path: Path,
    out_dir: Path,
    target_height_u: float = 34.0,
    expected_views: Optional[int] = None,
) -> Dict:
    """Analyzes a reference image and saves aligned view crops, ruler, and ref_analysis.json."""
    out_dir = Path(out_dir)
    crops_dir = out_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(ref_path) as raw_im:
        im_rgba = raw_im.convert("RGBA")
    # Composite onto clean white background for consistent RGB analysis
    white_bg = Image.new("RGBA", im_rgba.size, (255, 255, 255, 255))
    comp_rgba = Image.alpha_composite(white_bg, im_rgba)
    img_rgb = comp_rgba.convert("RGB")
    rgba = np.array(comp_rgba)
    arr = np.array(img_rgb)
    w, h = img_rgb.size

    boxes = split_views(rgba, expected_views=expected_views)
    view_names = ["ref_front", "ref_side", "ref_back"] if len(boxes) == 3 else (
        ["ref_front", "ref_back"] if len(boxes) == 2 else [f"ref_view{i}" for i in range(len(boxes))]
    )
    if len(boxes) == 1:
        view_names = ["ref_front"]

    global_y0 = min(b[1] for b in boxes)
    global_y1 = max(b[3] for b in boxes)
    global_h = max(1, global_y1 - global_y0)
    ppu = global_h / float(target_height_u)

    pad = 12
    views_meta = {}
    for name, (x0, y0, x1, y1) in zip(view_names, boxes):
        cx0, cx1 = max(0, x0 - pad), min(w, x1 + pad)
        cy0, cy1 = max(0, global_y0 - pad), min(h, global_y1 + pad)
        crop = img_rgb.crop((cx0, cy0, cx1, cy1))
        crop.save(crops_dir / f"{name}.png")
        views_meta[name] = {
            "bbox": [x0, y0, x1, y1],
            "width_px": x1 - x0,
            "height_px": y1 - y0,
            "width_u": round((x1 - x0) / ppu, 2),
        }

    # Vertical silhouette profile in Bedrock units
    profile = {}
    mask_full = _foreground_mask(rgba)
    for pct in range(2, 100, 4):
        nh = pct / 100.0
        row = max(0, min(h - 1, int(round(global_y1 - nh * global_h))))
        row_info = {"y_u": round(nh * target_height_u, 2)}
        for name, (x0, _, x1, _) in zip(view_names, boxes):
            xs = np.where(mask_full[row, x0:x1])[0]
            span_u = round((int(xs[-1] - xs[0]) + 1) / ppu, 2) if len(xs) else 0.0
            row_info[f"{name}_span_u"] = span_u
        profile[f"{nh:.2f}"] = row_info

    # Quantized palette extraction from foreground pixels (excluding near-white)
    fg_pixels = arr[mask_full]
    palette = []
    if len(fg_pixels) > 0:
        q_img = Image.fromarray(fg_pixels.reshape(1, -1, 3)).quantize(colors=12, method=Image.Quantize.MEDIANCUT)
        pal = q_img.getpalette() or []
        counts = sorted(q_img.getcolors() or [], reverse=True)
        for cnt, idx in counts:
            rgb = pal[idx * 3: idx * 3 + 3]
            if len(rgb) == 3:
                palette.append({"hex": rgb_to_hex(rgb), "rgb": [int(c) for c in rgb], "pixels": int(cnt)})

    # Ruler image overlay
    ruler = img_rgb.copy()
    draw = ImageDraw.Draw(ruler)
    for u in range(0, int(target_height_u) + 2, 2):
        y = int(round(global_y1 - u * ppu))
        if 0 <= y < h:
            col = (255, 80, 120) if u % 4 == 0 else (120, 160, 255)
            draw.line([(0, y), (w, y)], fill=col, width=1)
            draw.text((4, max(0, y - 10)), f"{u}u", fill=(200, 30, 70))
    ruler.save(out_dir / "ref_ruler.png")

    analysis = {
        "image_size": [w, h],
        "target_height_u": target_height_u,
        "global_y": [global_y0, global_y1, global_h],
        "px_per_u": round(ppu, 4),
        "views": views_meta,
        "dominant_palette": palette,
        "profile": profile,
    }
    with open(out_dir / "ref_analysis.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    return analysis


def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="Analyze a character turnaround reference image for YSM modeling.")
    parser.add_argument("image", type=Path, help="Path to reference turnaround image")
    parser.add_argument("-o", "--out", type=Path, default=Path("reference"), help="Output directory for crops & analysis")
    parser.add_argument("--height", type=float, default=34.0, help="Target Bedrock model height in units (default: 34.0)")
    parser.add_argument("--views", type=int, default=None, help="Optional expected number of views (1, 2, or 3)")
    args = parser.parse_args(argv)

    res = analyze_reference(args.image, args.out, target_height_u=args.height, expected_views=args.views)
    print(f"Analyzed {args.image} -> {len(res['views'])} view(s), px_per_u={res['px_per_u']}")
    for vname, vinfo in res["views"].items():
        print(f"  {vname}: {vinfo['width_px']}x{vinfo['height_px']}px (~{vinfo['width_u']}u wide)")
    print("Top palette:", [p["hex"] for p in res["dominant_palette"][:8]])
    print(f"Saved crops, ref_ruler.png, and ref_analysis.json to {args.out}")


if __name__ == "__main__":
    main()
