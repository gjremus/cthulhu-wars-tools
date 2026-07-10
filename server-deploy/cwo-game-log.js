#!/usr/bin/env -S NODE_PATH=/Users/gremus/.nvm/versions/node/v24.16.0/lib/node_modules node
// Extracts the player-visible game log from a CWO game URL.
// Requires: puppeteer (npm install -g puppeteer)
//
// Usage:
//   node cwo-game-log.js <URL> [wait_seconds]
//
// Examples:
//   node cwo-game-log.js https://cwo.freeddns.org/play/yjvfukkqjbamdrlp
//   node cwo-game-log.js https://cwo.freeddns.org/mnu/play/yqddoxxtvkoaiwpd 60
//
// Output: the full player game log text (stripped of HTML tags).
// The log is extracted from the #log element after the game finishes replaying.

const puppeteer = require('puppeteer');

const url = process.argv[2];
if (!url) {
  console.error('Usage: node cwo-game-log.js <URL> [wait_seconds]');
  process.exit(1);
}
const waitSec = parseInt(process.argv[3]) || 45;

(async () => {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  page.on('pageerror', err => {
    console.error(`[PAGE_ERROR] ${err.message}`);
  });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    console.error(`[NAV_ERROR] ${e.message}`);
  }

  await new Promise(r => setTimeout(r, waitSec * 1000));

  // Extract the game log from the DOM
  const log = await page.evaluate(() => {
    // Try common log container IDs
    const el = document.getElementById('log') ||
               document.querySelector('.game-log') ||
               document.querySelector('[class*="log"]');
    if (!el) return '[ERROR] No log element found in DOM';
    return el.innerText || el.textContent || '[ERROR] Log element empty';
  });

  console.log(log);
  await browser.close();
})().catch(err => {
  console.error(`FATAL: ${err.message}`);
  process.exit(1);
});
