#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`Testing DGT faction on ${START_URL}\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1280, height: 800 }
  });

  const page = await browser.newPage();
  const errors = [];
  const loggedMessages = [];

  // Capture ALL console messages
  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    loggedMessages.push({ type, text });

    // Print in real-time
    if (type === 'error') {
      const isAsset = text.includes('Failed to load resource') || text.includes('favicon');
      const prefix = isAsset ? '[ASSET ERROR]' : '[CONSOLE ERROR]';
      console.log(`${prefix} ${text}`);
      if (!isAsset) errors.push(text);
    } else if (type === 'log') {
      console.log(`[LOG] ${text}`);
    } else if (type === 'warn') {
      console.log(`[WARN] ${text}`);
    }
  });

  page.on('pageerror', err => {
    console.log(`[UNCAUGHT EXCEPTION] ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Loading main page...\n');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await wait(2000);

    console.log('\nLooking for faction picker...\n');
    const pickerInfo = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const found = buttons.find(b => {
        const text = (b.textContent || '').toLowerCase();
        return text.includes('alternative') || text.includes('picker') || text.includes('4 player');
      });
      return found ? found.textContent.substring(0, 50) : null;
    });

    if (pickerInfo) {
      console.log(`Found picker button: "${pickerInfo}"`);
      await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const btn = buttons.find(b => {
          const text = (b.textContent || '').toLowerCase();
          return text.includes('alternative') || text.includes('picker') || text.includes('4 player');
        });
        if (btn) btn.click();
      });
      await wait(3000);

      console.log('\nLooking for DGT in faction list...\n');
      const found = await page.evaluate(() => {
        const elements = Array.from(document.querySelectorAll('label, span, div, button'));
        const dgt = elements.find(el => {
          const text = el.textContent || '';
          return text.includes('DGT') || text.includes('Tribulation');
        });
        if (dgt) {
          dgt.click();
          return dgt.textContent.substring(0, 100);
        }
        return null;
      });

      if (found) {
        console.log(`Found and clicked: "${found}"\n`);
        await wait(1500);

        for (const faction of ['GC', 'CC', 'BG']) {
          await page.evaluate((f) => {
            const elements = Array.from(document.querySelectorAll('label, span, div, button'));
            const el = elements.find(e => (e.textContent || '').includes(f));
            if (el) el.click();
          }, faction);
          await wait(500);
        }

        console.log('Looking for Continue button...\n');
        const btnClicked = await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(b => {
            const text = (b.textContent || '').toLowerCase();
            return text.includes('continue') || text.includes('start') || text.includes('generate');
          });
          if (btn) {
            btn.click();
            return btn.textContent.substring(0, 50);
          }
          return null;
        });

        if (btnClicked) {
          console.log(`Clicked: "${btnClicked}"\n`);
          await wait(4000);

          console.log('Waiting for game to load and render...\n');
          await wait(5000);

          const gameState = await page.evaluate(() => {
            const hasAction = document.querySelector('#action') !== null;
            const hasPhaseText = document.body.textContent.includes('Phase');
            const hasFactionSheet = document.body.textContent.includes('Faction Sheet') ||
                                    document.body.textContent.includes('Spellbooks') ||
                                    document.body.textContent.includes('Power:');
            return { hasAction, hasPhaseText, hasFactionSheet };
          });

          console.log(`Game state check:`);
          console.log(`  - Has action div: ${gameState.hasAction}`);
          console.log(`  - Has phase text: ${gameState.hasPhaseText}`);
          console.log(`  - Has faction sheet elements: ${gameState.hasFactionSheet}\n`);
        }
      }
    }

  } catch (e) {
    console.log(`\nTest error: ${e.message}`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  await wait(1000);

  console.log('\n=== FINAL RESULTS ===\n');
  if (errors.length === 0) {
    console.log('SUCCESS: No JavaScript errors detected');
  } else {
    console.log(`FAILURE: ${errors.length} error(s) found:\n`);
    errors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`));
  }

  await browser.close();
  process.exit(errors.length > 0 ? 1 : 0);
}

testDGT().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
