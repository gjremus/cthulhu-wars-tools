// Checks whether game 454 ("Existence and Colour") has ended.
// Exit code 0 = game is OVER (winner declared). Exit code 1 = not over / unknown.
// Fail-safe: any error or ambiguity exits 1 (do NOT restore), because leaving the
// Agony Sting revert in place is harmless (454 is the only Mother Hydra game).
const puppeteer = require('/Users/gremus/cthulhu-wars-tools/node_modules/puppeteer');
const GAME_URL = 'https://cwo.freeddns.org/mnu/play/wpqfabmaynleeyzb';
(async () => {
  let over = false;
  try {
    const b = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox'] });
    const p = await b.newPage();
    await p.goto(GAME_URL, { waitUntil: 'networkidle2', timeout: 90000 });
    for (let i = 0; i < 40; i++) {
      const l = await p.evaluate(() => document.body.innerText.length);
      if (l > 3000) break;
      await new Promise(r => setTimeout(r, 3000));
    }
    await new Promise(r => setTimeout(r, 4000));
    over = await p.evaluate(() => {
      const t = document.body.innerText;
      // Strict: only the GameOverAction question text ("Winner is X" / "Winners are ...")
      // or the explicit Humanity-victory string.
      return /Winner is |Winners are |Winner is Humanity/.test(t);
    });
    await b.close();
  } catch (e) {
    process.stderr.write('check error (treating as NOT over): ' + e.message + '\n');
    process.exit(1);
  }
  if (over) { console.log('GAME_OVER'); process.exit(0); }
  console.log('GAME_ACTIVE'); process.exit(1);
})();
