#!/usr/bin/env node
/**
 * Test FM and PRM faction overlays by directly triggering them
 */
import puppeteer from 'puppeteer';

async function testFactionOverlay(faction, url) {
  console.log(`\n=== Testing ${faction} faction overlay ===`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  const errors = [];
  const missing404s = [];

  page.on('response', response => {
    if (response.status() === 404) {
      const url = response.url();
      if (url.includes('webp/info/')) {
        missing404s.push(url);
      }
    }
  });

  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });

  try {
    console.log(`  Loading game...`);
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Wait for game to be ready
    await new Promise(r => setTimeout(r, 5000));
    console.log(`  Game loaded`);

    // Directly trigger the faction overlay
    console.log(`  Triggering ${faction} overlay...`);
    const overlayResult = await page.evaluate((factionCode) => {
      try {
        // Call onExternalClick which is the standard way to show faction info
        if (typeof onExternalClick === 'function') {
          onExternalClick(factionCode);
          return { success: true, message: 'onExternalClick called' };
        } else {
          return { success: false, message: 'onExternalClick function not found' };
        }
      } catch (e) {
        return { success: false, message: e.message };
      }
    }, faction);

    console.log(`  Overlay trigger: ${overlayResult.message}`);

    if (!overlayResult.success) {
      errors.push(overlayResult.message);
    } else {
      // Wait for overlay to render
      await new Promise(r => setTimeout(r, 2000));

      // Check for missing images in the overlay
      const imageCheck = await page.evaluate(() => {
        const overlay = document.querySelector('.overlay');
        if (!overlay) {
          return { overlayFound: false, images: [] };
        }

        const imgs = overlay.querySelectorAll('img');
        const imageInfo = [];

        imgs.forEach(img => {
          const loaded = img.complete && img.naturalWidth > 0;
          const isInfoImage = img.src.includes('webp/info/');
          if (isInfoImage) {
            imageInfo.push({
              src: img.src,
              loaded: loaded,
              width: img.naturalWidth,
              height: img.naturalHeight
            });
          }
        });

        return { overlayFound: true, images: imageInfo };
      });

      if (!imageCheck.overlayFound) {
        console.log(`  ✗ Overlay not found after trigger`);
        errors.push('Overlay not found');
      } else {
        console.log(`  ✓ Overlay found`);
        const totalImages = imageCheck.images.length;
        const loadedImages = imageCheck.images.filter(i => i.loaded).length;

        console.log(`  Images: ${loadedImages}/${totalImages} loaded`);

        imageCheck.images.forEach(img => {
          const basename = img.src.split('/').pop();
          if (img.loaded) {
            console.log(`    ✓ ${basename} (${img.width}x${img.height})`);
          } else {
            console.log(`    ✗ ${basename} (FAILED TO LOAD)`);
            errors.push(`Failed to load: ${basename}`);
          }
        });
      }
    }

    // Report any 404s
    if (missing404s.length > 0) {
      console.log(`  ✗ 404 errors:`);
      missing404s.forEach(url => {
        const basename = url.split('/').pop();
        console.log(`    - ${basename}`);
        errors.push(`404: ${basename}`);
      });
    }

  } catch (e) {
    console.log(`  ✗ Error: ${e.message}`);
    errors.push(e.message);
  }

  await browser.close();

  return { faction, success: errors.length === 0 && missing404s.length === 0, errors };
}

async function runTests() {
  const baseUrl = 'http://localhost:9876/?setup=4:GC-';

  const tests = [
    { faction: 'FM', url: baseUrl + 'FM-CC-BG' },
    { faction: 'PRM', url: baseUrl + 'PRM-CC-BG' }
  ];

  console.log('=== FACTION OVERLAY TEST ===');
  console.log(`Testing faction overlays for unit info image loading\n`);

  const results = [];

  for (const test of tests) {
    const result = await testFactionOverlay(test.faction, test.url);
    results.push(result);
  }

  console.log('\n=== RESULTS ===\n');
  const passed = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  if (passed.length > 0) {
    console.log(`✓ PASSED (${passed.length}): ${passed.map(r => r.faction).join(', ')}`);
  }
  if (failed.length > 0) {
    console.log(`✗ FAILED (${failed.length}): ${failed.map(r => r.faction).join(', ')}`);
    failed.forEach(r => {
      console.log(`\n  ${r.faction} errors:`);
      r.errors.forEach(e => console.log(`    - ${e}`));
    });
  }

  return failed.length === 0;
}

runTests()
  .then(success => process.exit(success ? 0 : 1))
  .catch(err => {
    console.error(err);
    process.exit(1);
  });
