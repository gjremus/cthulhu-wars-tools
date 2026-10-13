#!/usr/bin/env node
/**
 * Detect if the page is being reloaded
 */
import puppeteer from 'puppeteer';

async function detectReload() {
  console.log('=== DGT RELOAD DETECTION ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  let navigations = 0;
  let frameReloads = 0;

  page.on('framenavigated', frame => {
    frameReloads++;
    console.log(`\n>>> FRAME NAVIGATED (${frameReloads}) <<<`);
    console.log(`URL: ${frame.url()}`);
    console.log(`Name: ${frame.name() || '(main)'}`);
  });

  page.on('response', response => {
    const url = response.url();
    const status = response.status();
    // Log main page reloads
    if (url.includes('HB/?setup') && status === 200) {
      console.log(`[MAIN PAGE RESPONSE] ${status} ${url}`);
    }
  });

  page.on('framedetached', frame => {
    console.log(`\n!!! FRAME DETACHED !!!\n`);
  });

  try {
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`Loading: ${url}\n`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log(`Initial load complete (${frameReloads} frame navigations)\n`);

    // Wait through the crash point
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 1000));
      console.log(`[${i + 1}s] Navigations so far: ${frameReloads}`);
    }

  } catch (e) {
    console.log(`Error: ${e.message}`);
  }

  await browser.close();

  console.log(`\n=== SUMMARY ===`);
  console.log(`Total frame navigations: ${frameReloads}`);
  console.log(`(Initial load = 1, any reloads = additional count)`);
}

detectReload().catch(console.error);
