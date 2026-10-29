#!/usr/bin/env node
// Live browser test of the designer "Generate Silhouette" button. Usage: node scripts/test-silhouette-button.mjs <factionId> "<unit name>"
import puppeteer from 'puppeteer';
const FID = process.argv[2] || 'kdwyrr4nirx5';
const BASE = 'https://cwo.freeddns.org/designer/';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const browser = await puppeteer.launch({headless: true, args: ['--no-sandbox']});
const page = await browser.newPage();
await page.setViewport({width: 1400, height: 1000});
page.on('console', m => console.log(`[console.${m.type()}] ${m.text()}`));
page.on('pageerror', e => console.log(`[pageerror] ${e.message}`));
page.on('requestfailed', r => console.log(`[requestfailed] ${r.url()} ${r.failure()?.errorText}`));
page.on('request', r => { if (r.method() !== 'GET') console.log(`[request] ${r.method()} ${r.url()}\n  body: ${(r.postData() || '').slice(0, 300)}`); });
page.on('response', async r => {
  if (r.request().method() !== 'GET') { let t = ''; try { t = await r.text(); } catch {} console.log(`[response] ${r.status()} ${r.url()}\n  body: ${t.slice(0, 400)}`); }
});
page.on('dialog', async d => { console.log(`[dialog ${d.type()}] ${d.message().slice(0, 300)}`); await d.accept(); });

try {
  await page.goto(BASE, {waitUntil: 'networkidle2', timeout: 30000});
  await page.type('input[type="text"]', 'scrolltest_7jyc2n');
  await page.type('input[type="password"]', 'password');
  { const b = await page.evaluateHandle(() => [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Login')); await b.asElement().click(); }
  await sleep(3000);
  console.log('URL after login:', page.url());
  await page.goto(BASE + '#/faction/' + FID + '/section/units', {waitUntil: 'networkidle2'});
  await sleep(3000);
  console.log('URL:', page.url());
  const btns = await page.$$eval('button', els => els.filter(b => b.textContent.trim() === 'Generate Silhouette').map(b => ({disabled: b.disabled, visible: !!b.offsetParent})));
  console.log('Generate Silhouette buttons:', JSON.stringify(btns));
  if (!btns.length) {
    const heads = await page.$$eval('button, h2, h3, summary, .sx-section-title', els => els.map(e => e.textContent.trim()).filter(t => t && t.length < 40));
    console.log('Clickable texts:', JSON.stringify(heads.slice(0, 60)));
    await page.screenshot({path: '/tmp/trace-sil-nobutton.png', fullPage: true});
  } else {
    // Pick the Generate Silhouette button that sits in the unit block whose name field is UNIT
    const UNIT = process.argv[3] || '';
    const info = await page.evaluate((UNIT) => [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Generate Silhouette').map((b, i) => {
      let el = b; while (el && !(el.querySelector && [...el.querySelectorAll('input')].some(x => x.value && x.value.trim()))) el = el.parentElement;
      const names = el ? [...el.querySelectorAll('input')].map(x => x.value).filter(Boolean) : [];
      return {i, disabled: b.disabled, unit: names[0] || '?', match: !!UNIT && names.includes(UNIT)};
    }), UNIT);
    console.log('Buttons by unit:', JSON.stringify(info));
    const pick = info.find(x => (UNIT ? x.match : true) && !x.disabled);
    if (!pick) console.log('No enabled button for unit', UNIT);
    else {
      const h = await page.evaluateHandle(i => [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === 'Generate Silhouette')[i], pick.i);
      await h.asElement().evaluate(b => b.scrollIntoView({block: 'center'}));
      await page.screenshot({path: '/tmp/trace-sil-before.png'});
      await h.asElement().click();
      console.log('Clicked button for unit', pick.unit, '- waiting...');
      await sleep(6000);
      await page.screenshot({path: '/tmp/trace-sil-after.png'});
    }
  }
} catch (e) { console.log('[ERROR]', e.stack); }
await browser.close();
