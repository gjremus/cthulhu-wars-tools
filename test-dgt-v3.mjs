#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`\n=== TESTING DGT FACTION ===`);
  console.log(`URL: ${START_URL}\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1280, height: 800 }
  });

  const page = await browser.newPage();
  const errors = [];

  // Capture console errors and logs
  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();

    if (type === 'error') {
      if (!text.includes('Failed to load resource') && 
          !text.includes('favicon') &&
          !text.includes('404')) {
        console.log(`  ⚠️  CONSOLE ERROR: ${text}`);
        errors.push(text);
      }
    } else if (type === 'warn') {
      if (text.includes('DGT') || text.includes('Tribulation') || 
          text.includes('undefined') || text.includes('null')) {
        console.log(`  ⚠️  WARNING: ${text}`);
      }
    }
  });

  // Capture uncaught exceptions
  page.on('pageerror', err => {
    console.log(`  ⚠️  EXCEPTION: ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Step 1: Loading main page...');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await wait(3000);
    console.log('  ✓ Main page loaded\n');

    console.log('Step 2: Waiting for React to fully mount...');
    await wait(3000);
    console.log('  ✓ Waiting complete\n');

    console.log('Step 3: Finding faction picker button...');
    const pickerFound = await page.evaluate(() => {
      // Log what we see
      console.log(`Page title: ${document.title}`);
      console.log(`Body HTML length: ${document.body.innerHTML.length}`);

      const allButtons = Array.from(document.querySelectorAll('button, [role="button"], div'));
      console.log(`Found ${allButtons.length} clickable elements`);

      const button = Array.from(document.querySelectorAll('button')).find(b => {
        const t = (b.textContent || '').toLowerCase();
        return t.includes('picker') || t.includes('alternative') || t.includes('4');
      });

      if (button) {
        console.log(`Found picker button with text: ${button.textContent.substring(0, 50)}`);
        return true;
      }
      return false;
    });

    if (!pickerFound) {
      console.log('  ✗ Picker button not found - page may still be loading\n');
    } else {
      console.log('  ✓ Picker button found\n');
    }

    console.log('Step 4: Getting all visible text containing DGT...');
    const dgtText = await page.evaluate(() => {
      const fullText = document.body.innerText;
      const lines = fullText.split('\n');
      const dgtLines = lines.filter(line => 
        line.includes('DGT') || line.includes('Tribulation') || line.includes('TriBU')
      );
      return dgtLines.slice(0, 10);
    });

    if (dgtText.length > 0) {
      console.log('  Found DGT references:');
      dgtText.forEach(line => console.log(`    - "${line}"`));
    } else {
      console.log('  ✗ No DGT text found on page');
    }
    console.log();

    console.log('Step 5: Extracting console logs from page...');
    const logs = await page.evaluate(() => {
      return window.__consoleLogs || [];
    });
    console.log(`  Found ${logs.length} captured logs\n`);

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}\n`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  console.log('=== TEST RESULTS ===\n');
  if (errors.length === 0) {
    console.log('✓ NO JAVASCRIPT ERRORS DETECTED');
    console.log('  The game loaded without console errors.');
  } else {
    console.log(`✗ FOUND ${errors.length} ERROR(S):\n`);
    errors.forEach((err, i) => {
      console.log(`  ${i + 1}. ${err}`);
    });
  }

  await browser.close();
  process.exit(errors.length > 0 ? 1 : 0);
}

testDGT().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
