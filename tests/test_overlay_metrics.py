"""Focused unit tests for the silhouette IoU metrics."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ysm_engine import compare_silhouettes


def _opaque_shape(size=(64, 64), box=(16, 16, 48, 48)) -> Image.Image:
    img = Image.new("RGB", size, (255, 255, 255))
    ImageDraw.Draw(img).rectangle(box, fill=(0, 0, 0))
    return img


def _alpha_shape(size=(64, 64), box=(22, 22, 42, 42), hole=None) -> Image.Image:
    arr = np.zeros((size[1], size[0], 4), dtype=np.uint8)
    arr[box[1]:box[3], box[0]:box[2]] = (255, 255, 255, 255)
    if hole is not None:
        arr[hole[1]:hole[3], hole[0]:hole[2]] = (0, 0, 0, 0)
    return Image.fromarray(arr, mode="RGBA")


class CompareSilhouettesTests(unittest.TestCase):
    def test_identical_opaque_images_score_one(self):
        img = _opaque_shape()
        metrics = compare_silhouettes(img, img.copy())
        self.assertEqual(metrics["iou"], 1.0)
        self.assertGreater(metrics["union_px"], 0)
        self.assertEqual(metrics["intersection_px"], metrics["union_px"])

    def test_disjoint_masks_score_zero(self):
        ref = Image.new("RGB", (64, 64), (255, 255, 255))
        mod = Image.new("RGB", (64, 64), (255, 255, 255))
        ImageDraw.Draw(ref).rectangle((0, 0, 23, 63), fill=(0, 0, 0))
        ImageDraw.Draw(mod).rectangle((40, 0, 63, 63), fill=(0, 0, 0))
        metrics = compare_silhouettes(ref, mod)
        self.assertEqual(metrics["iou"], 0.0)
        self.assertEqual(metrics["intersection_px"], 0)

    def test_known_partial_overlap_iou(self):
        ref = Image.new("RGB", (100, 100), (255, 255, 255))
        mod = Image.new("RGB", (100, 100), (255, 255, 255))
        ImageDraw.Draw(ref).rectangle((0, 0, 49, 99), fill=(0, 0, 0))
        ImageDraw.Draw(mod).rectangle((25, 0, 74, 99), fill=(0, 0, 0))
        metrics = compare_silhouettes(ref, mod)
        # 25 columns overlap, 75 columns union.
        self.assertEqual(metrics["intersection_px"], 2500)
        self.assertEqual(metrics["union_px"], 7500)
        self.assertAlmostEqual(metrics["iou"], 1.0 / 3.0, places=4)

    def test_mismatched_sizes_resize_model_to_reference(self):
        ref = Image.new("RGB", (64, 64), (0, 0, 0))
        mod = Image.new("RGB", (32, 32), (0, 0, 0))
        metrics = compare_silhouettes(ref, mod)
        self.assertEqual(metrics["iou"], 1.0)
        self.assertEqual(metrics["ref_coverage"], 1.0)
        self.assertEqual(metrics["union_px"], 64 * 64)

    def test_alpha_mask_keeps_white_foreground(self):
        img = _alpha_shape()
        metrics = compare_silhouettes(img, img.copy())
        # 20x20 opaque white square on a transparent background: color-distance
        # against white would see nothing, so this checks the alpha path.
        self.assertEqual(metrics["intersection_px"], 20 * 20)
        self.assertEqual(metrics["iou"], 1.0)
        self.assertAlmostEqual(metrics["ref_coverage"], 400 / 4096, places=4)

    def test_alpha_mask_detects_transparent_hole(self):
        ref = _alpha_shape()
        mod = _alpha_shape(hole=(30, 30, 34, 34))
        metrics = compare_silhouettes(ref, mod)
        self.assertEqual(metrics["intersection_px"], 400 - 16)
        self.assertEqual(metrics["union_px"], 400)
        self.assertAlmostEqual(metrics["iou"], 384 / 400, places=4)

    def test_empty_masks_score_zero_not_one(self):
        blank = Image.new("RGB", (64, 64), (255, 255, 255))
        metrics = compare_silhouettes(blank, blank.copy())
        self.assertEqual(metrics["union_px"], 0)
        self.assertEqual(metrics["iou"], 0.0)
        self.assertEqual(metrics["mean_abs_diff"], 0.0)


if __name__ == "__main__":
    unittest.main()
