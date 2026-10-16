#!/usr/bin/env node
/**
 * Capture detailed console output to debug crash
 */
import puppeteer from 'puppeteer';

async function debugCrash(faction) {
  console.log(`\n=== Debugging ${faction} crash ===`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();

  // Capture ALL console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error' || type === 'warn' || text.includes('404') || text.includes('Failed')) {
      console.log(`  [${type}] ${text}`);
    }
  });

  // Capture JavaScript errors
  page.on('pageerror', error => {
    console.log(`  [pageerror] ${error.message}`);
    if (error.stack) {
      console.log(`    Stack: ${error.stack.substring(0, 200)}`);
    }
  });

  // Capture response errors
  page.on('response', response => {
    if (response.status() >= 400) {
      console.log(`  [HTTP ${response.status()}] ${response.url()}`);
    }
  });

  try {
    const url = `https://cwo.freeddns.org/HB/?setup=4:GC-${faction}-CC-BG`;
    console.log(`  Loading: ${url}\n`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    console.log(`\n  Waiting 15 seconds to see what happens...`);
    await new Promise(r => setTimeout(r, 15000));

    console.log(`  No crash detected after 15 seconds`);

  } catch (e) {
    console.log(`  Exception: ${e.message}`);
  }

  await browser.close();
}

async function run() {
  await debugCrash('FM');
}

run().catch(console.error);
