// Cthulhu Wars Faction Designer - Main Application
(function() {
  'use strict';

  // Measured end-to-end times (2026-10-09), shown under the matching buttons.
  const SB_ALL_EXTRACT_MINUTES = 4;

  class App {
    constructor() {
      this.root = document.getElementById('root');
      this.state = {
        token: localStorage.getItem('cw_designer_token'),
        username: localStorage.getItem('cw_designer_username'),
        factions: null,
        currentFaction: null,
        builtDesign: null,
        reference: null
      };
      this.saveQueue = new Map();
      this.saveTimer = null;
      this.saveIndicator = document.getElementById('save-indicator');
    }

    start() {
      // Load reference data
      fetch('/designer/reference.json')
        .then(r => r.json())
        .then(ref => {
          this.state.reference = ref;
          this.startRouter();
        })
        .catch(err => {
          console.error('Failed to load reference.json:', err);
          this.startRouter();
        });
    }

    startRouter() {
      // Admin console "view" link: #/admin-view/<admin token>/<fid>. The token is kept for this tab only
      // and taken out of the address bar straight away.
      const av = window.location.hash.match(/^#\/admin-view\/([^/]+)\/([^/]+)/);
      if (av) {
        sessionStorage.setItem('cw_designer_admin_view', av[1]);
        history.replaceState(null, '', `#/faction/${av[2]}`);
      }
      this.state.adminView = sessionStorage.getItem('cw_designer_admin_view');
      window.addEventListener('hashchange', () => this.route());
      this.route();
    }

    route() {
      const hash = window.location.hash.slice(1) || '/';
      const [path, ...rest] = hash.split('/').filter(Boolean);
      // Opening any other section clears a shown "complete" extraction status back to n/a
      if (!(path === 'faction' && rest[0] && rest.length === 1)) this.extractComplete = null;

      if (this.state.adminView) {
        // Admin view only ever shows one faction, read only
        if (path === 'faction' && rest[0]) {
          const screen = rest.slice(1).join('/');
          if (screen) this.renderScreen(rest[0], screen); else this.loadFaction(rest[0]);
        } else {
          this.root.innerHTML = '<p style="padding:20px;">Admin view: close this tab to go back to the admin console.</p>';
        }
      } else if (!this.state.token && path !== 'register') {
        this.renderLogin();
      } else if (path === 'register') {
        this.renderRegister();
      } else if (path === 'factions') {
        this.renderFactionList();
      } else if (path === 'unit' && rest[0]) {
        const uid = rest[0];
        const screen = rest.slice(1).join('/');
        if (!screen) {
          this.renderUnitScreen(uid);
        } else if (screen === 'build') {
          this.renderUnitBuildScreen(uid);
        }
      } else if (path === 'faction') {
        const fid = rest[0];
        const screen = rest.slice(1).join('/');
        if (fid && !screen) {
          this.loadFaction(fid);
        } else if (fid && screen) {
          this.renderScreen(fid, screen);
        }
      } else {
        // Default to faction list if logged in
        window.location.hash = '#/factions';
      }
    }

    // API methods
    async api(method, path, body = null) {
      const opts = {
        method,
        headers: {}
      };

      if (this.state.token) {
        opts.headers['Authorization'] = `Bearer ${this.state.token}`;
      }

      if (body && typeof body === 'object') {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
      } else if (body) {
        opts.body = body;
      }

      const url = `/designer/api${path}`;
      const resp = await fetch(url, opts);

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({error: 'Request failed'}));
        throw new Error(err.error || 'Request failed');
      }

      return resp.json();
    }

    // Auth
    async login(username, password) {
      const data = await this.api('POST', '/login', {username, password});
      this.state.token = data.token;
      this.state.username = data.username;
      localStorage.setItem('cw_designer_token', data.token);
      localStorage.setItem('cw_designer_username', data.username);
      window.location.hash = '#/factions';
    }

    async register(username, password) {
      const data = await this.api('POST', '/register', {username, password});
      this.state.token = data.token;
      this.state.username = data.username;
      localStorage.setItem('cw_designer_token', data.token);
      localStorage.setItem('cw_designer_username', data.username);
      window.location.hash = '#/factions';
    }

    logout() {
      this.api('POST', '/logout').catch(() => {});
      this.state.token = null;
      this.state.username = null;
      localStorage.removeItem('cw_designer_token');
      localStorage.removeItem('cw_designer_username');
      window.location.hash = '#/';
    }

    // Factions
    async loadFactionList() {
      const data = await this.api('GET', '/factions');
      this.state.factions = data.factions;
      return data.factions;
    }

    async createFaction(name, acronym) {
      const data = await this.api('POST', '/factions', {name, acronym});
      return data;
    }

    async loadFaction(fid) {
      const data = this.state.adminView
        ? await this.api('GET', `/admin/${this.state.adminView}/view-faction/${fid}`)
        : await this.api('GET', `/factions/${fid}`);
      this.state.currentFaction = data;
      this.state.builtDesign = data.builtDesign;
      // Only draw the main page if the user is still on it (a slow load must not cover a section they opened since)
      if (window.location.hash.replace(/\/$/, '') === `#/faction/${fid}`) this.renderMainDesign();
    }

    ordinal(n) {
      const t = n % 100, u = n % 10;
      if (t >= 11 && t <= 13) return n + 'th';
      return n + (u === 1 ? 'st' : u === 2 ? 'nd' : u === 3 ? 'rd' : 'th');
    }

    // Extraction status under the extract buttons: n/a -> waiting to be picked up -> Nth in queue ->
    // in process -> complete. "Complete" shows once a request this page saw finishes, and clears back
    // to n/a when the user opens another section (see route()).
    showExtractStatus(fid, status) {
      const el = this.extractStatusEl;
      if (!el) return;
      this.extractActive = this.extractActive || {};
      let text;
      if (status) {
        this.extractActive[fid] = true;
        if (this.extractComplete === fid) this.extractComplete = null;
        text = status.state === 'in_process' ? 'in process'
             : status.state === 'queued' ? `${this.ordinal(status.position)} in queue`
             : 'waiting to be picked up';
      } else {
        if (this.extractActive[fid]) {
          delete this.extractActive[fid];
          this.extractComplete = fid;
        }
        text = this.extractComplete === fid ? 'complete' : 'n/a';
      }
      el.textContent = `Extraction status: ${text}`;
    }

    async refreshExtractStatus(fid) {
      if (!this.extractStatusEl || !document.body.contains(this.extractStatusEl)) return;
      try {
        const data = this.state.adminView
          ? await this.api('GET', `/admin/${this.state.adminView}/view-faction/${fid}`).then(d => ({status: d.extractQueue}))
          : await this.api('GET', `/factions/${fid}/extract-queue`);
        this.showExtractStatus(fid, data.status);
      } catch (e) { /* keep the last status */ }
    }

    // Re-check every 20 seconds while the main page is showing, so the place counts down
    startExtractStatusPoll(fid) {
      if (this.extractStatusTimer) clearInterval(this.extractStatusTimer);
      this.extractStatusTimer = setInterval(() => {
        if (!this.extractStatusEl || !document.body.contains(this.extractStatusEl)) {
          clearInterval(this.extractStatusTimer);
          this.extractStatusTimer = null;
          return;
        }
        this.refreshExtractStatus(fid);
      }, 20000);
    }

    // A faction shared with this user as read only (owner set it up from the admin console)
    isReadOnly() {
      return !!(this.state.currentFaction && this.state.currentFaction.readOnly);
    }

    // Read only: every field is greyed out and every button that would change something is hidden.
    // Buttons that only move between pages are kept (Exit to Main, Back to List, section buttons).
    lockReadOnly(el) {
      if (!this.isReadOnly() || !el) return;
      el.querySelectorAll('input, select, textarea').forEach(x => { x.disabled = true; });
      el.querySelectorAll('button').forEach(b => {
        const keep = b.dataset.nav === '1' || b.textContent.trim() === 'Exit to Main';
        if (!keep) b.style.display = 'none';
      });
    }

    readOnlyBanner() {
      const f = this.state.currentFaction;
      const div = document.createElement('div');
      div.className = 'read-only-banner';
      div.style.cssText = 'border: 1px solid #000; background: #fde68a; color: #222; padding: 8px 12px; margin: 10px 0; border-radius: 4px;';
      div.textContent = f.adminView
        ? `Admin view (read only): designed by ${f.ownerName || f.owner}. You can look at everything, but nothing can be changed here.`
        : `Read only: ${f.ownerName || f.owner} shared this design with you. You can look at everything, but you can't change it.`;
      return div;
    }

    async patch(fid, ops) {
      if (this.isReadOnly()) return;
      const data = await this.api('POST', `/factions/${fid}/patch`, {ops});
      // Update local state
      if (this.state.currentFaction && this.state.currentFaction.id === fid) {
        this.state.currentFaction.current = data.current;
        this.state.currentFaction.maxVersion = data.maxVersion;
        this.state.currentFaction.versions = data.versions;
        this.state.currentFaction.session = data.session;
        this.state.currentFaction.updated = data.updated;
      }
    }

    async closeSession(fid) {
      if (this.isReadOnly()) return;
      await this.api('POST', `/factions/${fid}/close-session`);
    }

    async createRequest(id, type, text, data, kind = 'faction') {
      const endpoint = kind === 'unit' ? `/units/${id}/request` : `/factions/${id}/request`;
      const r = await this.api('POST', endpoint, {type, text, data});
      if (type === 'extract' && kind === 'faction') this.refreshExtractStatus(id);
      return r;
    }

    async getRequests(fid) {
      return await this.api('GET', `/factions/${fid}/requests`);
    }

    // Image upload with downscaling
    async uploadImage(kind) {
      if (this.isReadOnly()) return null;
      return new Promise((resolve) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';

        input.onchange = async () => {
          const file = input.files[0];
          if (!file) {
            resolve(null);
            return;
          }

          try {
            // Show saving indicator
            this.showSaveIndicator('saving', 'Uploading image...');

            // Downscale
            const maxSize = kind === 'small' ? 800 : 2000;
            const blob = await this.downscaleImage(file, maxSize);

            // Upload
            const resp = await fetch('/designer/api/images', {
              method: 'POST',
              headers: {
                'Authorization': `Bearer ${this.state.token}`,
                'Content-Type': blob.type
              },
              body: blob
            });

            if (!resp.ok) {
              const err = await resp.json().catch(() => ({error: 'Upload failed'}));
              throw new Error(err.error);
            }

            const data = await resp.json();
            this.showSaveIndicator('saved', 'Image uploaded');
            setTimeout(() => this.hideSaveIndicator(), 2000);
            resolve(data.id);
          } catch (err) {
            console.error('Image upload error:', err);
            this.showSaveIndicator('error', 'Upload failed: ' + err.message);
            setTimeout(() => this.hideSaveIndicator(), 3000);
            resolve(null);
          }
        };

        input.click();
      });
    }

    async downscaleImage(file, maxSize) {
      return new Promise((resolve, reject) => {
        const img = new Image();
        const url = URL.createObjectURL(file);

        img.onload = () => {
          URL.revokeObjectURL(url);

          let {width, height} = img;
          const longSide = Math.max(width, height);

          if (longSide > maxSize) {
            const scale = maxSize / longSide;
            width = Math.round(width * scale);
            height = Math.round(height * scale);
          }

          const canvas = document.createElement('canvas');
          canvas.width = width;
          canvas.height = height;
          const ctx = canvas.getContext('2d');
          ctx.drawImage(img, 0, 0, width, height);

          // Try webp first
          canvas.toBlob((blob) => {
            if (blob) {
              resolve(blob);
            } else {
              // Fallback to png
              canvas.toBlob((blob) => {
                resolve(blob);
              }, 'image/png');
            }
          }, 'image/webp', 0.85);
        };

        img.onerror = () => {
          URL.revokeObjectURL(url);
          reject(new Error('Failed to load image'));
        };

        img.src = url;
      });
    }

    imgUrl(id) {
      return `/designer/img/${id}`;
    }

    // CW / Necro library picker
    async pickLibraryImage() {
      if (this.isReadOnly()) return null;

      return new Promise(async (resolve) => {
        // Load library.json once and cache
        if (!this.libraryCache) {
          try {
            const resp = await fetch('/designer/library/library.json');
            if (!resp.ok) throw new Error('Failed to load library');
            this.libraryCache = await resp.json();
          } catch (err) {
            console.error('Library load error:', err);
            this.showSaveIndicator('error', 'Failed to load library: ' + err.message);
            setTimeout(() => this.hideSaveIndicator(), 3000);
            resolve(null);
            return;
          }
        }

        const library = this.libraryCache;

        // Own layer above #overlay, so the map viewer underneath stays open
        const layer = document.createElement('div');
        layer.className = 'library-picker';
        const close = () => layer.remove();

        // Group by type
        const sections = {
          'Cultist': [],
          'Monster': [],
          'Terror': [],
          'GOO': [],
          'Elder God': []
        };

        library.forEach(item => {
          if (sections[item.type]) sections[item.type].push(item);
        });

        // Sort each section alphabetically by name, then faction
        Object.keys(sections).forEach(key => {
          sections[key].sort((a, b) => {
            if (a.name !== b.name) return a.name.localeCompare(b.name);
            return (a.faction || '').localeCompare(b.faction || '');
          });
        });

        // Build overlay content
        const content = document.createElement('div');
        content.style.cssText = 'background: #111; padding: 20px; max-width: 1100px; margin: 0 auto;';

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'sx-btn';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.style.marginBottom = '20px';
        cancelBtn.onclick = () => {
          close();
          resolve(null);
        };
        content.appendChild(cancelBtn);

        const sectionTitles = {
          'Cultist': 'Cultists',
          'Monster': 'Monsters',
          'Terror': 'Terrors',
          'GOO': 'GOOs / iGOOs',
          'Elder God': 'Elder Gods'
        };

        ['Cultist', 'Monster', 'Terror', 'GOO', 'Elder God'].forEach(type => {
          const items = sections[type];
          if (items.length === 0) return;

          const heading = document.createElement('h3');
          heading.textContent = sectionTitles[type];
          heading.style.cssText = 'margin: 20px 0 10px 0; color: #eee;';
          content.appendChild(heading);

          const grid = document.createElement('div');
          grid.style.cssText = 'display: grid; grid-template-columns: repeat(auto-fill, minmax(96px, 1fr)); gap: 12px; margin-bottom: 20px;';

          items.forEach(item => {
            const tile = document.createElement('div');
            tile.style.cssText = 'display: flex; flex-direction: column; align-items: center; cursor: pointer;';

            const img = document.createElement('img');
            img.src = `/designer/library/${item.file}`;
            img.loading = 'lazy';
            img.style.cssText = 'width: 100%; height: 80px; object-fit: contain; border: 1px solid #666; background: #222;';

            const nameDiv = document.createElement('div');
            nameDiv.textContent = item.name;
            nameDiv.style.cssText = 'font-size: 12px; margin-top: 4px; text-align: center; color: #eee;';

            const factionDiv = document.createElement('div');
            if (item.faction && item.faction !== 'Neutral') {
              factionDiv.textContent = item.faction;
              factionDiv.style.cssText = 'font-size: 10px; color: #aaa; text-align: center;';
            }

            tile.onclick = async () => {
              try {
                this.showSaveIndicator('saving', 'Uploading image...');

                // Fetch the file as a blob
                const resp = await fetch(`/designer/library/${item.file}`);
                if (!resp.ok) throw new Error('Failed to fetch image');
                const blob = await resp.blob();

                // Upload to server
                const uploadResp = await fetch('/designer/api/images', {
                  method: 'POST',
                  headers: {
                    'Authorization': `Bearer ${this.state.token}`,
                    'Content-Type': blob.type || (item.file.endsWith('.webp') ? 'image/webp' : 'image/png')
                  },
                  body: blob
                });

                if (!uploadResp.ok) {
                  const err = await uploadResp.json().catch(() => ({error: 'Upload failed'}));
                  throw new Error(err.error);
                }

                const data = await uploadResp.json();
                this.showSaveIndicator('saved', 'Image uploaded');
                setTimeout(() => this.hideSaveIndicator(), 2000);
                close();
                resolve(data.id);
              } catch (err) {
                console.error('Library image upload error:', err);
                this.showSaveIndicator('error', 'Upload failed: ' + err.message);
                setTimeout(() => this.hideSaveIndicator(), 3000);
                resolve(null);
              }
            };

            tile.appendChild(img);
            tile.appendChild(nameDiv);
            if (factionDiv.textContent) tile.appendChild(factionDiv);
            grid.appendChild(tile);
          });

          content.appendChild(grid);
        });

        layer.appendChild(content);
        document.body.appendChild(layer);
      });
    }

    // Autosave
    // kind 'unit' = a neutral unit from My Units (fid is then its unit id)
    scheduleSave(fid, path, value, kind = 'faction') {
      if (this.isReadOnly()) return;
      const key = `${kind}:${fid}:${path}`;
      this.saveQueue.set(key, {fid, path, value, kind});

      clearTimeout(this.saveTimer);
      this.saveTimer = setTimeout(() => this.flushSaves(), 600);

      this.showSaveIndicator('saving', 'Saving...');
    }

    async flushSaves() {
      if (this.saveQueue.size === 0) return;

      const saves = Array.from(this.saveQueue.values());
      this.saveQueue.clear();

      // Group by faction (or unit)
      const byFid = {};
      for (const {fid, path, value, kind} of saves) {
        const g = `${kind}:${fid}`;
        if (!byFid[g]) byFid[g] = [];
        byFid[g].push({op: 'set', path, value});
      }

      // Send patches
      for (const [g, ops] of Object.entries(byFid)) {
        const [kind, fid] = g.split(':');
        try {
          if (kind === 'unit') await this.api('POST', `/units/${fid}/patch`, {ops});
          else await this.patch(fid, ops);
          this.showSaveIndicator('saved', 'All changes saved');
          setTimeout(() => this.hideSaveIndicator(), 2000);
        } catch (err) {
          console.error('Save error:', err);
          this.showSaveIndicator('error', 'Save failed: ' + err.message);
          // Retry after delay
          setTimeout(() => {
            for (const op of ops) {
              this.saveQueue.set(`${kind}:${fid}:${op.path}`, {fid, path: op.path, value: op.value, kind});
            }
            this.flushSaves();
          }, 5000);
        }
      }
    }

    showSaveIndicator(type, text) {
      this.saveIndicator.textContent = text;
      this.saveIndicator.className = type;
      this.saveIndicator.style.display = 'block';
    }

    hideSaveIndicator() {
      this.saveIndicator.style.display = 'none';
    }

    // Overlay
    openOverlay(content) {
      const overlay = document.getElementById('overlay');
      overlay.innerHTML = '';

      if (typeof content === 'string') {
        overlay.innerHTML = content;
      } else {
        overlay.appendChild(content);
      }

      const closeBtn = document.createElement('button');
      closeBtn.textContent = 'Close';
      closeBtn.style.display = 'block';
      closeBtn.style.margin = '20px auto';
      closeBtn.onclick = () => this.closeOverlay();
      overlay.appendChild(closeBtn);

      overlay.style.display = 'block';
    }

    closeOverlay() {
      document.getElementById('overlay').style.display = 'none';
    }

    // Confirm dialog
    confirm(message, yesLabel = 'Yes', noLabel = 'No') {
      return new Promise((resolve) => {
        const div = document.createElement('div');
        div.className = 'confirm-overlay';

        const dialog = document.createElement('div');
        dialog.className = 'confirm-dialog';

        const p = document.createElement('p');
        p.textContent = message;
        dialog.appendChild(p);

        const buttons = document.createElement('div');
        buttons.className = 'buttons';

        const yesBtn = document.createElement('button');
        yesBtn.className = 'primary';
        yesBtn.textContent = yesLabel;
        yesBtn.onclick = () => {
          div.remove();
          resolve(true);
        };

        const noBtn = document.createElement('button');
        noBtn.textContent = noLabel;
        noBtn.onclick = () => {
          div.remove();
          resolve(false);
        };

        buttons.appendChild(yesBtn);
        buttons.appendChild(noBtn);
        dialog.appendChild(buttons);
        div.appendChild(dialog);
        document.body.appendChild(div);
      });
    }

    // Render methods
    renderLogin() {
      const form = document.createElement('div');
      form.className = 'auth-form';

      const title = document.createElement('h1');
      title.textContent = 'Faction Designer Login';
      form.appendChild(title);

      const userGroup = document.createElement('div');
      userGroup.className = 'form-group';
      const userLabel = document.createElement('label');
      userLabel.textContent = 'Username';
      const userInput = document.createElement('input');
      userInput.type = 'text';
      userInput.id = 'username';
      userGroup.appendChild(userLabel);
      userGroup.appendChild(userInput);
      form.appendChild(userGroup);

      const passGroup = document.createElement('div');
      passGroup.className = 'form-group';
      const passLabel = document.createElement('label');
      passLabel.textContent = 'Password';
      const passInput = document.createElement('input');
      passInput.type = 'password';
      passInput.id = 'password';
      passGroup.appendChild(passLabel);
      passGroup.appendChild(passInput);
      form.appendChild(passGroup);

      const loginBtn = document.createElement('button');
      loginBtn.className = 'primary';
      loginBtn.textContent = 'Login';
      loginBtn.onclick = async () => {
        const username = userInput.value.trim();
        const password = passInput.value;
        if (!username || !password) return;

        try {
          loginBtn.disabled = true;
          await this.login(username, password);
        } catch (err) {
          loginBtn.disabled = false;
          this.showError(form, err.message);
        }
      };
      form.appendChild(loginBtn);

      const registerLink = document.createElement('button');
      registerLink.className = 'link-button';
      registerLink.textContent = 'Need an account? Register';
      registerLink.onclick = () => {
        window.location.hash = '#/register';
      };
      form.appendChild(registerLink);

      this.root.innerHTML = '';
      this.root.appendChild(form);
    }

    renderRegister() {
      const form = document.createElement('div');
      form.className = 'auth-form';

      const title = document.createElement('h1');
      title.textContent = 'Register';
      form.appendChild(title);

      const userGroup = document.createElement('div');
      userGroup.className = 'form-group';
      const userLabel = document.createElement('label');
      userLabel.textContent = 'Username (3-24 characters, letters/numbers/_/.-/)';
      const userInput = document.createElement('input');
      userInput.type = 'text';
      userInput.id = 'username';
      userGroup.appendChild(userLabel);
      userGroup.appendChild(userInput);
      form.appendChild(userGroup);

      const passGroup = document.createElement('div');
      passGroup.className = 'form-group';
      const passLabel = document.createElement('label');
      passLabel.textContent = 'Password (at least 4 characters)';
      const passInput = document.createElement('input');
      passInput.type = 'password';
      passInput.id = 'password';
      passGroup.appendChild(passLabel);
      passGroup.appendChild(passInput);
      form.appendChild(passGroup);

      const registerBtn = document.createElement('button');
      registerBtn.className = 'primary';
      registerBtn.textContent = 'Register';
      registerBtn.onclick = async () => {
        const username = userInput.value.trim();
        const password = passInput.value;
        if (!username || !password) return;
        if (username.length < 3 || username.length > 24) {
          this.showError(form, 'Username must be 3-24 characters');
          return;
        }
        if (password.length < 4) {
          this.showError(form, 'Password must be at least 4 characters');
          return;
        }

        try {
          registerBtn.disabled = true;
          await this.register(username, password);
        } catch (err) {
          registerBtn.disabled = false;
          this.showError(form, err.message);
        }
      };
      form.appendChild(registerBtn);

      const loginLink = document.createElement('button');
      loginLink.className = 'link-button';
      loginLink.textContent = 'Already have an account? Login';
      loginLink.onclick = () => {
        window.location.hash = '#/';
      };
      form.appendChild(loginLink);

      this.root.innerHTML = '';
      this.root.appendChild(form);
    }

    showError(container, message) {
      let errorDiv = container.querySelector('.error');
      if (!errorDiv) {
        errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        container.appendChild(errorDiv);
      }
      errorDiv.textContent = message;
    }

    async renderFactionList() {
      this.root.innerHTML = '<div class="spinner"></div>';

      try {
        const [factions, units] = await Promise.all([
          this.loadFactionList(),
          this.api('GET', '/units').then(d => d.units)
        ]);

        this.root.innerHTML = '';

        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.alignItems = 'center';
        header.style.marginBottom = '20px';

        const title = document.createElement('h1');
        title.textContent = 'My Customs';
        header.appendChild(title);

        const logoutBtn = document.createElement('button');
        logoutBtn.textContent = 'Logout';
        logoutBtn.onclick = () => this.logout();
        header.appendChild(logoutBtn);

        this.root.appendChild(header);

        const factionsTitle = document.createElement('h2');
        factionsTitle.textContent = 'My Factions';
        factionsTitle.style.marginBottom = '12px';
        this.root.appendChild(factionsTitle);

        const createBtn = document.createElement('button');
        createBtn.className = 'primary';
        createBtn.textContent = 'Create New Faction';
        createBtn.style.marginBottom = '20px';
        createBtn.onclick = () => this.showCreateDialog();
        this.root.appendChild(createBtn);

        if (factions.filter(f => !f.readOnly).length === 0) {
          const p = document.createElement('p');
          p.textContent = 'No factions yet. Create one to get started.';
          p.style.color = '#888';
          this.root.appendChild(p);
        } else {
          const grid = document.createElement('div');
          grid.className = 'faction-grid';

          for (const faction of factions.filter(f => !f.readOnly)) {
            const card = document.createElement('div');
            card.className = 'faction-card';
            card.onclick = () => {
              window.location.hash = `#/faction/${faction.id}`;
            };

            const name = document.createElement('h3');
            name.textContent = faction.name;
            card.appendChild(name);

            const acronym = document.createElement('div');
            acronym.className = 'acronym';
            acronym.textContent = faction.acronym;
            card.appendChild(acronym);

            const status = document.createElement('div');
            status.className = 'status';
            status.textContent = `Status: ${faction.buildStatus || 'Not Ready'}`;
            card.appendChild(status);

            const updated = document.createElement('div');
            updated.className = 'status';
            updated.textContent = `Updated: ${new Date(faction.updated * 1000).toLocaleDateString()}`;
            card.appendChild(updated);

            grid.appendChild(card);
          }

          this.root.appendChild(grid);
        }

        // Designs other users shared with this user (read only)
        const shared = factions.filter(f => f.readOnly);
        if (shared.length) {
          const h = document.createElement('h2');
          h.textContent = 'Shared with me (read only)';
          h.style.marginTop = '30px';
          this.root.appendChild(h);
          const grid = document.createElement('div');
          grid.className = 'faction-grid';
          for (const faction of shared) {
            const card = document.createElement('div');
            card.className = 'faction-card';
            card.onclick = () => { window.location.hash = `#/faction/${faction.id}`; };
            const name = document.createElement('h3');
            name.textContent = faction.name;
            card.appendChild(name);
            const acronym = document.createElement('div');
            acronym.className = 'acronym';
            acronym.textContent = faction.acronym;
            card.appendChild(acronym);
            const by = document.createElement('div');
            by.className = 'status';
            by.textContent = `Designed by ${faction.ownerName || faction.owner}`;
            card.appendChild(by);
            grid.appendChild(card);
          }
          this.root.appendChild(grid);
        }

        // Neutral units, kept apart from any faction
        const unitsTitle = document.createElement('h2');
        unitsTitle.textContent = 'My Units';
        unitsTitle.style.margin = '30px 0 12px';
        this.root.appendChild(unitsTitle);

        const createUnitBtn = document.createElement('button');
        createUnitBtn.className = 'primary';
        createUnitBtn.textContent = 'Create New Unit';
        createUnitBtn.style.marginBottom = '20px';
        createUnitBtn.onclick = () => this.showCreateUnitDialog();
        this.root.appendChild(createUnitBtn);

        if (units.length === 0) {
          const p = document.createElement('p');
          p.textContent = 'No units yet. Create one to get started.';
          p.style.color = '#888';
          this.root.appendChild(p);
        } else {
          const grid = document.createElement('div');
          grid.className = 'faction-grid';
          for (const unit of units) {
            const card = document.createElement('div');
            card.className = 'faction-card';
            card.onclick = () => { window.location.hash = `#/unit/${unit.id}`; };
            const name = document.createElement('h3');
            name.textContent = unit.name || 'Unnamed unit';
            card.appendChild(name);
            const type = document.createElement('div');
            type.className = 'status';
            type.textContent = `Type: ${unit.type || 'not chosen'}`;
            card.appendChild(type);
            const updated = document.createElement('div');
            updated.className = 'status';
            updated.textContent = `Updated: ${new Date(unit.updated * 1000).toLocaleDateString()}`;
            card.appendChild(updated);
            grid.appendChild(card);
          }
          this.root.appendChild(grid);
        }
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading factions: ${err.message}</p>`;
      }
    }

    showCreateDialog() {
      const overlay = document.createElement('div');
      overlay.className = 'confirm-overlay';

      const dialog = document.createElement('div');
      dialog.className = 'confirm-dialog';
      dialog.style.maxWidth = '600px';

      const title = document.createElement('h2');
      title.textContent = 'Create New Faction';
      title.style.marginBottom = '20px';
      dialog.appendChild(title);

      const nameGroup = document.createElement('div');
      nameGroup.className = 'form-group';
      const nameLabel = document.createElement('label');
      nameLabel.textContent = 'Faction Name (at least 5 characters)';
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.style.width = '100%';
      nameGroup.appendChild(nameLabel);
      nameGroup.appendChild(nameInput);
      dialog.appendChild(nameGroup);

      const acrGroup = document.createElement('div');
      acrGroup.className = 'form-group';
      const acrLabel = document.createElement('label');
      acrLabel.textContent = 'Faction Acronym (2-3 characters)';
      const acrInput = document.createElement('input');
      acrInput.type = 'text';
      acrInput.style.width = '100%';
      acrInput.style.textTransform = 'uppercase';
      acrGroup.appendChild(acrLabel);
      acrGroup.appendChild(acrInput);
      dialog.appendChild(acrGroup);

      const buttons = document.createElement('div');
      buttons.className = 'buttons';

      const createBtn = document.createElement('button');
      createBtn.className = 'primary';
      createBtn.textContent = 'Create';
      createBtn.disabled = true;

      const checkValid = () => {
        const name = nameInput.value.trim();
        const acr = acrInput.value.trim().toUpperCase();
        createBtn.disabled = !(name.length >= 5 && acr.length >= 2 && acr.length <= 3);
      };

      nameInput.addEventListener('input', checkValid);
      acrInput.addEventListener('input', checkValid);

      createBtn.onclick = async () => {
        const name = nameInput.value.trim();
        const acronym = acrInput.value.trim().toUpperCase();

        try {
          createBtn.disabled = true;
          const faction = await this.createFaction(name, acronym);
          overlay.remove();
          window.location.hash = `#/faction/${faction.id}`;
        } catch (err) {
          createBtn.disabled = false;
          this.showError(dialog, err.message);
        }
      };

      const cancelBtn = document.createElement('button');
      cancelBtn.textContent = 'Cancel';
      cancelBtn.onclick = () => overlay.remove();

      buttons.appendChild(createBtn);
      buttons.appendChild(cancelBtn);
      dialog.appendChild(buttons);

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);
    }

    renderMainDesign() {
      const faction = this.state.currentFaction;
      const design = faction.design;

      this.root.innerHTML = '';

      // Header with faction name and color picker
      const header = document.createElement('div');
      header.className = 'design-header';

      const backBtn = document.createElement('button');
      backBtn.textContent = '← Back to List';
      backBtn.dataset.nav = '1';
      backBtn.onclick = () => {
        this.flushSaves();
        window.location.hash = '#/factions';
      };
      header.appendChild(backBtn);

      const nameTitle = document.createElement('h1');
      nameTitle.className = 'faction-title';
      nameTitle.textContent = faction.name;
      header.appendChild(nameTitle);

      if (design.meta) {
        const colorGroup = document.createElement('div');
        colorGroup.className = 'color-picker-group';

        const colorLabel = document.createElement('span');
        colorLabel.textContent = 'Faction colour (for tinting unit art):';
        colorGroup.appendChild(colorLabel);

        const colorInput = document.createElement('input');
        colorInput.type = 'color';
        colorInput.value = design.meta.color || '#888888';
        colorInput.addEventListener('change', () => {
          this.scheduleSave(faction.id, 'meta.color', colorInput.value);
          design.meta.color = colorInput.value;
        });
        colorGroup.appendChild(colorInput);

        header.appendChild(colorGroup);
      }

      this.root.appendChild(header);
      if (this.isReadOnly()) this.root.appendChild(this.readOnlyBanner());

      // Images section
      const imagesSection = document.createElement('div');
      imagesSection.className = 'images-section';

      // Faction card
      const cardSection = document.createElement('div');
      cardSection.className = 'card-image-section';
      const cardTitle = document.createElement('h3');
      cardTitle.textContent = 'Faction Card';
      cardSection.appendChild(cardTitle);

      if (design.card.image) {
        const img = document.createElement('img');
        img.src = this.imgUrl(design.card.image);
        img.className = 'image-thumbnail';
        img.onclick = () => this.showCardFullscreen(faction);
        cardSection.appendChild(img);

        // Two extract choices. Times are measured end-to-end on a 5-unit card (2026-10-09).
        const extractRow = document.createElement('div');
        extractRow.className = 'extract-choices';
        extractRow.style.cssText = 'display: flex; gap: 12px; margin-top: 10px; flex-wrap: wrap;';
        const extractChoice = (label, minutes, withImages) => {
          const wrap = document.createElement('div');
          wrap.style.cssText = 'display: flex; flex-direction: column; align-items: center;';
          const b = document.createElement('button');
          b.className = 'small';
          b.textContent = label;
          const est = document.createElement('div');
          est.className = 'extract-estimate';
          est.style.cssText = 'font-size: 0.8em; opacity: 0.75; margin-top: 3px;';
          est.textContent = `about ${minutes} min`;
          b.onclick = async () => {
            const hasContent = !Rules.isEmpty('ufa', design) || !Rules.isEmpty('setup', design) ||
                              !Rules.isEmpty('units', design) || !Rules.isEmpty('sbr', design);
            const hasPictures = withImages && (!!design.card.glyph ||
                              ((design.units && design.units.rows) || []).some(u => u.silhouette));
            if (hasContent || hasPictures) {
              const confirmed = await this.confirm(
                withImages ? 'Extract will overwrite existing sections, unit silhouettes and the faction glyph. Are you sure?'
                           : 'Extract will overwrite existing sections. Are you sure?',
                'Yes - Extract',
                'Cancel'
              );
              if (!confirmed) return;
            }

            b.disabled = true;
            try {
              await this.createRequest(
                faction.id,
                'extract',
                withImages ? `Extract card text + images for ${faction.name}` : `Extract card text for ${faction.name}`,
                {target: 'card', image: design.card.image, images: withImages}
              );
              alert(`Extract requested. The card will be read and the sections filled in for you, in about ${minutes} minutes.`);
            } catch (err) {
              alert('Extract request failed: ' + err.message);
            }
            b.disabled = false;
          };
          wrap.appendChild(b);
          wrap.appendChild(est);
          extractRow.appendChild(wrap);
        };
        extractChoice('Extract text', 7, false);
        extractChoice('Extract text + images', 30, true);
        cardSection.appendChild(extractRow);

        // One extraction status line for the whole faction (n/a when nothing is queued)
        const extractStatus = document.createElement('div');
        extractStatus.className = 'extract-status';
        extractStatus.style.cssText = 'margin-top: 8px; font-size: 0.9em; font-weight: bold;';
        cardSection.appendChild(extractStatus);
        this.extractStatusEl = extractStatus;
        this.showExtractStatus(faction.id, faction.extractQueue);
        this.startExtractStatusPoll(faction.id);
      } else {
        const uploadBtn = document.createElement('button');
        uploadBtn.textContent = 'Upload faction card image';
        uploadBtn.onclick = async () => {
          const imageId = await this.uploadImage('card');
          if (imageId) {
            this.scheduleSave(faction.id, 'card.image', imageId);
            design.card.image = imageId;
            this.renderMainDesign();
          }
        };
        cardSection.appendChild(uploadBtn);
      }

      // Faction glyph (the faction's symbol). Extract fills it from the card when it can.
      const glyphDiv = document.createElement('div');
      glyphDiv.className = 'glyph-image-section';
      glyphDiv.style.marginTop = '14px';
      const glyphTitle = document.createElement('h4');
      glyphTitle.textContent = 'Faction Glyph';
      glyphTitle.style.margin = '0 0 6px';
      glyphDiv.appendChild(glyphTitle);
      const setGlyph = id => {
        this.scheduleSave(faction.id, 'card.glyph', id);
        design.card.glyph = id;
        this.renderMainDesign();
      };
      const glyphUpload = async () => {
        const imageId = await this.uploadImage('small');
        if (imageId) setGlyph(imageId);
      };
      if (design.card.glyph) {
        const gimg = document.createElement('img');
        gimg.src = this.imgUrl(design.card.glyph);
        gimg.className = 'glyph-thumbnail';
        gimg.alt = 'Faction glyph';
        gimg.style.cssText = 'width: 72px; height: 72px; object-fit: contain; display: block; margin-bottom: 6px; cursor: pointer;';
        gimg.title = 'Click to replace';
        gimg.onclick = glyphUpload;
        glyphDiv.appendChild(gimg);
        const replaceBtn = document.createElement('button');
        replaceBtn.className = 'small';
        replaceBtn.textContent = 'Replace glyph';
        replaceBtn.onclick = glyphUpload;
        glyphDiv.appendChild(replaceBtn);
        const removeBtn = document.createElement('button');
        removeBtn.className = 'small';
        removeBtn.textContent = 'Remove glyph';
        removeBtn.style.marginLeft = '6px';
        removeBtn.onclick = () => setGlyph(null);
        glyphDiv.appendChild(removeBtn);
      } else {
        const glyphBtn = document.createElement('button');
        glyphBtn.textContent = 'Upload faction glyph';
        glyphBtn.onclick = glyphUpload;
        glyphDiv.appendChild(glyphBtn);
        if (design.card.image) {
          const note = document.createElement('div');
          note.className = 'sx-hint-text';
          note.style.cssText = 'font-size: 0.85em; opacity: 0.75; margin-top: 4px;';
          note.textContent = 'Or press "Extract text + images": it cuts the glyph and unit silhouettes out of the card for you.';
          glyphDiv.appendChild(note);
        }
      }
      cardSection.appendChild(glyphDiv);

      imagesSection.appendChild(cardSection);

      // Spellbook images
      const sbSection = document.createElement('div');
      sbSection.className = 'sb-images-section';
      const sbTitle = document.createElement('h3');
      sbTitle.textContent = 'Spellbook Images';
      sbSection.appendChild(sbTitle);

      if (Rules.sbAnyTwo(design.sb)) {
        // 2 sided spellbooks (any of them): one set of images for each side
        ['sbImages', 'sbImagesB'].forEach(key => {
          const sub = document.createElement('h4');
          sub.textContent = key === 'sbImagesB' ? 'Side B' : 'Side A';
          sbSection.appendChild(sub);
          const box = document.createElement('div');
          sbSection.appendChild(box);
          this.renderSpellbookImages(faction, box, key);
        });
      } else {
        this.renderSpellbookImages(faction, sbSection);
      }

      imagesSection.appendChild(sbSection);
      this.root.appendChild(imagesSection);

      // Section buttons
      const sectionsDiv = document.createElement('div');

      for (const sec of Rules.SECTIONS) {
        const btn = document.createElement('button');
        btn.className = 'section-button';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = sec.title;
        btn.appendChild(nameSpan);

        const labelSpan = document.createElement('span');
        labelSpan.className = 'section-label';
        labelSpan.textContent = Rules.isEmpty(sec.key, design) ? 'empty' : 'edited';
        btn.appendChild(labelSpan);

        btn.dataset.nav = '1';
        btn.onclick = () => {
          window.location.hash = `#/faction/${faction.id}/section/${sec.key}`;
        };

        sectionsDiv.appendChild(btn);
      }

      // Build button
      const buildBtn = document.createElement('button');
      buildBtn.className = 'section-button';
      const buildName = document.createElement('span');
      buildName.textContent = 'Build';
      buildBtn.appendChild(buildName);
      const buildLabel = document.createElement('span');
      buildLabel.className = 'section-label';
      buildLabel.innerHTML = this.getBuildStatusLabel(faction);
      buildBtn.appendChild(buildLabel);
      buildBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}/build`;
      };
      sectionsDiv.appendChild(buildBtn);

      // Simple Update button
      const updateBtn = document.createElement('button');
      updateBtn.className = 'section-button';
      updateBtn.disabled = faction.build.status !== 'built';
      const updateName = document.createElement('span');
      updateName.textContent = 'Simple Update';
      updateBtn.appendChild(updateName);
      updateBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}/simple-update`;
      };
      sectionsDiv.appendChild(updateBtn);

      // Bug Report button
      const bugBtn = document.createElement('button');
      bugBtn.className = 'section-button';
      bugBtn.disabled = faction.build.status !== 'built';
      const bugName = document.createElement('span');
      bugName.textContent = 'Bug Report';
      bugBtn.appendChild(bugName);
      bugBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}/bug-report`;
      };
      sectionsDiv.appendChild(bugBtn);

      // Versions button
      const versionsBtn = document.createElement('button');
      versionsBtn.className = 'section-button';
      const versionsName = document.createElement('span');
      versionsName.textContent = 'Versions';
      versionsBtn.appendChild(versionsName);
      versionsBtn.dataset.nav = '1';
      versionsBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}/versions`;
      };
      sectionsDiv.appendChild(versionsBtn);

      this.root.appendChild(sectionsDiv);
      // Read only: Build / Simple Update / Bug Report buttons are hidden with the other change buttons
      this.lockReadOnly(this.root);
    }

    // key = 'sbImages' (side A, or the only side) or 'sbImagesB' (side B of 2 sided spellbooks)
    renderSpellbookImages(faction, container, key = 'sbImages') {
      const design = faction.design;
      const sideB = key === 'sbImagesB';
      if (!design[key]) design[key] = {mode: null, all: null, each: [null, null, null, null, null, null]};
      const sbImages = design[key];
      const sideName = sideB ? ' (side B)' : (Rules.sbAnyTwo(design.sb) ? ' (side A)' : '');
      const sideData = sideB ? {side: 'B'} : (Rules.sbAnyTwo(design.sb) ? {side: 'A'} : {});

      if (!sbImages.mode) {
        const btn1 = document.createElement('button');
        btn1.textContent = 'Upload all 6 in 1 image';
        btn1.onclick = async () => {
          const imageId = await this.uploadImage('card');
          if (imageId) {
            this.scheduleSave(faction.id, key + '.mode', 'all');
            this.scheduleSave(faction.id, key + '.all', imageId);
            sbImages.mode = 'all';
            sbImages.all = imageId;
            this.renderMainDesign();
          }
        };
        container.appendChild(btn1);

        const btn2 = document.createElement('button');
        btn2.textContent = 'Upload 1 at a time';
        btn2.style.marginLeft = '10px';
        btn2.onclick = () => {
          this.scheduleSave(faction.id, key + '.mode', 'each');
          sbImages.mode = 'each';
          this.renderMainDesign();
        };
        container.appendChild(btn2);
      } else if (sbImages.mode === 'all') {
        if (sbImages.all) {
          const img = document.createElement('img');
          img.src = this.imgUrl(sbImages.all);
          img.className = 'image-thumbnail';
          img.onclick = () => {
            const fullImg = document.createElement('img');
            fullImg.src = this.imgUrl(sbImages.all);
            this.openOverlay(fullImg);
          };
          container.appendChild(img);

          const btnGroup = document.createElement('div');
          btnGroup.style.marginTop = '10px';

          const replaceBtn = document.createElement('button');
          replaceBtn.className = 'small';
          replaceBtn.textContent = 'Replace';
          replaceBtn.onclick = async () => {
            const imageId = await this.uploadImage('card');
            if (imageId) {
              this.scheduleSave(faction.id, key + '.all', imageId);
              sbImages.all = imageId;
              this.renderMainDesign();
            }
          };
          btnGroup.appendChild(replaceBtn);

          const extractBtn = document.createElement('button');
          extractBtn.className = 'small';
          extractBtn.textContent = 'Extract';
          extractBtn.style.marginLeft = '5px';
          extractBtn.onclick = async () => {
            await this.createRequest(
              faction.id,
              'extract',
              `Extract spellbook text${sideName} for ${faction.name}`,
              Object.assign({target: 'sbAll', image: sbImages.all}, sideData)
            );
            alert('Extract requested.');
          };
          btnGroup.appendChild(extractBtn);

          const deleteBtn = document.createElement('button');
          deleteBtn.className = 'small danger';
          deleteBtn.textContent = 'Delete';
          deleteBtn.style.marginLeft = '5px';
          deleteBtn.onclick = () => {
            this.scheduleSave(faction.id, key + '.mode', null);
            this.scheduleSave(faction.id, key + '.all', null);
            sbImages.mode = null;
            sbImages.all = null;
            this.renderMainDesign();
          };
          btnGroup.appendChild(deleteBtn);

          container.appendChild(btnGroup);
        }
      } else if (sbImages.mode === 'each') {
        const deleteAllBtn = document.createElement('button');
        deleteAllBtn.className = 'small danger';
        deleteAllBtn.textContent = 'Delete all 6, to replace with 1 image for all 6';
        deleteAllBtn.style.marginBottom = '15px';
        deleteAllBtn.onclick = () => {
          this.scheduleSave(faction.id, key + '.mode', null);
          for (let i = 0; i < 6; i++) {
            this.scheduleSave(faction.id, `${key}.each.${i}`, null);
          }
          sbImages.mode = null;
          sbImages.each = [null, null, null, null, null, null];
          this.renderMainDesign();
        };
        container.appendChild(deleteAllBtn);

        const grid = document.createElement('div');
        grid.className = 'image-grid';

        for (let i = 0; i < 6; i++) {
          const slot = document.createElement('div');
          slot.className = 'image-slot';

          const label = document.createElement('div');
          label.textContent = `Spellbook ${i + 1}${sideName}`;
          label.style.fontWeight = 'bold';
          label.style.marginBottom = '10px';
          slot.appendChild(label);

          if (sbImages.each[i]) {
            const img = document.createElement('img');
            img.src = this.imgUrl(sbImages.each[i]);
            slot.appendChild(img);

            const btnGroup = document.createElement('div');

            const replaceBtn = document.createElement('button');
            replaceBtn.className = 'small';
            replaceBtn.textContent = 'Replace';
            replaceBtn.onclick = async () => {
              const imageId = await this.uploadImage('card');
              if (imageId) {
                this.scheduleSave(faction.id, `${key}.each.${i}`, imageId);
                sbImages.each[i] = imageId;
                this.renderMainDesign();
              }
            };
            btnGroup.appendChild(replaceBtn);

            const extractBtn = document.createElement('button');
            extractBtn.className = 'small';
            extractBtn.textContent = 'Extract';
            extractBtn.style.marginLeft = '5px';
            extractBtn.onclick = async () => {
              await this.createRequest(
                faction.id,
                'extract',
                `Extract spellbook ${i + 1}${sideName} for ${faction.name}`,
                Object.assign({target: 'sbEach', index: i, image: sbImages.each[i]}, sideData)
              );
              alert('Extract requested.');
            };
            btnGroup.appendChild(extractBtn);

            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'small danger';
            deleteBtn.textContent = 'Delete';
            deleteBtn.style.marginLeft = '5px';
            deleteBtn.onclick = () => {
              this.scheduleSave(faction.id, `${key}.each.${i}`, null);
              sbImages.each[i] = null;
              this.renderMainDesign();
            };
            btnGroup.appendChild(deleteBtn);

            slot.appendChild(btnGroup);
          } else {
            const uploadBtn = document.createElement('button');
            uploadBtn.className = 'small';
            uploadBtn.textContent = 'Upload';
            uploadBtn.onclick = async () => {
              const imageId = await this.uploadImage('card');
              if (imageId) {
                this.scheduleSave(faction.id, `${key}.each.${i}`, imageId);
                sbImages.each[i] = imageId;
                this.renderMainDesign();
              }
            };
            slot.appendChild(uploadBtn);
          }

          grid.appendChild(slot);
        }

        container.appendChild(grid);

        // All six uploaded -> one request reads all of them (one run, cheaper than six).
        if (sbImages.each.every(Boolean)) {
          const allWrap = document.createElement('div');
          allWrap.className = 'sb-extract-all';
          allWrap.style.cssText = 'display: flex; flex-direction: column; align-items: center; margin-top: 15px;';
          const allBtn = document.createElement('button');
          allBtn.textContent = 'Extract all spellbooks text';
          const est = document.createElement('div');
          est.className = 'extract-estimate';
          est.style.cssText = 'font-size: 0.8em; opacity: 0.75; margin-top: 3px;';
          est.textContent = `about ${SB_ALL_EXTRACT_MINUTES} min`;
          allBtn.onclick = async () => {
            if (!Rules.isEmpty('sb', design)) {
              const ok = await this.confirm(`Extract will overwrite all 6 spellbooks${sideName}. Are you sure?`, 'Yes - Extract', 'Cancel');
              if (!ok) return;
            }
            allBtn.disabled = true;
            try {
              await this.createRequest(faction.id, 'extract', `Extract all spellbooks text${sideName} for ${faction.name}`,
                Object.assign({target: 'sbEachAll', each: sbImages.each.slice()}, sideData));
              alert(`Extract requested. All 6 spellbooks will be filled in for you in about ${SB_ALL_EXTRACT_MINUTES} minutes.`);
            } catch (err) {
              alert('Extract request failed: ' + err.message);
            }
            allBtn.disabled = false;
          };
          allWrap.appendChild(allBtn);
          allWrap.appendChild(est);
          container.appendChild(allWrap);
        }
      }
    }

    showCardFullscreen(faction) {
      const design = faction.design;
      const img = document.createElement('img');
      img.src = this.imgUrl(design.card.image);
      img.style.maxWidth = '100%';
      img.style.display = 'block';
      img.style.margin = '0 auto';

      const div = document.createElement('div');
      div.appendChild(img);

      const uploadBtn = document.createElement('button');
      uploadBtn.textContent = 'Upload new image';
      uploadBtn.style.display = 'block';
      uploadBtn.style.margin = '20px auto';
      uploadBtn.onclick = async () => {
        const imageId = await this.uploadImage('card');
        if (imageId) {
          this.scheduleSave(faction.id, 'card.image', imageId);
          design.card.image = imageId;
          this.closeOverlay();
          this.renderMainDesign();
        }
      };
      div.appendChild(uploadBtn);

      this.openOverlay(div);
    }

    getBuildStatusLabel(faction) {
      const build = faction.build;
      if (build.status === 'built') {
        return '<span class="status-built">Built</span>';
      }
      if (build.status === 'in_progress') {
        return '<span class="status-in-progress">Build in progress</span>';
      }
      if (build.status === 'requested') {
        return '<span class="status-requested">Build Requested</span>';
      }
      if (Rules.buildReady(faction.design)) {
        return '<span class="status-ready">Ready</span>';
      }
      return '<span class="status-not-ready">Not Ready</span>';
    }

    getBuildStatusLabelForUnit(unit) {
      const build = unit.build || {status: 'none'};
      if (build.status === 'built') {
        return '<span class="status-built">Built</span>';
      }
      if (build.status === 'in_progress') {
        return '<span class="status-in-progress">Build in progress</span>';
      }
      if (build.status === 'requested') {
        return '<span class="status-requested">Build Requested</span>';
      }
      // Check if unit is ready: needs name and type at minimum
      const row = (unit.design.units && unit.design.units.rows && unit.design.units.rows[0]) || {};
      if (row.name && row.type) {
        return '<span class="status-ready">Ready</span>';
      }
      return '<span class="status-not-ready">Not Ready</span>';
    }

    renderScreen(fid, screen) {
      if (!this.state.currentFaction || this.state.currentFaction.id !== fid) {
        this.loadFaction(fid).then(() => this.renderScreen(fid, screen));
        return;
      }

      if (this.isReadOnly() && !screen.startsWith('section/') && screen !== 'versions') {
        window.location.hash = `#/faction/${fid}`;
        return;
      }

      if (screen.startsWith('section/')) {
        const key = screen.split('/')[1];
        this.renderSectionScreen(key);
      } else if (screen === 'versions') {
        this.renderVersionsScreen();
        this.lockReadOnly(this.root);
      } else if (screen === 'build') {
        this.renderBuildScreen();
      } else if (screen === 'simple-update') {
        this.renderSimpleUpdateScreen();
      } else if (screen === 'bug-report') {
        this.renderBugReportScreen();
      }
      // Versions / Build / Simple Update / Bug Report also get Exit to Main at the bottom (doc: every section)
      if (!screen.startsWith('section/')) {
        const bottom = document.createElement('div');
        bottom.style.cssText = 'margin-top:24px;';
        const exit = document.createElement('button');
        exit.textContent = 'Exit to Main';
        exit.onclick = () => { window.location.hash = `#/faction/${fid}`; };
        bottom.appendChild(exit);
        // Placed after any content the screen adds asynchronously
        const hash = window.location.hash;
        setTimeout(() => { if (window.location.hash === hash) this.root.appendChild(bottom); }, 400);
      }
    }

    showCreateUnitDialog() {
      const overlay = document.createElement('div');
      overlay.className = 'confirm-overlay';

      const dialog = document.createElement('div');
      dialog.className = 'confirm-dialog';
      dialog.style.maxWidth = '600px';

      const title = document.createElement('h2');
      title.textContent = 'Create New Unit';
      title.style.marginBottom = '20px';
      dialog.appendChild(title);

      const nameGroup = document.createElement('div');
      nameGroup.className = 'form-group';
      const nameLabel = document.createElement('label');
      nameLabel.textContent = 'Unit Name';
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
      nameInput.maxLength = 60;
      nameInput.style.width = '100%';
      nameGroup.appendChild(nameLabel);
      nameGroup.appendChild(nameInput);
      dialog.appendChild(nameGroup);

      const buttons = document.createElement('div');
      buttons.className = 'buttons';

      const createBtn = document.createElement('button');
      createBtn.className = 'primary';
      createBtn.textContent = 'Create';
      createBtn.disabled = true;
      nameInput.addEventListener('input', () => { createBtn.disabled = !nameInput.value.trim(); });

      createBtn.onclick = async () => {
        try {
          createBtn.disabled = true;
          const unit = await this.api('POST', '/units', {name: nameInput.value.trim()});
          overlay.remove();
          window.location.hash = `#/unit/${unit.id}`;
        } catch (err) {
          createBtn.disabled = false;
          this.showError(dialog, err.message);
        }
      };

      const cancelBtn = document.createElement('button');
      cancelBtn.textContent = 'Cancel';
      cancelBtn.onclick = () => overlay.remove();

      buttons.appendChild(createBtn);
      buttons.appendChild(cancelBtn);
      dialog.appendChild(buttons);

      overlay.appendChild(dialog);
      document.body.appendChild(overlay);
      nameInput.focus();
    }

    // A neutral unit from My Units: the faction Units form, one unit only, nothing tied to a faction
    async renderUnitScreen(uid) {
      this.root.innerHTML = '<div class="spinner"></div>';
      // A neutral unit is always the user's own, so nothing from a faction opened before may make it read only
      this.state.currentFaction = null;
      let unit;
      try {
        unit = await this.api('GET', `/units/${uid}`);
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading unit: ${err.message}</p>`;
        return;
      }
      if (window.location.hash.replace(/\/$/, '') !== `#/unit/${uid}`) return;
      const design = unit.design;

      this.root.innerHTML = '';
      const title = document.createElement('h1');
      title.className = 'faction-title';
      title.textContent = design.units.rows[0].name || 'Unit';
      this.root.appendChild(title);

      const container = document.createElement('div');
      this.root.appendChild(container);

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Back to My Customs';
      backBtn.style.marginTop = '20px';
      backBtn.onclick = async () => {
        await this.flushSaves();
        window.location.hash = '#/factions';
      };
      this.root.appendChild(backBtn);

      // Build button
      const buildBtn = document.createElement('button');
      buildBtn.textContent = 'Build';
      buildBtn.style.marginTop = '10px';
      buildBtn.style.marginLeft = '10px';
      buildBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}/build`;
      };
      this.root.appendChild(buildBtn);

      const ctx = {
        design,
        neutral: true,
        reference: this.state.reference,
        set: (path, value) => {
          this.setDesignValue(design, path, value);
          this.scheduleSave(uid, path, value, 'unit');
          if (/\.name$/.test(path)) title.textContent = value || 'Unit';
          // Same redraw rule as faction sections: not while typing in a text or number box
          const ev = window.event;
          const t = ev && ev.target;
          const typing = ev && ev.type === 'input' && t &&
            (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && /^(text|number|search|email|url)$/.test(t.type)));
          if (!typing) ctx.rerender();
        },
        uploadImage: (kind) => this.uploadImage(kind),
        pickLibraryImage: () => this.pickLibraryImage(),
        imgUrl: (id) => this.imgUrl(id),
        confirm: (msg, yes, no) => this.confirm(msg, yes, no),
        rerender: () => {
          const y = window.scrollY;
          container.innerHTML = '';
          Sections.render('units', container, ctx);
          window.scrollTo(0, y);
        },
        openOverlay: (content) => this.openOverlay(content),
        closeOverlay: () => this.closeOverlay()
      };

      Sections.render('units', container, ctx);
    }

    renderSectionScreen(key) {
      const faction = this.state.currentFaction;
      const design = faction.design;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = async () => {
        await this.flushSaves();
        await this.closeSession(faction.id);
        window.location.hash = `#/faction/${faction.id}`;
      };
      backBtn.style.marginTop = '20px';

      if (this.isReadOnly()) this.root.appendChild(this.readOnlyBanner());
      const container = document.createElement('div');
      this.root.appendChild(container);
      // The doc puts Exit to Main at the bottom of every section
      this.root.appendChild(backBtn);

      const ctx = {
        design,
        faction,
        reference: this.state.reference,
        set: (path, value) => {
          if (this.isReadOnly()) return;
          this.setDesignValue(design, path, value);
          this.scheduleSave(faction.id, path, value);
          // Greyed-out fields are decided at render time, so checkboxes, selects and radios must
          // redraw the section. Typing in a text/number box must not (it would steal focus).
          // Judge by the event, not document.activeElement: Safari doesn't focus a clicked
          // checkbox, so focus stays in the last text box and the redraw was skipped.
          const ev = window.event;
          const t = ev && ev.target;
          const typing = ev && ev.type === 'input' && t &&
            (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && /^(text|number|search|email|url)$/.test(t.type)));
          if (!typing) ctx.rerender();
        },
        addRow: (tablePath, row) => {
          if (this.isReadOnly()) return;
          const parts = tablePath.split('.');
          let obj = design;
          for (let i = 0; i < parts.length; i++) {
            if (i === parts.length - 1) {
              obj[parts[i]].push(row);
            } else {
              obj = obj[parts[i]];
            }
          }
          this.patch(faction.id, [{op: 'addRow', path: tablePath, row}]);
          ctx.rerender();
        },
        deleteRow: (tablePath, rowId) => {
          if (this.isReadOnly()) return;
          const parts = tablePath.split('.');
          let obj = design;
          for (let i = 0; i < parts.length; i++) {
            if (i === parts.length - 1) {
              obj[parts[i]] = obj[parts[i]].filter(r => r.id !== rowId);
            } else {
              obj = obj[parts[i]];
            }
          }
          this.patch(faction.id, [{op: 'deleteRow', path: tablePath, id: rowId}]);
          ctx.rerender();
        },
        uploadImage: (kind) => this.uploadImage(kind),
        pickLibraryImage: () => this.pickLibraryImage(),
        imgUrl: (id) => this.imgUrl(id),
        confirm: (msg, yes, no) => this.confirm(msg, yes, no),
        createRequest: (type, text, data) => this.isReadOnly() ? Promise.resolve(null) : this.createRequest(faction.id, type, text, data),
        rerender: () => {
          const y = window.scrollY;
          container.innerHTML = '';
          Sections.render(key, container, ctx);
          this.lockReadOnly(container);
          window.scrollTo(0, y);
        },
        openOverlay: (content) => this.openOverlay(content),
        closeOverlay: () => this.closeOverlay()
      };

      Sections.render(key, container, ctx);
      this.lockReadOnly(container);
    }

    setDesignValue(design, path, value) {
      // Array rows are addressed by row id (SPEC §7), e.g. units.rows.<rowId>.name
      const step = (o, k) => Array.isArray(o) && !/^\d+$/.test(k) ? o.find(r => r && r.id === k) : o[k];
      const parts = path.split('.');
      let obj = design;
      for (let i = 0; i < parts.length - 1; i++) {
        obj = step(obj, parts[i]);
        if (obj == null) return;
      }
      obj[parts[parts.length - 1]] = value;
    }

    renderVersionsScreen() {
      const faction = this.state.currentFaction;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Versions';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const headerRow = document.createElement('tr');
      ['Version', 'Sections Changed', 'Changed from Version', 'Used in Live Game', 'Actions'].forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      const liveVersions = [faction.build.liveVersion, ...faction.liveGameVersions].filter(v => v !== null);

      for (const ver of faction.versions) {
        const row = document.createElement('tr');
        if (ver.n === faction.current) {
          row.style.background = '#3a3a3a';
        }

        const versionCell = document.createElement('td');
        versionCell.textContent = ver.n + (ver.n === faction.current ? ' (current)' : '');
        row.appendChild(versionCell);

        const sectionsCell = document.createElement('td');
        sectionsCell.textContent = ver.deleted ? 'DELETED' : ver.sections.join(', ') || 'Initial';
        row.appendChild(sectionsCell);

        const fromCell = document.createElement('td');
        fromCell.textContent = ver.from !== null ? ver.from : '-';
        row.appendChild(fromCell);

        const liveCell = document.createElement('td');
        liveCell.textContent = liveVersions.includes(ver.n) ? 'Y' : 'N';
        row.appendChild(liveCell);

        const actionsCell = document.createElement('td');
        if (!ver.deleted) {
          const rollbackBtn = document.createElement('button');
          rollbackBtn.className = 'small';
          rollbackBtn.textContent = 'Roll back';
          rollbackBtn.disabled = ver.n === faction.current;
          rollbackBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Roll back to version ${ver.n}? This will load that version's design.`,
              'Roll back',
              'Cancel'
            );
            if (confirmed) {
              try {
                const data = await this.api('POST', `/factions/${faction.id}/rollback`, {version: ver.n});
                this.state.currentFaction = data;
                this.renderVersionsScreen();
              } catch (err) {
                alert('Rollback failed: ' + err.message);
              }
            }
          };
          actionsCell.appendChild(rollbackBtn);

          const deleteBtn = document.createElement('button');
          deleteBtn.className = 'small danger';
          deleteBtn.textContent = 'Delete';
          deleteBtn.style.marginLeft = '5px';
          deleteBtn.disabled = liveVersions.includes(ver.n) || ver.n === faction.current || faction.versions.filter(v => !v.deleted).length === 1;
          deleteBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Delete version ${ver.n}? This cannot be undone.`,
              'Delete',
              'Cancel'
            );
            if (confirmed) {
              try {
                const data = await this.api('POST', `/factions/${faction.id}/delete-version`, {version: ver.n});
                this.state.currentFaction = data;
                this.renderVersionsScreen();
              } catch (err) {
                alert('Delete failed: ' + err.message);
              }
            }
          };
          actionsCell.appendChild(deleteBtn);
        }
        row.appendChild(actionsCell);

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      this.root.appendChild(table);
    }

    renderBuildScreen() {
      const faction = this.state.currentFaction;
      const design = faction.design;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Build';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const statusDiv = document.createElement('div');
      statusDiv.style.marginBottom = '20px';
      statusDiv.innerHTML = `<strong>Status:</strong> ${this.getBuildStatusLabel(faction)}`;
      this.root.appendChild(statusDiv);

      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const headerRow = document.createElement('tr');
      ['Section', 'Status'].forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');

      for (const key of Rules.BUILD_SECTIONS) {
        const row = document.createElement('tr');

        const sectionCell = document.createElement('td');
        const sec = Rules.SECTIONS.find(s => s.key === key);
        sectionCell.textContent = sec.title;
        row.appendChild(sectionCell);

        const statusCell = document.createElement('td');
        const st = Rules.status(key, design);
        statusCell.className = `status-${st.toLowerCase().replace('/', '')}`;
        statusCell.textContent = st;
        row.appendChild(statusCell);

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      this.root.appendChild(table);

      const versionInfo = document.createElement('div');
      versionInfo.style.marginTop = '20px';
      versionInfo.innerHTML = `
        <p><strong>Current Design Version:</strong> ${faction.current}</p>
        <p><strong>Current Live Built Version:</strong> ${faction.build.liveVersion !== null ? faction.build.liveVersion : 'N/A'}</p>
      `;
      this.root.appendChild(versionInfo);

      if (faction.build.status !== 'built') {
        const executeBtn = document.createElement('button');
        executeBtn.className = 'primary';
        executeBtn.textContent = 'Execute build';
        executeBtn.disabled = !Rules.buildReady(design) || faction.build.status === 'requested' || faction.build.status === 'in_progress';
        executeBtn.style.marginTop = '20px';
        executeBtn.onclick = async () => {
          try {
            await this.createRequest(
              faction.id,
              'build',
              `Design complete and ready to execute build for ${faction.name}`,
              {version: faction.current}
            );
            alert('Build requested. Check the admin console.');
            faction.build.status = 'requested';
            this.renderBuildScreen();
          } catch (err) {
            alert('Build request failed: ' + err.message);
          }
        };
        this.root.appendChild(executeBtn);
      } else {
        const updateBtn = document.createElement('button');
        updateBtn.className = 'primary';
        updateBtn.textContent = 'Update';
        updateBtn.disabled = faction.current === faction.build.liveVersion;
        updateBtn.style.marginTop = '20px';
        updateBtn.onclick = async () => {
          const sections = Rules.BUILD_SECTIONS.filter(key => {
            const diff = Rules.describeSectionDiff(key, this.state.builtDesign, design);
            return diff !== '';
          });

          if (sections.length === 0) {
            alert('No changes detected.');
            return;
          }

          try {
            for (const key of sections) {
              const sec = Rules.SECTIONS.find(s => s.key === key);
              const diff = Rules.describeSectionDiff(key, this.state.builtDesign, design);
              await this.createRequest(
                faction.id,
                'update',
                `${faction.name} update required. ${sec.title} needs to be changed. New version includes ${diff}.`,
                {section: key, fromVersion: faction.build.liveVersion, toVersion: faction.current}
              );
            }
            alert(`Update requests created for ${sections.length} section(s).`);
          } catch (err) {
            alert('Update request failed: ' + err.message);
          }
        };
        this.root.appendChild(updateBtn);
      }
    }

    async renderUnitBuildScreen(uid) {
      this.root.innerHTML = '<div class="spinner"></div>';
      let unit;
      try {
        unit = await this.api('GET', `/units/${uid}`);
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading unit: ${err.message}</p>`;
        return;
      }
      if (window.location.hash.replace(/\/$/, '') !== `#/unit/${uid}/build`) return;
      const design = unit.design;
      const row = (design.units && design.units.rows && design.units.rows[0]) || {};
      const build = unit.build || {status: 'none'};

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Back to Unit';
      backBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Build';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const statusDiv = document.createElement('div');
      statusDiv.style.marginBottom = '20px';
      statusDiv.innerHTML = `<strong>Status:</strong> ${this.getBuildStatusLabelForUnit(unit)}`;
      this.root.appendChild(statusDiv);

      const summaryDiv = document.createElement('div');
      summaryDiv.style.marginBottom = '20px';
      const readyFields = [];
      const missingFields = [];
      if (row.name) readyFields.push('Name'); else missingFields.push('Name');
      if (row.type) readyFields.push('Type'); else missingFields.push('Type');
      if (row.cost !== undefined && row.cost !== null) readyFields.push('Cost');
      if (row.combat) readyFields.push('Combat');
      summaryDiv.innerHTML = `
        <p><strong>Unit Name:</strong> ${row.name || 'Not set'}</p>
        <p><strong>Unit Type:</strong> ${row.type || 'Not set'}</p>
        <p><strong>Ready to build:</strong> ${missingFields.length === 0 ? 'Yes' : 'No (missing: ' + missingFields.join(', ') + ')'}</p>
      `;
      this.root.appendChild(summaryDiv);

      const isReady = row.name && row.type;

      if (build.status !== 'built') {
        const executeBtn = document.createElement('button');
        executeBtn.className = 'primary';
        executeBtn.textContent = 'Execute build';
        executeBtn.disabled = !isReady || build.status === 'requested' || build.status === 'in_progress';
        executeBtn.style.marginTop = '20px';
        executeBtn.onclick = async () => {
          try {
            await this.createRequest(
              uid,
              'build',
              `Design complete and ready to execute build for unit ${row.name}`,
              {},
              'unit'
            );
            alert('Build requested. Check the admin console.');
            unit.build = unit.build || {};
            unit.build.status = 'requested';
            this.renderUnitBuildScreen(uid);
          } catch (err) {
            alert('Build request failed: ' + err.message);
          }
        };
        this.root.appendChild(executeBtn);
      }

      const exitBtn = document.createElement('button');
      exitBtn.textContent = 'Back to Unit';
      exitBtn.style.marginTop = '20px';
      exitBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}`;
      };
      this.root.appendChild(exitBtn);
    }

    renderSimpleUpdateScreen() {
      const faction = this.state.currentFaction;
      const design = faction.design;
      const builtDesign = this.state.builtDesign;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Simple Update';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      // Pushes are applied by the server straight away (no ticker), so there is nothing pending to flash
      const note = document.createElement('p');
      note.textContent = 'Pushing a number updates the homebrew build straight away. Games already in progress keep the numbers they started with.';
      this.root.appendChild(note);

      if (!builtDesign) {
        const p = document.createElement('p');
        p.textContent = 'No built version available.';
        this.root.appendChild(p);
        return;
      }

      const builtNums = Rules.fixedNumbers(builtDesign);
      const designNums = Rules.fixedNumbers(design);

      // Find differences
      const diffs = [];
      for (const dNum of designNums) {
        const bNum = builtNums.find(b => b.section === dNum.section && b.rowId === dNum.rowId && b.field === dNum.field);
        if (!bNum || bNum.value !== dNum.value) {
          diffs.push({
            section: dNum.section,
            sectionTitle: dNum.sectionTitle,
            name: dNum.name,
            rowId: dNum.rowId,
            field: dNum.field,
            buildValue: bNum ? bNum.value : null,
            designValue: dNum.value
          });
        }
      }

      if (diffs.length === 0) {
        const p = document.createElement('p');
        p.textContent = 'No fixed number differences found.';
        this.root.appendChild(p);
        return;
      }

      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const headerRow = document.createElement('tr');
      ['Section', 'Name', 'Current value in build', 'Current value in design', 'Action'].forEach(h => {
        const th = document.createElement('th');
        th.textContent = h;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');

      for (const diff of diffs) {
        const row = document.createElement('tr');

        const sectionCell = document.createElement('td');
        sectionCell.textContent = diff.sectionTitle;
        row.appendChild(sectionCell);

        const nameCell = document.createElement('td');
        nameCell.textContent = diff.name;
        row.appendChild(nameCell);

        const buildCell = document.createElement('td');
        buildCell.textContent = diff.buildValue !== null ? diff.buildValue : '-';
        row.appendChild(buildCell);

        const designCell = document.createElement('td');
        designCell.textContent = diff.designValue !== null ? diff.designValue : '-';
        row.appendChild(designCell);

        const actionCell = document.createElement('td');
        const pushBtn = document.createElement('button');
        pushBtn.className = 'small primary';
        pushBtn.textContent = 'Push design to build';
        pushBtn.onclick = async () => {
          try {
            await this.createRequest(
              faction.id,
              'simple_update',
              `Faction ${faction.name} update, change ${diff.sectionTitle} ${diff.name} fixed value to ${diff.designValue}`,
              {
                section: diff.section,
                rowId: diff.rowId,
                field: diff.field,
                name: diff.name,
                buildValue: diff.buildValue,
                designValue: diff.designValue
              }
            );
            await this.loadFaction(faction.id);
            alert(`Updated in the build: ${diff.name} is now ${diff.designValue}.`);
            this.renderSimpleUpdateScreen();
          } catch (err) {
            alert('Request failed: ' + err.message);
          }
        };
        actionCell.appendChild(pushBtn);
        row.appendChild(actionCell);

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      this.root.appendChild(table);
    }

    renderBugReportScreen() {
      const faction = this.state.currentFaction;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/faction/${faction.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Bug Report';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const label = document.createElement('label');
      label.textContent = 'Describe the bug:';
      label.style.marginTop = '20px';
      this.root.appendChild(label);

      const textarea = document.createElement('textarea');
      textarea.style.width = '100%';
      textarea.style.minHeight = '200px';
      textarea.value = localStorage.getItem(`bug_draft_${faction.id}`) || '';
      textarea.addEventListener('input', () => {
        localStorage.setItem(`bug_draft_${faction.id}`, textarea.value);
      });
      this.root.appendChild(textarea);

      const sendBtn = document.createElement('button');
      sendBtn.className = 'primary';
      sendBtn.textContent = 'Send bug report';
      sendBtn.style.marginTop = '20px';
      sendBtn.onclick = async () => {
        const description = textarea.value.trim();
        if (!description) {
          alert('Please describe the bug.');
          return;
        }

        try {
          await this.createRequest(
            faction.id,
            'bug',
            `Bug report for ${faction.name} (built v${faction.build.liveVersion}): ${description}`,
            {description}
          );
          alert('Bug report sent.');
          localStorage.removeItem(`bug_draft_${faction.id}`);
          textarea.value = '';
        } catch (err) {
          alert('Failed to send bug report: ' + err.message);
        }
      };
      this.root.appendChild(sendBtn);
    }
  }

  // Wait for Rules and Sections to load before initializing
  function waitForDeps(callback) {
    if (window.Rules && window.Sections) {
      callback();
    } else {
      setTimeout(() => waitForDeps(callback), 50);
    }
  }

  function init() {
    const app = new App();
    window.app = app;
    app.start();
  }

  waitForDeps(init);

  // Flush saves on unload
  window.addEventListener('beforeunload', () => {
    if (window.app && window.app.saveQueue.size > 0) {
      navigator.sendBeacon('/designer/api/flush', JSON.stringify({
        token: window.app.state.token,
        saves: Array.from(window.app.saveQueue.values())
      }));
    }
  });
})();
