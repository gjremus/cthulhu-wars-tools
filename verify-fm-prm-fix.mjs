#!/usr/bin/env node
/**
 * Manual verification of FM and PRM faction cards
 */
import puppeteer from 'puppeteer';

async function verify() {
  console.log('=== FM/PRM FACTION CARD FIX VERIFICATION ===\n');
  console.log('Opening browser to test FM and PRM faction cards...');
  console.log('');
  console.log('MANUAL TEST STEPS:');
  console.log('1. Wait for game to load');
  console.log('2. Click on FM faction card (pale pink/flesh colored)');
  console.log('3. Verify all unit images appear (should see 5 units with images)');
  console.log('4. Close the card overlay');
  console.log('5. Click on PRM faction card (deep red)');
  console.log('6. Verify all unit images appear (should see 4 units with images)');
  console.log('');
  console.log('Browser will stay open for 90 seconds for manual testing...\n');

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--start-maximized'],
    devtools: false
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1400, height: 900 });

  try {
    console.log('Loading game with FM and PRM...');
    await page.goto('https://cwo.freeddns.org/HB/?setup=4:GC-FM-PRM-BG', {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    console.log('✓ Page loaded\n');
    console.log('==> Browser is open. Please test the faction cards manually.');
    console.log('    Browser will auto-close in 90 seconds...\n');

    // Wait 90 seconds
    await new Promise(r => setTimeout(r, 90000));

  } catch (e) {
    console.error(`Error: ${e.message}`);
  }

  await browser.close();
  console.log('\n✓ Verification complete');
  console.log('\nIf both faction cards opened without crashing and all unit images');
  console.log('appeared correctly, the fix is working.');
}

verify().catch(console.error);
