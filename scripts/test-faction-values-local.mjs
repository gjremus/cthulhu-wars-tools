#!/usr/bin/env node
// Checks that a faction loads in a real (headless) browser and that its overlay /
// requirement / spellbook text shows the numbers from solo/faction-values/<acr>.json.
//
// Usage (from cthulhu-wars-tools/, where node_modules/puppeteer lives):
//   node scripts/test-faction-values-local.mjs <base-url> <ACR> "<overlay key>" "<expected text>" [...more pairs]
//   <base-url>  e.g. http://127.0.0.1:8765/HB  (local copy)  or  https://cwo.freeddns.org/HB  (live)
//   "<overlay key>" ""            = the faction card
//                   requirement   = the requirement text, e.g. "Roll 9 or more dice in a single Combat"
//                   spellbook     = the spellbook name, e.g. "Manned Battlements"
// Exit code 0 = every expected text found and no page errors.
import puppeteer from 'puppeteer';

const [base, acr, ...pairs] = process.argv.slice(2);
const url = `${base.replace(/\/$/, '')}/?setup=4:GC-${acr}-CC-BG`;
// Bundled headless Chrome: the system Chrome app crashes on this page in headless mode.
const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'] });
const errors = [];
let fails = 0;

async function overlayText(key) {
  const page = await browser.newPage();
  page.on('pageerror', e => errors.push(`EXCEPTION [${key}]: ` + e.message));
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
  for (let i = 0; i < 30; i++) {
    await new Promise(r => setTimeout(r, 1000));
    try {
      const ready = await page.evaluate(() => typeof onExternalClick === 'function');
      if (ready) break;
    } catch (e) { /* page still starting */ }
  }
  await new Promise(r => setTimeout(r, 1500));
  let text = '';
  try {
    text = await page.evaluate(async (acr, key) => {
      try { key === '' ? onExternalClick(acr) : onExternalClick(acr, key); }
      catch (e) { return 'OVERLAY ERROR: ' + e.message; }
      await new Promise(r => setTimeout(r, 1500));   // the overlay fills in on a timer
      const o = document.getElementById('overlay');
      return o ? o.textContent.replace(/\s+/g, ' ') : '';
    }, acr, key);
  } catch (e) { text = 'EVAL ERROR: ' + e.message; }
  await page.close().catch(() => {});
  return text;
}

for (let i = 0; i < pairs.length; i += 2) {
  const key = pairs[i], want = pairs[i + 1];
  const text = await overlayText(key);
  const ok = text.includes(want);
  if (!ok) fails++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${acr} [${key || 'faction card'}] expects "${want}"` +
    (ok ? '' : `\n      got: ${text.slice(0, 400)}`));
}
await browser.close();
if (errors.length) console.log('PAGE ERRORS:\n  ' + errors.join('\n  '));
console.log(errors.length || fails ? `RESULT: FAIL (${fails} text, ${errors.length} page errors)` : 'RESULT: PASS');
process.exit(errors.length || fails ? 1 : 0);
