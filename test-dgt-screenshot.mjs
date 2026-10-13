#!/usr/bin/env node
import puppeteer from 'puppeteer';
import fs from 'fs';

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';
const START_URL = `${SERVER}/${BUILD}/`;

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log(`Taking screenshots of DGT faction startup...\n`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1400, height: 900 }
  });

  const page = await browser.newPage();
  const errors = [];
  const allMessages = [];

  page.on('console', msg => {
    const text = msg.text();
    const type = msg.type();
    allMessages.push({ type, text });
    
    if (type === 'error' && 
        !text.includes('Failed to load resource') && 
        !text.includes('favicon')) {
      console.log(`[${type.toUpperCase()}] ${text}`);
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`[EXCEPTION] ${err.message}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('1. Loading...');
    await page.goto(START_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    
    console.log('2. Waiting for render...');
    await wait(5000);
    
    console.log('3. Taking screenshot 1 (after load)...');
    await page.screenshot({ path: '/tmp/dgt-01-loaded.png' });
    console.log('   Saved to /tmp/dgt-01-loaded.png');

    const html1 = await page.evaluate(() => document.body.innerHTML.substring(0, 500));
    console.log(`   Body HTML preview: ${html1}...\n`);

    console.log('4. Clicking to find faction picker...');
    await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button, div[role="button"]'));
      buttons.forEach((b, i) => console.log(`Button ${i}: "${b.textContent?.substring(0, 50)}"`));
    });

    console.log('5. Waiting more for full render...');
    await wait(4000);

    console.log('6. Taking screenshot 2 (after wait)...');
    await page.screenshot({ path: '/tmp/dgt-02-fullrender.png' });
    console.log('   Saved to /tmp/dgt-02-fullrender.png\n');

    console.log('7. Checking for factionpicker...');
    const hasPickerBtn = await page.evaluate(() => {
      const buttons = Array.from(document.querySelectorAll('button'));
      const btn = buttons.find(b => 
        b.textContent.toLowerCase().includes('faction') ||
        b.textContent.toLowerCase().includes('picker')
      );
      return btn ? btn.textContent : null;
    });

    if (hasPickerBtn) {
      console.log(`   Found: ${hasPickerBtn}`);
      await page.click('button:has-text("picker")').catch(() => {});
      await wait(2000);
      
      console.log('8. Taking screenshot 3 (after picker click)...');
      await page.screenshot({ path: '/tmp/dgt-03-afterpicker.png' });
      console.log('   Saved to /tmp/dgt-03-afterpicker.png');
    } else {
      console.log('   No picker button found\n');
    }

  } catch (e) {
    console.log(`Error: ${e.message}`);
    errors.push(`ERROR: ${e.message}`);
  }

  console.log('\n=== CONSOLE MESSAGES ===\n');
  allMessages.forEach(msg => {
    if (msg.type !== 'log' || msg.text.length < 200) {
      console.log(`[${msg.type.toUpperCase()}] ${msg.text}`);
    }
  });

  console.log('\n=== ERRORS FOUND ===\n');
  if (errors.length === 0) {
    console.log('✓ No JavaScript errors detected');
  } else {
    console.log(`✗ ${errors.length} error(s):`);
    errors.forEach((err, i) => console.log(`  ${i + 1}. ${err}`));
  }

  await browser.close();
}

testDGT().catch(e => {
  console.error('Fatal:', e);
  process.exit(1);
});
