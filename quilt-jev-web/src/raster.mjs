// quilt-jev-web :: raster.mjs  --- pure-JS scanline executor for the display list.
// Two executors, one op list. This one runs in Node (no canvas, no native
// modules, no network), so the receipt PNG is painted by the same geometry the
// browser paints. Canvas2D executes the identical list in app.mjs.

export function rasterize(display, ss = 2) {
  const W = display.width * ss, H = display.height * ss;
  const buf = new Uint8ClampedArray(W * H * 4);
  for (const op of display.ops) {
    if (op.op === 'clear') {
      for (let i = 0; i < W * H; i++) { buf[i * 4] = op.c[0]; buf[i * 4 + 1] = op.c[1]; buf[i * 4 + 2] = op.c[2]; buf[i * 4 + 3] = op.c[3]; }
      continue;
    }
    fillPoly(buf, W, H, op.pts.map(([x, y]) => [x * ss, y * ss]), op.c);
  }
  return { data: buf, width: W, height: H, ss, down: display.width, dwidth: display.height };
}

function fillPoly(buf, W, H, pts, c) {
  let ymin = Infinity, ymax = -Infinity;
  for (const [, y] of pts) { if (y < ymin) ymin = y; if (y > ymax) ymax = y; }
  ymin = Math.max(0, Math.floor(ymin)); ymax = Math.min(H - 1, Math.ceil(ymax));
  const xs = [];
  for (let y = ymin; y <= ymax; y++) {
    const sy = y + 0.5;
    xs.length = 0;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i], b = pts[(i + 1) % pts.length];
      if ((a[1] <= sy && b[1] > sy) || (b[1] <= sy && a[1] > sy)) {
        xs.push(a[0] + ((sy - a[1]) / (b[1] - a[1])) * (b[0] - a[0]));
      }
    }
    if (!xs.length) continue;
    xs.sort((p, q) => p - q);
    for (let k = 0; k + 1 < xs.length; k += 2) {
      const x0 = Math.max(0, Math.ceil(xs[k] - 0.5)), x1 = Math.min(W - 1, Math.floor(xs[k + 1] - 0.5));
      for (let x = x0; x <= x1; x++) blend(buf, (y * W + x) * 4, c);
    }
  }
}
function blend(buf, o, c) {
  const a = c[3] / 255;
  if (a >= 1) { buf[o] = c[0]; buf[o + 1] = c[1]; buf[o + 2] = c[2]; buf[o + 3] = 255; return; }
  buf[o] = buf[o] + (c[0] - buf[o]) * a;
  buf[o + 1] = buf[o + 1] + (c[1] - buf[o + 1]) * a;
  buf[o + 2] = buf[o + 2] + (c[2] - buf[o + 2]) * a;
  buf[o + 3] = 255;
}

// Content hash of the *pixels*, not the ops. This is the negative control's
// instrument: identical tensor -> identical pixels; shuffled tensor -> different
// pixels. Hashing ops would only prove the op list changed; hashing pixels
// proves something was actually painted.
export function pixelHash(img) {
  let h = 0x811c9dc5 >>> 0;
  for (let i = 0; i < img.data.length; i += 4) {
    h ^= img.data[i]; h = Math.imul(h, 0x01000193) >>> 0;
    h ^= img.data[i + 1]; h = Math.imul(h, 0x01000193) >>> 0;
    h ^= img.data[i + 2]; h = Math.imul(h, 0x01000193) >>> 0;
  }
  return ('00000000' + h.toString(16)).slice(-8);
}
export function downsample(img) {
  const { width: W, height: H, ss } = img;
  const w = W / ss, h = H / ss;
  const out = new Uint8ClampedArray(w * h * 4);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    let r = 0, g = 0, b = 0;
    for (let dy = 0; dy < ss; dy++) for (let dx = 0; dx < ss; dx++) {
      const o = (((y * ss + dy) * W) + (x * ss + dx)) * 4;
      r += img.data[o]; g += img.data[o + 1]; b += img.data[o + 2];
    }
    const n = ss * ss, o = (y * w + x) * 4;
    out[o] = r / n; out[o + 1] = g / n; out[o + 2] = b / n; out[o + 3] = 255;
  }
  return { data: out, width: w, height: h, ss: 1, down: w, dwidth: h };
}
