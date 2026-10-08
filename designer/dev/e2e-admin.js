#!/usr/bin/env node
// admin.html "Custom Designs" smoke test against the local stand-in (dev/local-caddy.py on :8095).
// Run: NODE_PATH=$(npm root -g) node dev/e2e-admin.js
const puppeteer = require('puppeteer');
const BASE = 'http://127.0.0.1:8095';
const TOKEN = 'devtoken123';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', name, extra); };

async function post(path, body, tok) {
  const r = await fetch(BASE + '/designer/api' + path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(tok ? { Authorization: 'Bearer ' + tok } : {}) }, body: JSON.stringify(body) });
  return r.json();
}

(async () => {
  // Seed: two users, three factions
  const stamp = Date.now().toString().slice(-5);
  const u1 = 'adm1' + stamp, u2 = 'adm2' + stamp;
  const t1 = (await post('/register', { username: u1, password: 'secret1' })).token;
  const t2 = (await post('/register', { username: u2, password: 'secret1' })).token;
  const L = () => String.fromCharCode(65 + Math.floor(Math.random() * 26));
  const fa = await post('/factions', { name: 'Hollow Choir', acronym: 'H' + L() + L() }, t1);
  const fb = await post('/factions', { name: 'Ember Court', acronym: 'E' + L() + L() }, t1);
  const fc = await post('/factions', { name: 'Tidewrack', acronym: 'T' + L() + L() }, t2);
  console.log('seeded', [fa, fb, fc].map(f => f.name + ':' + (f.id || f.error)).join(' '));

  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  const dialogs = [];
  page.on('dialog', d => { dialogs.push(d.message()); d.accept(); });

  await page.goto(BASE + '/admin.html', { waitUntil: 'networkidle0' });
  await page.$eval('#server-url', e => e.value = '');
  await page.$eval('#server-url', (e, v) => e.value = v, BASE);
  await page.type('#owner-token', TOKEN);
  await page.evaluate(() => signIn());
  await sleep(1500);
  await page.evaluate(() => { showSection('customdesigns'); loadDesignerData(); });
  await sleep(1000);
  const listText = () => page.$eval('#designer-users-list', e => e.innerText);

  let t = await listText();
  check('users listed, collapsed', t.includes(u1) && t.includes(u2) && !t.includes('Hollow Choir'), '');

  await page.evaluate(u => toggleDesignerUser(u), u1); await sleep(200);
  t = await listText();
  check('expand shows factions', t.includes('Hollow Choir') && t.includes('Ember Court') && !t.includes('Tidewrack'));
  await page.evaluate(u => toggleDesignerUser(u), u1); await sleep(200);
  check('collapse hides factions', !(await listText()).includes('Hollow Choir'));

  await page.type('#designer-search', 'tidewr'); await sleep(300);
  t = await listText();
  check('search by faction shows owner opened', t.includes(u2) && t.includes('Tidewrack') && !t.includes(u1), t.replace(/\n/g, ' | ').slice(0, 120));
  await page.$eval('#designer-search', e => { e.value = ''; e.dispatchEvent(new Event('input')); }); await sleep(300);

  check('no checkboxes before Select', (await page.$$('.designer-faction-cb, .designer-user-cb')).length === 0);
  await page.click('#designer-select-btn'); await sleep(300);
  const bar = await page.$eval('#designer-bulk-bar', e => getComputedStyle(e).display);
  check('Select shows checkboxes + bottom bar', (await page.$$('.designer-faction-cb')).length >= 3 && bar !== 'none', 'bar=' + bar);

  // Tick one faction of u1 and delete via bulk bar
  await page.$eval(`.designer-faction-cb[data-fid="${fb.id}"]`, e => e.click());
  await page.click('#designer-bulk-delete-btn'); await sleep(1200);
  t = await listText();
  check('bulk delete removed checked faction only', !t.includes('Ember Court') && t.includes('Hollow Choir') && t.includes('Tidewrack'), dialogs.slice(-1)[0] || '');

  // Tick user u2 -> removes user and their factions
  await page.$eval(`.designer-user-cb[data-user="${u2}"]`, e => e.click());
  await page.click('#designer-bulk-delete-btn'); await sleep(1200);
  t = await listText();
  check('deleting checked user removes user + factions', !t.includes(u2) && !t.includes('Tidewrack'), dialogs.slice(-1)[0] || '');
  const login2 = await post('/login', { username: u2, password: 'secret1' });
  check('deleted user can no longer log in', !login2.token);

  await page.click('#designer-select-btn'); await sleep(200);

  // Single delete button
  await page.evaluate(u => { if (!DESIGNER_EXPANDED.has(u)) toggleDesignerUser(u); }, u1); await sleep(200);
  await page.evaluate((fid) => deleteSingleDesignerFaction(fid, 'Hollow Choir'), fa.id); await sleep(1000);
  check('single Delete removes faction', !(await listText()).includes('Hollow Choir'));

  // Reset password -> log in with "password"
  await page.evaluate(u => resetDesignerPassword(u), u1); await sleep(1000);
  const login1 = await post('/login', { username: u1, password: 'password' });
  check('reset password -> logs in with "password"', !!login1.token, dialogs.slice(-1)[0] || '');

  // Build banner on the Games view
  const fd = await post('/factions', { name: 'Banner Test', acronym: 'B' + L() + L() }, login1.token);
  await post(`/factions/${fd.id}/request`, { type: 'build', text: 'Design complete and ready to execute build for Banner Test', data: {} }, login1.token);
  await page.evaluate(() => typeof loadDesignerBanners === 'function' && loadDesignerBanners()); await sleep(1000);
  const banners = await page.$eval('#designer-banners', e => e.innerText);
  check('build banner shown', /Banner Test/.test(banners), banners.slice(0, 120));

  check('no page errors', errors.length === 0, errors.join(' | '));
  await page.screenshot({ path: '/tmp/designer-smoke/admin.png', fullPage: true });
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  await browser.close();
})().catch(e => { console.error('CRASH', e); process.exit(1); });
