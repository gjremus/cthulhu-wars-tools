#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`Testing DGT Faction Crash\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1400, height: 900 }
  });

  const page = await browser.newPage();
  const errors = [];
  const allLogs = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    
    allLogs.push({ type, text });

    if (type === 'error' && 
        !text.includes('Failed to load resource') && 
        !text.includes('favicon')) {
      console.log(`[CONSOLE ERROR] ${text}`);
      if (!text.includes('404')) errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`[EXCEPTION] ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('1. Loading main page...');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await wait(2000);

    console.log('2. Clicking "Quick Game" button...');
    await page.click('button:has-text("Quick Game")').catch(async () => {
      // Fallback: find and click using XPath
      await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const btn = buttons.find(b => b.textContent.includes('Quick Game'));
        if (btn) btn.click();
      });
    });
    await wait(4000);

    console.log('3. Taking screenshot of picker screen...');
    await page.screenshot({ path: '/tmp/dgt-picker-screen.png' });

    console.log('4. Looking for factions available...');
    const factionsFound = await page.evaluate(() => {
      const text = document.body.textContent;
      console.log(`Page text includes "DGT": ${text.includes('DGT')}`);
      console.log(`Page text includes "Faction": ${text.includes('Faction')}`);
      console.log(`Page text includes "GC": ${text.includes('GC')}`);
      
      const buttons = Array.from(document.querySelectorAll('button, label, div, span'));
      const factionsText = buttons
        .filter(b => (b.textContent || '').includes('DGT') || 
                    (b.textContent || '').includes('Tribulation'))
        .map(b => b.textContent.substring(0, 60));
      
      return factionsText;
    });

    console.log(`Factions found: ${JSON.stringify(factionsFound)}\n`);

    if (factionsFound.length === 0) {
      console.log('Trying to find Alternative Picker button...');
      const pickerClicked = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button, div, span'));
        const altPicker = buttons.find(b => {
          const t = (b.textContent || '').toLowerCase();
          return t.includes('alternative') || t.includes('picker') || t.includes('select');
        });
        if (altPicker) {
          console.log(`Found picker: ${altPicker.textContent.substring(0, 50)}`);
          altPicker.click();
          return true;
        }
        return false;
      });

      if (pickerClicked) {
        await wait(3000);
        console.log('5b. Taking screenshot after picker click...');
        await page.screenshot({ path: '/tmp/dgt-after-alt-picker.png' });
      }
    }

    console.log('\n5. Now looking for DGT to select...');
    const dgtSelected = await page.evaluate(() => {
      const all = Array.from(document.querySelectorAll('button, label, div, span'));
      const dgt = all.find(el => {
        const t = el.textContent || '';
        return t.includes('DGT') || t.includes('Tribulation') || t.includes('TriBU');
      });
      if (dgt) {
        console.log(`Found DGT: ${dgt.textContent.substring(0, 80)}`);
        dgt.click();
        return true;
      }
      console.log(`No DGT found. Elements: ${all.slice(0, 20).map(a => a.textContent.substring(0, 20)).join(' | ')}`);
      return false;
    });

    if (dgtSelected) {
      await wait(2000);
      console.log('6. Selecting companion factions (GC, CC, BG)...');
      for (const faction of ['GC', 'CC', 'BG']) {
        await page.evaluate((f) => {
          const el = Array.from(document.querySelectorAll('*')).find(e => 
            (e.textContent || '').includes(f));
          if (el) el.click();
        }, faction);
        await wait(500);
      }

      console.log('7. Clicking Continue/Generate...');
      const continued = await page.evaluate(() => {
        const buttons = Array.from(document.querySelectorAll('button'));
        const btn = buttons.find(b => {
          const t = (b.textContent || '').toLowerCase();
          return t.includes('continue') || t.includes('generate') || t.includes('start');
        });
        if (btn) {
          btn.click();
          return true;
        }
        return false;
      });

      if (continued) {
        console.log('   Waiting for game to start...');
        await wait(8000);
        console.log('8. Taking final screenshot...');
        await page.screenshot({ path: '/tmp/dgt-game-final.png' });
      }
    }

  } catch (e) {
    console.log(`ERROR: ${e.message}`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  console.log('\n=== CONSOLE ERROR REPORT ===\n');
  if (errors.length === 0) {
    console.log('✓ NO JAVASCRIPT ERRORS DETECTED');
  } else {
    console.log(`✗ ${errors.length} ERRORS FOUND:\n`);
    errors.forEach((err, i) => console.log(`${i + 1}. ${err}`));
  }

  await browser.close();
}

testDGT().catch(e => console.error('Fatal:', e));
