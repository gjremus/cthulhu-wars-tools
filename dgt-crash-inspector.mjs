#!/usr/bin/env node
/**
 * Use CDP to capture detailed crash information
 */
import puppeteer from 'puppeteer';

async function inspect() {
  console.log('=== DGT CRASH INSPECTOR (via CDP) ===\n');

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const client = await page.target().createCDPSession();

  // Enable all runtime notifications
  await client.send('Runtime.enable');
  await client.send('Console.enable');
  await client.send('Network.enable');

  let exceptionDetails = [];

  // Capture runtime exceptions
  client.on('Runtime.exceptionThrown', event => {
    const exc = event.exceptionDetails;
    console.log('\n>>> RUNTIME EXCEPTION THROWN <<<');
    console.log(`URL: ${exc.url}`);
    console.log(`Line: ${exc.lineNumber}:${exc.columnNumber}`);
    console.log(`Text: ${exc.text}`);
    if (exc.exception && exc.exception.value) {
      console.log(`Value: ${exc.exception.value}`);
    }
    if (exc.exception && exc.exception.description) {
      console.log(`Description: ${exc.exception.description}`);
    }
    exceptionDetails.push(exc);
  });

  client.on('Inspector.targetCrashed', () => {
    console.log('\n>>> TARGET CRASHED <<<');
  });

  page.on('console', msg => {
    if (msg.type() === 'error' || msg.type() === 'warn') {
      console.log(`[${msg.type().toUpperCase()}] ${msg.text()}`);
    }
  });

  try {
    const url = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`Loading: ${url}\n`);

    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
    console.log('DOM loaded, waiting for crash...\n');

    // Wait and monitor
    for (let i = 0; i < 10; i++) {
      await new Promise(r => setTimeout(r, 1000));
      console.log(`[${i + 1}s]`);
    }

  } catch (e) {
    console.log(`Nav error: ${e.message}`);
  }

  await browser.close();

  console.log('\n=== SUMMARY ===');
  console.log(`Exceptions captured: ${exceptionDetails.length}`);
  exceptionDetails.forEach((e, i) => {
    console.log(`\n${i + 1}. Line ${e.lineNumber}:${e.columnNumber} in ${e.url}`);
    console.log(`   ${e.text}`);
  });
}

inspect().catch(console.error);
