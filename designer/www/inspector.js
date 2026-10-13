// Admin Read-Only Faction Build Inspector
// Mirrors the designer build form, showing read-only build progress and Claude feedback

class FactionBuildInspectorScreen {
  constructor(faction, app) {
    this.faction = faction;
    this.app = app;
    this.claudeQA = faction.claudeQA || {};
    this.requestId = faction.requestId;
    this.submittedAt = faction.submittedAt;
    this.buildHistory = faction.buildHistory || [];
    this.ownerName = faction.ownerName || faction.owner;
  }

  render() {
    const container = document.createElement('div');
    container.className = 'inspector-container';
    container.appendChild(this.renderHeader());

    const layout = document.createElement('div');
    layout.className = 'inspector-layout';
    layout.appendChild(this.renderSidebar());
    layout.appendChild(this.renderMainPanel());
    container.appendChild(layout);

    this.app.root.innerHTML = '';
    this.app.root.appendChild(container);

    // Set up sidebar scroll linking
    this.setupSidebarScrollLinks();
  }

  renderHeader() {
    const header = document.createElement('div');
    header.className = 'inspector-header';

    const titleRow = document.createElement('div');
    titleRow.className = 'inspector-header-title';
    const factionName = this.faction.name || this.faction.id || 'Unknown Faction';
    const factionAcronym = this.faction.design?.ae?.acronym || '';
    titleRow.innerHTML = `
      <div class="inspector-header-left">
        <h1>CWO Faction Build Inspector</h1>
        <span class="inspector-faction-label">
          ${factionName}
          ${factionAcronym ? `(${factionAcronym})` : ''}
        </span>
      </div>
      <div class="inspector-header-right">
        <span class="inspector-request-id">Request #${this.requestId || 'N/A'}</span>
      </div>
    `;

    const statusRow = document.createElement('div');
    statusRow.className = 'inspector-header-status';

    const buildStatus = this.faction.build?.status || 'none';
    const statusLabel = this.app.getBuildStatusLabel(this.faction);
    const statusClass = `status-${buildStatus}`;

    const submittedDate = this.submittedAt
      ? new Date(this.submittedAt * 1000).toLocaleString('en-US', {
          year: 'numeric', month: '2-digit', day: '2-digit',
          hour: '2-digit', minute: '2-digit'
        })
      : 'N/A';

    statusRow.innerHTML = `
      <span class="inspector-status-badge ${statusClass}">${statusLabel}</span>
      <span class="inspector-metadata">
        Submitted by: <strong>${this.ownerName}</strong> on ${submittedDate}
      </span>
      <span class="inspector-version">
        Design v${this.faction.current || 'N/A'}
      </span>
    `;

    header.appendChild(titleRow);
    header.appendChild(statusRow);
    return header;
  }

  renderSidebar() {
    const sidebar = document.createElement('div');
    sidebar.className = 'inspector-sidebar';

    const title = document.createElement('div');
    title.className = 'sidebar-title';
    title.textContent = 'Section Status';
    sidebar.appendChild(title);

    const list = document.createElement('div');
    list.className = 'section-status-list';

    // Build section status entries from design
    const sections = [
      { key: 'overview', label: 'Overview' },
      { key: 'abilities', label: 'Abilities' },
      { key: 'units', label: 'Units' },
      { key: 'specialAbilities', label: 'Special Abilities' },
      { key: 'powers', label: 'Powers' }
    ];

    sections.forEach(section => {
      const item = this.createSidebarItem(section);
      if (item) list.appendChild(item);
    });

    // Add Claude Q&A section
    const qaItem = document.createElement('div');
    qaItem.className = 'section-status-item';
    qaItem.innerHTML = `
      <span class="status-icon">◆</span>
      <span class="section-link" data-section="claudeQA">Claude Feedback</span>
    `;
    qaItem.style.cursor = 'pointer';
    qaItem.onclick = () => this.scrollToSection('claudeQA');
    list.appendChild(qaItem);

    sidebar.appendChild(list);
    return sidebar;
  }

  createSidebarItem(section) {
    const item = document.createElement('div');
    item.className = 'section-status-item';

    const sectionData = this.faction.design?.[section.key];
    if (!sectionData && section.key !== 'overview') return null;

    // Determine status icon and label
    let statusIcon = '—';
    let statusClass = 'status-na';
    let statusText = '';

    if (section.key === 'abilities' && Array.isArray(sectionData)) {
      const count = sectionData.length;
      if (count === 6) {
        statusIcon = '✓';
        statusClass = 'status-complete';
      } else if (count > 0) {
        statusIcon = '◆';
        statusClass = 'status-pending';
        statusText = `(${count}/6)`;
      } else {
        statusIcon = '✗';
        statusClass = 'status-incomplete';
      }
    } else if (section.key === 'units' && Array.isArray(sectionData)) {
      const count = sectionData.length;
      if (count >= 5) {
        statusIcon = '✓';
        statusClass = 'status-complete';
      } else if (count > 0) {
        statusIcon = '◆';
        statusClass = 'status-pending';
        statusText = `(${count}/5)`;
      } else {
        statusIcon = '✗';
        statusClass = 'status-incomplete';
      }
    } else if (sectionData) {
      statusIcon = '✓';
      statusClass = 'status-complete';
    }

    item.innerHTML = `
      <span class="status-icon ${statusClass}">${statusIcon}</span>
      <span class="section-link" data-section="${section.key}">
        ${section.label}
        ${statusText ? `<span class="status-text">${statusText}</span>` : ''}
      </span>
    `;
    item.style.cursor = 'pointer';
    item.onclick = () => this.scrollToSection(section.key);

    return item;
  }

  renderMainPanel() {
    const main = document.createElement('div');
    main.className = 'inspector-main';

    // Overview section (always first)
    const sections = [
      { key: 'overview', title: 'Overview' },
      { key: 'abilities', title: 'Abilities' },
      { key: 'units', title: 'Units' },
      { key: 'specialAbilities', title: 'Special Abilities' },
      { key: 'powers', title: 'Powers' }
    ];

    sections.forEach((section, idx) => {
      const sectionEl = this.renderSectionDetail(section, idx === 0);
      if (sectionEl) main.appendChild(sectionEl);
    });

    // Claude Feedback section
    const claudeSection = this.renderClaudeQASection();
    if (claudeSection) main.appendChild(claudeSection);

    return main;
  }

  renderSectionDetail(section, isFirst) {
    const data = section.key === 'overview'
      ? this.faction.design?.meta
      : this.faction.design?.[section.key];

    if (!data && section.key !== 'overview') return null;

    const container = document.createElement('div');
    container.className = 'section-panel';
    container.id = `section-${section.key}`;
    if (isFirst) container.classList.add('expanded');

    const header = document.createElement('div');
    header.className = 'section-header';
    header.innerHTML = `<h2>${section.title}</h2>`;
    header.style.cursor = 'pointer';
    header.onclick = () => {
      container.classList.toggle('expanded');
    };
    container.appendChild(header);

    const content = document.createElement('div');
    content.className = 'section-content';

    if (section.key === 'overview') {
      content.appendChild(this.renderOverviewContent());
    } else if (section.key === 'abilities') {
      content.appendChild(this.renderAbilitiesContent());
    } else if (section.key === 'units') {
      content.appendChild(this.renderUnitsContent());
    } else if (section.key === 'specialAbilities') {
      content.appendChild(this.renderSpecialAbilitiesContent());
    } else if (section.key === 'powers') {
      content.appendChild(this.renderPowersContent());
    }

    // Add Claude Q&A for this section if available
    const sectionQA = this.claudeQA.section?.[section.key];
    if (sectionQA?.questions?.length > 0 || sectionQA?.feedback) {
      const qaDiv = document.createElement('div');
      qaDiv.className = 'section-qa';
      qaDiv.appendChild(this.renderClaudeQA(sectionQA));
      content.appendChild(qaDiv);
    }

    container.appendChild(content);
    return container;
  }

  renderOverviewContent() {
    const div = document.createElement('div');
    const meta = this.faction.design?.meta || {};
    const ae = this.faction.design?.ae || {};

    // Build status label - handle case where app might not have getBuildStatusLabel
    let statusLabel = 'Unknown';
    if (this.app && this.app.getBuildStatusLabel) {
      try {
        statusLabel = this.app.getBuildStatusLabel(this.faction);
      } catch (e) {
        statusLabel = this.faction.build?.status || 'none';
      }
    } else {
      statusLabel = this.faction.build?.status || 'none';
    }

    div.innerHTML = `
      <div class="field-row">
        <label>Name:</label>
        <span class="read-only-field">${ae.name || this.faction.name || 'N/A'}</span>
      </div>
      <div class="field-row">
        <label>Acronym:</label>
        <span class="read-only-field">${ae.acronym || 'N/A'}</span>
      </div>
      <div class="field-row">
        <label>Status:</label>
        <span class="read-only-field ${this.faction.build?.status ? `status-${this.faction.build.status}` : ''}">
          ${statusLabel}
        </span>
      </div>
      ${meta.color ? `
        <div class="field-row">
          <label>Color:</label>
          <span class="read-only-field" style="background: ${meta.color}; padding: 2px 6px; border-radius: 3px;">
            ${meta.color}
          </span>
        </div>
      ` : ''}
      ${meta.adminNotes ? `
        <div class="field-row">
          <label>Admin Notes:</label>
          <p class="read-only-field">${escapeHtml(meta.adminNotes)}</p>
        </div>
      ` : ''}
    `;

    return div;
  }

  renderAbilitiesContent() {
    const div = document.createElement('div');
    const abilities = this.faction.design?.abilities || [];

    if (abilities.length === 0) {
      div.innerHTML = '<p class="placeholder">No abilities defined.</p>';
      return div;
    }

    div.innerHTML = abilities.map((ability, idx) => `
      <div class="ability-item">
        <strong>${ability.name || `Ability ${idx + 1}`}</strong>
        ${ability.desc ? `<p>${escapeHtml(ability.desc)}</p>` : ''}
      </div>
    `).join('');

    return div;
  }

  renderUnitsContent() {
    const div = document.createElement('div');
    const units = this.faction.design?.units || [];

    if (units.length === 0) {
      div.innerHTML = '<p class="placeholder">No units defined.</p>';
      return div;
    }

    div.innerHTML = `<p class="section-status-label">
      ${units.length} / 5 units
    </p>` + units.map((unit, idx) => `
      <div class="unit-item">
        <strong>${unit.name || `Unit ${idx + 1}`}</strong>
        ${unit.type ? `<span class="unit-type">${unit.type}</span>` : ''}
        ${unit.stats ? `<p class="unit-stats">${escapeHtml(JSON.stringify(unit.stats))}</p>` : ''}
      </div>
    `).join('');

    return div;
  }

  renderSpecialAbilitiesContent() {
    const div = document.createElement('div');
    const specials = this.faction.design?.specialAbilities || [];

    if (specials.length === 0) {
      div.innerHTML = '<p class="placeholder">No special abilities defined.</p>';
      return div;
    }

    div.innerHTML = specials.map((special, idx) => `
      <div class="special-item">
        <strong>${special.name || `Special ${idx + 1}`}</strong>
        ${special.desc ? `<p>${escapeHtml(special.desc)}</p>` : ''}
      </div>
    `).join('');

    return div;
  }

  renderPowersContent() {
    const div = document.createElement('div');
    const powers = this.faction.design?.powers || [];

    if (powers.length === 0) {
      div.innerHTML = '<p class="placeholder">No powers defined.</p>';
      return div;
    }

    div.innerHTML = powers.map((power, idx) => `
      <div class="power-item">
        <strong>${power.name || `Power ${idx + 1}`}</strong>
        ${power.desc ? `<p>${escapeHtml(power.desc)}</p>` : ''}
      </div>
    `).join('');

    return div;
  }

  renderClaudeQASection() {
    const container = document.createElement('div');
    container.className = 'section-panel';
    container.id = 'section-claudeQA';

    const header = document.createElement('div');
    header.className = 'section-header';
    header.innerHTML = '<h2>Claude Feedback & Q&A</h2>';
    header.style.cursor = 'pointer';
    header.onclick = () => {
      container.classList.toggle('expanded');
    };
    container.appendChild(header);

    const content = document.createElement('div');
    content.className = 'section-content';

    const buildQA = this.claudeQA.build;
    if (buildQA) {
      content.appendChild(this.renderClaudeQA(buildQA));
    } else {
      content.innerHTML = '<p class="placeholder">No Claude feedback available.</p>';
    }

    container.appendChild(content);
    return container;
  }

  renderClaudeQA(qaData) {
    const div = document.createElement('div');
    div.className = 'qa-section';

    if (!qaData) return div;

    // Render questions
    if (qaData.questions && Array.isArray(qaData.questions)) {
      qaData.questions.forEach(q => {
        const qBox = document.createElement('div');
        qBox.className = `qa-box ${q.adminAnswer ? '' : 'qa-unanswered'}`;

        const qEl = document.createElement('div');
        qEl.className = 'qa-question';
        qEl.innerHTML = `<strong>Claude:</strong> "${escapeHtml(q.question)}"`;
        qBox.appendChild(qEl);

        if (q.adminAnswer) {
          const aEl = document.createElement('div');
          aEl.className = 'qa-answer';
          const timestamp = q.answeredAt
            ? new Date(q.answeredAt * 1000).toLocaleString()
            : '';
          aEl.innerHTML = `
            <strong>Admin Response:</strong> ${escapeHtml(q.adminAnswer)}
            ${timestamp ? `<div class="qa-timestamp">— ${timestamp}</div>` : ''}
          `;
          qBox.appendChild(aEl);
        } else {
          const pendingEl = document.createElement('div');
          pendingEl.className = 'qa-pending';
          pendingEl.innerHTML = '<strong>Awaiting admin response...</strong>';
          qBox.appendChild(pendingEl);
        }

        div.appendChild(qBox);
      });
    }

    // Render feedback
    if (qaData.feedback) {
      const feedbackBox = document.createElement('div');
      feedbackBox.className = 'qa-feedback-box';
      feedbackBox.innerHTML = `
        <strong>Claude Feedback:</strong>
        <div class="qa-feedback-text">${escapeHtml(qaData.feedback).replace(/\n/g, '<br>')}</div>
      `;
      div.appendChild(feedbackBox);
    }

    return div;
  }

  scrollToSection(sectionKey) {
    const el = document.getElementById(`section-${sectionKey}`);
    if (el) {
      el.classList.add('expanded');
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  setupSidebarScrollLinks() {
    const links = document.querySelectorAll('.section-link');
    links.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const section = link.dataset.section;
        this.scrollToSection(section);
      });
    });
  }
}

// Utility to escape HTML for display
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}
