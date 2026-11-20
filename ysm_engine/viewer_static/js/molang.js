/**
 * Bedrock / YSM Molang expression & keyframe animation evaluator.
 * Matches ysm_engine/renderer.py semantics (degree-based trig, catmullrom & linear keyframes).
 */

const DEG2RAD = Math.PI / 180;
const exprCache = new Map();

const MOLANG_ENV = {
  _sin: (d) => Math.sin(d * DEG2RAD),
  _cos: (d) => Math.cos(d * DEG2RAD),
  _tan: (d) => Math.tan(d * DEG2RAD),
  _asin: (v) => Math.asin(Math.max(-1, Math.min(1, v))) / DEG2RAD,
  _acos: (v) => Math.acos(Math.max(-1, Math.min(1, v))) / DEG2RAD,
  _atan: (v) => Math.atan(v) / DEG2RAD,
  _atan2: (y, x) => Math.atan2(y, x) / DEG2RAD,
  _abs: Math.abs,
  _clamp: (x, lo, hi) => Math.max(lo, Math.min(hi, x)),
  _min: Math.min,
  _max: Math.max,
  _floor: Math.floor,
  _ceil: Math.ceil,
  _round: Math.round,
  _sqrt: (v) => Math.sqrt(Math.max(0, v)),
  _pow: Math.pow,
  _mod: (a, b) => (b === 0 ? 0 : a % b),
  _lerp: (a, b, t) => a + (b - a) * t,
  _pi: Math.PI,
};

function compileMolang(rawExpr) {
  if (exprCache.has(rawExpr)) return exprCache.get(rawExpr);

  let js = String(rawExpr).trim();
  if (!js) {
    const zero = () => 0;
    exprCache.set(rawExpr, zero);
    return zero;
  }
  // Normalize Molang identifiers to JS helpers
  js = js
    .replace(/\b(?:query|q)\.anim_time\b/gi, "t")
    .replace(/\b(?:query|q)\.life_time\b/gi, "t")
    .replace(/\b(?:query|q)\.modified_distance_moved\b/gi, "(t * 4.5)")
    .replace(/\b(?:query|q)\.modified_move_speed\b/gi, "1.0")
    .replace(/\b(?:query|q)\.ground_speed\b/gi, "4.3")
    .replace(/\b(?:query|q)\.head_x_rotation\b/gi, "headPitch")
    .replace(/\b(?:query|q)\.head_y_rotation\b/gi, "headYaw")
    .replace(/\b(?:query|q)\.is_on_ground\b/gi, "1")
    .replace(/\b(?:query|q)\.is_in_water\b/gi, "0")
    .replace(/\b(?:query|q)\.is_sneaking\b/gi, "0")
    .replace(/\b(?:query|q)\.[a-z0-9_]+\b/gi, "0")
    .replace(/\b(?:variable|v)\.[a-z0-9_]+\b/gi, "0")
    .replace(/\bmath\.sin\b/gi, "E._sin")
    .replace(/\bmath\.cos\b/gi, "E._cos")
    .replace(/\bmath\.tan\b/gi, "E._tan")
    .replace(/\bmath\.asin\b/gi, "E._asin")
    .replace(/\bmath\.acos\b/gi, "E._acos")
    .replace(/\bmath\.atan2\b/gi, "E._atan2")
    .replace(/\bmath\.atan\b/gi, "E._atan")
    .replace(/\bmath\.abs\b/gi, "E._abs")
    .replace(/\bmath\.clamp\b/gi, "E._clamp")
    .replace(/\bmath\.min\b/gi, "E._min")
    .replace(/\bmath\.max\b/gi, "E._max")
    .replace(/\bmath\.floor\b/gi, "E._floor")
    .replace(/\bmath\.ceil\b/gi, "E._ceil")
    .replace(/\bmath\.round\b/gi, "E._round")
    .replace(/\bmath\.sqrt\b/gi, "E._sqrt")
    .replace(/\bmath\.pow\b/gi, "E._pow")
    .replace(/\bmath\.mod\b/gi, "E._mod")
    .replace(/\bmath\.lerp\b/gi, "E._lerp")
    .replace(/\bmath\.pi\b/gi, "E._pi");

  // Basic safety filter: allow only math/expression characters
  if (/[^0-9a-zA-Z_.\s+\-*/%(),?:!<>=&|]/.test(js)) {
    const zero = () => 0;
    exprCache.set(rawExpr, zero);
    return zero;
  }

  let fn;
  try {
    // eslint-disable-next-line no-new-func
    fn = new Function("t", "E", "headYaw", "headPitch", `"use strict"; return Number(${js}) || 0;`);
  } catch {
    fn = () => 0;
  }
  exprCache.set(rawExpr, fn);
  return fn;
}

export function evalMolang(val, t, headYaw = 0, headPitch = 0) {
  if (typeof val === "number") return Number.isFinite(val) ? val : 0;
  if (typeof val === "string") {
    const n = Number(val);
    if (!Number.isNaN(n) && val.trim() !== "") return n;
    try {
      const r = compileMolang(val)(t, MOLANG_ENV, headYaw, headPitch);
      return Number.isFinite(r) ? r : 0;
    } catch {
      return 0;
    }
  }
  return 0;
}

function evalVec3(raw, t, def, headYaw, headPitch) {
  if (raw == null) return [def[0], def[1], def[2]];
  if (typeof raw === "number" || typeof raw === "string") {
    const v = evalMolang(raw, t, headYaw, headPitch);
    return [v, v, v];
  }
  if (Array.isArray(raw)) {
    return [
      evalMolang(raw[0] ?? def[0], t, headYaw, headPitch),
      evalMolang(raw[1] ?? def[1], t, headYaw, headPitch),
      evalMolang(raw[2] ?? def[2], t, headYaw, headPitch),
    ];
  }
  if (typeof raw === "object") {
    if ("vector" in raw) return evalVec3(raw.vector, t, def, headYaw, headPitch);
    if ("post" in raw) return evalVec3(raw.post, t, def, headYaw, headPitch);

    // Keyframe map { "0.0": ..., "0.25": ... }
    const kfs = [];
    for (const [k, v] of Object.entries(raw)) {
      const kt = parseFloat(k);
      if (!Number.isNaN(kt)) kfs.push([kt, v]);
    }
    if (!kfs.length) return [def[0], def[1], def[2]];
    kfs.sort((a, b) => a[0] - b[0]);

    if (t <= kfs[0][0]) {
      const v0 = kfs[0][1];
      return evalVec3(v0 && typeof v0 === "object" && "post" in v0 ? v0.post : v0, t, def, headYaw, headPitch);
    }
    if (t >= kfs[kfs.length - 1][0]) {
      const vl = kfs[kfs.length - 1][1];
      return evalVec3(vl && typeof vl === "object" && "post" in vl ? vl.post : vl, t, def, headYaw, headPitch);
    }

    for (let i = 0; i < kfs.length - 1; i++) {
      const [t0, v0] = kfs[i];
      const [t1, v1] = kfs[i + 1];
      if (t >= t0 && t <= t1) {
        const p0 = evalVec3(v0 && typeof v0 === "object" && "post" in v0 ? v0.post : v0, t, def, headYaw, headPitch);
        const p1 = evalVec3(v1 && typeof v1 === "object" && "pre" in v1 ? v1.pre : v1, t, def, headYaw, headPitch);
        const dt = Math.max(1e-6, t1 - t0);
        let u = (t - t0) / dt;
        if (v0 && typeof v0 === "object" && v0.lerp_mode === "catmullrom") {
          u = u * u * (3 - 2 * u);
        }
        return [
          p0[0] + (p1[0] - p0[0]) * u,
          p0[1] + (p1[1] - p0[1]) * u,
          p0[2] + (p1[2] - p0[2]) * u,
        ];
      }
    }
  }
  return [def[0], def[1], def[2]];
}

export function getAnimationLength(anim) {
  if (!anim) return 1.0;
  if (typeof anim.animation_length === "number" && anim.animation_length > 0) {
    return anim.animation_length;
  }
  let maxT = 0;
  const bones = anim.bones || {};
  for (const track of Object.values(bones)) {
    if (!track || typeof track !== "object") continue;
    for (const ch of ["rotation", "position", "scale"]) {
      const raw = track[ch];
      if (raw && typeof raw === "object" && !Array.isArray(raw)) {
        for (const k of Object.keys(raw)) {
          const kt = parseFloat(k);
          if (!Number.isNaN(kt) && kt > maxT) maxT = kt;
        }
      }
    }
  }
  return maxT > 0 ? maxT : 2.0;
}

export function evaluateAnimation(anim, rawTime, headYaw = 0, headPitch = 0, forceLoop = true) {
  if (!anim || !anim.bones) return {};
  const len = getAnimationLength(anim);
  let t = rawTime;
  const loopMode = anim.loop;

  if (len > 1e-6) {
    if (loopMode === true || (forceLoop && loopMode !== "hold_on_last_frame")) {
      t = ((t % len) + len) % len;
    } else if (loopMode === "hold_on_last_frame") {
      t = Math.min(Math.max(0, t), len);
    } else {
      t = Math.min(Math.max(0, t), len);
    }
  }

  const out = {};
  for (const [bname, tracks] of Object.entries(anim.bones)) {
    if (!tracks || typeof tracks !== "object") continue;
    out[bname] = {
      rotation: evalVec3(tracks.rotation, t, [0, 0, 0], headYaw, headPitch),
      position: evalVec3(tracks.position, t, [0, 0, 0], headYaw, headPitch),
      scale: evalVec3(tracks.scale, t, [1, 1, 1], headYaw, headPitch),
    };
  }
  return out;
}

export function mergePoses(basePose, overlayPose) {
  const merged = {};
  for (const [b, p] of Object.entries(basePose || {})) {
    merged[b] = {
      rotation: [...p.rotation],
      position: [...p.position],
      scale: [...p.scale],
    };
  }
  for (const [b, p] of Object.entries(overlayPose || {})) {
    if (!merged[b]) {
      merged[b] = {
        rotation: [...p.rotation],
        position: [...p.position],
        scale: [...p.scale],
      };
    } else {
      merged[b].rotation[0] += p.rotation[0];
      merged[b].rotation[1] += p.rotation[1];
      merged[b].rotation[2] += p.rotation[2];
      merged[b].position[0] += p.position[0];
      merged[b].position[1] += p.position[1];
      merged[b].position[2] += p.position[2];
      merged[b].scale[0] *= p.scale[0];
      merged[b].scale[1] *= p.scale[1];
      merged[b].scale[2] *= p.scale[2];
    }
  }
  return merged;
}
