/**
 * Universal YSM 2.6.0 / Bedrock 1.12.0 / Bedrock 1.8.0 / Blockbench .bbmodel parser.
 * Produces a unified runtime pack:
 *   {
 *     name, tips, sourceLabel,
 *     models: { main: ParsedGeo, arm?: ParsedGeo },
 *     textures: [ { name, image: HTMLImageElement, width, height } ],
 *     animations: { main: { [animName]: animObj }, arm?: { [animName]: animObj } }
 *   }
 */

function stripBom(str) {
  return str.charCodeAt(0) === 0xfeff ? str.slice(1) : str;
}

function parseJsonLoose(bytesOrText) {
  const text =
    typeof bytesOrText === "string"
      ? bytesOrText
      : new TextDecoder("utf-8").decode(bytesOrText);
  return JSON.parse(stripBom(text));
}

export function loadImageFromBytes(bytes, mime = "image/png") {
  return new Promise((resolve, reject) => {
    const blob = new Blob([bytes], { type: mime });
    const url = URL.createObjectURL(blob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = (err) => {
      URL.revokeObjectURL(url);
      reject(err);
    };
    img.src = url;
  });
}

export function loadImageFromDataUrl(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = dataUrl;
  });
}

/**
 * Convert standard Bedrock Box-UV [u, v] into per-face UV rectangles.
 */
function boxUvToPerFace(uvArr, size, mirror = false) {
  const u = Number(uvArr[0]) || 0;
  const v = Number(uvArr[1]) || 0;
  const dx = Math.floor(Math.abs(Number(size[0]) || 0));
  const dy = Math.floor(Math.abs(Number(size[1]) || 0));
  const dz = Math.floor(Math.abs(Number(size[2]) || 0));
  if (!mirror) {
    return {
      north: { uv: [u + dz, v + dz], uv_size: [dx, dy] },
      south: { uv: [u + dz + dx + dz, v + dz], uv_size: [dx, dy] },
      east: { uv: [u, v + dz], uv_size: [dz, dy] },
      west: { uv: [u + dz + dx, v + dz], uv_size: [dz, dy] },
      up: { uv: [u + dz + dx, v + dz], uv_size: [-dx, -dz] },
      down: { uv: [u + dz + dx + dx, v], uv_size: [-dx, dz] },
    };
  }
  return {
    north: { uv: [u + dz + dx, v + dz], uv_size: [-dx, dy] },
    south: { uv: [u + dz + dx + dz + dx, v + dz], uv_size: [-dx, dy] },
    west: { uv: [u + dz, v + dz], uv_size: [-dz, dy] },
    east: { uv: [u + dz + dx + dz, v + dz], uv_size: [-dz, dy] },
    up: { uv: [u + dz, v + dz], uv_size: [dx, -dz] },
    down: { uv: [u + dz + dx, v], uv_size: [dx, dz] },
  };
}

/**
 * Parse Bedrock 1.12.0 (`minecraft:geometry`) or legacy 1.8.0 (`geometry.*`) JSON.
 */
export function parseBedrockGeometry(json) {
  let g0 = null;
  let texW = 64;
  let texH = 64;

  if (Array.isArray(json["minecraft:geometry"]) && json["minecraft:geometry"].length > 0) {
    g0 = json["minecraft:geometry"][0];
    const desc = g0.description || {};
    texW = Number(desc.texture_width) || 64;
    texH = Number(desc.texture_height) || 64;
  } else {
    // Legacy Bedrock 1.8.0: { "geometry.xxx": { texturewidth, textureheight, bones } }
    for (const [k, v] of Object.entries(json)) {
      if (k.startsWith("geometry.") && v && typeof v === "object" && Array.isArray(v.bones)) {
        g0 = v;
        texW = Number(v.texturewidth ?? v.texture_width) || 64;
        texH = Number(v.textureheight ?? v.texture_height) || 64;
        break;
      }
    }
  }
  if (!g0 || !Array.isArray(g0.bones)) {
    throw new Error("未找到有效的 Bedrock 骨骼几何数据（minecraft:geometry）。");
  }

  let totalCubes = 0;
  const bones = g0.bones.map((b) => {
    const boneMirror = Boolean(b.mirror);
    const cubes = (b.cubes || []).map((c) => {
      totalCubes++;
      const origin = (c.origin || [0, 0, 0]).map(Number);
      const size = (c.size || [0, 0, 0]).map(Number);
      const inflate = Number(c.inflate) || 0;
      const rotation = c.rotation ? c.rotation.map(Number) : null;
      const pivot = c.pivot
        ? c.pivot.map(Number)
        : [origin[0] + size[0] * 0.5, origin[1] + size[1] * 0.5, origin[2] + size[2] * 0.5];
      const mirror = c.mirror != null ? Boolean(c.mirror) : boneMirror;

      let facesUv = {};
      if (Array.isArray(c.uv)) {
        facesUv = boxUvToPerFace(c.uv, size, mirror);
      } else if (c.uv && typeof c.uv === "object") {
        facesUv = c.uv;
      }

      return { origin, size, inflate, rotation, pivot, facesUv };
    });

    return {
      name: String(b.name || "bone"),
      parent: b.parent ? String(b.parent) : null,
      pivot: (b.pivot || [0, 0, 0]).map(Number),
      rotation: (b.rotation || [0, 0, 0]).map(Number),
      neverRender: Boolean(b.neverRender),
      cubes,
    };
  });

  return {
    textureWidth: texW,
    textureHeight: texH,
    bones,
    boneCount: bones.length,
    cubeCount: totalCubes,
  };
}

/**
 * Parse a Blockbench .bbmodel JSON directly into our unified runtime pack.
 */
export async function parseBBModel(json, fileName = "model.bbmodel") {
  const res = json.resolution || { width: 64, height: 64 };
  const texW = Number(res.width) || 64;
  const texH = Number(res.height) || 64;

  const elemMap = new Map();
  for (const el of json.elements || []) {
    if (el && el.uuid) elemMap.set(el.uuid, el);
  }

  const bones = [];
  let totalCubes = 0;

  function bbCubeToBedrock(el) {
    const from = (el.from || [0, 0, 0]).map(Number);
    const to = (el.to || [0, 0, 0]).map(Number);
    const sx = to[0] - from[0];
    const sy = to[1] - from[1];
    const sz = to[2] - from[2];
    // Blockbench right-handed X -> Bedrock X = -(from[0] + sx) = -to[0]
    const origin = [-to[0], from[1], from[2]];
    const size = [sx, sy, sz];
    const inflate = Number(el.inflate) || 0;
    const orig = (el.origin || [0, 0, 0]).map(Number);
    const pivot = [-orig[0], orig[1], orig[2]];
    const rot = el.rotation
      ? [-Number(el.rotation[0] || 0), -Number(el.rotation[1] || 0), Number(el.rotation[2] || 0)]
      : null;

    const facesUv = {};
    if (el.faces && typeof el.faces === "object") {
      for (const fname of ["north", "south", "east", "west", "up", "down"]) {
        const f = el.faces[fname];
        if (f && Array.isArray(f.uv) && f.uv.length === 4) {
          const [u1, v1, u2, v2] = f.uv.map(Number);
          // Blockbench east/west map across X flip: BB east (+X) -> Bedrock west, BB west (-X) -> Bedrock east
          const targetFace = fname === "east" ? "east" : fname === "west" ? "west" : fname;
          facesUv[targetFace] = { uv: [u1, v1], uv_size: [u2 - u1, v2 - v1] };
        }
      }
    }
    totalCubes++;
    return { origin, size, inflate, rotation: rot, pivot, facesUv };
  }

  function walkOutliner(nodes, parentName) {
    const looseCubes = [];
    for (const node of nodes || []) {
      if (typeof node === "string") {
        const el = elemMap.get(node);
        if (el) looseCubes.push(bbCubeToBedrock(el));
      } else if (node && typeof node === "object") {
        const name = String(node.name || "group");
        const orig = (node.origin || [0, 0, 0]).map(Number);
        const pivot = [-orig[0], orig[1], orig[2]];
        const rot = node.rotation
          ? [-Number(node.rotation[0] || 0), -Number(node.rotation[1] || 0), Number(node.rotation[2] || 0)]
          : [0, 0, 0];
        const boneObj = {
          name,
          parent: parentName,
          pivot,
          rotation: rot,
          neverRender: node.visibility === false,
          cubes: [],
        };
        bones.push(boneObj);
        const childCubes = walkOutliner(node.children || [], name);
        boneObj.cubes.push(...childCubes);
      }
    }
    return looseCubes;
  }

  const rootCubes = walkOutliner(json.outliner || [], null);
  if (rootCubes.length > 0) {
    bones.unshift({
      name: "root",
      parent: null,
      pivot: [0, 0, 0],
      rotation: [0, 0, 0],
      neverRender: false,
      cubes: rootCubes,
    });
  }

  // Extract embedded textures
  const textures = [];
  for (const tex of json.textures || []) {
    if (tex && typeof tex.source === "string" && tex.source.startsWith("data:")) {
      const img = await loadImageFromDataUrl(tex.source);
      textures.push({
        name: tex.name || `texture_${textures.length + 1}.png`,
        image: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
      });
    }
  }

  // Extract animations if present
  const mainAnims = {};
  for (const a of json.animations || []) {
    if (!a || !a.name) continue;
    const animBones = {};
    for (const anim of Object.values(a.animators || {})) {
      if (!anim || !anim.name) continue;
      const tracks = {};
      for (const kf of anim.keyframes || []) {
        const ch = kf.channel;
        if (!["rotation", "position", "scale"].includes(ch)) continue;
        if (!tracks[ch]) tracks[ch] = {};
        const dp = kf.data_points?.[0] || { x: 0, y: 0, z: 0 };
        tracks[ch][String(kf.time ?? 0)] = [dp.x ?? 0, dp.y ?? 0, dp.z ?? 0];
      }
      if (Object.keys(tracks).length) animBones[anim.name] = tracks;
    }
    mainAnims[a.name] = {
      loop: a.loop === "loop" ? true : a.loop === "hold" ? "hold_on_last_frame" : false,
      animation_length: Number(a.length) || 1.0,
      bones: animBones,
    };
  }

  return {
    name: json.name || fileName.replace(/\.bbmodel$/i, ""),
    tips: `从 Blockbench 工程 ${fileName} 导入`,
    sourceLabel: fileName,
    models: {
      main: {
        textureWidth: texW,
        textureHeight: texH,
        bones,
        boneCount: bones.length,
        cubeCount: totalCubes,
      },
    },
    textures,
    animations: { main: mainAnims },
  };
}

/**
 * Helper to look up a relative path inside a file map regardless of top-level wrapper directory.
 */
function findFileInMap(fileMap, relPath, prefix = "") {
  const cleanRel = relPath.replace(/^\.?\//, "").replace(/\\/g, "/");
  const exact = prefix ? `${prefix}${cleanRel}` : cleanRel;
  if (fileMap.has(exact)) return { key: exact, bytes: fileMap.get(exact) };
  if (fileMap.has(cleanRel)) return { key: cleanRel, bytes: fileMap.get(cleanRel) };
  const lowerTarget = cleanRel.toLowerCase();
  for (const [k, v] of fileMap.entries()) {
    const kl = k.toLowerCase();
    if (kl === lowerTarget || kl.endsWith("/" + lowerTarget)) {
      return { key: k, bytes: v };
    }
  }
  return null;
}

/**
 * Parse a complete YSM 2.6.0 / 1.x model pack from a Map<path, Uint8Array>.
 */
export async function parseYsmFileMap(fileMap, sourceLabel = "YSM 模型包") {
  // Check for single .bbmodel inside map
  for (const [k, bytes] of fileMap.entries()) {
    if (k.toLowerCase().endsWith(".bbmodel")) {
      return parseBBModel(parseJsonLoose(bytes), k.split("/").pop());
    }
  }

  // Locate ysm.json (if present)
  let ysmEntry = null;
  let prefix = "";
  for (const [k, bytes] of fileMap.entries()) {
    if (k.toLowerCase() === "ysm.json" || k.toLowerCase().endsWith("/ysm.json")) {
      ysmEntry = { key: k, data: parseJsonLoose(bytes) };
      const idx = k.lastIndexOf("/");
      prefix = idx >= 0 ? k.slice(0, idx + 1) : "";
      break;
    }
  }

  let modelName = sourceLabel.replace(/\.(zip|ysm)$/i, "");
  let tips = "";
  let mainModelPath = null;
  let armModelPath = null;
  let mainAnimPath = null;
  let armAnimPath = null;
  let texturePaths = [];

  if (ysmEntry) {
    const ysm = ysmEntry.data;
    if (ysm.metadata?.name) modelName = ysm.metadata.name;
    if (ysm.metadata?.tips) tips = ysm.metadata.tips;
    const playerFiles = ysm.files?.player || ysm.player || {};
    if (typeof playerFiles.model === "object" && playerFiles.model) {
      mainModelPath = playerFiles.model.main || null;
      armModelPath = playerFiles.model.arm || null;
    }
    if (typeof playerFiles.animation === "object" && playerFiles.animation) {
      mainAnimPath = playerFiles.animation.main || null;
      armAnimPath = playerFiles.animation.arm || null;
    }
    if (Array.isArray(playerFiles.texture)) {
      for (const t of playerFiles.texture) {
        if (typeof t === "string") texturePaths.push(t);
        else if (t && typeof t === "object" && t.uv) texturePaths.push(t.uv);
      }
    }
  }

  // Auto-discover files when ysm.json is absent or incomplete
  const allKeys = [...fileMap.keys()];
  if (!mainModelPath) {
    mainModelPath =
      allKeys.find((k) => /main\.json$/i.test(k)) ||
      allKeys.find((k) => /\.geo\.json$/i.test(k)) ||
      allKeys.find((k) => /\.json$/i.test(k) && !/animation|ysm\.json|lang\//i.test(k));
  }
  if (!armModelPath) {
    armModelPath = allKeys.find((k) => /arm\.json$/i.test(k)) || null;
  }
  if (!mainAnimPath) {
    mainAnimPath =
      allKeys.find((k) => /main\.animation\.json$/i.test(k)) ||
      allKeys.find((k) => /\.animation\.json$/i.test(k) && !/arm\.animation\.json$/i.test(k)) ||
      null;
  }
  if (!armAnimPath) {
    armAnimPath = allKeys.find((k) => /arm\.animation\.json$/i.test(k)) || null;
  }

  // Collect all PNG textures (prioritizing ysm.json order)
  const seenTexKeys = new Set();
  const textures = [];
  for (const tp of texturePaths) {
    const found = findFileInMap(fileMap, tp, prefix);
    if (found && !seenTexKeys.has(found.key)) {
      seenTexKeys.add(found.key);
      const img = await loadImageFromBytes(found.bytes, "image/png");
      textures.push({
        name: found.key.split("/").pop(),
        image: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
      });
    }
  }
  for (const k of allKeys) {
    if (k.toLowerCase().endsWith(".png") && !seenTexKeys.has(k)) {
      seenTexKeys.add(k);
      const img = await loadImageFromBytes(fileMap.get(k), "image/png");
      textures.push({
        name: k.split("/").pop(),
        image: img,
        width: img.naturalWidth || img.width,
        height: img.naturalHeight || img.height,
      });
    }
  }

  if (!mainModelPath) {
    throw new Error("未在导入文件中找到模型几何 JSON（如 models/main.json）。");
  }

  const mainModelEntry = findFileInMap(fileMap, mainModelPath, prefix);
  if (!mainModelEntry) {
    throw new Error(`找不到主模型文件：${mainModelPath}`);
  }
  const models = {
    main: parseBedrockGeometry(parseJsonLoose(mainModelEntry.bytes)),
  };

  if (armModelPath) {
    const armEntry = findFileInMap(fileMap, armModelPath, prefix);
    if (armEntry) {
      try {
        models.arm = parseBedrockGeometry(parseJsonLoose(armEntry.bytes));
      } catch (e) {
        console.warn("Skipping arm model:", e);
      }
    }
  }

  const animations = { main: {} };
  if (mainAnimPath) {
    const animEntry = findFileInMap(fileMap, mainAnimPath, prefix);
    if (animEntry) {
      const parsed = parseJsonLoose(animEntry.bytes);
      animations.main = parsed.animations || {};
    }
  }
  if (armAnimPath) {
    const armAnimEntry = findFileInMap(fileMap, armAnimPath, prefix);
    if (armAnimEntry) {
      try {
        const parsed = parseJsonLoose(armAnimEntry.bytes);
        animations.arm = parsed.animations || {};
      } catch (e) {
        console.warn("Skipping arm animations:", e);
      }
    }
  }

  // If no PNG was imported, generate a crisp fallback checkerboard texture
  if (textures.length === 0) {
    const canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 64;
    const ctx = canvas.getContext("2d");
    for (let y = 0; y < 64; y += 8) {
      for (let x = 0; x < 64; x += 8) {
        ctx.fillStyle = ((x + y) / 8) % 2 === 0 ? "#d7dcf2" : "#aeb9df";
        ctx.fillRect(x, y, 8, 8);
      }
    }
    const img = await loadImageFromDataUrl(canvas.toDataURL("image/png"));
    textures.push({ name: "fallback_checker.png", image: img, width: 64, height: 64 });
  }

  return {
    name: modelName,
    tips,
    sourceLabel,
    models,
    textures,
    animations,
  };
}
