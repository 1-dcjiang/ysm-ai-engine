import { unzipBuffer } from "./zip_reader.js";
import { parseYsmFileMap, parseBBModel, loadImageFromBytes } from "./bedrock_parser.js";
import { evaluateAnimation, getAnimationLength, mergePoses } from "./molang.js";
import { YsmWebGLRenderer } from "./webgl_renderer.js";
import { decodeRadianceHDR, sampleHemisphereColors } from "./hdr_loader.js";

// ============================================================================
// Friendly Chinese Labels for Standard YSM 2.6.0 Animations
// ============================================================================
const ANIM_LABELS = {
  __bind__: "默认站姿 (Bind)",
  idle: "待机呼吸",
  gui: "界面展示",
  walk: "行走",
  run: "奔跑",
  sneaking: "潜行待机",
  sneak: "潜行移动",
  jump: "跳跃",
  sit: "坐姿",
  boat: "乘船",
  ride: "骑乘",
  ride_pig: "骑猪",
  swim: "游泳",
  swim_stand: "水中漂浮",
  fly: "创造飞行",
  elytra_fly: "鞘翅滑翔",
  sleep: "睡眠",
  climb: "攀爬移动",
  climbing: "攀爬静止",
  ladder_up: "爬梯向上",
  ladder_stillness: "爬梯静止",
  ladder_down: "爬梯向下",
  swing_hand: "主手挥动",
  swing_offhand: "副手挥动",
  use_mainhand: "使用主手",
  use_offhand: "使用副手",
  attacked: "受伤受击",
  death: "倒地死亡",
  parallel0: "微风发丝层",
  empty: "空白状态",
  "use_mainhand:eat": "进食",
  "use_mainhand:drink": "饮水",
  "use_mainhand:bow": "拉弓射击",
  "use_mainhand:shield": "主手举盾",
  "use_offhand:shield": "副手举盾",
};

const ANIM_ORDER = [
  "idle", "gui", "walk", "run", "jump", "sit", "sneaking", "sneak",
  "fly", "elytra_fly", "swim", "swim_stand", "swing_hand", "swing_offhand",
  "climb", "ladder_up", "boat", "ride", "attacked", "sleep", "death",
];

// ============================================================================
// 6 Curated Studio Lighting & Environment Presets
// ============================================================================
const LIGHTING_PRESETS = {
  studio: {
    ambientIntensity: 0.72,
    skyColor: "#f3f6ff",
    groundColor: "#d9d2e9",
    keyIntensity: 0.56,
    keyColor: "#fff8f2",
    keyAzimuth: 36,
    keyElevation: 48,
    shadowStrength: 0.52,
    fillIntensity: 0.24,
    fillColor: "#cfe0ff",
    rimIntensity: 0.34,
    rimColor: "#ffffff",
    shadingMode: 0,
    exposure: 1.0,
    saturation: 1.02,
    bgTop: "#eef2fb",
    bgBottom: "#dfe6f6",
    skyboxMode: "pastel",
  },
  daylight: {
    ambientIntensity: 0.78,
    skyColor: "#d9eeff",
    groundColor: "#e6e0d5",
    keyIntensity: 0.72,
    keyColor: "#fffaf0",
    keyAzimuth: 48,
    keyElevation: 62,
    shadowStrength: 0.62,
    fillIntensity: 0.20,
    fillColor: "#c5e2ff",
    rimIntensity: 0.28,
    rimColor: "#e8f6ff",
    shadingMode: 0,
    exposure: 1.02,
    saturation: 1.06,
    bgTop: "#d7ebff",
    bgBottom: "#f4f8ff",
    skyboxMode: "clear",
  },
  sunset: {
    ambientIntensity: 0.58,
    skyColor: "#ffd2be",
    groundColor: "#785a82",
    keyIntensity: 0.85,
    keyColor: "#ffb885",
    keyAzimuth: 72,
    keyElevation: 22,
    shadowStrength: 0.70,
    fillIntensity: 0.24,
    fillColor: "#9eb4ff",
    rimIntensity: 0.65,
    rimColor: "#ffd2a6",
    shadingMode: 0,
    exposure: 1.04,
    saturation: 1.12,
    bgTop: "#3a2d54",
    bgBottom: "#c47d86",
    skyboxMode: "sunset",
  },
  moonlight: {
    ambientIntensity: 0.46,
    skyColor: "#7ea2f5",
    groundColor: "#252b48",
    keyIntensity: 0.62,
    keyColor: "#b8d4ff",
    keyAzimuth: 315,
    keyElevation: 44,
    shadowStrength: 0.72,
    fillIntensity: 0.22,
    fillColor: "#586ab8",
    rimIntensity: 0.78,
    rimColor: "#a8d8ff",
    shadingMode: 0,
    exposure: 1.08,
    saturation: 0.96,
    bgTop: "#11182c",
    bgBottom: "#253459",
    skyboxMode: "night",
  },
  neon: {
    ambientIntensity: 0.42,
    skyColor: "#b38cff",
    groundColor: "#21324f",
    keyIntensity: 0.52,
    keyColor: "#e6dcff",
    keyAzimuth: 24,
    keyElevation: 35,
    shadowStrength: 0.65,
    fillIntensity: 0.36,
    fillColor: "#6beeff",
    rimIntensity: 1.10,
    rimColor: "#ff7de9",
    shadingMode: 1,
    exposure: 1.05,
    saturation: 1.18,
    bgTop: "#151226",
    bgBottom: "#251c45",
    skyboxMode: "studioDark",
  },
  unlit: {
    ambientIntensity: 1.0,
    skyColor: "#ffffff",
    groundColor: "#ffffff",
    keyIntensity: 0.0,
    keyColor: "#ffffff",
    keyAzimuth: 36,
    keyElevation: 48,
    shadowStrength: 0.0,
    fillIntensity: 0.0,
    fillColor: "#ffffff",
    rimIntensity: 0.0,
    rimColor: "#ffffff",
    shadingMode: 2,
    exposure: 1.0,
    saturation: 1.0,
    bgTop: "#f4f6fc",
    bgBottom: "#eaeef9",
    skyboxMode: "gradient",
  },
};

const BONE_HINTS = {
  All: "总根骨骼",
  Waist: "腰部",
  Body: "躯干",
  AllHead: "头部总控",
  Head: "头颅",
  WhaleHood: "鲸鱼兜帽",
  HairBangs: "前刘海",
  HairFrontRight: "右前垂发",
  HairFrontLeft: "左前垂发",
  HairBack: "背发上段",
  HairBackLower: "背发下段",
  EyeRight: "右眼",
  EyeLeft: "左眼",
  RightArm: "右臂",
  RightHand: "右手",
  LeftArm: "左臂",
  LeftHand: "左手",
  RightLeg: "右腿",
  LeftLeg: "左腿",
  Skirt: "百褶裙",
  ChestRibbon: "胸前领结",
  SideStrap: "侧边飘带",
};

// ============================================================================
// Application State
// ============================================================================
const $ = (id) => document.getElementById(id);
const renderer = new YsmWebGLRenderer($("glCanvas"));

const state = {
  pack: null,
  activePart: "main", // "main" | "arm"
  activeTexIndex: 0,
  activeAnim: "idle",
  activeTab: "anim",
  playing: true,
  loop: true,
  useParallel: true,
  speed: 1.0,
  animTime: 0,
  parallelTime: 0,
  headYaw: 0,
  headPitch: 0,
  selectedBone: null,
  boneOverrides: new Map(), // boneName -> { rotation:[0,0,0], position:[0,0,0], scale:[1,1,1], hidden:false, mode:'add' }
  skySyncAmb: true,
};

let toastTimer = null;
function showToast(msg, duration = 2800) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.add("hidden"), duration);
}

// ============================================================================
// Apply Pack to Renderer & Sync UI
// ============================================================================
function activatePack(pack, resetCamera = true) {
  state.pack = pack;
  state.activePart = "main";
  state.activeTexIndex = 0;
  state.animTime = 0;

  const geo = pack.models.main;
  renderer.setGeometry(geo);
  if (pack.textures.length > 0) {
    renderer.setTexture(pack.textures[0].image);
  }
  if (resetCamera) {
    renderer.frameModel("threeQuarter");
    syncCameraDockActive("threeQuarter");
  }

  // Pick a pleasant default animation
  const anims = pack.animations.main || {};
  if (anims.idle) state.activeAnim = "idle";
  else if (anims.gui) state.activeAnim = "gui";
  else {
    const keys = Object.keys(anims);
    state.activeAnim = keys.length > 0 ? keys[0] : "__bind__";
  }

  // Update UI metadata
  $("modelMetaSub").textContent = `${pack.name} · ${pack.sourceLabel}`;
  $("infoName").textContent = pack.name;
  $("infoTips").textContent = pack.tips || "已通过本地 WebGL2 引擎加载。";

  // Enable/disable arm button
  const armBtn = document.querySelector('#partSeg [data-part="arm"]');
  armBtn.disabled = !pack.models.arm;
  document.querySelectorAll("#partSeg .seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.part === "main");
  });

  state.boneOverrides.clear();
  state.selectedBone = geo.bones.find((b) => b.name === "RightArm")?.name || geo.bones[0]?.name || null;

  updateHudStats();
  renderAnimList();
  renderBoneTree();
  syncBoneEditorUi();
  renderTextureList();
  syncTimeControls();
}

function switchModelPart(part) {
  if (!state.pack || !state.pack.models[part]) return;
  state.activePart = part;
  const geo = state.pack.models[part];
  renderer.setGeometry(geo);
  renderer.frameModel("threeQuarter");

  const anims = state.pack.animations[part] || {};
  const keys = Object.keys(anims);
  state.activeAnim = anims.idle ? "idle" : keys[0] || "__bind__";
  state.animTime = 0;
  state.boneOverrides.clear();
  state.selectedBone = geo.bones[0]?.name || null;

  document.querySelectorAll("#partSeg .seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.part === part);
  });
  updateHudStats();
  renderAnimList();
  renderBoneTree();
  syncBoneEditorUi();
  syncTimeControls();
}

function updateHudStats() {
  if (!state.pack) return;
  const geo = state.pack.models[state.activePart];
  const tex = state.pack.textures[state.activeTexIndex];
  $("statName").textContent = state.pack.name;
  $("statBones").textContent = `${geo.boneCount} 骨骼`;
  $("statCubes").textContent = `${geo.cubeCount} 方块`;
  $("statTex").textContent = tex ? `${tex.width}×${tex.height}` : "-";
}

function renderAnimList() {
  const container = $("animList");
  container.innerHTML = "";
  const anims = (state.pack?.animations?.[state.activePart]) || {};
  const filter = $("animSearch").value.trim().toLowerCase();

  const names = Object.keys(anims).sort((a, b) => {
    const ia = ANIM_ORDER.indexOf(a);
    const ib = ANIM_ORDER.indexOf(b);
    if (ia >= 0 && ib >= 0) return ia - ib;
    if (ia >= 0) return -1;
    if (ib >= 0) return 1;
    return a.localeCompare(b);
  });

  const allEntries = ["__bind__", ...names];
  let shown = 0;
  for (const name of allEntries) {
    const cn = ANIM_LABELS[name] || name;
    if (filter && !name.toLowerCase().includes(filter) && !cn.toLowerCase().includes(filter)) {
      continue;
    }
    shown++;
    const btn = document.createElement("button");
    btn.className = "anim-pill" + (state.activeAnim === name ? " active" : "");
    btn.innerHTML = `<span class="cn">${cn}</span><span class="en">${name === "__bind__" ? "static" : name}</span>`;
    btn.addEventListener("click", () => {
      state.activeAnim = name;
      state.animTime = 0;
      state.playing = true;
      $("btnPlayPause").textContent = "⏸ 暂停";
      renderAnimList();
      syncTimeControls();
    });
    container.appendChild(btn);
  }
  $("animCount").textContent = String(names.length);
  if (shown === 0) {
    container.innerHTML = `<div style="grid-column:1/-1;color:var(--text-dim);font-size:11px;padding:8px;">无匹配动作</div>`;
  }
}

function renderTextureList() {
  const list = $("texList");
  list.innerHTML = "";
  const textures = state.pack?.textures || [];
  textures.forEach((t, idx) => {
    const item = document.createElement("button");
    item.className = "tex-item" + (idx === state.activeTexIndex ? " active" : "");
    item.innerHTML = `<span>${t.name}</span><span class="mono-badge">${t.width}×${t.height}</span>`;
    item.addEventListener("click", () => {
      state.activeTexIndex = idx;
      renderer.setTexture(t.image);
      renderTextureList();
      updateHudStats();
    });
    list.appendChild(item);
  });
  const activeTex = textures[state.activeTexIndex];
  if (activeTex) {
    $("texPreview").src = activeTex.image.src;
  }
}

function getActiveAnimObj() {
  if (!state.pack || state.activeAnim === "__bind__") return null;
  return state.pack.animations?.[state.activePart]?.[state.activeAnim] || null;
}

function syncTimeControls() {
  const anim = getActiveAnimObj();
  const len = anim ? getAnimationLength(anim) : 1.0;
  const rng = $("rngTime");
  rng.max = String(len);
  const clamped = Math.min(len, Math.max(0, state.animTime));
  rng.value = String(clamped);
  $("timeLabel").textContent = `${clamped.toFixed(2)}s / ${len.toFixed(2)}s`;
}

// ============================================================================
// Per-Bone Manual Pose Editor (Hierarchy, Sliders, Mirror, Export)
// ============================================================================
function getOrCreateBoneOverride(boneName) {
  if (!state.boneOverrides.has(boneName)) {
    state.boneOverrides.set(boneName, {
      rotation: [0, 0, 0],
      position: [0, 0, 0],
      scale: [1, 1, 1],
      hidden: false,
      mode: "add",
    });
  }
  return state.boneOverrides.get(boneName);
}

function isBoneModified(boneName) {
  const ov = state.boneOverrides.get(boneName);
  if (!ov) return false;
  return (
    ov.hidden ||
    ov.mode === "replace" ||
    ov.rotation.some((v) => Math.abs(v) > 1e-3) ||
    ov.position.some((v) => Math.abs(v) > 1e-3) ||
    ov.scale.some((v) => Math.abs(v - 1) > 1e-3)
  );
}

function buildOrderedBoneTree(bones) {
  const childrenMap = new Map();
  const boneSet = new Set(bones.map((b) => b.name));
  const roots = [];
  for (const b of bones) {
    if (!b.parent || !boneSet.has(b.parent)) {
      roots.push(b);
    } else {
      if (!childrenMap.has(b.parent)) childrenMap.set(b.parent, []);
      childrenMap.get(b.parent).push(b);
    }
  }
  const ordered = [];
  const walk = (b, depth) => {
    ordered.push({ bone: b, depth });
    for (const ch of childrenMap.get(b.name) || []) {
      walk(ch, depth + 1);
    }
  };
  for (const r of roots) walk(r, 0);
  return ordered;
}

function renderBoneTree() {
  const container = $("boneTree");
  if (!container) return;
  container.innerHTML = "";
  const geo = state.pack?.models?.[state.activePart];
  if (!geo) return;

  const filter = ($("boneSearch")?.value || "").trim().toLowerCase();
  const ordered = buildOrderedBoneTree(geo.bones);
  $("boneCountLabel").textContent = String(geo.bones.length);

  for (const { bone, depth } of ordered) {
    const hint = BONE_HINTS[bone.name] || "";
    if (filter && !bone.name.toLowerCase().includes(filter) && !hint.toLowerCase().includes(filter)) {
      continue;
    }
    const ov = state.boneOverrides.get(bone.name);
    const hidden = Boolean(ov && ov.hidden);
    const modified = isBoneModified(bone.name);

    const row = document.createElement("div");
    row.className = "bone-row" + (state.selectedBone === bone.name ? " active" : "");

    const left = document.createElement("div");
    left.className = "bone-row-left";
    const indentPx = filter ? 0 : Math.min(depth, 5) * 11;
    left.style.paddingLeft = `${indentPx}px`;

    const prefix = depth > 0 && !filter ? `<span class="bone-indent">└</span>` : "";
    const modDot = modified ? `<span class="bone-mod-dot" title="已手动调整"></span>` : "";
    const hintTag = hint ? ` <span style="opacity:0.55;font-size:10px;">${hint}</span>` : "";
    left.innerHTML = `${prefix}${modDot}<span>${bone.name}${hintTag}</span>`;

    const visBtn = document.createElement("button");
    visBtn.className = "bone-vis-btn" + (hidden ? " is-hidden" : "");
    visBtn.title = hidden ? "显示此骨骼" : "隐藏此骨骼";
    visBtn.textContent = hidden ? "🚫" : "👁";
    visBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const targetOv = getOrCreateBoneOverride(bone.name);
      targetOv.hidden = !targetOv.hidden;
      renderBoneTree();
    });

    row.appendChild(left);
    row.appendChild(visBtn);
    row.addEventListener("click", () => {
      state.selectedBone = bone.name;
      renderBoneTree();
      syncBoneEditorUi();
    });
    container.appendChild(row);
  }
}

function syncBoneEditorUi() {
  const bname = state.selectedBone;
  const hint = bname && BONE_HINTS[bname] ? ` (${BONE_HINTS[bname]})` : "";
  $("selBoneName").textContent = bname ? `${bname}${hint}` : "未选择";
  const ov = (bname && state.boneOverrides.get(bname)) || {
    rotation: [0, 0, 0],
    position: [0, 0, 0],
    scale: [1, 1, 1],
    hidden: false,
    mode: "add",
  };

  $("rngBoneRx").value = ov.rotation[0];
  $("valBoneRx").textContent = `${Math.round(ov.rotation[0])}°`;
  $("rngBoneRy").value = ov.rotation[1];
  $("valBoneRy").textContent = `${Math.round(ov.rotation[1])}°`;
  $("rngBoneRz").value = ov.rotation[2];
  $("valBoneRz").textContent = `${Math.round(ov.rotation[2])}°`;

  $("rngBonePx").value = ov.position[0];
  $("valBonePx").textContent = ov.position[0].toFixed(1);
  $("rngBonePy").value = ov.position[1];
  $("valBonePy").textContent = ov.position[1].toFixed(1);
  $("rngBonePz").value = ov.position[2];
  $("valBonePz").textContent = ov.position[2].toFixed(1);

  $("rngBoneSx").value = ov.scale[0];
  $("valBoneSx").textContent = ov.scale[0].toFixed(2);
  $("rngBoneSy").value = ov.scale[1];
  $("valBoneSy").textContent = ov.scale[1].toFixed(2);
  $("rngBoneSz").value = ov.scale[2];
  $("valBoneSz").textContent = ov.scale[2].toFixed(2);

  document.querySelectorAll("#boneModeSeg .seg-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.bmode === ov.mode);
  });
}

function mirrorSelectedBone() {
  const bname = state.selectedBone;
  const geo = state.pack?.models?.[state.activePart];
  if (!bname || !geo) return;

  let mirrorName = null;
  if (bname.includes("Right")) mirrorName = bname.replace("Right", "Left");
  else if (bname.includes("Left")) mirrorName = bname.replace("Left", "Right");

  if (!mirrorName || !geo.bones.some((b) => b.name === mirrorName)) {
    showToast(`未找到 ${bname} 的左右对称骨骼`);
    return;
  }

  const src = getOrCreateBoneOverride(bname);
  const dst = getOrCreateBoneOverride(mirrorName);
  dst.rotation = [src.rotation[0], -src.rotation[1], -src.rotation[2]];
  dst.position = [-src.position[0], src.position[1], src.position[2]];
  dst.scale = [...src.scale];
  dst.mode = src.mode;
  renderBoneTree();
  showToast(`已将 ${bname} 姿态镜像复制到 ${mirrorName}`);
}

function exportManualPoseJson() {
  const bonesOut = {};
  for (const [bname, ov] of state.boneOverrides.entries()) {
    if (!isBoneModified(bname)) continue;
    const track = {};
    if (ov.rotation.some((v) => Math.abs(v) > 1e-3)) {
      track.rotation = ov.rotation.map((v) => Number(v.toFixed(2)));
    }
    if (ov.position.some((v) => Math.abs(v) > 1e-3)) {
      track.position = ov.position.map((v) => Number(v.toFixed(2)));
    }
    if (ov.scale.some((v) => Math.abs(v - 1) > 1e-3)) {
      track.scale = ov.scale.map((v) => Number(v.toFixed(3)));
    }
    if (ov.hidden) {
      track.scale = [0, 0, 0];
    }
    if (Object.keys(track).length > 0) {
      bonesOut[bname] = track;
    }
  }
  if (Object.keys(bonesOut).length === 0) {
    showToast("尚未修改任何骨骼，请先拖动骨骼滑块调整姿势！");
    return;
  }
  const animPayload = {
    format_version: "1.8.0",
    animations: {
      custom_pose: {
        loop: true,
        animation_length: 1.0,
        bones: bonesOut,
      },
    },
  };
  const blob = new Blob([JSON.stringify(animPayload, null, 2)], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(state.pack?.name || "ysm_model").replace(/[^\w\u4e00-\u9fa5-]+/g, "_")}_custom_pose.animation.json`;
  a.click();
  URL.revokeObjectURL(url);
  showToast(`已导出自定义动作 JSON（含 ${Object.keys(bonesOut).length} 根骨骼）`);
}

// ============================================================================
// Lighting, Skybox & Background UI Sync
// ============================================================================
async function loadCustomSkyboxFile(file) {
  if (!file) return;
  try {
    showToast(`正在加载天空盒 ${file.name} ...`);
    let imgSource;
    if (/\.hdr$/i.test(file.name)) {
      const buf = await file.arrayBuffer();
      imgSource = decodeRadianceHDR(buf);
    } else {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const mime = /\.jpe?g$/i.test(file.name)
        ? "image/jpeg"
        : /\.webp$/i.test(file.name)
        ? "image/webp"
        : "image/png";
      imgSource = await loadImageFromBytes(bytes, mime);
    }
    renderer.setSkyboxTexture(imgSource);
    renderer.lighting.skyboxMode = "custom";
    renderer.lighting.transparentBg = false;

    if (state.skySyncAmb) {
      const hemi = sampleHemisphereColors(imgSource);
      renderer.lighting.skyColor = hemi.skyColor;
      renderer.lighting.groundColor = hemi.groundColor;
    }

    $("customSkyName").textContent = `已加载：${file.name}`;
    $("customSkyBadge").classList.remove("hidden");
    syncLightingUiFromState();
    showToast(`已切换自定义 360° 天空盒：${file.name}`);
  } catch (err) {
    console.error(err);
    showToast(`天空盒加载失败：${err.message || err}`, 4200);
  }
}

function applyStageBackground() {
  const L = renderer.lighting;
  const wrap = $("stageWrap");
  if (L.transparentBg) {
    wrap.classList.add("transparent-bg");
    wrap.style.background = "";
  } else {
    wrap.classList.remove("transparent-bg");
    wrap.style.background = `linear-gradient(180deg, ${L.bgTop} 0%, ${L.bgBottom} 100%)`;
  }
}

function syncLightingUiFromState() {
  const L = renderer.lighting;
  $("rngAmbInt").value = L.ambientIntensity;
  $("valAmbInt").textContent = L.ambientIntensity.toFixed(2);
  $("colSky").value = L.skyColor;
  $("colGround").value = L.groundColor;

  $("rngKeyInt").value = L.keyIntensity;
  $("valKeyInt").textContent = L.keyIntensity.toFixed(2);
  $("rngKeyAz").value = L.keyAzimuth;
  $("valKeyAz").textContent = `${Math.round(L.keyAzimuth)}°`;
  $("rngKeyEl").value = L.keyElevation;
  $("valKeyEl").textContent = `${Math.round(L.keyElevation)}°`;
  $("rngShadow").value = L.shadowStrength;
  $("valShadow").textContent = `${Math.round(L.shadowStrength * 100)}%`;
  $("colKey").value = L.keyColor;

  $("colFill").value = L.fillColor;
  $("rngFillInt").value = L.fillIntensity;
  $("valFillInt").textContent = L.fillIntensity.toFixed(2);

  $("rngRimInt").value = L.rimIntensity;
  $("valRimInt").textContent = L.rimIntensity.toFixed(2);
  $("colRim").value = L.rimColor;

  $("rngExp").value = L.exposure;
  $("valExp").textContent = L.exposure.toFixed(2);
  $("rngSat").value = L.saturation;
  $("valSat").textContent = L.saturation.toFixed(2);

  $("rngSkyRot").value = L.skyRotation;
  $("valSkyRot").textContent = `${Math.round(L.skyRotation)}°`;
  $("rngSkyExp").value = L.skyExposure;
  $("valSkyExp").textContent = L.skyExposure.toFixed(2);
  $("rngSkyBlur").value = L.skyBlur;
  $("valSkyBlur").textContent = `${Math.round(L.skyBlur * 100)}%`;

  $("colBgTop").value = L.bgTop;
  $("colBgBot").value = L.bgBottom;
  $("chkStage").checked = L.showStage;
  $("chkGrid").checked = L.showGrid;
  $("chkTransparent").checked = L.transparentBg;

  document.querySelectorAll("#shadingSeg .seg-btn").forEach((b) => {
    b.classList.toggle("active", Number(b.dataset.shading) === L.shadingMode);
  });
  document.querySelectorAll("#skyGrid .sky-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.sky === L.skyboxMode);
  });
  applyStageBackground();
}

function applyLightingPreset(presetKey) {
  const p = LIGHTING_PRESETS[presetKey];
  if (!p) return;
  Object.assign(renderer.lighting, p);
  syncLightingUiFromState();
  document.querySelectorAll(".preset-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.preset === presetKey);
  });
}

// ============================================================================
// Universal File / ZIP / Folder / BBModel Importer
// ============================================================================
async function handleImportedFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length) return;

  try {
    // 1. Single ZIP / YSM archive
    if (files.length === 1 && /\.(zip|ysm)$/i.test(files[0].name)) {
      showToast(`正在解压 ${files[0].name} ...`);
      const buf = await files[0].arrayBuffer();
      const map = await unzipBuffer(buf);
      const pack = await parseYsmFileMap(map, files[0].name);
      activatePack(pack);
      showToast(`已加载模型包：${pack.name}`);
      return;
    }

    // 2. Single .bbmodel
    if (files.length === 1 && /\.bbmodel$/i.test(files[0].name)) {
      const text = await files[0].text();
      const pack = await parseBBModel(JSON.parse(text), files[0].name);
      activatePack(pack);
      showToast(`已导入 Blockbench 工程：${pack.name}`);
      return;
    }

    // 2.5. Single HDR / JPG / WebP panorama -> load as 360° Skybox!
    if (files.length === 1 && /\.(hdr|jpe?g|webp)$/i.test(files[0].name)) {
      await loadCustomSkyboxFile(files[0]);
      return;
    }

    // 3. Single PNG texture hot-swap
    if (files.length === 1 && /\.png$/i.test(files[0].name) && state.pack) {
      const bytes = new Uint8Array(await files[0].arrayBuffer());
      const img = await loadImageFromBytes(bytes, "image/png");
      state.pack.textures.push({
        name: files[0].name,
        image: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
      });
      state.activeTexIndex = state.pack.textures.length - 1;
      renderer.setTexture(img);
      renderTextureList();
      updateHudStats();
      showToast(`已切换皮肤贴图：${files[0].name}`);
      return;
    }

    // 4. Single animation JSON hot-swap
    if (files.length === 1 && /\.animation\.json$/i.test(files[0].name) && state.pack) {
      const parsed = JSON.parse(await files[0].text());
      if (parsed.animations) {
        state.pack.animations[state.activePart] = parsed.animations;
        const keys = Object.keys(parsed.animations);
        state.activeAnim = parsed.animations.idle ? "idle" : keys[0] || "__bind__";
        state.animTime = 0;
        renderAnimList();
        syncTimeControls();
        showToast(`已加载动画文件：${files[0].name}（${keys.length} 组动作）`);
        return;
      }
    }

    // 5. Folder or multi-file drop
    const map = new Map();
    for (const f of files) {
      const key = (f.webkitRelativePath || f.name).replace(/\\/g, "/");
      map.set(key, new Uint8Array(await f.arrayBuffer()));
    }
    const label = files[0].webkitRelativePath
      ? files[0].webkitRelativePath.split("/")[0]
      : "自定义文件组";
    const pack = await parseYsmFileMap(map, label);
    activatePack(pack);
    showToast(`已加载模型：${pack.name}`);
  } catch (err) {
    console.error(err);
    showToast(`导入失败：${err.message || err}`, 4500);
  }
}

// ============================================================================
// Auto-Preload Local Model Directory (when passed to `ysm-viewer` CLI)
// ============================================================================
async function loadDemoPack() {
  try {
    const infoRes = await fetch("/api/demo-info");
    if (!infoRes.ok) {
      $("modelMetaSub").textContent = "等待导入 YSM 模型包（支持拖拽 .zip / .bbmodel / 文件夹）";
      return;
    }
    const info = await infoRes.json();
    if (!info.available || !Array.isArray(info.files) || info.files.length === 0) {
      $("modelMetaSub").textContent = "请拖入或点击导入 .zip / .bbmodel / 模型文件夹";
      return;
    }

    const demoBtn = $("btnLoadDemo");
    if (demoBtn) demoBtn.classList.remove("hidden");
    showToast(`正在加载本地模型：${info.name}...`);

    const map = new Map();
    await Promise.all(
      info.files.map(async (p) => {
        const res = await fetch(`/demo/model/${p}`);
        if (res.ok) {
          map.set(p, new Uint8Array(await res.arrayBuffer()));
        }
      })
    );

    const pack = await parseYsmFileMap(map, `${info.name} (本地目录)`);
    activatePack(pack);
    showToast(`已加载本地模型：${pack.name}`);
  } catch (err) {
    console.warn("Preload skipped:", err);
    $("modelMetaSub").textContent = "等待导入 YSM 模型包（支持拖拽 .zip / .bbmodel / 文件夹）";
  }
}

// ============================================================================
// Wire Up UI Events
// ============================================================================
function syncCameraDockActive(camName) {
  document.querySelectorAll(".dock-btn[data-cam]").forEach((b) => {
    b.classList.toggle("active", b.dataset.cam === camName);
  });
}

function initUI() {
  // Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
      btn.classList.add("active");
      state.activeTab = btn.dataset.tab;
      $(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // Panel collapse
  $("btnTogglePanel").addEventListener("click", () => {
    $("inspector").classList.toggle("collapsed");
  });

  // File & Folder imports
  const triggerFilePick = () => {
    $("fileInput").value = "";
    $("fileInput").click();
  };
  $("btnImportFiles").addEventListener("click", triggerFilePick);
  $("btnImportFiles2").addEventListener("click", triggerFilePick);
  $("btnImportFolder").addEventListener("click", () => {
    $("folderInput").value = "";
    $("folderInput").click();
  });
  $("btnLoadDemo").addEventListener("click", loadDemoPack);

  $("fileInput").addEventListener("change", (e) => handleImportedFiles(e.target.files));
  $("folderInput").addEventListener("change", (e) => handleImportedFiles(e.target.files));

  $("btnAddTex").addEventListener("click", () => {
    $("texInput").value = "";
    $("texInput").click();
  });
  $("texInput").addEventListener("change", (e) => handleImportedFiles(e.target.files));

  $("btnReplaceAnim").addEventListener("click", () => {
    $("animInput").value = "";
    $("animInput").click();
  });
  $("animInput").addEventListener("change", (e) => handleImportedFiles(e.target.files));

  // Global Drag & Drop
  let dragCounter = 0;
  window.addEventListener("dragenter", (e) => {
    e.preventDefault();
    dragCounter++;
    $("dropOverlay").classList.remove("hidden");
  });
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("dragleave", () => {
    dragCounter = Math.max(0, dragCounter - 1);
    if (dragCounter === 0) $("dropOverlay").classList.add("hidden");
  });
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    dragCounter = 0;
    $("dropOverlay").classList.add("hidden");
    if (e.dataTransfer?.files?.length) {
      handleImportedFiles(e.dataTransfer.files);
    }
  });

  // Camera dock
  document.querySelectorAll(".dock-btn[data-cam]").forEach((btn) => {
    btn.addEventListener("click", () => {
      renderer.frameModel(btn.dataset.cam);
      syncCameraDockActive(btn.dataset.cam);
    });
  });

  $("btnOrtho").addEventListener("click", (e) => {
    renderer.camera.ortho = !renderer.camera.ortho;
    e.currentTarget.textContent = renderer.camera.ortho ? "正交" : "透视";
    e.currentTarget.classList.toggle("active", renderer.camera.ortho);
  });

  $("btnAutoRotate").addEventListener("click", (e) => {
    renderer.camera.autoRotate = !renderer.camera.autoRotate;
    e.currentTarget.classList.toggle("active", renderer.camera.autoRotate);
  });

  $("btnSkeleton").addEventListener("click", (e) => {
    renderer.lighting.showSkeleton = !renderer.lighting.showSkeleton;
    e.currentTarget.classList.toggle("active", renderer.lighting.showSkeleton);
  });

  // Screenshot PNG export
  $("btnScreenshot").addEventListener("click", () => {
    const srcCanvas = $("glCanvas");
    const out = document.createElement("canvas");
    out.width = srcCanvas.width;
    out.height = srcCanvas.height;
    const ctx = out.getContext("2d");
    if (!renderer.lighting.transparentBg) {
      const grad = ctx.createLinearGradient(0, 0, 0, out.height);
      grad.addColorStop(0, renderer.lighting.bgTop);
      grad.addColorStop(1, renderer.lighting.bgBottom);
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, out.width, out.height);
    }
    ctx.drawImage(srcCanvas, 0, 0);
    const link = document.createElement("a");
    link.download = `${(state.pack?.name || "ysm_model").replace(/[^\w\u4e00-\u9fa5-]+/g, "_")}_${state.activeAnim}.png`;
    link.href = out.toDataURL("image/png");
    link.click();
    showToast("已保存高清 PNG 截图 📸");
  });

  // Animation controls
  $("btnPlayPause").addEventListener("click", () => {
    state.playing = !state.playing;
    $("btnPlayPause").textContent = state.playing ? "⏸ 暂停" : "▶ 播放";
  });
  $("btnResetAnim").addEventListener("click", () => {
    state.animTime = 0;
    syncTimeControls();
  });
  $("chkLoop").addEventListener("change", (e) => {
    state.loop = e.target.checked;
  });
  $("chkParallel").addEventListener("change", (e) => {
    state.useParallel = e.target.checked;
  });
  $("rngTime").addEventListener("input", (e) => {
    state.animTime = parseFloat(e.target.value) || 0;
    state.playing = false;
    $("btnPlayPause").textContent = "▶ 播放";
    syncTimeControls();
  });
  $("rngSpeed").addEventListener("input", (e) => {
    state.speed = parseFloat(e.target.value) || 1.0;
    $("valSpeed").textContent = `${state.speed.toFixed(2)}×`;
  });
  $("animSearch").addEventListener("input", renderAnimList);

  // Head look controls
  $("rngHeadYaw").addEventListener("input", (e) => {
    state.headYaw = parseFloat(e.target.value) || 0;
    $("valHeadYaw").textContent = `${Math.round(state.headYaw)}°`;
  });
  $("rngHeadPitch").addEventListener("input", (e) => {
    state.headPitch = parseFloat(e.target.value) || 0;
    $("valHeadPitch").textContent = `${Math.round(state.headPitch)}°`;
  });
  $("btnResetHead").addEventListener("click", () => {
    state.headYaw = 0;
    state.headPitch = 0;
    $("rngHeadYaw").value = 0;
    $("rngHeadPitch").value = 0;
    $("valHeadYaw").textContent = "0°";
    $("valHeadPitch").textContent = "0°";
  });

  // Per-Bone Manual Pose Editor Listeners
  $("boneSearch").addEventListener("input", renderBoneTree);

  const bindBoneAxis = (id, channel, axisIdx, valId, fmt) => {
    $(id).addEventListener("input", (e) => {
      if (!state.selectedBone) return;
      const v = parseFloat(e.target.value);
      const ov = getOrCreateBoneOverride(state.selectedBone);
      ov[channel][axisIdx] = v;
      $(valId).textContent = fmt(v);
      renderBoneTree();
    });
  };
  bindBoneAxis("rngBoneRx", "rotation", 0, "valBoneRx", (v) => `${Math.round(v)}°`);
  bindBoneAxis("rngBoneRy", "rotation", 1, "valBoneRy", (v) => `${Math.round(v)}°`);
  bindBoneAxis("rngBoneRz", "rotation", 2, "valBoneRz", (v) => `${Math.round(v)}°`);
  bindBoneAxis("rngBonePx", "position", 0, "valBonePx", (v) => v.toFixed(1));
  bindBoneAxis("rngBonePy", "position", 1, "valBonePy", (v) => v.toFixed(1));
  bindBoneAxis("rngBonePz", "position", 2, "valBonePz", (v) => v.toFixed(1));
  bindBoneAxis("rngBoneSx", "scale", 0, "valBoneSx", (v) => v.toFixed(2));
  bindBoneAxis("rngBoneSy", "scale", 1, "valBoneSy", (v) => v.toFixed(2));
  bindBoneAxis("rngBoneSz", "scale", 2, "valBoneSz", (v) => v.toFixed(2));

  document.querySelectorAll("#boneModeSeg .seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      if (!state.selectedBone) return;
      const ov = getOrCreateBoneOverride(state.selectedBone);
      ov.mode = b.dataset.bmode;
      syncBoneEditorUi();
      renderBoneTree();
    });
  });

  $("btnResetBone").addEventListener("click", () => {
    if (!state.selectedBone) return;
    state.boneOverrides.delete(state.selectedBone);
    syncBoneEditorUi();
    renderBoneTree();
  });
  $("btnResetBonePos").addEventListener("click", () => {
    if (!state.selectedBone) return;
    const ov = getOrCreateBoneOverride(state.selectedBone);
    ov.position = [0, 0, 0];
    syncBoneEditorUi();
    renderBoneTree();
  });
  $("btnResetBoneScale").addEventListener("click", () => {
    if (!state.selectedBone) return;
    const ov = getOrCreateBoneOverride(state.selectedBone);
    ov.scale = [1, 1, 1];
    syncBoneEditorUi();
    renderBoneTree();
  });
  $("btnResetAllBones").addEventListener("click", () => {
    state.boneOverrides.clear();
    syncBoneEditorUi();
    renderBoneTree();
    showToast("已重置全部手动骨骼姿态");
  });
  $("btnMirrorBone").addEventListener("click", mirrorSelectedBone);
  $("btnExportPose").addEventListener("click", exportManualPoseJson);

  // 360° Skybox Controls
  document.querySelectorAll("#skyGrid .sky-btn").forEach((b) => {
    b.addEventListener("click", () => {
      renderer.lighting.skyboxMode = b.dataset.sky;
      renderer.lighting.transparentBg = false;
      syncLightingUiFromState();
    });
  });
  $("btnUploadSkybox").addEventListener("click", () => {
    $("skyboxInput").value = "";
    $("skyboxInput").click();
  });
  $("skyboxInput").addEventListener("change", (e) => {
    if (e.target.files?.[0]) loadCustomSkyboxFile(e.target.files[0]);
  });
  $("btnUseCustomSky").addEventListener("click", () => {
    if (!renderer.hasCustomSkybox) return;
    renderer.lighting.skyboxMode = "custom";
    renderer.lighting.transparentBg = false;
    syncLightingUiFromState();
  });
  $("rngSkyRot").addEventListener("input", (e) => {
    renderer.lighting.skyRotation = parseFloat(e.target.value) || 0;
    $("valSkyRot").textContent = `${Math.round(renderer.lighting.skyRotation)}°`;
  });
  $("rngSkyExp").addEventListener("input", (e) => {
    renderer.lighting.skyExposure = parseFloat(e.target.value) || 1.0;
    $("valSkyExp").textContent = renderer.lighting.skyExposure.toFixed(2);
  });
  $("rngSkyBlur").addEventListener("input", (e) => {
    renderer.lighting.skyBlur = parseFloat(e.target.value) || 0;
    $("valSkyBlur").textContent = `${Math.round(renderer.lighting.skyBlur * 100)}%`;
  });
  $("chkSkySyncAmb").addEventListener("change", (e) => {
    state.skySyncAmb = e.target.checked;
  });

  // Model part switcher
  document.querySelectorAll("#partSeg .seg-btn").forEach((b) => {
    b.addEventListener("click", () => switchModelPart(b.dataset.part));
  });

  // Lighting presets
  document.querySelectorAll(".preset-btn").forEach((b) => {
    b.addEventListener("click", () => applyLightingPreset(b.dataset.preset));
  });

  // Lighting sliders & colors
  const bindRange = (id, key, valId, fmt) => {
    $(id).addEventListener("input", (e) => {
      const v = parseFloat(e.target.value);
      renderer.lighting[key] = v;
      $(valId).textContent = fmt(v);
      document.querySelectorAll(".preset-btn").forEach((b) => b.classList.remove("active"));
    });
  };
  bindRange("rngAmbInt", "ambientIntensity", "valAmbInt", (v) => v.toFixed(2));
  bindRange("rngKeyInt", "keyIntensity", "valKeyInt", (v) => v.toFixed(2));
  bindRange("rngKeyAz", "keyAzimuth", "valKeyAz", (v) => `${Math.round(v)}°`);
  bindRange("rngKeyEl", "keyElevation", "valKeyEl", (v) => `${Math.round(v)}°`);
  bindRange("rngShadow", "shadowStrength", "valShadow", (v) => `${Math.round(v * 100)}%`);
  bindRange("rngFillInt", "fillIntensity", "valFillInt", (v) => v.toFixed(2));
  bindRange("rngRimInt", "rimIntensity", "valRimInt", (v) => v.toFixed(2));
  bindRange("rngExp", "exposure", "valExp", (v) => v.toFixed(2));
  bindRange("rngSat", "saturation", "valSat", (v) => v.toFixed(2));

  const bindColor = (id, key, onChange) => {
    $(id).addEventListener("input", (e) => {
      renderer.lighting[key] = e.target.value;
      if (onChange) onChange();
    });
  };
  bindColor("colSky", "skyColor");
  bindColor("colGround", "groundColor");
  bindColor("colKey", "keyColor");
  bindColor("colFill", "fillColor");
  bindColor("colRim", "rimColor");
  bindColor("colBgTop", "bgTop", applyStageBackground);
  bindColor("colBgBot", "bgBottom", applyStageBackground);

  document.querySelectorAll("#shadingSeg .seg-btn").forEach((b) => {
    b.addEventListener("click", () => {
      renderer.lighting.shadingMode = Number(b.dataset.shading);
      document.querySelectorAll("#shadingSeg .seg-btn").forEach((x) => {
        x.classList.toggle("active", x === b);
      });
    });
  });

  $("chkStage").addEventListener("change", (e) => {
    renderer.lighting.showStage = e.target.checked;
  });
  $("chkGrid").addEventListener("change", (e) => {
    renderer.lighting.showGrid = e.target.checked;
  });
  $("chkTransparent").addEventListener("change", (e) => {
    renderer.lighting.transparentBg = e.target.checked;
    applyStageBackground();
  });

  syncLightingUiFromState();
}

// ============================================================================
// Main Render Loop
// ============================================================================
let lastTs = performance.now();

function tick(now) {
  const dt = Math.min(0.05, Math.max(0, (now - lastTs) / 1000));
  lastTs = now;

  const anim = getActiveAnimObj();
  if (state.playing && anim) {
    const len = getAnimationLength(anim);
    state.animTime += dt * state.speed;
    if (len > 1e-6) {
      if (state.loop && anim.loop !== "hold_on_last_frame") {
        state.animTime = state.animTime % len;
      } else if (state.animTime >= len) {
        state.animTime = len;
      }
    }
    syncTimeControls();
  }
  state.parallelTime += dt * state.speed;

  let pose = anim ? evaluateAnimation(anim, state.animTime, state.headYaw, state.headPitch, state.loop) : {};

  // Overlay parallel0 gentle breeze layer when enabled and not already viewing parallel0
  const p0 = state.pack?.animations?.[state.activePart]?.parallel0;
  if (state.useParallel && p0 && state.activeAnim !== "parallel0" && state.activeAnim !== "__bind__") {
    const p0Pose = evaluateAnimation(p0, state.parallelTime, state.headYaw, state.headPitch, true);
    pose = mergePoses(pose, p0Pose);
  }

  const gizmoBone = state.activeTab === "bones" || renderer.lighting.showSkeleton ? state.selectedBone : null;
  renderer.render(
    pose,
    { yaw: state.headYaw, pitch: state.headPitch },
    dt,
    state.boneOverrides,
    gizmoBone
  );
  requestAnimationFrame(tick);
}

initUI();
loadDemoPack();
requestAnimationFrame(tick);
