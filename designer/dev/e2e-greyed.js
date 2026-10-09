#!/usr/bin/env node
// Test all greyed/disabled dependencies in sections.js
// Run: NODE_PATH=$(npm root -g) node dev/e2e-greyed.js
const puppeteer = require('puppeteer');
const BASE = 'http://127.0.0.1:8095';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const results = [];
const check = (name, ok, extra = '') => { results.push(ok); console.log(ok ? 'PASS' : 'FAIL', name, extra); };

(async () => {
  const browser = await puppeteer.launch({ headless: true, args: ['--no-sandbox'] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  const errors = [];
  page.on('pageerror', e => errors.push('PAGEERROR ' + e.message));
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) errors.push(`HTTP ${r.status()} ${r.url()}`); });
  page.on('dialog', d => d.accept());

  const user = 'grey' + Date.now().toString().slice(-6);

  // Register via UI to let the app handle auth properly
  await page.goto(BASE + '/designer/#/register', { waitUntil: 'networkidle0' });
  await page.type('#username', user);
  await page.type('#password', 'secret1');
  await page.click('button.primary');
  await sleep(1000);

  // Create faction
  const L = () => String.fromCharCode(65 + Math.floor(Math.random() * 26));
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('button')].find(b => b.textContent.includes('Create New Faction'));
    if (b) b.click();
  });
  await sleep(500);
  const inputs = await page.$$('.confirm-dialog input');
  await inputs[0].type('Grey Test');
  await inputs[1].type('G' + L() + L());
  await page.evaluate(() => {
    const b = [...document.querySelectorAll('.confirm-dialog button')].find(b => b.textContent.trim() === 'Create');
    if (b) b.click();
  });
  await sleep(1500);

  const clickBtn = async text => {
    const found = await page.evaluate(t => {
      const b = [...document.querySelectorAll('button')].find(b => b.textContent.includes(t) && !b.disabled);
      if (b) { b.click(); return true; }
      return false;
    }, text);
    await sleep(300);
    return found;
  };

  // Helper to check if a label's field is greyed
  const isLabelGreyed = label => page.evaluate(l => {
    const labels = [...document.querySelectorAll('label')];
    // Exact label first: 'Fixed Numeric Cost' must not hit 'Includes Fixed Numeric Cost?'.
    const match = labels.find(la => la.textContent.trim() === l) || labels.find(la => la.textContent.includes(l));
    if (!match) return null;
    const field = match.closest('.sx-field');
    return field && field.classList.contains('sx-greyed');
  }, label);

  // Helper to click checkbox by label
  const clickCheckbox = async label => {
    await page.evaluate(l => {
      const labels = [...document.querySelectorAll('label')];
      const match = labels.find(la => la.textContent.includes(l));
      if (match) {
        const cb = match.querySelector('input[type="checkbox"]');
        if (cb) cb.click();
      }
    }, label);
    await sleep(400);
  };

  // Helper to check if input is disabled
  const isDisabled = sel => page.$eval(sel, e => e.disabled).catch(() => null);

  // 1. AE section
  await clickBtn('Alternate'); await sleep(500);
  check('AE: name initially greyed', await isLabelGreyed('Name'));
  await clickCheckbox('Alternate resource economy');
  check('AE: name available after enable', !(await isLabelGreyed('Name')));

  // Test typing preserves focus
  const typeFocus = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const match = labels.find(l => l.textContent === 'Name');
    if (!match) return null;
    const inp = match.closest('.sx-field').querySelector('input');
    if (!inp) return null;
    inp.focus();
    inp.value = '';
    inp.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  });
  if (typeFocus) {
    await page.keyboard.type('Mad');
    await sleep(200);
    const focused = await page.evaluate(() => document.activeElement && document.activeElement.value);
    check('AE: typing preserves focus', focused === 'Mad', `focused=${focused}`);
  }

  const tableGreyed = await page.evaluate(() => {
    const t = document.querySelector('.sx-table');
    return t && t.classList.contains('sx-greyed');
  });
  check('AE: table not greyed when enabled', !tableGreyed);

  await clickCheckbox('Alternate resource economy');
  if (process.env.PROBE) console.log('PROBE AE', await page.evaluate(() => [...document.querySelectorAll('.sx-field')].map(f => f.className + ':' + f.textContent.slice(0, 30) + ':' + (f.querySelector('input[type=checkbox]') ? f.querySelector('input[type=checkbox]').checked : '')).join(' | ')));
  check('AE: name greyed again after disable', await isLabelGreyed('Name'));

  // 2. UFA section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Unique faction'); await sleep(500);
  if (process.env.PROBE) console.log('PROBE UFA', await page.evaluate(() => location.hash + ' ' + [...document.querySelectorAll('button')].map(b => b.textContent.trim()).slice(0, 25).join(',') + ' || ' + [...document.querySelectorAll('.sx-field')].map(f => f.className + ':' + f.textContent.slice(0, 30)).join(' | ')));
  check('UFA: cost initially greyed', await isLabelGreyed('Fixed Numeric Cost'));
  await clickCheckbox('Includes Fixed Numeric Cost');
  check('UFA: cost available', !(await isLabelGreyed('Fixed Numeric Cost')));
  await clickCheckbox('Includes Fixed Numeric Cost');
  check('UFA: cost greyed again', await isLabelGreyed('Fixed Numeric Cost'));

  check('UFA: effect initially greyed', await isLabelGreyed('Fixed Numeric Effect'));
  await clickCheckbox('Includes Fixed Numeric Effect');
  check('UFA: effect available', !(await isLabelGreyed('Fixed Numeric Effect')));
  await clickCheckbox('Includes Fixed Numeric Effect');
  check('UFA: effect greyed again', await isLabelGreyed('Fixed Numeric Effect'));

  // 3. Setup section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Setup'); await sleep(500);
  check('Setup: earth region initially greyed', await isLabelGreyed('Earth Region'));

  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const loc = labels.find(l => l.textContent === 'Location type');
    const sel = loc.closest('.sx-field').querySelector('select');
    sel.value = 'single';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  check('Setup: earth region available for single', !(await isLabelGreyed('Earth Region')));

  const constraintsGreyed = await page.evaluate(() => {
    const h3 = [...document.querySelectorAll('h3')].find(h => h.textContent === 'Constraints');
    if (!h3) return null;
    const div = h3.parentElement;
    return div.style.opacity === '0.4' || div.style.pointerEvents === 'none';
  });
  check('Setup: constraints greyed for single', constraintsGreyed);

  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const loc = labels.find(l => l.textContent === 'Location type');
    const sel = loc.closest('.sx-field').querySelector('select');
    sel.value = 'multi';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  check('Setup: earth region greyed for multi', await isLabelGreyed('Earth Region'));

  // 4. Units section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Units'); await sleep(500);

  const mapGreyed1 = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const match = labels.find(l => l.textContent === 'Map image');
    return match && match.closest('.sx-field').classList.contains('sx-greyed');
  });
  check('Units: map image initially greyed', mapGreyed1);

  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const t = labels.find(l => l.textContent === 'Type');
    const sel = t.closest('.sx-field').querySelector('select');
    sel.value = 'Cultist';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  const mapGreyed2 = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const match = labels.find(l => l.textContent === 'Map image');
    return match && match.closest('.sx-field').classList.contains('sx-greyed');
  });
  check('Units: map image available after type', !mapGreyed2);

  // Cost type tests
  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const ct = labels.find(l => l.textContent === 'Cost Type');
    const sel = ct.closest('.sx-field').querySelector('select');
    sel.value = 'Fixed';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  const hasCostField = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    return labels.some(l => l.textContent === 'Cost' && !l.textContent.includes('Type'));
  });
  check('Units: cost field shown for Fixed', hasCostField);

  // Combat type tests
  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const ct = labels.find(l => l.textContent === 'Combat type');
    const sel = ct.closest('.sx-field').querySelector('select');
    sel.value = 'Fixed Dice';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  const hasDice = await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    return labels.some(l => l.textContent === 'Dice');
  });
  check('Units: dice field shown for Fixed Dice', hasDice);

  // 5. SBR section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Spell Book'); await sleep(500);
  const sbrDisabled1 = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    if (!row) return null;
    const num = row.querySelector('input[type="number"]');
    return num && num.disabled;
  });
  check('SBR: num initially disabled', sbrDisabled1);

  await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const cb = row.querySelector('input[type="checkbox"]');
    if (cb) cb.click();
  });
  await sleep(400);
  const sbrEnabled = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const num = row.querySelector('input[type="number"]');
    return num && !num.disabled;
  });
  check('SBR: num enabled after check', sbrEnabled);

  // 6. SB section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Spellbooks'); await sleep(500);
  const sbDisabled1 = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('table tbody tr')];
    const row = rows[0];
    if (!row) return null;
    const nums = [...row.querySelectorAll('input[type="number"]')];
    const effect = nums.find(n => n !== nums[0]); // not cost, the other one
    return effect && effect.disabled;
  });
  check('SB: effect initially disabled', sbDisabled1);

  await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const cb = row.querySelector('input[type="checkbox"]');
    if (cb) cb.click();
  });
  await sleep(400);
  const sbEnabled = await page.evaluate(() => {
    const rows = [...document.querySelectorAll('table tbody tr')];
    const row = rows[0];
    const nums = [...row.querySelectorAll('input[type="number"]')];
    const effect = nums.find(n => n !== nums[0]);
    return effect && !effect.disabled;
  });
  check('SB: effect enabled after check', sbEnabled);

  // 7. Tokens section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Tokens'); await sleep(500);
  const tokDisabled1 = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const nums = [...row.querySelectorAll('input[type="number"]')];
    const last = nums[nums.length - 1];
    return last && last.disabled;
  });
  check('Tokens: effect initially disabled', tokDisabled1);

  await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const cbs = [...row.querySelectorAll('input[type="checkbox"]')];
    const last = cbs[cbs.length - 1];
    if (last) last.click();
  });
  await sleep(400);
  const tokEnabled = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const nums = [...row.querySelectorAll('input[type="number"]')];
    const last = nums[nums.length - 1];
    return last && !last.disabled;
  });
  check('Tokens: effect enabled after check', tokEnabled);

  // 8. Custom section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Other Custom'); await sleep(500);
  const custDisabled1 = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const num = row.querySelector('input[type="number"]');
    return num && num.disabled;
  });
  check('Custom: num initially disabled', custDisabled1);

  await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const cb = row.querySelector('input[type="checkbox"]');
    if (cb) cb.click();
  });
  await sleep(400);
  const custEnabled = await page.evaluate(() => {
    const row = document.querySelector('table tbody tr');
    const num = row.querySelector('input[type="number"]');
    return num && !num.disabled;
  });
  check('Custom: num enabled after check', custEnabled);

  // 9. Menus section
  await clickBtn('Exit to Main'); await sleep(300);
  await clickBtn('Menu Design'); await sleep(500);

  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const sec = labels.find(l => l.textContent === 'Section');
    const sel = sec.closest('.sx-field').querySelector('select');
    sel.value = 'ufa';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  const itemGreyedUFA = await isLabelGreyed('Item');
  check('Menus: item greyed for UFA', itemGreyedUFA);

  await page.evaluate(() => {
    const labels = [...document.querySelectorAll('label')];
    const sec = labels.find(l => l.textContent === 'Section');
    const sel = sec.closest('.sx-field').querySelector('select');
    sel.value = 'ae';
    sel.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await sleep(400);
  const itemAvailAE = !(await isLabelGreyed('Item'));
  check('Menus: item available for AE', itemAvailAE);

  check('Menus: subtitle initially greyed', await isLabelGreyed('Subtitle'));
  await clickCheckbox('Menu Subtitle');
  check('Menus: subtitle available', !(await isLabelGreyed('Subtitle')));

  check('Menus: next menu initially greyed', await isLabelGreyed('Next Menu Prompt'));
  await clickCheckbox('Can lead to another Menu');
  check('Menus: next menu available', !(await isLabelGreyed('Next Menu Prompt')));
  check('Menus: next trigger available', !(await isLabelGreyed('Next Menu triggered by')));

  check('no page errors / failed requests', errors.length === 0, errors.join(' | '));
  await page.screenshot({ path: '/tmp/designer-smoke/greyed.png', fullPage: true });
  console.log(`\n${results.filter(Boolean).length}/${results.length} passed`);
  await browser.close();
})().catch(e => { console.error('CRASH', e); process.exit(1); });
