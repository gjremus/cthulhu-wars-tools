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
        adminToken: sessionStorage.getItem('cw_designer_admin_token'),
        factions: null,
        units: null,
        maps: null,
        currentFaction: null,
        currentMap: null,
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
        // Admin view shows one faction or map, read only
        if (path === 'faction' && rest[0]) {
          const screen = rest.slice(1).join('/');
          if (screen) this.renderScreen(rest[0], screen); else this.loadFaction(rest[0]);
        } else if (path === 'map' && rest[0]) {
          const mid = rest[0];
          const screen = rest.slice(1).join('/');
          if (!screen) {
            this.loadMap(mid);
          } else if (screen.startsWith('section/')) {
            const section = screen.split('/')[1];
            this.renderMapSectionScreen(mid, section);
          } else if (screen === 'build') {
            this.renderMapBuildScreen(mid);
          } else if (screen === 'versions') {
            this.renderMapVersionsScreen(mid);
          }
        } else {
          this.root.innerHTML = '<p style="padding:20px;">Admin view: close this tab to go back to the admin console.</p>';
        }
      } else if (path === 'admin' && rest[0] === 'users') {
        // Admin console - all users
        if (rest.length === 1) {
          this.renderAdminDashboard();
        } else if (rest.length === 2) {
          this.renderAdminUserDetail(rest[1]);
        }
      } else if (path === 'admin' && rest[0] === 'factions' && rest[1]) {
        // Admin console - read-only faction view
        this.state.adminToken = sessionStorage.getItem('cw_designer_admin_token');
        if (this.state.adminToken) {
          this.loadFaction(rest[1]);
        }
      } else if (path === 'admin' && rest[0] === 'maps' && rest[1]) {
        // Admin console - read-only map view
        this.state.adminToken = sessionStorage.getItem('cw_designer_admin_token');
        if (this.state.adminToken) {
          this.loadMap(rest[1]);
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
        } else if (screen === 'versions') {
          this.renderUnitVersionsScreen(uid);
        } else if (screen === 'bug-report') {
          this.renderUnitBugReportScreen(uid);
        } else if (screen === 'simple-update') {
          this.renderUnitSimpleUpdateScreen(uid);
        }
      } else if (path === 'map' && rest[0]) {
        const mid = rest[0];
        const screen = rest.slice(1).join('/');
        if (!screen) {
          this.loadMap(mid);
        } else if (screen.startsWith('section/')) {
          const section = screen.split('/')[1];
          this.renderMapSectionScreen(mid, section);
        } else if (screen === 'build') {
          this.renderMapBuildScreen(mid);
        } else if (screen === 'versions') {
          this.renderMapVersionsScreen(mid);
        } else if (screen === 'bug-report') {
          this.renderMapBugReportScreen(mid);
        } else if (screen === 'simple-update') {
          this.renderMapSimpleUpdateScreen(mid);
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
        : this.state.adminToken
        ? await this.api('GET', `/admin/${this.state.adminToken}/view-faction/${fid}`)
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

    // Maps
    async loadMapList() {
      const data = await this.api('GET', '/maps');
      this.state.maps = data.maps;
      return data.maps;
    }

    async createMap(name) {
      const data = await this.api('POST', '/maps', {name});
      return data;
    }

    async loadMap(mid) {
      const data = this.state.adminView
        ? await this.api('GET', `/admin/${this.state.adminView}/view-map/${mid}`)
        : this.state.adminToken
        ? await this.api('GET', `/admin/${this.state.adminToken}/view-map/${mid}`)
        : await this.api('GET', `/maps/${mid}`);
      // Defensive deep-merge: ensure all expected keys exist with default values
      if (data.design) {
        data.design = this.mergeMapDefaults(data.design);
      }
      this.state.currentMap = data;
      this.state.builtDesign = data.builtDesign;
      if (window.location.hash.replace(/\/$/, '') === `#/map/${mid}`) this.renderMapMainDesign();
    }

    mergeMapDefaults(design) {
      // Deep-merge design with defaults from Rules.newMapDesign() so missing keys never crash
      const defaults = Rules.newMapDesign();
      const merge = (target, source) => {
        if (!source || typeof source !== 'object' || Array.isArray(source)) return source;
        if (!target || typeof target !== 'object' || Array.isArray(target)) return source;
        const result = Object.assign({}, source);
        Object.keys(target).forEach(key => {
          if (key in source) {
            result[key] = merge(target[key], source[key]);
          } else {
            result[key] = target[key];
          }
        });
        return result;
      };
      return merge(defaults, design);
    }

    async patchMap(mid, ops) {
      if (this.isReadOnly()) return;
      const data = await this.api('POST', `/maps/${mid}/patch`, {ops});
      if (this.state.currentMap && this.state.currentMap.id === mid) {
        this.state.currentMap.current = data.current;
        this.state.currentMap.maxVersion = data.maxVersion;
        this.state.currentMap.versions = data.versions;
        this.state.currentMap.session = data.session;
        this.state.currentMap.updated = data.updated;
      }
    }

    async closeMapSession(mid) {
      if (this.isReadOnly()) return;
      await this.api('POST', `/maps/${mid}/close-session`);
    }

    async createMapRequest(mid, type, text, data) {
      const r = await this.api('POST', `/maps/${mid}/request`, {type, text, data});
      if (type === 'extract') this.refreshExtractStatus(mid);
      return r;
    }

    async getMapRequests(mid) {
      return await this.api('GET', `/maps/${mid}/requests`);
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
      const isAdmin = this.state.adminView;
      const bannerText = isAdmin
        ? 'Admin view (read-only): Viewing designer submission. All validation, feedback, and Claude questions visible. Form locked.'
        : 'Shared view (read-only): Form locked for editing.';

      const div = document.createElement('div');
      div.className = 'banner-readonly';
      div.style.cssText = 'border: 1px solid #000; background: #fde68a; color: #222; padding: 8px 12px; margin: 10px 0; border-radius: 4px;';
      div.textContent = bannerText;
      return div;
    }

    buildStatusBanner(entity, isAdminView = false) {
      if (!entity.build) return null;
      const status = entity.build.status || 'none';
      const colors = {
        'none': '#666',
        'requested': '#f59e0b',
        'in_progress': '#3b82f6',
        'built': '#10b981',
        'needs_answers': '#ef4444'
      };

      const div = document.createElement('div');
      div.className = 'admin-view-build-panel';
      div.style.cssText = `background: ${colors[status] || '#666'}; color: #fff; padding: 12px; margin-bottom: 20px; font-weight: bold; border-radius: 4px;`;

      let text = `Build Status: ${status.toUpperCase()}`;
      if (entity.build.requestedAt) {
        text += `<br>Requested: ${new Date(entity.build.requestedAt * 1000).toLocaleString()}`;
      }
      if (entity.build.liveVersion) {
        text += `<br>Live Version: ${entity.build.liveVersion}`;
      }
      if (entity.build.rid) {
        text += `<br>Request ID: ${entity.build.rid}`;
      }

      // Add admin-specific details for certain statuses
      if (isAdminView && status === 'needs_answers') {
        // Count pending Claude questions
        const pendingCount = this.getPendingClaudeQuestionsCount(entity);
        if (pendingCount > 0) {
          text += `<br><strong>Pending Claude Questions: ${pendingCount}</strong>`;
        }
      }

      div.innerHTML = text;
      return div;
    }

    // Helper to count pending Claude questions
    getPendingClaudeQuestionsCount(entity) {
      const claudeQA = entity.claudeQA || {};
      return Object.values(claudeQA).filter(sec => sec && sec.questions && sec.questions.trim()).length;
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

    // CW / Necro library picker (paginated)
    async pickLibraryImage() {
      if (this.isReadOnly()) return null;

      return new Promise(async (resolve) => {
        // Show layer immediately
        const layer = document.createElement('div');
        layer.className = 'library-picker';
        document.body.appendChild(layer);

        const loading = document.createElement('div');
        loading.className = 'library-loading';
        loading.textContent = 'Loading pictures…';
        layer.appendChild(loading);

        // Load library.json once and cache
        if (!this.libraryCache) {
          try {
            const resp = await fetch('/designer/library/library.json');
            if (!resp.ok) throw new Error('Failed to load library');
            this.libraryCache = await resp.json();
          } catch (err) {
            console.error('Library load error:', err);
            layer.innerHTML = '';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'library-error';
            errorDiv.textContent = 'Failed to load library: ' + err.message;
            layer.appendChild(errorDiv);
            const backBtn = document.createElement('button');
            backBtn.className = 'library-btn';
            backBtn.textContent = 'Back to unit';
            backBtn.onclick = () => {
              layer.remove();
              resolve(null);
            };
            layer.appendChild(backBtn);
            return;
          }
        }

        // Group by type and sort within each
        const typeOrder = ['Cultist', 'Monster', 'Terror', 'GOO', 'Elder God'];
        const sections = {};
        typeOrder.forEach(t => { sections[t] = []; });

        this.libraryCache.forEach(item => {
          if (sections[item.type]) sections[item.type].push(item);
        });

        Object.keys(sections).forEach(type => {
          sections[type].sort((a, b) => {
            if (a.name !== b.name) return a.name.localeCompare(b.name);
            return (a.faction || '').localeCompare(b.faction || '');
          });
        });

        let uploading = false;
        let currentPage = 0;
        let pages = [];
        let tileW = 88;
        let tileH = 115;
        let cols = 3;
        let rows = 2;
        let resizeTimer;

        const close = () => {
          window.removeEventListener('resize', onResize);
          window.removeEventListener('orientationchange', onResize);
          layer.remove();
        };

        layer.innerHTML = '';

        const topBar = document.createElement('div');
        topBar.className = 'library-topbar';
        layer.appendChild(topBar);

        const backBtn = document.createElement('button');
        backBtn.className = 'library-btn';
        backBtn.textContent = 'Back to unit';
        backBtn.onclick = () => {
          close();
          resolve(null);
        };
        topBar.appendChild(backBtn);

        const typeJumps = document.createElement('div');
        typeJumps.className = 'library-type-jumps';
        topBar.appendChild(typeJumps);

        const typeLabels = {
          'Cultist': 'Cultists',
          'Monster': 'Monsters',
          'Terror': 'Terrors',
          'GOO': 'GOOs / iGOOs',
          'Elder God': 'Elder Gods'
        };

        const nav = document.createElement('div');
        nav.className = 'library-nav';
        topBar.appendChild(nav);

        const prevBtn = document.createElement('button');
        prevBtn.className = 'library-btn';
        prevBtn.textContent = 'Prev';
        nav.appendChild(prevBtn);

        const pageLabel = document.createElement('span');
        pageLabel.className = 'library-page-label';
        nav.appendChild(pageLabel);

        const nextBtn = document.createElement('button');
        nextBtn.className = 'library-btn';
        nextBtn.textContent = 'Next';
        nav.appendChild(nextBtn);

        const grid = document.createElement('div');
        grid.className = 'library-grid';
        layer.appendChild(grid);

        const errorMsg = document.createElement('div');
        errorMsg.className = 'library-error-inline';
        layer.appendChild(errorMsg);

        // Build pages: paginate within each type
        const buildPages = (pageSize) => {
          const newPages = [];
          typeOrder.forEach(type => {
            const items = sections[type];
            if (items.length === 0) return;
            for (let i = 0; i < items.length; i += pageSize) {
              newPages.push({
                type,
                items: items.slice(i, Math.min(i + pageSize, items.length))
              });
            }
          });
          return newPages;
        };

        // Compute page size from viewport (measure top bar after DOM)
        const computePageSize = () => {
          const vw = window.innerWidth;
          const vh = window.innerHeight;

          if (vw < 600) {
            tileW = 88; tileH = 88 * 0.85 + 40;
          } else if (vw < 1100) {
            tileW = 120; tileH = 120 * 0.85 + 40;
          } else {
            tileW = 160; tileH = 160 * 0.85 + 40;
          }

          const gap = 12;
          const topBarH = topBar.offsetHeight || 60;
          // The grid fills the space under the top bar, so measure it once the top bar is complete
          const gridH = grid.clientHeight || (vh - topBarH - 40 - 20 - 24);
          cols = Math.max(2, Math.floor((vw - 40) / (tileW + gap)));
          rows = Math.max(1, Math.floor(gridH / (tileH + gap)));
          const pageSize = Math.max(6, cols * rows);

          const oldType = pages[currentPage]?.type;
          pages = buildPages(pageSize);

          // Keep same type visible after resize
          if (oldType) {
            const idx = pages.findIndex(p => p.type === oldType);
            if (idx >= 0) currentPage = idx;
          }
          currentPage = Math.max(0, Math.min(currentPage, pages.length - 1));
        };

        const onResize = () => {
          clearTimeout(resizeTimer);
          resizeTimer = setTimeout(() => {
            computePageSize();
            renderPage();
          }, 200);
        };

        window.addEventListener('resize', onResize);
        window.addEventListener('orientationchange', onResize);

        // Build type jump buttons
        typeOrder.forEach(type => {
          if (sections[type].length === 0) return;
          const btn = document.createElement('button');
          btn.className = 'library-type-btn';
          btn.textContent = typeLabels[type];
          btn.dataset.type = type;
          btn.onclick = () => {
            const idx = pages.findIndex(p => p.type === type);
            if (idx >= 0) {
              currentPage = idx;
              renderPage();
            }
          };
          typeJumps.appendChild(btn);
        });

        // Widest label first, so the top bar wraps as it will once a page is shown before the grid is measured
        pageLabel.textContent = 'GOOs / iGOOs · Page 00 of 00';
        computePageSize();

        prevBtn.onclick = () => {
          if (currentPage > 0) {
            currentPage--;
            renderPage();
          }
        };

        nextBtn.onclick = () => {
          if (currentPage < pages.length - 1) {
            currentPage++;
            renderPage();
          }
        };

        const renderPage = () => {
          if (pages.length === 0) return;

          const page = pages[currentPage];
          const pageType = page.type;

          // Update nav
          prevBtn.disabled = currentPage === 0;
          nextBtn.disabled = currentPage >= pages.length - 1;
          pageLabel.textContent = `${typeLabels[pageType]} · Page ${currentPage + 1} of ${pages.length}`;

          // Update type button highlight
          typeJumps.querySelectorAll('.library-type-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.type === pageType);
          });

          // Render tiles
          grid.innerHTML = '';
          grid.style.gridTemplateColumns = `repeat(${cols}, ${tileW}px)`;
          errorMsg.textContent = '';

          page.items.forEach(item => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'library-tile';
            btn.title = item.faction && item.faction !== 'Neutral' ? `${item.name} (${item.faction})` : item.name;
            btn.style.height = `${tileH}px`;

            const img = document.createElement('img');
            img.src = `/designer/library/${item.file}`;
            img.loading = 'lazy';
            img.alt = item.name;

            const nameDiv = document.createElement('div');
            nameDiv.className = 'library-tile-name';
            nameDiv.textContent = item.name;

            const factionDiv = document.createElement('div');
            factionDiv.className = 'library-tile-faction';
            if (item.faction && item.faction !== 'Neutral') {
              factionDiv.textContent = item.faction;
            }

            btn.appendChild(img);
            btn.appendChild(nameDiv);
            btn.appendChild(factionDiv);

            btn.onclick = async () => {
              if (uploading) return;
              uploading = true;

              try {
                this.showSaveIndicator('saving', 'Uploading image...');
                errorMsg.textContent = 'Uploading…';

                const resp = await fetch(`/designer/library/${item.file}`);
                if (!resp.ok) throw new Error('Failed to fetch image');
                const blob = await resp.blob();

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
                errorMsg.textContent = 'Upload failed: ' + err.message;
                uploading = false;
              }
            };

            grid.appendChild(btn);
          });
        };

        renderPage();
      });
    }

    // Autosave
    // kind: 'faction' | 'unit' | 'map'
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
          else if (kind === 'map') await this.patchMap(fid, ops);
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
      // Read only: the picture viewers keep only Done, so no button is shown that can't change anything
      if (this.isReadOnly()) {
        overlay.querySelectorAll('button').forEach(b => {
          if (b.textContent.trim() !== 'Done') b.style.display = 'none';
        });
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
        if (noLabel !== null) buttons.appendChild(noBtn);
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
        const [factions, units, maps] = await Promise.all([
          this.loadFactionList(),
          this.api('GET', '/units').then(d => d.units),
          this.loadMapList()
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
            status.innerHTML = `Status: ${this.buildStatusHtml(faction.buildStatus)}`;
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
        const shared = factions.filter(f => f.readOnly && !f.base);
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

        // Base factions (always shown last, read only for everyone)
        const baseFactions = factions.filter(f => f.base);
        if (baseFactions.length) {
          const h = document.createElement('h2');
          h.textContent = 'Base factions (read only)';
          h.style.marginTop = '30px';
          this.root.appendChild(h);
          const grid = document.createElement('div');
          grid.className = 'faction-grid';
          for (const faction of baseFactions) {
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
            const label = document.createElement('div');
            label.className = 'status';
            label.textContent = 'Base faction';
            card.appendChild(label);
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
            const status = document.createElement('div');
            status.className = 'status';
            status.innerHTML = `Status: ${this.buildStatusHtml(unit.buildStatus)}`;
            card.appendChild(status);
            const updated = document.createElement('div');
            updated.className = 'status';
            updated.textContent = `Updated: ${new Date(unit.updated * 1000).toLocaleDateString()}`;
            card.appendChild(updated);
            grid.appendChild(card);
          }
          this.root.appendChild(grid);
        }

        // My Maps
        const mapsTitle = document.createElement('h2');
        mapsTitle.textContent = 'My Maps';
        mapsTitle.style.margin = '30px 0 12px';
        this.root.appendChild(mapsTitle);

        const createMapBtn = document.createElement('button');
        createMapBtn.className = 'primary';
        createMapBtn.textContent = 'Create New Map';
        createMapBtn.style.marginBottom = '20px';
        createMapBtn.onclick = () => this.showCreateMapDialog();
        this.root.appendChild(createMapBtn);

        if (maps.filter(m => !m.readOnly).length === 0) {
          const p = document.createElement('p');
          p.textContent = 'No maps yet. Create one to get started.';
          p.style.color = '#888';
          this.root.appendChild(p);
        } else {
          const grid = document.createElement('div');
          grid.className = 'faction-grid';
          for (const map of maps.filter(m => !m.readOnly)) {
            const card = document.createElement('div');
            card.className = 'faction-card';
            card.onclick = () => { window.location.hash = `#/map/${map.id}`; };
            const name = document.createElement('h3');
            name.textContent = map.name;
            card.appendChild(name);
            const status = document.createElement('div');
            status.className = 'status';
            status.innerHTML = `Status: ${this.buildStatusHtml(map.buildStatus)}`;
            card.appendChild(status);
            const updated = document.createElement('div');
            updated.className = 'status';
            updated.textContent = `Updated: ${new Date(map.updated * 1000).toLocaleDateString()}`;
            card.appendChild(updated);
            grid.appendChild(card);
          }
          this.root.appendChild(grid);
        }

        // Shared maps (read only)
        const sharedMaps = maps.filter(m => m.readOnly);
        if (sharedMaps.length) {
          const h = document.createElement('h2');
          h.textContent = 'Shared with me (read only)';
          h.style.marginTop = '30px';
          this.root.appendChild(h);
          const grid = document.createElement('div');
          grid.className = 'faction-grid';
          for (const map of sharedMaps) {
            const card = document.createElement('div');
            card.className = 'faction-card';
            card.onclick = () => { window.location.hash = `#/map/${map.id}`; };
            const name = document.createElement('h3');
            name.textContent = map.name;
            card.appendChild(name);
            const by = document.createElement('div');
            by.className = 'status';
            by.textContent = `Designed by ${map.ownerName || map.owner}`;
            card.appendChild(by);
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

    showCreateMapDialog() {
      const overlay = document.createElement('div');
      overlay.className = 'confirm-overlay';

      const dialog = document.createElement('div');
      dialog.className = 'confirm-dialog';
      dialog.style.maxWidth = '600px';

      const title = document.createElement('h2');
      title.textContent = 'Create New Map';
      title.style.marginBottom = '20px';
      dialog.appendChild(title);

      const nameGroup = document.createElement('div');
      nameGroup.className = 'form-group';
      const nameLabel = document.createElement('label');
      nameLabel.textContent = 'Map Name (at least 3 characters)';
      const nameInput = document.createElement('input');
      nameInput.type = 'text';
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

      nameInput.addEventListener('input', () => {
        createBtn.disabled = nameInput.value.trim().length < 3;
      });

      createBtn.onclick = async () => {
        const name = nameInput.value.trim();
        try {
          createBtn.disabled = true;
          const map = await this.createMap(name);
          overlay.remove();
          window.location.hash = `#/map/${map.id}`;
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
      if (this.state.adminView && faction.build) {
        const banner = this.buildStatusBanner(faction, true);
        if (banner) this.root.appendChild(banner);
      }

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

        // Check if this section has Claude questions
        const claudeQA = faction.claudeQA || {};
        const hasQuestions = claudeQA[sec.key] && claudeQA[sec.key].questions && claudeQA[sec.key].questions.trim();

        if (hasQuestions) {
          labelSpan.textContent = 'Claude Question';
          labelSpan.style.color = '#fbbf24'; // Amber color for questions
        } else {
          labelSpan.textContent = Rules.isEmpty(sec.key, design) ? 'empty' : 'edited';
        }
        btn.appendChild(labelSpan);

        // Add status badge for admin view
        if (this.state.adminView) {
          const badgeSpan = document.createElement('span');
          badgeSpan.className = 'section-status-badge';
          badgeSpan.innerHTML = this.getSectionStatusBadge(sec.key, faction);
          btn.appendChild(badgeSpan);
        }

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

    // Build status words, shared by the faction and unit screens and the list cards
    buildStatusHtml(status, ready, hasQuestions, sectionsWithQuestions) {
      const sectionSuffix = sectionsWithQuestions && sectionsWithQuestions.length > 0
        ? ': ' + sectionsWithQuestions.join(', ')
        : '';

      if (status === 'built') {
        return hasQuestions
          ? `<span class="status-built">Built</span> <span class="status-requested">(Claude has questions for you${sectionSuffix})</span>`
          : '<span class="status-built">Built</span>';
      }
      if (status === 'requested') {
        return '<span class="status-requested">Submitted, waiting to be picked up</span>';
      }
      if (status === 'in_progress') {
        return '<span class="status-in-progress">Build in progress</span>';
      }
      if (status === 'needs_answers') {
        return `<span class="status-requested">Waiting for your answers to Claude's questions${sectionSuffix}</span>`;
      }
      if (ready === undefined) {
        return '<span>Not submitted</span>';
      }
      return ready ? '<span class="status-ready">Ready</span>' : '<span class="status-not-ready">Not Ready</span>';
    }

    hasClaudeQuestions(entity) {
      return Object.values(entity.claudeQA || {}).some(sec => sec && sec.questions);
    }

    // Get section names that have Claude questions, for display in build status
    getSectionsWithQuestions(entity, sectionsList) {
      const sections = [];
      const claudeQA = entity.claudeQA || {};

      for (const sec of sectionsList) {
        const key = sec.key;
        if (claudeQA[key] && claudeQA[key].questions && claudeQA[key].questions.trim()) {
          sections.push(sec.title);
        }
      }

      return sections;
    }

    // Get status badge HTML for a section in the main menu
    getSectionStatusBadge(key, faction) {
      const claudeQA = faction.claudeQA || {};
      const design = faction.design;

      // If section has Claude questions, show amber badge with count
      if (claudeQA[key] && claudeQA[key].questions && claudeQA[key].questions.trim()) {
        if (this.state.adminView) {
          return '<span class="status-badge-amber">⚠ Claude Q</span>';
        }
        return '<span class="status-amber">Claude Question</span>';
      }

      // Otherwise call Rules.status to determine completion
      if (!window.Rules || !window.Rules.status) {
        return '';
      }

      const statusResult = window.Rules.status(key, design);
      if (statusResult === 'Complete') {
        return '<span class="status-complete">✓</span>';
      } else if (statusResult === 'Incomplete') {
        if (this.state.adminView) {
          return '<span class="status-badge-red">✗ Incomplete</span>';
        }
        return '<span class="status-incomplete">Incomplete</span>';
      } else if (statusResult === 'N/A') {
        return '<span class="status-na">N/A</span>';
      }

      return '';
    }

    // Get status badge HTML for a map section in the main menu (admin view)
    getMapSectionStatusBadge(key, map) {
      const claudeQA = map.claudeQA || {};
      const design = map.design;

      // If section has Claude questions, show amber badge
      if (claudeQA[key] && claudeQA[key].questions && claudeQA[key].questions.trim()) {
        if (this.state.adminView) {
          return '<span class="status-badge-amber">⚠ Claude Q</span>';
        }
        return '<span class="status-amber">Claude Question</span>';
      }

      // For maps, use Rules.mapStatus if available
      if (!window.Rules || !window.Rules.mapStatus) {
        return '';
      }

      const statusResult = window.Rules.mapStatus(key, design);
      // mapStatus typically returns strings like status values, check if incomplete
      if (statusResult && statusResult.includes('Incomplete')) {
        if (this.state.adminView) {
          return '<span class="status-badge-red">✗ Incomplete</span>';
        }
      }

      return '';
    }

    getBuildStatusLabel(faction) {
      const sectionsWithQuestions = this.getSectionsWithQuestions(faction, Rules.SECTIONS);
      return this.buildStatusHtml(faction.build.status, Rules.buildReady(faction.design), this.hasClaudeQuestions(faction), sectionsWithQuestions);
    }

    getBuildStatusLabelForUnit(unit) {
      const build = unit.build || {status: 'none'};
      // Ready needs a name and type at minimum
      const row = (unit.design.units && unit.design.units.rows && unit.design.units.rows[0]) || {};
      // For units, section is always "unit"
      const sectionsWithQuestions = [];
      const claudeQA = unit.claudeQA || {};
      if (claudeQA.unit && claudeQA.unit.questions && claudeQA.unit.questions.trim()) {
        sectionsWithQuestions.push('Unit');
      }
      return this.buildStatusHtml(build.status, !!(row.name && row.type), this.hasClaudeQuestions(unit), sectionsWithQuestions);
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

      // Simple Update button
      const updateBtn = document.createElement('button');
      updateBtn.textContent = 'Simple Update';
      updateBtn.disabled = !(unit.build && unit.build.status === 'built');
      updateBtn.style.marginTop = '10px';
      updateBtn.style.marginLeft = '10px';
      updateBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}/simple-update`;
      };
      this.root.appendChild(updateBtn);

      // Bug Report button
      const bugBtn = document.createElement('button');
      bugBtn.textContent = 'Bug Report';
      bugBtn.disabled = !(unit.build && unit.build.status === 'built');
      bugBtn.style.marginTop = '10px';
      bugBtn.style.marginLeft = '10px';
      bugBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}/bug-report`;
      };
      this.root.appendChild(bugBtn);

      // Versions button
      const versionsBtn = document.createElement('button');
      versionsBtn.textContent = 'Versions';
      versionsBtn.style.marginTop = '10px';
      versionsBtn.style.marginLeft = '10px';
      versionsBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}/versions`;
      };
      this.root.appendChild(versionsBtn);

      const ctx = {
        design,
        unit,
        neutral: true,
        reference: this.state.reference,
        adminView: this.state.adminView ? true : false,
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
          else if (t.classList.contains('sx-missing')) t.classList.toggle('sx-missing', Rules.missingFields(path.split('.')[0], design).includes(path));
        },
        uploadImage: (kind) => this.uploadImage(kind),
        pickLibraryImage: () => this.pickLibraryImage(),
        imgUrl: (id) => this.imgUrl(id),
        confirm: (msg, yes, no) => this.confirm(msg, yes, no),
        readOnly: false,
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
        adminView: this.state.adminView ? true : false,  // Mark admin view for UI styling/messaging
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
          else if (t.classList.contains('sx-missing')) t.classList.toggle('sx-missing', Rules.missingFields(path.split('.')[0], design).includes(path));
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
        readOnly: this.isReadOnly(),
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

    describeMissingFields(key, sectionTitle, missing, design) {
      const parts = [];
      const d = design[key];

      // Helper to get user-friendly name for a row
      const getRowName = (tablePath, rowId) => {
        const table = tablePath.split('.').reduce((obj, prop) => obj && obj[prop], design);
        if (!table) return null;
        const row = table.find(r => r.id === rowId);
        if (!row) return null;
        return row.name || null;
      };

      // Group missing fields by row
      const byRow = {};
      missing.forEach(path => {
        const match = path.match(/^([^.]+)\.(rows|units)\.([^.]+)\.(.+)$/);
        if (match) {
          const [, section, table, rowId, field] = match;
          if (!byRow[rowId]) byRow[rowId] = {section, table, rowId, fields: []};
          byRow[rowId].fields.push(field);
        } else {
          // Section-level field
          if (!byRow['_root']) byRow['_root'] = {section: key, fields: []};
          byRow['_root'].fields.push(path.replace(key + '.', ''));
        }
      });

      // Generate descriptions
      Object.values(byRow).forEach(group => {
        if (group.section === '_root' || !group.rowId || group.rowId === '_root') {
          // Section-level fields
          const fieldLabels = {
            'name': 'Name',
            'acronym': 'Acronym',
            'phase': 'Phase',
            'type': 'Type',
            'text': 'Text',
            'location': 'Location type',
            'earthRegion': 'Earth Region',
            'libraryRegion': 'Library Region',
            'constraints.follows': 'Follows faction',
            'gate': 'Gate',
            'power': 'Starting power',
            'aeStart': 'Starting alternate economy'
          };
          group.fields.forEach(f => {
            const label = fieldLabels[f] || f;
            parts.push(`${label} is not set`);
          });
        } else {
          // Row-level fields
          const rows = design[group.section][group.table] || [];
          const name = getRowName(`${group.section}.${group.table}`, group.rowId);
          const fieldLabels = {
            'abilityName': 'Special Ability Name',
            'abilityText': 'Special Ability Text',
            'name': 'Name',
            'type': 'Type',
            'silhouette': 'Silhouette',
            'qty': 'Quantity',
            'costType': 'Cost Type',
            'cost': 'Cost',
            'costCalc': 'Cost calculation',
            'awakenReq': 'Requirements/process',
            'awakenPower': 'Power cost',
            'awakenRegion': 'Region placement',
            'combatType': 'Combat type',
            'dice': 'Dice',
            'diceCalc': 'Dice calculation',
            'pains': 'Pains',
            'kills': 'Kills',
            'resultsCalc': 'Results calculation',
            'text': 'Text',
            'typeB': 'Type (Side B)',
            'nameB': 'Name (Side B)',
            'textB': 'Text (Side B)',
            'image': 'Image',
            'restrictions': 'Unit Restrictions',
            'adjacency': 'Adjacency',
            'placement': 'Placement',
            'effects': 'Effects',
            'effect': 'Fixed Numeric Effect',
            'usage': 'Usage',
            'num': 'Fixed Numeric Cost or Effect',
            'sign': 'Sign',
            'kind': 'Fixed or Variable',
            'calc': 'Calculation',
            'desc': 'Description',
            'effectB': 'Fixed Numeric Effect (Side B)',
            'name2': 'Second power Name', 'type2': 'Second power Type', 'text2': 'Second power Text', 'effect2': 'Second power Effect',
            'nameB2': 'Side B second power Name', 'typeB2': 'Side B second power Type', 'textB2': 'Side B second power Text', 'effectB2': 'Side B second power Effect'
          };

          const missingLabels = group.fields.map(f => fieldLabels[f] || f);
          const rowLabel = name ? `"${name}"` : `row ${rows.findIndex(r => r.id === group.rowId) + 1}`;

          if (missingLabels.length === 1) {
            parts.push(`${rowLabel} needs ${missingLabels[0]}`);
          } else {
            parts.push(`${rowLabel} needs ${missingLabels.slice(0, -1).join(', ')} and ${missingLabels[missingLabels.length - 1]}`);
          }
        }
      });

      return parts.join('. ') + (parts.length > 0 ? '.' : '');
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

      // Stability field
      const stabilityDiv = document.createElement('div');
      stabilityDiv.style.marginBottom = '20px';
      stabilityDiv.innerHTML = '<strong>Stability:</strong> ';

      const stability = faction.stability || 'alpha';
      const stabilityLabels = {alpha: 'Untested / Alpha', beta: 'Tested / Beta', stable: 'Stable'};

      const isBase = faction.base || false;
      const isBuilt = faction.build && faction.build.status === 'built';
      const canEdit = !isBase && isBuilt;

      if (canEdit) {
        const stabilitySelect = document.createElement('select');
        stabilitySelect.style.padding = '4px';
        ['alpha', 'beta', 'stable'].forEach(val => {
          const option = document.createElement('option');
          option.value = val;
          option.textContent = stabilityLabels[val];
          if (val === stability) option.selected = true;
          stabilitySelect.appendChild(option);
        });
        stabilitySelect.onchange = async (e) => {
          try {
            await this.api('POST', `/factions/${faction.id}/stability`, {stability: e.target.value});
            faction.stability = e.target.value;
            alert(`Stability updated to ${stabilityLabels[e.target.value]}`);
          } catch (err) {
            alert('Failed to update stability: ' + err.message);
            stabilitySelect.value = stability; // Revert
          }
        };
        stabilityDiv.appendChild(stabilitySelect);
      } else {
        const stabilityText = document.createElement('span');
        stabilityText.textContent = stabilityLabels[stability];
        if (isBase) {
          stabilityText.textContent += ' (read-only)';
        } else if (!isBuilt) {
          stabilityText.textContent = '(set when built)';
          stabilityText.style.color = '#aaa';
        }
        stabilityDiv.appendChild(stabilityText);
      }
      this.root.appendChild(stabilityDiv);

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

      const incompleteSections = [];

      for (const key of Rules.BUILD_SECTIONS) {
        const row = document.createElement('tr');

        const sectionCell = document.createElement('td');
        const sec = Rules.SECTIONS.find(s => s.key === key);
        const st = Rules.status(key, design);

        if (st === 'Incomplete') {
          const link = document.createElement('a');
          link.href = `#/faction/${faction.id}/section/${key}`;
          link.textContent = sec.title;
          link.style.color = '#60a5fa';
          link.style.textDecoration = 'underline';
          sectionCell.appendChild(link);
          incompleteSections.push({key, title: sec.title});
        } else {
          sectionCell.textContent = sec.title;
        }
        row.appendChild(sectionCell);

        const statusCell = document.createElement('td');
        statusCell.className = `status-${st.toLowerCase().replace('/', '')}`;
        statusCell.textContent = st;
        row.appendChild(statusCell);

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      this.root.appendChild(table);

      // Add plain-language descriptions for incomplete sections
      if (incompleteSections.length > 0) {
        const missingDiv = document.createElement('div');
        missingDiv.style.cssText = 'margin-top: 20px; padding: 16px; background: #2a2a2a; border: 1px solid #666; border-radius: 4px;';
        const missingTitle = document.createElement('h3');
        missingTitle.textContent = 'Missing fields';
        missingTitle.style.marginTop = '0';
        missingDiv.appendChild(missingTitle);

        incompleteSections.forEach(sec => {
          const missing = Rules.missingFields(sec.key, design);
          if (missing.length === 0) return;

          const desc = this.describeMissingFields(sec.key, sec.title, missing, design);
          if (desc) {
            const p = document.createElement('p');
            const strong = document.createElement('strong');
            strong.textContent = `${sec.title}: `;
            p.appendChild(strong);
            p.appendChild(document.createTextNode(desc));
            p.style.margin = '8px 0';
            missingDiv.appendChild(p);
          }
        });

        this.root.appendChild(missingDiv);
      }

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

      if (this.isReadOnly()) this.root.appendChild(this.readOnlyBanner());
      this.lockReadOnly(this.root);
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
      if (Rules.unitHasAbility(row) && !row.abilityText) missingFields.push('Special Ability');
      if (row.cost !== undefined && row.cost !== null) readyFields.push('Cost');
      if (row.combat) readyFields.push('Combat');
      summaryDiv.innerHTML = `
        <p><strong>Unit Name:</strong> ${row.name || 'Not set'}</p>
        <p><strong>Unit Type:</strong> ${row.type || 'Not set'}</p>
        <p><strong>Ready to build:</strong> ${missingFields.length === 0 ? 'Yes' : 'No (missing: ' + missingFields.join(', ') + ')'}</p>
      `;
      this.root.appendChild(summaryDiv);

      const isReady = missingFields.length === 0;

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

    // Map render methods

    renderMapMainDesign() {
      const map = this.state.currentMap;
      const design = map.design;

      this.root.innerHTML = '';

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
      nameTitle.textContent = map.name;
      header.appendChild(nameTitle);

      this.root.appendChild(header);
      if (this.isReadOnly()) this.root.appendChild(this.readOnlyBanner());
      if (this.state.adminView && map.build) {
        const banner = this.buildStatusBanner(map, true);
        if (banner) this.root.appendChild(banner);
      }

      // Section buttons
      const sectionsDiv = document.createElement('div');

      for (const sec of Rules.MAP_SECTIONS) {
        const btn = document.createElement('button');
        btn.className = 'section-button';

        const nameSpan = document.createElement('span');
        nameSpan.textContent = sec.title;
        btn.appendChild(nameSpan);

        const labelSpan = document.createElement('span');
        labelSpan.className = 'section-label';

        // Check if this section has Claude questions
        const claudeQA = map.claudeQA || {};
        const hasQuestions = claudeQA[sec.key] && claudeQA[sec.key].questions && claudeQA[sec.key].questions.trim();

        if (hasQuestions) {
          labelSpan.textContent = 'Claude Question';
          labelSpan.style.color = '#fbbf24'; // Amber color for questions
        } else {
          const st = Rules.mapStatus(sec.key, design);
          labelSpan.textContent = st;
        }
        btn.appendChild(labelSpan);

        // Add status badge for admin view
        if (this.state.adminView) {
          const badgeSpan = document.createElement('span');
          badgeSpan.className = 'section-status-badge';
          badgeSpan.innerHTML = this.getMapSectionStatusBadge(sec.key, map);
          btn.appendChild(badgeSpan);
        }

        btn.dataset.nav = '1';
        btn.onclick = () => {
          window.location.hash = `#/map/${map.id}/section/${sec.key}`;
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
      buildLabel.innerHTML = this.getMapBuildStatusLabel(map);
      buildBtn.appendChild(buildLabel);
      buildBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}/build`;
      };
      sectionsDiv.appendChild(buildBtn);

      // Simple Update button
      const updateBtn = document.createElement('button');
      updateBtn.className = 'section-button';
      updateBtn.disabled = map.build.status !== 'built';
      const updateName = document.createElement('span');
      updateName.textContent = 'Simple Update';
      updateBtn.appendChild(updateName);
      updateBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}/simple-update`;
      };
      sectionsDiv.appendChild(updateBtn);

      // Bug Report button
      const bugBtn = document.createElement('button');
      bugBtn.className = 'section-button';
      bugBtn.disabled = map.build.status !== 'built';
      const bugName = document.createElement('span');
      bugName.textContent = 'Bug Report';
      bugBtn.appendChild(bugName);
      bugBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}/bug-report`;
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
        window.location.hash = `#/map/${map.id}/versions`;
      };
      sectionsDiv.appendChild(versionsBtn);

      this.root.appendChild(sectionsDiv);
      this.lockReadOnly(this.root);
    }

    getMapBuildStatusLabel(map) {
      const sectionsWithQuestions = this.getSectionsWithQuestions(map, Rules.MAP_SECTIONS);
      return this.buildStatusHtml(map.build.status, Rules.mapBuildReady(map.design), this.hasClaudeQuestions(map), sectionsWithQuestions);
    }

    async renderMapSectionScreen(mid, section) {
      if (!this.state.currentMap || this.state.currentMap.id !== mid) {
        await this.loadMap(mid);
        if (window.location.hash.replace(/\/$/, '') !== `#/map/${mid}/section/${section}`) return;
      }

      const map = this.state.currentMap;
      const design = map.design;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = async () => {
        await this.flushSaves();
        await this.closeMapSession(map.id);
        window.location.hash = `#/map/${map.id}`;
      };
      backBtn.style.marginTop = '20px';

      if (this.isReadOnly()) this.root.appendChild(this.readOnlyBanner());
      const container = document.createElement('div');
      this.root.appendChild(container);
      this.root.appendChild(backBtn);

      const ctx = {
        design,
        map,
        reference: this.state.reference,
        adminView: this.state.adminView ? true : false,
        set: (path, value) => {
          if (this.isReadOnly()) return;
          this.setDesignValue(design, path, value);
          this.scheduleSave(map.id, path, value, 'map');
          const ev = window.event;
          const t = ev && ev.target;
          const typing = ev && ev.type === 'input' && t &&
            (t.tagName === 'TEXTAREA' || (t.tagName === 'INPUT' && /^(text|number|search|email|url)$/.test(t.type)));
          if (!typing) ctx.rerender();
          else if (t.classList.contains('sx-missing')) t.classList.toggle('sx-missing', Rules.missingMapFields(path.split('.')[0], design).includes(path));
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
          this.patchMap(map.id, [{op: 'addRow', path: tablePath, row}]);
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
          this.patchMap(map.id, [{op: 'deleteRow', path: tablePath, id: rowId}]);
          ctx.rerender();
        },
        uploadImage: (kind) => this.uploadImage(kind),
        pickLibraryImage: () => this.pickLibraryImage(),
        imgUrl: (id) => this.imgUrl(id),
        confirm: (msg, yes, no) => this.confirm(msg, yes, no),
        readOnly: this.isReadOnly(),
        createRequest: (type, text, data) => this.isReadOnly() ? Promise.resolve(null) : this.createMapRequest(map.id, type, text, data),
        rerender: () => {
          const y = window.scrollY;
          container.innerHTML = '';
          Sections.render(section, container, ctx);
          this.lockReadOnly(container);
          window.scrollTo(0, y);
        },
        openOverlay: (content) => this.openOverlay(content),
        closeOverlay: () => this.closeOverlay()
      };

      Sections.render(section, container, ctx);
      this.lockReadOnly(container);
    }

    async renderMapBuildScreen(mid) {
      if (!this.state.currentMap || this.state.currentMap.id !== mid) {
        await this.loadMap(mid);
        if (window.location.hash.replace(/\/$/, '') !== `#/map/${mid}/build`) return;
      }

      const map = this.state.currentMap;
      const design = map.design;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Build';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const statusDiv = document.createElement('div');
      statusDiv.style.marginBottom = '20px';
      statusDiv.innerHTML = `<strong>Status:</strong> ${this.getMapBuildStatusLabel(map)}`;
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
      const incompleteSections = [];

      for (const key of Rules.MAP_BUILD_SECTIONS) {
        const row = document.createElement('tr');
        const sectionCell = document.createElement('td');
        const sec = Rules.MAP_SECTIONS.find(s => s.key === key);
        const st = Rules.mapStatus(key, design);

        if (st === 'Incomplete') {
          const link = document.createElement('a');
          link.href = `#/map/${map.id}/section/${key}`;
          link.textContent = sec.title;
          link.style.color = '#60a5fa';
          link.style.textDecoration = 'underline';
          sectionCell.appendChild(link);
          incompleteSections.push({key, title: sec.title});
        } else {
          sectionCell.textContent = sec.title;
        }
        row.appendChild(sectionCell);

        const statusCell = document.createElement('td');
        statusCell.className = `status-${st.toLowerCase().replace('/', '')}`;
        statusCell.textContent = st;
        row.appendChild(statusCell);

        tbody.appendChild(row);
      }

      table.appendChild(tbody);
      this.root.appendChild(table);

      if (incompleteSections.length > 0) {
        const missingDiv = document.createElement('div');
        missingDiv.style.cssText = 'margin-top: 20px; padding: 16px; background: #2a2a2a; border: 1px solid #666; border-radius: 4px;';
        const missingTitle = document.createElement('h3');
        missingTitle.textContent = 'Missing fields';
        missingTitle.style.marginTop = '0';
        missingDiv.appendChild(missingTitle);

        incompleteSections.forEach(sec => {
          const missing = Rules.missingMapFields(sec.key, design);
          if (missing.length === 0) return;
          const p = document.createElement('p');
          const strong = document.createElement('strong');
          strong.textContent = `${sec.title}: `;
          p.appendChild(strong);
          p.appendChild(document.createTextNode(missing.join(', ')));
          p.style.margin = '8px 0';
          missingDiv.appendChild(p);
        });

        this.root.appendChild(missingDiv);
      }

      const versionInfo = document.createElement('div');
      versionInfo.style.marginTop = '20px';
      versionInfo.innerHTML = `
        <p><strong>Current Design Version:</strong> ${map.current}</p>
        <p><strong>Current Live Built Version:</strong> ${map.build.liveVersion !== null ? map.build.liveVersion : 'N/A'}</p>
      `;
      this.root.appendChild(versionInfo);

      if (map.build.status !== 'built') {
        const executeBtn = document.createElement('button');
        executeBtn.className = 'primary';
        executeBtn.textContent = 'Execute build';
        executeBtn.disabled = !Rules.mapBuildReady(design) || map.build.status === 'requested' || map.build.status === 'in_progress';
        executeBtn.style.marginTop = '20px';
        executeBtn.onclick = async () => {
          try {
            await this.createMapRequest(
              map.id,
              'build',
              `Design complete and ready to execute build for ${map.name}`,
              {version: map.current}
            );
            alert('Build requested. Check the admin console.');
            map.build.status = 'requested';
            this.renderMapBuildScreen(mid);
          } catch (err) {
            alert('Build request failed: ' + err.message);
          }
        };
        this.root.appendChild(executeBtn);
      }
    }

    async renderMapVersionsScreen(mid) {
      if (!this.state.currentMap || this.state.currentMap.id !== mid) {
        await this.loadMap(mid);
        if (window.location.hash.replace(/\/$/, '') !== `#/map/${mid}/versions`) return;
      }

      const map = this.state.currentMap;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}`;
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
      const liveVersions = [map.build.liveVersion, ...map.liveGameVersions].filter(v => v !== null);

      for (const ver of map.versions) {
        const row = document.createElement('tr');
        if (ver.n === map.current) {
          row.style.background = '#3a3a3a';
        }

        const versionCell = document.createElement('td');
        versionCell.textContent = ver.n + (ver.n === map.current ? ' (current)' : '');
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
          rollbackBtn.disabled = ver.n === map.current;
          rollbackBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Roll back to version ${ver.n}? This will load that version's design.`,
              'Roll back',
              'Cancel'
            );
            if (confirmed) {
              try {
                const data = await this.api('POST', `/maps/${map.id}/rollback`, {version: ver.n});
                this.state.currentMap = data;
                this.renderMapVersionsScreen(mid);
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
          deleteBtn.disabled = liveVersions.includes(ver.n) || ver.n === map.current || map.versions.filter(v => !v.deleted).length === 1;
          deleteBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Delete version ${ver.n}? This cannot be undone.`,
              'Delete',
              'Cancel'
            );
            if (confirmed) {
              try {
                const data = await this.api('POST', `/maps/${map.id}/delete-version`, {version: ver.n});
                this.state.currentMap = data;
                this.renderMapVersionsScreen(mid);
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

    async renderMapBugReportScreen(mid) {
      if (!this.state.currentMap || this.state.currentMap.id !== mid) {
        await this.loadMap(mid);
        if (window.location.hash.replace(/\/$/, '') !== `#/map/${mid}/bug-report`) return;
      }

      const map = this.state.currentMap;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}`;
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
      textarea.value = localStorage.getItem(`bug_draft_map_${map.id}`) || '';
      textarea.addEventListener('input', () => {
        localStorage.setItem(`bug_draft_map_${map.id}`, textarea.value);
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
          await this.createMapRequest(
            map.id,
            'bug',
            `Bug report for ${map.name} (built v${map.build.liveVersion}): ${description}`,
            {description}
          );
          alert('Bug report sent.');
          localStorage.removeItem(`bug_draft_map_${map.id}`);
          textarea.value = '';
        } catch (err) {
          alert('Failed to send bug report: ' + err.message);
        }
      };
      this.root.appendChild(sendBtn);
    }

    async renderMapSimpleUpdateScreen(mid) {
      if (!this.state.currentMap || this.state.currentMap.id !== mid) {
        await this.loadMap(mid);
        if (window.location.hash.replace(/\/$/, '') !== `#/map/${mid}/simple-update`) return;
      }

      const map = this.state.currentMap;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Exit to Main';
      backBtn.onclick = () => {
        window.location.hash = `#/map/${map.id}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Simple Update';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const note = document.createElement('p');
      note.textContent = 'For maps, describe what needs to be changed:';
      this.root.appendChild(note);

      const textarea = document.createElement('textarea');
      textarea.style.width = '100%';
      textarea.style.minHeight = '200px';
      textarea.value = localStorage.getItem(`update_draft_map_${map.id}`) || '';
      textarea.addEventListener('input', () => {
        localStorage.setItem(`update_draft_map_${map.id}`, textarea.value);
      });
      this.root.appendChild(textarea);

      const sendBtn = document.createElement('button');
      sendBtn.className = 'primary';
      sendBtn.textContent = 'Submit update request';
      sendBtn.style.marginTop = '20px';
      sendBtn.onclick = async () => {
        const description = textarea.value.trim();
        if (!description) {
          alert('Please describe what needs to be changed.');
          return;
        }

        try {
          await this.createMapRequest(
            map.id,
            'update',
            `Map ${map.name} update: ${description}`,
            {description}
          );
          alert('Update request sent.');
          localStorage.removeItem(`update_draft_map_${map.id}`);
          textarea.value = '';
        } catch (err) {
          alert('Failed to send update request: ' + err.message);
        }
      };
      this.root.appendChild(sendBtn);
    }

    // Unit meta sections
    async renderUnitVersionsScreen(uid) {
      this.root.innerHTML = '<div class="spinner"></div>';
      let unit;
      try {
        unit = await this.api('GET', `/units/${uid}`);
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading unit: ${err.message}</p>`;
        return;
      }
      if (window.location.hash.replace(/\/$/, '') !== `#/unit/${uid}/versions`) return;

      // Lazy migration: units without versions get version 1 created from current design
      if (!unit.versions) {
        unit.versions = [{n: 1, from: null, sections: [], created: unit.created, deleted: false}];
        unit.current = 1;
        unit.maxVersion = 1;
        await this.api('POST', `/units/${uid}/patch`, {ops: [{op: 'set', path: 'versions', value: unit.versions}]});
      }

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Back to Unit';
      backBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}`;
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
      const liveVersions = [unit.build && unit.build.liveVersion, ...(unit.liveGameVersions || [])].filter(v => v !== null);

      for (const ver of unit.versions) {
        const row = document.createElement('tr');
        if (ver.n === unit.current) {
          row.style.background = '#3a3a3a';
        }

        const versionCell = document.createElement('td');
        versionCell.textContent = ver.n + (ver.n === unit.current ? ' (current)' : '');
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
          rollbackBtn.disabled = ver.n === unit.current;
          rollbackBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Roll back to version ${ver.n}? This will load that version's design.`,
              'Roll back',
              'Cancel'
            );
            if (confirmed) {
              try {
                unit = await this.api('POST', `/units/${uid}/rollback`, {version: ver.n});
                this.renderUnitVersionsScreen(uid);
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
          deleteBtn.disabled = liveVersions.includes(ver.n) || ver.n === unit.current || unit.versions.filter(v => !v.deleted).length === 1;
          deleteBtn.onclick = async () => {
            const confirmed = await this.confirm(
              `Delete version ${ver.n}? This cannot be undone.`,
              'Delete',
              'Cancel'
            );
            if (confirmed) {
              try {
                unit = await this.api('POST', `/units/${uid}/delete-version`, {version: ver.n});
                this.renderUnitVersionsScreen(uid);
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

    async renderUnitBugReportScreen(uid) {
      this.root.innerHTML = '<div class="spinner"></div>';
      let unit;
      try {
        unit = await this.api('GET', `/units/${uid}`);
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading unit: ${err.message}</p>`;
        return;
      }
      if (window.location.hash.replace(/\/$/, '') !== `#/unit/${uid}/bug-report`) return;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Back to Unit';
      backBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}`;
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
      textarea.value = localStorage.getItem(`bug_draft_unit_${uid}`) || '';
      textarea.addEventListener('input', () => {
        localStorage.setItem(`bug_draft_unit_${uid}`, textarea.value);
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
            uid,
            'bug',
            `Bug report for unit ${unit.design.units.rows[0].name}: ${description}`,
            {description},
            'unit'
          );
          alert('Bug report sent.');
          localStorage.removeItem(`bug_draft_unit_${uid}`);
          textarea.value = '';
        } catch (err) {
          alert('Failed to send bug report: ' + err.message);
        }
      };
      this.root.appendChild(sendBtn);
    }

    async renderUnitSimpleUpdateScreen(uid) {
      this.root.innerHTML = '<div class="spinner"></div>';
      let unit;
      try {
        unit = await this.api('GET', `/units/${uid}`);
      } catch (err) {
        this.root.innerHTML = `<p style="color: #f87171;">Error loading unit: ${err.message}</p>`;
        return;
      }
      if (window.location.hash.replace(/\/$/, '') !== `#/unit/${uid}/simple-update`) return;

      this.root.innerHTML = '';

      const backBtn = document.createElement('button');
      backBtn.textContent = 'Back to Unit';
      backBtn.onclick = () => {
        window.location.hash = `#/unit/${uid}`;
      };
      this.root.appendChild(backBtn);

      const title = document.createElement('h2');
      title.textContent = 'Simple Update';
      title.style.marginTop = '20px';
      this.root.appendChild(title);

      const note = document.createElement('p');
      note.textContent = 'For units, describe what needs to be changed:';
      this.root.appendChild(note);

      const textarea = document.createElement('textarea');
      textarea.style.width = '100%';
      textarea.style.minHeight = '200px';
      textarea.value = localStorage.getItem(`update_draft_unit_${uid}`) || '';
      textarea.addEventListener('input', () => {
        localStorage.setItem(`update_draft_unit_${uid}`, textarea.value);
      });
      this.root.appendChild(textarea);

      const sendBtn = document.createElement('button');
      sendBtn.className = 'primary';
      sendBtn.textContent = 'Submit update request';
      sendBtn.style.marginTop = '20px';
      sendBtn.onclick = async () => {
        const description = textarea.value.trim();
        if (!description) {
          alert('Please describe what needs to be changed.');
          return;
        }

        try {
          await this.createRequest(
            uid,
            'update',
            `Unit ${unit.design.units.rows[0].name} update: ${description}`,
            {description},
            'unit'
          );
          alert('Update request sent.');
          localStorage.removeItem(`update_draft_unit_${uid}`);
          textarea.value = '';
        } catch (err) {
          alert('Failed to send update request: ' + err.message);
        }
      };
      this.root.appendChild(sendBtn);
    }

    // Admin Console - Dashboard
    async renderAdminDashboard() {
      this.root.innerHTML = '<div class="spinner"></div>';

      try {
        const adminToken = sessionStorage.getItem('cw_designer_admin_token');
        if (!adminToken) {
          this.root.innerHTML = '<p style="padding:20px; color: red;">No admin token found. Please access via the admin link.</p>';
          return;
        }

        const response = await this.api('GET', `/admin/${adminToken}/users`);
        const users = response.users || [];

        this.root.innerHTML = '';

        const header = document.createElement('div');
        header.style.display = 'flex';
        header.style.justifyContent = 'space-between';
        header.style.alignItems = 'center';
        header.style.marginBottom = '20px';

        const title = document.createElement('h1');
        title.textContent = 'Admin Console — All Users';
        header.appendChild(title);

        const exitBtn = document.createElement('button');
        exitBtn.textContent = 'Exit Admin View';
        exitBtn.onclick = () => {
          sessionStorage.removeItem('cw_designer_admin_token');
          window.location.hash = '#/';
        };
        header.appendChild(exitBtn);

        this.root.appendChild(header);

        if (users.length === 0) {
          const p = document.createElement('p');
          p.textContent = 'No users found.';
          p.style.color = '#888';
          this.root.appendChild(p);
        } else {
          const table = document.createElement('table');
          table.style.borderCollapse = 'collapse';
          table.style.width = '100%';
          table.style.marginTop = '20px';

          // Header row
          const headerRow = document.createElement('tr');
          headerRow.style.border = '1px solid #000';
          ['Username', 'Factions', 'Maps', 'Units', 'Last Login', 'Created'].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            th.style.border = '1px solid #000';
            th.style.padding = '8px';
            th.style.textAlign = 'left';
            th.style.backgroundColor = '#f0f0f0';
            headerRow.appendChild(th);
          });
          table.appendChild(headerRow);

          // Data rows
          users.forEach(user => {
            const row = document.createElement('tr');
            row.style.border = '1px solid #000';

            // Username (link to user detail)
            const usernameCell = document.createElement('td');
            usernameCell.style.border = '1px solid #000';
            usernameCell.style.padding = '8px';
            const usernameLink = document.createElement('a');
            usernameLink.href = `#/admin/users/${user.username}`;
            usernameLink.textContent = user.username;
            usernameLink.style.color = '#0066cc';
            usernameLink.style.textDecoration = 'underline';
            usernameCell.appendChild(usernameLink);
            row.appendChild(usernameCell);

            // Factions
            const factionsCell = document.createElement('td');
            factionsCell.style.border = '1px solid #000';
            factionsCell.style.padding = '8px';
            if (user.factions && user.factions.length > 0) {
              user.factions.forEach((faction, idx) => {
                if (idx > 0) factionsCell.appendChild(document.createElement('br'));
                const link = document.createElement('a');
                link.href = `#/admin/factions/${faction.id}`;
                link.textContent = faction.name;
                link.style.color = '#0066cc';
                link.style.textDecoration = 'underline';
                factionsCell.appendChild(link);
              });
            } else {
              factionsCell.textContent = '—';
            }
            row.appendChild(factionsCell);

            // Maps
            const mapsCell = document.createElement('td');
            mapsCell.style.border = '1px solid #000';
            mapsCell.style.padding = '8px';
            if (user.maps && user.maps.length > 0) {
              user.maps.forEach((map, idx) => {
                if (idx > 0) mapsCell.appendChild(document.createElement('br'));
                const link = document.createElement('a');
                link.href = `#/admin/maps/${map.id}`;
                link.textContent = map.name;
                link.style.color = '#0066cc';
                link.style.textDecoration = 'underline';
                mapsCell.appendChild(link);
              });
            } else {
              mapsCell.textContent = '—';
            }
            row.appendChild(mapsCell);

            // Units
            const unitsCell = document.createElement('td');
            unitsCell.style.border = '1px solid #000';
            unitsCell.style.padding = '8px';
            if (user.units && user.units.length > 0) {
              unitsCell.textContent = `${user.units.length} unit${user.units.length !== 1 ? 's' : ''}`;
            } else {
              unitsCell.textContent = '—';
            }
            row.appendChild(unitsCell);

            // Last Login
            const lastLoginCell = document.createElement('td');
            lastLoginCell.style.border = '1px solid #000';
            lastLoginCell.style.padding = '8px';
            lastLoginCell.textContent = user.lastLogin ? new Date(user.lastLogin * 1000).toLocaleDateString() : '—';
            row.appendChild(lastLoginCell);

            // Created
            const createdCell = document.createElement('td');
            createdCell.style.border = '1px solid #000';
            createdCell.style.padding = '8px';
            createdCell.textContent = user.created ? new Date(user.created * 1000).toLocaleDateString() : '—';
            row.appendChild(createdCell);

            row.style.backgroundColor = row.children.length % 2 === 0 ? '#f9f9f9' : '#fff';
            table.appendChild(row);
          });

          this.root.appendChild(table);
        }
      } catch (err) {
        this.root.innerHTML = `<p style="padding:20px; color: red;">Failed to load admin dashboard: ${err.message}</p>`;
      }
    }

    // Admin Console - User Detail
    async renderAdminUserDetail(username) {
      this.root.innerHTML = '<div class="spinner"></div>';

      try {
        const adminToken = sessionStorage.getItem('cw_designer_admin_token');
        if (!adminToken) {
          this.root.innerHTML = '<p style="padding:20px; color: red;">No admin token found.</p>';
          return;
        }

        const response = await this.api('GET', `/admin/${adminToken}/users`);
        const users = response.users || [];
        const user = users.find(u => u.username === username);

        if (!user) {
          this.root.innerHTML = '<p style="padding:20px; color: red;">User not found.</p>';
          return;
        }

        this.root.innerHTML = '';

        const backBtn = document.createElement('button');
        backBtn.textContent = 'Back to Admin Dashboard';
        backBtn.onclick = () => {
          window.location.hash = '#/admin/users';
        };
        this.root.appendChild(backBtn);

        const title = document.createElement('h1');
        title.textContent = `Admin Console — ${username}`;
        title.style.marginTop = '20px';
        this.root.appendChild(title);

        // Factions table
        if (user.factions && user.factions.length > 0) {
          const h2 = document.createElement('h2');
          h2.textContent = 'Factions';
          h2.style.marginTop = '30px';
          h2.style.marginBottom = '12px';
          this.root.appendChild(h2);

          const table = document.createElement('table');
          table.style.borderCollapse = 'collapse';
          table.style.width = '100%';
          table.style.border = '1px solid #000';

          const headerRow = document.createElement('tr');
          headerRow.style.backgroundColor = '#f0f0f0';
          ['Name', 'Version', 'Build Status', 'Updated'].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            th.style.border = '1px solid #000';
            th.style.padding = '8px';
            th.style.textAlign = 'left';
            headerRow.appendChild(th);
          });
          table.appendChild(headerRow);

          user.factions.forEach((faction, idx) => {
            const row = document.createElement('tr');
            row.style.backgroundColor = idx % 2 === 0 ? '#f9f9f9' : '#fff';
            row.style.border = '1px solid #000';

            const nameCell = document.createElement('td');
            nameCell.style.border = '1px solid #000';
            nameCell.style.padding = '8px';
            const nameLink = document.createElement('a');
            nameLink.href = `#/admin/factions/${faction.id}`;
            nameLink.textContent = faction.name;
            nameLink.style.color = '#0066cc';
            nameLink.style.textDecoration = 'underline';
            nameCell.appendChild(nameLink);
            row.appendChild(nameCell);

            const versionCell = document.createElement('td');
            versionCell.style.border = '1px solid #000';
            versionCell.style.padding = '8px';
            versionCell.textContent = faction.version || '—';
            row.appendChild(versionCell);

            const buildCell = document.createElement('td');
            buildCell.style.border = '1px solid #000';
            buildCell.style.padding = '8px';
            buildCell.innerHTML = this.buildStatusHtml(faction.buildStatus);
            row.appendChild(buildCell);

            const updatedCell = document.createElement('td');
            updatedCell.style.border = '1px solid #000';
            updatedCell.style.padding = '8px';
            updatedCell.textContent = faction.updated ? new Date(faction.updated * 1000).toLocaleDateString() : '—';
            row.appendChild(updatedCell);

            table.appendChild(row);
          });

          this.root.appendChild(table);
        }

        // Maps table
        if (user.maps && user.maps.length > 0) {
          const h2 = document.createElement('h2');
          h2.textContent = 'Maps';
          h2.style.marginTop = '30px';
          h2.style.marginBottom = '12px';
          this.root.appendChild(h2);

          const table = document.createElement('table');
          table.style.borderCollapse = 'collapse';
          table.style.width = '100%';
          table.style.border = '1px solid #000';

          const headerRow = document.createElement('tr');
          headerRow.style.backgroundColor = '#f0f0f0';
          ['Name', 'Version', 'Build Status', 'Updated'].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            th.style.border = '1px solid #000';
            th.style.padding = '8px';
            th.style.textAlign = 'left';
            headerRow.appendChild(th);
          });
          table.appendChild(headerRow);

          user.maps.forEach((map, idx) => {
            const row = document.createElement('tr');
            row.style.backgroundColor = idx % 2 === 0 ? '#f9f9f9' : '#fff';
            row.style.border = '1px solid #000';

            const nameCell = document.createElement('td');
            nameCell.style.border = '1px solid #000';
            nameCell.style.padding = '8px';
            const nameLink = document.createElement('a');
            nameLink.href = `#/admin/maps/${map.id}`;
            nameLink.textContent = map.name;
            nameLink.style.color = '#0066cc';
            nameLink.style.textDecoration = 'underline';
            nameCell.appendChild(nameLink);
            row.appendChild(nameCell);

            const versionCell = document.createElement('td');
            versionCell.style.border = '1px solid #000';
            versionCell.style.padding = '8px';
            versionCell.textContent = map.version || '—';
            row.appendChild(versionCell);

            const buildCell = document.createElement('td');
            buildCell.style.border = '1px solid #000';
            buildCell.style.padding = '8px';
            buildCell.innerHTML = this.buildStatusHtml(map.buildStatus);
            row.appendChild(buildCell);

            const updatedCell = document.createElement('td');
            updatedCell.style.border = '1px solid #000';
            updatedCell.style.padding = '8px';
            updatedCell.textContent = map.updated ? new Date(map.updated * 1000).toLocaleDateString() : '—';
            row.appendChild(updatedCell);

            table.appendChild(row);
          });

          this.root.appendChild(table);
        }

        // Units count
        if (user.units && user.units.length > 0) {
          const h2 = document.createElement('h2');
          h2.textContent = 'Units';
          h2.style.marginTop = '30px';
          h2.style.marginBottom = '12px';
          this.root.appendChild(h2);

          const p = document.createElement('p');
          p.textContent = `${user.units.length} unit${user.units.length !== 1 ? 's' : ''} created`;
          this.root.appendChild(p);
        }
      } catch (err) {
        this.root.innerHTML = `<p style="padding:20px; color: red;">Failed to load user details: ${err.message}</p>`;
      }
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
