#!/usr/bin/env node
// Map designer: per-image "Move" + bulk "Select" mode.
// Run against local stand-in:  BASE=http://127.0.0.1:8395 NODE_PATH=$(npm root -g) node dev/e2e-image-move.js
// Or against live (read-write on a throwaway user + map): BASE=https://cwo.freeddns.org node dev/e2e-image-move.js
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');
const BASE = process.env.BASE || 'http://127.0.0.1:8395';
const GLYPHS = path.join(__dirname, '..', 'www', 'glyphs');
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', name, extra); };

(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1000 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  page.on('dialog', d => d.accept());

  await page.goto(BASE + '/designer/', { waitUntil: 'networkidle0' });
  const user = 'mv' + Date.now().toString().slice(-7);
  const api = (method, url, body, ct) => page.evaluate(async (method, url, body, ct, tok) => {
    const headers = {};
    if (tok) headers.Authorization = 'Bearer ' + tok;
    let payload;
    if (ct === 'b64png') { headers['Content-Type'] = 'image/png'; payload = Uint8Array.from(atob(body), c => c.charCodeAt(0)); }
    else if (body) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
    const r = await fetch(url, { method, headers, body: payload });
    return r.json();
  }, method, url, body || null, ct || null, global.TOK || null);

  global.TOK = (await api('POST', '/designer/api/register', { username: user, password: 'secret1' })).token;
  const map = await api('POST', '/designer/api/maps', { name: 'Move Test ' + user });
  const mid = map.id || (map.map && map.map.id);
  check('map created', !!mid, JSON.stringify(map).slice(0, 120));

  const pngs = ['chevron.png', 'dragon.png', 'thorns.png', 'chevron.png'];
  const imgIds = [];
  for (const f of pngs) {
    const r = await api('POST', '/designer/api/images', fs.readFileSync(path.join(GLYPHS, f)).toString('base64'), 'b64png');
    imgIds.push(r.id);
  }
  check('images uploaded', imgIds.every(Boolean), JSON.stringify(imgIds));
  const rid = () => Math.random().toString(36).slice(2, 10);
  const ops = [
    { op: 'addRow', path: 'images.items', row: { id: rid(), label: 'Alpha', image: imgIds[0] } },
    { op: 'addRow', path: 'images.items', row: { id: rid(), label: 'Bravo', image: imgIds[1] } },
    { op: 'addRow', path: 'images.items', row: { id: rid(), label: 'Charlie', image: imgIds[2] } },
    { op: 'addRow', path: 'images.items', row: { id: rid(), label: 'NoPic', image: null } },
    { op: 'addRow', path: 'glyphs.rows', row: { id: rid(), name: 'Existing glyph', image: imgIds[3], desc: 'x' } }
  ];
  await api('POST', `/designer/api/maps/${mid}/patch`, { ops });
  const getMap = async () => { const m = await api('GET', `/designer/api/maps/${mid}`); return m.design || (m.map && m.map.design) || m; };

  await page.evaluate(t => localStorage.setItem('cw_designer_token', t), global.TOK);
  const open = async sec => { await page.goto(`${BASE}/designer/#/map/${mid}/section/${sec}`, { waitUntil: 'networkidle0' }); await page.reload({ waitUntil: 'networkidle0' }); await sleep(800); };
  const buttons = text => page.$$eval('button', (bs, text) => bs.filter(b => b.textContent.trim() === text && b.offsetParent !== null).length, text);
  const clickBtn = (text, nth = 0) => page.evaluate((text, nth) => { const b = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === text && b.offsetParent !== null)[nth]; if (b) b.click(); return !!b; }, text, nth);
  const menuTargets = () => page.$$eval('.sx-imgmove-menu button', bs => bs.map(b => b.textContent.trim()));
  const shot = n => page.screenshot({ path: `/tmp/imgmove-${n}.png`, fullPage: true });

  // ---- Single move ----
  await open('images');
  check('Select button shown', (await buttons('Select')) === 1);
  check('Move button on each row WITH a picture (3, not the empty row)', (await page.$$('.sx-imgmove-btn')).length === 3);
  await page.evaluate(() => document.querySelectorAll('.sx-imgmove-btn')[1].click());
  await sleep(200); await shot('1-single-menu');
  const t1 = await menuTargets();
  check('menu lists the OTHER sections + Cancel', JSON.stringify(t1) === JSON.stringify(['Bitmaps', 'Map Glyphs', 'Tokens', 'Cancel']), JSON.stringify(t1));
  await clickBtn('Cancel'); await sleep(200);
  check('Cancel closes menu', (await page.$$('.sx-imgmove-menu')).length === 0);
  await page.evaluate(() => document.querySelectorAll('.sx-imgmove-btn')[1].click()); await sleep(150);
  await page.keyboard.press('Escape'); await sleep(150);
  check('Esc closes menu', (await page.$$('.sx-imgmove-menu')).length === 0);
  await page.evaluate(() => document.querySelectorAll('.sx-imgmove-btn')[1].click()); await sleep(150);
  await page.mouse.click(5, 5); await sleep(150);
  check('click outside closes menu', (await page.$$('.sx-imgmove-menu')).length === 0);
  let d = await getMap();
  check('nothing moved after cancels', d.images.items.length === 4 && d.glyphs.rows.length === 1);

  await page.evaluate(() => document.querySelectorAll('.sx-imgmove-btn')[1].click()); await sleep(150);
  await page.evaluate(() => document.querySelector('.sx-imgmove-menu [data-move-to="glyphs"]').click());
  await sleep(1500);
  check('menu gone after move', (await page.$$('.sx-imgmove-menu')).length === 0);
  d = await getMap();
  check('Bravo removed from Board Images', d.images.items.map(i => i.label).join() === 'Alpha,Charlie,NoPic', d.images.items.map(i => i.label).join());
  const g = d.glyphs.rows.find(r => r.name === 'Bravo');
  check('Bravo added to Map Glyphs as new row with same picture', !!g && g.image === imgIds[1] && d.glyphs.rows.length === 2);

  // ---- Bulk move ----
  await clickBtn('Select'); await sleep(300);
  check('selection mode visually distinct', (await page.$$('.sx-select-mode')).length > 0 && (await page.$$('.sx-imgmove-bar.sx-selecting')).length === 1);
  check('checkbox per picture (2)', (await page.$$('.sx-imgmove-check')).length === 2);
  check('per-row Move hidden in select mode', (await page.$$('.sx-imgmove-btn')).length === 0);
  check('Move disabled with none ticked', await page.evaluate(() => [...document.querySelectorAll('.sx-imgmove-bar button')].find(b => b.textContent.startsWith('Move')).disabled));
  await page.evaluate(() => document.querySelectorAll('.sx-imgmove-check').forEach(c => c.click())); await sleep(200);
  check('Move (2) shown', (await buttons('Move (2)')) === 1);
  await shot('2-select-mode');
  await clickBtn('Move (2)'); await sleep(200);
  check('bulk menu title', (await page.$eval('.sx-imgmove-menu h3', e => e.textContent)) === 'Move 2 images to:');
  await shot('3-bulk-menu');
  await page.evaluate(() => document.querySelector('.sx-imgmove-menu [data-move-to="tokens"]').click());
  await sleep(1500);
  d = await getMap();
  check('both removed from Board Images', d.images.items.map(i => i.label).join() === 'NoPic', d.images.items.map(i => i.label).join());
  const toks = d.tokens.rows;
  check('both added to Tokens (blank placeholder replaced)', toks.length === 2 && toks.map(t => t.name).join() === 'Alpha,Charlie' && toks[0].image === imgIds[0] && toks[1].image === imgIds[2], JSON.stringify(toks.map(t => [t.name, t.image])));
  check('selection cleared after move', (await page.$$('.sx-imgmove-check')).length === 0 && (await page.$$('.sx-select-mode')).length === 0);
  await shot('4-after-bulk');

  // ---- Select-mode Cancel, then move from the Tokens section ----
  await open('tokens');
  check('tokens: Move buttons present', (await page.$$('.sx-imgmove-btn')).length === 2);
  await clickBtn('Select'); await sleep(200);
  await page.evaluate(() => document.querySelector('.sx-imgmove-check').click());
  await clickBtn('Cancel'); await sleep(200);
  check('select-mode Cancel leaves mode and clears ticks', (await page.$$('.sx-imgmove-check')).length === 0);
  await clickBtn('Select'); await sleep(200);
  check('re-entering select mode starts with nothing ticked', (await page.$$eval('.sx-imgmove-check', cs => cs.filter(c => c.checked).length)) === 0);
  await clickBtn('Select all'); await sleep(200);
  await clickBtn('Move (2)'); await sleep(200);
  await page.evaluate(() => document.querySelector('.sx-imgmove-menu [data-move-to="bitmaps"]').click());
  await sleep(1500);
  d = await getMap();
  check('tokens -> bitmaps moved both', d.bitmaps.items.filter(b => b.image).length === 2, JSON.stringify(d.bitmaps.items.map(b => b.image)));
  check('tokens keeps one blank row', d.tokens.rows.length === 1 && !d.tokens.rows[0].image);
  await open('bitmaps'); await shot('5-bitmaps');
  check('bitmaps: Move button per bitmap', (await page.$$('.sx-imgmove-btn')).length === 2);

  check('no page errors', errors.length === 0, errors.join(' | '));
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed; map id ${mid}, user ${user}`);
  await browser.close();
  process.exit(results.every(Boolean) ? 0 : 1);
})().catch(e => { console.error(e); process.exit(2); });
