// Development stub for rules.js
(function() {
  'use strict';

  const SB_TYPES = ['Ongoing', 'Action', 'Unlimited Action', 'Pre-Battle', 'Battle', 'Post-Battle', 'Movement', 'Gather Power Phase', 'Doom Phase', 'Once Only'];

  function newId() {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let id = '';
    for (let i = 0; i < 8; i++) {
      id += chars[Math.floor(Math.random() * chars.length)];
    }
    return id;
  }

  window.Rules = {
    SECTIONS: [
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
    ],

    BUILD_SECTIONS: ['ae', 'ufa', 'setup', 'units', 'sbr', 'sb', 'region', 'tokens', 'custom'],

    newDesign() {
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
          name: '', phase: null, type: null, hasCost: false, cost: null,
          hasEffect: false, effect: null, text: ''
        },
        setup: {
          text: '', location: null, earthRegion: null, libraryRegion: null,
          constraints: {
            follows: null, water: true, land: true, emptyFactionGlyph: true,
            thorn: true, dragon: true, chevron: true, noneOf3: true,
            proximity: 'N/A', custom: ''
          },
          gate: null,
          units: [{id: newId(), onMap: true, name: '', qty: null}],
          power: 8, aeStart: 0
        },
        units: {
          rows: [
            this.blankRow('units.rows'),
            this.blankRow('units.rows'),
            this.blankRow('units.rows')
          ]
        },
        sbr: {
          multiText: '',
          rows: Array(6).fill(0).map(() => ({id: newId(), text: '', hasNum: false, num: null}))
        },
        sb: {
          rows: Array(6).fill(0).map(() => ({
            id: newId(), name: '', type: null, cost: 0,
            hasEffect: false, effect: null, text: ''
          }))
        },
        region: {
          rows: [{id: newId(), name: '', image: null, restrictions: '', adjacency: ''}]
        },
        tokens: {
          rows: [{id: newId(), name: '', qty: null, image: null, placement: '', effects: '', hasEffect: false, effect: null}]
        },
        custom: {
          rows: [{id: newId(), name: '', image: null, placement: '', usage: '', effects: '', hasNum: false, num: null}]
        },
        menus: {
          rows: [{
            id: newId(), name: '', section: null, item: null, prompted: null,
            title: '', hasSubtitle: false, subtitle: '', button: '',
            cancel: false, skip: false, leadsToNext: false, next: null, nextTrigger: ''
          }]
        }
      };
    },

    blankRow(tablePath) {
      if (tablePath === 'units.rows') {
        return {
          id: newId(), type: null, name: '', mapImage: null, mapScale: 1.0,
          silhouette: null, qty: null, costType: null, cost: null, costCalc: '',
          awakenReq: '', awakenPower: null, awakenRegion: '', combatType: null,
          dice: null, diceCalc: '', pains: null, kills: null, resultsCalc: '',
          relatedSb: [], relatedSbNames: [], abilityName: '', abilityText: ''
        };
      }
      if (tablePath === 'ae.rows') {
        return {id: newId(), sign: '+', kind: 'fixed', qty: null, calc: '', desc: ''};
      }
      if (tablePath === 'setup.units') {
        return {id: newId(), onMap: true, name: '', qty: null};
      }
      if (tablePath === 'sbr.rows') {
        return {id: newId(), text: '', hasNum: false, num: null};
      }
      if (tablePath === 'sb.rows') {
        return {id: newId(), name: '', type: null, cost: 0, hasEffect: false, effect: null, text: ''};
      }
      if (tablePath === 'region.rows') {
        return {id: newId(), name: '', image: null, restrictions: '', adjacency: ''};
      }
      if (tablePath === 'tokens.rows') {
        return {id: newId(), name: '', qty: null, image: null, placement: '', effects: '', hasEffect: false, effect: null};
      }
      if (tablePath === 'custom.rows') {
        return {id: newId(), name: '', image: null, placement: '', usage: '', effects: '', hasNum: false, num: null};
      }
      if (tablePath === 'menus.rows') {
        return {
          id: newId(), name: '', section: null, item: null, prompted: null,
          title: '', hasSubtitle: false, subtitle: '', button: '',
          cancel: false, skip: false, leadsToNext: false, next: null, nextTrigger: ''
        };
      }
      return {id: newId()};
    },

    isEmpty(key, design) {
      const d = design[key];
      if (!d) return true;

      if (key === 'ae') {
        if (!d.enabled) return true;
        if (d.name || d.acronym) return false;
        return !d.rows.some(r => r.sign !== '+' || r.kind !== 'fixed' || r.qty !== null || r.calc || r.desc);
      }
      if (key === 'ufa') {
        return !d.name && !d.phase && !d.type && !d.text && !d.hasCost && !d.hasEffect;
      }
      if (key === 'setup') {
        return !d.text && !d.location && !d.earthRegion && !d.libraryRegion && !d.gate &&
               d.power === 8 && d.aeStart === 0 &&
               !d.units.some(u => u.onMap !== true || u.name || u.qty !== null);
      }
      if (key === 'units') {
        return !d.rows.some(r => r.type || r.name || r.silhouette || r.qty !== null);
      }
      if (key === 'sbr') {
        return !d.multiText && !d.rows.some(r => r.text || r.hasNum || r.num !== null);
      }
      if (key === 'sb') {
        return !d.rows.some(r => r.name || r.type || r.cost !== 0 || r.hasEffect || r.text);
      }
      if (key === 'region') {
        return !d.rows.some(r => r.name || r.image || r.restrictions || r.adjacency);
      }
      if (key === 'tokens') {
        return !d.rows.some(r => r.name || r.qty !== null || r.image || r.placement || r.effects || r.hasEffect);
      }
      if (key === 'custom') {
        return !d.rows.some(r => r.name || r.image || r.placement || r.usage || r.effects || r.hasNum);
      }
      if (key === 'menus') {
        return !d.rows.some(r => r.name || r.section || r.prompted || r.title || r.button);
      }
      return true;
    },

    status(key, design) {
      if (['ae', 'region', 'tokens', 'custom'].includes(key)) {
        if (this.isEmpty(key, design)) return 'N/A';
        const d = design[key];
        if (key === 'ae' && !d.enabled) return 'N/A';
        // Simplified completeness check
        return 'Complete';
      }
      if (key === 'ufa') {
        const d = design.ufa;
        if (!d.name || !d.phase || !d.type || !d.text) return 'Incomplete';
        if (d.hasCost && d.cost === null) return 'Incomplete';
        if (d.hasEffect && d.effect === null) return 'Incomplete';
        return 'Complete';
      }
      if (key === 'setup') {
        const d = design.setup;
        if (!d.text || !d.location || d.gate === null) return 'Incomplete';
        if (d.location === 'single' && (!d.earthRegion || !d.libraryRegion)) return 'Incomplete';
        if (d.location === 'multi' && !d.constraints.follows) return 'Incomplete';
        if (d.power === null) return 'Incomplete';
        if (design.ae.enabled && d.aeStart === null) return 'Incomplete';
        if (!d.units.some(u => u.name && u.qty !== null)) return 'Incomplete';
        return 'Complete';
      }
      if (key === 'units') {
        const d = design.units;
        if (!d.rows.some(r => r.type && r.name)) return 'Incomplete';
        return 'Complete';
      }
      if (key === 'sbr') {
        const d = design.sbr;
        if (!d.rows.every(r => r.text && (!r.hasNum || r.num !== null))) return 'Incomplete';
        return 'Complete';
      }
      if (key === 'sb') {
        const d = design.sb;
        const complete = d.rows.filter(r => r.name && r.type && r.text && (!r.hasEffect || r.effect !== null));
        if (complete.length < 6) return 'Incomplete';
        return 'Complete';
      }
      return 'Incomplete';
    },

    buildReady(design) {
      return this.BUILD_SECTIONS.every(key => {
        const st = this.status(key, design);
        return st === 'N/A' || st === 'Complete';
      });
    },

    fixedNumbers(design) {
      const nums = [];
      // Simplified - just return empty for stub
      return nums;
    },

    describeSectionDiff(key, oldDesign, newDesign) {
      // Simplified stub
      if (JSON.stringify(oldDesign[key]) === JSON.stringify(newDesign[key])) return '';
      return 'Section changed';
    },

    newId
  };
})();
