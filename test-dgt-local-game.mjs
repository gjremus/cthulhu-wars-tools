#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`\n=== DGT FACTION CRASH TEST ===\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1400, height: 900 }
  });

  const page = await browser.newPage();
  const errors = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();

    if (type === 'error' && 
        !text.includes('Failed to load resource') && 
        !text.includes('favicon') &&
        !text.includes('404')) {
      console.log(`[CONSOLE ERROR]\n  ${text}\n`);
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`[UNCAUGHT EXCEPTION]\n  ${err.message}\n`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Step 1: Loading main page...');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await wait(2000);
    console.log('  OK\n');

    console.log('Step 2: Clicking "Local Game"...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find(b => b.textContent.trim() === 'Local Game');
      if (btn) {
        console.log(`Clicking button with text: "${btn.textContent}"`);
        btn.click();
      }
    });
    await wait(4000);
    console.log('  OK\n');

    console.log('Step 3: Taking screenshot of faction selector...');
    await page.screenshot({ path: '/tmp/dgt-local-game-screen.png' });
    console.log('  Saved to /tmp/dgt-local-game-screen.png\n');

    console.log('Step 4: Looking for faction picker or selector...');
    const pickerState = await page.evaluate(() => {
      const hasAlternativePicker = document.body.textContent.includes('Alternative');
      const hasButtonText = document.body.textContent.includes('Continue');
      const buttons = Array.from(document.querySelectorAll('button'));
      const buttonTexts = buttons.map(b => b.textContent.trim()).filter(t => t.length > 0);
      
      return {
        hasAlternativePicker,
        hasButtonText,
        buttonCount: buttons.length,
        visibleButtons: buttonTexts.slice(0, 15)
      };
    });

    console.log(`  Buttons found: ${pickerState.buttonCount}`);
    console.log(`  Visible buttons: ${pickerState.visibleButtons.join(', ')}\n`);

    console.log('Step 5: Looking for DGT faction...');
    const hasDGT = await page.evaluate(() => {
      return document.body.textContent.includes('DGT') || 
             document.body.textContent.includes('Tribulation');
    });

    console.log(`  DGT found on page: ${hasDGT}\n`);

    if (hasDGT) {
      console.log('Step 6: Clicking DGT faction...');
      const dgtClicked = await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('label, input, span, button, div'));
        const dgt = items.find(item => 
          (item.textContent || '').includes('DGT') || 
          (item.textContent || '').includes('Tribulation'));
        
        if (dgt) {
          console.log(`Found: ${dgt.textContent.substring(0, 80)}`);
          
          // If it's a checkbox/input, check it
          const input = dgt.querySelector('input') || 
                        (dgt.tagName === 'INPUT' ? dgt : null);
          if (input) {
            input.checked = true;
            input.dispatchEvent(new Event('change', { bubbles: true }));
          } else {
            dgt.click();
          }
          return true;
        }
        return false;
      });

      if (dgtClicked) {
        await wait(2000);
        console.log('  OK\n');

        console.log('Step 7: Finding and clicking Continue button...');
        const continueClicked = await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(b => {
            const t = b.textContent.toLowerCase();
            return t.includes('continue') || t.includes('generate') || t.includes('start');
          });
          if (btn) {
            console.log(`Clicking: "${btn.textContent}"`);
            btn.click();
            return true;
          }
          return false;
        });

        if (continueClicked) {
          console.log('  OK\n');
          
          console.log('Step 8: Waiting for game to load...');
          await wait(6000);

          console.log('Step 9: Taking screenshot of loaded game...');
          await page.screenshot({ path: '/tmp/dgt-game-loaded-final.png' });
          console.log('  Saved to /tmp/dgt-game-loaded-final.png\n');

          console.log('Step 10: Checking for faction sheet and spellbooks...');
          const gameUI = await page.evaluate(() => {
            const hasActionDiv = document.querySelector('#action') !== null;
            const hasText = document.body.textContent;
            const hasDGT = hasText.includes('DGT') || hasText.includes('Tribulation');
            const hasSpellbook = hasText.includes('Spellbook');
            const hasActionPhase = hasText.includes('Action Phase');
            const hasFactSheet = hasText.includes('Faction Sheet');

            return { hasActionDiv, hasDGT, hasSpellbook, hasActionPhase, hasFactSheet };
          });

          console.log(`  Action div present: ${gameUI.hasActionDiv}`);
          console.log(`  DGT faction visible: ${gameUI.hasDGT}`);
          console.log(`  Spellbooks visible: ${gameUI.hasSpellbook}`);
          console.log(`  Action Phase text: ${gameUI.hasActionPhase}`);
          console.log(`  Faction Sheet visible: ${gameUI.hasFactSheet}\n`);
        }
      }
    }

  } catch (e) {
    console.log(`ERROR: ${e.message}\n`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  console.log('=== RESULTS ===\n');
  if (errors.length === 0) {
    console.log('✓ NO JAVASCRIPT ERRORS OR EXCEPTIONS DETECTED');
    console.log('\nThe game loaded without console errors.');
    console.log('If the faction sheet and spellbooks are missing,');
    console.log('it is NOT due to a JavaScript error.');
  } else {
    console.log(`✗ FOUND ${errors.length} ERROR(S):\n`);
    errors.forEach((err, i) => {
      console.log(`${i + 1}. ${err}\n`);
    });
  }

  await browser.close();
}

testDGT().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
