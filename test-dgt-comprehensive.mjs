import puppeteer from 'puppeteer';

const wait = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function testDGT() {
  console.log('=== COMPREHENSIVE DGT TEST ===\n');

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const page = await browser.newPage();
  const allMessages = [];
  const allErrors = [];
  let consoleErrorCount = 0;

  page.on('console', msg => {
    const text = msg.text();
    allMessages.push({ type: msg.type(), text });
    
    if (msg.type() === 'error') {
      // Filter noise
      if (!text.includes('Failed to load resource') &&
          !text.includes('favicon') &&
          !text.includes('CVDisplayLink') &&
          !text.match(/^chrome-extension:/) &&
          text.trim() !== '') {
        console.log(`❌ CONSOLE ERROR: ${text}`);
        allErrors.push(`CONSOLE ERROR: ${text}`);
        consoleErrorCount++;
      }
    }
  });

  page.on('pageerror', err => {
    console.log(`❌ JAVASCRIPT EXCEPTION: ${err.message}`);
    console.log(`   Stack: ${err.stack}`);
    allErrors.push(`EXCEPTION: ${err.message}`);
  });

  page.on('response', response => {
    if (!response.ok() && response.url().includes('cwo.freeddns.org')) {
      console.log(`⚠️  Bad response: ${response.status()} ${response.url()}`);
    }
  });

  try {
    console.log('1. Loading main page...');
    await page.goto('https://cwo.freeddns.org/HB/', { waitUntil: 'networkidle2', timeout: 60000 });
    await wait(2000);

    console.log('2. Checking for game board / picker...');
    const hasUI = await page.evaluate(() => {
      return !!document.body.innerHTML;
    });

    if (hasUI) {
      console.log('✓ Page loaded with content');
    } else {
      console.log('✗ No content found on page');
      allErrors.push('PAGE HAS NO CONTENT');
    }

    console.log('3. Testing setup URL directly with DGT...');
    const setupURL = 'https://cwo.freeddns.org/HB/?setup=4:GC-DGT-CC-BG';
    console.log(`   URL: ${setupURL}`);
    
    await page.goto(setupURL, { waitUntil: 'networkidle2', timeout: 60000 });
    await wait(3000);

    console.log('4. Checking for game UI...');
    const hasGameUI = await page.evaluate(() => {
      const checks = {
        hasActionDiv: !!document.querySelector('#action'),
        hasGameBoard: !!document.querySelector('.game-board'),
        hasPhaseText: document.body.textContent.includes('Phase'),
        hasSetupText: document.body.textContent.includes('Setup'),
        bodySize: document.body.innerHTML.length
      };
      return checks;
    });

    console.log(`   Action div: ${hasGameUI.hasActionDiv}`);
    console.log(`   Game board: ${hasGameUI.hasGameBoard}`);
    console.log(`   Phase/Setup text: ${hasGameUI.hasPhaseText || hasGameUI.hasSetupText}`);
    console.log(`   Body HTML size: ${hasGameUI.bodySize} bytes`);

    if (!hasGameUI.hasActionDiv && !hasGameUI.hasGameBoard && !hasGameUI.hasPhaseText) {
      allErrors.push('GAME UI DID NOT LOAD');
    } else {
      console.log('✓ Game UI elements detected');
    }

    console.log('5. Waiting for full game initialization...');
    await wait(5000);

    console.log('6. Final check - scanning for DGT references...');
    const hasDGT = await page.evaluate(() => {
      const html = document.body.innerHTML;
      return {
        hasDGTText: html.includes('DGT') || html.includes('Tribulation'),
        hasDGTClass: html.includes('dgt'),
        hasDGTAssets: html.includes('dgt-acolyte') || html.includes('dgt-conquest')
      };
    });

    console.log(`   Has DGT text: ${hasDGT.hasDGTText}`);
    console.log(`   Has .dgt class: ${hasDGT.hasDGTClass}`);
    console.log(`   Has DGT assets: ${hasDGT.hasDGTAssets}`);

  } catch (e) {
    console.error(`ERROR: ${e.message}`);
    allErrors.push(`ERROR: ${e.message}`);
  }

  await browser.close();

  console.log(`\n=== TEST SUMMARY ===`);
  console.log(`Total console messages: ${allMessages.length}`);
  console.log(`Console errors: ${consoleErrorCount}`);
  console.log(`JavaScript exceptions: ${allErrors.filter(e => e.includes('EXCEPTION')).length}`);
  console.log(`Total failures: ${allErrors.length}`);

  if (allErrors.length === 0) {
    console.log('\n✅ DGT FACTION LOADS CLEANLY — NO ERRORS DETECTED');
    process.exit(0);
  } else {
    console.log('\n❌ ERRORS FOUND:');
    allErrors.forEach(e => console.log(`   - ${e}`));
    process.exit(1);
  }
}

testDGT().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
