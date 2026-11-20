/**
 * Skybox image & Radiance .hdr (RGBE) loader + hemisphere ambient color sampler.
 * Zero external dependencies.
 */

/**
 * Decode a Radiance .hdr (RGBE) ArrayBuffer into a tone-mapped HTMLCanvasElement.
 */
export function decodeRadianceHDR(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  let pos = 0;

  function readLine() {
    let line = "";
    while (pos < bytes.length) {
      const c = bytes[pos++];
      if (c === 10) break; // \n
      if (c !== 13) line += String.fromCharCode(c);
    }
    return line;
  }

  // Parse header until empty line
  let formatOk = false;
  while (pos < bytes.length) {
    const line = readLine();
    if (line.startsWith("FORMAT=")) {
      formatOk = line.includes("32-bit_rle_rgbe");
    }
    if (line === "") break;
  }
  if (!formatOk) {
    // Still attempt resolution parse for loose headers
  }

  const resLine = readLine();
  const match = resLine.match(/-Y\s+(\d+)\s+\+X\s+(\d+)/i);
  if (!match) {
    throw new Error("不支持的 HDR 分辨率头格式（仅支持标准 -Y H +X W RGBE）。");
  }
  const height = parseInt(match[1], 10);
  const width = parseInt(match[2], 10);

  const rgba = new Uint8ClampedArray(width * height * 4);
  const scanline = new Uint8Array(width * 4);

  for (let y = 0; y < height; y++) {
    if (pos + 4 > bytes.length) break;
    const b0 = bytes[pos];
    const b1 = bytes[pos + 1];
    const b2 = bytes[pos + 2];
    const b3 = bytes[pos + 3];

    if (b0 === 2 && b1 === 2 && ((b2 << 8) | b3) === width) {
      // New RLE scanline
      pos += 4;
      for (let ch = 0; ch < 4; ch++) {
        let x = 0;
        while (x < width && pos < bytes.length) {
          const code = bytes[pos++];
          if (code > 128) {
            const count = code - 128;
            const val = bytes[pos++];
            for (let k = 0; k < count && x < width; k++) {
              scanline[x * 4 + ch] = val;
              x++;
            }
          } else {
            const count = code;
            for (let k = 0; k < count && x < width; k++) {
              scanline[x * 4 + ch] = bytes[pos++];
              x++;
            }
          }
        }
      }
    } else {
      // Uncompressed scanline
      for (let i = 0; i < width * 4 && pos < bytes.length; i++) {
        scanline[i] = bytes[pos++];
      }
    }

    // Convert RGBE -> linear float -> ACES-like filmic sRGB
    const rowOff = y * width * 4;
    for (let x = 0; x < width; x++) {
      const e = scanline[x * 4 + 3];
      let r = 0, g = 0, b = 0;
      if (e > 0) {
        const scale = Math.pow(2.0, e - 128 - 8);
        r = scanline[x * 4 + 0] * scale;
        g = scanline[x * 4 + 1] * scale;
        b = scanline[x * 4 + 2] * scale;
      }
      // Soft Reinhard tone mapping + gamma 2.2
      r = Math.pow(r / (1.0 + r), 1 / 2.2);
      g = Math.pow(g / (1.0 + g), 1 / 2.2);
      b = Math.pow(b / (1.0 + b), 1 / 2.2);
      rgba[rowOff + x * 4 + 0] = Math.min(255, Math.max(0, Math.round(r * 255)));
      rgba[rowOff + x * 4 + 1] = Math.min(255, Math.max(0, Math.round(g * 255)));
      rgba[rowOff + x * 4 + 2] = Math.min(255, Math.max(0, Math.round(b * 255)));
      rgba[rowOff + x * 4 + 3] = 255;
    }
  }

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  ctx.putImageData(new ImageData(rgba, width, height), 0, 0);
  return canvas;
}

/**
 * Sample average upper-hemisphere (sky) and lower-hemisphere (ground) hex colors
 * from any HTMLImageElement or HTMLCanvasElement skybox so ambient light matches it!
 */
export function sampleHemisphereColors(imgSource) {
  const cw = 64;
  const ch = 32;
  const canvas = document.createElement("canvas");
  canvas.width = cw;
  canvas.height = ch;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(imgSource, 0, 0, cw, ch);
  const data = ctx.getImageData(0, 0, cw, ch).data;

  let sr = 0, sg = 0, sb = 0, sc = 0;
  let gr = 0, gg = 0, gb = 0, gc = 0;

  for (let y = 0; y < ch; y++) {
    for (let x = 0; x < cw; x++) {
      const idx = (y * cw + x) * 4;
      if (y < ch / 2) {
        sr += data[idx]; sg += data[idx + 1]; sb += data[idx + 2]; sc++;
      } else {
        gr += data[idx]; gg += data[idx + 1]; gb += data[idx + 2]; gc++;
      }
    }
  }

  const toHex = (r, g, b) => {
    // Lift slightly toward pastel white so character skin/hair stay vibrant and never muddy
    const lr = Math.min(255, Math.round(r * 0.72 + 255 * 0.28));
    const lg = Math.min(255, Math.round(g * 0.72 + 255 * 0.28));
    const lb = Math.min(255, Math.round(b * 0.72 + 255 * 0.28));
    return "#" + [lr, lg, lb].map((v) => v.toString(16).padStart(2, "0")).join("");
  };

  return {
    skyColor: toHex(sr / Math.max(1, sc), sg / Math.max(1, sc), sb / Math.max(1, sc)),
    groundColor: toHex(gr / Math.max(1, gc), gg / Math.max(1, gc), gb / Math.max(1, gc)),
  };
}
