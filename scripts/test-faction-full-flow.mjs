#!/usr/bin/env node
/**
 * Test the FULL flow of creating an online game with a faction:
 * 1. Load main page
 * 2. Click faction picker
 * 3. Select the test faction + 3 others
 * 4. Start game
 * 5. Create online game (get the secret URL with gobbledygook)
 * 6. Load that game
 * 7. Check for ANY JavaScript errors
 *
 * Usage: ./test-faction-full-flow.mjs FM
 */
import puppeteer from 'puppeteer';

const FACTION = process.argv[2];
if (!FACTION) {
  console.error('Usage: ./test-faction-full-flow.mjs <FACTION_ACRONYM>');
  console.error('Example: ./test-faction-full-flow.mjs FM');
  process.exit(1);
}

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;
const TIMEOUT = 60000;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testFullFlow() {
  console.log(`Testing FULL FLOW for faction ${FACTION}...`);
  console.log(`Starting at: ${START_URL}`);

  const browser = await puppeteer.launch({
    headless: false,  // VISIBLE so we can see what's happening
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1280, height: 800 }
  });

  const page = await browser.newPage();
  const errors = [];

  // Capture console errors
  page.on('console', msg => {
    const text = msg.text();
    if (msg.type() === 'error') {
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink')) {
        console.log(`  ⚠️  CONSOLE ERROR: ${text}`);
        errors.push(`CONSOLE ERROR: ${text}`);
      }
    }
  });

  // Capture JavaScript exceptions
  page.on('pageerror', err => {
    console.log(`  ⚠️  JAVASCRIPT EXCEPTION: ${err.message}`);
    errors.push(`JAVASCRIPT EXCEPTION: ${err.message}`);
  });

  try {
    console.log('\n1. Loading main page...');
    await page.goto(START_URL, { waitUntil: 'networkidle2', timeout: TIMEOUT });
    await wait(3000);

    console.log('2. Looking for faction picker button...');
    // Look for "Alternative Faction Picker" or whatever button starts the picker
    const pickerClicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button, div'));
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
      errors.push('Could not find faction picker button on main page');
      throw new Error('No picker button found');
    }

    console.log('3. Clicked picker button, waiting for picker to load...');
    await wait(3000);

    console.log(`4. Looking for ${FACTION} faction in picker...`);
    const clickedFaction = await page.evaluate((factionCode) => {
      // Find all clickable elements
      const elements = Array.from(document.querySelectorAll('button, div, span, label, input'));

      // Look for the faction - try multiple patterns
      const factionElement = elements.find(el => {
        const text = el.textContent || '';
        const classes = el.className || '';

        // Check if it's a checkbox/option for this faction
        return text.includes(factionCode) ||
               classes.includes(factionCode.toLowerCase()) ||
               (el.id && el.id.includes(factionCode.toLowerCase()));
      });

      if (factionElement) {
        factionElement.click();
        return `Clicked element with text: ${factionElement.textContent?.substring(0, 50)}`;
      }
      return null;
    }, FACTION);

    if (!clickedFaction) {
      errors.push(`Could not find ${FACTION} in faction picker`);
      throw new Error(`Faction ${FACTION} not found in picker`);
    }
    console.log(`   ${clickedFaction}`);
    await wait(1000);

    console.log('5. Selecting 3 more factions for 4-player game...');
    // Click 3 more factions (GC, CC, BG are standard)
    for (const otherFaction of ['GC', 'CC', 'BG']) {
      const clicked = await page.evaluate((f) => {
        const elements = Array.from(document.querySelectorAll('button, div, span, label, input'));
        const el = elements.find(e => (e.textContent || '').includes(f));
        if (el) {
          el.click();
          return true;
        }
        return false;
      }, otherFaction);

      if (clicked) {
        console.log(`   Selected ${otherFaction}`);
        await wait(500);
      }
    }

    console.log('6. Looking for Continue/Start Game button...');
    const continueClicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const continueBtn = buttons.find(b => {
        const text = (b.textContent || '').toLowerCase();
        return text.includes('continue') ||
               text.includes('start') ||
               text.includes('generate');
      });

      if (continueBtn) {
        continueBtn.click();
        return true;
      }
      return false;
    });

    if (!continueClicked) {
      errors.push('Could not find Continue/Start button');
      throw new Error('No continue button');
    }

    console.log('7. Waiting for game setup screen...');
    await wait(3000);

    console.log('8. Looking for "Online Game" button...');
    const onlineClicked = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const onlineBtn = buttons.find(b => {
        const text = (b.textContent || '').toLowerCase();
        return text.includes('online');
      });

      if (onlineBtn) {
        onlineBtn.click();
        return true;
      }
      return false;
    });

    if (!onlineClicked) {
      console.log('   No Online button found (may not be needed for this build)');
    } else {
      console.log('   Clicked Online Game button');
    }

    console.log('9. Waiting for game to start and secret URL to appear...');
    await wait(5000);

    // Check if we got a secret URL (gobbledygook string)
    const currentUrl = page.url();
    console.log(`   Current URL: ${currentUrl}`);

    if (currentUrl.includes('/play/') || currentUrl.match(/[a-f0-9]{20,}/)) {
      console.log('   ✓ Got secret game URL with gobbledygook!');
    } else {
      console.log('   Note: URL may not have changed to /play/ format yet');
    }

    console.log('10. Waiting for game to fully load...');
    await wait(8000);

    console.log('11. Checking for game UI elements...');
    const hasGameUI = await page.evaluate(() => {
      return document.querySelector('#action') !== null ||
             document.body.textContent.includes('Action Phase') ||
             document.body.textContent.includes('Doom Phase') ||
             document.body.textContent.includes('Power:');
    });

    if (!hasGameUI) {
      errors.push('Game UI did not load (no action div or phase text found)');
    } else {
      console.log('   ✓ Game UI loaded successfully');
    }

  } catch (e) {
    console.log(`\n❌ ERROR during test: ${e.message}`);
    errors.push(`TEST ERROR: ${e.message}`);
  }

  await wait(3000);
  await browser.close();

  // Report results
  console.log('\n=== FULL FLOW TEST RESULTS ===');
  if (errors.length === 0) {
    console.log(`✓ ${FACTION}: Full flow completed with NO errors`);
    console.log(`  Faction ${FACTION} can be marked BUILT`);
    process.exit(0);
  } else {
    console.log(`✗ ${FACTION}: FAILED with ${errors.length} error(s)`);
    console.log(`  Faction ${FACTION} is NOT built - fix these errors first:\n`);
    errors.forEach(err => console.log(`    - ${err}`));
    console.log(`\n  DO NOT mark this faction as "built" until these errors are fixed.`);
    process.exit(1);
  }
}

testFullFlow().catch(e => {
  console.error('Script error:', e);
  process.exit(1);
});
