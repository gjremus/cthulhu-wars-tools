#!/usr/bin/env node
/**
 * Simple visual test - opens browser and waits for manual verification
 */
import puppeteer from 'puppeteer';

async function testFactions() {
  console.log('Opening browser for manual faction card test...');
  console.log('');
  console.log('Instructions:');
  console.log('1. Click on the FM faction card (pink)');
  console.log('2. Check if all unit images load (should see 5 units)');
  console.log('3. Close the overlay');
  console.log('4. Click on the PRM faction card (red)');
  console.log('5. Check if all unit images load (should see 4 units)');
  console.log('6. Browser will stay open for 60 seconds, then auto-close');
  console.log('');

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    devtools: true
  });

  const page = await browser.newPage();

  page.on('console', msg => {
    if (msg.type() === 'error') {
      console.log(`❌ ${msg.text()}`);
    }
  });

  try {
    console.log('Loading game with FM and PRM...');
    await page.goto('http://localhost:8765/?setup=4:GC-FM-PRM-BG', {
      waitUntil: 'domcontentloaded',
      timeout: 30000
    });

    console.log('✓ Page loaded');
    console.log('');
    console.log('==> Browser is open. Test the faction cards manually.');
    console.log('    Will auto-close in 60 seconds...');

    // Wait 60 seconds
    await new Promise(r => setTimeout(r, 60000));

  } catch (e) {
    console.error(`Error: ${e.message}`);
  }

  await browser.close();
  console.log('\n✓ Test complete');
}

testFactions().catch(console.error);
