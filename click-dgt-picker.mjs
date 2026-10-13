import puppeteer from 'puppeteer';

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function clickDGTPicker() {
  // Connect to existing browser instance
  const browserWSEndpoint = 'ws://localhost:9222/devtools/browser/...';
  
  // Actually, let's just create fresh browser and run through the flow
  const browser = await puppeteer.launch({
    headless: false,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--remote-debugging-port=9222'],
    defaultViewport: { width: 1400, height: 900 }
  });

  const page = await browser.newPage();
  const allConsoleMessages = [];
  const allErrors = [];

  page.on('console', msg => {
    allConsoleMessages.push({ type: msg.type(), text: msg.text() });
    console.log(`[${msg.type().toUpperCase()}] ${msg.text()}`);
  });

  page.on('pageerror', err => {
    console.log(`\n⚠️  UNCAUGHT EXCEPTION: ${err.message}`);
    console.log(err.stack);
    allErrors.push(err);
  });

  try {
    console.log('1. Loading home page...');
    await page.goto('https://cwo.freeddns.org/HB/', { waitUntil: 'networkidle2', timeout: 60000 });
    await wait(3000);

    console.log('\n2. Finding and clicking Alternative Faction Picker button...');
    const found = await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent.includes('Alternative') || btn.textContent.includes('Picker')) {
          console.log('Found button:', btn.textContent);
          btn.click();
          return true;
        }
      }
      return false;
    });

    if (!found) {
      console.log('Could not find picker button via evaluate, trying via locate...');
    } else {
      console.log('✓ Clicked picker button');
    }

    await wait(3000);

    console.log('\n3. Searching for DGT faction in picker...');
    const foundDGT = await page.evaluate(() => {
      const elements = document.querySelectorAll('*');
      for (const el of elements) {
        if (el.textContent && el.textContent.includes('DGT')) {
          console.log('Found DGT element:', el.tagName, el.className, el.textContent.substring(0, 50));
          if (el.tagName === 'INPUT' || el.tagName === 'BUTTON' || el.parentElement?.tagName === 'LABEL') {
            el.click();
            return true;
          }
        }
      }
      return false;
    });

    if (foundDGT) {
      console.log('✓ Clicked DGT faction');
    } else {
      console.log('✗ Could not find DGT faction');
    }

    await wait(2000);

    console.log('\n4. Selecting other factions (GC, CC, BG)...');
    for (const f of ['GC', 'CC', 'BG']) {
      await page.evaluate((faction) => {
        const els = document.querySelectorAll('*');
        for (const el of els) {
          if (el.textContent && el.textContent.includes(faction) && el.textContent.length < 50) {
            el.click();
            break;
          }
        }
      }, f);
      await wait(500);
    }

    console.log('\n5. Looking for Continue/Start button...');
    await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent.includes('Continue') || btn.textContent.includes('Start')) {
          console.log('Clicking:', btn.textContent);
          btn.click();
          return;
        }
      }
    });

    await wait(5000);

    console.log('\n✓ Game should be starting. Waiting 15 seconds for full load...');
    await wait(15000);

    console.log('\n=== WAITING COMPLETE ===');
    console.log(`Captured ${allConsoleMessages.length} console messages`);
    allConsoleMessages.forEach(m => {
      if (m.type === 'error') {
        console.log(`  ERROR: ${m.text}`);
      }
    });

  } catch (e) {
    console.error('Script error:', e.message);
    console.error(e.stack);
  }

  await wait(5000);
  await browser.close();

  process.exit(allErrors.length > 0 ? 1 : 0);
}

clickDGTPicker().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
