#!/usr/bin/env node
/**
 * Debug why the frame detaches during game load
 */
import puppeteer from 'puppeteer';

async function debug() {
  console.log('=== DGT FRAME DETACH DEBUG ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  // Detailed error tracking
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      console.log(`[ERROR] ${text}`);
    }
  });

  page.on('pageerror', err => {
    console.log(`[UNCAUGHT] ${err.message}`);
  });

  page.on('framedetached', frame => {
    console.log(`\n!!! FRAME DETACHED !!!`);
    console.log(`Frame URL: ${frame.url()}`);
    console.log(`Frame name: ${frame.name()}`);
  });

  try {
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`Loading: ${url}\n`);

    // Use lower timeout to catch issues faster
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log('DOM loaded\n');

    for (let i = 1; i <= 15; i++) {
      await new Promise(r => setTimeout(r, 1000));
      console.log(`[${i}s] Page alive, frame attached: ${page.mainFrame() !== null}`);

      // Try to access the page
      try {
        const title = await page.title();
        console.log(`    Title: ${title.substring(0, 50)}`);
      } catch (e) {
        if (e.message.includes('detached')) {
          console.log(`    ERROR: Frame became detached!`);
          break;
        }
      }
    }

  } catch (e) {
    console.log(`Error: ${e.message}`);
  }

  await browser.close();
}

debug().catch(console.error);
