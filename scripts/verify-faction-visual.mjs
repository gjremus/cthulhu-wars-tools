#!/usr/bin/env node
/**
 * VISUAL VERIFICATION of a faction in a REAL game (not the menu, not the designer).
 *
 * Usage (run from ~/Claude-Projects/cthulhu-wars-tools - puppeteer lives there):
 *   node scripts/verify-faction-visual.mjs <ACR> [BUILD=HB]
 *   node scripts/verify-faction-visual.mjs FM
 *
 * What it does:
 *   1. Opens https://cwo.freeddns.org/<BUILD>/ and clicks through the real menus:
 *      Local Game -> 4 Players -> Alternate faction selection -> reserve <ACR> for
 *      Player 1 -> Generate -> Continue -> Start game.
 *      (The old "?setup=4:GC-<ACR>-CC-BG" link only shows the MAIN MENU - a check
 *       run there proves nothing about the faction.)
 *   2. Screenshots: board.png, panel.png (the faction's side panel with its 6
 *      spellbook-requirement rows), card.png (faction card), phone.png,
 *      sbr-1..6.png (each requirement popup), sb-<n>.png (each spellbook name on the
 *      card, clicked).
 *   3. Prints: faction images loaded/broken, faction colors, SB requirement row count,
 *      JavaScript errors, failed downloads.
 *
 * YOU MUST STILL OPEN EVERY SCREENSHOT WITH THE Read TOOL AND LOOK AT IT.
 * This script collects evidence; it does not decide that things look right.
 *
 * Exit code: 1 if JS errors, broken faction images, 404s for faction files, the game
 * did not start, or the faction card did not open. 0 otherwise.
 *
 * NOTE: no executablePath on purpose - the system Google Chrome drops the connection
 * with puppeteer 25 ("Session closed"). The bundled Chrome works.
 */
import puppeteer from 'puppeteer';
import fs from 'fs';

const ACR = (process.argv[2] || '').toUpperCase();
const BUILD = process.argv[3] || 'HB';
if (!ACR) { console.error('Usage: node scripts/verify-faction-visual.mjs <ACR> [HB]'); process.exit(2); }
const acr = ACR.toLowerCase();
const OUT = `/tmp/verify-${acr}-${new Date().toISOString().slice(0, 10)}`;
fs.mkdirSync(OUT, { recursive: true });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const problems = [];

const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--disable-setuid-sandbox'],
  defaultViewport: { width: 1400, height: 1000 }
});
const page = await browser.newPage();

// Error capture FIRST, before the page loads.
const errors = [], failed = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push('PAGEERROR: ' + e.message));
page.on('requestfailed', r => failed.push(r.url() + ' ' + (r.failure()?.errorText || '')));
page.on('response', r => { if (r.status() >= 400) failed.push(r.status() + ' ' + r.url()); });

// Click the first leaf element whose text equals t (or starts with t.slice(1) if t starts with ^).
const clickText = t => page.evaluate(t => {
  const m = e => t.startsWith('^') ? e.textContent.trim().startsWith(t.slice(1)) : e.textContent.trim() === t;
  const el = [...document.querySelectorAll('*')].find(e => e.children.length === 0 && m(e));
  if (!el) return false; el.click(); return true;
}, t);
const shot = async name => { await page.screenshot({ path: `${OUT}/${name}` }); console.log('  screenshot', `${OUT}/${name}`); };

try {
  // ---- 1. Get into a real game with this faction --------------------------------
  // domcontentloaded, not networkidle2: the site does not always go network-quiet.
  await page.goto(`https://cwo.freeddns.org/${BUILD}/`, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await sleep(5000);
  for (const c of ['Local Game', '4 Players', 'Alternate faction selection']) {
    if (!await clickText(c)) throw new Error(`menu button "${c}" not found`);
    await sleep(2500);
  }
  // Make sure every Stability filter (Stable / Tested-Beta / Untested-Alpha) is
  // checked - some homebrew factions (e.g. CS, FBE) are tagged Tested/Beta or
  // Untested/Alpha and are hidden from the picker if that box is unchecked.
  await page.evaluate(() => {
    const stabilityRow = [...document.querySelectorAll('div')].find(d => d.textContent.trim().startsWith('Stability:') && d.querySelector('input[type=checkbox]'));
    if (stabilityRow) stabilityRow.querySelectorAll('input[type=checkbox]').forEach(cb => { if (!cb.checked) cb.click(); });
  });
  await sleep(500);
  // Reserve the faction for Player 1: untick that row's "All", wait for the redraw,
  // THEN tick the faction (the row is re-drawn, so find the checkbox again).
  const found = await page.evaluate(acr => {
    const lab = [...document.querySelectorAll('label')].find(l => l.querySelector(`img[src$="/${acr}-glyph.webp"]`));
    if (!lab) return false;
    const all = [...lab.parentElement.querySelectorAll('label')].find(l => l.textContent.trim() === 'All')?.querySelector('input');
    if (all && all.checked) all.click();
    return true;
  }, acr);
  if (!found) throw new Error(`${acr}-glyph.webp not in the alternate picker - faction missing from picker (or hidden by the Stability filter)`);
  await sleep(1000);
  await page.evaluate(acr => {
    const lab = [...document.querySelectorAll('label')].find(l => l.querySelector(`img[src$="/${acr}-glyph.webp"]`));
    const cb = lab.querySelector('input'); if (!cb.checked) cb.click();
  }, acr);
  await sleep(1000);
  // Restrict the other 3 (randomly-rolled) players to the 4 base factions
  // (GC/CC/BG/YS). Those never have an extra "starts in" / "Choose Tribe"
  // setup prompt, so this keeps the random co-players from blocking
  // Continue/Start game with an unpredictable number of custom-setup dialogs
  // (homebrew/designer factions almost all have one). We only care about
  // screenshotting the RESERVED faction's own card, so the other 3 players'
  // factions don't matter.
  // Each click can trigger a redraw that replaces the DOM nodes, so re-query
  // fresh from scratch on every single click rather than reusing one captured
  // NodeList across multiple clicks (stale element refs silently no-op).
  for (let idx = 1; idx <= 3; idx++) {
    await page.evaluate(idx => {
      const allLabels = [...document.querySelectorAll('label')].filter(l => l.textContent.trim() === 'All');
      const cb = allLabels[idx]?.querySelector('input');
      if (cb && cb.checked) cb.click();
    }, idx);
    await sleep(500);
  }
  for (let idx = 1; idx <= 3; idx++) {
    for (const b of ['gc', 'cc', 'bg', 'ys']) {
      await page.evaluate((idx, b) => {
        const allLabels = [...document.querySelectorAll('label')].filter(l => l.textContent.trim() === 'All');
        const row = allLabels[idx]?.parentElement;
        const lab = row && [...row.querySelectorAll('label')].find(l => l.querySelector(`img[src$="/${b}-glyph.webp"]`));
        const cb = lab?.querySelector('input');
        if (cb && !cb.checked) cb.click();
      }, idx, b);
      await sleep(300);
    }
  }
  await shot('picker.png');
  // Some randomly-rolled co-players (e.g. TT needs "Choose Tribe", XSS/others
  // need a "<Faction> starts in" region pick) block Continue/Start game until
  // resolved. Since we only care about the reserved faction, just take the
  // first offered option (never "Cancel") for whichever player is blocking.
  const resolveBlockingPrompt = async () => {
    // These prompts render as <div id=action><div>(heading, mixed text+span
    // nodes, e.g. per-letter-colored faction name)</div><div class=option>...
    // </div>...</div> - match on the whole heading div's text (not a single
    // leaf node - the faction name is its own colored <span> inside it) and
    // click via real mouse coordinates (not a synthetic DOM .click()) since
    // these widgets are built on pointer events.
    const box = await page.evaluate(acr => {
      const action = document.getElementById('action');
      if (!action || !action.children.length) return null;
      const headingText = action.children[0].textContent.trim();
      if (!(headingText === 'Choose Tribe' || headingText === 'Order of play' || /starts in$/.test(headingText))) return null;
      const opts = [...action.querySelectorAll('.option')].filter(o => !['Cancel', 'Commands'].includes(o.textContent.trim()));
      if (!opts.length) return null;
      // "Order of play" offers 2+ full turn-order permutations - prefer
      // whichever one puts our RESERVED faction first, so it becomes the
      // active player (only the active player's name/card reliably opens).
      let opt = opts[0];
      if (headingText === 'Order of play') {
        opt = opts.find(o => o.querySelector(`span.${acr}`) === o.querySelectorAll('span[class]')[0]) || opts[0];
      }
      const r = opt.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2, text: opt.textContent.trim() };
    }, acr);
    if (!box) return false;
    console.log(`  resolving blocking prompt: clicking "${box.text}"`);
    await page.mouse.click(box.x, box.y);
    return true;
  };
  for (const c of ['Generate', 'Continue', 'Start game']) {
    if (!await clickText(c)) throw new Error(`setup button "${c}" not found`);
    await sleep(4000);
    // Several random co-players in a row can each have their own custom-setup
    // prompt (region pick, tribe pick, etc.) - keep resolving until none left.
    for (let i = 0; i < 25; i++) {
      if (!await resolveBlockingPrompt()) break;
      await sleep(1200);
    }
  }
  const inGame = await page.evaluate(acr => !!document.querySelector(`.name span.${acr}, span.${acr}`), acr);
  if (!inGame) throw new Error('game did not start (faction name not on screen)');
  // The RESERVED faction itself can also have its own post-start "<Faction>
  // starts in" placement prompt (e.g. CS) that sits on top of the board and
  // blocks opening the faction card until resolved.
  for (let i = 0; i < 10; i++) {
    if (!await resolveBlockingPrompt()) break;
    await sleep(1200);
  }
  // Dismiss any leftover non-blocking informational overlay (e.g. "Order of
  // play") that can still be covering the board and intercepting clicks.
  await page.keyboard.press('Escape');
  await sleep(1000);
  await shot('board.png');

  // ---- 2. Faction panel: glyph + 6 spellbook requirement rows --------------------
  const panel = await page.evaluate(acr => {
    const nameSpan = [...document.querySelectorAll(`span.${acr}`)].find(s => s.parentElement.classList.contains('name'));
    if (!nameSpan) return null;
    // climb to the panel that holds the .spellbook rows
    let p = nameSpan; while (p && !p.querySelector('.spellbook')) p = p.parentElement;
    if (!p) return { rows: 0 };
    p.setAttribute('data-verify-panel', '1');
    return { rows: p.querySelectorAll('.spellbook').length,
             texts: [...p.querySelectorAll('.spellbook')].map(d => d.textContent.trim()) };
  }, acr);
  console.log('\nFaction panel SB requirement rows:', panel ? panel.rows : 'panel not found', panel?.texts || '');
  if (!panel || panel.rows !== 6) problems.push(`V5: expected 6 spellbook requirement rows, found ${panel ? panel.rows : 'no panel'}`);
  const panelEl = await page.$('[data-verify-panel="1"]');
  if (panelEl) { await panelEl.screenshot({ path: `${OUT}/panel.png` }); console.log('  screenshot', `${OUT}/panel.png`); }

  // Each requirement row popup
  const nRows = panel?.rows || 0;
  for (let i = 0; i < nRows; i++) {
    // the panel is re-drawn after every click, so find it again each time
    await page.evaluate((acr, i) => {
      let p = [...document.querySelectorAll(`span.${acr}`)].find(s => s.parentElement.classList.contains('name'));
      while (p && !p.querySelector('.spellbook')) p = p.parentElement;
      p?.querySelectorAll('.spellbook')[i]?.click();
    }, acr, i);
    await sleep(1500);
    await shot(`sbr-${i + 1}.png`);
    await page.keyboard.press('Escape'); await sleep(600);
  }

  // ---- 3. Faction card -----------------------------------------------------------
  // Same selector the panel step above just used successfully (synthetic
  // .click(), not a real mouse click - a real click at these coordinates can
  // land on a different overlapping element and get swallowed).
  const clicked = await page.evaluate(acr => {
    const s = [...document.querySelectorAll(`span.${acr}`)].find(s => s.parentElement.classList.contains('name'));
    if (!s) return false;
    s.click();
    return true;
  }, acr);
  console.log('  faction name span clicked:', clicked);
  await sleep(2500);
  let card = await page.$('.faction-table');
  if (!card && clicked) {
    // retry once more in case the first click only dismissed a leftover overlay
    await page.evaluate(acr => [...document.querySelectorAll(`span.${acr}`)].find(s => s.parentElement.classList.contains('name'))?.click(), acr);
    await sleep(2500);
    card = await page.$('.faction-table');
  }
  if (!card) {
    // Fallback (e.g. CS): real mouse click on whatever span.<acr> is visible,
    // in case the synthetic click truly found nothing at all.
    const nameBox = await page.evaluate(acr => {
      const inLog = el => !!el.closest('#log');
      const s = [...document.querySelectorAll(`span.${acr}`)].find(s => s.getBoundingClientRect().width > 0 && !inLog(s));
      if (!s) return null;
      const r = s.getBoundingClientRect();
      return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    }, acr);
    console.log('  fallback: faction name span (any) found at:', nameBox);
    if (nameBox) {
      await page.mouse.click(nameBox.x, nameBox.y);
      await sleep(2500);
      card = await page.$('.faction-table');
    }
  }
  if (card) { await card.screenshot({ path: `${OUT}/card.png` }); console.log('  screenshot', `${OUT}/card.png`); await shot('card-full.png'); }
  else problems.push('V4: faction card (.faction-table) did not open');

  // Card colors and text (V1/V2/V12)
  const cardInfo = await page.evaluate(() => {
    const t = document.querySelector('.faction-table'); if (!t) return null;
    const txt = t.innerText;
    const bad = ['undefined', 'NaN', 'Values.', 'null'].filter(w => txt.includes(w));
    const els = [...t.querySelectorAll('*')].filter(e => e.children.length === 0 && e.textContent.trim()).slice(0, 25);
    return { bad, sample: els.map(e => { const s = getComputedStyle(e);
      return `${e.textContent.trim().slice(0, 28).padEnd(28)} color=${s.color} font=${s.fontFamily.split(',')[0]} ${s.fontSize}`; }) };
  });
  if (cardInfo) {
    console.log('\nCard text colors (compare with designer meta.color):'); cardInfo.sample.forEach(l => console.log('  ' + l));
    if (cardInfo.bad.length) problems.push('V12: card text contains ' + cardInfo.bad.join(', '));
  }
  const factionColor = await page.evaluate(acr => { const s = document.querySelector(`span.${acr}`); return s ? getComputedStyle(s).color : null; }, acr);
  console.log(`Faction name color (span.${acr}):`, factionColor);

  // Spellbook names on the card: click each and screenshot the popup (V6)
  // Spellbook names = the text after "Spellbook:" / "Spellbooks:" in the card notes.
  const sbNames = await page.evaluate(() => {
    const t = document.querySelector('.faction-table'); if (!t) return [];
    const names = [];
    for (const m of t.innerText.matchAll(/Spellbooks?:\s*([^\n.]+)/g))
      m[1].split(',').map(x => x.trim()).filter(Boolean).forEach(n => names.push(n));
    return [...new Set(names)];
  });
  console.log('\nSpellbook names found on card:', sbNames.length, sbNames);
  for (const [i, n] of sbNames.entries()) {
    const ok = await clickText(n); await sleep(1500);
    if (ok) await shot(`sb-${i + 1}.png`); else console.log(`  could not click "${n}"`);
    await page.keyboard.press('Escape'); await sleep(600);
    await page.evaluate(acr => [...document.querySelectorAll(`span.${acr}`)].find(s => s.parentElement.classList.contains('name'))?.click(), acr);
    await sleep(1500);
  }

  // ---- 4. Faction images (V3/V9/V10) --------------------------------------------
  const imgs = await page.evaluate(acr => [...document.images]
    .filter(i => i.src.toLowerCase().split('/').pop().startsWith(acr + '-'))
    .map(i => ({ file: i.src.split('/').pop(), ok: i.complete && i.naturalWidth > 0, size: `${i.naturalWidth}x${i.naturalHeight}` })), acr);
  const bgs = await page.evaluate(acr => [...new Set([...document.querySelectorAll('*')].map(e => getComputedStyle(e).backgroundImage)
    .filter(b => b && b !== 'none' && b.toLowerCase().includes('/' + acr + '-')))], acr);
  // the same unit icon appears once per map spot - group them
  const byFile = {}; for (const i of imgs) { const k = `${i.ok ? 'OK    ' : 'BROKEN'} ${i.file} ${i.size}`; byFile[k] = (byFile[k] || 0) + 1; }
  console.log('\nFaction <img> files:'); Object.entries(byFile).forEach(([k, n]) => console.log(`  ${k}${n > 1 ? `  (x${n})` : ''}`));
  if (bgs.length) console.log('Faction background images:', bgs);
  const broken = imgs.filter(i => !i.ok);
  if (broken.length) problems.push(`V3/V9: ${broken.length} broken faction image(s): ` + broken.map(b => b.file).join(', '));
  if (!imgs.length && !bgs.length) problems.push(`V3/V9: no ${acr}-* images found on screen at all`);

  // ---- 5. Phone size (V12) ------------------------------------------------------
  await page.setViewport({ width: 390, height: 844 }); await sleep(1500);
  await shot('phone.png');
} catch (e) {
  problems.push('SCRIPT: ' + e.message);
  try { await shot('error.png'); } catch {}
}

// ---- 6. Errors (V15) --------------------------------------------------------------
console.log('\n=== JAVASCRIPT ERRORS ===');
console.log(errors.length ? errors.join('\n') : '(none)');
console.log('=== FAILED REQUESTS ===');
console.log(failed.length ? failed.join('\n') : '(none)');
if (errors.length) problems.push(`V15: ${errors.length} JavaScript error(s)`);
const facFails = failed.filter(f => f.toLowerCase().includes('/' + acr + '-'));
if (facFails.length) problems.push(`V15: ${facFails.length} failed download(s) of ${acr}- files`);

console.log('\n=== AUTOMATIC PROBLEMS FOUND ===');
console.log(problems.length ? problems.map(p => '  - ' + p).join('\n') : '  (none - now READ every screenshot below; the script cannot judge looks)');
console.log('\nEvidence folder:', OUT);
console.log(fs.readdirSync(OUT).map(f => '  ' + f).join('\n'));
await browser.close();
process.exit(problems.length ? 1 : 0);
