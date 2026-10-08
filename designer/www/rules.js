(function() {
  'use strict';

  const SB_TYPES = ['Ongoing', 'Action', 'Unlimited Action', 'Pre-Battle', 'Battle',
                    'Post-Battle', 'Movement', 'Gather Power Phase', 'Doom Phase', 'Once Only'];

  const UNIT_TYPES = ['Cultist', 'Monster', 'Terror', 'Great Old One', 'Elder God',
                      'Building', 'Custom Gate'];

  const COST_TYPES = ['Fixed', 'Variable', 'Awakening'];

  const COMBAT_TYPES = ['Fixed Dice', 'Variable Dice', 'Fixed Results', 'Variable Results', 'N/A'];

  const SECTIONS = [
    {key: 'ae', title: 'Alternate economy'},
    {key: 'ufa', title: 'Unique faction ability'},
    {key: 'setup', title: 'Setup'},
    {key: 'units', title: 'Units'},
    {key: 'sbr', title: 'Spell Book Requirements'},
    {key: 'sb', title: 'Spellbooks'},
    {key: 'region', title: 'Faction region (ex. "the Moon")'},
    {key: 'tokens', title: 'Tokens (ex. "Craters")'},
    {key: 'custom', title: 'Other Custom (ex. "Cursed Tomes")'},
    {key: 'menus', title: 'Menu Design'}
  ];

  const BUILD_SECTIONS = ['ae', 'ufa', 'setup', 'units', 'sbr', 'sb', 'region', 'tokens', 'custom'];

  function newId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = '';
    for (let i = 0; i < 8; i++) {
      id += chars[Math.floor(Math.random() * chars.length)];
    }
    return id;
  }

  function newDesign() {
    return {
      meta: {color: null},
      card: {image: null},
      sbImages: {mode: null, all: null, each: [null, null, null, null, null, null]},
      ae: {
        enabled: false,
        name: '',
        acronym: '',
        rows: [{id: newId(), sign: '+', kind: 'fixed', qty: null, calc: '', desc: ''}]
      },
      ufa: {
        name: '',
        phase: null,
        type: null,
        hasCost: false,
        cost: null,
        hasEffect: false,
        effect: null,
        text: ''
      },
      setup: {
        text: '',
        location: null,
        earthRegion: null,
        libraryRegion: null,
        constraints: {
          follows: null,
          water: true,
          land: true,
          emptyFactionGlyph: true,
          thorn: true,
          dragon: true,
          chevron: true,
          noneOf3: true,
          proximity: 'N/A',
          custom: ''
        },
        gate: null,
        units: [{id: newId(), onMap: true, name: '', qty: null}],
        power: 8,
        aeStart: 0
      },
      units: {
        rows: [
          blankUnit(),
          blankUnit(),
          blankUnit()
        ]
      },
      sbr: {
        multiText: '',
        rows: Array(6).fill(null).map(() => ({id: newId(), text: '', hasNum: false, num: null}))
      },
      sb: {
        rows: Array(6).fill(null).map(() => ({
          id: newId(),
          name: '',
          type: null,
          cost: 0,
          hasEffect: false,
          effect: null,
          text: ''
        }))
      },
      region: {
        rows: [{id: newId(), name: '', image: null, restrictions: '', adjacency: ''}]
      },
      tokens: {
        rows: [{
          id: newId(),
          name: '',
          qty: null,
          image: null,
          placement: '',
          effects: '',
          hasEffect: false,
          effect: null
        }]
      },
      custom: {
        rows: [{
          id: newId(),
          name: '',
          image: null,
          placement: '',
          usage: '',
          effects: '',
          hasNum: false,
          num: null
        }]
      },
      menus: {
        rows: [{
          id: newId(),
          name: '',
          section: null,
          item: null,
          prompted: null,
          title: '',
          hasSubtitle: false,
          subtitle: '',
          button: '',
          cancel: false,
          skip: false,
          leadsToNext: false,
          next: null,
          nextTrigger: ''
        }]
      }
    };
  }

  function blankUnit() {
    return {
      id: newId(),
      type: null,
      name: '',
      mapImage: null,
      mapScale: 1.0,
      silhouette: null,
      qty: null,
      costType: null,
      cost: null,
      costCalc: '',
      awakenReq: '',
      awakenPower: null,
      awakenRegion: '',
      combatType: null,
      dice: null,
      diceCalc: '',
      pains: null,
      kills: null,
      resultsCalc: '',
      relatedSb: [],
      relatedSbNames: [],
      abilityName: '',
      abilityText: ''
    };
  }

  function blankRow(tablePath) {
    if (tablePath === 'ae.rows') {
      return {id: newId(), sign: '+', kind: 'fixed', qty: null, calc: '', desc: ''};
    } else if (tablePath === 'setup.units') {
      return {id: newId(), onMap: true, name: '', qty: null};
    } else if (tablePath === 'units.rows') {
      return blankUnit();
    } else if (tablePath === 'sbr.rows') {
      return {id: newId(), text: '', hasNum: false, num: null};
    } else if (tablePath === 'sb.rows') {
      return {id: newId(), name: '', type: null, cost: 0, hasEffect: false, effect: null, text: ''};
    } else if (tablePath === 'region.rows') {
      return {id: newId(), name: '', image: null, restrictions: '', adjacency: ''};
    } else if (tablePath === 'tokens.rows') {
      return {id: newId(), name: '', qty: null, image: null, placement: '', effects: '', hasEffect: false, effect: null};
    } else if (tablePath === 'custom.rows') {
      return {id: newId(), name: '', image: null, placement: '', usage: '', effects: '', hasNum: false, num: null};
    } else if (tablePath === 'menus.rows') {
      return {
        id: newId(),
        name: '',
        section: null,
        item: null,
        prompted: null,
        title: '',
        hasSubtitle: false,
        subtitle: '',
        button: '',
        cancel: false,
        skip: false,
        leadsToNext: false,
        next: null,
        nextTrigger: ''
      };
    }
    return null;
  }

  function eq(a, b) {
    if (a === b) return true;
    if (a == null || b == null) return false;
    if (Array.isArray(a) && Array.isArray(b)) {
      if (a.length !== b.length) return false;
      return a.every((v, i) => eq(v, b[i]));
    }
    if (typeof a === 'object' && typeof b === 'object') {
      const ka = Object.keys(a).sort();
      const kb = Object.keys(b).sort();
      if (ka.length !== kb.length) return false;
      return ka.every(k => eq(a[k], b[k]));
    }
    return false;
  }

  function normalizeForComparison(obj) {
    if (obj == null) return obj;
    if (Array.isArray(obj)) {
      return obj.map(item => normalizeForComparison(item));
    }
    if (typeof obj === 'object') {
      const result = {};
      for (let k in obj) {
        if (k !== 'id') {
          result[k] = normalizeForComparison(obj[k]);
        }
      }
      return result;
    }
    return obj;
  }

  // Empty = nothing but blank rows and default values. Blank rows are ignored, so a section with
  // extra empty rows (or one whose content was all deleted) still reads "empty".
  function stripBlankRows(key, sec) {
    if (sec == null || typeof sec !== 'object') return sec;
    const out = Object.assign({}, sec);
    ['rows', 'units'].forEach(t => {
      if (Array.isArray(out[t])) {
        const blank = blankRow(key + '.' + t);
        if (blank) out[t] = out[t].filter(r => !isRowEmpty(r, blank));
      }
    });
    return out;
  }

  function isEmpty(key, design) {
    const defaults = newDesign();
    const a = normalizeForComparison(stripBlankRows(key, design[key]));
    const b = normalizeForComparison(stripBlankRows(key, defaults[key]));
    return eq(a, b);
  }

  function isRowEmpty(row, blankRow) {
    const a = normalizeForComparison(row);
    const b = normalizeForComparison(blankRow);
    return eq(a, b);
  }

  function isRowComplete(row, rowType) {
    if (rowType === 'ae') {
      if (row.kind === 'fixed') {
        return row.sign && row.kind && row.qty != null && row.desc;
      } else {
        return row.sign && row.kind && row.calc && row.desc;
      }
    } else if (rowType === 'setupUnit') {
      return row.name && row.qty != null;
    } else if (rowType === 'unit') {
      if (!row.type || !row.name || !row.silhouette || row.qty == null) return false;
      if (row.qty < 1 || row.qty > 20) return false;
      if (!row.costType) return false;
      if (row.costType === 'Fixed' && row.cost == null) return false;
      if (row.costType === 'Variable' && !row.costCalc) return false;
      if (row.costType === 'Awakening' && (!row.awakenReq || row.awakenPower == null || !row.awakenRegion)) return false;
      if (!row.combatType) return false;
      if (row.combatType === 'Fixed Dice' && row.dice == null) return false;
      if (row.combatType === 'Variable Dice' && !row.diceCalc) return false;
      if (row.combatType === 'Fixed Results' && (row.pains == null || row.kills == null)) return false;
      if (row.combatType === 'Variable Results' && !row.resultsCalc) return false;
      return true;
    } else if (rowType === 'sbr') {
      if (!row.text) return false;
      if (row.hasNum && row.num == null) return false;
      return true;
    } else if (rowType === 'sb') {
      if (!row.name || !row.type || !row.text) return false;
      if (row.hasEffect && row.effect == null) return false;
      return true;
    } else if (rowType === 'region') {
      return row.name && row.image && row.restrictions && row.adjacency;
    } else if (rowType === 'tokens') {
      if (!row.name || row.qty == null || !row.image || !row.placement || !row.effects) return false;
      if (row.hasEffect && row.effect == null) return false;
      return true;
    } else if (rowType === 'custom') {
      if (!row.name || !row.image || !row.placement || !row.usage || !row.effects) return false;
      if (row.hasNum && row.num == null) return false;
      return true;
    }
    return false;
  }

  function status(key, design) {
    const d = design[key];

    if (key === 'ae') {
      if (isEmpty(key, design)) return 'N/A';
      if (!d.enabled) return 'N/A';
      if (!d.name || !d.acronym || d.acronym.length !== 1) return 'Incomplete';
      const completeRows = d.rows.filter(r => isRowComplete(r, 'ae'));
      if (completeRows.length === 0) return 'Incomplete';
      const partialRows = d.rows.filter(r => !isRowComplete(r, 'ae') && !isRowEmpty(r, blankRow('ae.rows')));
      if (partialRows.length > 0) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'ufa') {
      if (!d.name || !d.phase || !d.type || !d.text) return 'Incomplete';
      if (d.hasCost && d.cost == null) return 'Incomplete';
      if (d.hasEffect && d.effect == null) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'setup') {
      if (!d.text || !d.location) return 'Incomplete';
      if (d.location === 'single' && (!d.earthRegion || !d.libraryRegion)) return 'Incomplete';
      if (d.location === 'multi' && !d.constraints.follows) return 'Incomplete';
      if (d.gate == null) return 'Incomplete';
      if (d.power == null) return 'Incomplete';
      const completeUnits = d.units.filter(u => isRowComplete(u, 'setupUnit'));
      if (completeUnits.length === 0) return 'Incomplete';
      const partialUnits = d.units.filter(u => !isRowComplete(u, 'setupUnit') && !isRowEmpty(u, blankRow('setup.units')));
      if (partialUnits.length > 0) return 'Incomplete';
      const aeEnabled = design.ae && design.ae.enabled;
      if (aeEnabled && d.aeStart == null) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'units') {
      const completeUnits = d.rows.filter(u => isRowComplete(u, 'unit'));
      if (completeUnits.length === 0) return 'Incomplete';
      const partialUnits = d.rows.filter(u => !isRowComplete(u, 'unit') && !isRowEmpty(u, blankUnit()));
      if (partialUnits.length > 0) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'sbr') {
      for (let row of d.rows) {
        if (!isRowComplete(row, 'sbr')) return 'Incomplete';
      }
      return 'Complete';
    }

    if (key === 'sb') {
      const completeRows = d.rows.filter(r => isRowComplete(r, 'sb'));
      if (completeRows.length < 6) return 'Incomplete';
      const partialRows = d.rows.filter(r => !isRowComplete(r, 'sb') && !isRowEmpty(r, blankRow('sb.rows')));
      if (partialRows.length > 0) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'region') {
      if (isEmpty(key, design)) return 'N/A';
      const allEmpty = d.rows.every(r => isRowEmpty(r, blankRow('region.rows')));
      if (allEmpty) return 'N/A';
      const completeRows = d.rows.filter(r => isRowComplete(r, 'region'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('region.rows')));
      if (completeRows.length === nonEmptyRows.length && completeRows.length > 0) return 'Complete';
      return 'Incomplete';
    }

    if (key === 'tokens') {
      if (isEmpty(key, design)) return 'N/A';
      const allEmpty = d.rows.every(r => isRowEmpty(r, blankRow('tokens.rows')));
      if (allEmpty) return 'N/A';
      const completeRows = d.rows.filter(r => isRowComplete(r, 'tokens'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('tokens.rows')));
      if (completeRows.length === nonEmptyRows.length && completeRows.length > 0) return 'Complete';
      return 'Incomplete';
    }

    if (key === 'custom') {
      if (isEmpty(key, design)) return 'N/A';
      const allEmpty = d.rows.every(r => isRowEmpty(r, blankRow('custom.rows')));
      if (allEmpty) return 'N/A';
      const completeRows = d.rows.filter(r => isRowComplete(r, 'custom'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('custom.rows')));
      if (completeRows.length === nonEmptyRows.length && completeRows.length > 0) return 'Complete';
      return 'Incomplete';
    }

    return 'N/A';
  }

  function buildReady(design) {
    return BUILD_SECTIONS.every(key => {
      const s = status(key, design);
      return s === 'N/A' || s === 'Complete';
    });
  }

  function fixedNumbers(design) {
    const numbers = [];

    if (design.ae && design.ae.enabled) {
      design.ae.rows.forEach(row => {
        if (row.kind === 'fixed' && row.qty != null) {
          numbers.push({
            section: 'ae',
            sectionTitle: 'Alternate Economy',
            rowId: row.id,
            field: 'qty',
            name: row.desc || 'Increment',
            value: row.qty
          });
        }
      });
    }

    if (design.ufa) {
      if (design.ufa.hasCost && design.ufa.cost != null) {
        numbers.push({
          section: 'ufa',
          sectionTitle: 'Unique Faction Ability',
          rowId: null,
          field: 'cost',
          name: 'UFA Cost',
          value: design.ufa.cost
        });
      }
      if (design.ufa.hasEffect && design.ufa.effect != null) {
        numbers.push({
          section: 'ufa',
          sectionTitle: 'Unique Faction Ability',
          rowId: null,
          field: 'effect',
          name: 'UFA Effect',
          value: design.ufa.effect
        });
      }
    }

    if (design.setup) {
      if (design.setup.power != null) {
        numbers.push({
          section: 'setup',
          sectionTitle: 'Setup',
          rowId: null,
          field: 'power',
          name: 'Starting Power',
          value: design.setup.power
        });
      }
      if (design.ae && design.ae.enabled && design.setup.aeStart != null) {
        numbers.push({
          section: 'setup',
          sectionTitle: 'Setup',
          rowId: null,
          field: 'aeStart',
          name: 'Starting ' + (design.ae.name || 'AE'),
          value: design.setup.aeStart
        });
      }
      design.setup.units.forEach(u => {
        if (u.qty != null && u.name) {
          numbers.push({
            section: 'setup',
            sectionTitle: 'Setup',
            rowId: u.id,
            field: 'qty',
            name: u.name + ' setup quantity',
            value: u.qty
          });
        }
      });
    }

    if (design.units) {
      design.units.rows.forEach(u => {
        if (u.qty != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'qty',
            name: u.name + ' quantity',
            value: u.qty
          });
        }
        if (u.costType === 'Fixed' && u.cost != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'cost',
            name: u.name + ' cost',
            value: u.cost
          });
        }
        if (u.costType === 'Awakening' && u.awakenPower != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'awakenPower',
            name: u.name + ' awaken power',
            value: u.awakenPower
          });
        }
        if (u.combatType === 'Fixed Dice' && u.dice != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'dice',
            name: u.name + ' combat dice',
            value: u.dice
          });
        }
        if (u.combatType === 'Fixed Results' && u.name) {
          if (u.pains != null) {
            numbers.push({
              section: 'units',
              sectionTitle: 'Units',
              rowId: u.id,
              field: 'pains',
              name: u.name + ' pains',
              value: u.pains
            });
          }
          if (u.kills != null) {
            numbers.push({
              section: 'units',
              sectionTitle: 'Units',
              rowId: u.id,
              field: 'kills',
              name: u.name + ' kills',
              value: u.kills
            });
          }
        }
      });
    }

    if (design.sbr) {
      design.sbr.rows.forEach(row => {
        if (row.hasNum && row.num != null) {
          numbers.push({
            section: 'sbr',
            sectionTitle: 'Spellbook Requirements',
            rowId: row.id,
            field: 'num',
            name: row.text || 'SBR',
            value: row.num
          });
        }
      });
    }

    if (design.sb) {
      design.sb.rows.forEach(row => {
        if (row.cost != null && row.name) {
          numbers.push({
            section: 'sb',
            sectionTitle: 'Spellbooks',
            rowId: row.id,
            field: 'cost',
            name: row.name + ' cost',
            value: row.cost
          });
        }
        if (row.hasEffect && row.effect != null && row.name) {
          numbers.push({
            section: 'sb',
            sectionTitle: 'Spellbooks',
            rowId: row.id,
            field: 'effect',
            name: row.name + ' effect',
            value: row.effect
          });
        }
      });
    }

    if (design.tokens) {
      design.tokens.rows.forEach(row => {
        if (row.qty != null && row.name) {
          numbers.push({
            section: 'tokens',
            sectionTitle: 'Tokens',
            rowId: row.id,
            field: 'qty',
            name: row.name + ' quantity',
            value: row.qty
          });
        }
        if (row.hasEffect && row.effect != null && row.name) {
          numbers.push({
            section: 'tokens',
            sectionTitle: 'Tokens',
            rowId: row.id,
            field: 'effect',
            name: row.name + ' effect',
            value: row.effect
          });
        }
      });
    }

    if (design.custom) {
      design.custom.rows.forEach(row => {
        if (row.hasNum && row.num != null && row.name) {
          numbers.push({
            section: 'custom',
            sectionTitle: 'Other Custom',
            rowId: row.id,
            field: 'num',
            name: row.name + ' number',
            value: row.num
          });
        }
      });
    }

    return numbers;
  }

  function describeSectionDiff(key, oldDesign, newDesign) {
    const parts = [];
    const old = oldDesign[key];
    const neu = newDesign[key];

    if (eq(old, neu)) return '';

    if (key === 'ae') {
      if (old.name !== neu.name) parts.push('name changed to "' + neu.name + '"');
      if (old.acronym !== neu.acronym) parts.push('acronym changed to "' + neu.acronym + '"');
      const oldRows = old.rows.map(r => r.desc).join(', ');
      const newRows = neu.rows.map(r => r.desc).join(', ');
      if (oldRows !== newRows) parts.push('increments changed');
    } else if (key === 'ufa') {
      if (old.name !== neu.name) parts.push('name changed to "' + neu.name + '"');
      if (old.text !== neu.text) parts.push('text changed');
    } else if (key === 'setup') {
      if (old.text !== neu.text) parts.push('setup text changed');
      if (old.location !== neu.location) parts.push('location type changed');
    } else if (key === 'units') {
      const oldUnits = old.rows.filter(u => u.name).map(u => u.name);
      const newUnits = neu.rows.filter(u => u.name).map(u => u.name);
      const added = newUnits.filter(n => !oldUnits.includes(n));
      const removed = oldUnits.filter(n => !newUnits.includes(n));
      added.forEach(n => parts.push('new unit "' + n + '"'));
      removed.forEach(n => parts.push('removed unit "' + n + '"'));
      newUnits.forEach(name => {
        const oldU = old.rows.find(u => u.name === name);
        const newU = neu.rows.find(u => u.name === name);
        if (oldU && newU && !eq(oldU, newU)) {
          parts.push('"' + name + '" changed');
        }
      });
    } else if (key === 'sbr') {
      parts.push('spellbook requirements changed');
    } else if (key === 'sb') {
      const oldSbs = old.rows.filter(s => s.name).map(s => s.name);
      const newSbs = neu.rows.filter(s => s.name).map(s => s.name);
      const added = newSbs.filter(n => !oldSbs.includes(n));
      const removed = oldSbs.filter(n => !newSbs.includes(n));
      added.forEach(n => parts.push('new spellbook "' + n + '"'));
      removed.forEach(n => parts.push('removed spellbook "' + n + '"'));
      newSbs.forEach(name => {
        const oldS = old.rows.find(s => s.name === name);
        const newS = neu.rows.find(s => s.name === name);
        if (oldS && newS && !eq(oldS, newS)) {
          parts.push('"' + name + '" changed');
        }
      });
    } else if (key === 'region') {
      parts.push('faction region changed');
    } else if (key === 'tokens') {
      parts.push('tokens changed');
    } else if (key === 'custom') {
      parts.push('custom elements changed');
    } else if (key === 'menus') {
      parts.push('menu design changed');
    }

    return parts.join('; ');
  }

  window.Rules = {
    SECTIONS,
    BUILD_SECTIONS,
    SB_TYPES,
    UNIT_TYPES,
    COST_TYPES,
    COMBAT_TYPES,
    newDesign,
    blankRow,
    isEmpty,
    status,
    buildReady,
    fixedNumbers,
    describeSectionDiff,
    newId
  };
})();
