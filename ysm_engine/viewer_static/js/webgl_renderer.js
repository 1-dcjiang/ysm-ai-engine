/**
 * Pure WebGL2 3D Studio Renderer for YSM 2.6.0 / Bedrock 1.12.0 Models.
 * Features:
 *   - Exact Bedrock <-> Right-Handed transform parity with ysm_engine/renderer.py
 *   - Crisp Minecraft NEAREST pixel-art texture sampling + alpha cutout
 *   - Real-time 2048x2048 PCF soft shadow map (stage + self-shadowing)
 *   - Hemisphere Ambient + Key Directional + Soft Fill + Fresnel Rim Backlight
 *   - Studio / Toon / Unlit shading modes + Exposure & Saturation controls
 *   - Smooth Orbit/Pan/Zoom camera (Perspective & Orthographic) + Turntable + Skeleton Overlay
 */

const DEG2RAD = Math.PI / 180;

// ============================================================================
// Column-major 4x4 Matrix Math (OpenGL / WebGL convention: v' = M * v)
// ============================================================================
function mat4Identity() {
  const m = new Float32Array(16);
  m[0] = m[5] = m[10] = m[15] = 1;
  return m;
}

function mat4Mul(a, b, out = new Float32Array(16)) {
  for (let c = 0; c < 4; c++) {
    const b0 = b[c * 4 + 0];
    const b1 = b[c * 4 + 1];
    const b2 = b[c * 4 + 2];
    const b3 = b[c * 4 + 3];
    out[c * 4 + 0] = a[0] * b0 + a[4] * b1 + a[8] * b2 + a[12] * b3;
    out[c * 4 + 1] = a[1] * b0 + a[5] * b1 + a[9] * b2 + a[13] * b3;
    out[c * 4 + 2] = a[2] * b0 + a[6] * b1 + a[10] * b2 + a[14] * b3;
    out[c * 4 + 3] = a[3] * b0 + a[7] * b1 + a[11] * b2 + a[15] * b3;
  }
  return out;
}

function mat3FromBedrockRot(rxDeg, ryDeg, rzDeg) {
  // Exact match to renderer.py: R = Rz(+rz) * Ry(-ry) * Rx(-rx)
  const ax = -rxDeg * DEG2RAD;
  const ay = -ryDeg * DEG2RAD;
  const az = rzDeg * DEG2RAD;
  const cx = Math.cos(ax), sx = Math.sin(ax);
  const cy = Math.cos(ay), sy = Math.sin(ay);
  const cz = Math.cos(az), sz = Math.sin(az);

  // Rz * Ry * Rx (row-major elements r_ij)
  const r00 = cz * cy;
  const r01 = cz * sy * sx - sz * cx;
  const r02 = cz * sy * cx + sz * sx;

  const r10 = sz * cy;
  const r11 = sz * sy * sx + cz * cx;
  const r12 = sz * sy * cx - cz * sx;

  const r20 = -sy;
  const r21 = cy * sx;
  const r22 = cy * cx;

  return [r00, r01, r02, r10, r11, r12, r20, r21, r22];
}

function mat4BoneLocal(pivRh, rotDeg, posRh, scale) {
  const [r00, r01, r02, r10, r11, r12, r20, r21, r22] = mat3FromBedrockRot(
    rotDeg[0],
    rotDeg[1],
    rotDeg[2]
  );
  const sx = scale[0], sy = scale[1], sz = scale[2];
  // RS = R * diag(sx, sy, sz)
  const m00 = r00 * sx, m01 = r01 * sy, m02 = r02 * sz;
  const m10 = r10 * sx, m11 = r11 * sy, m12 = r12 * sz;
  const m20 = r20 * sx, m21 = r21 * sy, m22 = r22 * sz;

  const px = pivRh[0], py = pivRh[1], pz = pivRh[2];
  const tx = px + posRh[0] - (m00 * px + m01 * py + m02 * pz);
  const ty = py + posRh[1] - (m10 * px + m11 * py + m12 * pz);
  const tz = pz + posRh[2] - (m20 * px + m21 * py + m22 * pz);

  const m = new Float32Array(16);
  // Column 0
  m[0] = m00; m[1] = m10; m[2] = m20; m[3] = 0;
  // Column 1
  m[4] = m01; m[5] = m11; m[6] = m21; m[7] = 0;
  // Column 2
  m[8] = m02; m[9] = m12; m[10] = m22; m[11] = 0;
  // Column 3
  m[12] = tx; m[13] = ty; m[14] = tz; m[15] = 1;
  return m;
}

function transformPoint(m, p) {
  return [
    m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12],
    m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13],
    m[2] * p[0] + m[6] * p[1] + m[10] * p[2] + m[14],
  ];
}

function mat4Perspective(fovDeg, aspect, near, far) {
  const f = 1.0 / Math.tan((fovDeg * DEG2RAD) / 2);
  const nf = 1 / (near - far);
  const m = new Float32Array(16);
  m[0] = f / aspect;
  m[5] = f;
  m[10] = (far + near) * nf;
  m[11] = -1;
  m[14] = 2 * far * near * nf;
  return m;
}

function mat4Ortho(left, right, bottom, top, near, far) {
  const m = new Float32Array(16);
  const lr = 1 / (left - right);
  const bt = 1 / (bottom - top);
  const nf = 1 / (near - far);
  m[0] = -2 * lr;
  m[5] = -2 * bt;
  m[10] = 2 * nf;
  m[12] = (left + right) * lr;
  m[13] = (top + bottom) * bt;
  m[14] = (far + near) * nf;
  m[15] = 1;
  return m;
}

function mat4LookAt(eye, target, up = [0, 1, 0]) {
  let zx = eye[0] - target[0];
  let zy = eye[1] - target[1];
  let zz = eye[2] - target[2];
  let len = Math.hypot(zx, zy, zz) || 1;
  zx /= len; zy /= len; zz /= len;

  let xx = up[1] * zz - up[2] * zy;
  let xy = up[2] * zx - up[0] * zz;
  let xz = up[0] * zy - up[1] * zx;
  len = Math.hypot(xx, xy, xz);
  if (len < 1e-6) {
    xx = 1; xy = 0; xz = 0;
  } else {
    xx /= len; xy /= len; xz /= len;
  }

  const yx = zy * xz - zz * xy;
  const yy = zz * xx - zx * xz;
  const yz = zx * xy - zy * xx;

  const m = new Float32Array(16);
  m[0] = xx; m[1] = yx; m[2] = zx; m[3] = 0;
  m[4] = xy; m[5] = yy; m[6] = zy; m[7] = 0;
  m[8] = xz; m[9] = yz; m[10] = zz; m[11] = 0;
  m[12] = -(xx * eye[0] + xy * eye[1] + xz * eye[2]);
  m[13] = -(yx * eye[0] + yy * eye[1] + yz * eye[2]);
  m[14] = -(zx * eye[0] + zy * eye[1] + zz * eye[2]);
  m[15] = 1;
  return m;
}

function hexToRgb01(hex) {
  const s = String(hex || "#ffffff").replace("#", "");
  const n = parseInt(s.length === 3 ? s.split("").map((c) => c + c).join("") : s, 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

// ============================================================================
// GLSL Shaders (WebGL2 GLSL ES 3.00)
// ============================================================================
const SHADOW_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec3 aPos;
layout(location = 2) in vec2 aUv;
uniform mat4 uLightVP;
uniform mat4 uBoneMat;
out vec2 vUv;
void main() {
  vUv = aUv;
  gl_Position = uLightVP * uBoneMat * vec4(aPos, 1.0);
}
`;

const SHADOW_FS = `#version 300 es
precision highp float;
in vec2 vUv;
uniform sampler2D uTex;
void main() {
  if (texture(uTex, vUv).a < 0.15) discard;
}
`;

const MODEL_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNorm;
layout(location = 2) in vec2 aUv;

uniform mat4 uVP;
uniform mat4 uLightVP;
uniform mat4 uBoneMat;

out vec3 vWorldPos;
out vec3 vWorldNorm;
out vec2 vUv;
out vec4 vLightPos;

void main() {
  vec4 wp = uBoneMat * vec4(aPos, 1.0);
  vWorldPos = wp.xyz;
  vWorldNorm = normalize(mat3(uBoneMat) * aNorm);
  vUv = aUv;
  vLightPos = uLightVP * wp;
  gl_Position = uVP * wp;
}
`;

const MODEL_FS = `#version 300 es
precision highp float;
in vec3 vWorldPos;
in vec3 vWorldNorm;
in vec2 vUv;
in vec4 vLightPos;

uniform sampler2D uTex;
uniform sampler2D uShadowMap;
uniform vec3 uCamPos;

uniform vec3 uSkyColor;
uniform vec3 uGroundColor;
uniform float uAmbientIntensity;

uniform vec3 uKeyDir;
uniform vec3 uKeyColor;
uniform float uKeyIntensity;
uniform float uShadowStrength;

uniform vec3 uFillDir;
uniform vec3 uFillColor;
uniform float uFillIntensity;

uniform vec3 uRimColor;
uniform float uRimIntensity;
uniform float uRimPower;

uniform int uShadingMode; // 0: Studio Smooth, 1: Anime Toon, 2: Unlit Flat
uniform float uExposure;
uniform float uSaturation;

out vec4 fragColor;

float calcShadow(vec4 lp, vec3 N, vec3 L) {
  vec3 proj = lp.xyz / lp.w;
  proj = proj * 0.5 + 0.5;
  if (proj.x < 0.0 || proj.x > 1.0 || proj.y < 0.0 || proj.y > 1.0 || proj.z > 1.0) {
    return 1.0;
  }
  float bias = max(0.0022 * (1.0 - max(dot(N, L), 0.0)), 0.0008);
  vec2 texel = 1.0 / vec2(textureSize(uShadowMap, 0));
  float lit = 0.0;
  for (int x = -1; x <= 1; x++) {
    for (int y = -1; y <= 1; y++) {
      float d = texture(uShadowMap, proj.xy + vec2(x, y) * texel * 1.4).r;
      lit += (proj.z - bias <= d) ? 1.0 : 0.0;
    }
  }
  lit /= 9.0;
  return mix(1.0 - uShadowStrength * 0.65, 1.0, lit);
}

void main() {
  vec4 texel = texture(uTex, vUv);
  if (texel.a < 0.12) discard;

  vec3 albedo = texel.rgb;
  vec3 N = normalize(vWorldNorm);
  if (!gl_FrontFacing) N = -N;
  vec3 V = normalize(uCamPos - vWorldPos);
  vec3 L = normalize(uKeyDir);
  vec3 F = normalize(uFillDir);

  vec3 color;
  if (uShadingMode == 2) {
    // Unlit flat pure texture mode
    color = albedo;
  } else {
    // Hemisphere ambient lighting (Sky + Ground bounce)
    float hemi = clamp(N.y * 0.5 + 0.5, 0.0, 1.0);
    vec3 ambient = mix(uGroundColor, uSkyColor, hemi) * uAmbientIntensity;

    float ndl = dot(N, L);
    float shadow = calcShadow(vLightPos, N, L);

    float keyDiff;
    if (uShadingMode == 1) {
      // Soft Anime Toon 2-band step
      float halfLambert = ndl * 0.5 + 0.5;
      keyDiff = mix(0.28, 1.0, smoothstep(0.42, 0.56, halfLambert * shadow));
    } else {
      // Half-Lambert wrap diffuse for flattering voxel shading
      float wrap = clamp((ndl + 0.35) / 1.35, 0.0, 1.0);
      keyDiff = wrap * shadow;
    }

    float fillDiff = clamp(dot(N, F) * 0.5 + 0.5, 0.0, 1.0);
    float rim = pow(1.0 - max(dot(N, V), 0.0), uRimPower) * (0.4 + 0.6 * max(dot(N, L) * 0.5 + 0.5, 0.0));

    vec3 lightSum = ambient + uKeyColor * (uKeyIntensity * keyDiff) + uFillColor * (uFillIntensity * fillDiff);
    color = albedo * lightSum + uRimColor * (rim * uRimIntensity * 0.55);
  }

  // Exposure & Saturation grading
  color *= uExposure;
  float luma = dot(color, vec3(0.299, 0.587, 0.114));
  color = mix(vec3(luma), color, uSaturation);
  // Gentle soft highlight roll-off (prevents harsh clipping on bright snow-white hair)
  color = color / (1.0 + max(color - 0.85, 0.0) * 0.35);

  fragColor = vec4(clamp(color, 0.0, 1.0), texel.a);
}
`;

const STAGE_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec3 aPos;
uniform mat4 uVP;
uniform mat4 uLightVP;
out vec3 vWorldPos;
out vec4 vLightPos;
void main() {
  vWorldPos = aPos;
  vLightPos = uLightVP * vec4(aPos, 1.0);
  gl_Position = uVP * vec4(aPos, 1.0);
}
`;

const STAGE_FS = `#version 300 es
precision highp float;
in vec3 vWorldPos;
in vec4 vLightPos;
uniform sampler2D uShadowMap;
uniform vec3 uStageColor;
uniform vec3 uGridColor;
uniform float uShowGrid;
uniform float uShadowStrength;
out vec4 fragColor;

void main() {
  float dist = length(vWorldPos.xz);
  float discAlpha = 1.0 - smoothstep(14.0, 28.0, dist);
  if (discAlpha < 0.005) discard;

  // PCF 5x5 soft shadow on floor
  vec3 proj = vLightPos.xyz / vLightPos.w;
  proj = proj * 0.5 + 0.5;
  float lit = 1.0;
  if (proj.x >= 0.0 && proj.x <= 1.0 && proj.y >= 0.0 && proj.y <= 1.0 && proj.z <= 1.0) {
    vec2 texel = 1.0 / vec2(textureSize(uShadowMap, 0));
    float sum = 0.0;
    for (int x = -2; x <= 2; x++) {
      for (int y = -2; y <= 2; y++) {
        float d = texture(uShadowMap, proj.xy + vec2(x, y) * texel * 1.8).r;
        sum += (proj.z - 0.0015 <= d) ? 1.0 : 0.0;
      }
    }
    lit = sum / 25.0;
  }

  // Subtle voxel grid lines (4u spacing)
  float gridLine = 0.0;
  if (uShowGrid > 0.5) {
    vec2 g = abs(fract(vWorldPos.xz / 4.0 - 0.5) - 0.5) / fwidth(vWorldPos.xz / 4.0);
    float line = 1.0 - min(min(g.x, g.y), 1.0);
    gridLine = line * 0.28 * (1.0 - smoothstep(10.0, 24.0, dist));
  }

  // Soft pedestal ring around character feet
  float ring = (1.0 - smoothstep(0.0, 0.22, abs(dist - 9.5))) * 0.22;

  float shadowDarken = mix(1.0 - uShadowStrength * 0.42, 1.0, lit);
  vec3 col = mix(uStageColor, uGridColor, max(gridLine, ring)) * shadowDarken;
  float alpha = discAlpha * (0.42 + (1.0 - lit) * uShadowStrength * 0.45 + max(gridLine, ring));
  fragColor = vec4(col, clamp(alpha, 0.0, 0.92));
}
`;

const LINE_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aCol;
uniform mat4 uVP;
out vec3 vCol;
void main() {
  vCol = aCol;
  gl_Position = uVP * vec4(aPos, 1.0);
  gl_PointSize = 6.5;
}
`;

const LINE_FS = `#version 300 es
precision highp float;
in vec3 vCol;
out vec4 fragColor;
void main() {
  fragColor = vec4(vCol, 0.95);
}
`;

const SKYBOX_VS = `#version 300 es
precision highp float;
layout(location = 0) in vec2 aPos;
out vec2 vNdc;
void main() {
  vNdc = aPos;
  gl_Position = vec4(aPos, 0.9999, 1.0);
}
`;

const SKYBOX_FS = `#version 300 es
precision highp float;
in vec2 vNdc;

uniform vec3 uCamRight;
uniform vec3 uCamUp;
uniform vec3 uCamFwd;
uniform float uTanHalfFov;
uniform float uAspect;
uniform int uSkyMode;       // 1:clear, 2:pastel, 3:night, 4:sunset, 5:studioDark, 6:custom
uniform float uSkyRotRad;
uniform float uSkyExposure;
uniform float uSkyBlur;
uniform float uTime;
uniform vec3 uSunDir;
uniform sampler2D uSkyTex;

out vec4 fragColor;

float hash21(vec2 p) {
  p = fract(p * vec2(234.34, 435.345));
  p += dot(p, p + 34.23);
  return fract(p.x * p.y);
}

float noise2(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float a = hash21(i);
  float b = hash21(i + vec2(1.0, 0.0));
  float c = hash21(i + vec2(0.0, 1.0));
  float d = hash21(i + vec2(1.0, 1.0));
  return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 4; i++) {
    v += amp * noise2(p);
    p = p * 2.05 + vec2(13.1, 7.7);
    amp *= 0.5;
  }
  return v;
}

vec3 rotY(vec3 v, float a) {
  float c = cos(a), s = sin(a);
  return vec3(c * v.x + s * v.z, v.y, -s * v.x + c * v.z);
}

void main() {
  vec3 dir = normalize(uCamFwd + uCamRight * (vNdc.x * uAspect * uTanHalfFov) + uCamUp * (vNdc.y * uTanHalfFov));
  vec3 rdir = rotY(dir, uSkyRotRad);
  vec3 sunD = normalize(rotY(uSunDir, uSkyRotRad));
  float y = rdir.y;
  vec3 col = vec3(0.0);

  if (uSkyMode == 6) {
    // Equirectangular 360 panorama texture
    float u = atan(rdir.z, rdir.x) / 6.28318530718 + 0.5;
    float v = acos(clamp(rdir.y, -1.0, 1.0)) / 3.14159265359;
    col = textureLod(uSkyTex, vec2(u, v), uSkyBlur * 5.5).rgb;
  } else if (uSkyMode == 1) {
    // 1: Clear Sky + Sun + Soft Drifting Clouds
    vec3 zenith = vec3(0.30, 0.57, 0.94);
    vec3 horizon = vec3(0.84, 0.93, 1.00);
    vec3 ground = vec3(0.76, 0.84, 0.93);
    col = y >= 0.0
      ? mix(horizon, zenith, pow(clamp(y, 0.0, 1.0), 0.58))
      : mix(horizon, ground, pow(clamp(-y, 0.0, 1.0), 0.65));

    float sunAmt = max(dot(rdir, sunD), 0.0);
    col += vec3(1.0, 0.96, 0.84) * (pow(sunAmt, 240.0) * 1.4 + pow(sunAmt, 14.0) * 0.25);

    if (y > 0.02) {
      vec2 cuv = rdir.xz / (y + 0.16) * 0.65 + vec2(uTime * 0.012, uTime * 0.005);
      float c = smoothstep(0.47, 0.78, fbm(cuv * 2.2));
      float fade = smoothstep(0.02, 0.24, y);
      col = mix(col, vec3(0.99, 0.995, 1.0), c * fade * 0.78);
    }
  } else if (uSkyMode == 2) {
    // 2: Dreamy Pastel Sakura-Lavender Sky
    vec3 zenith = vec3(0.62, 0.72, 0.98);
    vec3 mid = vec3(0.86, 0.84, 0.99);
    vec3 horizon = vec3(0.99, 0.87, 0.94);
    vec3 ground = vec3(0.86, 0.83, 0.95);
    if (y >= 0.0) {
      col = mix(horizon, mid, smoothstep(0.0, 0.28, y));
      col = mix(col, zenith, smoothstep(0.24, 0.85, y));
    } else {
      col = mix(horizon, ground, pow(clamp(-y, 0.0, 1.0), 0.6));
    }
    float sunAmt = max(dot(rdir, sunD), 0.0);
    col += vec3(1.0, 0.93, 0.98) * (pow(sunAmt, 80.0) * 0.65 + pow(sunAmt, 8.0) * 0.18);
    if (y > 0.01) {
      vec2 cuv = rdir.xz / (y + 0.22) * 0.55 + vec2(uTime * 0.009, 0.0);
      float c = smoothstep(0.45, 0.80, fbm(cuv * 1.9));
      col = mix(col, vec3(1.0, 0.97, 0.99), c * smoothstep(0.01, 0.22, y) * 0.65);
    }
  } else if (uSkyMode == 3) {
    // 3: Starry Night + Milky Way + Moon
    vec3 zenith = vec3(0.03, 0.05, 0.13);
    vec3 horizon = vec3(0.11, 0.16, 0.31);
    vec3 ground = vec3(0.05, 0.07, 0.14);
    col = y >= 0.0
      ? mix(horizon, zenith, pow(clamp(y, 0.0, 1.0), 0.55))
      : mix(horizon, ground, pow(clamp(-y, 0.0, 1.0), 0.6));

    // Soft violet milky way ribbon
    float band = exp(-pow((rdir.x * 0.6 + rdir.y * 0.5 - rdir.z * 0.4) * 3.0, 2.0));
    float neb = fbm(vec2(atan(rdir.z, rdir.x) * 3.0, rdir.y * 5.0));
    col += vec3(0.22, 0.20, 0.48) * band * neb * smoothstep(-0.05, 0.25, y) * 0.65;

    // Crisp procedural stars
    if (y > -0.05) {
      vec2 sgrid = vec2(atan(rdir.z, rdir.x) * 38.0, asin(clamp(rdir.y, -1.0, 1.0)) * 38.0);
      float cell = hash21(floor(sgrid));
      vec2 f = fract(sgrid) - 0.5;
      float d = length(f);
      float twinkle = 0.72 + 0.28 * sin(uTime * 2.5 + cell * 40.0);
      float star = step(0.955, cell) * smoothstep(0.22, 0.02, d) * twinkle * smoothstep(-0.05, 0.15, y);
      col += mix(vec3(0.82, 0.90, 1.0), vec3(1.0, 0.92, 0.82), fract(cell * 17.0)) * star * 1.3;
    }

    // Glowing moon
    vec3 moonDir = normalize(vec3(-0.42, 0.45, 0.78));
    float mAmt = max(dot(rdir, moonDir), 0.0);
    col += vec3(0.85, 0.92, 1.0) * (smoothstep(0.9985, 0.9993, mAmt) * 1.1 + pow(mAmt, 28.0) * 0.28);
  } else if (uSkyMode == 4) {
    // 4: Golden Hour Sunset
    vec3 zenith = vec3(0.18, 0.20, 0.44);
    vec3 mid = vec3(0.76, 0.39, 0.52);
    vec3 horizon = vec3(1.00, 0.68, 0.46);
    vec3 ground = vec3(0.26, 0.18, 0.29);
    if (y >= 0.0) {
      col = mix(horizon, mid, smoothstep(0.0, 0.26, y));
      col = mix(col, zenith, smoothstep(0.22, 0.78, y));
    } else {
      col = mix(horizon * 0.7, ground, pow(clamp(-y, 0.0, 1.0), 0.5));
    }
    vec3 lowSun = normalize(vec3(sunD.x, max(0.12, min(0.32, sunD.y)), sunD.z));
    float sunAmt = max(dot(rdir, lowSun), 0.0);
    col += vec3(1.0, 0.85, 0.55) * (pow(sunAmt, 180.0) * 1.4 + pow(sunAmt, 9.0) * 0.38);
    if (y > 0.01) {
      vec2 cuv = rdir.xz / (y + 0.18) * 0.6 + vec2(uTime * 0.01, 0.0);
      float c = smoothstep(0.48, 0.78, fbm(cuv * 2.1));
      vec3 cloudCol = mix(vec3(0.62, 0.34, 0.48), vec3(1.0, 0.82, 0.64), pow(sunAmt, 2.0));
      col = mix(col, cloudCol, c * smoothstep(0.01, 0.20, y) * 0.72);
    }
  } else {
    // 5: Dark Studio Cyclorama Dome
    vec3 zenith = vec3(0.08, 0.10, 0.18);
    vec3 horizon = vec3(0.19, 0.23, 0.36);
    vec3 ground = vec3(0.07, 0.09, 0.15);
    col = y >= 0.0
      ? mix(horizon, zenith, pow(clamp(y, 0.0, 1.0), 0.55))
      : mix(horizon, ground, pow(clamp(-y, 0.0, 1.0), 0.55));
    float ring = exp(-pow((y - 0.02) * 18.0, 2.0));
    col += vec3(0.26, 0.36, 0.68) * ring * 0.32;
  }

  col *= uSkyExposure;
  fragColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`;

function compileShader(gl, type, src) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(sh);
    gl.deleteShader(sh);
    throw new Error(`Shader compile error: ${info}`);
  }
  return sh;
}

function createProgram(gl, vsSrc, fsSrc) {
  const prog = gl.createProgram();
  const vs = compileShader(gl, gl.VERTEX_SHADER, vsSrc);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, fsSrc);
  gl.attachShader(prog, vs);
  gl.attachShader(prog, fs);
  gl.linkProgram(prog);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(prog);
    gl.deleteProgram(prog);
    throw new Error(`Program link error: ${info}`);
  }
  return prog;
}

// ============================================================================
// Main YSM WebGL2 Renderer Class
// ============================================================================
export class YsmWebGLRenderer {
  constructor(canvas) {
    this.canvas = canvas;
    const gl = canvas.getContext("webgl2", {
      antialias: true,
      alpha: true,
      preserveDrawingBuffer: true,
    });
    if (!gl) {
      throw new Error("当前浏览器不支持 WebGL2，无法初始化 3D 展示引擎。");
    }
    this.gl = gl;

    this.progShadow = createProgram(gl, SHADOW_VS, SHADOW_FS);
    this.progModel = createProgram(gl, MODEL_VS, MODEL_FS);
    this.progStage = createProgram(gl, STAGE_VS, STAGE_FS);
    this.progLine = createProgram(gl, LINE_VS, LINE_FS);
    this.progSkybox = createProgram(gl, SKYBOX_VS, SKYBOX_FS);

    this._initShadowMap(2048);
    this._initStageBuffer();
    this._initSkeletonBuffer();
    this._initSkyboxBuffer();

    // Scene state
    this.geo = null;
    this.boneBatches = [];
    this.boneMap = new Map();
    this.modelVao = null;
    this.modelVbo = null;
    this.texture = null;
    this.skyboxTexture = null;
    this.hasCustomSkybox = false;
    this._elapsed = 0;
    this.modelBounds = { minY: 0, maxY: 32, centerY: 16, radius: 18 };

    // Camera state (spherical orbit in right-handed space; yaw=0 faces front -Z!)
    this.camera = {
      yaw: -22,      // degrees; 0 = pure front, +90 = left side, 180 = back
      pitch: 8,      // degrees
      distance: 62,
      target: [0, 16.5, 0],
      fov: 34,
      ortho: false,
      autoRotate: false,
      autoRotateSpeed: 24,
    };

    // Lighting & environment settings
    this.lighting = {
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
      rimPower: 2.8,
      shadingMode: 0, // 0: Studio, 1: Toon, 2: Unlit
      exposure: 1.0,
      saturation: 1.02,
      bgTop: "#eef2fb",
      bgBottom: "#dfe6f6",
      transparentBg: false,
      showStage: true,
      showGrid: true,
      showSkeleton: false,
      skyboxMode: "pastel", // gradient | clear | pastel | night | sunset | studioDark | custom
      skyRotation: 0,
      skyExposure: 1.0,
      skyBlur: 0.0,
    };

    this._bindPointerControls();
  }

  _initShadowMap(size) {
    const gl = this.gl;
    this.shadowSize = size;
    this.shadowTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, this.shadowTex);
    gl.texImage2D(
      gl.TEXTURE_2D,
      0,
      gl.DEPTH_COMPONENT24,
      size,
      size,
      0,
      gl.DEPTH_COMPONENT,
      gl.UNSIGNED_INT,
      null
    );
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);

    this.shadowFbo = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.shadowFbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.TEXTURE_2D, this.shadowTex, 0);
    gl.drawBuffers([gl.NONE]);
    gl.readBuffer(gl.NONE);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  }

  _initStageBuffer() {
    const gl = this.gl;
    const s = 30.0;
    const verts = new Float32Array([
      -s, 0, -s,   s, 0, -s,   s, 0, s,
      -s, 0, -s,   s, 0, s,   -s, 0, s,
    ]);
    this.stageVao = gl.createVertexArray();
    this.stageVbo = gl.createBuffer();
    gl.bindVertexArray(this.stageVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.stageVbo);
    gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
  }

  _initSkeletonBuffer() {
    const gl = this.gl;
    this.skelVao = gl.createVertexArray();
    this.skelVbo = gl.createBuffer();
    gl.bindVertexArray(this.skelVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.skelVbo);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 24, 0);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 24, 12);
    gl.bindVertexArray(null);
  }

  _initSkyboxBuffer() {
    const gl = this.gl;
    const verts = new Float32Array([
      -1, -1,  1, -1,  1,  1,
      -1, -1,  1,  1, -1,  1,
    ]);
    this.skyVao = gl.createVertexArray();
    this.skyVbo = gl.createBuffer();
    gl.bindVertexArray(this.skyVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.skyVbo);
    gl.bufferData(gl.ARRAY_BUFFER, verts, gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gl.bindVertexArray(null);
  }

  setSkyboxTexture(imgOrCanvas) {
    const gl = this.gl;
    if (this.skyboxTexture) gl.deleteTexture(this.skyboxTexture);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, imgOrCanvas);
    gl.generateMipmap(gl.TEXTURE_2D);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.skyboxTexture = tex;
    this.hasCustomSkybox = true;
  }

  _bindPointerControls() {
    const el = this.canvas;
    let dragging = false;
    let mode = "orbit";
    let lastX = 0;
    let lastY = 0;

    el.addEventListener("contextmenu", (e) => e.preventDefault());
    el.addEventListener("pointerdown", (e) => {
      if (e.button === 2 || e.shiftKey) mode = "pan";
      else if (e.button === 0) mode = "orbit";
      else return;
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
      el.setPointerCapture(e.pointerId);
    });
    el.addEventListener("pointermove", (e) => {
      if (!dragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;

      if (mode === "orbit") {
        this.camera.yaw -= dx * 0.45;
        this.camera.pitch = Math.max(-80, Math.min(82, this.camera.pitch + dy * 0.38));
      } else {
        const panScale = this.camera.distance * 0.0014;
        const yawRad = this.camera.yaw * DEG2RAD;
        // Screen right vector in world XZ
        const rx = -Math.cos(yawRad);
        const rz = Math.sin(yawRad);
        this.camera.target[0] -= dx * panScale * rx;
        this.camera.target[2] -= dx * panScale * rz;
        this.camera.target[1] += dy * panScale;
      }
    });
    const endDrag = () => {
      dragging = false;
    };
    el.addEventListener("pointerup", endDrag);
    el.addEventListener("pointercancel", endDrag);
    el.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const factor = Math.exp(e.deltaY * 0.0011);
        this.camera.distance = Math.max(16, Math.min(180, this.camera.distance * factor));
      },
      { passive: false }
    );
  }

  setTexture(image) {
    const gl = this.gl;
    if (this.texture) gl.deleteTexture(this.texture);
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    this.texture = tex;
  }

  setGeometry(parsedGeo) {
    const gl = this.gl;
    this.geo = parsedGeo;
    this.boneMap = new Map();
    for (const b of parsedGeo.bones) {
      this.boneMap.set(b.name, b);
    }

    const uvW = parsedGeo.textureWidth || 64;
    const uvH = parsedGeo.textureHeight || 64;
    const verts = [];
    this.boneBatches = [];

    let minY = Infinity, maxY = -Infinity;
    let maxR = 8;

    for (const b of parsedGeo.bones) {
      const startVertex = verts.length / 8;

      for (const cube of b.cubes) {
        const [ox, oy, oz] = cube.origin;
        const [sx, sy, sz] = cube.size;
        const inf = cube.inflate || 0;

        const fx = -(ox + sx) - inf;
        const tx = -ox + inf;
        const fy = oy - inf;
        const ty = oy + sy + inf;
        const fz = oz - inf;
        const tz = oz + sz + inf;

        let cubeMat = null;
        if (cube.rotation && (Math.abs(cube.rotation[0]) > 1e-6 || Math.abs(cube.rotation[1]) > 1e-6 || Math.abs(cube.rotation[2]) > 1e-6)) {
          const cp = cube.pivot || [ox + sx * 0.5, oy + sy * 0.5, oz + sz * 0.5];
          const cpRh = [-cp[0], cp[1], cp[2]];
          cubeMat = mat4BoneLocal(cpRh, cube.rotation, [0, 0, 0], [1, 1, 1]);
        }

        const facesSpec = {
          north: {
            pts: [[tx, ty, fz], [fx, ty, fz], [fx, fy, fz], [tx, fy, fz]],
            nrm: [0, 0, -1],
          },
          south: {
            pts: [[fx, ty, tz], [tx, ty, tz], [tx, fy, tz], [fx, fy, tz]],
            nrm: [0, 0, 1],
          },
          east: {
            pts: [[tx, ty, tz], [tx, ty, fz], [tx, fy, fz], [tx, fy, tz]],
            nrm: [1, 0, 0],
          },
          west: {
            pts: [[fx, ty, fz], [fx, ty, tz], [fx, fy, tz], [fx, fy, fz]],
            nrm: [-1, 0, 0],
          },
          up: {
            pts: [[tx, ty, tz], [fx, ty, tz], [fx, ty, fz], [tx, ty, fz]],
            nrm: [0, 1, 0],
          },
          down: {
            pts: [[tx, fy, fz], [fx, fy, fz], [fx, fy, tz], [tx, fy, tz]],
            nrm: [0, -1, 0],
          },
        };

        for (const [fname, spec] of Object.entries(facesSpec)) {
          const fuv = cube.facesUv[fname];
          if (!fuv || !fuv.uv || !fuv.uv_size) continue;
          const u0 = Number(fuv.uv[0]) / uvW;
          const v0 = Number(fuv.uv[1]) / uvH;
          const uw = Number(fuv.uv_size[0]) / uvW;
          const vh = Number(fuv.uv_size[1]) / uvH;
          if (Math.abs(uw) < 1e-6 || Math.abs(vh) < 1e-6) continue;

          // Subtle inset by 0.0001 to avoid edge bleed on nearest-neighbor texel borders
          const epsU = uw >= 0 ? 1e-5 : -1e-5;
          const epsV = vh >= 0 ? 1e-5 : -1e-5;
          const qUv = [
            [u0 + epsU, v0 + epsV],
            [u0 + uw - epsU, v0 + epsV],
            [u0 + uw - epsU, v0 + vh - epsV],
            [u0 + epsU, v0 + vh - epsV],
          ];

          let pts = spec.pts;
          let nrm = spec.nrm;
          if (cubeMat) {
            pts = pts.map((p) => transformPoint(cubeMat, p));
            const nx = cubeMat[0] * nrm[0] + cubeMat[4] * nrm[1] + cubeMat[8] * nrm[2];
            const ny = cubeMat[1] * nrm[0] + cubeMat[5] * nrm[1] + cubeMat[9] * nrm[2];
            const nz = cubeMat[2] * nrm[0] + cubeMat[6] * nrm[1] + cubeMat[10] * nrm[2];
            const nl = Math.hypot(nx, ny, nz) || 1;
            nrm = [nx / nl, ny / nl, nz / nl];
          }

          for (const p of pts) {
            if (p[1] < minY) minY = p[1];
            if (p[1] > maxY) maxY = p[1];
            const r = Math.hypot(p[0], p[2]);
            if (r > maxR) maxR = r;
          }

          // Two triangles: (0, 2, 1) and (0, 3, 2)
          const idxOrder = [0, 2, 1, 0, 3, 2];
          for (const idx of idxOrder) {
            const p = pts[idx];
            const uv = qUv[idx];
            verts.push(p[0], p[1], p[2], nrm[0], nrm[1], nrm[2], uv[0], uv[1]);
          }
        }
      }

      const vertexCount = verts.length / 8 - startVertex;
      this.boneBatches.push({
        boneName: b.name,
        start: startVertex,
        count: vertexCount,
      });
    }

    if (!Number.isFinite(minY)) {
      minY = 0;
      maxY = 32;
    }
    const height = Math.max(8, maxY - minY);
    this.modelBounds = {
      minY,
      maxY,
      centerY: (minY + maxY) * 0.5,
      height,
      radius: Math.max(height * 0.55, maxR),
    };

    if (this.modelVao) gl.deleteVertexArray(this.modelVao);
    if (this.modelVbo) gl.deleteBuffer(this.modelVbo);
    this.modelVao = gl.createVertexArray();
    this.modelVbo = gl.createBuffer();
    gl.bindVertexArray(this.modelVao);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.modelVbo);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(verts), gl.STATIC_DRAW);
    // Stride = 8 floats = 32 bytes
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 3, gl.FLOAT, false, 32, 0);
    gl.enableVertexAttribArray(1);
    gl.vertexAttribPointer(1, 3, gl.FLOAT, false, 32, 12);
    gl.enableVertexAttribArray(2);
    gl.vertexAttribPointer(2, 2, gl.FLOAT, false, 32, 24);
    gl.bindVertexArray(null);
  }

  frameModel(preset = "threeQuarter") {
    const b = this.modelBounds;
    this.camera.target = [0, b.centerY - b.height * 0.04, 0];
    this.camera.distance = Math.max(28, b.height * 2.18);
    if (preset === "front") {
      this.camera.yaw = 0;
      this.camera.pitch = 4;
    } else if (preset === "side") {
      this.camera.yaw = 90;
      this.camera.pitch = 4;
    } else if (preset === "back") {
      this.camera.yaw = 180;
      this.camera.pitch = 4;
    } else if (preset === "closeup") {
      this.camera.target = [0, b.minY + b.height * 0.78, 0];
      this.camera.distance = Math.max(18, b.height * 0.85);
      this.camera.yaw = -16;
      this.camera.pitch = 5;
    } else {
      this.camera.yaw = -24;
      this.camera.pitch = 9;
    }
  }

  computeBoneTransforms(animPose, headOverride = { yaw: 0, pitch: 0 }, boneOverrides = null) {
    const cache = new Map();
    if (!this.geo) return cache;

    const resolve = (bname) => {
      if (cache.has(bname)) return cache.get(bname);
      const b = this.boneMap.get(bname);
      if (!b) return { mat: mat4Identity(), worldPivot: [0, 0, 0], visible: true };

      let pMat = mat4Identity();
      let pVis = true;
      if (b.parent && this.boneMap.has(b.parent)) {
        const p = resolve(b.parent);
        pMat = p.mat;
        pVis = p.visible;
      }

      const ov = boneOverrides ? boneOverrides.get(bname) : null;
      let visible = pVis && !b.neverRender && !(ov && ov.hidden);
      const pivRh = [-b.pivot[0], b.pivot[1], b.pivot[2]];
      const pose = animPose?.[bname];

      let rot;
      let pos;
      let scale;
      if (ov && ov.mode === "replace") {
        rot = [b.rotation[0] + ov.rotation[0], b.rotation[1] + ov.rotation[1], b.rotation[2] + ov.rotation[2]];
        pos = [ov.position[0], ov.position[1], ov.position[2]];
        scale = [ov.scale[0], ov.scale[1], ov.scale[2]];
      } else {
        rot = [
          b.rotation[0] + (pose ? pose.rotation[0] : 0) + (ov ? ov.rotation[0] : 0),
          b.rotation[1] + (pose ? pose.rotation[1] : 0) + (ov ? ov.rotation[1] : 0),
          b.rotation[2] + (pose ? pose.rotation[2] : 0) + (ov ? ov.rotation[2] : 0),
        ];
        pos = [
          (pose ? pose.position[0] : 0) + (ov ? ov.position[0] : 0),
          (pose ? pose.position[1] : 0) + (ov ? ov.position[1] : 0),
          (pose ? pose.position[2] : 0) + (ov ? ov.position[2] : 0),
        ];
        scale = [
          (pose ? pose.scale[0] : 1) * (ov ? ov.scale[0] : 1),
          (pose ? pose.scale[1] : 1) * (ov ? ov.scale[1] : 1),
          (pose ? pose.scale[2] : 1) * (ov ? ov.scale[2] : 1),
        ];
      }

      // Apply manual interactive head look override onto AllHead (or Head if no AllHead)
      if (
        (bname === "AllHead" || (bname === "Head" && !this.boneMap.has("AllHead"))) &&
        (Math.abs(headOverride.yaw) > 1e-4 || Math.abs(headOverride.pitch) > 1e-4)
      ) {
        rot[0] += headOverride.pitch;
        rot[1] += headOverride.yaw;
      }

      const posRh = [-pos[0], pos[1], pos[2]];
      if (Math.abs(scale[0]) < 1e-4 || Math.abs(scale[1]) < 1e-4 || Math.abs(scale[2]) < 1e-4) {
        visible = false;
      }

      const localMat = mat4BoneLocal(pivRh, rot, posRh, scale);
      const worldMat = mat4Mul(pMat, localMat);
      const worldPivot = transformPoint(worldMat, pivRh);
      const res = { mat: worldMat, worldPivot, visible };
      cache.set(bname, res);
      return res;
    };

    for (const b of this.geo.bones) {
      resolve(b.name);
    }
    return cache;
  }

  resizeIfNeeded() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.floor(this.canvas.clientWidth * dpr));
    const h = Math.max(1, Math.floor(this.canvas.clientHeight * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
  }

  render(animPose, headOverride, dtSeconds = 0, boneOverrides = null, selectedBoneName = null) {
    this.resizeIfNeeded();
    const gl = this.gl;
    const W = this.canvas.width;
    const H = this.canvas.height;
    const L = this.lighting;
    this._elapsed += dtSeconds;

    if (this.camera.autoRotate && dtSeconds > 0) {
      this.camera.yaw = (this.camera.yaw + this.camera.autoRotateSpeed * dtSeconds) % 360;
    }

    // Compute camera matrices (yaw=0 -> eye on -Z facing +Z, matching front view!)
    const yawRad = this.camera.yaw * DEG2RAD;
    const pitchRad = this.camera.pitch * DEG2RAD;
    const dist = this.camera.distance;
    const cp = Math.cos(pitchRad);
    const eye = [
      this.camera.target[0] + dist * cp * Math.sin(yawRad),
      this.camera.target[1] + dist * Math.sin(pitchRad),
      this.camera.target[2] - dist * cp * Math.cos(yawRad),
    ];
    const viewMat = mat4LookAt(eye, this.camera.target, [0, 1, 0]);
    const aspect = W / Math.max(1, H);
    let projMat;
    if (this.camera.ortho) {
      const halfH = dist * Math.tan((this.camera.fov * DEG2RAD) / 2);
      const halfW = halfH * aspect;
      projMat = mat4Ortho(-halfW, halfW, -halfH, halfH, 0.5, 400);
    } else {
      projMat = mat4Perspective(this.camera.fov, aspect, 0.5, 400);
    }
    const vpMat = mat4Mul(projMat, viewMat);

    // Camera basis vectors for 360° skybox ray construction (extracted directly from viewMat rows!)
    const camRight = [viewMat[0], viewMat[4], viewMat[8]];
    const camUp = [viewMat[1], viewMat[5], viewMat[9]];
    const camFwd = [-viewMat[2], -viewMat[6], -viewMat[10]];

    // Compute key light direction & light VP matrix
    const azRad = L.keyAzimuth * DEG2RAD;
    const elRad = L.keyElevation * DEG2RAD;
    const keyDir = [
      Math.cos(elRad) * Math.sin(azRad),
      Math.sin(elRad),
      -Math.cos(elRad) * Math.cos(azRad),
    ];
    const fillDir = [-keyDir[0] * 0.85, 0.35, -keyDir[2] * 0.65];

    const centerY = this.modelBounds.centerY;
    const shadowHalf = Math.max(22, this.modelBounds.radius * 1.45);
    const lightEye = [keyDir[0] * 70, centerY + keyDir[1] * 70, keyDir[2] * 70];
    const lightView = mat4LookAt(lightEye, [0, centerY, 0], [0, 1, 0]);
    const lightProj = mat4Ortho(-shadowHalf, shadowHalf, -shadowHalf, shadowHalf, 10, 150);
    const lightVP = mat4Mul(lightProj, lightView);

    const xforms = this.computeBoneTransforms(animPose, headOverride, boneOverrides);

    // ------------------------------------------------------------------
    // PASS 1: Shadow Depth Map
    // ------------------------------------------------------------------
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.shadowFbo);
    gl.viewport(0, 0, this.shadowSize, this.shadowSize);
    gl.enable(gl.DEPTH_TEST);
    gl.depthMask(true);
    gl.disable(gl.BLEND);
    gl.disable(gl.CULL_FACE);
    gl.clear(gl.DEPTH_BUFFER_BIT);

    if (this.modelVao && this.texture) {
      gl.useProgram(this.progShadow);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.progShadow, "uLightVP"), false, lightVP);
      const locBone = gl.getUniformLocation(this.progShadow, "uBoneMat");
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.uniform1i(gl.getUniformLocation(this.progShadow, "uTex"), 0);
      gl.bindVertexArray(this.modelVao);
      for (const batch of this.boneBatches) {
        if (batch.count === 0) continue;
        const xf = xforms.get(batch.boneName);
        if (!xf || !xf.visible) continue;
        gl.uniformMatrix4fv(locBone, false, xf.mat);
        gl.drawArrays(gl.TRIANGLES, batch.start, batch.count);
      }
      gl.bindVertexArray(null);
    }

    // ------------------------------------------------------------------
    // PASS 2: Main Viewport
    // ------------------------------------------------------------------
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, W, H);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    // 2.0. 360° 3D Skybox Dome (when enabled and not transparent export mode)
    const SKY_MODE_MAP = {
      gradient: 0,
      clear: 1,
      pastel: 2,
      night: 3,
      sunset: 4,
      studioDark: 5,
      custom: 6,
    };
    const skyModeInt = L.transparentBg ? 0 : (SKY_MODE_MAP[L.skyboxMode] || 0);
    if (skyModeInt > 0 && (skyModeInt !== 6 || this.hasCustomSkybox)) {
      gl.useProgram(this.progSkybox);
      gl.disable(gl.DEPTH_TEST);
      gl.depthMask(false);
      gl.disable(gl.BLEND);

      const uk = (name) => gl.getUniformLocation(this.progSkybox, name);
      gl.uniform3fv(uk("uCamRight"), camRight);
      gl.uniform3fv(uk("uCamUp"), camUp);
      gl.uniform3fv(uk("uCamFwd"), camFwd);
      gl.uniform1f(uk("uTanHalfFov"), Math.tan((this.camera.fov * DEG2RAD) / 2));
      gl.uniform1f(uk("uAspect"), aspect);
      gl.uniform1i(uk("uSkyMode"), skyModeInt);
      gl.uniform1f(uk("uSkyRotRad"), (L.skyRotation || 0) * DEG2RAD);
      gl.uniform1f(uk("uSkyExposure"), L.skyExposure ?? 1.0);
      gl.uniform1f(uk("uSkyBlur"), L.skyBlur ?? 0.0);
      gl.uniform1f(uk("uTime"), this._elapsed);
      gl.uniform3fv(uk("uSunDir"), keyDir);

      if (this.skyboxTexture) {
        gl.activeTexture(gl.TEXTURE2);
        gl.bindTexture(gl.TEXTURE_2D, this.skyboxTexture);
        gl.uniform1i(uk("uSkyTex"), 2);
      }

      gl.bindVertexArray(this.skyVao);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      gl.bindVertexArray(null);
      gl.depthMask(true);
    }

    // 2A. Model Render
    if (this.modelVao && this.texture) {
      gl.useProgram(this.progModel);
      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(true);
      gl.disable(gl.CULL_FACE);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      const u = (name) => gl.getUniformLocation(this.progModel, name);
      gl.uniformMatrix4fv(u("uVP"), false, vpMat);
      gl.uniformMatrix4fv(u("uLightVP"), false, lightVP);
      gl.uniform3fv(u("uCamPos"), eye);

      gl.uniform3fv(u("uSkyColor"), hexToRgb01(L.skyColor));
      gl.uniform3fv(u("uGroundColor"), hexToRgb01(L.groundColor));
      gl.uniform1f(u("uAmbientIntensity"), L.ambientIntensity);

      gl.uniform3fv(u("uKeyDir"), keyDir);
      gl.uniform3fv(u("uKeyColor"), hexToRgb01(L.keyColor));
      gl.uniform1f(u("uKeyIntensity"), L.keyIntensity);
      gl.uniform1f(u("uShadowStrength"), L.shadowStrength);

      gl.uniform3fv(u("uFillDir"), fillDir);
      gl.uniform3fv(u("uFillColor"), hexToRgb01(L.fillColor));
      gl.uniform1f(u("uFillIntensity"), L.fillIntensity);

      gl.uniform3fv(u("uRimColor"), hexToRgb01(L.rimColor));
      gl.uniform1f(u("uRimIntensity"), L.rimIntensity);
      gl.uniform1f(u("uRimPower"), L.rimPower);

      gl.uniform1i(u("uShadingMode"), L.shadingMode);
      gl.uniform1f(u("uExposure"), L.exposure);
      gl.uniform1f(u("uSaturation"), L.saturation);

      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texture);
      gl.uniform1i(u("uTex"), 0);

      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.shadowTex);
      gl.uniform1i(u("uShadowMap"), 1);

      const locBone = u("uBoneMat");
      gl.bindVertexArray(this.modelVao);
      for (const batch of this.boneBatches) {
        if (batch.count === 0) continue;
        const xf = xforms.get(batch.boneName);
        if (!xf || !xf.visible) continue;
        gl.uniformMatrix4fv(locBone, false, xf.mat);
        gl.drawArrays(gl.TRIANGLES, batch.start, batch.count);
      }
      gl.bindVertexArray(null);
    }

    // 2B. Ground Studio Stage (shadow receiver + subtle grid)
    if (L.showStage) {
      gl.useProgram(this.progStage);
      gl.enable(gl.DEPTH_TEST);
      gl.depthMask(false);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

      const us = (name) => gl.getUniformLocation(this.progStage, name);
      gl.uniformMatrix4fv(us("uVP"), false, vpMat);
      gl.uniformMatrix4fv(us("uLightVP"), false, lightVP);
      const bgRgb = hexToRgb01(L.bgBottom);
      const isDark =
        L.skyboxMode === "night" ||
        L.skyboxMode === "studioDark" ||
        (L.skyboxMode === "gradient" && bgRgb[0] * 0.3 + bgRgb[1] * 0.59 + bgRgb[2] * 0.11 < 0.45);
      gl.uniform3fv(us("uStageColor"), isDark ? [0.16, 0.19, 0.28] : [0.89, 0.91, 0.97]);
      gl.uniform3fv(us("uGridColor"), isDark ? [0.48, 0.62, 0.92] : [0.52, 0.60, 0.84]);
      gl.uniform1f(us("uShowGrid"), L.showGrid ? 1.0 : 0.0);
      gl.uniform1f(us("uShadowStrength"), L.shadowStrength);

      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.shadowTex);
      gl.uniform1i(us("uShadowMap"), 1);

      gl.bindVertexArray(this.stageVao);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      gl.bindVertexArray(null);
      gl.depthMask(true);
    }

    // 2C. Optional 3D Skeleton Pivot & Selected Bone Gizmo Overlay
    if ((L.showSkeleton || selectedBoneName) && this.geo) {
      const lineVerts = [];
      const pointVerts = [];
      if (L.showSkeleton) {
        for (const b of this.geo.bones) {
          const xf = xforms.get(b.name);
          if (!xf) continue;
          const isSel = b.name === selectedBoneName;
          const isLoc = b.name.includes("Locator");
          const col = isSel ? [1.0, 0.84, 0.18] : isLoc ? [0.15, 0.85, 0.52] : [0.95, 0.32, 0.52];
          pointVerts.push(xf.worldPivot[0], xf.worldPivot[1], xf.worldPivot[2], col[0], col[1], col[2]);
          if (b.parent && xforms.has(b.parent)) {
            const pxf = xforms.get(b.parent);
            lineVerts.push(
              pxf.worldPivot[0], pxf.worldPivot[1], pxf.worldPivot[2], col[0], col[1], col[2],
              xf.worldPivot[0], xf.worldPivot[1], xf.worldPivot[2], col[0], col[1], col[2]
            );
          }
        }
      }
      // Draw crisp RGB local-axes gizmo at selected bone pivot
      if (selectedBoneName && xforms.has(selectedBoneName)) {
        const sxf = xforms.get(selectedBoneName);
        const p = sxf.worldPivot;
        const m = sxf.mat;
        const axLen = 3.2;
        const axes = [
          { vec: [-m[0], -m[1], -m[2]], col: [1.0, 0.32, 0.36] }, // Bedrock +X (Red)
          { vec: [m[4], m[5], m[6]], col: [0.32, 0.92, 0.45] },    // +Y (Green)
          { vec: [m[8], m[9], m[10]], col: [0.35, 0.65, 1.0] },    // +Z (Blue)
        ];
        for (const ax of axes) {
          const al = Math.hypot(ax.vec[0], ax.vec[1], ax.vec[2]) || 1;
          lineVerts.push(
            p[0], p[1], p[2], ax.col[0], ax.col[1], ax.col[2],
            p[0] + (ax.vec[0] / al) * axLen, p[1] + (ax.vec[1] / al) * axLen, p[2] + (ax.vec[2] / al) * axLen,
            ax.col[0], ax.col[1], ax.col[2]
          );
        }
        pointVerts.push(p[0], p[1], p[2], 1.0, 0.86, 0.22);
      }
      gl.useProgram(this.progLine);
      gl.disable(gl.DEPTH_TEST);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.progLine, "uVP"), false, vpMat);
      gl.bindVertexArray(this.skelVao);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.skelVbo);
      if (lineVerts.length) {
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(lineVerts), gl.DYNAMIC_DRAW);
        gl.drawArrays(gl.LINES, 0, lineVerts.length / 6);
      }
      if (pointVerts.length) {
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(pointVerts), gl.DYNAMIC_DRAW);
        gl.drawArrays(gl.POINTS, 0, pointVerts.length / 6);
      }
      gl.bindVertexArray(null);
      gl.enable(gl.DEPTH_TEST);
    }
  }
}
