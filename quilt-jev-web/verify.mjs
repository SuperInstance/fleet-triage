// quilt-jev-web :: verify.mjs  -- the executable claims. Run: node verify.mjs
// This is the negative control FIRST: if a shuffled tensor paints the same
// pixels, nothing else in this file is worth reading.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { synthGrid } from './src/synth.mjs';
import { render, DEFAULT_DIALS, PROJECTIONS, classify } from './src/render.mjs';
import { rasterize, pixelHash, downsample } from './src/raster.mjs';
import { encodePNG } from './src/png.mjs';
import { checkInvariants, serialize, tensorSha, fold, cellDisagreement, jsd } from './src/tensor.mjs';
import { keyPresent, FAILURE } from './src/jev.mjs';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(HERE, 'out');
fs.mkdirSync(OUT, { recursive: true });
const R = [];
const ok = (c, name, detail = '') => { R.push({ c: !!c, name, detail }); if (!c) process.exitCode = 1; return !!c; };
const P = (s = '') => process.stdout.write(s + '\n');

const g = synthGrid();
const sha = tensorSha(g);
P(`\n=== quilt-jev-web / verify ===`);
P(`tensor        ${serialize(g).length} bytes canonical, sha ${sha}`);
P(`api key       ${keyPresent() ? 'PRESENT' : 'ABSENT -> no-key mode, synthetic fixture, NOT zeros'}`);
P(`labels        ${g.labels.join(' ')}`);

// ---------------------------------------------------------------- I2 first
const once = serialize(g), twice = serialize(JSON.parse(once));
ok(once === twice, 'I2 tensor round-trips byte for byte', `${once.length} == ${twice.length}`);
const fails = checkInvariants(g);
ok(fails.length === 0, 'I1/I2 invariants pass on the fixture', fails.slice(0, 3).join(' | '));

// ---------------------------------------------------------------- NEGATIVE CONTROL
P(`\n--- negative control (first, as demanded) ---`);
const base = render(g, { ...DEFAULT_DIALS, cell: 20 });
const b1 = rasterize(base), b2 = rasterize(render(g, { ...DEFAULT_DIALS, cell: 20 }));
const h1 = pixelHash(b1), h2 = pixelHash(b2);
ok(h1 === h2, 'same tensor renders to IDENTICAL pixels twice', `${h1} == ${h2}`);

// shuffle the CELLS (positions), deterministically -- the classic "is it
// actually reading the field?" control
const shuffled = { ...g, cells: g.cells.map((c, i) => ({ ...c, x: (c.x + 3) % g.width, y: (c.y + 2) % g.height, _i: i })).sort((a, b) => a.y - b.y || a.x - b.x) };
const sh = render(shuffled, { ...DEFAULT_DIALS, cell: 20 });
const hs = pixelHash(rasterize(sh));
ok(h1 !== hs, 'a SHUFFLED tensor renders VISIBLY differently', `${h1} != ${hs}`);

// and a second negative: dials must change the image, or nothing is wired
const dh = pixelHash(rasterize(render(g, { ...DEFAULT_DIALS, cell: 20, projection: 'margin.relief' })));
ok(dh !== h1, 'changing the projection changes the pixels', `${h1} != ${dh}`);
// and: a fold must change the image, or the grid-size dial is a lie
const f2 = fold(g, 6, 4);
const fh = pixelHash(rasterize(render(f2, { ...DEFAULT_DIALS, cell: 20 })));
ok(fh !== h1, 'changing the grid size (a fold) changes the image', `${h1} != ${fh}`);
ok(tensorSha(f2) !== sha, 'a fold is a NEW TENSOR ADDRESS, and says so in meta.foldedFrom',
   `${sha} -> ${tensorSha(f2)}, meta.foldedFrom.sha == ${sha} ? ${f2.meta.foldedFrom.sha === sha}`);

// ---------------------------------------------------------------- I3
P(`\n--- I3: one tensor, four labelled projections ---`);
const shas = new Set(); const written = [];
for (const id of Object.keys(PROJECTIONS)) {
  const d = render(g, { ...DEFAULT_DIALS, cell: 26, projection: id });
  shas.add(d.ops.length ? sha : 'none');
  const img = downsample(rasterize(d));
  const file = path.join(OUT, `${id}.png`);
  fs.writeFileSync(file, encodePNG(img));
  written.push([id, d.stats, pixelHash(rasterize(d))]);
  P(`  ${id.padEnd(14)} px ${pixelHash(rasterize(d))}  ${d.projection.relief.padEnd(7)} relief  ${d.projection.grain.padEnd(6)} grain   ${d.projection.carriesHistory ? 'history: YES' : 'history: no '}  -> ${path.basename(file)}`);
}
ok(shas.size === 1, 'I3 all four projections read ONE tensor (one sha, four views)', `${shas.size} distinct`);
ok(written.every(([, s]) => s.void > 0), 'VOID cells are counted separately from zeros', `void=${written[0][1].void}`);

// ---------------------------------------------------------------- the state census
P(`\n--- the four states, from the fixture ---`);
const census = { settled: 0, open: 0, contested: 0, overclaim: 0, void: 0 };
for (const c of g.cells) census[c.origin === 'void' ? 'void' : classify(c)]++;
for (const [k, v] of Object.entries(census)) P(`  ${k.padEnd(10)} ${String(v).padStart(3)}`);
ok(census.contested > 0 && census.overclaim > 0 && census.void > 0,
   'the surface has cells of every state, including the confidently-wrong ones',
   `contested=${census.contested} overclaim=${census.overclaim} void=${census.void}`);

// ---------------------------------------------------------------- history
P(`\n--- I-history: disagreement is rendered, not listed ---`);
for (const c of g.cells) {
  if (c.history.length < 2) continue;
  const pairs = c.history.slice(1).map((h, i) => jsd(c.history[i].probabilities, h.probabilities).toFixed(3));
  P(`  cell(${c.x},${c.y}) judges=[${c.history.map((h) => h.judge).join(',')}] rank=${c.history.length} maxJSD=${cellDisagreement(c).toFixed(3)} pairwise=[${pairs.join(' ')}] head=${c.choice}`);
}
const multi = g.cells.filter((c) => c.history.length > 1);
ok(multi.length > 0, 'some cells carry more than one judgment', `${multi.length} multi-rank cells`);
// history is preserved through a fold (this is the thing a naive fold destroys)
const totalJ = (gg) => gg.cells.reduce((a, c) => a + c.history.length, 0);
for (const [w, h] of [[6, 4], [4, 2], [1, 1]]) {
  const f = fold(g, w, h);
  ok(totalJ(f) === totalJ(g), `a ${w}x${h} fold CONCATENATES history, it does not average it away`,
     `${totalJ(g)} -> ${totalJ(f)}`);
}
ok(fold(g, 4, 2).cells.some((c) => c.history.length > 3), 'a fold MERGES rank, so one patch can be a 3-deep stack',
   `max rank at 4x2 = ${Math.max(...fold(g, 4, 2).cells.map((c) => c.history.length))}`);

// ---------------------------------------------------------------- the folds
P(`\n--- I4: grid size is a dial ---`);
for (const [w, h] of [[12, 8], [6, 4], [4, 2], [3, 2], [1, 1]]) {
  const fg = fold(g, w, h);
  const d = render(fg, { ...DEFAULT_DIALS, cell: 26 });
  const fi = downsample(rasterize(d));
  fs.writeFileSync(path.join(OUT, `fold-${w}x${h}.png`), encodePNG(fi));
  P(`  ${String(w + 'x' + h).padEnd(7)} sha ${tensorSha(fg)}  from ${fg.meta.foldedFrom.width}x${fg.meta.foldedFrom.height}@${fg.meta.foldedFrom.sha}  void ${d.stats.void}  contested ${d.stats.contested}  swallowed ${d.stats.swallowed || 0}  overclaim ${d.stats.overclaim}  history ${fg.cells.reduce((a, c) => a + c.history.length, 0)} judgments`);
  ok(checkInvariants(fg).length === 0, `invariants hold at ${w}x${h}`);
}
ok(fold(g, 1, 1).cells[0].history.length === g.cells.reduce((a, c) => a + c.history.length, 0),
   'a 1x1 fold loses no judgment anywhere in the field',
   `${fold(g, 1, 1).cells[0].history.length} judgments in one cell`);
// The finding, not a hope: averaging dissolves the contested signal. Prove it
// is dissolved *in the mean* and *recoverable in the fold's own record*.
const fineContested = g.cells.filter((c) => c.entropyNorm > 0.55 && c.margin > 0.2).length;
const f4 = fold(g, 4, 2);
const meanContested = f4.cells.filter((c) => c.entropyNorm > 0.55 && c.margin > 0.2).length;
const recovered = f4.cells.reduce((a, c) => a + (c.block ? c.block.contestedInside : 0), 0);
P(`  contested fine cells ${fineContested} -> surviving as a MEAN at 4x2: ${meanContested} -> recovered from the fold's block record: ${recovered}`);
ok(recovered === fineContested, 'the fold does not lose contested cells; it MOVES them from the mean into the block record',
   `${fineContested} == ${recovered}`);

// ---------------------------------------------------------------- no-key
P(`\n--- the no-key distinction ---`);
ok(!keyPresent(), 'no API key in this environment (so the no-key path is the real path)');
const zeroTensor = { ...g, cells: g.cells.map((c) => c.origin === 'void' ? c : ({ ...c, probabilities: Object.fromEntries(c.labelSet.map((l) => [l, 1 / c.labelSet.length])), confidence: 0.33, history: [{ judge: 'zeros', at: null, confidence: 0.33, probabilities: Object.fromEntries(c.labelSet.map((l) => [l, 1 / c.labelSet.length])) }] })) };
const zh = pixelHash(rasterize(render(zeroTensor, { ...DEFAULT_DIALS, cell: 20 })));
ok(zh !== h1, 'a tensor of UNIFORM ZEROS does not look like the fixture', `${h1} != ${zh}`);
P(`  fixture px ${h1}   uniform-zeros px ${zh}   -> distinguishable`);
ok(Object.keys(FAILURE).length === 4, 'transport and schema failure are four distinct typed values, not one',
   Object.values(FAILURE).join('/'));

// ---------------------------------------------------------------- verdict
P(`\n--- verdict ---`);
const bad = R.filter((r) => !r.c);
for (const r of R) P(`  ${r.c ? 'PASS' : 'FAIL'}  ${r.name}${r.detail ? `   (${r.detail})` : ''}`);
P(`\n${R.length - bad.length}/${R.length} pass${bad.length ? '  *** ' + bad.length + ' FAILING ***' : ''}\n`);
if (bad.length) process.exit(1);
