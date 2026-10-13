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
      .sx-missing { border: 2px solid #e53935 !important; }
      .sx-img-thumb.sx-missing { border: 2px solid #e53935; }
      input[type="checkbox"].sx-missing, input[type="radio"].sx-missing { outline: 2px solid #e53935; outline-offset: 2px; }

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
    const missing = opts.missing || false;

    const inputClass = missing ? 'sx-missing' : '';
    const input = rows
      ? h('textarea', {className: inputClass, value: value || '', oninput: e => onChange(e.target.value), rows})
      : h('input', {className: inputClass, type: 'text', value: value || '', oninput: e => onChange(e.target.value)});

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label, hint ? h('span', {className: 'sx-hint', title: hint}, 'ⓘ') : null),
      input
    );
  }

  function numberField(label, value, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const min = opts.min != null ? opts.min : null;
    const max = opts.max != null ? opts.max : null;
    const missing = opts.missing || false;

    const attrs = {
      type: 'number',
      className: missing ? 'sx-missing' : '',
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
    const missing = opts.missing || false;

    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {}, label),
      h('select', {className: missing ? 'sx-missing' : '', value: value || '', onchange: e => onChange(e.target.value || null)},
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
    const missing = opts.missing || false;
    return h('div', {className: 'sx-field' + (greyed ? ' sx-greyed' : '')},
      h('label', {},
        h('input', {className: missing ? 'sx-missing' : '', type: 'checkbox', checked, onchange: e => onChange(e.target.checked)}),
        label
      )
    );
  }

  function imageField(label, imageId, ctx, onChange, opts = {}) {
    const greyed = opts.greyed || false;
    const size = opts.size || 'small';
    const missing = opts.missing || false;

    const thumbClass = 'sx-img-thumb' + (imageId ? '' : ' sx-empty') + (missing ? ' sx-missing' : '');
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

  // Helper to render Claude Q&A boxes for each section (admin view only)
  function renderClaudeQA(container, ctx, sectionName) {
    if (!ctx.adminView) return;

    const claudeQAData = ctx.faction ? ctx.faction.claudeQA : (ctx.map ? ctx.map.claudeQA : (ctx.unit ? ctx.unit.claudeQA : null));
    if (!claudeQAData) return;

    const qa = claudeQAData[sectionName];
    if (!qa) return;

    // Questions box
    if (qa.questions && qa.questions.trim()) {
      const qDiv = document.createElement('div');
      qDiv.style.cssText = 'margin: 16px 0; padding: 12px; background: #1e3a8a; border: 2px solid #3b82f6; color: #fff; border-radius: 4px;';
      const qLabel = document.createElement('strong');
      qLabel.style.cssText = 'display: block; margin-bottom: 8px;';
      qLabel.textContent = 'Claude Questions:';
      const qPre = document.createElement('pre');
      qPre.style.cssText = 'white-space: pre-wrap; margin: 0; font-family: monospace; font-size: 13px;';
      qPre.textContent = qa.questions;
      qDiv.appendChild(qLabel);
      qDiv.appendChild(qPre);
      container.appendChild(qDiv);
    }

    // Answers box
    if (qa.questions && qa.questions.trim()) {
      const aDiv = document.createElement('div');
      aDiv.style.cssText = 'margin: 16px 0; padding: 12px; background: #065f46; border: 2px solid #10b981; color: #fff; border-radius: 4px;';
      const aLabel = document.createElement('strong');
      aLabel.style.cssText = 'display: block; margin-bottom: 8px;';
      aLabel.textContent = 'Claude Answers:';

      if (qa.answers && qa.answers.trim()) {
        const aPre = document.createElement('pre');
        aPre.style.cssText = 'white-space: pre-wrap; margin: 0; font-family: monospace; font-size: 13px;';
        aPre.textContent = qa.answers;
        aDiv.appendChild(aPre);
      } else if (ctx.readOnly) {
        // In read-only mode, show placeholder if no answers yet
        const placeholder = document.createElement('p');
        placeholder.style.cssText = 'color: #d1d5db; font-style: italic; padding: 8px 0; margin: 0;';
        placeholder.textContent = 'Awaiting designer\'s answer';
        aDiv.appendChild(placeholder);
      }

      container.appendChild(aDiv);
    }
  }

  // Helper to render admin notes for each section
  function renderAdminNotes(container, ctx, sectionPath) {
    if (!ctx.adminView) return;

    const adminNotesDiv = document.createElement('div');
    adminNotesDiv.style.cssText = 'margin-top: 20px; border-top: 2px solid #000; padding-top: 10px;';

    const label = document.createElement('label');
    label.style.cssText = 'display: block; font-weight: bold; margin-bottom: 4px;';
    label.textContent = 'Admin Notes (visible only to admin):';

    const textarea = document.createElement('textarea');
    // Get the value from the design object
    let value = '';
    const parts = sectionPath.split('.');
    let obj = ctx.design;
    for (let i = 0; i < parts.length; i++) {
      obj = obj[parts[i]];
      if (obj == null) break;
    }
    if (obj && typeof obj === 'object' && 'adminNotes' in obj) {
      value = obj.adminNotes || '';
    }

    textarea.value = value;
    textarea.style.cssText = 'width: 100%; min-height: 80px; font-family: monospace; font-size: 12px; border: 2px solid #f59e0b; background: #fef3c7; color: #000;';
    textarea.placeholder = 'Internal notes about this section...';
    // Admin notes are ONLY editable in admin view - regular users never see them
    textarea.disabled = false;

    textarea.addEventListener('input', () => {
      ctx.set(`${sectionPath}.adminNotes`, textarea.value);
    });

    adminNotesDiv.appendChild(label);
    adminNotesDiv.appendChild(textarea);

    // Add submit button (only in admin mode)
    const buttonDiv = document.createElement('div');
    buttonDiv.style.cssText = 'margin-top: 8px; display: flex; gap: 8px; align-items: center;';

    const submitBtn = document.createElement('button');
    submitBtn.textContent = 'Submit to Queue (Immediate)';
    submitBtn.style.cssText = 'padding: 8px 16px; background: #dc2626; color: #fff; border: 1px solid #991b1b; cursor: pointer; font-weight: bold; border-radius: 3px;';
    submitBtn.onmouseover = () => submitBtn.style.background = '#b91c1c';
    submitBtn.onmouseout = () => submitBtn.style.background = '#dc2626';

    const statusSpan = document.createElement('span');
    statusSpan.style.cssText = 'font-size: 12px; color: #666;';
    statusSpan.textContent = '';

    submitBtn.onclick = async () => {
      const noteContent = textarea.value.trim();
      if (!noteContent) {
        statusSpan.textContent = 'Error: Note cannot be empty';
        statusSpan.style.color = '#dc2626';
        return;
      }

      submitBtn.disabled = true;
      statusSpan.textContent = 'Submitting...';
      statusSpan.style.color = '#666';

      try {
        await ctx.submitAdminNote(sectionPath, noteContent);
        statusSpan.textContent = 'Submitted to queue ✓';
        statusSpan.style.color = '#16a34a';
        textarea.value = '';
        ctx.set(`${sectionPath}.adminNotes`, '');
        setTimeout(() => {
          statusSpan.textContent = '';
          submitBtn.disabled = false;
        }, 3000);
      } catch (err) {
        statusSpan.textContent = `Error: ${err.message}`;
        statusSpan.style.color = '#dc2626';
        submitBtn.disabled = false;
      }
    };

    buttonDiv.appendChild(submitBtn);
    buttonDiv.appendChild(statusSpan);
    adminNotesDiv.appendChild(buttonDiv);
    container.appendChild(adminNotesDiv);
  }

  // Section renderers

  function renderAE(container, ctx) {
    const d = ctx.design.ae;
    const missing = window.Rules.missingFields('ae', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(checkboxField('Alternate resource economy', d.enabled, val => {
      ctx.set('ae.enabled', val);
    }));

    const greyed = !d.enabled;

    container.appendChild(textField('Name', d.name, val => ctx.set('ae.name', val), {greyed, missing: isMissing('ae.name')}));
    container.appendChild(textField('Acronym (single letter)', d.acronym, val => ctx.set('ae.acronym', val.substring(0, 1)), {greyed, missing: isMissing('ae.acronym')}));

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
        h('select', {
          className: isMissing(`ae.rows.${row.id}.kind`) ? 'sx-missing' : '',
          value: row.kind,
          onchange: e => ctx.set(`ae.rows.${row.id}.kind`, e.target.value)
        },
          h('option', {value: 'fixed'}, 'Fixed'),
          h('option', {value: 'variable'}, 'Variable')
        )
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`ae.rows.${row.id}.qty`) ? 'sx-missing' : '',
          type: 'number',
          value: row.qty != null ? row.qty : '',
          disabled: row.kind === 'variable',
          oninput: e => ctx.set(`ae.rows.${row.id}.qty`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`ae.rows.${row.id}.calc`) ? 'sx-missing' : '',
          type: 'text',
          value: row.calc || '',
          disabled: row.kind === 'fixed',
          oninput: e => ctx.set(`ae.rows.${row.id}.calc`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`ae.rows.${row.id}.desc`) ? 'sx-missing' : '',
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

    renderClaudeQA(container, ctx, 'ae');
    renderAdminNotes(container, ctx, 'ae');
  }

  function renderUFA(container, ctx) {
    const d = ctx.design.ufa;
    const missing = window.Rules.missingFields('ufa', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(textField('Name', d.name, val => ctx.set('ufa.name', val), {missing: isMissing('ufa.name')}));

    container.appendChild(selectField('Phase', d.phase, [
      'Setup', 'Action', 'Gather Power', 'Player Order', 'Doom'
    ], val => ctx.set('ufa.phase', val), {missing: isMissing('ufa.phase')}));

    container.appendChild(selectField('Type', d.type, window.Rules.SB_TYPES, val => ctx.set('ufa.type', val), {missing: isMissing('ufa.type')}));

    container.appendChild(checkboxField('Includes Fixed Numeric Cost?', d.hasCost, val => ctx.set('ufa.hasCost', val)));
    container.appendChild(numberField('Fixed Numeric Cost', d.cost, val => ctx.set('ufa.cost', val), {greyed: !d.hasCost, min: 0, missing: isMissing('ufa.cost')}));

    container.appendChild(checkboxField('Includes Fixed Numeric Effect?', d.hasEffect, val => ctx.set('ufa.hasEffect', val)));
    container.appendChild(numberField('Fixed Numeric Effect', d.effect, val => ctx.set('ufa.effect', val), {greyed: !d.hasEffect, min: 0, missing: isMissing('ufa.effect')}));

    const textLen = 200;
    container.appendChild(textField('Text', d.text, val => ctx.set('ufa.text', val), {rows: Math.max(3, Math.ceil(textLen / 45)), missing: isMissing('ufa.text')}));

    renderClaudeQA(container, ctx, 'ufa');
    renderAdminNotes(container, ctx, 'ufa');
  }

  function renderSetup(container, ctx) {
    const d = ctx.design.setup;
    const ref = ctx.reference || {};
    const missing = window.Rules.missingFields('setup', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(textField('Text for faction card', d.text, val => ctx.set('setup.text', val), {rows: 4, missing: isMissing('setup.text')}));

    container.appendChild(selectField('Location type', d.location, ['single', 'multi'], val => {
      ctx.set('setup.location', val);
    }, {placeholder: '-- Select --', missing: isMissing('setup.location')}));

    const isSingle = d.location === 'single';
    const isMulti = d.location === 'multi';

    container.appendChild(selectField('Earth Region', d.earthRegion, ref.earth33Regions || [], val => ctx.set('setup.earthRegion', val), {
      greyed: !isSingle,
      missing: isMissing('setup.earthRegion')
    }));

    container.appendChild(selectField('Library Region', d.libraryRegion, ref.library33Regions || [], val => ctx.set('setup.libraryRegion', val), {
      greyed: !isSingle,
      missing: isMissing('setup.libraryRegion')
    }));

    const constraintsDiv = h('div', {style: isMulti ? '' : 'opacity: 0.4; pointer-events: none;'});
    constraintsDiv.appendChild(h('h3', {}, 'Constraints'));

    // Doc: leave out factions with pre-set start regions; start with the first one that has a choice
    const fixedNames = new Set((ref.fixedStartFactions || []).map(f => f.name));
    const placementOrder = (ref.placementOrder || []).filter(f => !fixedNames.has(f.name));
    const followsOptions = [{value: '0', label: '0. Base Factions'}]
      .concat(placementOrder.map((f, i) => ({value: String(i + 1), label: `${i + 1}. ${f.name}`})));
    constraintsDiv.appendChild(selectField('Follows faction', d.constraints.follows, followsOptions, val => ctx.set('setup.constraints.follows', val), {
      placeholder: '-- Select --',
      missing: isMissing('setup.constraints.follows')
    }));

    constraintsDiv.appendChild(checkboxField('Water', d.constraints.water, val => ctx.set('setup.constraints.water', val)));
    constraintsDiv.appendChild(checkboxField('Land', d.constraints.land, val => ctx.set('setup.constraints.land', val)));
    constraintsDiv.appendChild(checkboxField('Empty regions with faction glyphs', d.constraints.emptyFactionGlyph, val => ctx.set('setup.constraints.emptyFactionGlyph', val)));

    // The three map glyphs, as printed on the Yellow Sign spellbook requirements
    const glyphImg = name => h('img', {src: `glyphs/${name}.png`, alt: name, title: name,
      style: 'height: 24px; vertical-align: middle; margin: 0 4px;'});
    constraintsDiv.appendChild(checkboxField([glyphImg('thorns'), 'Thorn glyph'], d.constraints.thorn, val => ctx.set('setup.constraints.thorn', val)));
    constraintsDiv.appendChild(checkboxField([glyphImg('dragon'), 'Dragon glyph'], d.constraints.dragon, val => ctx.set('setup.constraints.dragon', val)));
    constraintsDiv.appendChild(checkboxField([glyphImg('chevron'), 'Chevron glyph'], d.constraints.chevron, val => ctx.set('setup.constraints.chevron', val)));
    constraintsDiv.appendChild(checkboxField(['None of the 3 glyphs ', glyphImg('thorns'), glyphImg('dragon'), glyphImg('chevron')], d.constraints.noneOf3, val => ctx.set('setup.constraints.noneOf3', val)));

    constraintsDiv.appendChild(selectField('Proximity to other factions', d.constraints.proximity, ['adjacent', 'as far as possible', 'N/A'], val => ctx.set('setup.constraints.proximity', val)));

    constraintsDiv.appendChild(textField('Custom', d.constraints.custom, val => ctx.set('setup.constraints.custom', val), {rows: 2}));

    container.appendChild(constraintsDiv);

    const gateMissing = isMissing('setup.gate');
    container.appendChild(h('div', {className: 'sx-field'},
      h('label', {}, 'Gate'),
      h('label', {},
        h('input', {className: gateMissing ? 'sx-missing' : '', type: 'radio', name: 'gate', checked: d.gate === true, onchange: () => ctx.set('setup.gate', true)}),
        ' Yes'
      ),
      h('label', {style: 'margin-left: 16px;'},
        h('input', {className: gateMissing ? 'sx-missing' : '', type: 'radio', name: 'gate', checked: d.gate === false, onchange: () => ctx.set('setup.gate', false)}),
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
        h('input', {
          className: isMissing(`setup.units.${unit.id}.name`) ? 'sx-missing' : '',
          type: 'text',
          value: unit.name || '',
          oninput: e => ctx.set(`setup.units.${unit.id}.name`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`setup.units.${unit.id}.qty`) ? 'sx-missing' : '',
          type: 'number',
          value: unit.qty != null ? unit.qty : '',
          oninput: e => ctx.set(`setup.units.${unit.id}.qty`, e.target.value ? parseInt(e.target.value) : null)
        })
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

    container.appendChild(numberField('Starting power', d.power, val => ctx.set('setup.power', val), {min: 0, missing: isMissing('setup.power')}));

    const aeEnabled = ctx.design.ae && ctx.design.ae.enabled;
    const aeName = aeEnabled && ctx.design.ae.name ? ctx.design.ae.name : 'alternate economy';
    container.appendChild(numberField('Starting ' + aeName, d.aeStart, val => ctx.set('setup.aeStart', val), {greyed: !aeEnabled, min: 0, missing: isMissing('setup.aeStart')}));

    renderClaudeQA(container, ctx, 'setup');
    renderAdminNotes(container, ctx, 'setup');
  }

  function renderUnits(container, ctx) {
    const d = ctx.design.units;
    const ref = ctx.reference || {};
    // ctx.neutral: a stand-alone unit from My Units. One unit only, and nothing that belongs to a
    // faction (cultists, buildings, gates, its spellbooks, adding or deleting units).
    const neutral = !!ctx.neutral;
    const sbRows = ctx.design.sb ? ctx.design.sb.rows : [];
    const sbStatus = neutral ? null : window.Rules.status('sb', ctx.design);
    const unitTypes = neutral ? window.Rules.NEUTRAL_UNIT_TYPES : window.Rules.UNIT_TYPES;
    // Neutral units are ready with just a name, a type and (if ticked) the special ability
    const missing = neutral ? window.Rules.missingFields('units', ctx.design)
      .filter(p => /\.(name|type|abilityText)$/.test(p)) : window.Rules.missingFields('units', ctx.design);
    const isMissing = path => missing.includes(path);

    d.rows.slice(0, neutral ? 1 : d.rows.length).forEach((unit, idx) => {
      const unitDiv = h('div', {style: 'margin-bottom: 40px; padding: 16px; border: 2px solid #444;'});
      if (!neutral) unitDiv.appendChild(h('h3', {}, `Unit ${idx + 1}`));

      unitDiv.appendChild(selectField('Type', unit.type, unitTypes, val => {
        ctx.set(`units.rows.${unit.id}.type`, val);
      }, {missing: isMissing(`units.rows.${unit.id}.type`)}));

      unitDiv.appendChild(textField('Name', unit.name, val => ctx.set(`units.rows.${unit.id}.name`, val), {missing: isMissing(`units.rows.${unit.id}.name`)}));

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
      const silMissing = isMissing(`units.rows.${unit.id}.silhouette`);
      const silDiv = h('div', {className: 'sx-field'});
      silDiv.appendChild(h('label', {}, 'Silhouette'));
      if (unit.silhouette) {
        const thumb = h('img', {
          src: ctx.imgUrl(unit.silhouette),
          className: 'sx-img-thumb' + (silMissing ? ' sx-missing' : ''),
          onclick: () => openUnitSilhouetteViewer(unit, ctx)
        });
        silDiv.appendChild(thumb);
      } else {
        const uploadBtn = h('div', {
          className: 'sx-img-thumb sx-empty' + (silMissing ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`units.rows.${unit.id}.silhouette`, id);
          }
        }, 'Click to upload');
        silDiv.appendChild(uploadBtn);
        const libraryBtn = h('button', {
          className: 'sx-btn',
          style: 'display: block; margin-top: 8px; font-size: 12px; padding: 4px 8px;',
          onclick: async () => {
            const id = await ctx.pickLibraryImage();
            if (id) {
              ctx.set(`units.rows.${unit.id}.silhouette`, id);
              ctx.rerender();
            }
          }
        }, 'CW / Necro');
        silDiv.appendChild(libraryBtn);
      }
      unitDiv.appendChild(silDiv);

      unitDiv.appendChild(numberField('Quantity', unit.qty, val => ctx.set(`units.rows.${unit.id}.qty`, val), {min: 1, max: 20, missing: isMissing(`units.rows.${unit.id}.qty`)}));

      // Cost
      unitDiv.appendChild(selectField('Cost Type', unit.costType, window.Rules.COST_TYPES, val => {
        ctx.set(`units.rows.${unit.id}.costType`, val);
      }, {missing: isMissing(`units.rows.${unit.id}.costType`)}));

      if (unit.costType === 'Fixed') {
        unitDiv.appendChild(numberField('Cost', unit.cost, val => ctx.set(`units.rows.${unit.id}.cost`, val), {min: 0, missing: isMissing(`units.rows.${unit.id}.cost`)}));
      } else if (unit.costType === 'Variable') {
        unitDiv.appendChild(textField('Cost calculation', unit.costCalc, val => ctx.set(`units.rows.${unit.id}.costCalc`, val), {rows: 2, missing: isMissing(`units.rows.${unit.id}.costCalc`)}));
      } else if (unit.costType === 'Awakening') {
        unitDiv.appendChild(textField('Requirements/process', unit.awakenReq, val => ctx.set(`units.rows.${unit.id}.awakenReq`, val), {rows: 3, missing: isMissing(`units.rows.${unit.id}.awakenReq`)}));
        unitDiv.appendChild(numberField('Power cost', unit.awakenPower, val => ctx.set(`units.rows.${unit.id}.awakenPower`, val), {min: 0, missing: isMissing(`units.rows.${unit.id}.awakenPower`)}));
        unitDiv.appendChild(textField('Region placement', unit.awakenRegion, val => ctx.set(`units.rows.${unit.id}.awakenRegion`, val), {missing: isMissing(`units.rows.${unit.id}.awakenRegion`)}));
      }

      // Combat
      unitDiv.appendChild(selectField('Combat type', unit.combatType, window.Rules.COMBAT_TYPES, val => {
        ctx.set(`units.rows.${unit.id}.combatType`, val);
      }, {missing: isMissing(`units.rows.${unit.id}.combatType`)}));

      const combatGreyed = unit.combatType === 'N/A';

      if (unit.combatType === 'Fixed Dice') {
        unitDiv.appendChild(numberField('Dice', unit.dice, val => ctx.set(`units.rows.${unit.id}.dice`, val), {min: 0, missing: isMissing(`units.rows.${unit.id}.dice`)}));
      } else if (unit.combatType === 'Variable Dice') {
        unitDiv.appendChild(textField('Dice calculation', unit.diceCalc, val => ctx.set(`units.rows.${unit.id}.diceCalc`, val), {rows: 2, missing: isMissing(`units.rows.${unit.id}.diceCalc`)}));
      } else if (unit.combatType === 'Fixed Results') {
        unitDiv.appendChild(numberField('Pains', unit.pains, val => ctx.set(`units.rows.${unit.id}.pains`, val), {min: 0, missing: isMissing(`units.rows.${unit.id}.pains`)}));
        unitDiv.appendChild(numberField('Kills', unit.kills, val => ctx.set(`units.rows.${unit.id}.kills`, val), {min: 0, missing: isMissing(`units.rows.${unit.id}.kills`)}));
      } else if (unit.combatType === 'Variable Results') {
        unitDiv.appendChild(textField('Results calculation', unit.resultsCalc, val => ctx.set(`units.rows.${unit.id}.resultsCalc`, val), {rows: 2, missing: isMissing(`units.rows.${unit.id}.resultsCalc`)}));
      }

      // Related Spellbooks
      if (!neutral) {
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
      }

      // Special ability: name is optional, only text is required when the box is ticked
      const hasAbility = window.Rules.unitHasAbility(unit);
      unitDiv.appendChild(checkboxField('Special Ability', hasAbility, val => ctx.set(`units.rows.${unit.id}.hasAbility`, val)));
      if (hasAbility) {
        unitDiv.appendChild(textField('Special Ability Name (optional)', unit.abilityName, val => ctx.set(`units.rows.${unit.id}.abilityName`, val)));
        unitDiv.appendChild(textField('Special Ability Text', unit.abilityText, val => ctx.set(`units.rows.${unit.id}.abilityText`, val), {rows: 4, missing: isMissing(`units.rows.${unit.id}.abilityText`)}));
      }

      // Spellbook for iGOO / Elder God neutral units
      if (neutral && (unit.type === 'Great Old One' || unit.type === 'Elder God')) {
        // Default spellbook structure in memory if missing (backward compatibility)
        const defaultSb = {enabled: false, requirement: {text: '', hasNum: false, num: null}, book: {name: '', type: null, cost: 0, hasEffect: false, effect: null, text: ''}};
        const sb = unit.spellbook || defaultSb;

        // Helper to get current spellbook or default
        const getCurrentSb = () => unit.spellbook || defaultSb;

        unitDiv.appendChild(checkboxField('Spellbook', sb.enabled, val => {
          // Build new object from current state to avoid stale closures
          const current = getCurrentSb();
          ctx.set(`units.rows.${unit.id}.spellbook`, {
            enabled: val,
            requirement: {...current.requirement},
            book: {...current.book}
          });
        }));

        if (sb.enabled) {
          const sbDiv = h('div', {style: 'margin: 20px 0; padding: 16px; border: 1px solid #666; background: #1a1a1a;'});

          // Spellbook Requirement - match faction editor labels exactly
          sbDiv.appendChild(h('h4', {style: 'margin: 0 0 12px 0;'}, 'Spellbook Requirement'));
          sbDiv.appendChild(textField('Spellbook Requirement Text', sb.requirement.text, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              requirement: {...current.requirement, text: val}
            });
          }, {rows: 3}));
          sbDiv.appendChild(checkboxField('Includes Fixed Numeric Cost or Effect?', sb.requirement.hasNum, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              requirement: {...current.requirement, hasNum: val}
            });
          }));
          sbDiv.appendChild(numberField('Fixed Numeric Cost or Effect', sb.requirement.num, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              requirement: {...current.requirement, num: val}
            });
          }, {greyed: !sb.requirement.hasNum}));

          // Spellbook - match faction editor labels exactly
          sbDiv.appendChild(h('h4', {style: 'margin: 20px 0 12px 0;'}, 'Spellbook'));
          sbDiv.appendChild(textField('Name', sb.book.name, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, name: val}
            });
          }));
          sbDiv.appendChild(selectField('Type', sb.book.type, window.Rules.SB_TYPES, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, type: val}
            });
          }));
          sbDiv.appendChild(numberField('Cost', sb.book.cost, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, cost: val}
            });
          }, {min: 0}));
          sbDiv.appendChild(checkboxField('Includes Fixed Numeric Effect?', sb.book.hasEffect, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, hasEffect: val}
            });
          }));
          sbDiv.appendChild(numberField('Fixed Numeric Effect', sb.book.effect, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, effect: val}
            });
          }, {greyed: !sb.book.hasEffect}));
          sbDiv.appendChild(textField('Text', sb.book.text, val => {
            const current = getCurrentSb();
            ctx.set(`units.rows.${unit.id}.spellbook`, {
              ...current,
              book: {...current.book, text: val}
            });
          }, {rows: 4}));

          unitDiv.appendChild(sbDiv);
        }
      }

      if (idx >= 3 && !neutral) {
        unitDiv.appendChild(h('button', {className: 'sx-btn', onclick: async () => {
          const confirmed = await ctx.confirm('Are you sure you want to delete this unit?', 'Yes - delete', 'No - cancel');
          if (confirmed) ctx.deleteRow('units.rows', unit.id);
        }}, 'Delete this unit'));
      }

      container.appendChild(unitDiv);
    });

    if (neutral) return;
    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newUnit = window.Rules.blankRow('units.rows');
      ctx.addRow('units.rows', newUnit);
    }}, 'Add unit'));

    renderClaudeQA(container, ctx, 'units');
    renderAdminNotes(container, ctx, 'units');
  }

  // In-game box (map pixels, Earth unitScale 1.0) each unit type is drawn in, from the type's
  // default unit in CthulhuWarsSolo.scala: [x offset, y offset, width, height] from the unit's spot.
  const UNIT_MAP_BOX = {
    'Cultist':       [-17, -54, 40, 59],    // gc-acolyte
    'Monster':       [-35, -75, 70, 85],    // n-dimensional-shambler
    'Terror':        [-48, -109, 95, 116],  // n-hound-of-tindalos
    'Great Old One': [-52, -112, 105, 122], // n-cthugha
    'Elder God':     [-64, -210, 128, 210], // bb-bastet
    'Building':      [-39, -90, 78, 110],   // an-cathedral
    'Custom Gate':   [-38, -38, 76, 76]     // gate
  };

  function openUnitMapViewer(unit, ctx, defaultArt) {
    const ref = ctx.reference || {};
    const mapData = ref.earthMap3W || {url: '', w: 1791, h: 894, southPacific: {x: 540, y: 830}};
    const box = UNIT_MAP_BOX[unit.type] || UNIT_MAP_BOX['Cultist'];
    const MARGIN = 12;   // the game leaves 12 map pixels round the board

    let scale = unit.mapScale || 1.0;
    const canvas = h('canvas', {style: 'display: block; margin: 0 auto;'});
    const canvasCtx = canvas.getContext('2d');

    const mapImg = new Image();
    mapImg.src = mapData.url;

    const unitImg = new Image();
    const displayImage = unit.mapImage || (defaultArt ? defaultArt.url : null);
    if (displayImage) {
      unitImg.src = displayImage.startsWith('http') ? displayImage : ctx.imgUrl(displayImage);
    }

    // Tint like the game's getTintedAsset: "color" fill, then cut back to the art's own shape
    // (drawn on a canvas of its own, so the map underneath is never coloured)
    function unitArt() {
      const color = ctx.design.meta && ctx.design.meta.color;
      if (!color) return unitImg;
      const c = document.createElement('canvas');
      c.width = unitImg.naturalWidth;
      c.height = unitImg.naturalHeight;
      const g = c.getContext('2d');
      g.drawImage(unitImg, 0, 0);
      g.globalCompositeOperation = 'color';
      g.fillStyle = color;
      g.fillRect(0, 0, c.width, c.height);
      g.globalCompositeOperation = 'destination-in';
      g.drawImage(unitImg, 0, 0);
      return c;
    }

    // Fit the board to the screen the way the game does: wide screens get the map as is,
    // tall (phone) screens get it turned a quarter turn with the units kept upright
    let horizontal = true, k = 1;
    function layout() {
      if (!canvas.isConnected) { window.removeEventListener('resize', layout); return; }
      const availW = Math.max(200, window.innerWidth - 40);
      const availH = Math.max(200, window.innerHeight - 40 - buttons.offsetHeight - 80);
      horizontal = availH <= availW;
      const boardW = (horizontal ? mapData.w : mapData.h) + 2 * MARGIN;
      const boardH = (horizontal ? mapData.h : mapData.w) + 2 * MARGIN;
      k = Math.min(availW / boardW, availH / boardH);
      const dpr = window.devicePixelRatio || 1;
      canvas.style.width = Math.floor(boardW * k) + 'px';
      canvas.style.height = Math.floor(boardH * k) + 'px';
      canvas.width = Math.floor(boardW * k * dpr);
      canvas.height = Math.floor(boardH * k * dpr);
      draw();
    }

    function draw() {
      const dpr = window.devicePixelRatio || 1;
      canvasCtx.setTransform(1, 0, 0, 1, 0, 0);
      canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
      canvasCtx.setTransform(k * dpr, 0, 0, k * dpr, 0, 0);
      canvasCtx.translate(MARGIN, MARGIN);
      if (mapImg.complete && mapImg.naturalWidth) {
        if (horizontal) {
          canvasCtx.drawImage(mapImg, 0, 0);
        } else {
          canvasCtx.save();
          canvasCtx.translate(mapData.h, 0);
          canvasCtx.rotate(Math.PI / 2);
          canvasCtx.drawImage(mapImg, 0, 0);
          canvasCtx.restore();
        }
      }
      if (unitImg.complete && unitImg.naturalWidth) {
        // Same spot as the game's gateXY: turned boards move (x, y) to (map height - y, x)
        const sp = mapData.southPacific;
        const px = horizontal ? sp.x : mapData.h - sp.y;
        const py = horizontal ? sp.y : sp.x;
        // Grow/Shrink scale the type's box about the unit's spot, like the game's scaledProto;
        // the art fills the box (keeping its shape), centred and standing on the box's bottom edge
        const bw = box[2] * scale, bh = box[3] * scale;
        const bx = px + box[0] * scale, by = py + box[1] * scale;
        const fit = Math.min(bw / unitImg.naturalWidth, bh / unitImg.naturalHeight);
        const w = unitImg.naturalWidth * fit, ht = unitImg.naturalHeight * fit;
        canvasCtx.drawImage(unitArt(), bx + (bw - w) / 2, by + bh - ht, w, ht);
      }
    }

    mapImg.onload = draw;
    unitImg.onload = draw;
    window.addEventListener('resize', layout);
    const close = () => { window.removeEventListener('resize', layout); ctx.closeOverlay(); };

    const buttons = h('div', {className: 'sx-overlay-buttons', style: 'position: static; margin-bottom: 10px;'},
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
      h('button', {className: 'sx-btn', onclick: async () => {
        const id = await ctx.pickLibraryImage();
        if (id) {
          ctx.set(`units.rows.${unit.id}.mapImage`, id);
          unitImg.src = ctx.imgUrl(id);
        }
      }}, 'CW / Necro'),
      h('button', {className: 'sx-btn', onclick: () => {
        ctx.set(`units.rows.${unit.id}.mapScale`, scale);
        close();
      }}, 'Done')
    );

    const content = h('div', {}, buttons, canvas);
    ctx.openOverlay(content);
    layout();
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
    if (window.Rules.unitHasAbility(unit) && unit.abilityText) {
      fields.push(unit.abilityName ? `${unit.abilityName}: ${unit.abilityText}` : `Special Ability: ${unit.abilityText}`);
    }

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
      h('button', {className: 'sx-btn', onclick: async () => {
        const id = await ctx.pickLibraryImage();
        if (id) {
          ctx.set(`units.rows.${unit.id}.silhouette`, id);
          ctx.closeOverlay();
          ctx.rerender();
        }
      }}, 'CW / Necro'),
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
    const missing = window.Rules.missingFields('sbr', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(textField('Multi-requirement text', d.multiText, val => ctx.set('sbr.multiText', val), {rows: 3}));

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {},
      h('tr', {},
        h('th', {}, 'Spellbook Requirement Text'),
        h('th', {}, 'Shortened Card Text (abbreviated)'),
        h('th', {style: 'width: 200px;'}, 'Includes Fixed Numeric Cost or Effect?'),
        h('th', {style: 'width: 150px;'}, 'Fixed Numeric Cost or Effect')
      )
    ));

    const tbody = h('tbody', {});
    d.rows.forEach(row => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`sbr.rows.${row.id}.text`) ? 'sx-missing' : '',
          value: row.text || '',
          rows: 3,
          oninput: e => ctx.set(`sbr.rows.${row.id}.text`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`sbr.rows.${row.id}.shortText`) ? 'sx-missing' : '',
          value: row.shortText || '',
          rows: 3,
          placeholder: 'Brief version for faction card display...',
          oninput: e => ctx.set(`sbr.rows.${row.id}.shortText`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasNum, onchange: e => ctx.set(`sbr.rows.${row.id}.hasNum`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`sbr.rows.${row.id}.num`) ? 'sx-missing' : '',
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

    renderClaudeQA(container, ctx, 'sbr');
    renderAdminNotes(container, ctx, 'sbr');
  }

  function renderSB(container, ctx) {
    const d = ctx.design.sb;
    const R = window.Rules;
    const missing = R.missingFields('sb', ctx.design);
    const isMissing = path => missing.includes(path);
    // 2 sided: a spellbook gets a side A and a side B, each with its own name, type, cost, effect and text.
    // "All 2 sided" sets every spellbook; each spellbook's own box can then flip it back to 1 sided.
    const two = R.sbAnyTwo(d);
    const allTwo = d.rows.length > 0 && d.rows.every(r => R.sbTwo(d, r));
    const ensureSideBImages = () => {
      if (!ctx.design.sbImagesB) ctx.set('sbImagesB', {mode: null, all: null, each: [null, null, null, null, null, null]});
    };
    container.appendChild(checkboxField('All 2 sided (every spellbook has a side A and a side B)', allTwo, val => {
      if (val) ensureSideBImages();
      ctx.set('sb.twoSided', val);
      d.rows.forEach(r => ctx.set(`sb.rows.${r.id}.twoSided`, val));
    }));
    const setRowTwo = (row, val) => {
      // Pin every spellbook's current setting first, so changing "All 2 sided" below can't flip the others
      d.rows.forEach(r => { if (r.twoSided == null) ctx.set(`sb.rows.${r.id}.twoSided`, R.sbTwo(d, r)); });
      if (val) ensureSideBImages();
      ctx.set(`sb.rows.${row.id}.twoSided`, val);
      ctx.set('sb.twoSided', d.rows.every(r => R.sbTwo(d, r)));
    };

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    const rowSides = r => R.sbTwo(d, r) ? ['', 'B'] : [''];
    // Dual powers: a side split into power 1 and power 2, each with its own name, type, cost, effect and text
    const anyDual = d.rows.some(r => rowSides(r).some(sd => r['dual' + sd]));
    const grouped = true;  // the Spellbook column holds each spellbook's own "2 sided" box
    table.appendChild(h('thead', {},
      h('tr', {},
        grouped ? h('th', {style: 'width: 100px;'}, 'Spellbook') : null,
        two ? h('th', {style: 'width: 60px;'}, 'Side') : null,
        h('th', {style: 'width: 70px;'}, 'Dual powers?'),
        anyDual ? h('th', {style: 'width: 60px;'}, 'Power') : null,
        h('th', {}, 'Name'),
        h('th', {}, 'Type'),
        h('th', {style: 'width: 100px;'}, 'Cost'),
        h('th', {style: 'width: 150px;'}, 'Includes Fixed Numeric Effect?'),
        h('th', {style: 'width: 100px;'}, 'Fixed Numeric Effect'),
        h('th', {}, 'Text'),
        h('th', {}, '')
      )
    ));

    // One side's (or one power's) cells. sfx = '' side A (or the only side), 'B' side B, '2' / 'B2' power 2
    function sideCells(tr, row, sfx) {
      const f = name => `sb.rows.${row.id}.${name}${sfx}`;
      const v = name => row[name + sfx];
      // Name and Text boxes at least 3x their old phone width (about 51px and 38px)
      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(f('name')) ? 'sx-missing' : '',
          type: 'text',
          value: v('name') || '',
          style: 'min-width: 155px;',
          oninput: e => ctx.set(f('name'), e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('select', {
          className: isMissing(f('type')) ? 'sx-missing' : '',
          value: v('type') || '',
          onchange: e => ctx.set(f('type'), e.target.value || null)
        },
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
          className: isMissing(f('effect')) ? 'sx-missing' : '',
          type: 'number',
          value: v('effect') != null ? v('effect') : '',
          disabled: !v('hasEffect'),
          oninput: e => ctx.set(f('effect'), e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(f('text')) ? 'sx-missing' : '',
          value: v('text') || '',
          rows: 3,
          style: 'min-width: 160px;',
          oninput: e => ctx.set(f('text'), e.target.value)
        })
      ));
    }

    const tbody = h('tbody', {});
    d.rows.forEach((row, idx) => {
      // sfx per table row: '' side A (or only side), 'B' side B, then '2' / 'B2' for power 2 of a dual powers side
      const sides = rowSides(row);
      const parts = sides.map(sd => row['dual' + sd] ? [sd, sd + '2'] : [sd]);
      const total = parts.reduce((n, p) => n + p.length, 0);
      let first = true;
      const trs = [];
      parts.forEach((sideParts, si) => {
        const sd = sides[si];
        sideParts.forEach((sfx, pi) => {
          const tr = h('tr', {});
          if (first && grouped) tr.appendChild(h('td', {rowSpan: total},
            h('div', {style: 'font-weight: bold;'}, `Spellbook ${idx + 1}`),
            // Label on the left; the checkbox keeps its own size (the table's 100% input width pushed it into the next column)
            h('label', {style: 'display: flex; align-items: center; gap: 4px; margin-top: 4px; font-size: 0.9em; white-space: nowrap;'},
              '2 sided',
              h('input', {type: 'checkbox', checked: R.sbTwo(d, row), title: 'Give this spellbook a side A and a side B',
                style: 'width: auto; margin: 0;', onchange: e => setRowTwo(row, e.target.checked)}))));
          if (pi === 0) {
            if (two) tr.appendChild(h('td', {rowSpan: sideParts.length}, sides.length < 2 ? '1 sided' : sd === 'B' ? 'Side B' : 'Side A'));
            tr.appendChild(h('td', {rowSpan: sideParts.length, style: 'text-align: center;'},
              h('input', {type: 'checkbox', checked: !!row['dual' + sd], title: 'Split this side into power 1 and power 2',
                onchange: e => ctx.set(`sb.rows.${row.id}.dual${sd}`, e.target.checked)})));
          }
          if (anyDual) tr.appendChild(h('td', {}, sideParts.length > 1 ? `Power ${pi + 1}` : ''));
          sideCells(tr, row, sfx);
          if (first) {
            if (d.rows.length > 6) {
              tr.appendChild(h('td', {rowSpan: total},
                h('button', {onclick: async () => {
                  const confirmed = await ctx.confirm('Are you sure you want to delete this spellbook?', 'Yes - delete', 'No - cancel');
                  if (confirmed) ctx.deleteRow('sb.rows', row.id);
                }}, 'Delete')
              ));
            } else {
              tr.appendChild(h('td', {rowSpan: total}));
            }
          }
          first = false;
          trs.push(tr);
        });
      });
      if (grouped) trs[trs.length - 1].style.borderBottom = '3px solid #000';
      trs.forEach(tr => tbody.appendChild(tr));
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankRow('sb.rows');
      ctx.addRow('sb.rows', newRow);
    }}, 'Add row'));

    renderClaudeQA(container, ctx, 'sb');
    renderAdminNotes(container, ctx, 'sb');
  }

  function renderRegion(container, ctx) {
    const d = ctx.design.region;
    const missing = window.Rules.missingFields('region', ctx.design);
    const isMissing = path => missing.includes(path);

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
        h('input', {
          className: isMissing(`region.rows.${row.id}.name`) ? 'sx-missing' : '',
          type: 'text',
          value: row.name || '',
          oninput: e => ctx.set(`region.rows.${row.id}.name`, e.target.value)
        })
      ));

      const imgTd = h('td', {});
      const imgMissing = isMissing(`region.rows.${row.id}.image`);
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb' + (imgMissing ? ' sx-missing' : ''),
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`region.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty' + (imgMissing ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`region.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`region.rows.${row.id}.restrictions`) ? 'sx-missing' : '',
          value: row.restrictions || '',
          rows: 2,
          oninput: e => ctx.set(`region.rows.${row.id}.restrictions`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`region.rows.${row.id}.adjacency`) ? 'sx-missing' : '',
          value: row.adjacency || '',
          rows: 2,
          oninput: e => ctx.set(`region.rows.${row.id}.adjacency`, e.target.value)
        })
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

    renderClaudeQA(container, ctx, 'region');
    renderAdminNotes(container, ctx, 'region');
  }

  function renderTokens(container, ctx) {
    const d = ctx.design.tokens;
    const missing = window.Rules.missingFields('tokens', ctx.design);
    const isMissing = path => missing.includes(path);

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
        h('input', {
          className: isMissing(`tokens.rows.${row.id}.name`) ? 'sx-missing' : '',
          type: 'text',
          value: row.name || '',
          oninput: e => ctx.set(`tokens.rows.${row.id}.name`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`tokens.rows.${row.id}.qty`) ? 'sx-missing' : '',
          type: 'number',
          value: row.qty != null ? row.qty : '',
          oninput: e => ctx.set(`tokens.rows.${row.id}.qty`, e.target.value ? parseInt(e.target.value) : null)
        })
      ));

      const imgTd = h('td', {});
      const imgMissing = isMissing(`tokens.rows.${row.id}.image`);
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb' + (imgMissing ? ' sx-missing' : ''),
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`tokens.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty' + (imgMissing ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`tokens.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`tokens.rows.${row.id}.placement`) ? 'sx-missing' : '',
          value: row.placement || '',
          rows: 2,
          oninput: e => ctx.set(`tokens.rows.${row.id}.placement`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`tokens.rows.${row.id}.effects`) ? 'sx-missing' : '',
          value: row.effects || '',
          rows: 2,
          oninput: e => ctx.set(`tokens.rows.${row.id}.effects`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasEffect, onchange: e => ctx.set(`tokens.rows.${row.id}.hasEffect`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`tokens.rows.${row.id}.effect`) ? 'sx-missing' : '',
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

    renderClaudeQA(container, ctx, 'tokens');
    renderAdminNotes(container, ctx, 'tokens');
  }

  function renderCustom(container, ctx) {
    const d = ctx.design.custom;
    const missing = window.Rules.missingFields('custom', ctx.design);
    const isMissing = path => missing.includes(path);

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
        h('input', {
          className: isMissing(`custom.rows.${row.id}.name`) ? 'sx-missing' : '',
          type: 'text',
          value: row.name || '',
          oninput: e => ctx.set(`custom.rows.${row.id}.name`, e.target.value)
        })
      ));

      const imgTd = h('td', {});
      const imgMissing = isMissing(`custom.rows.${row.id}.image`);
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb' + (imgMissing ? ' sx-missing' : ''),
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`custom.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty' + (imgMissing ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`custom.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`custom.rows.${row.id}.placement`) ? 'sx-missing' : '',
          value: row.placement || '',
          rows: 2,
          oninput: e => ctx.set(`custom.rows.${row.id}.placement`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`custom.rows.${row.id}.usage`) ? 'sx-missing' : '',
          value: row.usage || '',
          rows: 2,
          oninput: e => ctx.set(`custom.rows.${row.id}.usage`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('textarea', {
          className: isMissing(`custom.rows.${row.id}.effects`) ? 'sx-missing' : '',
          value: row.effects || '',
          rows: 2,
          oninput: e => ctx.set(`custom.rows.${row.id}.effects`, e.target.value)
        })
      ));

      tr.appendChild(h('td', {},
        h('input', {type: 'checkbox', checked: row.hasNum, onchange: e => ctx.set(`custom.rows.${row.id}.hasNum`, e.target.checked)})
      ));

      tr.appendChild(h('td', {},
        h('input', {
          className: isMissing(`custom.rows.${row.id}.num`) ? 'sx-missing' : '',
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

    renderClaudeQA(container, ctx, 'custom');
    renderAdminNotes(container, ctx, 'custom');
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
          label: window.Rules.sbTwo(ctx.design.sb, s) && s.nameB ? `${s.name} / ${s.nameB}` : s.name}));
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

      menuDiv.appendChild(selectField('Faction prompted', menu.prompted, ['Own', '1 Enemy', 'All enemies (turn order)', 'All enemies (at the same time)', 'All players (at the same time)', 'Any faction on their turn'], val => ctx.set(`menus.rows.${menu.id}.prompted`, val)));

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

    renderClaudeQA(container, ctx, 'menus');
    renderAdminNotes(container, ctx, 'menus');
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

  // Map section renderers

  function renderMapImages(container, ctx) {
    const d = ctx.design.images;
    const missing = window.Rules.missingMapFields('images', ctx.design);
    const isMissing = path => missing.includes(path);

    // Board images
    container.appendChild(h('h3', {}, 'Board Images'));

    const imagesDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Label'),
      h('th', {}, 'Image'),
      h('th', {}, '')
    )));

    const tbody = h('tbody', {});
    (d.items || []).forEach((item, idx) => {
      const tr = h('tr', {});
      tr.appendChild(h('td', {}, h('input', {
        type: 'text',
        value: item.label || '',
        oninput: e => ctx.set(`images.items.${item.id}.label`, e.target.value)
      })));

      const imgTd = h('td', {});
      if (item.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(item.image),
          className: 'sx-img-thumb',
          onclick: () => openImageEditor(item.image, ctx, id => ctx.set(`images.items.${item.id}.image`, id), 'card')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty' + (isMissing(`images.items.${item.id}.image`) ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('card');
            if (id) ctx.set(`images.items.${item.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this image?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('images.items', item.id);
      }}, 'Delete')));

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    imagesDiv.appendChild(table);
    container.appendChild(imagesDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newItem = window.Rules.blankMapRow('images.items');
      ctx.addRow('images.items', newItem);
    }}, 'Add image'));

    // Layout
    container.appendChild(h('h3', {style: 'margin-top: 24px;'}, 'Layout'));
    container.appendChild(selectField('Layout type', d.layout.type, [
      {value: 'single', label: 'Single image'},
      {value: 'side-by-side', label: 'Side by side (left to right)'},
      {value: 'stacked', label: 'Stacked (top to bottom)'},
      {value: 'grid', label: 'Grid'}
    ], val => ctx.set('images.layout.type', val)));

    if (d.layout.type === 'grid') {
      container.appendChild(numberField('Grid columns', d.layout.columns || 2, val => ctx.set('images.layout.columns', val), {min: 1, max: 8}));
    }
    container.appendChild(textField('Layout notes', d.layout.notes, val => ctx.set('images.layout.notes', val), {rows: 2}));

    // Regions
    container.appendChild(h('h3', {style: 'margin-top: 24px;'}, 'Regions'));

    const extractBtn = h('button', {className: 'sx-btn', onclick: async () => {
      const confirmed = await ctx.confirm('Extract region names and glyphs from the map images?', 'Yes - Extract', 'Cancel');
      if (!confirmed) return;
      extractBtn.disabled = true;
      try {
        await ctx.createRequest('extract', `Extract region names and glyphs for map ${ctx.map.name}`, {target: 'regions'});
        alert('Extract requested.');
      } catch (err) {
        alert('Request failed: ' + err.message);
      }
      extractBtn.disabled = false;
    }}, 'Extract Region Names and Glyphs');
    container.appendChild(extractBtn);

    const regionsDiv = h('div', {className: 'sx-table', style: 'margin-top: 16px;'});
    const regionsTable = h('table', {});
    const glyphNames = {gc: 'GC', cc: 'CC', bg: 'BG', ys: 'YS', dragon: 'Dragon', chevron: 'Chevron', thorn: 'Thorn'};
    const baseGlyphs = ['gc', 'cc', 'bg', 'ys', 'dragon', 'chevron', 'thorn'];
    const glyphFiles = {gc: 'gc-glyph.webp', cc: 'cc-glyph.webp', bg: 'bg-glyph.webp', ys: 'ys-glyph.webp',
      dragon: 'dragon.png', chevron: 'chevron.png', thorn: 'thorns.png'};
    const mapGlyphs = (ctx.design.glyphs && ctx.design.glyphs.rows) || [];

    regionsTable.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Name'),
      h('th', {}, 'Type'),
      ...baseGlyphs.map(g => h('th', {title: glyphNames[g]},
        h('img', {src: `glyphs/${glyphFiles[g]}`,
          style: 'height: 24px;', alt: glyphNames[g]}))),
      ...mapGlyphs.map(mg => h('th', {title: mg.name}, mg.image ? h('img', {src: ctx.imgUrl(mg.image), style: 'height: 24px;', alt: mg.name}) : mg.name)),
      h('th', {}, '')
    )));

    const regionsTbody = h('tbody', {});
    (d.regions.rows || []).forEach((region, idx) => {
      const tr = h('tr', {});
      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`images.regions.rows.${region.id}.name`) ? 'sx-missing' : '',
        type: 'text',
        value: region.name || '',
        oninput: e => ctx.set(`images.regions.rows.${region.id}.name`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('select', {
        value: region.type || 'Land',
        onchange: e => ctx.set(`images.regions.rows.${region.id}.type`, e.target.value)
      }, h('option', {value: 'Land'}, 'Land'), h('option', {value: 'Sea'}, 'Sea'))));

      const glyphs = region.glyphs || {};
      baseGlyphs.forEach(g => {
        tr.appendChild(h('td', {style: 'text-align: center;'}, h('input', {
          type: 'checkbox',
          checked: !!glyphs[g],
          onchange: e => ctx.set(`images.regions.rows.${region.id}.glyphs.${g}`, e.target.checked)
        })));
      });

      mapGlyphs.forEach(mg => {
        tr.appendChild(h('td', {style: 'text-align: center;'}, h('input', {
          type: 'checkbox',
          checked: !!glyphs[mg.id],
          onchange: e => ctx.set(`images.regions.rows.${region.id}.glyphs.${mg.id}`, e.target.checked)
        })));
      });

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this region?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('images.regions.rows', region.id);
      }}, 'Delete')));

      regionsTbody.appendChild(tr);
    });
    regionsTable.appendChild(regionsTbody);
    regionsDiv.appendChild(regionsTable);
    container.appendChild(regionsDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRegion = window.Rules.blankMapRow('images.regions.rows');
      ctx.addRow('images.regions.rows', newRegion);
    }}, 'Add region'));

    renderClaudeQA(container, ctx, 'images');
    renderAdminNotes(container, ctx, 'images');
  }

  function renderMapBitmaps(container, ctx) {
    const d = ctx.design.bitmaps;
    const regions = (ctx.design.images && ctx.design.images.regions && ctx.design.images.regions.rows) || [];
    const missing = window.Rules.missingMapFields('bitmaps', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(h('h3', {}, 'Placement Bitmaps'));
    container.appendChild(h('p', {}, 'Upload a bitmap for each map image. Click a pixel to assign that color to a region.'));

    (d.items || []).forEach((item, idx) => {
      const itemDiv = h('div', {style: 'margin: 24px 0; padding: 16px; border: 2px solid #444;'});
      itemDiv.appendChild(h('h4', {}, `Bitmap ${idx + 1}`));

      if (!item.image) {
        itemDiv.appendChild(h('button', {className: 'sx-btn', onclick: async () => {
          const id = await ctx.uploadImage('card');
          if (id) ctx.set(`bitmaps.items.${item.id}.image`, id);
        }}, 'Upload bitmap'));
      } else {
        const canvas = h('canvas', {style: 'border: 1px solid #666; display: block; max-width: 100%; cursor: crosshair;'});
        const img = new Image();
        img.onload = () => {
          canvas.width = img.width;
          canvas.height = img.height;
          const canvasCtx = canvas.getContext('2d');
          canvasCtx.drawImage(img, 0, 0);

          // Draw region labels at the centre of each assigned colour (computed once per bitmap load)
          const centroids = {};
          const colors = item.colors || {};
          if (Object.keys(colors).length) {
            const px = canvasCtx.getImageData(0, 0, canvas.width, canvas.height).data;
            const sums = {};
            for (let i = 0, n = 0; i < px.length; i += 4, n++) {
              const hex = '#' + [px[i], px[i + 1], px[i + 2]].map(v => v.toString(16).padStart(2, '0')).join('');
              const rid = colors[hex];
              if (!rid || px[i + 3] < 128) continue;
              const sm = sums[rid] || (sums[rid] = {x: 0, y: 0, c: 0});
              sm.x += n % canvas.width; sm.y += Math.floor(n / canvas.width); sm.c++;
            }
            Object.entries(sums).forEach(([rid, sm]) => { centroids[rid] = {x: sm.x / sm.c, y: sm.y / sm.c}; });
          }
          Object.entries(centroids).forEach(([rid, pos]) => {
            const region = regions.find(r => r.id === rid);
            if (region && region.name) {
              canvasCtx.fillStyle = '#fff';
              canvasCtx.strokeStyle = '#000';
              canvasCtx.lineWidth = 2;
              canvasCtx.font = `${Math.max(14, Math.round(canvas.width / 40))}px sans-serif`;
              canvasCtx.textAlign = 'center';
              canvasCtx.strokeText(region.name, pos.x, pos.y);
              canvasCtx.fillText(region.name, pos.x, pos.y);
            }
          });
        };
        img.src = ctx.imgUrl(item.image);

        canvas.onclick = async (e) => {
          const rect = canvas.getBoundingClientRect();
          const x = Math.floor((e.clientX - rect.left) * (canvas.width / rect.width));
          const y = Math.floor((e.clientY - rect.top) * (canvas.height / rect.height));

          const canvasCtx = canvas.getContext('2d');
          const imageData = canvasCtx.getImageData(0, 0, canvas.width, canvas.height);
          const pixelData = imageData.data;
          const idx = (y * canvas.width + x) * 4;
          const r = pixelData[idx];
          const g = pixelData[idx + 1];
          const b = pixelData[idx + 2];
          const color = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;

          // Show region picker
          const picker = h('div', {className: 'confirm-overlay'});
          const dialog = h('div', {className: 'confirm-dialog'});
          dialog.appendChild(h('h3', {}, `Assign color ${color} to:`));

          regions.forEach(region => {
            const btn = h('button', {
              className: 'sx-btn',
              style: 'display: block; width: 100%; margin: 8px 0;',
              onclick: () => {
                const colors = Object.assign({}, item.colors || {});
                colors[color] = region.id;
                ctx.set(`bitmaps.items.${item.id}.colors`, colors);
                picker.remove();
              }
            }, region.name || `Region ${regions.indexOf(region) + 1}`);
            dialog.appendChild(btn);
          });

          const noneBtn = h('button', {
            className: 'sx-btn',
            style: 'display: block; width: 100%; margin: 8px 0;',
            onclick: () => {
              const colors = Object.assign({}, item.colors || {});
              delete colors[color];
              ctx.set(`bitmaps.items.${item.id}.colors`, colors);
              picker.remove();
            }
          }, 'None');
          dialog.appendChild(noneBtn);

          const cancelBtn = h('button', {
            className: 'sx-btn',
            style: 'display: block; width: 100%; margin: 16px 0 0;',
            onclick: () => picker.remove()
          }, 'Cancel');
          dialog.appendChild(cancelBtn);

          picker.appendChild(dialog);
          document.body.appendChild(picker);
        };

        itemDiv.appendChild(canvas);

        const replaceBtn = h('button', {className: 'sx-btn', style: 'margin-top: 12px;', onclick: async () => {
          const id = await ctx.uploadImage('card');
          if (id) ctx.set(`bitmaps.items.${item.id}.image`, id);
        }}, 'Replace');
        itemDiv.appendChild(replaceBtn);

        const deleteBtn = h('button', {className: 'sx-btn danger', style: 'margin-left: 8px;', onclick: async () => {
          const confirmed = await ctx.confirm('Delete this bitmap?', 'Yes - delete', 'No - cancel');
          if (confirmed) ctx.deleteRow('bitmaps.items', item.id);
        }}, 'Delete');
        itemDiv.appendChild(deleteBtn);
      }

      container.appendChild(itemDiv);
    });

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newItem = window.Rules.blankMapRow('bitmaps.items');
      ctx.addRow('bitmaps.items', newItem);
    }}, 'Add bitmap'));

    // Unplaced regions
    const placed = new Set();
    (d.items || []).forEach(item => {
      if (item.colors) {
        Object.values(item.colors).forEach(rid => placed.add(rid));
      }
    });
    const unplaced = regions.filter(r => !placed.has(r.id));

    if (unplaced.length > 0) {
      container.appendChild(h('h4', {style: 'margin-top: 24px;'}, 'Regions not yet on a bitmap'));
      container.appendChild(h('ul', {}, ...unplaced.map(r => h('li', {}, r.name || `Region ${regions.indexOf(r) + 1}`))));
    }

    renderClaudeQA(container, ctx, 'bitmaps');
    renderAdminNotes(container, ctx, 'bitmaps');
  }

  function renderMapAdjacency(container, ctx) {
    const d = ctx.design.adjacency;
    const regions = (ctx.design.images && ctx.design.images.regions && ctx.design.images.regions.rows) || [];
    const cols = d.cols || 32;
    const rows = d.rows || 16;
    const cells = d.cells || [];

    // Cells use the region's bitmap colour; regions not on a bitmap get a stable made-up colour
    const bitmapColour = {};
    ((ctx.design.bitmaps && ctx.design.bitmaps.items) || []).forEach(bm =>
      Object.entries(bm.colors || {}).forEach(([hex, rid]) => { if (!bitmapColour[rid]) bitmapColour[rid] = hex; }));
    const regionColour = rid => bitmapColour[rid] ||
      `hsl(${(Math.max(0, regions.findIndex(r => r.id === rid)) * 137.5) % 360}, 70%, 50%)`;

    container.appendChild(h('h3', {}, 'Adjacency Grid'));

    container.appendChild(numberField('Columns', cols, val => ctx.set('adjacency.cols', val), {min: 4, max: 64}));
    container.appendChild(numberField('Rows', rows, val => ctx.set('adjacency.rows', val), {min: 4, max: 64}));

    const autoBtn = h('button', {className: 'sx-btn', onclick: async () => {
      // Auto-generate adjacency from bitmaps
      const images = ctx.design.images;
      const bitmaps = ctx.design.bitmaps;

      const boardImages = (images && images.items) || [];
      const bitmapItems = ((bitmaps && bitmaps.items) || []).filter(bm => bm.image);
      if (bitmapItems.length === 0) {
        await ctx.confirm('Upload at least one placement bitmap first.', 'OK', null);
        return;
      }

      const confirmed = await ctx.confirm('This will overwrite the current adjacency grid. Continue?', 'Yes', 'Cancel');
      if (!confirmed) return;

      // Load all bitmap images (bitmap N belongs to board image N)
      const loadedBitmaps = [];
      for (const bitmap of bitmapItems) {
        const img = new Image();
        img.src = ctx.imgUrl(bitmap.image);
        const ok = await new Promise(resolve => { img.onload = () => resolve(true); img.onerror = () => resolve(false); });
        if (ok) loadedBitmaps.push({img, colors: bitmap.colors || {}});
      }
      if (loadedBitmaps.length === 0) return;

      // Join bitmaps in the same order and layout as the board images
      const layoutInfo = (images && images.layout) || {};
      const layout = layoutInfo.type || 'single';
      const gridCols = Math.max(1, layoutInfo.columns || 2);
      const order = (layoutInfo.order && layoutInfo.order.length) ? layoutInfo.order : boardImages.map(im => im.id);
      let orderedBitmaps = order.map(imgId => loadedBitmaps[boardImages.findIndex(im => im.id === imgId)]).filter(b => b);
      loadedBitmaps.forEach(bm => { if (!orderedBitmaps.includes(bm)) orderedBitmaps.push(bm); });

      // Calculate joined canvas dimensions
      let joinedWidth = 0, joinedHeight = 0;
      const positions = [];

      if (layout === 'single' || orderedBitmaps.length === 1) {
        joinedWidth = orderedBitmaps[0].img.width;
        joinedHeight = orderedBitmaps[0].img.height;
        positions.push({x: 0, y: 0, bitmap: orderedBitmaps[0]});
      } else if (layout === 'side-by-side') {
        joinedHeight = Math.max(...orderedBitmaps.map(b => b.img.height));
        let x = 0;
        orderedBitmaps.forEach(bitmap => {
          positions.push({x, y: 0, bitmap});
          x += bitmap.img.width;
        });
        joinedWidth = x;
      } else if (layout === 'stacked') {
        joinedWidth = Math.max(...orderedBitmaps.map(b => b.img.width));
        let y = 0;
        orderedBitmaps.forEach(bitmap => {
          positions.push({x: 0, y, bitmap});
          y += bitmap.img.height;
        });
        joinedHeight = y;
      } else if (layout === 'grid') {
        const rows = Math.ceil(orderedBitmaps.length / gridCols);
        const colWidths = [];
        const rowHeights = [];
        for (let i = 0; i < gridCols; i++) colWidths[i] = 0;
        for (let i = 0; i < rows; i++) rowHeights[i] = 0;

        orderedBitmaps.forEach((bitmap, idx) => {
          const r = Math.floor(idx / gridCols);
          const c = idx % gridCols;
          colWidths[c] = Math.max(colWidths[c], bitmap.img.width);
          rowHeights[r] = Math.max(rowHeights[r], bitmap.img.height);
        });

        orderedBitmaps.forEach((bitmap, idx) => {
          const r = Math.floor(idx / gridCols);
          const c = idx % gridCols;
          const x = colWidths.slice(0, c).reduce((sum, w) => sum + w, 0);
          const y = rowHeights.slice(0, r).reduce((sum, h) => sum + h, 0);
          positions.push({x, y, bitmap});
        });

        joinedWidth = colWidths.reduce((sum, w) => sum + w, 0);
        joinedHeight = rowHeights.reduce((sum, h) => sum + h, 0);
      }

      // Create joined canvas
      const canvas = document.createElement('canvas');
      canvas.width = joinedWidth;
      canvas.height = joinedHeight;
      const canvasCtx = canvas.getContext('2d');

      // Draw all bitmaps onto canvas
      positions.forEach(pos => {
        canvasCtx.drawImage(pos.bitmap.img, pos.x, pos.y);
      });

      // Sample each cell with majority color
      const newCells = [];
      const cellWidth = joinedWidth / cols;
      const cellHeight = joinedHeight / rows;

      function isIgnoredPixel(r, g, b, a) {
        if (a < 128) return true; // transparent
        const brightness = (r + g + b) / 3;
        if (brightness > 250) return true; // near-white
        if (brightness < 5) return true; // near-black
        return false;
      }

      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          // Sample all pixels in cell
          const x1 = Math.floor(c * cellWidth);
          const y1 = Math.floor(r * cellHeight);
          const x2 = Math.floor((c + 1) * cellWidth);
          const y2 = Math.floor((r + 1) * cellHeight);
          const w = x2 - x1;
          const h = y2 - y1;

          if (w <= 0 || h <= 0) {
            newCells.push(null);
            continue;
          }

          const imageData = canvasCtx.getImageData(x1, y1, w, h);
          const pixels = imageData.data;
          const colorCounts = {};

          for (let i = 0; i < pixels.length; i += 4) {
            const pr = pixels[i];
            const pg = pixels[i + 1];
            const pb = pixels[i + 2];
            const pa = pixels[i + 3];

            if (isIgnoredPixel(pr, pg, pb, pa)) continue;

            const color = `#${[pr, pg, pb].map(v => v.toString(16).padStart(2, '0')).join('')}`;
            colorCounts[color] = (colorCounts[color] || 0) + 1;
          }

          // Find majority color
          let majorityColor = null;
          let maxCount = 0;
          for (const color in colorCounts) {
            if (colorCounts[color] > maxCount) {
              maxCount = colorCounts[color];
              majorityColor = color;
            }
          }

          // Map color to region through bitmap colors
          let regionId = null;
          if (majorityColor) {
            // Check which bitmap this cell overlaps with
            const cellCenterX = x1 + w / 2;
            const cellCenterY = y1 + h / 2;
            for (const pos of positions) {
              if (cellCenterX >= pos.x && cellCenterX < pos.x + pos.bitmap.img.width &&
                  cellCenterY >= pos.y && cellCenterY < pos.y + pos.bitmap.img.height) {
                if (pos.bitmap.colors[majorityColor]) {
                  regionId = pos.bitmap.colors[majorityColor];
                }
                break;
              }
            }
          }

          newCells.push(regionId);
        }
      }

      ctx.set('adjacency.cells', newCells);
      ctx.rerender();
    }}, 'Auto generate from bitmaps');
    container.appendChild(autoBtn);

    // Grid
    const gridDiv = h('div', {style: 'overflow-x: auto; margin: 16px 0;'});
    const table = h('table', {style: 'border-collapse: collapse; user-select: none;'});

    let selectedRegion = null;
    let painting = false;

    for (let r = 0; r < rows; r++) {
      const tr = h('tr', {});
      for (let c = 0; c < cols; c++) {
        const idx = r * cols + c;
        const cellRegionId = cells[idx] || null;
        const cellRegion = regions.find(reg => reg.id === cellRegionId);

        const td = h('td', {
          style: `width: 20px; height: 20px; border: 1px solid #666; cursor: pointer; background: ${cellRegionId ? regionColour(cellRegionId) : '#222'};`,
          title: cellRegion ? cellRegion.name : 'Empty',
          onmousedown: async () => {
            painting = true;
            // Show region picker
            const picker = h('div', {className: 'confirm-overlay'});
            const dialog = h('div', {className: 'confirm-dialog', style: 'max-height: 70vh; overflow-y: auto;'});
            dialog.appendChild(h('h3', {}, 'Choose region:'));

            const emptyBtn = h('button', {
              className: 'sx-btn',
              style: 'display: block; width: 100%; margin: 8px 0;',
              onclick: () => {
                selectedRegion = null;
                const newCells = cells.slice();
                while (newCells.length < cols * rows) newCells.push(null);
                newCells[idx] = null;
                ctx.set('adjacency.cells', newCells);
                picker.remove();
              }
            }, 'Empty');
            dialog.appendChild(emptyBtn);

            regions.forEach(region => {
              const btn = h('button', {
                className: 'sx-btn',
                style: 'display: block; width: 100%; margin: 8px 0;',
                onclick: () => {
                  selectedRegion = region.id;
                  const newCells = cells.slice();
                  while (newCells.length < cols * rows) newCells.push(null);
                  newCells[idx] = region.id;
                  ctx.set('adjacency.cells', newCells);
                  picker.remove();
                }
              }, region.name || `Region ${regions.indexOf(region) + 1}`);
              dialog.appendChild(btn);
            });

            const cancelBtn = h('button', {
              className: 'sx-btn',
              style: 'display: block; width: 100%; margin: 16px 0 0;',
              onclick: () => picker.remove()
            }, 'Cancel');
            dialog.appendChild(cancelBtn);

            picker.appendChild(dialog);
            document.body.appendChild(picker);
          },
          onmouseenter: () => {
            if (painting && selectedRegion !== undefined) {
              const newCells = cells.slice();
              while (newCells.length < cols * rows) newCells.push(null);
              newCells[idx] = selectedRegion;
              ctx.set('adjacency.cells', newCells);
            }
          }
        });
        tr.appendChild(td);
      }
      table.appendChild(tr);
    }

    document.addEventListener('mouseup', () => { painting = false; });

    gridDiv.appendChild(table);
    container.appendChild(gridDiv);

    // Derived adjacency list
    container.appendChild(h('h4', {}, 'Derived Adjacency'));
    const adjacency = {};
    for (let i = 0; i < cells.length; i++) {
      const rid = cells[i];
      if (!rid) continue;
      const r = Math.floor(i / cols);
      const c = i % cols;
      const neighbors = [[r - 1, c], [r + 1, c], [r, c - 1], [r, c + 1]];
      neighbors.forEach(([nr, nc]) => {
        if (nr < 0 || nr >= rows || nc < 0 || nc >= cols) return;
        const nid = cells[nr * cols + nc];
        if (nid && nid !== rid) {
          adjacency[rid] = adjacency[rid] || new Set();
          adjacency[rid].add(nid);
        }
      });
    }

    const adjList = h('div', {style: 'font-size: 0.9em; max-height: 300px; overflow-y: auto; border: 1px solid #666; padding: 12px;'});
    regions.forEach(region => {
      const neighbors = adjacency[region.id] || new Set();
      const neighborNames = Array.from(neighbors).map(nid => {
        const n = regions.find(r => r.id === nid);
        return n ? n.name : nid;
      }).join(', ');
      adjList.appendChild(h('div', {}, `${region.name}: ${neighborNames || '(none)'}`));
    });
    container.appendChild(adjList);

    // Special adjacency
    container.appendChild(h('h3', {style: 'margin-top: 24px;'}, 'Special Adjacency'));
    container.appendChild(h('p', {}, 'Custom adjacency types like doors, staircases, or portals.'));

    (d.special.rows || []).forEach((special, idx) => {
      const specialDiv = h('div', {style: 'margin: 16px 0; padding: 16px; border: 2px solid #444;'});
      specialDiv.appendChild(h('h4', {}, `Special Type ${idx + 1}`));

      specialDiv.appendChild(textField('Type name', special.name, val => ctx.set(`adjacency.special.rows.${special.id}.name`, val)));
      specialDiv.appendChild(textField('Description', special.desc, val => ctx.set(`adjacency.special.rows.${special.id}.desc`, val), {rows: 2}));
      specialDiv.appendChild(numberField('Cost to cross (optional)', special.cost, val => ctx.set(`adjacency.special.rows.${special.id}.cost`, val)));
      specialDiv.appendChild(checkboxField('One-way', special.oneWay, val => ctx.set(`adjacency.special.rows.${special.id}.oneWay`, val)));

      specialDiv.appendChild(h('h5', {}, 'Connected Regions'));
      (special.pairs || []).forEach((pair, pidx) => {
        const pairDiv = h('div', {style: 'display: flex; gap: 8px; align-items: center; margin: 8px 0;'});
        pairDiv.appendChild(h('select', {
          value: pair.from || '',
          onchange: e => ctx.set(`adjacency.special.rows.${special.id}.pairs.${pair.id}.from`, e.target.value || null)
        },
          h('option', {value: ''}, '-- Select from --'),
          ...regions.map(r => h('option', {value: r.id}, r.name))
        ));
        pairDiv.appendChild(h('span', {}, special.oneWay ? '→' : '↔'));
        pairDiv.appendChild(h('select', {
          value: pair.to || '',
          onchange: e => ctx.set(`adjacency.special.rows.${special.id}.pairs.${pair.id}.to`, e.target.value || null)
        },
          h('option', {value: ''}, '-- Select to --'),
          ...regions.map(r => h('option', {value: r.id}, r.name))
        ));
        pairDiv.appendChild(h('button', {className: 'sx-btn', onclick: () => {
          const newPairs = special.pairs.filter(p => p.id !== pair.id);
          ctx.set(`adjacency.special.rows.${special.id}.pairs`, newPairs);
        }}, 'Remove'));
        specialDiv.appendChild(pairDiv);
      });

      specialDiv.appendChild(h('button', {className: 'sx-btn', style: 'margin-top: 8px;', onclick: () => {
        const newPair = window.Rules.blankMapRow('adjacency.special.rows.pairs');
        const newPairs = (special.pairs || []).concat([newPair]);
        ctx.set(`adjacency.special.rows.${special.id}.pairs`, newPairs);
      }}, 'Add connection'));

      specialDiv.appendChild(h('button', {className: 'sx-btn danger', style: 'margin-top: 16px;', onclick: async () => {
        const confirmed = await ctx.confirm('Delete this special adjacency type?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('adjacency.special.rows', special.id);
      }}, 'Delete this special type'));

      container.appendChild(specialDiv);
    });

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newSpecial = window.Rules.blankMapRow('adjacency.special.rows');
      ctx.addRow('adjacency.special.rows', newSpecial);
    }}, 'Add special adjacency type'));

    renderClaudeQA(container, ctx, 'adjacency');
    renderAdminNotes(container, ctx, 'adjacency');
  }

  function renderMapUnits(container, ctx) {
    const d = ctx.design.units;

    container.appendChild(h('h3', {}, 'Map Units'));
    container.appendChild(textField('Wiki page URL', d.wikiUrl || '', val => ctx.set('units.wikiUrl', val)));

    const extractBtn = h('button', {className: 'sx-btn', style: 'margin: 8px 0;', onclick: async () => {
      if (!d.wikiUrl) {
        alert('Please enter a wiki page URL first.');
        return;
      }
      const confirmed = await ctx.confirm('Extract units and other content from wiki page?', 'Yes - Extract', 'Cancel');
      if (!confirmed) return;
      extractBtn.disabled = true;
      try {
        await ctx.createRequest('extract', `Extract units from wiki for map ${ctx.map.name}`, {target: 'wiki', url: d.wikiUrl});
        alert('Extract requested.');
      } catch (err) {
        alert('Request failed: ' + err.message);
      }
      extractBtn.disabled = false;
    }}, 'Extract units and other content from wiki');
    container.appendChild(extractBtn);

    // Reuse faction units renderer with neutral flag
    const neutralCtx = Object.assign({}, ctx, {neutral: true, design: {units: d}});
    renderUnits(container, neutralCtx);

    renderClaudeQA(container, ctx, 'units');
    renderAdminNotes(container, ctx, 'units');
  }

  function renderMapTokens(container, ctx) {
    const d = ctx.design.tokens;
    const neutralCtx = Object.assign({}, ctx, {design: {tokens: d}});
    renderTokens(container, neutralCtx);

    renderClaudeQA(container, ctx, 'tokens');
    renderAdminNotes(container, ctx, 'tokens');
  }

  function renderMapSB(container, ctx) {
    const d = ctx.design.sb;
    const missing = window.Rules.missingMapFields('sb', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(h('h3', {}, 'Spellbook Requirements'));

    const reqDiv = h('div', {className: 'sx-table'});
    const reqTable = h('table', {});
    reqTable.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Text'),
      h('th', {style: 'width: 200px;'}, 'Includes Fixed Numeric Cost or Effect?'),
      h('th', {style: 'width: 150px;'}, 'Fixed Numeric Cost or Effect'),
      h('th', {}, '')
    )));

    const reqTbody = h('tbody', {});
    (d.requirements.rows || []).forEach(row => {
      const tr = h('tr', {});
      tr.appendChild(h('td', {}, h('textarea', {
        className: isMissing(`sb.requirements.rows.${row.id}.text`) ? 'sx-missing' : '',
        value: row.text || '',
        rows: 3,
        oninput: e => ctx.set(`sb.requirements.rows.${row.id}.text`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('input', {
        type: 'checkbox',
        checked: row.hasNum,
        onchange: e => ctx.set(`sb.requirements.rows.${row.id}.hasNum`, e.target.checked)
      })));

      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`sb.requirements.rows.${row.id}.num`) ? 'sx-missing' : '',
        type: 'number',
        value: row.num != null ? row.num : '',
        disabled: !row.hasNum,
        oninput: e => ctx.set(`sb.requirements.rows.${row.id}.num`, e.target.value ? parseInt(e.target.value) : null)
      })));

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this requirement?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('sb.requirements.rows', row.id);
      }}, 'Delete')));

      reqTbody.appendChild(tr);
    });
    reqTable.appendChild(reqTbody);
    reqDiv.appendChild(reqTable);
    container.appendChild(reqDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankMapRow('sb.requirements.rows');
      ctx.addRow('sb.requirements.rows', newRow);
    }}, 'Add requirement'));

    // Spellbooks
    container.appendChild(h('h3', {style: 'margin-top: 24px;'}, 'Spellbooks'));

    const booksDiv = h('div', {className: 'sx-table'});
    const booksTable = h('table', {});
    booksTable.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Name'),
      h('th', {}, 'Type'),
      h('th', {style: 'width: 100px;'}, 'Cost'),
      h('th', {style: 'width: 150px;'}, 'Includes Fixed Numeric Effect?'),
      h('th', {style: 'width: 100px;'}, 'Fixed Numeric Effect'),
      h('th', {}, 'Text'),
      h('th', {}, '')
    )));

    const booksTbody = h('tbody', {});
    (d.books.rows || []).forEach(row => {
      const tr = h('tr', {});
      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`sb.books.rows.${row.id}.name`) ? 'sx-missing' : '',
        type: 'text',
        value: row.name || '',
        style: 'min-width: 155px;',
        oninput: e => ctx.set(`sb.books.rows.${row.id}.name`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('select', {
        className: isMissing(`sb.books.rows.${row.id}.type`) ? 'sx-missing' : '',
        value: row.type || '',
        onchange: e => ctx.set(`sb.books.rows.${row.id}.type`, e.target.value || null)
      },
        h('option', {value: ''}, '-- Select --'),
        ...window.Rules.SB_TYPES.map(t => h('option', {value: t}, t))
      )));

      tr.appendChild(h('td', {}, h('input', {
        type: 'number',
        value: row.cost != null ? row.cost : 0,
        oninput: e => ctx.set(`sb.books.rows.${row.id}.cost`, e.target.value ? parseInt(e.target.value) : 0)
      })));

      tr.appendChild(h('td', {}, h('input', {
        type: 'checkbox',
        checked: !!row.hasEffect,
        onchange: e => ctx.set(`sb.books.rows.${row.id}.hasEffect`, e.target.checked)
      })));

      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`sb.books.rows.${row.id}.effect`) ? 'sx-missing' : '',
        type: 'number',
        value: row.effect != null ? row.effect : '',
        disabled: !row.hasEffect,
        oninput: e => ctx.set(`sb.books.rows.${row.id}.effect`, e.target.value ? parseInt(e.target.value) : null)
      })));

      tr.appendChild(h('td', {}, h('textarea', {
        className: isMissing(`sb.books.rows.${row.id}.text`) ? 'sx-missing' : '',
        value: row.text || '',
        rows: 3,
        style: 'min-width: 160px;',
        oninput: e => ctx.set(`sb.books.rows.${row.id}.text`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this spellbook?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('sb.books.rows', row.id);
      }}, 'Delete')));

      booksTbody.appendChild(tr);
    });
    booksTable.appendChild(booksTbody);
    booksDiv.appendChild(booksTable);
    container.appendChild(booksDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankMapRow('sb.books.rows');
      ctx.addRow('sb.books.rows', newRow);
    }}, 'Add spellbook'));

    renderClaudeQA(container, ctx, 'sb');
    renderAdminNotes(container, ctx, 'sb');
  }

  function renderMapGlyphs(container, ctx) {
    const d = ctx.design.glyphs;
    const missing = window.Rules.missingMapFields('glyphs', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(h('h3', {}, 'Map Glyphs'));

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Name'),
      h('th', {}, 'Image'),
      h('th', {}, 'What it does'),
      h('th', {}, '')
    )));

    const tbody = h('tbody', {});
    (d.rows || []).forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`glyphs.rows.${row.id}.name`) ? 'sx-missing' : '',
        type: 'text',
        value: row.name || '',
        oninput: e => ctx.set(`glyphs.rows.${row.id}.name`, e.target.value)
      })));

      const imgTd = h('td', {});
      if (row.image) {
        imgTd.appendChild(h('img', {
          src: ctx.imgUrl(row.image),
          className: 'sx-img-thumb' + (isMissing(`glyphs.rows.${row.id}.image`) ? ' sx-missing' : ''),
          onclick: () => openImageEditor(row.image, ctx, id => ctx.set(`glyphs.rows.${row.id}.image`, id), 'small')
        }));
      } else {
        imgTd.appendChild(h('div', {
          className: 'sx-img-thumb sx-empty' + (isMissing(`glyphs.rows.${row.id}.image`) ? ' sx-missing' : ''),
          onclick: async () => {
            const id = await ctx.uploadImage('small');
            if (id) ctx.set(`glyphs.rows.${row.id}.image`, id);
          }
        }, 'Upload'));
      }
      tr.appendChild(imgTd);

      tr.appendChild(h('td', {}, h('textarea', {
        className: isMissing(`glyphs.rows.${row.id}.desc`) ? 'sx-missing' : '',
        value: row.desc || '',
        rows: 2,
        oninput: e => ctx.set(`glyphs.rows.${row.id}.desc`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this glyph?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('glyphs.rows', row.id);
      }}, 'Delete')));

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankMapRow('glyphs.rows');
      ctx.addRow('glyphs.rows', newRow);
    }}, 'Add glyph'));

    renderClaudeQA(container, ctx, 'glyphs');
    renderAdminNotes(container, ctx, 'glyphs');
  }

  function renderMapAbilities(container, ctx) {
    const d = ctx.design.abilities;
    const missing = window.Rules.missingMapFields('abilities', ctx.design);
    const isMissing = path => missing.includes(path);

    container.appendChild(h('h3', {}, 'Map Abilities'));

    const tableDiv = h('div', {className: 'sx-table'});
    const table = h('table', {});
    table.appendChild(h('thead', {}, h('tr', {},
      h('th', {}, 'Name'),
      h('th', {}, 'When'),
      h('th', {}, 'Type'),
      h('th', {}, 'Cost'),
      h('th', {}, 'Who can use it'),
      h('th', {}, 'Text'),
      h('th', {}, '')
    )));

    const tbody = h('tbody', {});
    (d.rows || []).forEach((row, idx) => {
      const tr = h('tr', {});

      tr.appendChild(h('td', {}, h('input', {
        className: isMissing(`abilities.rows.${row.id}.name`) ? 'sx-missing' : '',
        type: 'text',
        value: row.name || '',
        oninput: e => ctx.set(`abilities.rows.${row.id}.name`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('select', {
        className: isMissing(`abilities.rows.${row.id}.when`) ? 'sx-missing' : '',
        value: row.when || '',
        onchange: e => ctx.set(`abilities.rows.${row.id}.when`, e.target.value || null)
      },
        h('option', {value: ''}, '-- Select --'),
        ...window.Rules.MAP_ABILITY_PHASES.map(p => h('option', {value: p}, p))
      )));

      tr.appendChild(h('td', {}, h('select', {
        className: isMissing(`abilities.rows.${row.id}.type`) ? 'sx-missing' : '',
        value: row.type || '',
        onchange: e => ctx.set(`abilities.rows.${row.id}.type`, e.target.value || null)
      },
        h('option', {value: ''}, '-- Select --'),
        ...window.Rules.MAP_ABILITY_TYPES.map(t => h('option', {value: t}, t))
      )));

      tr.appendChild(h('td', {}, h('input', {
        type: 'number',
        value: row.cost != null ? row.cost : '',
        placeholder: 'optional',
        oninput: e => ctx.set(`abilities.rows.${row.id}.cost`, e.target.value ? parseInt(e.target.value) : null)
      })));

      tr.appendChild(h('td', {}, h('textarea', {
        className: isMissing(`abilities.rows.${row.id}.who`) ? 'sx-missing' : '',
        value: row.who || '',
        rows: 2,
        placeholder: 'e.g. "Faction controlling the Gate"',
        oninput: e => ctx.set(`abilities.rows.${row.id}.who`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('textarea', {
        className: isMissing(`abilities.rows.${row.id}.text`) ? 'sx-missing' : '',
        value: row.text || '',
        rows: 3,
        oninput: e => ctx.set(`abilities.rows.${row.id}.text`, e.target.value)
      })));

      tr.appendChild(h('td', {}, h('button', {onclick: async () => {
        const confirmed = await ctx.confirm('Delete this ability?', 'Yes - delete', 'No - cancel');
        if (confirmed) ctx.deleteRow('abilities.rows', row.id);
      }}, 'Delete')));

      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableDiv.appendChild(table);
    container.appendChild(tableDiv);

    container.appendChild(h('button', {className: 'sx-btn', onclick: () => {
      const newRow = window.Rules.blankMapRow('abilities.rows');
      ctx.addRow('abilities.rows', newRow);
    }}, 'Add ability'));

    renderClaudeQA(container, ctx, 'abilities');
    renderAdminNotes(container, ctx, 'abilities');
  }

  // Highlight missing fields in the container based on Rules.missingFields
  function highlightMissingFields(key, design, container) {
    if (!window.Rules || !window.Rules.missingFields) return;

    const missingPaths = window.Rules.missingFields(key, design);
    if (!missingPaths || missingPaths.length === 0) return;

    for (const path of missingPaths) {
      // Try to find the element by id or data-path attribute
      const parts = path.split('.');
      const fieldName = parts[parts.length - 1];

      // Search for inputs, selects, and textareas with matching IDs or data-path
      const inputs = container.querySelectorAll(`input[data-path="${path}"], select[data-path="${path}"], textarea[data-path="${path}"]`);
      inputs.forEach(el => {
        el.classList.add('sx-missing');
      });

      // Also try finding by ID if data-path didn't work
      if (inputs.length === 0) {
        const idMatch = container.querySelector(`[id*="${fieldName}"]`);
        if (idMatch && (idMatch.tagName === 'INPUT' || idMatch.tagName === 'SELECT' || idMatch.tagName === 'TEXTAREA' || idMatch.classList.contains('sx-img-thumb'))) {
          idMatch.classList.add('sx-missing');
        }
      }
    }
  }

  function render(key, container, ctx) {
    injectCSS();
    container.innerHTML = '';

    const renderers = {
      ae: renderAE,
      ufa: renderUFA,
      setup: renderSetup,
      units: ctx.map ? renderMapUnits : renderUnits,
      sbr: renderSBR,
      sb: ctx.map ? renderMapSB : renderSB,
      region: renderRegion,
      tokens: ctx.map ? renderMapTokens : renderTokens,
      custom: renderCustom,
      menus: renderMenus,
      interactions: renderInteractions,
      images: renderMapImages,
      bitmaps: renderMapBitmaps,
      adjacency: renderMapAdjacency,
      glyphs: renderMapGlyphs,
      abilities: renderMapAbilities
    };

    const renderer = renderers[key];
    if (renderer) {
      renderer(container, ctx);

      // Highlight missing fields if in admin view
      if (ctx.readOnly && ctx.adminView) {
        highlightMissingFields(key, ctx.design, container);
      }
      // Free box at the bottom of every design section (not Menu Design)
      const isFactionSection = window.Rules.BUILD_SECTIONS.includes(key);
      const isMapSection = window.Rules.MAP_BUILD_SECTIONS && window.Rules.MAP_BUILD_SECTIONS.includes(key);
      if (isFactionSection || isMapSection) {
        const sec = ctx.design[key] || {};
        container.appendChild(textField('Any custom logic or rules', sec.customLogic,
          val => ctx.set(key + '.customLogic', val),
          {rows: 8, greyed: key === 'ae' && !sec.enabled,
           hint: 'Anything about this section that the fields above cannot say: special timing, exceptions, interactions, edge cases'}));
      }

      // Claude Q&A boxes: hidden until a build has been attempted
      // Admin view: Claude Q&A section is always visible when buildAttempted=true,
      // whether viewing as designer or admin. This allows admins to see all feedback.
      // Answer submission form is only shown when not read-only (ctx.readOnly=false).
      const entity = ctx.faction || ctx.unit || ctx.map;
      const entityType = ctx.faction ? 'factions' : ctx.unit ? 'units' : ctx.map ? 'maps' : null;
      const sectionKey = ctx.neutral ? 'unit' : key;  // a neutral unit has one screen, keyed 'unit'
      if (entity && entityType && entity.buildAttempted) {
        entity.claudeQA = entity.claudeQA || {};
        const qa = entity.claudeQA[sectionKey] || {questions: '', answers: ''};
        const label = text => h('label', {style: 'display: block; font-weight: bold; margin-bottom: 8px;'}, text);
        const boxStyle = 'width: 100%; padding: 8px; font-family: monospace; font-size: 13px; resize: vertical; box-sizing: border-box;';

        const questionsBox = h('textarea', {readonly: true, placeholder: 'No questions from Claude on this section.',
          style: boxStyle + ' height: 50vh; border: 1px solid #666; background: #1a1a1a; color: #aaa;'});
        questionsBox.value = qa.questions || '';
        container.appendChild(h('div', {style: 'margin-top: 40px;'}, label('Claude questions'), questionsBox));

        const answersDiv = h('div', {style: 'margin-top: 20px;'});
        if (ctx.readOnly && !qa.answers) {
          const placeholder = h('p', {style: 'color: #888; font-style: italic; padding: 8px;'},
            'Awaiting designer\'s answer');
          answersDiv.appendChild(placeholder);
          container.appendChild(answersDiv);
        } else if (!ctx.readOnly) {
          const answersBox = h('textarea', {style: boxStyle + ' height: 35vh; border: 1px solid #888; background: #222; color: #eee;'});
          answersBox.value = qa.answers || '';
          const status = h('span', {style: 'margin-left: 12px; font-size: 14px;'});
          const submitBtn = h('button', {className: 'sx-btn', style: 'margin-top: 12px;', disabled: !answersBox.value.trim(),
            onclick: async () => {
              const text = answersBox.value.trim();
              submitBtn.disabled = true;
              status.textContent = '';
              try {
                const response = await fetch(`/designer/api/${entityType}/${entity.id}/answers`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('cw_designer_token')}`},
                  body: JSON.stringify({section: sectionKey, text})
                });
                if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || 'Failed to submit answers');
                entity.claudeQA[sectionKey] = Object.assign({}, qa, {answers: text});
                status.style.color = '#4ade80';
                status.textContent = 'Sent to Claude.';
              } catch (err) {
                status.style.color = '#f87171';
                status.textContent = 'Could not send: ' + err.message;
              } finally {
                submitBtn.disabled = !answersBox.value.trim();
              }
            }
          }, 'Submit answers');
          answersBox.oninput = () => { submitBtn.disabled = !answersBox.value.trim(); };
          answersDiv.appendChild(label('Answers for Claude'));
          answersDiv.appendChild(answersBox);
          answersDiv.appendChild(submitBtn);
          answersDiv.appendChild(status);
          container.appendChild(answersDiv);
        } else if (ctx.readOnly && qa.answers) {
          const answersBox = h('textarea', {readonly: true, style: boxStyle + ' height: 35vh; border: 1px solid #666; background: #1a1a1a; color: #aaa;'});
          answersBox.value = qa.answers || '';
          answersDiv.appendChild(label('Designer\'s answers'));
          answersDiv.appendChild(answersBox);
          container.appendChild(answersDiv);
        }
      }
    } else {
      container.appendChild(h('p', {}, 'Section not implemented: ' + key));
    }
  }

  // renderInteractions - integrated from temporary file
  function renderInteractions(container, ctx) {
  const d = ctx.design.interactions;
  const missing = window.Rules.missingFields('interactions', ctx.design);
  const isMissing = path => missing.includes(path);

  // Load abilities data (cached)
  if (!window._abilitiesData) {
    fetch('/designer/abilities-data.json')
      .then(r => r.json())
      .then(data => {
        window._abilitiesData = data;
        ctx.rerender(); // Re-render once data is loaded
      });
    container.appendChild(h('p', {}, 'Loading abilities data...'));
    return;
  }

  const abilitiesData = window._abilitiesData;

  // Helper to get abilities for a faction/type combination
  const getAbilities = (faction, type) => {
    if (!faction || !type) return [];
    return abilitiesData.abilities.filter(a => {
      if (a.faction !== faction) return false;
      // Map ability types
      if (type === 'UFA' && a.unit === 'N/A' && a.type !== 'Spellbook') return true;
      if (type === 'Spellbook' && a.type === 'Spellbook') return true;
      if (type === 'Unit Special' && a.unit !== 'N/A') return true;
      if (type === 'GOO/iGOO/EG ability' && a.unit !== 'N/A') return true;
      return false;
    });
  };

  // Helper to get ability text
  const getAbilityText = (faction, abilityName) => {
    const ability = abilitiesData.abilities.find(a => a.faction === faction && a.name === abilityName);
    return ability ? ability.text : '';
  };

  // Get this faction's abilities for dropdown
  const getYourAbilities = () => {
    const abilities = [{value: 'ufa', label: 'Unique Faction Ability'}];

    // Add spellbooks
    const sbRows = ctx.design.sb?.rows || [];
    sbRows.forEach((sb, idx) => {
      if (sb.name) {
        abilities.push({value: `sb_${idx + 1}`, label: `SB ${idx + 1}: ${sb.name}`});
      }
    });

    // Add units with abilities
    const unitRows = ctx.design.units?.rows || [];
    unitRows.forEach(unit => {
      if (unit.abilityName && unit.name) {
        abilities.push({value: `unit_${unit.name}`, label: `${unit.name}: ${unit.abilityName}`});
      }
    });

    // Add GOO ability if exists
    const goo = unitRows.find(u => u.type === 'Great Old One');
    if (goo && goo.abilityName) {
      abilities.push({value: 'goo', label: `${goo.name} (GOO ability)`});
    }

    return abilities;
  };

  const tableDiv = h('div', {className: 'sx-table'});
  const table = h('table', {});
  const thead = h('thead', {},
    h('tr', {},
      h('th', {}, 'Faction/Map'),
      h('th', {}, 'Ability Type'),
      h('th', {}, 'Ability'),
      h('th', {}, 'Ability Text'),
      h('th', {}, 'Your Faction\'s Ability'),
      h('th', {}, 'Interaction Description'),
      h('th', {}, '')
    )
  );
  table.appendChild(thead);

  const tbody = h('tbody', {});

  d.rows.forEach(row => {
    const tr = h('tr', {});

    // Check if this is the Ancient Sorcery row (required)
    const isAncientSorcery = row.otherFaction === 'Sleeper' &&
                             row.abilityType === 'Spellbook' &&
                             row.ability === 'Ancient Sorcery';

    if (isAncientSorcery) {
      tr.style.backgroundColor = '#1a2a1a'; // Slight green tint to indicate required row
    }

    // Column 1: Faction/Map dropdown
    tr.appendChild(h('td', {},
      h('select', {
        className: isMissing(`interactions.rows.${row.id}.otherFaction`) ? 'sx-missing' : '',
        value: row.otherFaction || '',
        onchange: e => {
          ctx.set(`interactions.rows.${row.id}.otherFaction`, e.target.value || null);
          ctx.set(`interactions.rows.${row.id}.ability`, null);
          ctx.set(`interactions.rows.${row.id}.abilityText`, '');
        }
      },
        h('option', {value: ''}, '-- Select --'),
        abilitiesData.factions.map(f => h('option', {value: f}, f))
      )
    ));

    // Column 2: Ability Type dropdown
    const abilityTypes = ['UFA', 'Spellbook', 'Unit Special', 'GOO/iGOO/EG ability'];
    tr.appendChild(h('td', {},
      h('select', {
        className: isMissing(`interactions.rows.${row.id}.abilityType`) ? 'sx-missing' : '',
        value: row.abilityType || '',
        onchange: e => {
          ctx.set(`interactions.rows.${row.id}.abilityType`, e.target.value || null);
          ctx.set(`interactions.rows.${row.id}.ability`, null);
          ctx.set(`interactions.rows.${row.id}.abilityText`, '');
        }
      },
        h('option', {value: ''}, '-- Select --'),
        abilityTypes.map(t => h('option', {value: t}, t))
      )
    ));

    // Column 3: Ability dropdown (waterfall based on columns 1+2)
    const availableAbilities = getAbilities(row.otherFaction, row.abilityType);
    tr.appendChild(h('td', {},
      h('select', {
        className: isMissing(`interactions.rows.${row.id}.ability`) ? 'sx-missing' : '',
        value: row.ability || '',
        disabled: !row.otherFaction || !row.abilityType,
        onchange: e => {
          ctx.set(`interactions.rows.${row.id}.ability`, e.target.value || null);
          const text = getAbilityText(row.otherFaction, e.target.value);
          ctx.set(`interactions.rows.${row.id}.abilityText`, text);
        }
      },
        h('option', {value: ''}, '-- Select --'),
        availableAbilities.map(a => h('option', {value: a.name}, a.name))
      )
    ));

    // Column 4: Ability Text (read-only, large)
    tr.appendChild(h('td', {},
      h('textarea', {
        value: row.abilityText || '',
        disabled: true,
        rows: 4,
        style: 'background: #1a1a1a; color: #888; resize: vertical; min-height: 80px;'
      })
    ));

    // Column 5: Your Faction's Ability dropdown
    const yourAbilities = getYourAbilities();
    tr.appendChild(h('td', {},
      h('select', {
        className: isMissing(`interactions.rows.${row.id}.yourAbility`) ? 'sx-missing' : '',
        value: row.yourAbility || '',
        onchange: e => ctx.set(`interactions.rows.${row.id}.yourAbility`, e.target.value || null)
      },
        h('option', {value: ''}, '-- Select --'),
        yourAbilities.map(a => h('option', {value: a.value}, a.label))
      )
    ));

    // Column 6: Interaction Description (large text box)
    tr.appendChild(h('td', {},
      h('textarea', {
        className: isMissing(`interactions.rows.${row.id}.interactionDesc`) ? 'sx-missing' : '',
        value: row.interactionDesc || '',
        rows: 4,
        style: 'min-height: 80px; resize: vertical;',
        oninput: e => ctx.set(`interactions.rows.${row.id}.interactionDesc`, e.target.value)
      })
    ));

    // Column 7: Delete button (only if not Ancient Sorcery row)
    tr.appendChild(h('td', {},
      isAncientSorcery
        ? h('span', {style: 'color: #888; font-size: 12px;'}, 'Required')
        : h('button', {
            onclick: async () => {
              const confirmed = await ctx.confirm('Delete this interaction row?', 'Yes', 'No');
              if (confirmed) ctx.deleteRow('interactions.rows', row.id);
            }
          }, 'Delete')
    ));

    tbody.appendChild(tr);
  });

  table.appendChild(tbody);
  tableDiv.appendChild(table);
  container.appendChild(tableDiv);

  // Add row button
  container.appendChild(h('button', {
    className: 'sx-btn',
    onclick: () => {
      const newRow = window.Rules.blankRow('interactions.rows');
      ctx.addRow('interactions.rows', newRow);
    }
  }, 'Add Interaction Row'));

  // Help text
  container.appendChild(h('p', {style: 'margin-top: 20px; font-size: 14px; color: #aaa;'},
    'The Ancient Sorcery row (green background) is required. All other rows are optional. ' +
    'Use this section to document interactions between your faction\'s abilities and known abilities ' +
    'from other factions, maps, or neutral units.'
  ));

  renderClaudeQA(container, ctx, 'interactions');
  renderAdminNotes(container, ctx, 'interactions');
}

  window.Sections = {render};
})();
