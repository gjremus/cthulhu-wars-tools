#!/usr/bin/env node
/**
 * Comprehensive DGT test: load and try faction card rendering
 */
import puppeteer from 'puppeteer';

async function comprehensiveTest() {
  console.log('=== COMPREHENSIVE DGT TEST ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-web-resources']
  });

  const page = await browser.newPage();
  const allErrors = [];
  const allWarnings = [];

  // Capture ALL console output verbatim
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    const location = msg.location();

    if (type === 'error') {
      console.log(`\n[CONSOLE ERROR] ${text}`);
      if (location && location.url) {
        console.log(`  Location: ${location.url}:${location.lineNumber}:${location.columnNumber}`);
      }
      allErrors.push({ type: 'console', text, location });
    } else if (type === 'warn') {
      console.log(`[WARN] ${text}`);
      allWarnings.push(text);
    } else if (type === 'log') {
      // Filter noise
      if (!text.includes('SVGAnimationElement') && text.length < 200) {
        console.log(`[LOG] ${text}`);
      }
    }
  });

  page.on('pageerror', err => {
    console.log(`\n[UNCAUGHT EXCEPTION] ${err.name}: ${err.message}`);
    console.log(`Stack:\n${err.stack}`);
    allErrors.push({ type: 'exception', name: err.name, message: err.message, stack: err.stack });
  });

  page.on('response', response => {
    if (!response.ok()) {
      const status = response.status();
      const url = response.url();
      if (!url.includes('favicon') && status !== 304) {
        console.log(`[HTTP ${status}] ${url}`);
        allErrors.push({ type: 'http', status, url });
      }
    }
  });

  try {
    console.log('Step 1: Navigate to direct game URL...');
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
    console.log('✓ Navigation complete\n');

    console.log('Step 2: Wait for game render (5 seconds)...');
    await new Promise(r => setTimeout(r, 5000));
    console.log('✓ Wait complete\n');

    console.log('Step 3: Check for DGT faction references...');
    const dgtCheck = await page.evaluate(() => {
      const bodyText = document.body.textContent;
      return {
        hasDGT: bodyText.includes('DGT'),
        hasTribulation: bodyText.includes('Tribulation'),
        hasPestilence: bodyText.includes('Pestilence'),
        hasWar: bodyText.includes('War'),
        hasFamine: bodyText.includes('Famine'),
        hasDeath: bodyText.includes('Death'),
        overlayDiv: document.querySelector('#overlay') !== null,
        actionDiv: document.querySelector('#action') !== null
      };
    });
    console.log('DGT faction visible:', JSON.stringify(dgtCheck, null, 2));

    console.log('\nStep 4: Attempt to trigger DGT card display...');
    try {
      await page.evaluate(() => {
        console.log('Attempting to call onExternalClick("DGT")...');
        if (typeof onExternalClick === 'function') {
          onExternalClick('DGT');
          console.log('onExternalClick("DGT") called successfully');
        } else {
          console.log('onExternalClick not found!');
        }
      });
      await new Promise(r => setTimeout(r, 2000));
      console.log('✓ Card display attempted\n');
    } catch (e) {
      console.log(`Note: Card display attempt error (may be expected): ${e.message}\n`);
    }

    console.log('Step 5: Look for overlay content...');
    const overlayContent = await page.evaluate(() => {
      const overlay = document.querySelector('#overlay');
      if (!overlay) return 'No overlay div found';
      const text = overlay.textContent;
      return text.substring(0, 500);
    });
    console.log('Overlay content (first 500 chars):', overlayContent.substring(0, 200));

    console.log('\nStep 6: Final wait (3 seconds)...');
    await new Promise(r => setTimeout(r, 3000));

  } catch (e) {
    console.log(`\n[NAVIGATION/TEST ERROR] ${e.message}`);
    console.log(e.stack);
    allErrors.push({ type: 'test', message: e.message, stack: e.stack });
  }

  await browser.close();

  console.log('\n\n=== FINAL REPORT ===');
  console.log(`Total console errors: ${allErrors.length}`);
  console.log(`Total warnings: ${allWarnings.length}`);

  if (allErrors.length > 0) {
    console.log('\n--- ERRORS ---');
    allErrors.forEach((err, i) => {
      console.log(`${i + 1}. [${err.type}] ${err.message || err.text || err.name || JSON.stringify(err)}`);
    });
    process.exit(1);
  } else {
    console.log('\n✓ NO ERRORS OR EXCEPTIONS DETECTED');
    process.exit(0);
  }
}

comprehensiveTest().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
