#!/usr/bin/env node
import puppeteer from 'puppeteer';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const SETUP = `4:GC-DGT-CC-BG`;
const URL = `${SERVER}/${BUILD}/?setup=${SETUP}`;

async function check() {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const errors = [];

  page.on('console', msg => {
    const text = msg.text();
    console.log(`[${msg.type()}] ${text}`);
    if (msg.type() === 'error' && !text.includes('Failed') && !text.includes('favicon')) {
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`[PAGE ERROR] ${err.message}`);
    errors.push(err.message);
  });

  page.on('requestfailed', req => {
    console.log(`[REQUEST FAILED] ${req.url()}`);
  });

  try {
    console.log(`\nLoading: ${URL}\n`);
    await page.goto(URL, { waitUntil: 'networkidle2', timeout: 45000 });

    console.log('\n--- Waiting 8 seconds for game to fully load ---\n');
    await new Promise(r => setTimeout(r, 8000));

    const html = await page.evaluate(() => {
      return {
        title: document.title,
        hasOverlay: document.querySelector('#overlay') !== null,
        bodyLength: document.body.innerHTML.length,
        scriptCount: document.querySelectorAll('script').length,
        imgCount: document.querySelectorAll('img').length,
        errorInConsole: window.__errors && window.__errors.length > 0
      };
    });

    console.log('\n--- Page State ---');
    console.log(html);

  } catch (e) {
    console.error('Error:', e.message);
    errors.push(e.message);
  }

  await browser.close();

  console.log('\n=== SUMMARY ===');
  console.log(`Total errors: ${errors.length}`);
  if (errors.length > 0) {
    console.log('Errors:');
    errors.forEach(e => console.log(`  - ${e}`));
  }
}

check().catch(console.error);
