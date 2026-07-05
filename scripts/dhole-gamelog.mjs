#!/usr/bin/env node
import puppeteer from 'puppeteer';
import { readFileSync } from 'fs';

const GAME_URL = 'https://cwo.freeddns.org/HB/play/pfcvdqyamfudlwgl';
const DEBUG_JS = '/Users/gremus/Claude-Projects/cw-homebrew-wt/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js';

async function main() {
  const debugJs = readFileSync(DEBUG_JS, 'utf8');

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  page.on('pageerror', err => {
    console.log(`[PAGE ERROR] ${err.message}`);
  });

  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = request.url();
    if (url.includes('main.js') || url.includes('cthulhu-wars-solo')) {
      request.respond({
        status: 200,
        contentType: 'application/javascript',
        body: debugJs
      });
    } else {
      request.continue();
    }
  });

  // Intercept the read API calls to capture game log
  const gameLogResponses = [];
  page.on('response', async response => {
    const url = response.url();
    if (url.includes('/read/')) {
      try {
        const text = await response.text();
        gameLogResponses.push({ url, text: text.substring(0, 500) });
      } catch (e) {}
    }
  });

  console.log(`Loading game: ${GAME_URL}`);
  try {
    await page.goto(GAME_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await new Promise(r => setTimeout(r, 20000));
  } catch (e) {
    console.log(`Navigation error: ${e.message}`);
  }

  // Look for Dhole-related actions in the game log
  console.log('\n=== GAME LOG RESPONSES ===');
  for (const resp of gameLogResponses) {
    if (resp.text.includes('Dhole') || resp.text.includes('dhole') || resp.text.includes('AssignKill')) {
      console.log(`\nURL: ${resp.url}`);
      console.log(`Content: ${resp.text}`);
    }
  }

  // Also try to get the full game log via page evaluation
  console.log('\n=== TRYING PAGE EVAL ===');
  try {
    const logData = await page.evaluate(() => {
      if (window.game && window.game.log) return JSON.stringify(window.game.log);
      if (window.CWO && window.CWO.game) return JSON.stringify(window.CWO.game.log);
      return 'no game object found';
    });
    console.log('Game log eval result:', logData.substring(0, 200));
  } catch (e) {
    console.log(`Eval error: ${e.message}`);
  }

  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
