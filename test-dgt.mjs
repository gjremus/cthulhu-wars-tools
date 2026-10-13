#!/usr/bin/env node
/**
 * Minimal test to check DGT faction for console errors
 */
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;
const TIMEOUT = 60000;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`Testing DGT faction...`);
  console.log(`Starting at: ${START_URL}`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1280, height: 800 }
  });

  const page = await browser.newPage();
  const errors = [];

  // Capture console logs and errors
  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();

    console.log(`[${type.toUpperCase()}] ${text}`);

    if (type === 'error') {
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink')) {
        errors.push(text);
      }
    }
  });

  // Capture JavaScript exceptions
  page.on('pageerror', err => {
    console.log(`[EXCEPTION] ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('\n1. Loading main page...');
    await page.goto(START_URL, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await wait(2000);

    console.log('2. Looking for faction picker button...');
    const pickerClicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
      const pickerBtn = buttons.find(b => {
        const text = (b.textContent || '').toLowerCase();
        return text.includes('alternative') ||
               text.includes('picker') ||
               text.includes('4 player') ||
               text.includes('select faction');
      });

      if (pickerBtn) {
        pickerBtn.click();
        return true;
      }
      return false;
    });

    if (!pickerClicked) {
      console.log('Note: Could not find faction picker button');
    } else {
      console.log('3. Clicked picker button, waiting...');
      await wait(2000);

      console.log('4. Looking for DGT faction in picker...');
      const clickedFaction = await page.evaluate(() => {
        const elements = Array.from(document.querySelectorAll('button, div, span, label'));
        const factionElement = elements.find(el => {
          const text = el.textContent || '';
          return text.includes('DGT') || text.includes('Tribulation') || text.includes('The Tribulation');
        });

        if (factionElement) {
          factionElement.click();
          return true;
        }
        return false;
      });

      if (clickedFaction) {
        console.log('   ✓ Found and clicked DGT');
        await wait(1000);

        // Select 3 more factions
        for (const otherFaction of ['GC', 'CC', 'BG']) {
          const clicked = await page.evaluate((f) => {
            const elements = Array.from(document.querySelectorAll('button, div, span, label'));
            const el = elements.find(e => (e.textContent || '').includes(f));
            if (el) {
              el.click();
              return true;
            }
            return false;
          }, otherFaction);

          if (clicked) {
            console.log(`   ✓ Selected ${otherFaction}`);
            await wait(500);
          }
        }

        console.log('5. Looking for Continue/Start Game button...');
        const continueClicked = await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const continueBtn = buttons.find(b => {
            const text = (b.textContent || '').toLowerCase();
            return text.includes('continue') || text.includes('start') || text.includes('generate');
          });

          if (continueBtn) {
            continueBtn.click();
            return true;
          }
          return false;
        });

        if (continueClicked) {
          console.log('   ✓ Clicked Continue');
          await wait(3000);

          console.log('6. Checking for Online/Solo game buttons...');
          const soloClicked = await page.evaluate(() => {
            const buttons = Array.from(document.querySelectorAll('button'));
            const soloBtn = buttons.find(b => {
              const text = (b.textContent || '').toLowerCase();
              return text.includes('solo') || text.includes('single');
            });

            if (soloBtn) {
              soloBtn.click();
              return true;
            }
            return false;
          });

          if (soloClicked) {
            console.log('   ✓ Clicked Solo');
          }

          console.log('7. Waiting for game to load...');
          await wait(8000);

          console.log('8. Checking for game UI...');
          const hasGameUI = await page.evaluate(() => {
            return document.querySelector('#action') !== null ||
                   document.body.textContent.includes('Action Phase') ||
                   document.body.textContent.includes('Doom Phase');
          });

          if (hasGameUI) {
            console.log('   ✓ Game UI loaded');
          } else {
            console.log('   ✗ Game UI did not load');
          }
        }
      }
    }

  } catch (e) {
    console.log(`\n❌ ERROR: ${e.message}`);
    console.log(e.stack);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  await wait(2000);

  // Print summary
  console.log('\n=== TEST SUMMARY ===');
  if (errors.length === 0) {
    console.log('✓ NO ERRORS DETECTED');
  } else {
    console.log(`✗ ${errors.length} ERROR(S) FOUND:`);
    errors.forEach((err, idx) => {
      console.log(`  ${idx + 1}. ${err}`);
    });
  }

  await browser.close();
  process.exit(errors.length > 0 ? 1 : 0);
}

testDGT().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
