import puppeteer from 'puppeteer';

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  const browser = await puppeteer.launch({
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: { width: 1400, height: 900 }
  });

  const page = await browser.newPage();
  const errors = [];

  page.on('console', msg => {
    const text = msg.text();
    console.log(`[${msg.type().toUpperCase()}] ${text}`);
    if (msg.type() === 'error' && 
        !text.includes('Failed to load') &&
        !text.includes('favicon') &&
        !text.includes('CVDisplayLink')) {
      errors.push(text);
    }
  });

  page.on('pageerror', err => {
    console.log(`[EXCEPTION] ${err.message}\n${err.stack}`);
    errors.push(`EXCEPTION: ${err.message}`);
  });

  try {
    console.log('Loading https://cwo.freeddns.org/HB/...');
    await page.goto('https://cwo.freeddns.org/HB/', { waitUntil: 'networkidle2', timeout: 60000 });
    await wait(2000);

    console.log('\n✓ Game page loaded. Check Chrome window for UI...');
    console.log('Script will keep running for 90 seconds while you interact with the picker.');
    await wait(90000);

  } catch (e) {
    console.error('Error:', e.message);
    errors.push(e.message);
  }

  await browser.close();

  console.log(`\n\n=== CAPTURED ${errors.length} ERRORS ===`);
  errors.forEach(e => console.log(`  - ${e}`));
  process.exit(errors.length > 0 ? 1 : 0);
}

testDGT().catch(e => {
  console.error('Script error:', e);
  process.exit(1);
});
