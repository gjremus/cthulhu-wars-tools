// Development stub for sections.js
(function() {
  'use strict';

  window.Sections = {
    render(key, container, ctx) {
      container.innerHTML = '';
      const div = document.createElement('div');
      div.style.padding = '20px';
      div.style.color = '#ccc';

      const title = document.createElement('h2');
      title.textContent = `Section: ${key}`;
      title.style.marginBottom = '20px';
      div.appendChild(title);

      const note = document.createElement('p');
      note.textContent = 'This is a stub. The real sections.js is being written by another agent.';
      note.style.marginBottom = '20px';
      div.appendChild(note);

      // Show some of the context
      const pre = document.createElement('pre');
      pre.style.background = '#222';
      pre.style.padding = '10px';
      pre.style.overflow = 'auto';
      pre.style.fontSize = '12px';
      pre.textContent = `Faction: ${ctx.faction.name} (${ctx.faction.acronym})
Design keys: ${Object.keys(ctx.design).join(', ')}
Section data: ${JSON.stringify(ctx.design[key], null, 2)}`;
      div.appendChild(pre);

      // Add a simple test field
      const label = document.createElement('label');
      label.textContent = 'Test field (autosaves): ';
      label.style.display = 'block';
      label.style.marginTop = '20px';

      const input = document.createElement('input');
      input.type = 'text';
      input.value = ctx.design[key]?.test || '';
      input.style.width = '300px';
      input.style.padding = '5px';
      input.addEventListener('input', () => {
        ctx.set(`${key}.test`, input.value);
      });

      label.appendChild(input);
      div.appendChild(label);

      container.appendChild(div);
    }
  };
})();
