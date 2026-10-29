#!/usr/bin/env -S NODE_PATH=/Users/gremus/.nvm/versions/node/v24.16.0/lib/node_modules node
// Captures browser console output (including println traces) from a CWO game URL.
// Requires: puppeteer (npm install -g puppeteer)
//
// Usage:
//   node cwo-console-capture.js <URL> [wait_seconds]
//
// Examples:
//   node cwo-console-capture.js https://cwo.freeddns.org/play/yjvfukkqjbamdrlp
//   node cwo-console-capture.js https://cwo.freeddns.org/mnu/play/yqddoxxtvkoaiwpd 60
//
// Output: all console messages (log, error, warn) and uncaught errors with stack traces.
// Useful for capturing Scala println() traces embedded in the compiled JS.

const puppeteer = require('puppeteer');

const url = process.argv[2];
if (!url) {
  console.error('Usage: node cwo-console-capture.js <URL> [wait_seconds]');
  process.exit(1);
}
const waitSec = parseInt(process.argv[3]) || 45;

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  const logs = [];
  page.on('console', async msg => {
    const args = msg.args();
    const parts = [];
    for (const arg of args) {
      try {
        const val = await arg.jsonValue();
        parts.push(typeof val === 'string' ? val : JSON.stringify(val));
      } catch {
        parts.push(arg.toString());
      }
    }
    const text = parts.join(' ');
    logs.push(`[${msg.type().toUpperCase()}] ${text}`);
  });
  page.on('pageerror', err => {
    logs.push(`[PAGE_ERROR] ${err.message}`);
    if (err.stack) logs.push(`[STACK] ${err.stack}`);
  });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    logs.push(`[NAV_ERROR] ${e.message}`);
  }

  await new Promise(r => setTimeout(r, waitSec * 1000));

  logs.forEach(l => console.log(l));
  await browser.close();
})().catch(err => {
  console.error(`FATAL: ${err.message}`);
  process.exit(1);
});
