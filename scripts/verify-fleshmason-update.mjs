// Real-browser check of the faction Build page Update button against the LIVE designer code,
// fed with Fleshmason's real data (design v10, built "9"). All /designer/api calls are
// intercepted: POSTs are captured and never reach the server, so nothing is queued for real.
import puppeteer from 'puppeteer';
import fs from 'fs';
const fid = 'dcylxgn1wkqs';
const faction = JSON.parse(fs.readFileSync(process.argv[2] || '/tmp/fmtest/api-faction.json', 'utf8'));
const posted = [], unknown = [];
const browser = await puppeteer.launch({headless: 'new', args: ['--no-sandbox']});
const page = await browser.newPage();
const consoleErrs = [];
page.on('console', m => { if (m.type() === 'error') consoleErrs.push(m.text()); });
page.on('pageerror', e => consoleErrs.push(String(e)));
page.on('response', r => { if (r.status() >= 400) consoleErrs.push('HTTP ' + r.status() + ' ' + r.url()); });
page.on('dialog', async d => { posted.push({dialog: d.type(), message: d.message()}); d.type() === 'confirm' ? d.accept() : d.dismiss(); });
await page.setRequestInterception(true);
page.on('request', req => {
  const u = new URL(req.url());
  if (!u.pathname.startsWith('/designer/api/')) return req.continue();
  const p = u.pathname.replace('/designer/api', '');
  const json = (o) => req.respond({status: 200, contentType: 'application/json', body: JSON.stringify(o)});
  if (req.method() === 'POST') { posted.push({path: p, body: JSON.parse(req.postData() || '{}')}); return json({ok: true, id: 'test'}); }
  if (p === `/factions/${fid}`) return json(faction);
  if (p === '/factions') return json({factions: [{id: fid, name: faction.name, owner: 'zehk', current: faction.current, build: faction.build}]});
  if (p.endsWith('/requests')) return json({requests: []});
  if (p.endsWith('/extract-queue')) return json({status: null});
  if (p === '/me' || p.includes('session')) return json({username: 'zehk'});
  unknown.push(req.method() + ' ' + p); return json({});
});
await page.goto('https://cwo.freeddns.org/designer/', {waitUntil: 'networkidle0'});
await page.evaluate(() => { localStorage.setItem('cw_designer_token', 'test-token'); localStorage.setItem('cw_designer_user', 'zehk'); });
await page.goto(`https://cwo.freeddns.org/designer/#/faction/${fid}/build`, {waitUntil: 'networkidle0'});
await page.reload({waitUntil: 'networkidle0'});
await new Promise(r => setTimeout(r, 1500));
const info = await page.evaluate(() => {
  const btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Update');
  const txt = document.body.innerText;
  return {hasUpdate: !!btn, disabled: btn ? btn.disabled : null,
          versions: (txt.match(/Current Design Version:.*\n?.*Current Live Built Version:.*/) || [txt.slice(0, 300)])[0]};
});
console.log('Build page:', JSON.stringify(info));
await page.screenshot({path: '/tmp/fmtest/fleshmason-build.png', fullPage: true});
if (info.hasUpdate && !info.disabled) {
  await page.evaluate(() => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Update').click());
  await new Promise(r => setTimeout(r, 1500));
}
console.log('Captured (not sent to server):'); posted.forEach(p => console.log(' ', JSON.stringify(p)));
if (unknown.length) console.log('Unmocked API calls:', unknown.join(', '));
if (consoleErrs.length) console.log('Console errors:', consoleErrs.join(' | '));
await browser.close();
