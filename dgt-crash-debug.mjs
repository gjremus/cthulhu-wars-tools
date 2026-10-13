#!/usr/bin/env node
/**
 * Deep debug for DGT faction crash.
 * Loads the faction and attempts to interact with card overlays, menus, etc.
 */
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const SETUP = `4:GC-DGT-CC-BG`;
const URL = `${SERVER}/${BUILD}/?setup=${SETUP}`;

async function debugDGT() {
  console.log(`[DGT DEBUG] Testing at ${URL}`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const errors = [];
  const warnings = [];
  const allConsoleMessages = [];

  // Capture ALL console output
  page.on('console', msg => {
    const text = msg.text();
    allConsoleMessages.push({ type: msg.type(), text });

    if (msg.type() === 'error') {
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink')) {
        errors.push(`[ERROR] ${text}`);
      }
    }
    if (msg.type() === 'warn') {
      warnings.push(`[WARN] ${text}`);
    }
  });

  // Capture exceptions
  page.on('pageerror', err => {
    errors.push(`[EXCEPTION] ${err.message}\n  Stack: ${err.stack}`);
  });

  try {
    console.log('[1] Loading page...');
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 });

    console.log('[2] Waiting 3s for JS initialization...');
    await new Promise(r => setTimeout(r, 3000));

    console.log('[3] Checking game state...');
    const gameState = await page.evaluate(() => {
      return {
        hasActionDiv: document.querySelector('#action') !== null,
        hasGameBoard: document.querySelector('.game-board') !== null,
        hasSetupUI: document.body.textContent.includes('Setup'),
        bodyText: document.body.textContent.substring(0, 500)
      };
    });
    console.log('[3] Game state:', gameState);

    console.log('[4] Checking for card overlays or menus...');
    const overlays = await page.evaluate(() => {
      const cards = document.querySelectorAll('[id*="card"], [class*="card"], [id*="overlay"], [class*="overlay"]');
      return Array.from(cards).slice(0, 5).map(el => ({
        id: el.id,
        class: el.className,
        tag: el.tagName
      }));
    });
    console.log('[4] Found overlays:', overlays);

    console.log('[5] Checking window for errors...');
    const windowErrors = await page.evaluate(() => {
      return {
        windowErrors: window.__errors || [],
        lastError: window.lastError,
        consoleErrorCount: (window.__consoleErrors || []).length
      };
    });
    console.log('[5] Window state:', windowErrors);

    console.log('[6] Looking for DGT-specific elements...');
    const dgtElements = await page.evaluate(() => {
      const search = document.body.innerHTML;
      return {
        hasDGT: search.includes('DGT') || search.includes('Tribulation'),
        hasTribu: search.includes('Tribu'),
        elementCount: document.querySelectorAll('*').length
      };
    });
    console.log('[6] DGT elements:', dgtElements);

    console.log('[7] Attempting to click on something...');
    try {
      const buttons = await page.$$eval('button, div[role="button"], a', els => {
        return els.slice(0, 3).map(el => ({
          text: el.textContent.substring(0, 50),
          tag: el.tagName
        }));
      });
      console.log('[7] Available buttons/clickables:', buttons);

      if (buttons.length > 0) {
        console.log('[8] Attempting first click...');
        const firstButton = await page.$('button, div[role="button"]');
        if (firstButton) {
          await firstButton.click();
          await new Promise(r => setTimeout(r, 2000));
          console.log('[8] Click successful, waiting for potential errors...');
        }
      }
    } catch (e) {
      console.log('[7] Click test failed (may be expected):', e.message);
    }

    console.log('[9] Final check for any errors...');
    await new Promise(r => setTimeout(r, 2000));

  } catch (e) {
    errors.push(`[LOAD CRITICAL] ${e.message}`);
    console.error('Critical error:', e);
  }

  await browser.close();

  // Report
  console.log('\n=== FINAL REPORT ===');
  console.log(`Total console messages: ${allConsoleMessages.length}`);
  console.log(`Errors captured: ${errors.length}`);
  console.log(`Warnings captured: ${warnings.length}`);

  if (allConsoleMessages.length > 0) {
    console.log('\n--- All Console Messages ---');
    allConsoleMessages.forEach(msg => {
      console.log(`[${msg.type.toUpperCase()}] ${msg.text.substring(0, 150)}`);
    });
  }

  if (warnings.length > 0) {
    console.log('\n--- Warnings ---');
    warnings.forEach(w => console.log(w));
  }

  if (errors.length > 0) {
    console.log('\n--- ERRORS ---');
    errors.forEach(e => console.log(e));
    process.exit(1);
  } else {
    console.log('\n✓ No errors detected during deep test.');
    process.exit(0);
  }
}

debugDGT().catch(e => {
  console.error('Script error:', e);
  process.exit(1);
});
