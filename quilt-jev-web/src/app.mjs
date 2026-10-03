// quilt-jev-web :: app.mjs  --- THE BROWSER EXECUTOR.
// The one thing this file is careful about: it does not contain any rendering
// logic. It executes the display list that src/render.mjs produced -- the same
// list verify.mjs rasterises in Node to produce the receipt PNG. If the two
// ever disagreed, the receipt would be a picture of something else.

import { synthGrid } from './synth.mjs';
import { render, DEFAULT_DIALS, PROJECTIONS, DEFAULT_PROJECTION, palette } from './render.mjs';
import { fold, tensorSha, serialize, at, isVoid, jsd, checkInvariants } from './tensor.mjs';
import { Jev, FAILURE, keyPresent } from './jev.mjs';

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));

// ---------------------------------------------------------------- state
const base = synthGrid();               // the fixture. the ONLY data source here.
let baseGrid = base;
let dials = { ...DEFAULT_DIALS, cell: 22 };
let foldW = base.width, foldH = base.height;
const jev = new Jev({ key: null });

function current() { return (foldW === baseGrid.width && foldH === baseGrid.height) ? baseGrid : fold(baseGrid, foldW, foldH); }

// ---------------------------------------------------------------- paint
const cv = $('cv'), ctx = cv.getContext('2d');
function paint() {
  const g = current();
  const d = render(g, dials);
  const dpr = window.devicePixelRatio || 1;
  cv.width = d.width * dpr; cv.height = d.height * dpr;
  // integer-scaled to fill the stage. a quilt rendered at 1x in a 1500px panel
  // is a 34px smudge, and "it is small" is indistinguishable from "it is empty".
  // pixelated + integer scale keeps every band edge exact -- no resampling blur,
  // no lying about where a boundary is.
  const st = $('stage');
  const fit = Math.max(1, Math.min(Math.floor((st.clientWidth - 36) / d.width), Math.floor((st.clientHeight - 36) / d.height)));
  cv.style.width = d.width * fit + 'px'; cv.style.height = d.height * fit + 'px';
  cv.dataset.fit = fit;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  for (const op of d.ops) {            // <- the whole renderer, right here
    if (op.op === 'clear') { ctx.fillStyle = `rgb(${op.c[0]},${op.c[1]},${op.c[2]})`; ctx.fillRect(0, 0, d.width, d.height); continue; }
    ctx.fillStyle = `rgba(${op.c[0]},${op.c[1]},${op.c[2]},${(op.c[3] ?? 255) / 255})`;
    ctx.beginPath();
    op.pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.closePath(); ctx.fill();
  }
  window.__lastDisplay = d;
  header(g, d);
  return d;
}
function header(g, d) {
  $('h-sha').textContent = tensorSha(g);
  $('h-grid').textContent = `${g.width}×${g.height}` + (g.meta.foldedFrom ? ` ← fold of ${g.meta.foldedFrom.width}×${g.meta.foldedFrom.height}@${g.meta.foldedFrom.sha}` : '');
  $('h-cells').textContent = `${g.cells.length - d.stats.void} judged / ${d.stats.void} void`;
  $('h-judg').textContent = g.cells.reduce((a, c) => a + c.history.length, 0);
  $('h-proj').textContent = d.projection.id;
  census(d.stats, g);
  legend(g, d);
  chips(d.stats);
  $('log').textContent = [
    `api key        ${keyPresent() ? 'PRESENT in this browser env' : 'ABSENT — no-key mode'}`,
    `source         ${g.meta.source}`,
    `note           ${g.meta.note || '(live judgments)'}`,
    `failure kinds  ${Object.values(FAILURE).join(' / ')}`,
    `retryable      ${Object.values(FAILURE).filter((k) => k === FAILURE.TRANSPORT).join(' / ')}  (only these are retried)`,
    `invariants     ${checkInvariants(g).length === 0 ? 'all pass' : 'FAIL'}`,
    `content addr   ${tensorSha(g)}`,
  ].join('\n');
}
function census(s, g) {
  const rows = [
    ['settled', s.settled, ''],
    ['open', s.open, ''],
    ['contested', s.contested, 'al'],
    ['overclaim', s.overclaim, 'am'],
    ['void', s.void, 'vd'],
  ];
  $('census').innerHTML = rows.map(([k, v, c]) =>
    `<tr class="${c}"><td>${k}</td><td class="n">${v}</td></tr>`).join('')
    + (s.swallowed ? `<tr class="am"><td>· swallowed by fold</td><td class="n">${s.swallowed}</td></tr>` : '')
    + `<tr class="vd"><td>multi-judged</td><td class="n">${s.history}</td></tr>`;
}
function legend(g, d) {
  $('legend').innerHTML = g.labels.map((l) => {
    let sum = 0, n = 0;
    for (const c of g.cells) if (c.probabilities && c.probabilities[l] !== undefined) { sum += c.probabilities[l]; n++; }
    return `<tr><td><span class="sw" style="background:${d.pal[l]}"></span>${esc(l)}</td><td class="n">${n ? (sum / n).toFixed(2) : '—'}</td></tr>`;
  }).join('');
}
function chips(s) {
  const list = [...s.contestedCells.map((c) => [c, 'contested']), ...s.overclaimCells.map((c) => [c, 'overclaim'])];
  $('chips').innerHTML = list.length
    ? list.map(([c, k]) => `<span class="chip ${k === 'contested' ? 'al' : ''}" data-x="${c[0]}" data-y="${c[1]}">${k} ${c[0]},${c[1]}</span>`).join('')
    : '<span class="k">none in this view</span>';
  $('chips').querySelectorAll('.chip').forEach((el) => el.onclick = () => {
    hoverCell(at(current(), +el.dataset.x, +el.dataset.y));
    ctx.strokeStyle = '#ffd640'; ctx.lineWidth = 2; ctx.strokeRect(+el.dataset.x * (dials.cell + dials.gap) + dials.gap - 2, +el.dataset.y * (dials.cell + dials.gap) + dials.gap - 2, dials.cell + 4, dials.cell + 4);
  });
}

// ---------------------------------------------------------------- readout
function hoverCell(cellObj) {
  const g = current(), d = window.__lastDisplay, c = cellObj || null;
  if (!c) { $('readout').innerHTML = '<span class="k">hover a patch.</span>'; return; }
  if (isVoid(c)) {
    $('readout').innerHTML = `<div class="h">cell(${c.x},${c.y}) · VOID</div>
      <div>never judged. there is no distribution here, and that is not the same as a
      distribution of zeros — this cell is excluded from every mean, every colour, every
      count, and it is counted on its own line.</div>`;
    return;
  }
  const bands = Object.keys(c.probabilities).sort().map((l) => [l, c.probabilities[l]]).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
  const w = 210;
  $('readout').innerHTML = `
    <div class="h">cell(${c.x},${c.y}) · ${esc(c.choice).toUpperCase()} · ${c.history.length > 1 ? `RANK ${c.history.length}` : 'single judgment'}</div>
    <div class="bars">${bands.map(([l, p]) =>
      `<div><span class="sw" style="background:${d.pal[l]}"></span><span style="width:64px">${esc(l)}</span>
       <span class="bar" style="width:${(p * w).toFixed(0)}px;background:${d.pal[l]}"></span>
       <span class="num">${p.toFixed(3)}</span></div>`).join('')}</div>
    <table style="margin-top:8px">
      <tr><td>entropy</td><td class="n">${c.entropy.toFixed(3)}</td><td style="color:#8a8f98">bits, /${Math.log2(c.labelSet.length).toFixed(2)} max</td></tr>
      <tr><td>margin</td><td class="n">${c.margin.toFixed(3)}</td><td style="color:#8a8f98">top1 − top2, decided-ness</td></tr>
      <tr><td>confidence</td><td class="n">${c.confidence.toFixed(3)}</td><td style="color:#8a8f98">JEV's own field</td></tr>
      <tr><td>p(argmax)</td><td class="n">${c.pArgmax.toFixed(3)}</td><td style="color:#8a8f98">from the map</td></tr>
      <tr><td style="color:${c.overclaim > 0 ? '#e83e2c' : ''}">overclaim</td>
          <td class="n" style="color:${c.overclaim > 0 ? '#e83e2c' : ''}">${c.overclaim > 0 ? '+' : ''}${(c.overclaim).toFixed(3)}</td>
          <td style="color:#8a8f98">${c.overclaim > 0 ? 'confidence > p(argmax) — the record contradicts itself' : 'no contradiction'}</td></tr>
    </table>
    ${c.history.length > 1 ? `<div class="h" style="margin-top:10px">HISTORY — ${c.history.length} judgments, none averaged</div>
      <table>${c.history.map((h, i) => {
        const prev = i ? c.history[i - 1] : null;
        const dj = prev ? jsd(prev.probabilities, h.probabilities) : null;
        return `<tr><td style="color:#8a8f98">${esc(h.judge)}</td><td>${esc(h.choice)}</td>
          <td class="n">${h.margin.toFixed(2)}</td><td class="n">${h.entropy.toFixed(2)}</td>
          <td class="n" style="color:${dj === null ? '#8a8f98' : dj > 0.03 ? '#e83e2c' : '#5fb87a'}">${dj === null ? '—' : 'JSD ' + dj.toFixed(3)}</td></tr>`;
      }).join('')}</table>` : ''}
    ${c.block ? `<div class="k" style="margin-top:8px">FOLD BLOCK · ${c.block.n} cells (${c.block.judged} judged) · spread ${c.block.spread.toFixed(3)} · contested inside ${c.block.contestedInside}</div>` : ''}`;
}
cv.onmousemove = (e) => {
  const d = window.__lastDisplay; if (!d) return;
  const r = cv.getBoundingClientRect();
  const x = Math.floor((e.clientX - r.left) * (d.width / r.width) - d.dials.gap) / (d.dials.cell + d.dials.gap);
  const y = Math.floor((e.clientY - r.top) * (d.height / r.height) - d.dials.gap) / (d.dials.cell + d.dials.gap);
  const g = current();
  if (x < 0 || y < 0 || x >= g.width || y >= g.height) return;
  hoverCell(at(g, Math.floor(x), Math.floor(y)));
};

// ---------------------------------------------------------------- controls
$('proj').innerHTML = Object.values(PROJECTIONS).map((p) =>
  `<label data-p="${p.id}"><input type="radio" name="p" ${p.id === DEFAULT_PROJECTION ? 'checked' : ''}>
   <span><b>${p.id}</b> — relief:${p.relief} grain:${p.grain} history:${p.carriesHistory ? 'yes' : 'no'}<i>${p.blurb}</i></span></label>`).join('');
$('proj').onchange = (e) => {
  if (!e.target.dataset && !e.target.closest) return;
  const lab = e.target.closest('label'); if (!lab) return;
  dials.projection = lab.dataset.p;
  [...$('proj').children].forEach((c) => c.classList.toggle('sel', c === lab));
  paint();
};
[...$('proj').children].forEach((c) => c.classList.toggle('sel', c.dataset.p === DEFAULT_PROJECTION));

$('d-cell').oninput = (e) => { dials.cell = +e.target.value; $('v-cell').textContent = dials.cell + 'px'; paint(); };
$('d-grain').oninput = (e) => { dials.grain = +e.target.value; $('v-grain').textContent = dials.grain.toFixed(2); paint(); };
$('folds').innerHTML = [[base.width, base.height], [6, 4], [4, 2], [3, 2], [1, 1]]
  .filter(([w, h]) => w <= base.width && h <= base.height && !(w === base.width && h === base.height))
  .map(([w, h]) => `<button data-f="${w}x${h}">${w}×${h}</button>`).join('') + `<button data-f="${base.width}x${base.height}">full ${base.width}×${base.height}</button>`;
$('folds').onclick = (e) => {
  const b = e.target.closest('button'); if (!b) return;
  [foldW, foldH] = b.dataset.f.split('x').map(Number);
  $('v-fold').textContent = `${foldW}×${foldH}`;
  paint();
};
$('b-stitch').onclick = () => { dials.stitch = !dials.stitch; $('b-stitch').textContent = 'stitch: ' + (dials.stitch ? 'on' : 'off'); paint(); };
$('b-void').onclick = () => { dials.showVoid = !dials.showVoid; $('b-void').textContent = 'void: ' + (dials.showVoid ? 'shown' : 'hidden'); paint(); };
$('b-png').onclick = () => {
  const d = window.__lastDisplay;
  const a = document.createElement('a');
  a.download = `quilt-${d.projection.id}-${d.width}x${d.height}.png`; a.href = cv.toDataURL('image/png'); a.click();
};
$('b-json').onclick = () => {
  const blob = new Blob([serialize(current())], { type: 'application/json' });
  const a = document.createElement('a');
  a.download = `quilt-${current().width}x${current().height}-${tensorSha(current())}.json`;
  a.href = URL.createObjectURL(blob); a.click();
};

// the banner is the LAST place the project's central failure mode can hide, so
// it is the loudest thing on the page and it states the distinction in words.
$('banner').className = 'banner ' + (keyPresent() ? 'key' : 'nokey');
$('banner').innerHTML = keyPresent()
  ? '<b>API KEY PRESENT.</b> Live judgments would be fetched by pressing Ask; this build ships the fixture so the surface is inspectable offline.'
  : '<b>NO API KEY — THIS IS NOT ZEROS.</b> The grid below is a hand-built <b>synthetic fixture</b> ' +
    '(<code>source: synthetic</code>, in the header, in the exported tensor, and in this sentence). ' +
    'A cell with no judgment is drawn <b>hatched and colourless</b> and counted on its own line; it can never be ' +
    'mistaken for a distribution of zeros, which would be coloured, banded and lit. ' +
    `${current().cells.length} cells, <b>${current().cells.filter(isVoid).length}</b> of them never judged.`;

$('v-cell').textContent = dials.cell + 'px';
$('v-grain').textContent = dials.grain.toFixed(2);
$('v-fold').textContent = `${foldW}×${foldH}`;
paint();
addEventListener('resize', () => paint());
window.__ready = true;
