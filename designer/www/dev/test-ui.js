// Test script for Faction Designer UI
// Run with: node test-ui.js
// Requires the mock server to be running on localhost:8091

const puppeteer = require('puppeteer');
const fs = require('fs').promises;
const path = require('path');

const BASE_URL = 'http://127.0.0.1:8091/designer/';
const SHOT_DIR = '/tmp/designer-shots';

async function ensureDir(dir) {
  try {
    await fs.mkdir(dir, { recursive: true });
  } catch (err) {
    // Ignore
  }
}

async function screenshot(page, name, width) {
  await page.setViewport({ width, height: 1000 });
  await page.screenshot({
    path: path.join(SHOT_DIR, `${name}-${width}px.png`),
    fullPage: true
  });
  console.log(`Screenshot: ${name} at ${width}px`);
}

async function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function test() {
  console.log('Starting UI test...');
  await ensureDir(SHOT_DIR);

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  try {
    const page = await browser.newPage();

    // Log console messages
    page.on('console', msg => {
      const type = msg.type();
      if (type === 'error' || type === 'warning') {
        console.log(`[Browser ${type}]`, msg.text());
      }
    });

    // Log page errors
    page.on('pageerror', err => {
      console.error('[Page Error]', err.message);
    });

    // 1. Login screen
    console.log('Testing login screen...');
    await page.goto(BASE_URL, { waitUntil: 'networkidle2' });
    await delay(500);
    await screenshot(page, '01-login', 1280);
    await screenshot(page, '01-login', 390);

    // 2. Register screen
    console.log('Testing register screen...');
    await page.click('button.link-button');
    await delay(500);
    await screenshot(page, '02-register', 1280);
    await screenshot(page, '02-register', 390);

    // Fill and submit registration
    await page.type('#username', 'testuser');
    await page.type('#password', 'testpass');
    await delay(200);
    await screenshot(page, '02b-register-filled', 1280);
    await page.click('button.primary');
    await delay(1000);

    // 3. Faction list (empty)
    console.log('Testing faction list...');
    await screenshot(page, '03-faction-list-empty', 1280);
    await screenshot(page, '03-faction-list-empty', 390);

    // 4. Create faction dialog
    console.log('Testing create faction dialog...');
    await page.click('button.primary');
    await delay(500);
    await screenshot(page, '04-create-dialog', 1280);
    await screenshot(page, '04-create-dialog', 390);

    // Fill form
    const nameInput = await page.$('input[type="text"]');
    await nameInput.type('The Deep Ones');
    const acrInputs = await page.$$('input[type="text"]');
    await acrInputs[1].type('TDO');
    await delay(200);
    await screenshot(page, '04b-create-filled', 1280);

    // Create faction
    const createBtn = await page.$('.confirm-dialog button.primary');
    await createBtn.click();
    await delay(1000);

    // 5. Main design page
    console.log('Testing main design page...');
    await screenshot(page, '05-main-design', 1280);
    await screenshot(page, '05-main-design', 390);

    // Scroll to see all buttons
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await delay(200);
    await screenshot(page, '05b-main-design-bottom', 1280);

    // 6. Test a section screen (UFA)
    console.log('Testing section screen...');
    const buttons = await page.$$('button.section-button');
    // Find UFA button (second one)
    await buttons[1].click();
    await delay(1000);
    await screenshot(page, '06-section-ufa', 1280);
    await screenshot(page, '06-section-ufa', 390);

    // Back to main
    await page.click('button');
    await delay(1000);

    // 7. Versions screen
    console.log('Testing versions screen...');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await delay(200);
    const allButtons = await page.$$('button.section-button');
    // Versions should be near the end
    await allButtons[allButtons.length - 1].click();
    await delay(1000);
    await screenshot(page, '07-versions', 1280);
    await screenshot(page, '07-versions', 390);

    // Back to main
    await page.click('button');
    await delay(1000);

    // 8. Build screen
    console.log('Testing build screen...');
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await delay(200);
    const buttons2 = await page.$$('button.section-button');
    // Build should be before Versions
    await buttons2[buttons2.length - 4].click();
    await delay(1000);
    await screenshot(page, '08-build', 1280);
    await screenshot(page, '08-build', 390);

    console.log('Test complete!');
    console.log(`Screenshots saved to: ${SHOT_DIR}`);

  } catch (err) {
    console.error('Test error:', err);
  } finally {
    await browser.close();
  }
}

test().catch(console.error);
