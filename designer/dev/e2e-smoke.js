#!/usr/bin/env node
// Designer smoke test against the REAL local backend (dev/local-caddy.py on :8095).
// Run: NODE_PATH=$(npm root -g) node dev/e2e-smoke.js
const puppeteer = require('puppeteer');
const fs = require('fs');
const BASE = 'http://127.0.0.1:8095/designer/';
const ADMIN = 'http://127.0.0.1:8095/designer/api/admin/devtoken123';
const SHOTS = '/tmp/designer-smoke';
fs.mkdirSync(SHOTS, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const errors = [];
const check = (name, ok, extra = '') => { results.push([ok ? 'PASS' : 'FAIL', name, extra]); console.log(ok ? 'PASS' : 'FAIL', name, extra); };

(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`HTTP ${r.status()} ${r.url()}`); });
  page.on('dialog', d => d.accept());

  const clickText = async (text, sel = 'button') => {
    const ok = await page.evaluate((text, sel) => {
      const el = [...document.querySelectorAll(sel)].find(b => b.textContent.trim().toLowerCase().includes(text.toLowerCase()) && !b.disabled);
      if (el) { el.click(); return true; } return false;
    }, text, sel);
    await sleep(500);
    return ok;
  };
  const bodyText = () => page.evaluate(() => document.body.innerText);
  const shot = n => page.screenshot({ path: `${SHOTS}/${n}.png`, fullPage: true });
  const api = (method, path, body) => page.evaluate(async (method, path, body) => {
    const tok = localStorage.getItem('cw_designer_token') || localStorage.getItem('token') ||
      Object.values(localStorage).find(v => /^[A-Za-z0-9_-]{20,}$/.test(v));
    const r = await fetch('/designer/api' + path, { method, headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + tok }, body: body ? JSON.stringify(body) : undefined });
    return r.json();
  }, method, path, body);
  const adminPost = (path, body) => page.evaluate(async (u, body) => (await fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json(), ADMIN + '/' + path, body);
  const adminGet = path => page.evaluate(async u => (await fetch(u)).json(), ADMIN + '/' + path);

  const user = 'alice' + Date.now().toString().slice(-6);

  // 1. Register / login
  await page.goto(BASE, { waitUntil: 'networkidle0' });
  await clickText('egister');
  await page.type('#username', user); await page.type('#password', 'secret1');
  await clickText('Register'); await sleep(800);
  check('register -> faction list', (await bodyText()).includes('Create New Faction'));
  await clickText('Log out') || await clickText('Logout');
  await page.goto(BASE, { waitUntil: 'networkidle0' });
  await page.type('#username', user); await page.type('#password', 'wrong');
  await clickText('Log in') || await clickText('Login');
  await sleep(600);
  const wrongTxt = await bodyText();
  check('wrong password rejected', !wrongTxt.includes('Create New Faction'), wrongTxt.match(/.*(password|incorrect|wrong).*/i)?.[0] || '');
  await page.$eval('#password', e => e.value = '');
  await page.type('#password', 'secret1');
  await clickText('Log in') || await clickText('Login');
  await sleep(800);
  check('login', (await bodyText()).includes('Create New Faction'));
  errors.length = 0; // the wrong-password 4xx above is expected

  // 2. Create faction
  await clickText('Create New Faction');
  const inputs = await page.$$('.confirm-dialog input');
  const createDisabled = () => page.evaluate(() => [...document.querySelectorAll('.confirm-dialog button')].find(b => b.textContent.trim() === 'Create').disabled);
  check('Create greyed when empty', await createDisabled());
  await inputs[0].type('Shad'); await inputs[1].type('SH');
  check('Create greyed with 4-char name', await createDisabled());
  await clickText('Cancel', '.confirm-dialog button');
  const list1 = await api('GET', '/factions');
  check('cancel saves nothing', list1.factions && list1.factions.length === 0);
  await clickText('Create New Faction');
  const in2 = await page.$$('.confirm-dialog input');
  await in2[0].type('Shadow Court'); await in2[1].type('GC');
  await clickText('Create', '.confirm-dialog button'); await sleep(600);
  check('reserved acronym rejected', (await api('GET', '/factions')).factions.length === 0, (await bodyText()).match(/.*reserved.*/i)?.[0] || '');
  await clickText('Cancel', '.confirm-dialog button');
  await clickText('Create New Faction');
  const in3 = await page.$$('.confirm-dialog input');
  const acr = 'S' + String.fromCharCode(65 + Math.floor(Math.random() * 26)) + String.fromCharCode(65 + Math.floor(Math.random() * 26));
  await in3[0].type('Shadow Court'); await in3[1].type(acr);
  await clickText('Create', '.confirm-dialog button'); await sleep(1200);
  const main = await bodyText();
  check('main page shows name', main.includes('Shadow Court'));
  const font = await page.$eval('.faction-title', e => getComputedStyle(e).fontFamily);
  check('name uses overlay font', /Bohemian/i.test(font), font);
  const labels = await page.$$eval('.section-button', bs => bs.map(b => b.innerText.replace(/\s+/g, ' ')));
  const designLabels = labels.filter(l => !/Build|Simple|Bug|Versions/.test(l));
  check('all sections empty on new faction', designLabels.length >= 10 && designLabels.every(l => /empty/i.test(l)), JSON.stringify(labels));
  check('build label Not ready', /Not Ready/i.test(labels.find(l => /Build/.test(l)) || ''));
  check('Simple Update + Bug Report greyed', await page.$$eval('.section-button', bs => bs.filter(b => /Simple Update|Bug Report/.test(b.innerText)).every(b => b.disabled)));
  await shot('01-main');
  const fid = (await api('GET', '/factions')).factions[0].id;

  // 3. Each section renders without errors; type into first text field of UFA
  const sectionNames = ['Alternate', 'Unique Faction', 'Setup', 'Units', 'Spell Book Req', 'Spellbooks', 'Faction region', 'Tokens', 'Other Custom', 'Menu Design'];
  for (const s of sectionNames) {
    errors.length = 0;
    const ok = await clickText(s, ".section-button"); await sleep(300);
    const onSection = await page.evaluate(() => /\/section\//.test(location.hash) && !document.querySelector(".section-button"));
    await sleep(500);
    const hasExit = await page.evaluate(() => { const b = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Exit to Main'); return b.length && b[b.length - 1].getBoundingClientRect().top > 200 && !document.querySelector(".section-button"); });
    await shot('sec-' + s.replace(/\W+/g, '_'));
    check(`section "${s}" opens, Exit to Main at bottom, no errors`, ok && onSection && hasExit && errors.length === 0, errors.join(' | '));
    await clickText('Exit to Main'); await sleep(500);
  }

  // 4. Autosave: type a UFA name via the UI, reload, check persisted + label edited
  await clickText('Unique Faction', '.section-button'); await sleep(400);
  const firstText = await page.$('input[type=text], input:not([type])');
  await firstText.type('Writhing Darkness');
  await sleep(1200);
  await clickText('Exit to Main'); await sleep(800);
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(800);
  let f = await api('GET', '/factions/' + fid);
  check('UFA name autosaved', f.design.ufa.name === 'Writhing Darkness', f.design.ufa.name);
  const ufaLabel = (await page.$$eval('.section-button', bs => bs.map(b => b.innerText))).find(l => /Unique/.test(l)) || '';
  check('UFA label edited after reload', /edited/i.test(ufaLabel), ufaLabel);

  // 5. Row edit via UI in Units (by-id path) then local state check
  await clickText('Units', '.section-button'); await sleep(400);
  const unitInputs = await page.$$('input[type=text], input:not([type])');
  if (unitInputs.length) { await unitInputs[0].type('Shade'); await sleep(1200); }
  f = await api('GET', '/factions/' + fid);
  check('unit row text autosaved by row id', f.design.units.rows.some(r => Object.values(r).includes('Shade')));
  await clickText('Exit to Main'); await sleep(500);

  // 6. Versions: a change (not addition) in a new session -> new version
  await api('POST', `/factions/${fid}/close-session`, {});
  await api('POST', `/factions/${fid}/patch`, { ops: [{ op: 'set', path: 'ufa.name', value: 'Writhing Dark' }] });
  f = await api('GET', '/factions/' + fid);
  check('change creates version 2', f.current === 2, 'current=' + f.current);
  await api('POST', `/factions/${fid}/close-session`, {});
  const rb = await api('POST', `/factions/${fid}/rollback`, { version: 1 });
  await api('POST', `/factions/${fid}/patch`, { ops: [{ op: 'set', path: 'ufa.name', value: 'Other' }] });
  f = await api('GET', '/factions/' + fid);
  const v3 = f.versions.find(v => v.n === 3);
  check('rollback to 1 then edit -> v3 changed from 1', f.current === 3 && v3 && v3.from === 1, JSON.stringify(v3));
  await api('POST', `/factions/${fid}/delete-version`, { version: 2 });
  await page.goto(BASE + '#/faction/' + fid + '/versions', { waitUntil: 'networkidle0' }); await sleep(800);
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(800);
  await clickText('Versions', '.section-button'); await sleep(800);
  const vt = await bodyText();
  check('versions table shows DELETED', vt.includes('DELETED'));
  await shot('02-versions');
  await clickText('Exit to Main'); await sleep(500);

  // 7. Fill a buildable design through the API, then Execute build via UI
  const d = f.design;
  const ops = [
    { op: 'set', path: 'ufa.phase', value: 'Action' }, { op: 'set', path: 'ufa.type', value: 'Action' }, { op: 'set', path: 'ufa.text', value: 'Do a thing.' },
    { op: 'set', path: 'ufa.hasCost', value: true }, { op: 'set', path: 'ufa.cost', value: 2 },
    { op: 'set', path: 'setup.text', value: 'Start in Asia.' }, { op: 'set', path: 'setup.location', value: 'single' },
    { op: 'set', path: 'setup.earthRegion', value: 'Asia' }, { op: 'set', path: 'setup.libraryRegion', value: 'X' }, { op: 'set', path: 'setup.gate', value: true },
    { op: 'set', path: `setup.units.${d.setup.units[0].id}.name`, value: 'Acolyte' }, { op: 'set', path: `setup.units.${d.setup.units[0].id}.qty`, value: 6 },
  ];
  d.units.rows.forEach((u, i) => {
    if (i === 0) {
      Object.entries({ type: 'Cultist', name: 'Acolyte', silhouette: 'x.webp', qty: 6, costType: 'Fixed', cost: 1, combatType: 'N/A' })
        .forEach(([k, v]) => ops.push({ op: 'set', path: `units.rows.${u.id}.${k}`, value: v }));
    } else ops.push({ op: 'deleteRow', path: 'units.rows', id: u.id });
  });
  d.sbr.rows.forEach((r, i) => ops.push({ op: 'set', path: `sbr.rows.${r.id}.text`, value: 'Req ' + i }));
  d.sb.rows.forEach((r, i) => { ops.push({ op: 'set', path: `sb.rows.${r.id}.name`, value: 'Book ' + i }); ops.push({ op: 'set', path: `sb.rows.${r.id}.type`, value: 'Action' }); ops.push({ op: 'set', path: `sb.rows.${r.id}.text`, value: 'Text ' + i }); });
  const pr = await api('POST', `/factions/${fid}/patch`, { ops });
  if (pr.error) console.log('patch error', pr.error);
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(800);
  const bstat = await page.evaluate(id => window.Rules && (async () => { const r = await fetch('/designer/api/factions/' + id, { headers: { Authorization: 'Bearer ' + (localStorage.getItem('cw_designer_token') || Object.values(localStorage).find(v => /^[A-Za-z0-9_-]{20,}$/.test(v))) } }); const f = await r.json(); return Rules.BUILD_SECTIONS.map(k => k + ':' + Rules.status(k, f.design)); })(), fid);
  console.log('   build statuses:', JSON.stringify(bstat));
  const lbl = (await page.$$eval('.section-button', bs => bs.map(b => b.innerText))).find(l => /^Build/.test(l.trim())) || '';
  check('build label Ready', /Ready/.test(lbl) && !/Not/.test(lbl), lbl);
  await clickText('Build', '.section-button'); await sleep(600);
  await shot('03-build');
  const executed = await clickText('Execute build'); await sleep(800);
  const open = await adminGet('requests?status=open');
  const breq = (open.requests || []).find(r => r.fid === fid && r.type === 'build');
  check('execute build -> build request', executed && !!breq, breq ? breq.text : '');
  check('build request text', breq && breq.text === 'Design complete and ready to execute build for Shadow Court');
  check('label Build Requested', /Build Requested/.test(await bodyText()));
  await clickText('Exit to Main'); await sleep(400);

  // 8. Built -> simple update + update
  f = await api('GET', '/factions/' + fid);
  await adminPost(`factions/${fid}/build-status`, { status: 'built', version: f.current });
  await api('POST', `/factions/${fid}/close-session`, {});
  await api('POST', `/factions/${fid}/patch`, { ops: [{ op: 'set', path: 'ufa.cost', value: 3 }] });
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(800);
  check('Simple Update + Bug Report enabled after build', await page.$$eval('.section-button', bs => bs.filter(b => /Simple Update|Bug Report/.test(b.innerText)).every(b => !b.disabled)));
  await clickText('Simple Update', '.section-button'); await sleep(800);
  await shot('04-simple-update');
  const suTxt = await bodyText();
  check('simple update lists UFA cost 2 -> 3', /UFA Cost/.test(suTxt));
  await clickText('Push design to build'); await sleep(1500);
  f = await api('GET', '/factions/' + fid);
  check('pushed straight to build (no ticker)', f.builtDesign && f.builtDesign.ufa.cost === 3);
  const lv = await page.evaluate(async a => (await fetch(`/designer/api/live/${a}/values`)).json(), acr);
  check('live values endpoint', lv.values && lv.values['ufa.cost'] === 3, JSON.stringify(lv));
  await api('POST', `/factions/${fid}/patch`, { ops: [{ op: 'set', path: 'ufa.text', value: 'Do a different thing.' }] });
  await page.goto(BASE + '#/faction/' + fid, { waitUntil: 'networkidle0' }); await page.reload({ waitUntil: 'networkidle0' }); await sleep(600);
  await clickText('Build', '.section-button'); await sleep(600);
  await clickText('Update'); await sleep(1000);
  const open2 = await adminGet('requests?status=open');
  const ureq = (open2.requests || []).filter(r => r.fid === fid && r.type === 'update');
  check('update request created', ureq.length > 0, ureq.map(r => r.text).join(' || '));
  check('no open simple_update left for ticker', !(open2.requests || []).some(r => r.fid === fid && r.type === 'simple_update'));
  await clickText('Exit to Main'); await sleep(400);

  // 9. Bug report
  await clickText('Bug Report', '.section-button'); await sleep(500);
  await page.type('textarea', 'The thing broke.');
  await clickText('Send') || await clickText('Submit');
  await sleep(800);
  const open3 = await adminGet('requests?status=open');
  check('bug request', (open3.requests || []).some(r => r.fid === fid && r.type === 'bug' && /The thing broke/.test(r.text)));

  // 10. Phone width: no page-level horizontal overflow on main page
  await page.setViewport({ width: 390, height: 844 });
  await page.goto(BASE + '#/faction/' + fid, { waitUntil: 'networkidle0' }); await sleep(800);
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await shot('05-phone-main');
  check('phone main no overflow', over <= 1, 'overflow px=' + over);
  await clickText('Units', '.section-button'); await sleep(500);
  const over2 = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  await shot('06-phone-units');
  check('phone units no page overflow', over2 <= 1, 'overflow px=' + over2);
  const sel = await page.$$eval('select', ss => ss.map(s => s.options[s.selectedIndex] && s.options[s.selectedIndex].text));
  check('saved dropdown values shown (Cultist/Fixed/N/A)', ['Cultist', 'Fixed', 'N/A'].every(v => sel.includes(v)), JSON.stringify(sel));
  const ticked = await page.$$eval('input[type=checkbox]', cs => cs.filter(c => c.checked).length);
  check('unticked boxes show unticked', ticked === 0, 'ticked=' + ticked);

  console.log('\n' + results.filter(r => r[0] === 'PASS').length + '/' + results.length + ' passed');
  await browser.close();
})().catch(e => { console.error('CRASH', e); process.exit(1); });
