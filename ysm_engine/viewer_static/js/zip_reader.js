/**
 * Lightweight zero-dependency ZIP archive reader using Central Directory
 * and native browser DecompressionStream('deflate-raw').
 * Supports Stored (0) and Deflate (8) entries + UTF-8 filenames.
 */
export async function unzipBuffer(arrayBuffer) {
  const bytes = new Uint8Array(arrayBuffer);
  const view = new DataView(arrayBuffer);
  const len = bytes.length;

  // Locate End of Central Directory (EOCD) signature: 0x06054b50
  let eocdOffset = -1;
  const minSearch = Math.max(0, len - 65557);
  for (let i = len - 22; i >= minSearch; i--) {
    if (
      bytes[i] === 0x50 &&
      bytes[i + 1] === 0x4b &&
      bytes[i + 2] === 0x05 &&
      bytes[i + 3] === 0x06
    ) {
      eocdOffset = i;
      break;
    }
  }
  if (eocdOffset < 0) {
    throw new Error("无效的 ZIP 文件（未找到中央目录结束标记 EOCD）。");
  }

  const totalEntries = view.getUint16(eocdOffset + 10, true);
  const cdOffset = view.getUint32(eocdOffset + 16, true);
  const decoder = new TextDecoder("utf-8");
  const files = new Map();

  let ptr = cdOffset;
  for (let idx = 0; idx < totalEntries; idx++) {
    if (ptr + 46 > len || view.getUint32(ptr, true) !== 0x02014b50) {
      break;
    }
    const method = view.getUint16(ptr + 10, true);
    const compressedSize = view.getUint32(ptr + 20, true);
    const uncompressedSize = view.getUint32(ptr + 24, true);
    const nameLen = view.getUint16(ptr + 28, true);
    const extraLen = view.getUint16(ptr + 30, true);
    const commentLen = view.getUint16(ptr + 32, true);
    const localHeaderOffset = view.getUint32(ptr + 42, true);

    const rawName = bytes.subarray(ptr + 46, ptr + 46 + nameLen);
    const name = decoder.decode(rawName).replace(/\\/g, "/");
    ptr += 46 + nameLen + extraLen + commentLen;

    if (name.endsWith("/") || name.startsWith("__MACOSX/")) {
      continue;
    }

    // Read local file header to find exact data start
    if (localHeaderOffset + 30 > len) continue;
    const localNameLen = view.getUint16(localHeaderOffset + 26, true);
    const localExtraLen = view.getUint16(localHeaderOffset + 28, true);
    const dataStart = localHeaderOffset + 30 + localNameLen + localExtraLen;
    const compressed = bytes.subarray(dataStart, dataStart + compressedSize);

    let outBytes;
    if (method === 0) {
      outBytes = compressed.slice();
    } else if (method === 8) {
      outBytes = await inflateRaw(compressed, uncompressedSize);
    } else {
      console.warn(`Unsupported ZIP compression method ${method} for ${name}`);
      continue;
    }
    files.set(name, outBytes);
  }
  return files;
}

async function inflateRaw(compressedBytes) {
  if (typeof DecompressionStream === "undefined") {
    throw new Error("当前浏览器不支持 DecompressionStream，请升级至新版 Chrome / Edge / Firefox。");
  }
  const ds = new DecompressionStream("deflate-raw");
  const writer = ds.writable.getWriter();
  const writePromise = writer.write(compressedBytes).then(() => writer.close());
  const chunks = [];
  const reader = ds.readable.getReader();
  let total = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    total += value.byteLength;
  }
  await writePromise;
  const result = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    result.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return result;
}
