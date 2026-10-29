#!/usr/bin/env node
/**
 * Test FM and PRM on live server
 */
import puppeteer from 'puppeteer';

async function testFaction(faction) {
  console.log(`\n=== Testing ${faction} on live server ===`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  let crashed = false;

  page.on('framedetached', () => {
    crashed = true;
    console.log(`  ✗ Page crashed`);
  });

  page.on('pageerror', error => {
    console.log(`  ✗ JS Error: ${error.message}`);
  });

  try {
    const url = `https://cwo.freeddns.org/HB/?setup=4:GC-${faction}-CC-BG`;
    console.log(`  Loading: ${url}`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Wait 10 seconds
    for (let i = 0; i < 10; i++) {
      if (crashed) break;
      await new Promise(r => setTimeout(r, 1000));
    }

    if (!crashed) {
      console.log(`  ✓ Game loaded without crashing`);

      // Try to trigger faction overlay
      console.log(`  Testing faction card overlay...`);
      const overlayTest = await page.evaluate((f) => {
        try {
          if (typeof onExternalClick === 'function') {
            onExternalClick(f);
            return { success: true, message: 'Overlay triggered' };
          }
          return { success: false, message: 'onExternalClick not found' };
        } catch (e) {
          return { success: false, message: e.message };
        }
      }, faction);

      console.log(`  ${overlayTest.success ? '✓' : '✗'} ${overlayTest.message}`);

      if (overlayTest.success) {
        await new Promise(r => setTimeout(r, 2000));

        // Check images loaded
        const imageCheck = await page.evaluate(() => {
          const overlay = document.querySelector('.overlay');
          if (!overlay) return { found: false, images: [] };

          const imgs = overlay.querySelectorAll('img[src*="/info/"]');
          return {
            found: true,
            images: Array.from(imgs).map(img => ({
              src: img.src.split('/').pop(),
              loaded: img.complete && img.naturalWidth > 0
            }))
          };
        });

        if (imageCheck.found) {
          const loaded = imageCheck.images.filter(i => i.loaded).length;
          const total = imageCheck.images.length;
          console.log(`  ✓ Overlay visible, ${loaded}/${total} images loaded`);
          if (loaded < total) {
            imageCheck.images.filter(i => !i.loaded).forEach(img => {
              console.log(`    ✗ Failed: ${img.src}`);
            });
          }
        } else {
          console.log(`  ✗ Overlay not found`);
        }
      }
    }

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}`);
  }

  await browser.close();

  return { faction, crashed };
}

async function run() {
  console.log('=== LIVE SERVER TEST ===');
  console.log('Testing FM and PRM faction cards on https://cwo.freeddns.org/HB/\n');

  const results = [];

  for (const faction of ['FM', 'PRM']) {
    const result = await testFaction(faction);
    results.push(result);
  }

  console.log('\n=== RESULTS ===\n');
  const ok = results.filter(r => !r.crashed);
  const failed = results.filter(r => r.crashed);

  if (ok.length > 0) {
    console.log(`✓ OK: ${ok.map(r => r.faction).join(', ')}`);
  }
  if (failed.length > 0) {
    console.log(`✗ CRASHED: ${failed.map(r => r.faction).join(', ')}`);
  }

  return failed.length === 0;
}

run()
  .then(success => process.exit(success ? 0 : 1))
  .catch(err => {
    console.error(err);
    process.exit(1);
  });
