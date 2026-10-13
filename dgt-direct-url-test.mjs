#!/usr/bin/env node
/**
 * Test DGT directly via URL setup string - captures ALL browser messages
 */
import puppeteer from 'puppeteer';

async function test() {
  console.log('DGT Direct URL Test\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  let errorCount = 0;
  let consoleCount = 0;

  // Intercept ALL console calls
  page.on('console', async msg => {
    consoleCount++;
    const type = msg.type();
    const location = msg.location();
    const text = msg.text();

    // Print all messages to capture any  errors
    console.log(`[CONSOLE:${type.toUpperCase()}] ${text}`);
    if (location && location.url) {
      console.log(`  -> ${location.url}:${location.lineNumber}`);
    }

    if (type === 'error') {
      errorCount++;
    }
  });

  page.on('pageerror', err => {
    console.log(`\n[UNCAUGHT EXCEPTION]\n${err.message}\n${err.stack}\n`);
    errorCount++;
  });

  try {
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`Loading: ${url}\n`);

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    console.log(`Page loaded. Waiting 10 seconds...\n`);

    // Wait and collect errors
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 1000));
      console.log(`[${i+1}s elapsed - errors so far: ${errorCount}]`);
    }

  } catch (e) {
    console.log(`\n[NAVIGATION ERROR]\n${e.message}\n${e.stack}\n`);
    errorCount++;
  }

  await browser.close();

  console.log(`\n=== SUMMARY ===`);
  console.log(`Total console messages: ${consoleCount}`);
  console.log(`Total errors: ${errorCount}`);
  console.log(`Build: HB (homebrew)`);
  console.log(`Faction: DGT (Tribulation)`);

  if (errorCount === 0) {
    console.log('\n✓ NO ERRORS DETECTED');
  } else {
    console.log(`\n✗ ${errorCount} ERROR(S) FOUND`);
  }
}

test().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
