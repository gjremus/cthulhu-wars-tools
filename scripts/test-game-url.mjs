#!/usr/bin/env node
/**
 * Test a game URL (with secret gobbledygook) for JavaScript errors
 * Usage: ./test-game-url.mjs <SECRET_URL>
 * Example: ./test-game-url.mjs "https://cwo.freeddns.org/HB/play/abc123def456..."
 */
import puppeteer from 'puppeteer';

const GAME_URL = process.argv[2];
if (!GAME_URL) {
  console.error('Usage: ./test-game-url.mjs <GAME_URL_WITH_SECRET>');
  console.error('Example: ./test-game-url.mjs "https://cwo.freeddns.org/HB/play/abc123..."');
  process.exit(1);
}

async function testGameUrl() {
  console.log(`Testing game URL: ${GAME_URL}`);

  const browser = await puppeteer.launch({
    headless: false,  // VISIBLE
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1280, height: 800 }
  });

  const page = await browser.newPage();
  const errors = [];
  const consoleMessages = [];

  // Capture ALL console messages
  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    consoleMessages.push({ type, text });

    if (type === 'error') {
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink')) {
        console.log(`\n⚠️  CONSOLE ERROR: ${text}`);
        errors.push(`CONSOLE ERROR: ${text}`);
      }
    }
  });

  // Capture JavaScript exceptions
  page.on('pageerror', err => {
    console.log(`\n⚠️  JAVASCRIPT EXCEPTION: ${err.message}`);
    console.log(`   Stack: ${err.stack?.split('\\n')[0]}`);
    errors.push(`JAVASCRIPT EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Loading game...');
    await page.goto(GAME_URL, { waitUntil: 'networkidle2', timeout: 60000 });

    console.log('Waiting for game to initialize (15 seconds)...');
    await new Promise(r => setTimeout(r, 15000));

    console.log(`\\nCaptured ${consoleMessages.length} console messages total`);
    console.log(`  - info: ${consoleMessages.filter(m => m.type === 'info').length}`);
    console.log(`  - log: ${consoleMessages.filter(m => m.type === 'log').length}`);
    console.log(`  - warning: ${consoleMessages.filter(m => m.type === 'warning').length}`);
    console.log(`  - error: ${consoleMessages.filter(m => m.type === 'error').length}`);

    // Check if game UI loaded
    const hasGameUI = await page.evaluate(() => {
      return document.querySelector('#action') !== null ||
             document.body.textContent.includes('Action Phase') ||
             document.body.textContent.includes('Doom Phase') ||
             document.body.textContent.includes('Power:');
    }).catch(() => false);

    if (!hasGameUI) {
      errors.push('Game UI did not load (no action div or phase text found)');
      console.log('\\n⚠️  Game UI did not appear');
    } else {
      console.log('\\n✓ Game UI detected');
    }

  } catch (e) {
    console.log(`\\n❌ ERROR loading page: ${e.message}`);
    errors.push(`LOAD ERROR: ${e.message}`);
  }

  console.log('\\nPress Ctrl+C to close browser...');
  await new Promise(r => setTimeout(r, 10000));
  await browser.close();

  // Report results
  console.log('\\n=== TEST RESULTS ===');
  if (errors.length === 0) {
    console.log(`✓ Game loaded with NO errors`);
    process.exit(0);
  } else {
    console.log(`✗ FAILED with ${errors.length} error(s):\\n`);
    errors.forEach(err => console.log(`  - ${err}`));
    process.exit(1);
  }
}

testGameUrl().catch(e => {
  console.error('Script error:', e);
  process.exit(1);
});
