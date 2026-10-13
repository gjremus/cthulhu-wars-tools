#!/usr/bin/env node
/**
 * Test multiple factions to see which ones crash
 */
import puppeteer from 'puppeteer';

async function testFaction(faction) {
  const url = `https://cwo.freeddns.org/HB/?setup=4:GC-${faction}-CC-BG`;

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  let crashed = false;

  page.on('framedetached', () => {
    crashed = true;
  });

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 });

    // Wait 8 seconds to see if it crashes
    for (let i = 0; i < 8; i++) {
      if (crashed) break;
      await new Promise(r => setTimeout(r, 1000));
    }

  } catch (e) {
    // Ignore
  }

  await browser.close();

  return { faction, crashed, status: crashed ? 'CRASH' : 'OK' };
}

async function runTests() {
  console.log('=== FACTION CRASH TEST ===\n');

  const factions = ['GC', 'CC', 'BG', 'YS', 'SL', 'CS', 'DGT', 'PRM', 'FM'];
  const results = [];

  for (const f of factions) {
    process.stdout.write(`Testing ${f}... `);
    const result = await testFaction(f);
    results.push(result);
    console.log(result.status);
  }

  console.log('\n=== RESULTS ===\n');
  const crashes = results.filter(r => r.crashed);
  const ok = results.filter(r => !r.crashed);

  if (ok.length > 0) {
    console.log(`✓ OK (${ok.length}): ${ok.map(r => r.faction).join(', ')}`);
  }
  if (crashes.length > 0) {
    console.log(`✗ CRASH (${crashes.length}): ${crashes.map(r => r.faction).join(', ')}`);
  }
}

runTests().catch(console.error);
