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
2. Inspect `reference/ref_ruler.png` and `reference/ref_analysis.json` to lock exact Y milestones and widths/depths.
3. Build skeleton + primary limb/torso/head volumes, then inspect `ysm-render clay` and `ysm-render turnaround`.
4. Verify proportions & silhouette before sculpting fine details.

### Phase 2: Head, Face & Hero Silhouette Sculpt
1. **Separate Eye Layer Pattern**: Create `EyeRight` and `EyeLeft` child bones under `Head`, placing crisp pixel-art eyes `~0.03u` in front of the skin cube so eye spacing, height, and proportions can be fine-tuned independently without repainting the head.
2. Sculpt headgear/hood/accessories with clean flush planes where smooth surfaces are expected (avoid unintended Z-fighting or SSAO cracks).
3. Run `ysm-render overlay <geo> <tex> reference/crops/ref_front.png -o renders/head_overlay.png --yaw 0 --ymin <y0> --ymax <y1>` and verify **50/50 overlay alignment** visually.

### Phase 3: Hair Layering, Side Thickness & 360° Polish
1. **Sheet vs Voxel Hair**: Match the reference aesthetic — use broad, thin (`0.25u–0.65u`), subtly fanned overlapping sheets for flat-plane anime hair, or `1x1x1` stacked voxels for chunky pixel hair.
2. **Side-View Thickness Check**: Always verify `yaw=90` (`ref_side.png`) and `yaw=180` (`ref_back.png`) using `render_overlay_compare` so back hair has real 3D side depth and no paper-thin gaps.
3. Inspect `ysm-render closeups` and `ysm-render clay` with SSAO lighting to confirm every surface layer reads cleanly.

### Phase 4: Animations, Validation & Packaging
1. Generate `animations/main.animation.json`, `animations/arm.animation.json`, `ysm.json`, and `lang/*.json`.
2. Add positive `rx` swing on `HairBack`/`HairBackLower` during `walk`/`run`/`sneaking`/`jump` so long back hair sweeps away from legs without clipping.
3. Render `ysm-render poses` and `ysm-render skeleton` and inspect visually.
4. Run `ysm-validate <pack_dir>` (must print `ALL CHECKS PASSED (0 errors)!`) and `ysm-package <pack_dir>` to produce `<pack>.zip` and `<pack>.bbmodel`.
