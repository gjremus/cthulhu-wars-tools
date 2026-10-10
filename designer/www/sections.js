(function() {
  'use strict';

  let cssInjected = false;

  function injectCSS() {
    if (cssInjected) return;
    cssInjected = true;
    const style = document.createElement('style');
    style.id = 'sections-css';
    style.textContent = `
      .sx-field { margin: 12px 0; }
      .sx-field label { display: block; font-weight: bold; margin-bottom: 4px; }
      .sx-field input[type="text"], .sx-field input[type="number"], .sx-field textarea, .sx-field select {
        width: 100%;
        max-width: 600px;
        padding: 6px;
        border: 1px solid #888;
        background: #222;
        color: #eee;
        font-family: inherit;
        font-size: 14px;
      }
      .sx-field textarea { min-height: 80px; resize: vertical; }
      .sx-field input[type="checkbox"] { width: auto; margin-right: 8px; }
      .sx-field.sx-greyed { opacity: 0.4; pointer-events: none; }

      .sx-table { border-collapse: collapse; margin: 16px 0; overflow-x: auto; display: block; }
      .sx-table table { border: 2px solid #000; width: 100%; min-width: 800px; }
      .sx-table th, .sx-table td { border: 1px solid #000; padding: 8px; text-align: left; vertical-align: top; }
      .sx-table th { background: #333; font-weight: bold; }
      .sx-table input, .sx-table select, .sx-table textarea {
        width: 100%;
        box-sizing: border-box;
        padding: 4px;
        border: 1px solid #666;
        background: #222;
        color: #eee;
        font-size: 13px;
      }
      .sx-table textarea { min-height: 50px; resize: vertical; }
      .sx-table button { padding: 4px 12px; margin: 2px; cursor: pointer; }

      .sx-btn { padding: 8px 16px; margin: 8px 8px 8px 0; cursor: pointer; background: #444; color: #eee; border: 1px solid #666; }
      .sx-btn:hover { background: #555; }

      .sx-img-thumb {
        width: 80px;
        height: 80px;
        border: 1px solid #666;
        display: inline-block;
        background: #111;
        cursor: pointer;
        object-fit: contain;
      }
      .sx-img-thumb.sx-empty { background: #333; }

      .sx-inline { display: inline-block; margin-right: 16px; }
      .sx-hint { font-size: 12px; color: #aaa; margin-left: 8px; cursor: help; }

      .sx-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0,0,0,0.9);
        z-index: 10000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
      }
      .sx-overlay-content {
        max-width: 95vw;
        max-height: 95vh;
        overflow: auto;
        background: #111;
        padding: 20px;
        border: 2px solid #666;
      }
      .sx-overlay-buttons {
        position: absolute;
        top: 20px;
        left: 20px;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        z-index: 10001;
      }
      .sx-overlay canvas { border: 1px solid #666; }

      .sx-menu-preview {
        background: #1a1a1a;
        border: 2px solid #666;
        padding: 20px;
        max-width: 500px;
        margin: 20px 0;
        font-family: 'Bohemian Typewriter', monospace;
      }
      .sx-menu-preview-title {
        font-size: 20px;
        font-weight: bold;
        margin-bottom: 16px;
        text-align: center;
      }
      .sx-menu-preview-option {
        padding: 8px;
        margin: 4px 0;
        cursor: pointer;
        border-left: 3px solid transparent;
      }
      .sx-menu-preview-option:hover {
        background: #333;
      }
      .sx-menu-preview-buttons {
        display: flex;
        gap: 8px;
        margin-top: 16px;
        justify-content: center;
      }
      .sx-menu-preview-btn {
        padding: 8px 16px;
        background: #444;
        border: 1px solid #666;
        cursor: pointer;
      }
    `;
    document.head.appendChild(style);
  }

  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (let k in attrs) {
        if (k === 'className') el.className = attrs[k];
        else if (k.startsWith('on')) el[k] = attrs[k];
        // As properties: setAttribute('checked', false) would still tick the box
        else if (k === 'checked' || k === 'disabled' || k === 'selected' || k === 'value') el[k] = attrs[k];
        else el.setAttribute(k, attrs[k]);
      }
    }
    children.flat(Infinity).forEach(child => {
      if (child == null || child === false) return;
      if (typeof child === 'string' || typeof child === 'number') {
        el.appendChild(document.createTextNode(child));
      } else {
        el.appendChild(child);
      }
    });
    // A select's value only sticks once its options exist
    if (tag === 'select' && attrs && 'value' in attrs) el.value = attrs.value;
    return el;
  }

  function textField(label, value, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const hint = opts.hint || '';
    const rows = opts.rows || null;

    const input = rows
      ? h('textarea', {value: value || '', oninput: e => onChange(e.target.value), rows})
      : h('input', {type: 'text', value: value || '', oninput: e => onChange(e.target.value)});

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label, hint ? h('span', {className: 'sx-hint', title: hint}, 'ⓘ') : null),
      input
    );
  }

  function numberField(label, value, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const min = opts.min != null ? opts.min : null;
    const max = opts.max != null ? opts.max : null;

    const attrs = {
      type: 'number',
      value: value != null ? value : '',
      oninput: e => onChange(e.target.value ? parseInt(e.target.value) : null),
      inputmode: 'numeric'
    };
    if (min != null) attrs.min = min;
    if (max != null) attrs.max = max;

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label),
      h('input', attrs)
    );
  }

  function selectField(label, value, options, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const placeholder = opts.placeholder || '';

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label),
      h('select', {value: value || '', onchange: e => onChange(e.target.value || null)},
        h('option', {value: ''}, placeholder || '-- Select --'),
        options.map(opt => {
          const val = typeof opt === 'string' ? opt : opt.value;
          const label = typeof opt === 'string' ? opt : opt.label;
          return h('option', {value: val}, label);
        })
      )
    );
  }

  function checkboxField(label, checked, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {},
        h('input', {type: 'checkbox', checked, onchange: e => onChange(e.target.checked)}),
        label
      )
    );
  }

  function imageField(label, imageId, ctx, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const size = opts.size || 'small';

    const thumbClass = 'sx-img-thumb' + (imageId ? '' : ' sx-empty');
    const thumb = imageId
      ? h('img', {src: ctx.imgUrl(imageId), className: thumbClass, onclick: () => openImageEditor(imageId, ctx, onChange, size)})
      : h('div', {className: thumbClass, onclick: async () => {
          const id = await ctx.uploadImage(size);
          if (id) onChange(id);
        }}, 'Click to upload');

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label),
      thumb
    );
  }

  function openImageEditor(imageId, ctx, onChange, size) {
    const content = h('div', {},
      h('div', {style: 'margin-bottom: 16px;'},
        h('button', {className: 'sx-btn', onclick: async () => {
          const id = await ctx.uploadImage(size);
          if (id) {
            onChange(id);
            ctx.closeOverlay();
          }
        }}, 'Replace'),
        h('button', {className: 'sx-btn', onclick: () => ctx.closeOverlay()}, 'Done')
      ),
      h('img', {src: ctx.imgUrl(imageId), style: 'max-width: 100%; max-height: 70vh; border: 1px solid #666;'})
    );
    ctx.openOverlay(content);
  }

  // Section renderers

  function renderAE(container, ctx) {
    const d = ctx.design.ae;

    container.appendChild(checkboxField('Alternate resource economy', d.enabled, val => {
      ctx.set('ae.enabled', val);
    }));

    const greyed = !d.enabled;

    container.appendChild(textField('Name', d.name, val => ctx.set('ae.name', val), {greyed}));
    container.appendChild(textField('Acronym (single letter)', d.acronym, val => ctx.set('ae.acronym', val.substring(0, 1)), {greyed}));

    const tableDiv = h('div', {className: 'sx-table' + (greyed ? ' sx-greyed' : '')});
    const table = h('table', {});
    const thead = h('thead', {},
      h('tr', {},
        h('th', {}, '+/-'),
        h('th', {}, 'Fixed/Var'),
        h('th', {}, 'Qty'),
        h('th', {}, 'Calc'),
        h('th', {}, 'Description'),
        h('th', {}, '')
      )
    );
    table.appendChild(thead);

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('button', {onclick: () => {
          ctx.set(`ae.rows.${row.id}.sign`, row.sign === '+' ? '-' : '+');
        }}, row.sign)
      ));

      tr.appendChild(h('td', {},
        h('select', {value: row.kind, onchange: e => ctx.set(`ae.rows.${row.id}.kind`, e.target.value)},
          h('option', {value: 'fixed'}, 'Fixed'),
          h('option', {value: 'variable'}, 'Variable')
        )
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: row.qty != null ? row.qty : '',
          disabled: row.kind === 'variable',
          oninput: e => ctx.set(`ae.rows.${row.id}.qty`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'text',
          value: row.calc || '',
          disabled: row.kind === 'fixed',
          oninput: e => ctx.set(`ae.rows.${row.id}.calc`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          value: row.desc || '',
          rows: 2,
          oninput: e => ctx.set(`ae.rows.${row.id}.desc`, e.target.value)
        })
      ));

      if (idx > 0) {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) {
              ctx.deleteRow('ae.rows', row.id);
            }
          }}, 'Delete')
        ));
      } else {
        tr.appendChild(h('td', {}));
      }

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);

    container.appendChild(tableDiv);

    if (!greyed) {
      container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
        const newRow = window.Rules.blankRow('ae.rows');
        ctx.addRow('ae.rows', newRow);
      }}, 'Add row'));
    }
  }

  function renderUFA(container, ctx) {
    const d = ctx.design.ufa;

    container.appendChild(textField('Name', d.name, val => ctx.set('ufa.name', val)));

    container.appendChild(selectField('Phase', d.phase, [
      'Setup', 'Action', 'Gather Power', 'Player Order', 'Doom'
    ], val => ctx.set('ufa.phase', val)));

    container.appendChild(selectField('Type', d.type, window.Rules.SB_TYPES, val => ctx.set('ufa.type', val)));

    container.appendChild(checkboxField('Includes Fixed Numeric Cost?', d.hasCost, val => ctx.set('ufa.hasCost', val)));
    container.appendChild(numberField('Fixed Numeric Cost', d.cost, val => ctx.set('ufa.cost', val), {greyed: !d.hasCost, min: 0}));

    container.appendChild(checkboxField('Includes Fixed Numeric Effect?', d.hasEffect, val => ctx.set('ufa.hasEffect', val)));
    container.appendChild(numberField('Fixed Numeric Effect', d.effect, val => ctx.set('ufa.effect', val), {greyed: !d.hasEffect, min: 0}));

    const textLen = 200;
    container.appendChild(textField('Text', d.text, val => ctx.set('ufa.text', val), {rows: Math.max(3, Math.ceil(textLen / 45))}));
  }

  function renderSetup(container, ctx) {
    const d = ctx.design.setup;
    const ref = ctx.reference || {};

    container.appendChild(textField('Text for faction card', d.text, val => ctx.set('setup.text', val), {rows: 4}));

    container.appendChild(selectField('Location type', d.location, ['single', 'multi'], val => {
      ctx.set('setup.location', val);
    }, {placeholder: '-- Select --'}));

    const isSingle = d.location === 'single';
    const isMulti = d.location === 'multi';

    container.appendChild(selectField('Earth Region', d.earthRegion, ref.earth33Regions || [], val => ctx.set('setup.earthRegion', val), {
      greyed: !isSingle
    }));

    container.appendChild(selectField('Library Region', d.libraryRegion, ref.library33Regions || [], val => ctx.set('setup.libraryRegion', val), {
      greyed: !isSingle
    }));

    const constraintsDiv = h('div', {style: isMulti ? '' : 'opacity: 0.4; pointer-events: none;'});
    constraintsDiv.appendChild(h('h3', {}, 'Constraints'));

    // Doc: leave out factions with pre-set start regions; start with the first one that has a choice
    const fixedNames = new Set((ref.fixedStartFactions || []).map(f => f.name));
    const placementOrder = (ref.placementOrder || []).filter(f => !fixedNames.has(f.name));
    const followsOptions = [{value: '0', label: '0. Base Factions'}]
      .concat(placementOrder.map((f, i) => ({value: String(i + 1), label: `${i + 1}. ${f.name}`})));
    constraintsDiv.appendChild(selectField('Follows faction', d.constraints.follows, followsOptions, val => ctx.set('setup.constraints.follows', val), {
      placeholder: '-- Select --'
    }));

    constraintsDiv.appendChild(checkboxField('Water', d.constraints.water, val => ctx.set('setup.constraints.water', val)));
    constraintsDiv.appendChild(checkboxField('Land', d.constraints.land, val => ctx.set('setup.constraints.land', val)));
    constraintsDiv.appendChild(checkboxField('Empty regions with faction glyphs', d.constraints.emptyFactionGlyph, val => ctx.set('setup.constraints.emptyFactionGlyph', val)));

    const glyphs = ref.glyphs || [];
    const thorn = glyphs.find(g => g.nickname === 'Thorn');
    const dragon = glyphs.find(g => g.nickname === 'Dragon');
    const chevron = glyphs.find(g => g.nickname === 'Chevron');

    constraintsDiv.appendChild(checkboxField((thorn ? thorn.unicodeSuggestion + ' ' : '') + 'Thorn glyph', d.constraints.thorn, val => ctx.set('setup.constraints.thorn', val)));
    constraintsDiv.appendChild(checkboxField((dragon ? dragon.unicodeSuggestion + ' ' : '') + 'Dragon glyph', d.constraints.dragon, val => ctx.set('setup.constraints.dragon', val)));
    constraintsDiv.appendChild(checkboxField((chevron ? chevron.unicodeSuggestion + ' ' : '') + 'Chevron glyph', d.constraints.chevron, val => ctx.set('setup.constraints.chevron', val)));
    constraintsDiv.appendChild(checkboxField('None of 3 ' + [thorn, dragon, chevron].filter(Boolean).map(g => g.unicodeSuggestion).join('/') + ' glyphs', d.constraints.noneOf3, val => ctx.set('setup.constraints.noneOf3', val)));

    constraintsDiv.appendChild(selectField('Proximity to other factions', d.constraints.proximity, ['adjacent', 'as far as possible', 'N/A'], val => ctx.set('setup.constraints.proximity', val)));

    constraintsDiv.appendChild(textField('Custom', d.constraints.custom, val => ctx.set('setup.constraints.custom', val), {rows: 2}));

    container.appendChild(constraintsDiv);

    container.appendChild(h('div', {className: 'sx-field'},
      h('label', {}, 'Gate'),
      h('label', {},
        h('input', {type: 'radio', name: 'gate', checked: d.gate === true, onchange: () => ctx.set('setup.gate', true)}),
        ' Yes'
      ),
      h('label', {style: 'margin-left: 16px;'},
        h('input', {type: 'radio', name: 'gate', checked: d.gate === false, onchange: () => ctx.set('setup.gate', false)}),
        ' No'
      )
    ));

    const unitsDiv = h('div', {className: 'sx-table'});
    const unitsTable = h('table', {});
    unitsTable.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'On map'),
        h('th', {}, 'Name'),
        h('th', {}, 'Qty'),
        h('th', {}, '')
      )
    ));

    const unitsTbody = h('tbody', {});
    d.units.forEach((unit, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: unit.onMap, onchange: e => ctx.set(`setup.units.${unit.id}.onMap`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'text', value: unit.name || '', oninput: e => ctx.set(`setup.units.${unit.id}.name`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'number', value: unit.qty != null ? unit.qty : '', oninput: e => ctx.set(`setup.units.${unit.id}.qty`, e.target.value ? parseInt(e.target.value) : null)})
      ));

      if (idx > 0) {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this unit?', 'Yes - delete', 'No - cancel');
            if (confirmed) ctx.deleteRow('setup.units', unit.id);
          }}, 'Delete')
        ));
      } else {
        tr.appendChild(h('td', {}));
      }

      unitsTbody.appendChild(tr);
    });
    unitsTable.appendChild(unitsTbody);
    unitsDiv.appendChild(unitsTable);
    container.appendChild(unitsDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newUnit = window.Rules.blankRow('setup.units');
      ctx.addRow('setup.units', newUnit);
    }}, 'Add unit'));

    container.appendChild(numberField('Starting power', d.power, val => ctx.set('setup.power', val), {min: 0}));

    const aeEnabled = ctx.design.ae && ctx.design.ae.enabled;
    const aeName = aeEnabled && ctx.design.ae.name ? ctx.design.ae.name : 'alternate economy';
    container.appendChild(numberField('Starting ' + aeName, d.aeStart, val => ctx.set('setup.aeStart', val), {greyed: !aeEnabled, min: 0}));
  }

  function renderUnits(container, ctx) {
    const d = ctx.design.units;
    const ref = ctx.reference || {};
    const sbRows = ctx.design.sb ? ctx.design.sb.rows : [];
    const sbStatus = window.Rules.status('sb', ctx.design);

    d.rows.forEach((unit, idx) => {
      const unitDiv = h('div', {style: 'margin-bottom: 40px; padding: 16px; border: 2px solid #444;'});
      unitDiv.appendChild(h('h3', {}, `Unit ${idx + 1}`));

      unitDiv.appendChild(selectField('Type', unit.type, window.Rules.UNIT_TYPES, val => {
        ctx.set(`units.rows.${unit.id}.type`, val);
      }));

      unitDiv.appendChild(textField('Name', unit.name, val => ctx.set(`units.rows.${unit.id}.name`, val)));

      // Map image
      const defaultArt = ref.defaultUnitArt || {};
      const typeKey = unit.type ? unit.type.toLowerCase().replace(/ /g, '').replace('greatoldone', 'goo').replace('eldergod', 'elderGod').replace('customgate', 'customGate') : null;
      const typeArt = typeKey ? defaultArt[typeKey] : null;

      const mapImageDiv = h('div', {className: 'sx-field' + (unit.type ? '' : ' sx-greyed')});
      mapImageDiv.appendChild(h('label', {}, 'Map image'));

      const displayImage = unit.mapImage || (typeArt ? typeArt.url : null);
      if (displayImage) {
        const thumb = h('img', {
          src: displayImage.startsWith('http') ? displayImage : ctx.imgUrl(displayImage),
          className: 'sx-img-thumb',
          onclick: () => openUnitMapViewer(unit, ctx, typeArt)
        });
        mapImageDiv.appendChild(thumb);
      } else {
        mapImageDiv.appendChild(h('div', {className: 'sx-img-thumb sx-empty'}, 'Choose type'));
      }
      unitDiv.appendChild(mapImageDiv);

      // Silhouette
      const silDiv = h('div', {className: 'sx-field'});
      silDiv.appendChild(h('label', {}, 'Silhouette'));
      if (unit.silhouette) {
        const thumb = h('img', {
          src: ctx.imgUrl(unit.silhouette),
          className: 'sx-img-thumb',
          onclick: () => openUnitSilhouetteViewer(unit, ctx)
        });
        silDiv.appendChild(thumb);
      } else {
        const uploadBtn = h('div', {
          className: 'sx-img-thumb sx-empty',
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`units.rows.${unit.id}.silhouette`, id);
          }
        }, 'Click to upload');
        silDiv.appendChild(uploadBtn);
      }
      unitDiv.appendChild(silDiv);

      unitDiv.appendChild(numberField('Quantity', unit.qty, val => ctx.set(`units.rows.${unit.id}.qty`, val), {min: 1, max: 20}));

      // Cost
      unitDiv.appendChild(selectField('Cost Type', unit.costType, window.Rules.COST_TYPES, val => {
        ctx.set(`units.rows.${unit.id}.costType`, val);
      }));

      if (unit.costType === 'Fixed') {
        unitDiv.appendChild(numberField('Cost', unit.cost, val => ctx.set(`units.rows.${unit.id}.cost`, val), {min: 0}));
      } else if (unit.costType === 'Variable') {
        unitDiv.appendChild(textField('Cost calculation', unit.costCalc, val => ctx.set(`units.rows.${unit.id}.costCalc`, val), {rows: 2}));
      } else if (unit.costType === 'Awakening') {
        unitDiv.appendChild(textField('Requirements/process', unit.awakenReq, val => ctx.set(`units.rows.${unit.id}.awakenReq`, val), {rows: 3}));
        unitDiv.appendChild(numberField('Power cost', unit.awakenPower, val => ctx.set(`units.rows.${unit.id}.awakenPower`, val), {min: 0}));
        unitDiv.appendChild(textField('Region placement', unit.awakenRegion, val => ctx.set(`units.rows.${unit.id}.awakenRegion`, val)));
      }

      // Combat
      unitDiv.appendChild(selectField('Combat type', unit.combatType, window.Rules.COMBAT_TYPES, val => {
        ctx.set(`units.rows.${unit.id}.combatType`, val);
      }));

      const combatGreyed = unit.combatType === 'N/A';

      if (unit.combatType === 'Fixed Dice') {
        unitDiv.appendChild(numberField('Dice', unit.dice, val => ctx.set(`units.rows.${unit.id}.dice`, val), {min: 0}));
      } else if (unit.combatType === 'Variable Dice') {
        unitDiv.appendChild(textField('Dice calculation', unit.diceCalc, val => ctx.set(`units.rows.${unit.id}.diceCalc`, val), {rows: 2}));
      } else if (unit.combatType === 'Fixed Results') {
        unitDiv.appendChild(numberField('Pains', unit.pains, val => ctx.set(`units.rows.${unit.id}.pains`, val), {min: 0}));
        unitDiv.appendChild(numberField('Kills', unit.kills, val => ctx.set(`units.rows.${unit.id}.kills`, val), {min: 0}));
      } else if (unit.combatType === 'Variable Results') {
        unitDiv.appendChild(textField('Results calculation', unit.resultsCalc, val => ctx.set(`units.rows.${unit.id}.resultsCalc`, val), {rows: 2}));
      }

      // Related Spellbooks
      const sbOptions = sbRows.filter(s => s.name).map(s => ({value: s.id, label: s.name}));
      const relatedDiv = h('div', {className: 'sx-field' + (sbOptions.length === 0 || (unit.relatedSbNames.length > 0 && sbStatus !== 'Complete') ? ' sx-greyed' : '')});
      relatedDiv.appendChild(h('label', {}, 'Related Spellbooks'));

      if (sbOptions.length === 0) {
        relatedDiv.appendChild(h('div', {}, 'None Defined Yet'));
      } else {
        sbOptions.forEach(opt => {
          const checked = unit.relatedSb.includes(opt.value);
          relatedDiv.appendChild(h('label', {style: 'display: block; margin: 4px 0;'},
            h('input', {
              type: 'checkbox',
              checked,
              onchange: e => {
                const newVal = e.target.checked
                  ? [...unit.relatedSb, opt.value]
                  : unit.relatedSb.filter(id => id !== opt.value);
                ctx.set(`units.rows.${unit.id}.relatedSb`, newVal);
              }
            }),
            ' ' + opt.label
          ));
        });
      }
      unitDiv.appendChild(relatedDiv);

      unitDiv.appendChild(textField('Special Ability Name', unit.abilityName, val => ctx.set(`units.rows.${unit.id}.abilityName`, val)));
      unitDiv.appendChild(textField('Special Ability Text', unit.abilityText, val => ctx.set(`units.rows.${unit.id}.abilityText`, val), {rows: 4}));

      if (idx >= 3) {
        unitDiv.appendChild(h('button', {className: 'sx-btn', onclick: async () => {
          const confirmed = await ctx.confirm('Are you sure you want to delete this unit?', 'Yes - delete', 'No - cancel');
          if (confirmed) ctx.deleteRow('units.rows', unit.id);
        }}, 'Delete this unit'));
      }

      container.appendChild(unitDiv);
    });

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newUnit = window.Rules.blankRow('units.rows');
      ctx.addRow('units.rows', newUnit);
    }}, 'Add unit'));
  }

  function openUnitMapViewer(unit, ctx, defaultArt) {
    const ref = ctx.reference || {};
    const mapData = ref.earthMap3W || {url: '', w: 1791, h: 894, southPacific: {x: 540, y: 830}};

    let scale = unit.mapScale || 1.0;
    const canvas = h('canvas', {width: mapData.w, height: mapData.h});
    const canvasCtx = canvas.getContext('2d');

    const mapImg = new Image();
    mapImg.crossOrigin = 'anonymous';
    mapImg.src = mapData.url;

    const unitImg = new Image();
    unitImg.crossOrigin = 'anonymous';
    const displayImage = unit.mapImage || (defaultArt ? defaultArt.url : null);
    if (displayImage) {
      unitImg.src = displayImage.startsWith('http') ? displayImage : ctx.imgUrl(displayImage);
    }

    function draw() {
      canvasCtx.clearRect(0, 0, mapData.w, mapData.h);
      if (mapImg.complete) {
        canvasCtx.drawImage(mapImg, 0, 0);
      }
      if (unitImg.complete && unitImg.src) {
        const w = unitImg.width * scale;
        const h = unitImg.height * scale;
        const x = mapData.southPacific.x - w / 2;
        const y = mapData.southPacific.y - h / 2;

        if (ctx.design.meta && ctx.design.meta.color) {
          canvasCtx.save();
          canvasCtx.globalCompositeOperation = 'source-over';
          canvasCtx.drawImage(unitImg, x, y, w, h);
          canvasCtx.globalCompositeOperation = 'source-atop';
          canvasCtx.fillStyle = ctx.design.meta.color;
          canvasCtx.fillRect(x, y, w, h);
          canvasCtx.restore();
        } else {
          canvasCtx.drawImage(unitImg, x, y, w, h);
        }
      }
    }

    mapImg.onload = draw;
    unitImg.onload = draw;

    const buttons = h('div', {className: 'sx-overlay-buttons'},
      h('button', {className: 'sx-btn', onclick: () => {
        scale *= 1.025;
        draw();
      }}, 'Grow'),
      h('button', {className: 'sx-btn', onclick: () => {
        scale /= 1.025;
        draw();
      }}, 'Shrink'),
      h('button', {className: 'sx-btn', onclick: () => {
        scale = 1.0;
        ctx.set(`units.rows.${unit.id}.mapImage`, null);
        ctx.set(`units.rows.${unit.id}.mapScale`, 1.0);
        unitImg.src = defaultArt ? defaultArt.url : '';
        draw();
      }}, 'Use default', defaultArt ? h('img', {src: defaultArt.url, style: 'width: 40px; height: 40px; margin-left: 8px; vertical-align: middle;'}) : null),
      h('button', {className: 'sx-btn', onclick: async () => {
        const id = await ctx.uploadImage('small');
        if (id) {
          ctx.set(`units.rows.${unit.id}.mapImage`, id);
          unitImg.src = ctx.imgUrl(id);
        }
      }}, 'Replace'),
      h('button', {className: 'sx-btn', onclick: () => {
        ctx.set(`units.rows.${unit.id}.mapScale`, scale);
        ctx.closeOverlay();
      }}, 'Done')
    );

    const content = h('div', {}, buttons, canvas);
    ctx.openOverlay(content);
  }

  function openUnitSilhouetteViewer(unit, ctx) {
    const previewDiv = h('div', {
      style: 'background: #1a1a1a; border: 2px solid #666; padding: 20px; width: 400px; font-family: "Bohemian Typewriter", monospace;'
    });

    previewDiv.appendChild(h('h2', {style: 'text-align: center; margin-bottom: 16px;'}, unit.name || 'Unit'));

    if (unit.silhouette) {
      previewDiv.appendChild(h('img', {
        src: ctx.imgUrl(unit.silhouette),
        style: 'display: block; margin: 16px auto; max-width: 200px; max-height: 200px; border: 1px solid #666;'
      }));
    }

    const fields = [];
    if (unit.costType === 'Fixed' && unit.cost != null) fields.push(`Cost: ${unit.cost}`);
    if (unit.combatType === 'Fixed Dice' && unit.dice != null) fields.push(`Combat: ${unit.dice} dice`);
    if (unit.combatType === 'Fixed Results') fields.push(`Combat: ${unit.pains || 0} pains, ${unit.kills || 0} kills`);
    if (unit.abilityName) fields.push(`${unit.abilityName}: ${unit.abilityText || ''}`);

    fields.forEach(f => {
      previewDiv.appendChild(h('div', {style: 'margin: 8px 0; font-size: 14px;'}, f));
    });

    const buttons = h('div', {style: 'margin-top: 20px; display: flex; gap: 8px; justify-content: center;'},
      h('button', {className: 'sx-btn', onclick: async () => {
        const id = await ctx.uploadImage('small');
        if (id) {
          ctx.set(`units.rows.${unit.id}.silhouette`, id);
          ctx.closeOverlay();
          ctx.rerender();
        }
      }}, 'Replace'),
      h('button', {className: 'sx-btn', onclick: () => ctx.closeOverlay()}, 'Done')
    );

    const content = h('div', {style: 'display: flex; flex-direction: column; align-items: center;'},
      buttons,
      previewDiv
    );
    ctx.openOverlay(content);
  }

  function renderSBR(container, ctx) {
    const d = ctx.design.sbr;

    container.appendChild(textField('Multi-requirement text', d.multiText, val => ctx.set('sbr.multiText', val), {rows: 3}));

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'Spellbook Requirement Text'),
        h('th', {style: 'width: 200px;'}, 'Includes Fixed Numeric Cost or Effect?'),
        h('th', {style: 'width: 150px;'}, 'Fixed Numeric Cost or Effect')
      )
    ));

    const tbody = h('tbody', {});
    d.rows.forEach(row => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('textarea', {value: row.text || '', rows: 3, oninput: e => ctx.set(`sbr.rows.${row.id}.text`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasNum, onchange: e => ctx.set(`sbr.rows.${row.id}.hasNum`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: row.num != null ? row.num : '',
          disabled: !row.hasNum,
          oninput: e => ctx.set(`sbr.rows.${row.id}.num`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);
  }

  function renderSB(container, ctx) {
    const d = ctx.design.sb;
    const two = !!d.twoSided;

    // 2 sided: every spellbook gets a side A and a side B, each with its own name, type, cost, effect and text
    container.appendChild(checkboxField('2 sided (each spellbook has a side A and a side B)', two, val => {
      if (val && !ctx.design.sbImagesB) ctx.set('sbImagesB', {mode: null, all: null, each: [null, null, null, null, null, null]});
      ctx.set('sb.twoSided', val);
    }));

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        two ? h('th', {style: 'width: 90px;'}, 'Spellbook') : null,
        two ? h('th', {style: 'width: 60px;'}, 'Side') : null,
        h('th', {}, 'Name'),
        h('th', {}, 'Type'),
        h('th', {style: 'width: 100px;'}, 'Cost'),
        h('th', {style: 'width: 150px;'}, 'Includes Fixed Numeric Effect?'),
        h('th', {style: 'width: 100px;'}, 'Fixed Numeric Effect'),
        h('th', {}, 'Text'),
        h('th', {}, '')
      )
    ));

    // One side's cells. sfx = '' for side A (or the only side), 'B' for side B
    function sideCells(tr, row, sfx) {
      const f = name => `sb.rows.${row.id}.${name}${sfx}`;
      const v = name => row[name + sfx];
      tr.appendChild(h('td', {},
        h('input', {type: 'text', value: v('name') || '', oninput: e => ctx.set(f('name'), e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('select', {value: v('type') || '', onchange: e => ctx.set(f('type'), e.target.value || null)},
          h('option', {value: ''}, '-- Select --'),
          window.Rules.SB_TYPES.map(t => h('option', {value: t}, t))
        )
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: v('cost') != null ? v('cost') : 0,
          oninput: e => ctx.set(f('cost'), e.target.value ? parseInt(e.target.value) : 0)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: !!v('hasEffect'), onchange: e => ctx.set(f('hasEffect'), e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: v('effect') != null ? v('effect') : '',
          disabled: !v('hasEffect'),
          oninput: e => ctx.set(f('effect'), e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {value: v('text') || '', rows: 3, oninput: e => ctx.set(f('text'), e.target.value)})
      ));
    }

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      const tr = h('tr', {});
      const span = two ? {rowSpan: 2} : {};
      if (two) {
        tr.appendChild(h('td', Object.assign({style: 'font-weight: bold;'}, span), `Spellbook ${idx + 1}`));
        tr.appendChild(h('td', {}, 'Side A'));
      }
      sideCells(tr, row, '');

      if (d.rows.length > 6) {
        tr.appendChild(h('td', span,
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this spellbook?', 'Yes - delete', 'No - cancel');
            if (confirmed) ctx.deleteRow('sb.rows', row.id);
          }}, 'Delete')
        ));
      } else {
        tr.appendChild(h('td', span));
      }

      tbody.appendChild(tr);

      if (two) {
        const trB = h('tr', {style: 'border-bottom: 3px solid #000;'});
        trB.appendChild(h('td', {}, 'Side B'));
        sideCells(trB, row, 'B');
        tbody.appendChild(trB);
      }
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankRow('sb.rows');
      ctx.addRow('sb.rows', newRow);
    }}, 'Add row'));
  }

  function renderRegion(container, ctx) {
    const d = ctx.design.region;

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'Name'),
        h('th', {}, 'Image'),
        h('th', {}, 'Unit Restrictions'),
        h('th', {}, 'Adjacency'),
        h('th', {}, '')
      )
    ));

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('input', {type: 'text', value: row.name || '', oninput: e => ctx.set(`region.rows.${row.id}.name`, e.target.value)})
      ));

      const imgTd = h('td', {});
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb',
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`region.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty',
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`region.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {value: row.restrictions || '', rows: 2, oninput: e => ctx.set(`region.rows.${row.id}.restrictions`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('textarea', {value: row.adjacency || '', rows: 2, oninput: e => ctx.set(`region.rows.${row.id}.adjacency`, e.target.value)})
      ));

      if (idx === 0 && d.rows.length === 1) {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Delete all values in this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) {
              ctx.set(`region.rows.${row.id}.name`, '');
              ctx.set(`region.rows.${row.id}.image`, null);
              ctx.set(`region.rows.${row.id}.restrictions`, '');
              ctx.set(`region.rows.${row.id}.adjacency`, '');
            }
          }}, 'Clear')
        ));
      } else {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) ctx.deleteRow('region.rows', row.id);
          }}, 'Delete')
        ));
      }

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankRow('region.rows');
      ctx.addRow('region.rows', newRow);
    }}, 'Add row'));
  }

  function renderTokens(container, ctx) {
    const d = ctx.design.tokens;

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'Name'),
        h('th', {}, 'Qty'),
        h('th', {}, 'Image'),
        h('th', {}, 'Placement on map or faction card'),
        h('th', {}, 'Effects'),
        h('th', {style: 'width: 120px;'}, 'Includes Fixed Numeric Effect?'),
        h('th', {style: 'width: 100px;'}, 'Fixed Numeric Effect'),
        h('th', {}, '')
      )
    ));

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('input', {type: 'text', value: row.name || '', oninput: e => ctx.set(`tokens.rows.${row.id}.name`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'number', value: row.qty != null ? row.qty : '', oninput: e => ctx.set(`tokens.rows.${row.id}.qty`, e.target.value ? parseInt(e.target.value) : null)})
      ));

      const imgTd = h('td', {});
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb',
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`tokens.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty',
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`tokens.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {value: row.placement || '', rows: 2, oninput: e => ctx.set(`tokens.rows.${row.id}.placement`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('textarea', {value: row.effects || '', rows: 2, oninput: e => ctx.set(`tokens.rows.${row.id}.effects`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasEffect, onchange: e => ctx.set(`tokens.rows.${row.id}.hasEffect`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: row.effect != null ? row.effect : '',
          disabled: !row.hasEffect,
          oninput: e => ctx.set(`tokens.rows.${row.id}.effect`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      if (idx === 0 && d.rows.length === 1) {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Delete all values in this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) {
              ctx.set(`tokens.rows.${row.id}.name`, '');
              ctx.set(`tokens.rows.${row.id}.qty`, null);
              ctx.set(`tokens.rows.${row.id}.image`, null);
              ctx.set(`tokens.rows.${row.id}.placement`, '');
              ctx.set(`tokens.rows.${row.id}.effects`, '');
              ctx.set(`tokens.rows.${row.id}.hasEffect`, false);
              ctx.set(`tokens.rows.${row.id}.effect`, null);
            }
          }}, 'Clear')
        ));
      } else {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) ctx.deleteRow('tokens.rows', row.id);
          }}, 'Delete')
        ));
      }

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankRow('tokens.rows');
      ctx.addRow('tokens.rows', newRow);
    }}, 'Add row'));
  }

  function renderCustom(container, ctx) {
    const d = ctx.design.custom;

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'Name'),
        h('th', {}, 'Image'),
        h('th', {}, 'Placement on screen'),
        h('th', {}, 'Usage'),
        h('th', {}, 'Effects'),
        h('th', {style: 'width: 120px;'}, 'Includes Fixed Numeric Cost or Effect?'),
        h('th', {style: 'width: 100px;'}, 'Fixed Numeric Cost or Effect'),
        h('th', {}, '')
      )
    ));

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('input', {type: 'text', value: row.name || '', oninput: e => ctx.set(`custom.rows.${row.id}.name`, e.target.value)})
      ));

      const imgTd = h('td', {});
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb',
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`custom.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty',
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`custom.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {value: row.placement || '', rows: 2, oninput: e => ctx.set(`custom.rows.${row.id}.placement`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('textarea', {value: row.usage || '', rows: 2, oninput: e => ctx.set(`custom.rows.${row.id}.usage`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('textarea', {value: row.effects || '', rows: 2, oninput: e => ctx.set(`custom.rows.${row.id}.effects`, e.target.value)})
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasNum, onchange: e => ctx.set(`custom.rows.${row.id}.hasNum`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          type: 'number',
          value: row.num != null ? row.num : '',
          disabled: !row.hasNum,
          oninput: e => ctx.set(`custom.rows.${row.id}.num`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      if (idx === 0 && d.rows.length === 1) {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Delete all values in this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) {
              ctx.set(`custom.rows.${row.id}.name`, '');
              ctx.set(`custom.rows.${row.id}.image`, null);
              ctx.set(`custom.rows.${row.id}.placement`, '');
              ctx.set(`custom.rows.${row.id}.usage`, '');
              ctx.set(`custom.rows.${row.id}.effects`, '');
              ctx.set(`custom.rows.${row.id}.hasNum`, false);
              ctx.set(`custom.rows.${row.id}.num`, null);
            }
          }}, 'Clear')
        ));
      } else {
        tr.appendChild(h('td', {},
          h('button', {onclick: async () => {
            const confirmed = await ctx.confirm('Are you sure you want to delete this row?', 'Yes - delete', 'No - cancel');
            if (confirmed) ctx.deleteRow('custom.rows', row.id);
          }}, 'Delete')
        ));
      }

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankRow('custom.rows');
      ctx.addRow('custom.rows', newRow);
    }}, 'Add row'));
  }

  const MENU_RECOMMEND_MINUTES = 5;

  function renderMenus(container, ctx) {
    const d = ctx.design.menus;
    const ref = ctx.reference || {};

    // The checker reads the whole design and writes suggested menus for every ability,
    // spellbook, unit, etc. that needs a player choice. Time measured 2026-10-09.
    const hasMenus = !window.Rules.isEmpty('menus', ctx.design);
    const recBtn = h('button', {className: 'sx-btn', onclick: async () => {
      if (hasMenus) {
        const ok = await ctx.confirm('Recommend menu design will replace the menus below with suggested ones. Are you sure?', 'Yes - Recommend', 'Cancel');
        if (!ok) return;
      }
      recBtn.disabled = true;
      try {
        await ctx.createRequest('extract', `Recommend menu design for ${ctx.faction.name}`, {target: 'menus'});
        alert(`Menu design requested. Suggested menus will appear here in about ${MENU_RECOMMEND_MINUTES} minutes.`);
      } catch (err) {
        alert('Request failed: ' + err.message);
      }
      recBtn.disabled = false;
    }}, 'Recommend menu design');
    container.appendChild(h('div', {className: 'menu-recommend', style: 'margin-bottom: 24px;'},
      recBtn,
      h('div', {className: 'extract-estimate', style: 'font-size: 0.8em; opacity: 0.75; margin-top: 3px;'}, `about ${MENU_RECOMMEND_MINUTES} min`),
      h('div', {style: 'font-size: 0.85em; opacity: 0.75; margin-top: 4px;'}, 'Reads everything you have filled in (abilities, spellbooks, units, tokens...) and suggests a menu for each choice a player makes. Fill those in first.')));

    d.rows.forEach((menu, idx) => {
      const menuDiv = h('div', {style: 'margin-bottom: 40px; padding: 16px; border: 2px solid #444;'});
      menuDiv.appendChild(h('h3', {}, `Menu ${idx + 1}`));

      menuDiv.appendChild(textField('Menu Name', menu.name, val => ctx.set(`menus.rows.${menu.id}.name`, val)));

      menuDiv.appendChild(selectField('Section', menu.section, window.Rules.BUILD_SECTIONS.map(k => {
        const s = window.Rules.SECTIONS.find(sec => sec.key === k);
        return {value: k, label: s ? s.title : k};
      }), val => {
        ctx.set(`menus.rows.${menu.id}.section`, val);
        ctx.set(`menus.rows.${menu.id}.item`, null);
      }));

      // Item pick list
      let itemOptions = [];
      let itemGreyed = false;
      if (menu.section === 'ufa') {
        itemGreyed = true;
      } else if (menu.section === 'ae') {
        itemOptions = ctx.design.ae.rows.map(r => ({value: r.id, label: r.desc || 'Increment'}));
      } else if (menu.section === 'units') {
        itemOptions = ctx.design.units.rows.filter(u => u.name).map(u => ({value: u.id, label: u.name}));
      } else if (menu.section === 'sbr') {
        itemOptions = ctx.design.sbr.rows.filter(r => r.text).map(r => ({value: r.id, label: r.text}));
      } else if (menu.section === 'sb') {
        itemOptions = ctx.design.sb.rows.filter(s => s.name).map(s => ({value: s.id,
          label: ctx.design.sb.twoSided && s.nameB ? `${s.name} / ${s.nameB}` : s.name}));
      } else if (menu.section === 'region') {
        itemOptions = ctx.design.region.rows.filter(r => r.name).map(r => ({value: r.id, label: r.name}));
      } else if (menu.section === 'tokens') {
        itemOptions = ctx.design.tokens.rows.filter(r => r.name).map(r => ({value: r.id, label: r.name}));
      } else if (menu.section === 'custom') {
        itemOptions = ctx.design.custom.rows.filter(r => r.name).map(r => ({value: r.id, label: r.name}));
      }

      menuDiv.appendChild(selectField('Item', menu.item, itemOptions, val => ctx.set(`menus.rows.${menu.id}.item`, val), {
        greyed: itemGreyed,
        placeholder: itemOptions.length === 0 ? 'No items available' : '-- Select --'
      }));

      menuDiv.appendChild(selectField('Faction prompted', menu.prompted, ['Own', '1 Enemy', 'All enemies (turn order)', 'All enemies (at the same time)', 'All players (at the same time)'], val => ctx.set(`menus.rows.${menu.id}.prompted`, val)));

      const placeholderHint = 'Placeholders: [Faction], [Region], [Unit], [Power], [Doom], [Enemy], [Spellbook], [Number] (for Pick a number menus)';
      menuDiv.appendChild(textField('Menu Title', menu.title, val => ctx.set(`menus.rows.${menu.id}.title`, val), {hint: placeholderHint}));

      menuDiv.appendChild(checkboxField('Menu Subtitle', menu.hasSubtitle, val => ctx.set(`menus.rows.${menu.id}.hasSubtitle`, val)));
      menuDiv.appendChild(textField('Subtitle', menu.subtitle, val => ctx.set(`menus.rows.${menu.id}.subtitle`, val), {greyed: !menu.hasSubtitle}));

      menuDiv.appendChild(textField('Button Text', menu.button, val => ctx.set(`menus.rows.${menu.id}.button`, val), {hint: placeholderHint}));

      menuDiv.appendChild(checkboxField('Cancel Button', menu.cancel, val => ctx.set(`menus.rows.${menu.id}.cancel`, val)));
      menuDiv.appendChild(checkboxField('Skip Button', menu.skip, val => ctx.set(`menus.rows.${menu.id}.skip`, val), {greyed: !!menu.infoOnly}));
      menuDiv.appendChild(checkboxField('Done Button', !!menu.done, val => {
        // Multi select needs a Done button to finish, so turning Done off also turns multi select off
        if (!val && menu.multiSelect) {
          ctx.set(`menus.rows.${menu.id}.multiSelect`, false);
          if (menu.showPicked) ctx.set(`menus.rows.${menu.id}.showPicked`, false);
        }
        ctx.set(`menus.rows.${menu.id}.done`, val);
      }, {greyed: !!menu.infoOnly}));
      menuDiv.appendChild(checkboxField('Multi select (pick one option, the menu comes back with the options that are left so more can be picked, until Done is clicked)', !!menu.multiSelect, val => {
        if (val && !menu.done) ctx.set(`menus.rows.${menu.id}.done`, true);
        if (!val && menu.showPicked) ctx.set(`menus.rows.${menu.id}.showPicked`, false);
        ctx.set(`menus.rows.${menu.id}.multiSelect`, val);
      }, {greyed: !!menu.infoOnly}));

      const set = (field, val) => ctx.set(`menus.rows.${menu.id}.${field}`, val);
      const info = !!menu.infoOnly;

      menuDiv.appendChild(checkboxField('Picked so far (multi select menus show what has been picked above the remaining options)', !!menu.showPicked,
        val => set('showPicked', val), {greyed: !menu.multiSelect || info}));

      menuDiv.appendChild(checkboxField('Repeat a set number of times (the menu is asked again, e.g. once per unit saved or until moves run out)', !!menu.repeat,
        val => set('repeat', val), {greyed: info}));
      menuDiv.appendChild(textField('How many times', menu.repeatCount, val => set('repeatCount', val),
        {greyed: !menu.repeat || info, hint: 'A number, a placeholder like [Power], or a rule like "until all moves are used"'}));

      menuDiv.appendChild(checkboxField('Pick a number (the player picks a number from a range instead of a list of buttons)', !!menu.numberPick,
        val => set('numberPick', val), {greyed: info}));
      menuDiv.appendChild(textField('Lowest number', menu.numberMin, val => set('numberMin', val), {greyed: !menu.numberPick || info, hint: 'A number or a placeholder like [Power]'}));
      menuDiv.appendChild(textField('Highest number', menu.numberMax, val => set('numberMax', val), {greyed: !menu.numberPick || info, hint: 'A number or a placeholder like [Power]'}));

      menuDiv.appendChild(checkboxField('Show options that cannot be picked, greyed out with a reason', !!menu.greyedOptions,
        val => set('greyedOptions', val), {greyed: info}));
      menuDiv.appendChild(textField('Reason shown', menu.greyedReason, val => set('greyedReason', val),
        {greyed: !menu.greyedOptions || info, hint: 'e.g. "needs a Gate" or "not enough Power"'}));

      menuDiv.appendChild(checkboxField('Confirm step (ask "are you sure?" before the choice is locked in)', !!menu.confirm, val => set('confirm', val), {greyed: info}));
      menuDiv.appendChild(textField('Confirm question', menu.confirmText, val => set('confirmText', val),
        {greyed: !menu.confirm || info, hint: placeholderHint}));

      // Info only: no choice at all, so the choice settings above are greyed out and turned off
      menuDiv.appendChild(checkboxField('Info only (just the title and subtitle text with an OK button, no choice)', info, val => {
        if (val) {
          ['multiSelect', 'showPicked', 'repeat', 'numberPick', 'greyedOptions', 'confirm', 'done', 'skip']
            .forEach(f => { if (menu[f]) set(f, false); });
        }
        set('infoOnly', val);
      }));

      menuDiv.appendChild(checkboxField('Can lead to another Menu prompt', menu.leadsToNext, val => ctx.set(`menus.rows.${menu.id}.leadsToNext`, val)));

      const nextMenuOptions = d.rows.filter(m => m.name && m.id !== menu.id).map(m => ({value: m.id, label: m.name}));
      menuDiv.appendChild(selectField('Next Menu Prompt', menu.next, nextMenuOptions, val => ctx.set(`menus.rows.${menu.id}.next`, val), {
        greyed: !menu.leadsToNext,
        placeholder: nextMenuOptions.length === 0 ? 'No other menus defined' : '-- Select --'
      }));

      menuDiv.appendChild(textField('Next Menu triggered by', menu.nextTrigger, val => ctx.set(`menus.rows.${menu.id}.nextTrigger`, val), {greyed: !menu.leadsToNext}));

      menuDiv.appendChild(h('button', {className: 'sx-btn', onclick: () => showMenuPreview(menu, ctx)}, 'Preview'));

      if (idx > 0) {
        menuDiv.appendChild(h('button', {className: 'sx-btn', onclick: async () => {
          const confirmed = await ctx.confirm('Are you sure you want to delete this menu?', 'Yes - delete', 'No - cancel');
          if (confirmed) ctx.deleteRow('menus.rows', menu.id);
        }}, 'Delete this menu'));
      }

      container.appendChild(menuDiv);
    });

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newMenu = window.Rules.blankRow('menus.rows');
      ctx.addRow('menus.rows', newMenu);
    }}, 'Add menu'));
  }

  function showMenuPreview(menu, ctx) {
    const ref = ctx.reference || {};
    const gcPreview = ref.gcPreview || {name: 'Great Cthulhu', units: ['Acolyte', 'Deep One', 'Shoggoth', 'Starspawn', 'Cthulhu']};
    const factionName = ctx.faction.name || 'Your Faction';
    const factionColor = ctx.design.meta.color || '#888';

    function substitute(text) {
      if (!text) return '';
      return text
        .replace(/\[Faction\]/g, factionName)
        .replace(/\[Region\]/g, 'South Pacific')
        .replace(/\[Unit\]/g, gcPreview.units[0] || 'Cultist')
        .replace(/\[Power\]/g, '4')
        .replace(/\[Doom\]/g, '7')
        .replace(/\[Enemy\]/g, gcPreview.name)
        .replace(/\[Spellbook\]/g, 'Example Spellbook');
    }

    const previewDiv = h('div', {className: 'sx-menu-preview'});

    if (menu.title) {
      previewDiv.appendChild(h('div', {
        className: 'sx-menu-preview-title',
        style: `color: ${factionColor};`
      }, substitute(menu.title)));
    }

    if (menu.hasSubtitle && menu.subtitle) {
      previewDiv.appendChild(h('div', {style: 'text-align: center; margin-bottom: 12px; font-size: 14px; color: #ccc;'}, substitute(menu.subtitle)));
    }

    const note = text => previewDiv.appendChild(h('div', {style: 'text-align: center; margin: 10px 0; font-size: 13px; color: #ccc; font-style: italic;'}, text));
    const info = !!menu.infoOnly;

    if (!info && menu.multiSelect && menu.showPicked) {
      previewDiv.appendChild(h('div', {style: 'text-align: center; margin-bottom: 10px; font-size: 13px; color: #ddd;'},
        `Picked so far: ${gcPreview.units[1] || 'Deep One'}`));
    }

    if (!info && menu.numberPick) {
      const lo = substitute(menu.numberMin) || '0';
      const hi = substitute(menu.numberMax) || '?';
      const nums = /^\d+$/.test(lo) && /^\d+$/.test(hi) && +hi - +lo <= 12
        ? Array.from({length: +hi - +lo + 1}, (_, i) => String(+lo + i)) : [lo, '...', hi];
      nums.forEach(n => previewDiv.appendChild(h('div', {className: 'sx-menu-preview-option', style: `border-left-color: ${factionColor};`},
        menu.button ? substitute(menu.button).replace(/\[Number\]/g, n) : n)));
    } else if (!info && menu.button) {
      previewDiv.appendChild(h('div', {
        className: 'sx-menu-preview-option',
        style: `border-left-color: ${factionColor};`
      }, substitute(menu.button)));
    }

    if (!info && menu.greyedOptions) {
      previewDiv.appendChild(h('div', {className: 'sx-menu-preview-option', style: 'border-left-color: #666; opacity: 0.45; cursor: default;'},
        `${substitute(menu.button).replace(/\[Number\]/g, /^\d+$/.test(substitute(menu.numberMax)) ? String(+substitute(menu.numberMax) + 1) : '?') || 'Option'} (${substitute(menu.greyedReason) || 'cannot be picked'})`));
    }

    if (!info && menu.multiSelect) note('Multi select: after each pick this menu comes back with the remaining options, until Done is clicked.');
    if (!info && menu.repeat) note(`Repeats: this menu is asked ${substitute(menu.repeatCount) || 'a set number of'} times.`);
    if (!info && menu.confirm) note(`After the pick: "${substitute(menu.confirmText) || 'Are you sure?'}" with Yes / No.`);
    if ((menu.prompted || '').includes('at the same time')) note(`${menu.prompted}: everyone answers this menu at once, and nobody sees the others' picks until all have answered.`);

    const buttons = [];
    if (info) buttons.push(h('div', {className: 'sx-menu-preview-btn'}, 'OK'));
    if (menu.cancel) buttons.push(h('div', {className: 'sx-menu-preview-btn'}, 'Cancel'));
    if (!info && menu.skip) buttons.push(h('div', {className: 'sx-menu-preview-btn'}, 'Skip'));
    if (!info && (menu.done || menu.multiSelect)) buttons.push(h('div', {className: 'sx-menu-preview-btn'}, 'Done'));

    if (buttons.length > 0) {
      previewDiv.appendChild(h('div', {className: 'sx-menu-preview-buttons'}, ...buttons));
    }

    const content = h('div', {},
      h('button', {className: 'sx-btn', onclick: () => ctx.closeOverlay(), style: 'margin-bottom: 16px;'}, 'Close'),
      previewDiv
    );

    ctx.openOverlay(content);
  }

  function render(key, container, ctx) {
    injectCSS();
    container.innerHTML = '';

    const renderers = {
      ae: renderAE,
      ufa: renderUFA,
      setup: renderSetup,
      units: renderUnits,
      sbr: renderSBR,
      sb: renderSB,
      region: renderRegion,
      tokens: renderTokens,
      custom: renderCustom,
      menus: renderMenus
    };

    const renderer = renderers[key];
    if (renderer) {
      renderer(container, ctx);
    } else {
      container.appendChild(h('p', {}, 'Section not implemented: ' + key));
    }
  }

  window.Sections = {render};
})();
