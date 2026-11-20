# YSM AI Modeling Engine — Agent SOP & Technical Specification

> This guide is designed to be read directly by AI coding agents (Antigravity, Claude Code, Cursor, Codex, etc.) before building a Minecraft **Yes Steve Model (YSM 2.5 / 2.6.0)** character pack with `ysm_engine`.

---

## 1. Bedrock 1.12.0 Coordinate & Rotation Reference

Never guess signs! Always use these verified right-handed conventions:

* **Axes (Bedrock JSON space)**:
  * `+Y`: Up (`y = 0.0` is ground/feet bottom)
  * `-Z`: **Front** (character looks toward `-Z`, `north` face)
  * `+Z`: **Back** (`south` face)
  * `-X`: **Character's RIGHT** (`RightArm`, `RightLeg`; appears on viewer's LEFT in straight front view)
  * `+X`: **Character's LEFT** (`LeftArm`, `LeftLeg`; appears on viewer's RIGHT in straight front view)

* **Rotation `[rx, ry, rz]` (degrees around `pivot`)**:
  * `rx > 0`: pitches top forward (`-Z`) / swings bottom backward (`+Z`) — e.g. legs/back-hair swing backward (`+Z`)
  * `rx < 0`: pitches top backward (`+Z`) / swings bottom forward (`-Z`) — e.g. legs/arms swing forward (`-Z`), back hair sweeps outward when negative around top pivot
  * `ry > 0`: turns front (`-Z`) toward character's RIGHT (`-X`)
  * `rz > 0`: tilts bottom outward toward character's RIGHT (`-X`); `rz < 0` tilts bottom outward toward LEFT (`+X`)
  * Use `YSMModel.add_mirrored_cube(right_bone, left_bone, ...)` for symmetrical parts; it mirrors `X=0`, flips `ry` & `rz` signs, and swaps `east`/`west` face textures automatically.

---

## 2. YSM 2.6.0 Hard Compliance Rules

All packs must pass `ysm-validate <pack_dir>` with **0 errors**:

1. **UTF-8 without BOM** for all `.json` files (`ysm.json`, `models/*.json`, `animations/*.json`, `lang/*.json`), `spec: 2` in `ysm.json`, and exact-case relative file paths.
2. **Per-Face Integer UV Standard**:
   * Every cube uses per-face UV dict (`north/south/east/west/up/down`).
   * `description.texture_width == png_width` and `description.texture_height == png_height`.
   * Every `uv` and `uv_size` coordinate is a strict non-zero integer (`>= 1`) with zero overlap (`YSMModel.add_cube` guarantees this automatically via `ShelfPacker`).
3. **Required Bones & Parent Chains**:
   * `All` → `Waist` → `Body` → `AllHead` → `Head` → `ViewLocator`
   * `Body` → `RightArm` → `RightHand` → `RightHandLocator`
   * `Body` → `LeftArm` → `LeftHand` → `LeftHandLocator`
   * `Waist` → `RightLeg`, `LeftLeg`
   * Locators under `Body`: `ElytraLocator`, `BackpackLocator`, `LeftShoulderLocator`, `RightShoulderLocator`
4. **First-Person Arms (`models/arm.json`)**:
   * Generated automatically via `YSMModel.export_arm_json(...)` — promotes `LeftArm` and `RightArm` to root and zeroes root rotation `[0, 0, 0]`.
5. **Required 29 Core Animations (`animations/main.animation.json`)**:
   * `empty`, `gui`, `idle`, `walk`, `run`, `sneaking`, `sneak`, `jump`, `swim`, `swim_stand`, `fly`, `elytra_fly`, `sit`, `boat`, `ride`, `ride_pig`, `sleep`, `climb`, `climbing`, `ladder_up`, `ladder_stillness`, `ladder_down`, `swing_hand`, `swing_offhand`, `use_mainhand`, `use_offhand`, `attacked`, `death`, `parallel0`.

---

## 3. Recommended 4-Phase Modeling Workflow

### Phase 1: Reference Analysis & Proportions Blockout
1. Run `ysm-analyze <ref_image> -o reference --height <H>` (typically `32.0` ~ `38.0` units).
2. Inspect `reference/ref_ruler.png`, `reference/ref_analysis.json`, and the auto-generated high-res zooms:
   * `reference/crops/zoom_head_front.png` (3× zoomed front head with `1.0u` Bedrock grid & `X=0` center line)
   * `reference/crops/zoom_face_super.png` (4× clean facial super-zoom for eye pixels, highlights, brows & blush)
   * `reference/crops/zoom_head_side.png` & `zoom_head_back.png` (for hood depth, side hair thickness & back hair layering)
3. Build skeleton + primary limb/torso/head volumes, then inspect `ysm-render clay` and `ysm-render turnaround`.
4. Verify proportions & silhouette before sculpting fine details.

### Phase 2: Face-First High-Detail Sculpt (Mandatory Face Gate)
> **Why early AI rounds fail on faces**: Looking only at a full-body 3-view sheet leaves the face at <8% of image area, causing AI agents to hallucinate tiny 2×2 dot eyes, miss highlights/brows, or bury eyes behind bangs. Follow this mandatory protocol:

1. **Inspect Super-Zoom First**: Open `reference/crops/zoom_face_super.png` and `reference/crops/zoom_head_front.png` BEFORE writing any face/eye code. Measure directly from the `1.0u` grid:
   * Exact eye bounding box (`width × height` in Bedrock units, e.g. `3×2` grid big eyes vs `2×2` eyes), inter-eye spacing (`X` distance from `0`), and eye `Y` range.
   * Full eye anatomy: eyebrow color/thickness/Y-offset, upper lash bar, main iris color, lower iris highlight/gradient, catchlight/specular pixel position, sclera/eye-white, blush marks, and mouth/nose hints.
   * Subtle color tint check: never default to pure `#FFFFFF` or `#000000` if the reference has warm cream skin or pale lavender/blue-tinted white hair — sample actual RGB values from the crops.
2. **Use High Facial Pixel Density + Separate Eye Layer**:
   * Create `EyeRight` and `EyeLeft` child bones under `Head` placed `~0.03u` in front of the skin face so eye width, height, and spacing can be micro-tuned without repainting the head.
   * Never let global `texels_per_unit=3.0` blur small facial features: either build crisp multi-layer sub-voxel eye/brow panels OR pass a dedicated high-resolution `face_painter` patch (e.g. `24×24` to `48×48` px on the front face) so pupils, iris gradients, and catchlights stay razor sharp.
3. **Strict Facial Z-Layer Hierarchy (No Bangs Occlusion / No Z-Fighting)**:
   * `Head` skin face at `z_face`
   * `EyeRight` / `EyeLeft` & brows at `z_face - 0.03u`
   * Front bangs / side locks at `z_face - 0.18u` to `z_face - 0.55u` (leave an explicit open window for eyes & brows matching `zoom_face_super.png`)
   * Outer headgear / hood rim at `z_face - 0.60u` or further forward.
4. **Phase 2 Visual Gate**: Run `ysm-render overlay <geo> <tex> reference/crops/ref_front.png -o renders/head_overlay.png --yaw 0 --ymin <y0> --ymax <y1>` and `ysm-render closeups`. Do NOT move to Phase 3 until eye position, brow height, bangs framing, and hood contour align within `~0.3u` on the 50/50 overlay!

### Phase 3: Hair Layering, Side Thickness & 360° Polish (Mandatory Hair Gate)
1. **Sheet vs Strip vs Block Hair**: Match the reference aesthetic — for anime/layered hair, build broad, thin (`0.25u–0.65u`), subtly fanned overlapping **sheets (片状)** rather than thin isolated noodle strips ("一条条") or bulky bricks ("一块块").
2. **Side-View Thickness Check**: Inspect `reference/crops/zoom_head_side.png` and `zoom_head_back.png`, and ALWAYS run `ysm-render overlay` on BOTH `yaw=90` (`ref_side.png`) and `yaw=180` (`ref_back.png`) so back hair has authentic 3D side-view Z depth and no paper-thin gaps.
3. Inspect `ysm-render closeups` and `ysm-render clay` with SSAO lighting to confirm every surface layer reads cleanly.

### Phase 4: Animations, Validation & Packaging
1. Generate `animations/main.animation.json`, `animations/arm.animation.json`, `ysm.json`, and `lang/*.json`.
2. Add positive `rx` swing on `HairBack`/`HairBackLower` during `walk`/`run`/`sneaking`/`jump` so long back hair sweeps away from legs without clipping.
3. Render `ysm-render poses` and `ysm-render skeleton` and inspect visually.
4. Run `ysm-validate <pack_dir>` (must print `ALL CHECKS PASSED (0 errors)!`) and `ysm-package <pack_dir>` to produce `<pack>.zip` and `<pack>.bbmodel`.
