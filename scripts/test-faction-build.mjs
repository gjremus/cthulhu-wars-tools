#!/usr/bin/env node
/**
 * Test if a faction can actually be loaded in a game without JavaScript errors.
 * Usage: ./test-faction-build.mjs FM
 *        ./test-faction-build.mjs PRM
 *        ./test-faction-build.mjs DGT
 *
 * Returns exit code 0 if faction loads cleanly, 1 if errors detected.
 */
import puppeteer from 'puppeteer';

const FACTION = process.argv[2];
if (!FACTION) {
  console.error('Usage: ./test-faction-build.mjs <FACTION_ACRONYM>');
  console.error('Example: ./test-faction-build.mjs FM');
  process.exit(1);
}

const SERVER = 'https://cwo.freeddns.org';
const BUILD = process.argv[3] || 'HB';  // Default to homebrew build
const SETUP = `4:GC-${FACTION}-CC-BG`;
const URL = `${SERVER}/${BUILD}/?setup=${SETUP}`;
const TIMEOUT = 30000;

async function testFaction() {
  console.log(`Testing faction ${FACTION} in ${BUILD} build...`);
  console.log(`URL: ${URL}`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const errors = [];
  const consoleMessages = [];

  // Capture console errors
  page.on('console', msg => {
    const text = msg.text();
    consoleMessages.push({ type: msg.type(), text });

    if (msg.type() === 'error') {
      // Filter out noise
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink')) {
        errors.push(`CONSOLE ERROR: ${text}`);
      }
    }
  });

  // Capture JavaScript exceptions
  page.on('pageerror', err => {
    errors.push(`JAVASCRIPT EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Loading page...');
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: TIMEOUT });

    // Wait for game to initialize
    console.log('Waiting for game initialization...');
    await new Promise(r => setTimeout(r, 10000));

    // Check if game actually loaded (look for game UI elements)
    try {
      const hasGameUI = await page.evaluate(() => {
        return document.querySelector('#action') !== null ||
               document.querySelector('.game-board') !== null ||
               document.body.textContent.includes('Setup') ||
               document.body.textContent.includes('Action Phase');
      });

      if (!hasGameUI) {
        errors.push('LOAD ERROR: Game UI did not appear (setup/action div missing)');
      }
    } catch (e) {
      // Ignore detached frame errors during evaluation
      if (!e.message.includes('detached')) {
        errors.push(`EVAL ERROR: ${e.message}`);
      }
    }

    console.log(`Captured ${consoleMessages.length} console messages`);

  } catch (e) {
    errors.push(`LOAD ERROR: ${e.message}`);
  }

  await browser.close();

  // Report results
  console.log('\n=== TEST RESULTS ===');
  if (errors.length === 0) {
    console.log(`✓ ${FACTION}: Loaded successfully with NO errors`);
    console.log(`  Faction ${FACTION} can be marked BUILT`);
    process.exit(0);
  } else {
    console.log(`✗ ${FACTION}: FAILED with ${errors.length} error(s)`);
    console.log(`  Faction ${FACTION} is NOT built - fix these errors first:\n`);
    errors.forEach(err => console.log(`    - ${err}`));
    console.log(`\n  DO NOT mark this faction as "built" until these errors are fixed.`);
    process.exit(1);
  }
}

testFaction().catch(e => {
  console.error('Test script error:', e);
  process.exit(1);
});
