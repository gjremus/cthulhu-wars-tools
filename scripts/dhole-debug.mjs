#!/usr/bin/env node
import puppeteer from 'puppeteer';
import { readFileSync } from 'fs';

const GAME_URL = 'https://cwo.freeddns.org/HB/play/pfcvdqyamfudlwgl';
const DEBUG_JS = '/Users/gremus/Claude-Projects/cw-homebrew-wt/solo/target/scala-2.13/cthulhu-wars-solo-hrf-opt/main.js';

async function main() {
  const debugJs = readFileSync(DEBUG_JS, 'utf8');
  console.log(`Loaded debug JS: ${(debugJs.length / 1024 / 1024).toFixed(1)} MB`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  const consoleLines = [];
  page.on('console', msg => {
    const text = msg.text();
    consoleLines.push(`[${msg.type()}] ${text}`);
    if (text.includes('DHOLE')) {
      console.log(`>>> ${text}`);
    }
  });
  page.on('pageerror', err => {
    console.log(`[PAGE ERROR] ${err.message}`);
  });

  await page.setRequestInterception(true);
  page.on('request', request => {
    const url = request.url();
    if (url.includes('main.js') || url.includes('cthulhu-wars-solo')) {
      console.log(`Intercepted JS request: ${url}`);
      request.respond({
        status: 200,
        contentType: 'application/javascript',
        body: debugJs
      });
    } else {
      request.continue();
    }
  });

  console.log(`Loading game: ${GAME_URL}`);
  try {
    await page.goto(GAME_URL, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log('Page loaded, waiting for game to replay...');
    await new Promise(r => setTimeout(r, 20000));
  } catch (e) {
    console.log(`Navigation error: ${e.message}`);
  }

  console.log('\n=== ALL CONSOLE OUTPUT ===');
  for (const line of consoleLines) {
    if (line.includes('DHOLE') || line.includes('Error') || line.includes('error')) {
      console.log(line);
    }
  }

  console.log(`\nTotal console lines: ${consoleLines.length}`);
  const dholeLines = consoleLines.filter(l => l.includes('DHOLE'));
  console.log(`DHOLE lines: ${dholeLines.length}`);
  if (dholeLines.length === 0) {
    console.log('\nNo DHOLE debug output found. Dumping last 30 console lines:');
    for (const line of consoleLines.slice(-30)) {
      console.log(line);
    }
  }

  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
