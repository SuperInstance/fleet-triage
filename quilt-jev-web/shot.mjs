import { chromium } from '/app/node_modules/playwright/index.mjs';
const b = await chromium.launch({ executablePath: '/workspace/.home/.cache/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-linux64/chrome-headless-shell', args: ['--no-sandbox'] });
const pg = await b.newPage({ viewport: { width: 1500, height: 1000 }, deviceScaleFactor: 2 });
const errs = [];
pg.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
pg.on('pageerror', (e) => errs.push('PAGEERROR ' + e.message));
await pg.goto('http://127.0.0.1:8171/', { waitUntil: 'networkidle' });
await pg.waitForFunction(() => window.__ready === true, { timeout: 10000 });
await pg.waitForTimeout(400);
const grab = async (name) => { await pg.screenshot({ path: `out/ui-${name}.png` }); console.log('shot', name); };
await grab('1-default');
// switch to entropy.relief -- the source's idea, as a labelled projection
await pg.locator('label[data-p="entropy.relief"]').click(); await pg.waitForTimeout(250);
await grab('2-entropy-relief');
await pg.locator('label[data-p="margin.relief"]').click(); await pg.waitForTimeout(250);
await grab('3-margin-relief');
await pg.locator('label[data-p="quilt.stitch"]').click(); await pg.waitForTimeout(200);
// fold the grid -- same field, coarser dial
await pg.locator('#folds button', { hasText: '6×4' }).first().click(); await pg.waitForTimeout(300);
await grab('4-fold-6x4');
await pg.locator('#folds button', { hasText: '1×1' }).first().click(); await pg.waitForTimeout(300);
await grab('5-fold-1x1');
await pg.locator('#folds button', { hasText: 'full' }).first().click(); await pg.waitForTimeout(200);
await pg.locator('#folds button', { hasText: 'full' }).first().click(); await pg.waitForTimeout(200);
// hover a CONTESTED cell and read the readout
const chip = pg.locator('#chips .chip').first();
const txt = await chip.textContent();
await chip.click(); await pg.waitForTimeout(300);
const readout = await pg.locator('#readout').innerText();
await pg.screenshot({ path: 'out/ui-6-readout.png' });
const head = await pg.locator('header').innerText();
console.log('--- header ---\n' + head);
console.log('--- clicked chip: ' + txt + ' ---\n' + readout);
console.log('--- console errors: ' + (errs.length ? errs.join(' | ') : 'NONE'));
await b.close();
