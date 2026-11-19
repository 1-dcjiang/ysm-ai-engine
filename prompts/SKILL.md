---
name: ysm-procedural-modeling
description: Build, SSAO-render, visually self-verify, validate, and package Minecraft Yes Steve Model (YSM 2.6.0) character packs using ysm-ai-engine.
---

# YSM Procedural Modeling Skill

Use this workflow whenever the user asks to create or refine a Minecraft **Yes Steve Model (YSM)** character model from reference images or descriptions.

## Environment Check
Ensure `ysm_engine` is importable (`pip install -e .` or copy `ysm_engine/` into the project root and ensure `numpy` and `pillow` are installed).
Read `prompts/AGENT_GUIDE.md` for full coordinate, rotation, and YSM 2.6.0 bone rules.

## Execution Loop

1. **Analyze Reference**:
   ```bash
   ysm-analyze <reference_image> -o reference --height 34.0
   ```
   Open `reference/ref_ruler.png` and `reference/crops/*` visually before writing geometry.

2. **Phase 1 — Skeleton & Proportions Blockout**:
   - Create `build_model.py` using `YSMModel` with all 18 required bones/locators.
   - Render clay & orthographic turnaround:
     ```bash
     ysm-render clay out/<pack>/models/main.json out/<pack>/textures/default.png -o renders/p1_clay.png
     ysm-render turnaround out/<pack>/models/main.json out/<pack>/textures/default.png --crops reference/crops -o renders/p1_turnaround.png
     ```
   - Inspect images and present milestone comparison to the user.

3. **Phase 2 & 3 — Detail Sculpting & 50/50 Overlay Alignment**:
   - Put eyes on separate `EyeRight`/`EyeLeft` bones under `Head` for independent sub-unit alignment.
   - Sculpt headgear, sheet/voxel hair with full side-view Z thickness, clothing pleats, and 3D emblems.
   - Verify Front (`yaw=0`), Left Side (`yaw=90`), and Back (`yaw=180`) with `ysm-render overlay`:
     ```bash
     ysm-render overlay <geo> <tex> reference/crops/ref_front.png -o renders/ov_front.png --yaw 0 --ymin 22 --ymax 34.6
     ysm-render overlay <geo> <tex> reference/crops/ref_side.png  -o renders/ov_side.png  --yaw 90 --ymin 10.5 --ymax 34.5
     ysm-render overlay <geo> <tex> reference/crops/ref_back.png  -o renders/ov_back.png  --yaw 180 --ymin 10.5 --ymax 34.5
     ```
   - Iterate until 50/50 overlays and `ysm-render closeups` match the reference faithfully.

4. **Phase 4 — Animations, Compliance & Packaging**:
   - Generate `main.animation.json` (all 29 core states), `arm.animation.json`, `ysm.json`, and `lang/*.json`.
   - Render poses & skeleton pivots:
     ```bash
     ysm-render poses <geo> <tex> <main_anim> -o renders/poses.png
     ysm-render skeleton <geo> <tex> -o renders/skeleton.png
     ```
   - Validate & package:
     ```bash
     ysm-validate out/<pack>
     ysm-package out/<pack>
     ```
   - Deliver `<pack>.zip` (for `.minecraft/config/yes_steve_model/custom/`) and `<pack>.bbmodel` (for Blockbench).
