#!/usr/bin/env node
/**
 * Debug what causes the crash
 */
import puppeteer from 'puppeteer';

async function testLoad(faction) {
  console.log(`\n=== Testing ${faction} ===`);

  const browser = await puppeteer.launch({
    headless: false,  // Show browser to see what's happening
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    devtools: true
  });

  const page = await browser.newPage();
  let crashed = false;
  const errors = [];

  page.on('framedetached', () => {
    crashed = true;
    console.log(`  ✗ Page crashed (frame detached)`);
  });

  page.on('pageerror', error => {
    errors.push(error.message);
    console.log(`  ✗ JS Error: ${error.message}`);
    console.log(`     Stack: ${error.stack}`);
  });

  page.on('console', msg => {
    const type = msg.type();
    if (type === 'error' || type === 'warning') {
      console.log(`  [${type}] ${msg.text()}`);
    }
  });

  try {
    console.log(`  Loading game...`);
    const url = `http://localhost:9876/?setup=4:GC-${faction}-CC-BG`;
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    console.log(`  Page loaded, waiting 20 seconds to see if it crashes...`);
    // Wait 20 seconds to see if it crashes
    for (let i = 0; i < 20; i++) {
      if (crashed) {
        console.log(`  Crashed at ${i} seconds`);
        break;
      }
      await new Promise(r => setTimeout(r, 1000));
    }

    if (!crashed) {
      console.log(`  ✓ Page loaded without crashing`);
    }

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}`);
  }

  console.log(`\n  Keeping browser open for 10 more seconds for manual inspection...`);
  await new Promise(r => setTimeout(r, 10000));

  await browser.close();

  return { faction, crashed, errors };
}

async function run() {
  // Test just FM first
  await testLoad('FM');
}

run().catch(console.error);
