#!/usr/bin/env node
/**
 * Capture console output RIGHT at the crash moment
 */
import puppeteer from 'puppeteer';

async function capture() {
  console.log('=== CAPTURE DGT CRASH MOMENT ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  let consoleLines = [];

  page.on('console', msg => {
    const line = `[${msg.type()}] ${msg.text()}`;
    consoleLines.push(line);
    if (msg.type() === 'error') {
      console.log(line);
    }
  });

  page.on('pageerror', err => {
    console.log(`\n>>> UNCAUGHT EXCEPTION BEFORE DETACH <<<`);
    console.log(`${err.name}: ${err.message}`);
    console.log(`Stack:\n${err.stack}`);
    consoleLines.push(`[EXCEPTION] ${err.name}: ${err.message}`);
  });

  page.on('framedetached', frame => {
    console.log(`\n>>> FRAME DETACHED AT THIS MOMENT <<<\n`);
    console.log('CONSOLE OUTPUT LEADING UP TO CRASH:');
    console.log('─'.repeat(60));
    // Print last 20 lines
    const relevant = consoleLines.slice(-20);
    relevant.forEach((line, i) => {
      console.log(`${relevant.length - i - 1} lines ago: ${line}`);
    });
  });

  try {
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`Loading: ${url}\n`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });

    // Wait through the crash
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 1000));
    }

  } catch (e) {
    // Ignore navigation errors from detached frames
  }

  await browser.close();

  console.log('\n--- ALL CONSOLE OUTPUT ---');
  console.log(consoleLines.join('\n'));
}

capture().catch(console.error);
