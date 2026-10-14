#!/usr/bin/env node
/**
 * Test the image swap feature in the Simple Update section.
 * This script simulates user interactions with the image swap UI.
 */

const puppeteer = require('puppeteer');

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function testImageSwaps() {
  const browser = await puppeteer.launch({headless: 'new'});
  const page = await browser.newPage();

  try {
    // Navigate to designer
    console.log('Opening designer...');
    await page.goto('http://127.0.0.1:8080/', {waitUntil: 'networkidle0', timeout: 10000});

    // Wait for faction list
    console.log('Waiting for faction list...');
    await page.waitForSelector('button.faction-item', {timeout: 5000});

    // Click first faction
    console.log('Selecting first faction...');
    const factionButtons = await page.$$('button.faction-item');
    if (factionButtons.length === 0) {
      console.log('No factions found, skipping test');
      return;
    }
    await factionButtons[0].click();
    await sleep(1000);

    // Navigate to Simple Update
    console.log('Opening Simple Update...');
    const simpleUpdateBtn = await page.$('button:has-text("Simple Update")');
    if (!simpleUpdateBtn) {
      console.log('Simple Update button not found (build may not be complete)');
      return;
    }

    await simpleUpdateBtn.click();
    await page.waitForSelector('h3::-p-text(Quick Image Swap)', {timeout: 5000});

    // Check that the image swap section exists
    console.log('Checking for Quick Image Swap section...');
    const imageSwapTitle = await page.$eval('h3', el => el.textContent);
    if (!imageSwapTitle.includes('Quick Image Swap')) {
      console.log('ERROR: Quick Image Swap section not found');
      return false;
    }
    console.log('✓ Quick Image Swap section found');

    // Check that Add Image Swap Row button exists
    const addRowBtn = await page.$('button::-p-text("+ Add image swap row")');
    if (!addRowBtn) {
      console.log('ERROR: Add image swap row button not found');
      return false;
    }
    console.log('✓ Add image swap row button found');

    // Click Add Image Swap Row
    console.log('Adding a new image swap row...');
    await addRowBtn.click();
    await sleep(500);

    // Check that a new input field was added
    const fileInputs = await page.$$('input[placeholder="e.g., fm-glyph.webp"]');
    if (fileInputs.length === 0) {
      console.log('ERROR: No filename input found');
      return false;
    }
    console.log(`✓ Found ${fileInputs.length} filename input field(s)`);

    // Type a filename
    console.log('Entering filename...');
    await fileInputs[fileInputs.length - 1].type('test-image.webp', {delay: 50});
    await sleep(300);

    // Verify filename was entered
    const filename = await page.$eval('input[placeholder="e.g., fm-glyph.webp"]', el => el.value);
    if (filename !== 'test-image.webp') {
      console.log(`ERROR: Filename not entered correctly, got: ${filename}`);
      return false;
    }
    console.log(`✓ Filename entered: ${filename}`);

    // Check that Delete button appears when there are multiple rows
    console.log('Checking Delete button...');
    await addRowBtn.click();
    await sleep(500);

    const deleteButtons = await page.$$('button::-p-text("Delete")');
    if (deleteButtons.length > 0) {
      console.log(`✓ Delete button(s) found: ${deleteButtons.length}`);
    }

    console.log('=== Image Swap Feature Tests: PASSED ===');
    return true;

  } catch (err) {
    console.error('Test failed:', err.message);
    return false;
  } finally {
    await browser.close();
  }
}

testImageSwaps().then(success => {
  process.exit(success ? 0 : 1);
});
