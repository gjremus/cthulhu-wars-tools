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
    console.log('Page loaded, waiting 25s for game to replay...');
    await new Promise(r => setTimeout(r, 25000));
  } catch (e) {
    console.log(`Navigation error: ${e.message}`);
  }

  // Check if the game is stopped at a prompt
  console.log('\n=== CHECKING GAME STATE ===');
  try {
    const state = await page.evaluate(() => {
      // Look for question/prompt UI elements
      const questions = document.querySelectorAll('.question, .ask, .prompt, [class*="question"], [class*="ask"]');
      const buttons = document.querySelectorAll('button, .button, [class*="btn"], [class*="action"]');
      const gameStatus = document.querySelector('.status, [class*="status"], [class*="turn"]');

      // Look for any visible choice UI
      const allText = document.body ? document.body.innerText : '';
      const hasDholeChoice = allText.includes('Planetary Destruction') && allText.includes('choose');
      const hasDoom = allText.includes('Opponent gains') && (allText.includes('doom') || allText.includes('Power'));

      return {
        questionsFound: questions.length,
        buttonsFound: buttons.length,
        statusText: gameStatus ? gameStatus.innerText : 'none',
        hasDholeChoice,
        hasDoom,
        bodyTextSnippet: allText.substring(0, 500),
        bodyTextEnd: allText.substring(allText.length - 500)
      };
    });
    console.log('Game state:', JSON.stringify(state, null, 2));
  } catch (e) {
    console.log(`State eval error: ${e.message}`);
  }

  // Also check if there are errors
  const errors = consoleLines.filter(l => l.includes('[error]') || l.includes('Error'));
  if (errors.length > 0) {
    console.log('\n=== ERRORS ===');
    for (const e of errors) console.log(e);
  }

  // Check total console output count
  console.log(`\nTotal console lines: ${consoleLines.length}`);
  console.log(`Last 5 console lines:`);
  for (const line of consoleLines.slice(-5)) {
    console.log(`  ${line}`);
  }

  await browser.close();
}

main().catch(e => { console.error(e); process.exit(1); });
