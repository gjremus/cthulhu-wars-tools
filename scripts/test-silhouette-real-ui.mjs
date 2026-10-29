#!/usr/bin/env node
// Real-UI test of the designer "Generate Silhouette" button on the REAL "Sphinx Worshippers" faction,
// unit "Pharoah Kephren". Goes through the login form and normal navigation (no deep links, no API calls),
// emulating the owner's iPhone, with a visible browser and a screenshot at every step.
// Usage: node scripts/test-silhouette-real-ui.mjs [--click] [--desktop]
import puppeteer, {KnownDevices} from 'puppeteer';
import fs from 'fs';

const CLICK = process.argv.includes('--click');
const DESKTOP = process.argv.includes('--desktop');
const USER = process.env.CW_USER || 'scrolltest_7jyc2n';
const PASS = process.env.CW_PASS || 'password';
const FACTION = 'Sphinx Worshippers';
const UNIT = 'Pharoah Kephren';
const BASE = 'https://cwo.freeddns.org/designer/';
const OUT = process.env.OUT || '/tmp/sil-real-ui';
fs.mkdirSync(OUT, {recursive: true});
const sleep = ms => new Promise(r => setTimeout(r, ms));
const t = () => new Date().toISOString().slice(11, 19);
let step = 0;
const shot = async (page, name) => { const p = `${OUT}/${String(++step).padStart(2, '0')}-${name}.png`; await page.screenshot({path: p}); console.log(`${t()} [screenshot] ${p}`); };

const browser = await puppeteer.launch({headless: process.env.HEADFUL ? false : true, args: ['--no-sandbox']});
const page = await browser.newPage();
if (DESKTOP) await page.setViewport({width: 1400, height: 1000});
else await page.emulate(KnownDevices['iPhone 15 Pro']);
await page.setCacheEnabled(true);

page.on('console', m => console.log(`${t()} [console.${m.type()}] ${m.text()}`));
page.on('pageerror', e => console.log(`${t()} [pageerror] ${e.message}`));
page.on('requestfailed', r => console.log(`${t()} [requestfailed] ${r.method()} ${r.url()} ${r.failure()?.errorText}`));
page.on('request', r => { if (r.method() !== 'GET' || /\.js(\?|$)/.test(r.url())) console.log(`${t()} [request] ${r.method()} ${r.url()}${r.postData() ? '\n    body: ' + r.postData().slice(0, 400) : ''}`); });
page.on('response', async r => {
  const u = r.url();
  if (r.request().method() !== 'GET' || /\.js(\?|$)/.test(u)) {
    let b = ''; if (r.request().method() !== 'GET') { try { b = (await r.text()).slice(0, 500); } catch {} }
    console.log(`${t()} [response] ${r.status()} ${r.request().method()} ${u} fromCache=${r.fromCache()} etag=${r.headers()['etag'] || ''}${b ? '\n    body: ' + b : ''}`);
  }
});
page.on('dialog', async d => { console.log(`${t()} [dialog ${d.type()}] ${d.message().slice(0, 300)}`); await sleep(500); await d.accept(); });

// Find a visible element whose own text is exactly / contains the given text, and tap/click it like a person
async function press(text, {exact = true, tag = '*'} = {}) {
  const h = await page.evaluateHandle((text, exact, tag) => {
    const els = [...document.querySelectorAll(tag)].filter(e => e.offsetParent !== null);
    const own = e => [...e.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
    return els.find(e => exact ? (own(e) === text || (e.tagName === 'BUTTON' && e.textContent.trim() === text)) : own(e).includes(text)) || null;
  }, text, exact, tag);
  const el = h.asElement();
  if (!el) return false;
  await el.evaluate(e => e.scrollIntoView({block: 'center'}));
  await sleep(300);
  if (DESKTOP) await el.click(); else await el.tap();
  return true;
}
const visibleTexts = () => page.evaluate(() => [...document.querySelectorAll('button, a, h1, h2, h3, summary, [onclick], .sx-section-title, td')]
  .filter(e => e.offsetParent !== null).map(e => e.textContent.trim().replace(/\s+/g, ' ')).filter(x => x && x.length < 60).slice(0, 80));

try {
  console.log(`${t()} mode=${DESKTOP ? 'desktop' : 'iPhone 15 Pro'} user=${USER} click=${CLICK}`);
  await page.goto(BASE, {waitUntil: 'networkidle2', timeout: 30000});
  await shot(page, 'start');
  // Log in through the real form
  await page.type('input[type="text"]', USER, {delay: 30});
  await page.type('input[type="password"]', PASS, {delay: 30});
  await shot(page, 'login-filled');
  if (!await press('Login', {tag: 'button'})) throw new Error('no Login button');
  await sleep(3000);
  await shot(page, 'after-login');
  console.log(`${t()} after login texts:`, JSON.stringify(await visibleTexts()));

  // Open the faction from the list, as a person would
  if (!await press(FACTION) && !await press(FACTION, {exact: false})) throw new Error('faction not in list');
  await sleep(3000);
  console.log(`${t()} URL: ${page.url()}`);
  await shot(page, 'faction-open');
  console.log(`${t()} faction page texts:`, JSON.stringify(await visibleTexts()));

  // Go to the Units section
  if (!await press('Units') && !await press('Units', {exact: false})) throw new Error('no Units section link');
  await sleep(3000);
  console.log(`${t()} URL: ${page.url()}`);
  await shot(page, 'units-section');

  // Find Pharoah Kephren's Generate Silhouette button
  const info = await page.evaluate((UNIT) => [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Generate Silhouette').map((b, i) => {
    let el = b; while (el && !(el.querySelector && [...el.querySelectorAll('input')].some(x => x.value && x.value.trim()))) el = el.parentElement;
    const names = el ? [...el.querySelectorAll('input')].map(x => x.value).filter(Boolean) : [];
    return {i, disabled: b.disabled, visible: b.offsetParent !== null, unit: names[0] || '?', match: names.includes(UNIT)};
  }), UNIT);
  console.log(`${t()} Generate Silhouette buttons:`, JSON.stringify(info));
  const pick = info.find(x => x.match);
  if (!pick) throw new Error(`no Generate Silhouette button in the ${UNIT} block`);
  const btn = (await page.evaluateHandle(i => [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Generate Silhouette')[i], pick.i)).asElement();
  await btn.evaluate(b => b.scrollIntoView({block: 'center'}));
  await sleep(500);
  await shot(page, 'kephren-button');
  if (CLICK) {
    console.log(`${t()} >>> pressing Generate Silhouette for ${pick.unit} (disabled=${pick.disabled})`);
    if (DESKTOP) await btn.click(); else await btn.tap();
    await sleep(8000);
    await shot(page, 'after-click');
    if (process.argv.includes('--twice')) {
      console.log(`${t()} >>> pressing Generate Silhouette AGAIN (repeat tap)`);
      await btn.evaluate(b => b.scrollIntoView({block: 'center'}));
      if (DESKTOP) await btn.click(); else await btn.tap();
      await sleep(6000);
      await shot(page, 'after-second-click');
    }
  }
} catch (e) { console.log(`${t()} [ERROR] ${e.message}`); await shot(page, 'error'); }
await sleep(1500);
await browser.close();
