(function() {
  'use strict';

  const ABILITY_TYPES = ['Ongoing', 'Action', 'Unlimited Action', 'Pre-Battle', 'Battle',
                         'Post-Battle', 'Move', 'Recruit Cultist Action', 'Summon Monster/Terror',
                         'Awaken GOO/EG/iGOO/iEG', 'Create Gate', 'Gather Power Phase',
                         'First Player Phase', 'Doom Phase', 'Once Only', 'Setup Variant'];

  // Legacy name for backwards compatibility
  const SB_TYPES = ABILITY_TYPES;

  const UNIT_TYPES = ['Cultist', 'Monster', 'Terror', 'Great Old One', 'Elder God',
                      'Building', 'Custom Gate'];

  // Stand-alone (neutral) units from My Units: no Cultists, Buildings or Gates, which belong to a faction
  const NEUTRAL_UNIT_TYPES = ['Cultist', 'Monster', 'Terror', 'Great Old One', 'Elder God'];

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
    {key: 'menus', title: 'Menu Design'},
    {key: 'interactions', title: 'Ability Interactions'}
  ];

  const BUILD_SECTIONS = ['ae', 'ufa', 'setup', 'units', 'sbr', 'sb', 'region', 'tokens', 'custom', 'interactions'];

  const MAP_SECTIONS = [
    {key: 'images', title: 'Map Images'},
    {key: 'bitmaps', title: 'Map Placement Bitmaps'},
    {key: 'adjacency', title: 'Adjacency'},
    {key: 'units', title: 'Map Units'},
    {key: 'tokens', title: 'Tokens'},
    {key: 'sb', title: 'Spellbooks'},
    {key: 'glyphs', title: 'Map Glyphs'},
    {key: 'abilities', title: 'Map Abilities'}
  ];

  const MAP_BUILD_SECTIONS = ['images', 'bitmaps', 'adjacency', 'units', 'tokens', 'sb', 'glyphs', 'abilities'];

  const MAP_ABILITY_PHASES = ['Gather Power', 'Determine First Player', 'Action', 'Doom', 'Battle', 'Ongoing', 'Setup'];
  const MAP_ABILITY_TYPES = ['Action', 'Ongoing', 'Battle', 'Pre-Battle', 'Post-Battle', 'Doom', 'Setup'];

  function newId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = '';
    for (let i = 0; i < 8; i++) {
      id += chars[Math.floor(Math.random() * chars.length)];
    }
    return id;
  }

  // Older designs were saved before some sections existed (e.g. 'interactions').
  // Fill any missing section with its default so every page and status check works.
  // Interactions rows get fixed ids so the server's own backfill (designer_server.py) matches.
  const BACKFILL_IDS = {interactions: ['ia-sleeper', 'ia-neutral', 'ia-bubastis']};
  function backfillDesign(design) {
    if (!design || typeof design !== 'object') return design;
    const defaults = newDesign();
    Object.keys(defaults).forEach(key => {
      const sec = defaults[key];
      // A section that only holds an admin note (stub left by an older admin-notes save) counts as missing
      const stub = design[key] && typeof design[key] === 'object' && sec && Array.isArray(sec.rows) && !Array.isArray(design[key].rows);
      if (design[key] == null || stub) {
        const ids = BACKFILL_IDS[key];
        if (ids && sec && Array.isArray(sec.rows)) sec.rows.forEach((r, i) => { if (ids[i]) r.id = ids[i]; });
        design[key] = stub ? Object.assign(sec, design[key], {rows: sec.rows}) : sec;
      }
    });
    return design;
  }

  function newDesign() {
    const design = {
      meta: {color: null},
      card: {image: null, glyph: null},
      sbImages: {mode: null, all: null, each: [null, null, null, null, null, null]},
      sbImagesB: {mode: null, all: null, each: [null, null, null, null, null, null]},   // side B of 2 sided spellbooks
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
        twoSided: false,   // "All 2 sided": every spellbook has a side A (the fields below) and a side B (the ...B fields).
                           // Each row's own twoSided overrides it; a row without one follows this setting.
        rows: Array(6).fill(null).map(() => ({
          id: newId(),
          name: '',
          type: null,
          cost: 0,
          hasEffect: false,
          effect: null,
          text: '',
          nameB: '',
          typeB: null,
          costB: 0,
          hasEffectB: false,
          effectB: null,
          textB: '',
          // Dual powers: a side split into power 1 (the fields above) and power 2 (the ...2 fields)
          dual: false, name2: '', type2: null, cost2: 0, hasEffect2: false, effect2: null, text2: '',
          dualB: false, nameB2: '', typeB2: null, costB2: 0, hasEffectB2: false, effectB2: null, textB2: ''
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
          done: false,
          multiSelect: false,
          repeat: false,
          repeatCount: '',
          numberPick: false,
          numberMin: '',
          numberMax: '',
          greyedOptions: false,
          greyedReason: '',
          infoOnly: false,
          confirm: false,
          confirmText: '',
          showPicked: false,
          leadsToNext: false,
          next: null,
          nextTrigger: ''
        }]
      },
      interactions: {
        rows: [
          {id: newId(), otherFaction: 'Sleeper', abilityType: 'Spellbook', ability: 'Ancient Sorcery', abilityText: '', yourAbility: 'ufa', interactionDesc: ''},
          {id: newId(), otherFaction: 'Neutral Monsters', abilityType: 'Unit Special', ability: 'Blasphemous Obeisance', abilityText: '', yourAbility: '', interactionDesc: ''},
          {id: newId(), otherFaction: 'Bubastis', abilityType: 'Unit Special', ability: 'Moon', abilityText: '', yourAbility: '', interactionDesc: ''}
        ]
      }
    };
    // Every design section ends with a free "Any custom logic or rules" box
    BUILD_SECTIONS.forEach(key => { design[key].customLogic = ''; design[key].adminNotes = ''; });
    return design;
  }

  function newMapDesign() {
    const design = {
      images: {
        items: [],  // [{id, label, image}]
        layout: {type: null, columns: 2, order: [], notes: ''},  // type: null | 'single' | 'side-by-side' | 'stacked' | 'grid'
        regions: {rows: []}  // [{id, name, type, glyphs:{gc,cc,bg,ys,dragon,chevron,thorn,...mapGlyphIds}}]
      },
      bitmaps: {
        items: [],  // [{id, imageId, image, colors: {"#rrggbb": regionId}, centroids: {regionId: {x,y}}}]
        unplacedRegions: []
      },
      adjacency: {
        cols: 32,
        rows: 16,
        cells: [],  // [regionId|null...]
        special: {rows: []}  // [{id, name, desc, cost, oneWay, pairs:[{id,from,to}]}]
      },
      units: {
        wikiUrl: '',
        rows: []  // same as faction units, but relatedSb stays [] for map units
      },
      tokens: {
        rows: []  // same as faction tokens
      },
      sb: {
        requirements: {rows: []},  // [{id, text, hasNum, num}]
        books: {rows: []}  // [{id, name, type, cost, hasEffect, effect, text}]
      },
      glyphs: {
        rows: []  // [{id, name, image, desc}]
      },
      abilities: {
        rows: []  // [{id, name, when, type, cost, who, text}]
      }
    };
    // Every map design section ends with a free "Any custom logic or rules" box
    MAP_BUILD_SECTIONS.forEach(key => { design[key].customLogic = ''; });
    return design;
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
      hasAbility: false,
      abilityType: null,
      abilityName: '',
      abilityText: '',
      spellbook: {
        enabled: false,
        requirement: {text: '', hasNum: false, num: null},
        book: {name: '', type: null, cost: 0, hasEffect: false, effect: null, text: ''}
      }
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
      return {id: newId(), name: '', type: null, cost: 0, hasEffect: false, effect: null, text: '',
        nameB: '', typeB: null, costB: 0, hasEffectB: false, effectB: null, textB: '',
        dual: false, name2: '', type2: null, cost2: 0, hasEffect2: false, effect2: null, text2: '',
        dualB: false, nameB2: '', typeB2: null, costB2: 0, hasEffectB2: false, effectB2: null, textB2: ''};
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
        done: false,
        multiSelect: false,
        repeat: false,
        repeatCount: '',
        numberPick: false,
        numberMin: '',
        numberMax: '',
        greyedOptions: false,
        greyedReason: '',
        infoOnly: false,
        confirm: false,
        confirmText: '',
        showPicked: false,
        leadsToNext: false,
        next: null,
        nextTrigger: '',
        additionalButtons: [],
        menuInstructions: ''
      };
    } else if (tablePath === 'interactions.rows') {
      return {
        id: newId(),
        otherFaction: '',
        abilityType: '',
        ability: '',
        abilityText: '',
        yourAbility: '',
        interactionDesc: ''
      };
    } else if (tablePath === 'menus.rows.additionalButtons.rows') {
      return {
        id: newId(),
        text: '',
        function: ''
      };
    }
    return null;
  }

  function blankMapRow(tablePath) {
    if (tablePath === 'images.items') {
      return {id: newId(), label: '', image: null};
    } else if (tablePath === 'images.regions.rows') {
      return {id: newId(), name: '', type: 'Land', glyphs: {gc: false, cc: false, bg: false, ys: false, dragon: false, chevron: false, thorn: false}};
    } else if (tablePath === 'bitmaps.items') {
      return {id: newId(), image: null, colors: {}, centroids: {}};
    } else if (tablePath === 'adjacency.special.rows') {
      return {id: newId(), name: '', desc: '', cost: null, oneWay: false, pairs: []};
    } else if (tablePath === 'adjacency.special.rows.pairs') {
      return {id: newId(), from: null, to: null};
    } else if (tablePath === 'units.rows') {
      return blankUnit();
    } else if (tablePath === 'tokens.rows') {
      return {id: newId(), name: '', qty: null, image: null, placement: '', effects: '', hasEffect: false, effect: null};
    } else if (tablePath === 'sb.requirements.rows') {
      return {id: newId(), text: '', hasNum: false, num: null};
    } else if (tablePath === 'sb.books.rows') {
      return {id: newId(), name: '', type: null, cost: 0, hasEffect: false, effect: null, text: ''};
    } else if (tablePath === 'glyphs.rows') {
      return {id: newId(), name: '', image: null, desc: ''};
    } else if (tablePath === 'abilities.rows') {
      return {id: newId(), name: '', when: null, type: null, cost: null, who: '', text: ''};
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
    // Settings added later (e.g. sb.twoSided) count as their default on older designs
    const sec = design[key] && typeof design[key] === 'object' && !Array.isArray(design[key])
      ? Object.assign({}, defaults[key], design[key]) : design[key];
    const a = normalizeForComparison(stripBlankRows(key, sec));
    const b = normalizeForComparison(stripBlankRows(key, defaults[key]));
    return eq(a, b);
  }

  function isMapEmpty(key, design) {
    const defaults = newMapDesign();
    const sec = design[key] && typeof design[key] === 'object' && !Array.isArray(design[key])
      ? Object.assign({}, defaults[key], design[key]) : design[key];
    const a = normalizeForComparison(sec);
    const b = normalizeForComparison(defaults[key]);
    return eq(a, b);
  }

  // Is this spellbook 2 sided? Its own box wins; older rows without one follow "All 2 sided".
  function sbTwo(sb, row) {
    return row && row.twoSided != null ? !!row.twoSided : !!(sb && sb.twoSided);
  }

  function sbAnyTwo(sb) {
    return !!(sb && sb.rows && sb.rows.some(r => sbTwo(sb, r)));
  }

  function isRowEmpty(row, blankRow) {
    // Fields added later (e.g. menu done/multiSelect/repeat) count as their default on older rows
    const a = normalizeForComparison(Object.assign({}, blankRow, row));
    const b = normalizeForComparison(blankRow);
    return eq(a, b);
  }

  // Does this unit have a special ability? Its own box wins; older units without one count as
  // having one when they already have an ability name or text.
  function unitHasAbility(u) {
    return u && u.hasAbility != null ? !!u.hasAbility : !!(u && (u.abilityName || u.abilityText));
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
      if (unitHasAbility(row) && !row.abilityText) return false;
      return true;
    } else if (rowType === 'sbr') {
      if (!row.text) return false;
      if (row.hasNum && row.num == null) return false;
      return true;
    } else if (rowType === 'sb' || rowType === 'sbB') {
      // One side of a spellbook ('sbB' = side B of a 2 sided one). A side with dual powers needs both powers.
      const side = rowType === 'sbB' ? 'B' : '';
      const part = sfx => !!(row['name' + sfx] && row['type' + sfx] && row['text' + sfx]) &&
        !(row['hasEffect' + sfx] && row['effect' + sfx] == null);
      return part(side) && (!row['dual' + side] || part(side + '2'));
    } else if (rowType === 'region') {
      return row.name && row.image && row.restrictions && row.adjacency;
    } else if (rowType === 'tokens') {
      if (!row.name || row.qty == null || !row.image || !row.placement || !row.effects) return false;
      if (row.hasEffect && row.effect == null) return false;
      return true;
    } else if (rowType === 'custom') {
      if (!row.name || !row.placement || !row.usage || !row.effects) return false;
      if (row.hasNum && row.num == null) return false;
      return true;
    } else if (rowType === 'mapGlyph') {
      return row.name && row.image && row.desc;
    } else if (rowType === 'mapAbility') {
      return row.name && row.when && row.type && row.who && row.text;
    } else if (rowType === 'mapSbRequirement') {
      if (!row.text) return false;
      if (row.hasNum && row.num == null) return false;
      return true;
    } else if (rowType === 'mapSbBook') {
      if (!row.name || !row.type || !row.text) return false;
      if (row.hasEffect && row.effect == null) return false;
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
      const done = r => isRowComplete(r, 'sb') && (!sbTwo(d, r) || isRowComplete(r, 'sbB'));
      const completeRows = d.rows.filter(done);
      if (completeRows.length < 6) return 'Incomplete';
      // Ticking a blank spellbook's "2 sided" box alone doesn't make it a part-filled spellbook
      const contentOnly = r => { const c = Object.assign({}, r); delete c.twoSided; return c; };
      const partialRows = d.rows.filter(r => !done(r) && !isRowEmpty(contentOnly(r), blankRow('sb.rows')));
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

    if (key === 'interactions') {
      // Only Ancient Sorcery row is required
      const ancientSorceryRow = ((d && d.rows) || []).find(r =>
        r.otherFaction === 'Sleeper' &&
        r.abilityType === 'Spellbook' &&
        r.ability === 'Ancient Sorcery'
      );
      if (!ancientSorceryRow) return 'Incomplete';
      if (!ancientSorceryRow.yourAbility || !ancientSorceryRow.interactionDesc) return 'Incomplete';
      return 'Complete';
    }

    return 'N/A';
  }

  function mapStatus(key, design) {
    const d = design[key];

    if (key === 'images') {
      if (!d.items || d.items.length === 0) return 'Incomplete';
      if (d.items.some(item => !item.image)) return 'Incomplete';
      if (!d.regions || !d.regions.rows || d.regions.rows.length === 0) return 'Incomplete';
      if (d.regions.rows.some(r => !r.name)) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'bitmaps') {
      if (!d.items || d.items.length === 0) return 'Incomplete';
      if (d.items.some(item => !item.image)) return 'Incomplete';
      const regionIds = design.images && design.images.regions && design.images.regions.rows
        ? design.images.regions.rows.map(r => r.id) : [];
      const placed = new Set();
      d.items.forEach(item => {
        if (item.colors) {
          Object.values(item.colors).forEach(rid => placed.add(rid));
        }
      });
      if (regionIds.some(rid => !placed.has(rid))) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'adjacency') {
      const regionIds = design.images && design.images.regions && design.images.regions.rows
        ? design.images.regions.rows.map(r => r.id) : [];
      if (regionIds.length === 0) return 'Incomplete';
      const adjacency = {};
      const cells = d.cells || [];
      for (let i = 0; i < cells.length; i++) {
        const rid = cells[i];
        if (!rid) continue;
        const r = Math.floor(i / (d.cols || 32));
        const c = i % (d.cols || 32);
        const neighbors = [
          [r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]
        ];
        neighbors.forEach(([nr, nc]) => {
          if (nr < 0 || nr >= (d.rows || 16) || nc < 0 || nc >= (d.cols || 32)) return;
          const nid = cells[nr * (d.cols || 32) + nc];
          if (nid && nid !== rid) {
            adjacency[rid] = adjacency[rid] || new Set();
            adjacency[rid].add(nid);
          }
        });
      }
      if (regionIds.some(rid => !adjacency[rid] || adjacency[rid].size === 0)) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'units') {
      if (isMapEmpty(key, design)) return 'N/A';
      const completeUnits = (d.rows || []).filter(u => isRowComplete(u, 'unit'));
      const partialUnits = (d.rows || []).filter(u => !isRowComplete(u, 'unit') && !isRowEmpty(u, blankUnit()));
      if (completeUnits.length === 0 && partialUnits.length === 0) return 'N/A';
      if (partialUnits.length > 0) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'tokens') {
      if (isMapEmpty(key, design)) return 'N/A';
      const allEmpty = (d.rows || []).every(r => isRowEmpty(r, blankMapRow('tokens.rows')));
      if (allEmpty) return 'N/A';
      const completeRows = (d.rows || []).filter(r => isRowComplete(r, 'tokens'));
      const nonEmptyRows = (d.rows || []).filter(r => !isRowEmpty(r, blankMapRow('tokens.rows')));
      if (completeRows.length === nonEmptyRows.length && completeRows.length > 0) return 'Complete';
      return 'Incomplete';
    }

    if (key === 'sb') {
      if (isMapEmpty(key, design)) return 'N/A';
      const reqRows = d.requirements && d.requirements.rows ? d.requirements.rows : [];
      const bookRows = d.books && d.books.rows ? d.books.rows : [];
      if (reqRows.length === 0 && bookRows.length === 0) return 'N/A';
      const reqComplete = reqRows.every(r => isRowComplete(r, 'mapSbRequirement'));
      const bookComplete = bookRows.every(r => isRowComplete(r, 'mapSbBook'));
      if (!reqComplete || !bookComplete) return 'Incomplete';
      return 'Complete';
    }

    if (key === 'glyphs') {
      if (isMapEmpty(key, design)) return 'N/A';
      const allEmpty = (d.rows || []).every(r => !r.name && !r.image && !r.desc);
      if (allEmpty) return 'N/A';
      const completeRows = (d.rows || []).filter(r => isRowComplete(r, 'mapGlyph'));
      const nonEmptyRows = (d.rows || []).filter(r => r.name || r.image || r.desc);
      if (completeRows.length === nonEmptyRows.length && completeRows.length > 0) return 'Complete';
      return 'Incomplete';
    }

    if (key === 'abilities') {
      if (isMapEmpty(key, design)) return 'N/A';
      const allEmpty = (d.rows || []).every(r => !r.name && !r.when && !r.type && !r.who && !r.text);
      if (allEmpty) return 'N/A';
      const completeRows = (d.rows || []).filter(r => isRowComplete(r, 'mapAbility'));
      const nonEmptyRows = (d.rows || []).filter(r => r.name || r.when || r.type || r.who || r.text);
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

  function mapBuildReady(design) {
    return MAP_BUILD_SECTIONS.every(key => {
      const s = mapStatus(key, design);
      return s === 'N/A' || s === 'Complete';
    });
  }

  // Returns field paths (e.g. 'units.rows.<id>.abilityName') that are blocking the section.
  // Returns [] when status is not 'Incomplete'.
  function missingFields(key, design) {
    const st = status(key, design);
    if (st !== 'Incomplete') return [];

    const missing = [];
    const d = design[key];

    if (key === 'ae') {
      if (!d.name) missing.push('ae.name');
      if (!d.acronym || d.acronym.length !== 1) missing.push('ae.acronym');
      const completeRows = d.rows.filter(r => isRowComplete(r, 'ae'));
      const partialRows = d.rows.filter(r => !isRowComplete(r, 'ae') && !isRowEmpty(r, blankRow('ae.rows')));
      // If no complete rows and no partial rows, flag first blank row's fields
      if (completeRows.length === 0 && partialRows.length === 0) {
        const firstBlank = d.rows.find(r => isRowEmpty(r, blankRow('ae.rows')));
        if (firstBlank) {
          missing.push(`ae.rows.${firstBlank.id}.sign`, `ae.rows.${firstBlank.id}.kind`);
          if (firstBlank.kind === 'fixed') {
            missing.push(`ae.rows.${firstBlank.id}.qty`, `ae.rows.${firstBlank.id}.desc`);
          } else {
            missing.push(`ae.rows.${firstBlank.id}.calc`, `ae.rows.${firstBlank.id}.desc`);
          }
        }
      }
      // Always flag partial rows
      partialRows.forEach(r => {
        if (!r.sign) missing.push(`ae.rows.${r.id}.sign`);
        if (!r.kind) missing.push(`ae.rows.${r.id}.kind`);
        if (r.kind === 'fixed') {
          if (r.qty == null) missing.push(`ae.rows.${r.id}.qty`);
        } else {
          if (!r.calc) missing.push(`ae.rows.${r.id}.calc`);
        }
        if (!r.desc) missing.push(`ae.rows.${r.id}.desc`);
      });
    }

    if (key === 'ufa') {
      if (!d.name) missing.push('ufa.name');
      if (!d.phase) missing.push('ufa.phase');
      if (!d.type) missing.push('ufa.type');
      if (!d.text) missing.push('ufa.text');
      if (d.hasCost && d.cost == null) missing.push('ufa.cost');
      if (d.hasEffect && d.effect == null) missing.push('ufa.effect');
    }

    if (key === 'setup') {
      if (!d.text) missing.push('setup.text');
      if (!d.location) missing.push('setup.location');
      if (d.location === 'single') {
        if (!d.earthRegion) missing.push('setup.earthRegion');
        if (!d.libraryRegion) missing.push('setup.libraryRegion');
      }
      if (d.location === 'multi' && !d.constraints.follows) missing.push('setup.constraints.follows');
      if (d.gate == null) missing.push('setup.gate');
      if (d.power == null) missing.push('setup.power');
      const completeUnits = d.units.filter(u => isRowComplete(u, 'setupUnit'));
      const partialUnits = d.units.filter(u => !isRowComplete(u, 'setupUnit') && !isRowEmpty(u, blankRow('setup.units')));
      // If no complete units and no partial units, flag first blank unit
      if (completeUnits.length === 0 && partialUnits.length === 0) {
        const firstBlank = d.units.find(u => isRowEmpty(u, blankRow('setup.units')));
        if (firstBlank) {
          missing.push(`setup.units.${firstBlank.id}.name`, `setup.units.${firstBlank.id}.qty`);
        }
      }
      // Always flag partial units
      partialUnits.forEach(u => {
        if (!u.name) missing.push(`setup.units.${u.id}.name`);
        if (u.qty == null) missing.push(`setup.units.${u.id}.qty`);
      });
      const aeEnabled = design.ae && design.ae.enabled;
      if (aeEnabled && d.aeStart == null) missing.push('setup.aeStart');
    }

    if (key === 'units') {
      const completeUnits = d.rows.filter(u => isRowComplete(u, 'unit'));
      const partialUnits = d.rows.filter(u => !isRowComplete(u, 'unit') && !isRowEmpty(u, blankUnit()));
      // If no complete units and no partial units, flag first blank unit's fields
      if (completeUnits.length === 0 && partialUnits.length === 0) {
        const firstBlank = d.rows.find(u => isRowEmpty(u, blankUnit()));
        if (firstBlank) {
          missing.push(`units.rows.${firstBlank.id}.type`, `units.rows.${firstBlank.id}.name`,
            `units.rows.${firstBlank.id}.silhouette`, `units.rows.${firstBlank.id}.qty`,
            `units.rows.${firstBlank.id}.costType`, `units.rows.${firstBlank.id}.combatType`);
        }
      }
      // Always flag partial units
      partialUnits.forEach(u => {
        if (!u.type) missing.push(`units.rows.${u.id}.type`);
        if (!u.name) missing.push(`units.rows.${u.id}.name`);
        if (!u.silhouette) missing.push(`units.rows.${u.id}.silhouette`);
        if (u.qty == null || u.qty < 1 || u.qty > 20) missing.push(`units.rows.${u.id}.qty`);
        if (!u.costType) missing.push(`units.rows.${u.id}.costType`);
        if (u.costType === 'Fixed' && u.cost == null) missing.push(`units.rows.${u.id}.cost`);
        if (u.costType === 'Variable' && !u.costCalc) missing.push(`units.rows.${u.id}.costCalc`);
        if (u.costType === 'Awakening') {
          if (!u.awakenReq) missing.push(`units.rows.${u.id}.awakenReq`);
          if (u.awakenPower == null) missing.push(`units.rows.${u.id}.awakenPower`);
          if (!u.awakenRegion) missing.push(`units.rows.${u.id}.awakenRegion`);
        }
        if (!u.combatType) missing.push(`units.rows.${u.id}.combatType`);
        if (u.combatType === 'Fixed Dice' && u.dice == null) missing.push(`units.rows.${u.id}.dice`);
        if (u.combatType === 'Variable Dice' && !u.diceCalc) missing.push(`units.rows.${u.id}.diceCalc`);
        if (u.combatType === 'Fixed Results') {
          if (u.pains == null) missing.push(`units.rows.${u.id}.pains`);
          if (u.kills == null) missing.push(`units.rows.${u.id}.kills`);
        }
        if (u.combatType === 'Variable Results' && !u.resultsCalc) missing.push(`units.rows.${u.id}.resultsCalc`);
        if (unitHasAbility(u)) {
          if (!u.abilityType) missing.push(`units.rows.${u.id}.abilityType`);
          if (!u.abilityText) missing.push(`units.rows.${u.id}.abilityText`);
        }
      });
    }

    if (key === 'sbr') {
      d.rows.forEach(row => {
        if (!row.text) missing.push(`sbr.rows.${row.id}.text`);
        if (row.hasNum && row.num == null) missing.push(`sbr.rows.${row.id}.num`);
      });
    }

    if (key === 'sb') {
      const done = r => isRowComplete(r, 'sb') && (!sbTwo(d, r) || isRowComplete(r, 'sbB'));
      const completeRows = d.rows.filter(done);
      const contentOnly = r => { const c = Object.assign({}, r); delete c.twoSided; return c; };
      const partialRows = d.rows.filter(r => !done(r) && !isRowEmpty(contentOnly(r), blankRow('sb.rows')));
      // If < 6 complete, flag blank rows up to 6
      if (completeRows.length < 6) {
        const blanks = d.rows.filter(r => isRowEmpty(contentOnly(r), blankRow('sb.rows')));
        const needed = Math.min(blanks.length, 6 - completeRows.length);
        for (let i = 0; i < needed; i++) {
          const r = blanks[i];
          missing.push(`sb.rows.${r.id}.name`, `sb.rows.${r.id}.type`, `sb.rows.${r.id}.text`);
        }
      }
      // Flag partial rows
      partialRows.forEach(r => {
        const sides = sbTwo(d, r) ? ['', 'B'] : [''];
        sides.forEach(side => {
          const parts = r['dual' + side] ? [side, side + '2'] : [side];
          parts.forEach(sfx => {
            if (!r['name' + sfx]) missing.push(`sb.rows.${r.id}.name${sfx}`);
            if (!r['type' + sfx]) missing.push(`sb.rows.${r.id}.type${sfx}`);
            if (!r['text' + sfx]) missing.push(`sb.rows.${r.id}.text${sfx}`);
            if (r['hasEffect' + sfx] && r['effect' + sfx] == null) missing.push(`sb.rows.${r.id}.effect${sfx}`);
          });
        });
      });
    }

    if (key === 'region') {
      const completeRows = d.rows.filter(r => isRowComplete(r, 'region'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('region.rows')));
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`region.rows.${r.id}.name`);
        if (!r.image) missing.push(`region.rows.${r.id}.image`);
        if (!r.restrictions) missing.push(`region.rows.${r.id}.restrictions`);
        if (!r.adjacency) missing.push(`region.rows.${r.id}.adjacency`);
      });
    }

    if (key === 'tokens') {
      const completeRows = d.rows.filter(r => isRowComplete(r, 'tokens'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('tokens.rows')));
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`tokens.rows.${r.id}.name`);
        if (r.qty == null) missing.push(`tokens.rows.${r.id}.qty`);
        if (!r.image) missing.push(`tokens.rows.${r.id}.image`);
        if (!r.placement) missing.push(`tokens.rows.${r.id}.placement`);
        if (!r.effects) missing.push(`tokens.rows.${r.id}.effects`);
        if (r.hasEffect && r.effect == null) missing.push(`tokens.rows.${r.id}.effect`);
      });
    }

    if (key === 'custom') {
      const completeRows = d.rows.filter(r => isRowComplete(r, 'custom'));
      const nonEmptyRows = d.rows.filter(r => !isRowEmpty(r, blankRow('custom.rows')));
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`custom.rows.${r.id}.name`);
        if (!r.placement) missing.push(`custom.rows.${r.id}.placement`);
        if (!r.usage) missing.push(`custom.rows.${r.id}.usage`);
        if (!r.effects) missing.push(`custom.rows.${r.id}.effects`);
        if (r.hasNum && r.num == null) missing.push(`custom.rows.${r.id}.num`);
      });
    }

    if (key === 'interactions') {
      const ancientSorceryRow = ((d && d.rows) || []).find(r =>
        r.otherFaction === 'Sleeper' &&
        r.abilityType === 'Spellbook' &&
        r.ability === 'Ancient Sorcery'
      );
      if (!ancientSorceryRow) {
        missing.push('interactions.rows');
      } else {
        if (!ancientSorceryRow.yourAbility) missing.push(`interactions.rows.${ancientSorceryRow.id}.yourAbility`);
        if (!ancientSorceryRow.interactionDesc) missing.push(`interactions.rows.${ancientSorceryRow.id}.interactionDesc`);
      }
    }

    return missing;
  }

  function missingMapFields(key, design) {
    const st = mapStatus(key, design);
    if (st !== 'Incomplete') return [];

    const missing = [];
    const d = design[key];

    if (key === 'images') {
      if (!d.items || d.items.length === 0) {
        missing.push('images.items');
      } else {
        d.items.forEach(item => {
          if (!item.image) missing.push(`images.items.${item.id}.image`);
        });
      }
      if (!d.regions || !d.regions.rows || d.regions.rows.length === 0) {
        missing.push('images.regions.rows');
      } else {
        d.regions.rows.forEach(r => {
          if (!r.name) missing.push(`images.regions.rows.${r.id}.name`);
        });
      }
    }

    if (key === 'bitmaps') {
      if (!d.items || d.items.length === 0) {
        missing.push('bitmaps.items');
      } else {
        d.items.forEach(item => {
          if (!item.image) missing.push(`bitmaps.items.${item.id}.image`);
        });
      }
      const regionIds = design.images && design.images.regions && design.images.regions.rows
        ? design.images.regions.rows.map(r => r.id) : [];
      const placed = new Set();
      d.items.forEach(item => {
        if (item.colors) {
          Object.values(item.colors).forEach(rid => placed.add(rid));
        }
      });
      regionIds.forEach(rid => {
        if (!placed.has(rid)) missing.push(`bitmaps.unplaced.${rid}`);
      });
    }

    if (key === 'adjacency') {
      const regionIds = design.images && design.images.regions && design.images.regions.rows
        ? design.images.regions.rows.map(r => r.id) : [];
      if (regionIds.length === 0) {
        missing.push('adjacency.grid');
      } else {
        const adjacency = {};
        const cells = d.cells || [];
        for (let i = 0; i < cells.length; i++) {
          const rid = cells[i];
          if (!rid) continue;
          const r = Math.floor(i / (d.cols || 32));
          const c = i % (d.cols || 32);
          const neighbors = [
            [r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]
          ];
          neighbors.forEach(([nr, nc]) => {
            if (nr < 0 || nr >= (d.rows || 16) || nc < 0 || nc >= (d.cols || 32)) return;
            const nid = cells[nr * (d.cols || 32) + nc];
            if (nid && nid !== rid) {
              adjacency[rid] = adjacency[rid] || new Set();
              adjacency[rid].add(nid);
            }
          });
        }
        regionIds.forEach(rid => {
          if (!adjacency[rid] || adjacency[rid].size === 0) {
            missing.push(`adjacency.region.${rid}`);
          }
        });
      }
    }

    if (key === 'units') {
      const partialUnits = (d.rows || []).filter(u => !isRowComplete(u, 'unit') && !isRowEmpty(u, blankUnit()));
      partialUnits.forEach(u => {
        if (!u.type) missing.push(`units.rows.${u.id}.type`);
        if (!u.name) missing.push(`units.rows.${u.id}.name`);
        if (!u.silhouette) missing.push(`units.rows.${u.id}.silhouette`);
        if (u.qty == null) missing.push(`units.rows.${u.id}.qty`);
        if (!u.costType) missing.push(`units.rows.${u.id}.costType`);
        if (!u.combatType) missing.push(`units.rows.${u.id}.combatType`);
        if (unitHasAbility(u) && !u.abilityText) missing.push(`units.rows.${u.id}.abilityText`);
      });
    }

    if (key === 'tokens') {
      const nonEmptyRows = (d.rows || []).filter(r => !isRowEmpty(r, blankMapRow('tokens.rows')));
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`tokens.rows.${r.id}.name`);
        if (r.qty == null) missing.push(`tokens.rows.${r.id}.qty`);
        if (!r.image) missing.push(`tokens.rows.${r.id}.image`);
        if (!r.placement) missing.push(`tokens.rows.${r.id}.placement`);
        if (!r.effects) missing.push(`tokens.rows.${r.id}.effects`);
        if (r.hasEffect && r.effect == null) missing.push(`tokens.rows.${r.id}.effect`);
      });
    }

    if (key === 'sb') {
      const reqRows = d.requirements && d.requirements.rows ? d.requirements.rows : [];
      const bookRows = d.books && d.books.rows ? d.books.rows : [];
      reqRows.forEach(r => {
        if (!r.text) missing.push(`sb.requirements.rows.${r.id}.text`);
        if (r.hasNum && r.num == null) missing.push(`sb.requirements.rows.${r.id}.num`);
      });
      bookRows.forEach(r => {
        if (!r.name) missing.push(`sb.books.rows.${r.id}.name`);
        if (!r.type) missing.push(`sb.books.rows.${r.id}.type`);
        if (!r.text) missing.push(`sb.books.rows.${r.id}.text`);
        if (r.hasEffect && r.effect == null) missing.push(`sb.books.rows.${r.id}.effect`);
      });
    }

    if (key === 'glyphs') {
      const nonEmptyRows = (d.rows || []).filter(r => r.name || r.image || r.desc);
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`glyphs.rows.${r.id}.name`);
        if (!r.image) missing.push(`glyphs.rows.${r.id}.image`);
        if (!r.desc) missing.push(`glyphs.rows.${r.id}.desc`);
      });
    }

    if (key === 'abilities') {
      const nonEmptyRows = (d.rows || []).filter(r => r.name || r.when || r.type || r.who || r.text);
      nonEmptyRows.forEach(r => {
        if (!r.name) missing.push(`abilities.rows.${r.id}.name`);
        if (!r.when) missing.push(`abilities.rows.${r.id}.when`);
        if (!r.type) missing.push(`abilities.rows.${r.id}.type`);
        if (!r.who) missing.push(`abilities.rows.${r.id}.who`);
        if (!r.text) missing.push(`abilities.rows.${r.id}.text`);
      });
    }

    return missing;
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
          name: 'UFA',
          value: design.ufa.cost
        });
      }
      if (design.ufa.hasEffect && design.ufa.effect != null) {
        numbers.push({
          section: 'ufa',
          sectionTitle: 'Unique Faction Ability',
          rowId: null,
          field: 'effect',
          name: 'UFA',
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
          name: 'Faction Setup',
          value: design.setup.power
        });
      }
      if (design.ae && design.ae.enabled && design.setup.aeStart != null) {
        numbers.push({
          section: 'setup',
          sectionTitle: 'Setup',
          rowId: null,
          field: 'aeStart',
          name: design.ae.name || 'AE',
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
            name: u.name,
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
            name: u.name,
            value: u.qty
          });
        }
        if (u.costType === 'Fixed' && u.cost != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'cost',
            name: u.name,
            value: u.cost
          });
        }
        if (u.costType === 'Awakening' && u.awakenPower != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'awakenPower',
            name: u.name,
            value: u.awakenPower
          });
        }
        if (u.combatType === 'Fixed Dice' && u.dice != null && u.name) {
          numbers.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'dice',
            name: u.name,
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
              name: u.name,
              value: u.pains
            });
          }
          if (u.kills != null) {
            numbers.push({
              section: 'units',
              sectionTitle: 'Units',
              rowId: u.id,
              field: 'kills',
              name: u.name,
              value: u.kills
            });
          }
        }
      });
    }

    if (design.sbr) {
      design.sbr.rows.forEach((row, idx) => {
        if (row.hasNum && row.num != null) {
          numbers.push({
            section: 'sbr',
            sectionTitle: 'Spellbook Requirements',
            rowId: row.id,
            field: 'num',
            name: 'SBR ' + (idx + 1),
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
            name: row.name,
            value: row.cost
          });
        }
        if (row.hasEffect && row.effect != null && row.name) {
          numbers.push({
            section: 'sb',
            sectionTitle: 'Spellbooks',
            rowId: row.id,
            field: 'effect',
            name: row.name,
            value: row.effect
          });
        }
        // Extra parts: power 2 of a dual powers side, and side B (and its power 2) of a 2 sided spellbook
        const extra = [];
        if (row.dual) extra.push(['2', ' (power 2)']);
        if (sbTwo(design.sb, row)) {
          extra.push(['B', ' (side B)']);
          if (row.dualB) extra.push(['B2', ' (side B, power 2)']);
        }
        extra.forEach(([sfx, tag]) => {
          const nm = row['name' + sfx];
          if (!nm) return;
          if (row['cost' + sfx] != null) {
            numbers.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'cost' + sfx, name: nm + tag, value: row['cost' + sfx]});
          }
          if (row['hasEffect' + sfx] && row['effect' + sfx] != null) {
            numbers.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'effect' + sfx, name: nm + tag, value: row['effect' + sfx]});
          }
        });
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
            name: row.name,
            value: row.qty
          });
        }
        if (row.hasEffect && row.effect != null && row.name) {
          numbers.push({
            section: 'tokens',
            sectionTitle: 'Tokens',
            rowId: row.id,
            field: 'effect',
            name: row.name,
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
            name: row.name,
            value: row.num
          });
        }
      });
    }

    return numbers;
  }

  // Hard-coded text elements that a non-coder can push straight into the live build, mirroring
  // fixedNumbers() above but for text strings (unit names, SB names/text, SBR text, UFA name/text).
  // Used by the Simple Update screen's "Fixed Text" table in app.js.
  function fixedText(design) {
    const texts = [];

    if (design.units) {
      design.units.rows.forEach(u => {
        if (u.name) {
          texts.push({
            section: 'units',
            sectionTitle: 'Units',
            rowId: u.id,
            field: 'name',
            name: u.name,
            value: u.name
          });
        }
      });
    }

    if (design.ufa) {
      if (design.ufa.name) {
        texts.push({
          section: 'ufa',
          sectionTitle: 'Unique Faction Ability',
          rowId: null,
          field: 'name',
          name: 'UFA Name',
          value: design.ufa.name
        });
      }
      if (design.ufa.text) {
        texts.push({
          section: 'ufa',
          sectionTitle: 'Unique Faction Ability',
          rowId: null,
          field: 'text',
          name: 'UFA Text',
          value: design.ufa.text
        });
      }
    }

    if (design.sbr) {
      design.sbr.rows.forEach((row, idx) => {
        const n = idx + 1;
        if (row.text) {
          texts.push({
            section: 'sbr',
            sectionTitle: 'Spellbook Requirements',
            rowId: row.id,
            field: 'text',
            name: 'SBR ' + n + ' (full)',
            value: row.text
          });
        }
        if (row.shortText) {
          texts.push({
            section: 'sbr',
            sectionTitle: 'Spellbook Requirements',
            rowId: row.id,
            field: 'shortText',
            name: 'SBR ' + n + ' (abbreviated)',
            value: row.shortText
          });
        }
      });
    }

    if (design.sb) {
      design.sb.rows.forEach(row => {
        if (row.name) {
          texts.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'name', name: row.name + ' (card name)', value: row.name});
        }
        if (row.text) {
          texts.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'text', name: (row.name || 'Spellbook') + ' (full text)', value: row.text});
        }
        // Extra parts: power 2 of a dual powers side, and side B (and its power 2) of a 2 sided spellbook
        // (same extra/sfx pattern as fixedNumbers' SB block above, so dual/2-sided spellbooks aren't missed)
        const extra = [];
        if (row.dual) extra.push(['2', ' (power 2)']);
        if (sbTwo(design.sb, row)) {
          extra.push(['B', ' (side B)']);
          if (row.dualB) extra.push(['B2', ' (side B, power 2)']);
        }
        extra.forEach(([sfx, tag]) => {
          const nm = row['name' + sfx];
          const txt = row['text' + sfx];
          if (nm) {
            texts.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'name' + sfx, name: nm + tag + ' (card name)', value: nm});
          }
          if (txt) {
            texts.push({section: 'sb', sectionTitle: 'Spellbooks', rowId: row.id, field: 'text' + sfx, name: (nm || row.name || 'Spellbook') + tag + ' (full text)', value: txt});
          }
        });
      });
    }

    return texts;
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
      // 2 sided changes: all at once ("All 2 sided") or one spellbook at a time
      const flipped = neu.rows.filter(r => {
        const o = old.rows.find(x => x.id === r.id);
        return o && sbTwo(old, o) !== sbTwo(neu, r);
      });
      if (flipped.length && flipped.length === neu.rows.length && new Set(flipped.map(r => sbTwo(neu, r))).size === 1) {
        parts.push(sbTwo(neu, flipped[0]) ? 'spellbooks made 2 sided' : 'spellbooks made 1 sided');
      } else {
        flipped.forEach(r => parts.push('spellbook "' + (r.name || 'unnamed') + '" made ' + (sbTwo(neu, r) ? '2 sided' : '1 sided')));
      }
      added.forEach(n => parts.push('new spellbook "' + n + '"'));
      removed.forEach(n => parts.push('removed spellbook "' + n + '"'));
      newSbs.forEach(name => {
        const oldS = old.rows.find(s => s.name === name);
        const newS = neu.rows.find(s => s.name === name);
        const noSide = r => { const c = Object.assign({}, r); delete c.twoSided; return c; };  // reported above
        if (oldS && newS && !eq(noSide(oldS), noSide(newS))) {
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

  function computeSpellbookGuidance(design) {
    const d = design.sb || {};
    const hasMultiPower = (d.rows || []).some(r => {
      const sides = sbTwo(d, r) ? ['', 'B'] : [''];
      return sides.some(sd => r['dual' + sd]);
    });
    const hasMultiSided = sbAnyTwo(d);

    if (!hasMultiPower && !hasMultiSided) return '';

    let guidance = '';

    if (hasMultiPower) {
      guidance += 'MULTI-POWER SPELLBOOKS:\n';
      guidance += '- Spellbooks with multiple powers on 1 side are a single spellbook\n';
      guidance += '- Completing a single SBR can earn you a SB with 2 powers—still ONE spellbook\n';
      guidance += '- Both powers are earned/blocked/copied together\n';
      guidance += '- Max 6 SBR/SB slots on faction card (unless explicitly told otherwise)\n';
      guidance += '- Spellbook overlays must describe BOTH powers\n';
      guidance += '- Moonbeast blocking a 2-power spellbook blocks BOTH powers\n';
    }

    if (hasMultiSided) {
      if (hasMultiPower) guidance += '\n';
      guidance += 'MULTI-SIDED SPELLBOOKS:\n';
      guidance += '- 2 sides with powers = 2 connected spellbooks, not 2 independent ones\n';
      guidance += '- Sides are swapped per that spellbook\'s rules, not taken independently\n';
      guidance += '- "Face down" sides: use Dragon Ascending (one-time) or Daemon Sultans (Doom Phase recharge) as templates\n';
      guidance += '- A 3rd "face down" side: use as one-time block OR determine recharge rules (Side A or B)\n';
    }

    return guidance;
  }

  window.Rules = {
    SECTIONS,
    BUILD_SECTIONS,
    MAP_SECTIONS,
    MAP_BUILD_SECTIONS,
    MAP_ABILITY_PHASES,
    MAP_ABILITY_TYPES,
    NEUTRAL_UNIT_TYPES,
    ABILITY_TYPES,
    SB_TYPES,
    UNIT_TYPES,
    COST_TYPES,
    COMBAT_TYPES,
    newDesign,
    backfillDesign,
    newMapDesign,
    blankRow,
    blankMapRow,
    isEmpty,
    isMapEmpty,
    status,
    mapStatus,
    buildReady,
    mapBuildReady,
    missingFields,
    missingMapFields,
    fixedNumbers,
    fixedText,
    sbTwo,
    sbAnyTwo,
    unitHasAbility,
    describeSectionDiff,
    computeSpellbookGuidance,
    newId
  };
})();
