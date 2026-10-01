// Feed voxelglyph's provable collision pair through syzygy-lattice's own band+class logic.
import { RAMPS } from './src/codec.mjs';

const luma = (r,g,b) => ((77*r + 150*g + 29*b) >> 8) & 0xff;   // BT.601, the port's weights
const BANDS = 10;

// voxelglyph FINDINGS.md: these two are 403 RGB units apart and both luma 140.
const A = [0,240,0], B = [255,60,255];

function flatCell(rgb) {
  const mean = luma(...rgb);
  return { mean, band: Math.min(BANDS-1, (mean*BANDS) >> 8), cls: 'flat' };
}
const a = flatCell(A), b = flatCell(B);
const glyphA = RAMPS[a.cls][a.band], glyphB = RAMPS[b.cls][b.band];

console.log(`  A = rgb(${A})  luma ${a.mean}  band ${a.band}  class ${a.cls}  -> "${glyphA}"`);
console.log(`  B = rgb(${B})  luma ${b.mean}  band ${b.band}  class ${b.cls}  -> "${glyphB}"`);
console.log('');
console.log(`  distance in RGB: ${Math.hypot(A[0]-B[0], A[1]-B[1], A[2]-B[2]).toFixed(1)} units`);
console.log(`  identical glyph after the lattice's own encoding: ${glyphA === glyphB ? 'YES' : 'no'}`);
console.log('');
console.log('  The lattice added ORIENTATION as a second channel and its pins verify that');
console.log('  channel. The BRIGHTNESS channel is still BT.601, still rank-one, and still');
console.log('  collides. Two colours 403 apart encode to the same character.');
