#!/usr/bin/env node
/**
 * Test FM and PRM faction card clicks to verify unit info images load
 */
import puppeteer from 'puppeteer';

async function testFactionCard(faction, url) {
  console.log(`\n=== Testing ${faction} faction card ===`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  // Listen for console errors
  const errors = [];
  page.on('pageerror', error => {
    errors.push(error.message);
    console.log(`  ✗ Page error: ${error.message}`);
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
      console.log(`  ✗ Console error: ${msg.text()}`);
    }
  });

  try {
    console.log(`  Loading game...`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Wait for game to initialize
    await new Promise(r => setTimeout(r, 3000));
    console.log(`  Game loaded`);

    // Try to find and click the faction card
    console.log(`  Looking for ${faction} faction card...`);
    const cardSelector = `.faction-token.${faction.toLowerCase()}`;

    try {
      await page.waitForSelector(cardSelector, { timeout: 5000 });
      console.log(`  Found faction card`);

      // Click the card
      console.log(`  Clicking faction card...`);
      await page.click(cardSelector);

      // Wait a bit for overlay to load
      await new Promise(r => setTimeout(r, 2000));
      console.log(`  Card clicked, overlay should be visible`);

      // Check if overlay appeared
      const overlayVisible = await page.evaluate(() => {
        const overlay = document.querySelector('.overlay');
        return overlay && overlay.style.display !== 'none';
      });

      if (overlayVisible) {
        console.log(`  ✓ Overlay appeared`);

        // Check for missing images
        const missingImages = await page.evaluate(() => {
          const imgs = document.querySelectorAll('.overlay img');
          const missing = [];
          imgs.forEach(img => {
            if (!img.complete || img.naturalWidth === 0) {
              missing.push(img.src);
            }
          });
          return missing;
        });

        if (missingImages.length > 0) {
          console.log(`  ✗ Missing images:`);
          missingImages.forEach(src => console.log(`    - ${src}`));
        } else {
          console.log(`  ✓ All images loaded`);
        }
      } else {
        console.log(`  ✗ Overlay did not appear`);
        errors.push('Overlay did not appear');
      }

    } catch (e) {
      console.log(`  ✗ Could not interact with card: ${e.message}`);
      errors.push(e.message);
    }

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}`);
    errors.push(e.message);
  }

  await browser.close();

  return { faction, success: errors.length === 0, errors };
}

async function runTests() {
  const baseUrl = 'http://localhost:8765/?setup=4:GC-';

  const tests = [
    { faction: 'FM', url: baseUrl + 'FM-CC-BG' },
    { faction: 'PRM', url: baseUrl + 'PRM-CC-BG' }
  ];

  console.log('=== FACTION CARD CLICK TEST ===');
  console.log(`Testing faction cards for unit info image loading\n`);

  const results = [];

  for (const test of tests) {
    const result = await testFactionCard(test.faction, test.url);
    results.push(result);
  }

  console.log('\n=== RESULTS ===\n');
  const passed = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  if (passed.length > 0) {
    console.log(`✓ PASSED (${passed.length}): ${passed.map(r => r.faction).join(', ')}`);
  }
  if (failed.length > 0) {
    console.log(`✗ FAILED (${failed.length}): ${failed.map(r => r.faction).join(', ')}`);
    failed.forEach(r => {
      console.log(`\n  ${r.faction}:`);
      r.errors.forEach(e => console.log(`    - ${e}`));
    });
  }

  return failed.length === 0;
}

runTests()
  .then(success => process.exit(success ? 0 : 1))
  .catch(err => {
    console.error(err);
    process.exit(1);
  });
