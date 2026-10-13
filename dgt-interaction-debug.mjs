#!/usr/bin/env node
/**
 * Try to trigger DGT-specific interactions to find the crash point
 */
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const SETUP = `4:GC-DGT-CC-BG`;
const URL = `${SERVER}/${BUILD}/?setup=${SETUP}`;

async function triggerDGT() {
  console.log(`Testing DGT interactions...`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const errors = [];

  // Intercept and log ALL network requests
  page.on('response', response => {
    if (!response.ok() && !response.url().includes('favicon')) {
      console.log(`[NETWORK] ${response.status()} ${response.url()}`);
    }
  });

  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error') {
      if (!text.includes('Failed to load') && !text.includes('favicon')) {
        errors.push(`[CONSOLE ERROR] ${text}`);
      }
    }
  });

  page.on('pageerror', err => {
    errors.push(`[PAGE ERROR] ${err.message}`);
  });

  try {
    console.log('Loading game...');
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 });

    await new Promise(r => setTimeout(r, 3000));

    // Inject a function to hook into the game's action system
    console.log('Injecting error capture hook...');
    await page.evaluateOnNewDocument(() => {
      window.__capturedErrors = [];
      window.__dgtDebug = {};

      // Hook into any method called
      const oldError = console.error;
      console.error = function(...args) {
        window.__capturedErrors.push({ type: 'console.error', args: args.map(a => String(a)) });
        return oldError.apply(console, args);
      };

      // Try to capture render errors
      if (window.React) {
        console.log('React found');
      }
    });

    // Wait for action phase
    console.log('Waiting for action phase...');
    await new Promise(r => setTimeout(r, 5000));

    // Try to find and click DGT-specific UI elements
    console.log('Looking for DGT faction card or menu...');
    const dgtUI = await page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll('*')).filter(el => {
        const text = el.textContent || '';
        const id = el.id || '';
        const cls = el.className || '';
        return text.includes('DGT') || text.includes('Tribulation') ||
               id.includes('dgt') || id.includes('tribulation') ||
               cls.includes('dgt') || cls.includes('tribulation');
      });
      return elements.slice(0, 10).map(el => ({
        tag: el.tagName,
        id: el.id,
        class: el.className,
        text: el.textContent.substring(0, 100)
      }));
    });
    console.log('DGT UI elements found:', dgtUI.length);
    if (dgtUI.length > 0) {
      console.log(dgtUI.slice(0, 3));
    }

    // Try to trigger card overlay
    console.log('Attempting to view faction card...');
    try {
      // Look for cards or overlay triggers
      await page.evaluate(() => {
        const cardId = document.querySelector('[id*="dgt-card"], [id*="tribulation-card"]');
        const anyCard = document.querySelector('[id*="card"]:not(.library-hint)');
        if (cardId) {
          console.log('Found DGT card');
          cardId.click();
        } else if (anyCard) {
          console.log('Found a card, clicking');
          anyCard.click();
        } else {
          console.log('No card found');
        }
      });
      await new Promise(r => setTimeout(r, 2000));
    } catch (e) {
      console.log('Card trigger error (may be expected):', e.message);
    }

    // Check for accumulated errors
    console.log('Checking for accumulated errors...');
    const accumulatedErrors = await page.evaluate(() => {
      return window.__capturedErrors || [];
    });

    if (accumulatedErrors.length > 0) {
      console.log('Accumulated errors:', accumulatedErrors);
      accumulatedErrors.forEach(err => errors.push(`[ACCUMULATED] ${JSON.stringify(err)}`));
    }

  } catch (e) {
    errors.push(`[TEST ERROR] ${e.message}`);
  }

  await browser.close();

  console.log('\n=== RESULT ===');
  if (errors.length === 0) {
    console.log('✓ No errors detected');
  } else {
    console.log(`✗ ${errors.length} error(s) found:`);
    errors.forEach(e => console.log(`  ${e}`));
  }

  process.exit(errors.length > 0 ? 1 : 0);
}

triggerDGT().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
