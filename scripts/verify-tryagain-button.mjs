// Verify the Claude Terminal Log "Try again" button is visible + clickable on desktop and mobile.
// Usage:
//   node scripts/verify-tryagain-button.mjs local            (local admin/admin.html, mocked log, retry POST intercepted)
//   node scripts/verify-tryagain-button.mjs live <TOKEN>     (live site, real log, retry POST intercepted - NOT sent)
import puppeteer from 'puppeteer';
import path from 'path';
import { fileURLToPath } from 'url';

const mode = process.argv[2] || 'local';
const token = process.argv[3] || 'TEST';
const here = path.dirname(fileURLToPath(import.meta.url));
const url = mode === 'live'
  ? 'https://cwo.freeddns.org/admin.html'
  : 'file://' + (process.env.ADMIN_FILE || path.resolve(here, '../admin/admin.html'));
const SERVER = 'https://cwo.freeddns.org';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const MOCK = { entries: [
  { n: 412, at: 1793400000, type: 'bug', user: 'admin', designObject: 'Tribulation', prompt: 'Fix the Dagon spellbook not triggering after battle '.repeat(4), summary: 'Patched handler and redeployed. '.repeat(20), cost: 0.42 },
  { n: 411, at: 1793390000, type: 'console', user: 'admin', designObject: '', prompt: 'Short prompt', summary: 'Done.', defaultSummary: true, cost: 0.01 },
]};

const views = [
  { name: 'desktop', width: 1400, height: 1000, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
];

const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
let allOk = true;
for (const v of views) {
  const page = await browser.newPage();
  await page.setViewport({ width: v.width, height: v.height, isMobile: v.mobile, hasTouch: v.mobile, deviceScaleFactor: v.mobile ? 2 : 1 });
  if (v.mobile) await page.setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/130.0 Mobile/15E148 Safari/604.1');
  const errors = [];
  page.on('pageerror', e => { if (!(mode === 'local' && String(e).includes('Failed to fetch'))) errors.push(String(e)); });
  page.on('requestfailed', r => console.log('  [req failed]', r.url().slice(0, 120), r.failure()?.errorText));
  page.on('dialog', async d => { console.log(`  [${v.name}] alert: ${d.message()}`); await d.dismiss(); });
  let posted = null;
  await page.setRequestInterception(true);
  const CORS = { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Headers': '*', 'Access-Control-Allow-Methods': '*' };
  page.on('request', req => {
    const u = req.url();
    if (req.method() === 'OPTIONS') return req.respond({ status: 204, headers: CORS });
    if (u.includes('/claude-prompt') && req.method() === 'POST') {
      posted = req.postData();
      return req.respond({ status: 200, headers: CORS, contentType: 'text/plain', body: 'ok' });
    }
    if (mode === 'local' && u.startsWith(SERVER)) {
      if (u.includes('/terminal-log')) return req.respond({ status: 200, headers: CORS, contentType: 'application/json', body: JSON.stringify(MOCK) });
      return req.respond({ status: 200, headers: CORS, contentType: 'application/json', body: '{}' });
    }
    req.continue();
  });
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(1500);
  await page.evaluate((s, t) => { SERVER = s; TOKEN = t; document.getElementById('login-pane').style.display = 'none'; document.getElementById('main-pane').style.display = 'block'; showSection('claudelog'); loadClaudeLog(); }, SERVER, token);
  try { await page.waitForSelector('#claudelog-body button', { timeout: 20000 }); }
  catch (e) { console.log(`[${v.name}] no button rendered; table body:`, await page.$eval('#claudelog-body', el => el.innerText.slice(0, 300)), errors); allOk = false; await page.close(); continue; }
  // Simulate a user who has scrolled the table to the start, then to the far end
  const result = await page.evaluate(() => {
    const btn = document.querySelector('#claudelog-body button');
    const scroller = document.getElementById('claudelog-table').parentElement;
    scroller.scrollLeft = 0;
    const r = btn.getBoundingClientRect();
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {
      text: btn.textContent, tableWidth: document.getElementById('claudelog-table').offsetWidth,
      left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height),
      inView: r.left >= 0 && r.right <= window.innerWidth && r.width > 20 && r.height > 10,
      onTop: hit === btn, rows: document.querySelectorAll('#claudelog-body button').length,
    };
  });
  await page.evaluate(() => document.querySelector('#claudelog-body button').scrollIntoView({ block: 'center', inline: 'nearest' }));
  await sleep(300);
  const shot = `/tmp/tryagain-${mode}-${v.name}.png`;
  await page.screenshot({ path: shot });
  // Real click (tap on mobile) at the button's on-screen position
  const box = await (await page.$('#claudelog-body button')).boundingBox();
  if (v.mobile) await page.touchscreen.tap(box.x + box.width / 2, box.y + box.height / 2);
  else await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
  await sleep(1500);
  const ok = result.inView && result.onTop && !!posted && errors.length === 0;
  allOk = allOk && ok;
  console.log(`[${v.name} ${v.width}x${v.height}] ${ok ? 'PASS' : 'FAIL'}`, JSON.stringify(result));
  console.log(`  retry POST captured: ${posted ? 'yes - ' + posted.split('\n')[0] : 'NO'}`);
  if (errors.length) console.log('  page errors:', errors.slice(0, 5));
  console.log(`  screenshot: ${shot}`);
  await page.close();
}
await browser.close();
process.exit(allOk ? 0 : 1);
