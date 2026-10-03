// big-render the same op list so the craft is inspectable
import fs from 'node:fs';
import { synthGrid } from './src/synth.mjs';
import { render, DEFAULT_DIALS, PROJECTIONS } from './src/render.mjs';
import { rasterize, downsample, pixelHash } from './src/raster.mjs';
import { encodePNG } from './src/png.mjs';
const g = synthGrid();
const which = process.argv[2] || 'quilt.stitch';
const cell = +(process.argv[3] || 64);
const d = render(g, { ...DEFAULT_DIALS, cell, gap: 2, projection: which });
fs.writeFileSync(`out/big-${which}.png`, encodePNG(downsample(rasterize(d))));
console.log(which, cell, 'px', pixelHash(rasterize(d)), 'stats', JSON.stringify(d.stats));
