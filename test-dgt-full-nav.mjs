#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`\n=== TESTING DGT FACTION ===\n`);

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
      console.log(`  ERROR: ${text}`);
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`  EXCEPTION: ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Step 1: Load page...');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await wait(3000);
    console.log('  OK');

    console.log('Step 2: Click "Quick Game"...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find(b => b.textContent.includes('Quick Game'));
      if (btn) btn.click();
    });
    await wait(3000);
    console.log('  OK');
    await page.screenshot({ path: '/tmp/dgt-after-quickgame.png' });

    console.log('Step 3: Look for faction selector...');
    const hasSelector = await page.evaluate(() => {
      return document.body.textContent.includes('faction') ||
             document.body.textContent.includes('Faction');
    });
    console.log(`  Found faction selector: ${hasSelector}`);
    
    console.log('Step 4: Click on "Alternative Faction Picker" or similar...');
    const clicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button, div[role="button"], span'));
      const btn = buttons.find(b => {
        const t = (b.textContent || '').toLowerCase();
        return t.includes('alternative') || 
               t.includes('picker') ||
               t.includes('4 player') ||
               t.includes('select faction');
      });
      if (btn) {
        console.log(`Clicking: ${btn.textContent.substring(0, 50)}`);
        btn.click();
        return true;
      }
      return false;
    });

    if (clicked) {
      await wait(2000);
      await page.screenshot({ path: '/tmp/dgt-after-picker-click.png' });
      console.log('  OK - opened picker');

      console.log('Step 5: Find DGT in faction list...');
      const dgtFound = await page.evaluate(() => {
        const items = Array.from(document.querySelectorAll('label, div, span, button'));
        const dgtItem = items.find(item => {
          const text = item.textContent || '';
          return text.includes('DGT') || text.includes('Tribulation');
        });
        if (dgtItem) {
          console.log(`Found DGT: ${dgtItem.textContent.substring(0, 80)}`);
          dgtItem.click();
          return true;
        }
        return false;
      });

      if (dgtFound) {
        await wait(1500);
        await page.screenshot({ path: '/tmp/dgt-after-select.png' });
        console.log('  OK - selected DGT');

        console.log('Step 6: Select 3 more factions...');
        for (const faction of ['GC', 'CC', 'BG']) {
          await page.evaluate((f) => {
            const items = Array.from(document.querySelectorAll('label, div, span, button'));
            const item = items.find(i => (i.textContent || '').includes(f));
            if (item) item.click();
          }, faction);
          await wait(500);
        }
        console.log('  OK');

        console.log('Step 7: Click Continue/Generate...');
        const continueClicked = await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const btn = buttons.find(b => {
            const t = (b.textContent || '').toLowerCase();
            return t.includes('continue') || 
                   t.includes('generate') ||
                   t.includes('start');
          });
          if (btn) {
            console.log(`Clicking: ${btn.textContent}`);
            btn.click();
            return true;
          }
          return false;
        });

        if (continueClicked) {
          await wait(4000);
          await page.screenshot({ path: '/tmp/dgt-game-starting.png' });
          console.log('  OK');

          console.log('Step 8: Wait for game to fully load...');
          await wait(6000);
          await page.screenshot({ path: '/tmp/dgt-game-loaded.png' });
          console.log('  OK');

          console.log('Step 9: Check game state...');
          const gameState = await page.evaluate(() => {
            const hasUI = document.querySelector('#action') !== null;
            const hasText = document.body.textContent;
            const hasDGT = hasText.includes('DGT') || hasText.includes('Tribulation');
            const hasSpellbook = hasText.includes('Spellbook') || hasText.includes('Action Phase');
            return { hasUI, hasDGT, hasSpellbook };
          });
          console.log(`  Game UI loaded: ${gameState.hasUI}`);
          console.log(`  DGT present: ${gameState.hasDGT}`);
          console.log(`  Spellbooks/Actions: ${gameState.hasSpellbook}`);
        }
      }
    }

  } catch (e) {
    console.log(`  ERROR: ${e.message}`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  console.log('\n=== RESULTS ===\n');
  if (errors.length === 0) {
    console.log('✓ NO JAVASCRIPT ERRORS');
  } else {
    console.log(`✗ ${errors.length} ERROR(S):`);
    errors.forEach(err => console.log(`  - ${err}`));
  }

  console.log('\nScreenshots saved:');
  console.log('  /tmp/dgt-after-quickgame.png');
  console.log('  /tmp/dgt-after-picker-click.png');
  console.log('  /tmp/dgt-after-select.png');
  console.log('  /tmp/dgt-game-starting.png');
  console.log('  /tmp/dgt-game-loaded.png\n');

  await browser.close();
  process.exit(errors.length > 0 ? 1 : 0);
}

testDGT().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
