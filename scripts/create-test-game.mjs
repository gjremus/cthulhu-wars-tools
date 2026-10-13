#!/usr/bin/env node
/**
 * Create an actual online game with a faction and test it
 * Usage: ./create-test-game.mjs FM
 */
import puppeteer from 'puppeteer';
import https from 'https';

const FACTION = process.argv[2];
if (!FACTION) {
  console.error('Usage: ./create-test-game.mjs <FACTION_ACRONYM>');
  console.error('Example: ./create-test-game.mjs FM');
  process.exit(1);
}

const SERVER = 'https://cwo.freeddns.org';
const BUILD = 'HB';

function httpsPost(url, body) {
  return new Promise((resolve, reject) => {
    const urlObj = new URL(url);
    const options = {
      hostname: urlObj.hostname,
      path: urlObj.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'text/plain',
        'Content-Length': Buffer.byteLength(body)
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(data));
    });

    req.on('error', reject);
    req.write(body);
    req.end();
  });
}

function httpsGet(url) {
  return new Promise((resolve, reject) => {
    https.get(url, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

async function createAndTestGame() {
  console.log(`Creating online game with faction ${FACTION}...`);

  // Create game with 4 factions: GC, FACTION, CC, BG
  const factions = ['GC', FACTION, 'CC', 'BG'];
  const version = 'Homebrew v 2.250';
  const gameName = `Test ${FACTION} ${Date.now()}`;

  // Format: "GC:Normal/FM:Normal/CC:Normal/BG:Normal "
  const setupString = factions.map(f => `${f}:Normal`).join('/') + ' ';

  // Roles: space-separated faction codes (server generates secrets)
  const roles = factions.join(' ');

  // POST body format (from the code):
  // roles (space-separated)\nversion\nname\nsetupString\nStartAction
  const body = [
    roles,
    version,
    gameName,
    setupString,
    'StartAction'
  ].join('\n');

  console.log(`\nPosting to ${SERVER}/${BUILD}/create`);
  console.log(`Game: ${gameName}`);
  console.log(`Factions: ${factions.join(', ')}`);

  try {
    // Create the game
    const masterSecret = await httpsPost(`${SERVER}/${BUILD}/create`, body);
    console.log(`✓ Game created, master secret: ${masterSecret.substring(0, 20)}...`);

    // Get individual role secrets
    const rolesResponse = await httpsGet(`${SERVER}/${BUILD}/roles/${masterSecret}`);
    console.log(`\nRoles response:\n${rolesResponse}`);
    const roleLines = rolesResponse.trim().split('\n');

    console.log(`\nGenerated ${roleLines.length} role URLs:`);
    roleLines.forEach(line => console.log(`  ${line}`));

    const testSecret = roleLines.find(line => line.startsWith(FACTION))?.split(' ')[1];

    if (!testSecret) {
      console.error(`ERROR: Could not find secret for faction ${FACTION}`);
      process.exit(1);
    }

    const testUrl = `${SERVER}/${BUILD}/play/${testSecret}`;
    console.log(`\nTesting ${FACTION} at: ${testUrl}`);

    // Now test the game with Puppeteer
    const browser = await puppeteer.launch({
      headless: false,  // VISIBLE
      executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
      defaultViewport: { width: 1280, height: 800 }
    });

    const page = await browser.newPage();
    const errors = [];

    // Capture console errors
    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error') {
        if (!text.includes('Failed to load resource') &&
            !text.includes('favicon') &&
            !text.includes('CVDisplayLink')) {
          console.log(`\n⚠️  CONSOLE ERROR: ${text}`);
          errors.push(`CONSOLE ERROR: ${text}`);
        }
      }
    });

    // Capture JavaScript exceptions
    page.on('pageerror', err => {
      console.log(`\n⚠️  JAVASCRIPT EXCEPTION: ${err.message}`);
      console.log(`   Stack: ${err.stack?.split('\n').slice(0, 3).join('\n   ')}`);
      errors.push(`JAVASCRIPT EXCEPTION: ${err.message}`);
    });

    console.log('\nLoading game...');
    await page.goto(testUrl, { waitUntil: 'networkidle2', timeout: 60000 });

    console.log('Waiting for game to initialize (15 seconds)...');
    await new Promise(r => setTimeout(r, 15000));

    console.log('Checking game UI...');
    const hasGameUI = await page.evaluate(() => {
      return document.querySelector('#action') !== null ||
             document.body.textContent.includes('Action Phase') ||
             document.body.textContent.includes('Doom Phase') ||
             document.body.textContent.includes('Power:');
    }).catch(() => false);

    console.log('\n=== TEST RESULTS ===');
    if (errors.length === 0 && hasGameUI) {
      console.log(`✓ ${FACTION}: Game created and loaded successfully with NO errors`);
      console.log(`  Game URL: ${testUrl}`);
      console.log(`\n  Faction ${FACTION} can be marked BUILT`);

      console.log('\nAll role URLs:');
      roleLines.forEach(line => {
        const parts = line.split(' ');
        const faction = parts[0] === '#' ? 'Spectator' : parts[0];
        const url = `${SERVER}/${BUILD}/play/${parts[1]}`;
        console.log(`  ${faction}: ${url}`);
      });

      await new Promise(r => setTimeout(r, 5000));
      await browser.close();
      process.exit(0);
    } else {
      console.log(`✗ ${FACTION}: FAILED`);
      if (!hasGameUI) {
        console.log('  - Game UI did not load');
      }
      if (errors.length > 0) {
        console.log(`  - ${errors.length} JavaScript error(s):`);
        errors.forEach(err => console.log(`    ${err}`));
      }
      console.log(`\n  DO NOT mark faction ${FACTION} as "built" until fixed.`);

      await new Promise(r => setTimeout(r, 10000));
      await browser.close();
      process.exit(1);
    }

  } catch (e) {
    console.error(`\nERROR: ${e.message}`);
    console.error(e.stack);
    process.exit(1);
  }
}

createAndTestGame().catch(e => {
  console.error('Script error:', e);
  process.exit(1);
});
