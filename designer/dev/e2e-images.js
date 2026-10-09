#!/usr/bin/env node
// Image + Extract flows against the local stand-in (dev/local-caddy.py on :8095).
// Run: NODE_PATH=$(npm root -g) node dev/e2e-images.js   (needs /tmp/designer-smoke/card.png + sb.png)
const puppeteer = require('puppeteer');
const BASE = 'http://127.0.0.1:8095';
const ADMIN = BASE + '/designer/api/admin/devtoken123';
const CARD = '/tmp/designer-smoke/card.png', SB = '/tmp/designer-smoke/sb.png';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', name, extra); };

(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`HTTP ${r.status()} ${r.url()}`); });
  const dialogs = [];
  page.on('dialog', d => { dialogs.push(d.message()); d.accept(); });

  await page.goto(BASE + '/designer/', { waitUntil: 'networkidle0' });
  const user = 'img' + Date.now().toString().slice(-6);
  const tok = await page.evaluate(async u => (await (await fetch('/designer/api/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: 'secret1' }) })).json()).token, user);
  const L = () => String.fromCharCode(65 + Math.floor(Math.random() * 26));
  const f = await page.evaluate(async (t, a) => (await (await fetch('/designer/api/factions', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: JSON.stringify({ name: 'Picture Test', acronym: a }) })).json()), tok, 'P' + L() + L());
  await page.evaluate(t => localStorage.setItem('cw_designer_token', t), tok);
  await page.goto(BASE + '/designer/#/faction/' + f.id, { waitUntil: 'networkidle0' });
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(600);

  const get = () => page.evaluate(async (t, id) => (await (await fetch('/designer/api/factions/' + id, { headers: { Authorization: 'Bearer ' + t } })).json()), tok, f.id);
  const btn = (text, scope = 'body') => page.evaluateHandle((text, scope) => [...document.querySelector(scope).querySelectorAll('button')].find(b => b.textContent.trim() === text && !b.disabled) || null, text, scope);
  const upload = async (text, file, scope) => {
    const b = await btn(text, scope);
    if (!(await b.evaluate(x => !!x))) return false;
    const [chooser] = await Promise.all([page.waitForFileChooser({ timeout: 5000 }), b.evaluate(x => x.click())]);
    await chooser.accept([file]);
    await sleep(2500); // downscale + upload + debounced save
    return true;
  };
  const imgOk = sel => page.$$eval(sel, is => is.length > 0 && is.every(i => i.complete && i.naturalWidth > 0));

  // Faction card
  check('card upload button', await upload('Upload faction card image', CARD));
  let d = (await get()).design;
  check('card saved', !!d.card.image, d.card.image);
  check('card thumbnail loads', await imgOk('.card-image-section img'));
  const imgUrl = await page.$eval('.card-image-section img', i => i.src);
  check('image served with correct type', await page.evaluate(async u => (await fetch(u)).headers.get('content-type'), imgUrl).then(ct => /^image\//.test(ct || '')));

  // Expand -> fullscreen -> replace
  await page.click('.card-image-section img'); await sleep(500);
  check('card opens full size', !!(await (await btn('Upload new image')).evaluate(x => !!x)));
  await upload('Upload new image', SB);
  d = (await get()).design;
  check('card replaced from full-size view', !!d.card.image && !imgUrl.includes(d.card.image), d.card.image);

  // Two extract buttons, each with its time estimate below
  const ests = await page.$$eval('.card-image-section .extract-estimate', es => es.map(e => e.textContent.trim()));
  check('two extract buttons with minute estimates', !!(await (await btn('Extract text', '.card-image-section')).evaluate(x => !!x)) && !!(await (await btn('Extract text + images', '.card-image-section')).evaluate(x => !!x)) && ests.length === 2 && ests.every(e => /^about \d+ min$/.test(e)), ests.join(', '));

  // Extract on card: empty design -> no confirm, request created
  dialogs.length = 0;
  await (await btn('Extract text', '.card-image-section')).evaluate(x => x.click()); await sleep(1000);
  let reqs = (await page.evaluate(async u => (await fetch(u)).json(), ADMIN + '/requests?status=open')).requests || [];
  check('extract (empty design) -> request, no overwrite warning', reqs.some(r => r.fid === f.id && r.type === 'extract' && r.data && r.data.target === 'card' && r.data.images === false) && !(await page.$('.confirm-dialog')), dialogs.join(' | '));

  // Extract with content -> confirm dialog first; Cancel makes no request
  await page.evaluate(async (t, id) => fetch('/designer/api/factions/' + id + '/patch', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + t }, body: JSON.stringify({ ops: [{ op: 'set', path: 'ufa.name', value: 'Something' }] }) }), tok, f.id);
  await page.reload({ waitUntil: 'networkidle0' }); await sleep(600);
  const before = reqs.filter(r => r.fid === f.id && r.type === 'extract').length;
  await (await btn('Extract text', '.card-image-section')).evaluate(x => x.click()); await sleep(500);
  const confTxt = await page.$eval('.confirm-dialog', e => e.innerText).catch(() => '');
  check('extract with content asks first', /overwrite/i.test(confTxt), confTxt.replace(/\n/g, ' '));
  await (await btn('Cancel', '.confirm-dialog')).evaluate(x => x.click()); await sleep(600);
  reqs = (await page.evaluate(async u => (await fetch(u)).json(), ADMIN + '/requests?status=open')).requests || [];
  check('cancel -> no extra request', reqs.filter(r => r.fid === f.id && r.type === 'extract').length === before);
  await (await btn('Extract text', '.card-image-section')).evaluate(x => x.click()); await sleep(500);
  await (await btn('Yes - Extract', '.confirm-dialog')).evaluate(x => x.click()); await sleep(1000);
  reqs = (await page.evaluate(async u => (await fetch(u)).json(), ADMIN + '/requests?status=open')).requests || [];
  check('Yes - Extract -> same waiting request reused (no duplicate job)', before === 1 && reqs.filter(r => r.fid === f.id && r.type === 'extract').length === 1 && /Extract requested/.test(dialogs.slice(-1)[0] || ''), dialogs.slice(-1)[0] || '');

  // Text + images -> its own request with images: true, message gives the bigger estimate
  await (await btn('Extract text + images', '.card-image-section')).evaluate(x => x.click()); await sleep(500);
  const confImg = await page.$eval('.confirm-dialog', e => e.innerText).catch(() => '');
  await (await btn('Yes - Extract', '.confirm-dialog')).evaluate(x => x.click()); await sleep(1000);
  reqs = (await page.evaluate(async u => (await fetch(u)).json(), ADMIN + '/requests?status=open')).requests || [];
  check('text + images -> request with images:true', reqs.some(r => r.fid === f.id && r.type === 'extract' && r.data.images === true) && /about 30 minutes/.test(dialogs.slice(-1)[0] || ''), dialogs.slice(-1)[0] || '');
  check('text + images confirm mentions silhouettes', /silhouettes/.test(confImg), confImg.replace(/\n/g, ' '));

  // Faction glyph (under the card)
  d = (await get()).design;
  check('new faction has card.glyph default', d.card.glyph === null, JSON.stringify(d.card));
  check('glyph upload button', await upload('Upload faction glyph', CARD, '.glyph-image-section'));
  d = (await get()).design;
  check('glyph saved', !!d.card.glyph && d.card.glyph !== d.card.image, d.card.glyph);
  check('glyph thumbnail loads', await imgOk('.glyph-image-section img'));
  const g1 = d.card.glyph;
  check('glyph replace', await upload('Replace glyph', SB, '.glyph-image-section'));
  d = (await get()).design;
  check('glyph replaced', !!d.card.glyph && d.card.glyph !== g1, d.card.glyph);
  await (await btn('Remove glyph', '.glyph-image-section')).evaluate(x => x.click()); await sleep(1500);
  d = (await get()).design;
  check('glyph removed -> upload button back', d.card.glyph === null && !!(await (await btn('Upload faction glyph', '.glyph-image-section')).evaluate(x => !!x)), String(d.card.glyph));
  check('card image untouched by glyph edits', !!d.card.image);

  // Spellbooks: all 6 in 1
  check('SB all-in-1 upload', await upload('Upload all 6 in 1 image', SB, '.sb-images-section'));
  d = (await get()).design;
  check('SB all saved', d.sbImages.mode === 'all' && !!d.sbImages.all, JSON.stringify(d.sbImages));
  check('SB all thumbnail loads', await imgOk('.sb-images-section img'));
  await (await btn('Delete', '.sb-images-section')).evaluate(x => x.click()); await sleep(1500);
  d = (await get()).design;
  check('SB all delete -> back to choice', !d.sbImages.mode && !d.sbImages.all && !!(await (await btn('Upload 1 at a time')).evaluate(x => !!x)), JSON.stringify(d.sbImages));

  // Spellbooks: 1 at a time
  await (await btn('Upload 1 at a time')).evaluate(x => x.click()); await sleep(800);
  check('6 slots shown', (await page.$$('.image-slot')).length === 6);
  await upload('Upload', SB, '.image-slot:nth-child(2)');
  await upload('Upload', SB, '.image-slot:nth-child(5)');
  d = (await get()).design;
  check('slots 2 and 5 saved', d.sbImages.mode === 'each' && !!d.sbImages.each[1] && !!d.sbImages.each[4] && !d.sbImages.each[0], JSON.stringify(d.sbImages.each));
  await (await btn('Delete', '.image-slot:nth-child(2)')).evaluate(x => x.click()); await sleep(1500);
  d = (await get()).design;
  check('delete one slot', !d.sbImages.each[1] && !!d.sbImages.each[4]);
  await (await btn('Delete all 6, to replace with 1 image for all 6')).evaluate(x => x.click()); await sleep(1500);
  d = (await get()).design;
  check('delete all 6 -> back to choice', !d.sbImages.mode && d.sbImages.each.every(x => !x), JSON.stringify(d.sbImages));

  await page.reload({ waitUntil: 'networkidle0' }); await sleep(600);
  check('after reload: choice buttons shown again', !!(await (await btn('Upload all 6 in 1 image')).evaluate(x => !!x)));
  check('no page errors / failed requests', errors.length === 0, errors.join(' | '));
  await page.screenshot({ path: '/tmp/designer-smoke/images.png', fullPage: true });
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  await browser.close();
})().catch(e => { console.error('CRASH', e); process.exit(1); });
