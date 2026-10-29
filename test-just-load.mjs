#!/usr/bin/env node
/**
 * Just load the page and see if it crashes
 */
import puppeteer from 'puppeteer';

async function testLoad(faction) {
  console.log(`\n=== Testing ${faction} ===`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  let crashed = false;

  page.on('framedetached', () => {
    crashed = true;
    console.log(`  ✗ Page crashed (frame detached)`);
  });

  page.on('pageerror', error => {
    console.log(`  ✗ JS Error: ${error.message}`);
  });

  try {
    console.log(`  Loading game...`);
    const url = `http://localhost:9876/?setup=4:GC-${faction}-CC-BG`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Wait 10 seconds to see if it crashes
    for (let i = 0; i < 10; i++) {
      if (crashed) break;
      await new Promise(r => setTimeout(r, 1000));
    }

    if (!crashed) {
      console.log(`  ✓ Page loaded without crashing`);
    }

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}`);
  }

  await browser.close();

  return { faction, crashed };
}

async function runTests() {
  console.log('=== CRASH TEST ===\n');

  const factions = ['FM', 'PRM'];
  const results = [];

  for (const f of factions) {
    const result = await testLoad(f);
    results.push(result);
  }

  console.log('\n=== RESULTS ===\n');
  const ok = results.filter(r => !r.crashed);
  const crashes = results.filter(r => r.crashed);

  if (ok.length > 0) {
    console.log(`✓ OK (${ok.length}): ${ok.map(r => r.faction).join(', ')}`);
  }
  if (crashes.length > 0) {
    console.log(`✗ CRASH (${crashes.length}): ${crashes.map(r => r.faction).join(', ')}`);
  }

  return crashes.length === 0;
}

runTests()
  .then(success => process.exit(success ? 0 : 1))
  .catch(err => {
    console.error(err);
    process.exit(1);
  });
