#!/usr/bin/env node
import puppeteer from 'puppeteer';
import { execSync } from 'child_process';
import { writeFileSync } from 'fs';

const SERVER = 'https://cwo.freeddns.org';
const SSH_KEY = '/Users/gremus/Library/CloudStorage/GoogleDrive-gremus@salesforce.com/My Drive/Personal/Games/Cthulhu Wars/Maps/Library at Celaeno/Server Deployment/oracle_cw_ed25519';
const SSH_HOST = 'oracle-cw-server@35.255.125.91';
const RESULTS_FILE = '/tmp/cwo-game-check-results.json';
const LOAD_TIMEOUT = 30000;

function sshRaw(cmd) {
  return execSync(cmd, { encoding: 'utf8' }).trim();
}

function getActiveGames() {
  const todayMs = Math.floor(new Date().setHours(0,0,0,0));
  const script = `
THRESHOLD=${todayMs}
DBDIR=/opt/cwo/data
GAME_IDS=$(
  { grep 'INSERT INTO "Meta"' $DBDIR/cwo.script
    grep 'INSERT INTO "Meta"' $DBDIR/cwo.log 2>/dev/null
  } | awk -F'[(),]' -v t=$THRESHOLD '$3 > t {print $2}' | sort -un
)
for GID in $GAME_IDS; do
  SECRET=$({ grep 'INSERT INTO "Roles"' $DBDIR/cwo.script
             grep 'INSERT INTO "Roles"' $DBDIR/cwo.log 2>/dev/null
           } | grep "($GID," | head -1 | sed "s/.*,'\\([^']*\\)'.*/\\1/")
  [ -n "$SECRET" ] && echo "$GID $SECRET"
done
`;
  const sshCmd = `ssh -i "${SSH_KEY}" -o StrictHostKeyChecking=no ${SSH_HOST} bash -s`;
  const output = execSync(sshCmd, { input: script, encoding: 'utf8' }).trim();
  if (!output) return [];
  return output.split('\n').map(line => {
    const [gameId, secret] = line.trim().split(' ');
    return { gameId, secret };
  }).filter(g => g.secret);
}

async function checkGame(browser, gameId, secret) {
  const url = `${SERVER}/play/${secret}`;
  const page = await browser.newPage();
  const errors = [];

  page.on('console', msg => {
    if (msg.type() === 'error') {
      const text = msg.text();
      if (!text.includes('Failed to load resource') && !text.includes('favicon'))
        errors.push(text);
    }
  });
  page.on('pageerror', err => errors.push(err.message));

  try {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: LOAD_TIMEOUT });
    await new Promise(r => setTimeout(r, 8000));
  } catch (e) {
    errors.push(`LOAD_ERROR: ${e.message}`);
  }

  await page.close();
  return { gameId, secret, url, errors, hasErrors: errors.length > 0 };
}

async function main() {
  console.log('Fetching active games from server...');
  const games = getActiveGames();
  console.log(`Found ${games.length} games active today.`);

  if (games.length === 0) {
    writeFileSync(RESULTS_FILE, JSON.stringify({ timestamp: Date.now(), games: [], errors: [] }, null, 2));
    console.log('No active games. Done.');
    return;
  }

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const results = [];
  for (const { gameId, secret } of games) {
    console.log(`Checking game ${gameId}...`);
    const result = await checkGame(browser, gameId, secret);
    results.push(result);
    if (result.hasErrors) {
      console.log(`  ERRORS in game ${gameId}: ${result.errors.length} error(s)`);
    } else {
      console.log(`  OK`);
    }
  }

  await browser.close();

  const errored = results.filter(r => r.hasErrors);
  const output = {
    timestamp: Date.now(),
    totalChecked: results.length,
    erroredCount: errored.length,
    errored,
    clean: results.filter(r => !r.hasErrors).map(r => ({ gameId: r.gameId }))
  };

  writeFileSync(RESULTS_FILE, JSON.stringify(output, null, 2));
  console.log(`\nDone. ${errored.length} game(s) with errors. Results at ${RESULTS_FILE}`);
}

main().catch(e => { console.error(e); process.exit(1); });
