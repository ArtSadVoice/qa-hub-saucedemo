// ── Project state ──────────────────────────────────────────────────────────
let currentProject = localStorage.getItem('fp_project') || '';
let allProjects    = [];

function pq(url) {
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}p=${encodeURIComponent(currentProject)}`;
}

// ── UI helpers: empty state + skeleton ─────────────────────────────────────
// Why: render empty lists and loading states consistently (see .empty-state
// and .skeleton-line in app.css). Returns HTML strings for container.innerHTML.
//
// Usage:
//   el.innerHTML = emptyStateHTML('📭', 'ยังไม่มี notification');
//   el.innerHTML = emptyStateHTML('📦', 'ยังไม่มีโปรเจค',
//       {text: '+ Add Project', onclick: "showSection('projects')"});
//   el.innerHTML = skeletonLinesHTML(3);  // 3 animated placeholder lines
function emptyStateHTML(icon, title, cta = null, desc = '') {
  const ctaHTML = cta
    ? `<button class="es-cta" onclick="${cta.onclick}">${cta.text}</button>`
    : '';
  const descHTML = desc ? `<div>${desc}</div>` : '';
  return `<div class="empty-state">
    <div class="es-icon">${icon}</div>
    <div class="es-title">${title}</div>
    ${descHTML}
    ${ctaHTML}
  </div>`;
}

function skeletonLinesHTML(count = 3) {
  const widths = ['', 'w-70', 'w-40'];
  return Array.from({ length: count }, (_, i) =>
    `<div class="skeleton-line ${widths[i % widths.length]}"></div>`
  ).join('');
}

// ── apiCall: unified fetch wrapper ─────────────────────────────────────────
// Why: /api/* now returns {error, detail} for 4xx/5xx (backend commit deaaf9d).
// Callers should surface those messages to the user, not swallow them.
//
// Usage:
//   const data = await apiCall('/api/projects');                    // GET
//   await apiCall('/api/projects/add', {method:'POST', body: obj}); // POST JSON
//
// Options:
//   body:    passed as JSON (auto-stringified + Content-Type: application/json)
//   silent:  true → skip the automatic error toast (caller handles it)
//   raw:     true → return Response instead of parsed JSON
//
// Behaviour:
//   - 2xx: returns parsed JSON (or Response if raw)
//   - 4xx/5xx: shows toast with server's error message, throws Error
//   - Network error: shows toast, throws
async function apiCall(url, opts = {}) {
  const { body, silent, raw, method, headers, ...rest } = opts;
  const init = { method: method || (body ? 'POST' : 'GET'), headers: { ...headers }, ...rest };
  if (body !== undefined) {
    init.body = typeof body === 'string' ? body : JSON.stringify(body);
    init.headers['Content-Type'] = init.headers['Content-Type'] || 'application/json';
  }

  let r;
  try {
    r = await fetch(url, init);
  } catch (netErr) {
    if (!silent) showToast(`Network error: ${netErr.message}`, 'err');
    const err = new Error(netErr.message);
    err.network = true;
    throw err;
  }

  if (raw) return r;

  if (!r.ok) {
    let detail = '';
    try { const j = await r.json(); detail = j.error || j.detail || ''; } catch {}
    const msg = detail || `HTTP ${r.status} on ${url}`;
    if (!silent) showToast(msg, 'err');
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }

  try { return await r.json(); } catch { return null; }
}

// ── Init ───────────────────────────────────────────────────────────────────
async function init() {
  applyBranding();
  try {
    allProjects = await apiCall('/api/projects');

    const sel = document.getElementById('project-select');
    if (!allProjects.length) {
      sel.innerHTML = '<option value="">No projects — add one in Projects tab</option>';
      return;
    }

    sel.innerHTML = allProjects.map(p => {
      const dot = {active:'🟢', planning:'🟡', paused:'⚪'}[p.phase] || '🟢';
      return `<option value="${p.id}">${dot} ${p.name}</option>`;
    }).join('');

    // Restore last-used project, or default to first
    if (!currentProject || !allProjects.find(p => p.id === currentProject)) {
      currentProject = allProjects[0].id;
      localStorage.setItem('fp_project', currentProject);
    }
    sel.value = currentProject;
    updateTopbarProj();

  } catch(e) { console.error('init:', e); }

  markPipelineStages();
  updatePipelineForType();
  updateTabsForType();
  loadInfo();
  loadPipelineStatus();
  updateDownloadLinks();
}

function switchProject(id) {
  currentProject = id;
  localStorage.setItem('fp_project', id);
  _dashEnvFilter = 'all'; _applyEnvBtnStyle('.dash-env-btn','all'); _applyEnvBtnStyle('.ts-env-btn','all');
  _rhEnvFilter   = 'all'; _applyEnvBtnStyle('.rh-env-btn','all');
  _rhTagFilter = ''; _rhDateFrom = ''; _rhDateTo = '';
  _allBugs = []; _bugSort = { col: 'created_at', dir: 'desc' };
  const sel = document.getElementById('project-select');
  if (sel) sel.value = id;
  updateTopbarProj();
  updateDownloadLinks();
  updatePipelineForType();
  updateTabsForType();
  // Reload data for active section
  loadInfo();
  loadPipelineStatus();
  const name = document.querySelector('.section.active')?.id?.replace('section-','');
  if (name === 'chart')       loadChart();
  if (name === 'input')       loadInput();
  if (name === 'output')      loadOutput();
  if (name === 'screenshots') loadScreenshots();
  if (name === 'projects')    loadProjectsGrid();
  if (name === 'pipeline')    loadRunHistory();
  if (name === 'schedule')  { loadSchedule(); loadSchedLog(); }
  if (name === 'summary')    loadSummary();
  if (name === 'release')    loadRelease();
  if (name === 'bugs')        loadBugs(); else loadBugBadge();
}

function updateTopbarProj() {
  const proj = allProjects.find(p => p.id === currentProject);
  const phaseInfo = {planning:{e:'🗂️',c:'#FB8C00'}, paused:{e:'⏸️',c:'#9E9E9E'}};
  const ph = phaseInfo[proj?.phase];
  const badge = ph
    ? ` <span style="font-size:10px;background:rgba(255,255,255,0.15);padding:2px 8px;border-radius:10px;margin-left:6px;font-weight:600;color:rgba(255,255,255,0.9)">${ph.e} ${proj.phase}</span>`
    : '';
  document.getElementById('topbar-proj').innerHTML = (proj?.name || currentProject || '—') + badge;
}

async function _loadStatDelta() {
  const el = document.getElementById('s-pct-delta');
  if (!el) return;
  try {
    const r = await fetch(pq('/api/run/history'));
    const rows = await r.json();
    const valid = rows.filter(e => e.pass > 0 || e.fail > 0);
    if (valid.length < 2) { el.textContent = ''; return; }
    const cur  = valid[valid.length - 1];
    const prev = valid[valid.length - 2];
    const pct1 = cur.pass  + cur.fail  > 0 ? Math.round(cur.pass  / (cur.pass  + cur.fail)  * 100) : null;
    const pct2 = prev.pass + prev.fail > 0 ? Math.round(prev.pass / (prev.pass + prev.fail) * 100) : null;
    if (pct1 === null || pct2 === null) { el.textContent = ''; return; }
    const delta = pct1 - pct2;
    if (delta === 0) { el.innerHTML = '<span style="color:var(--muted)">→ 0%</span>'; return; }
    const color = delta > 0 ? '#43A047' : '#E53935';
    const arrow = delta > 0 ? '↑' : '↓';
    el.innerHTML = `<span style="color:${color};font-weight:700">${arrow}${Math.abs(delta)}% vs prev</span>`;
  } catch(e) { if (el) el.textContent = ''; }
}

function updateDownloadLinks() {
  const dlOut = document.getElementById('dl-output-link');
  if (dlOut) dlOut.href = pq('/api/output/download');
}

// ── Tab visibility by project type ────────────────────────────────────────
const FULL_PIPELINE_TABS = ['input', 'output', 'chart'];   // hidden for tests-only types
const TESTS_ONLY_TYPES = new Set(['playwright-only', 'pytest-only']);

function updateTabsForType() {
  const proj = allProjects.find(p => p.id === currentProject);
  const isTestsOnly = TESTS_ONLY_TYPES.has(proj?.type);

  document.querySelectorAll('.nav-item').forEach(nav => {
    const txt = nav.textContent.trim().toLowerCase();
    const isFullOnly = FULL_PIPELINE_TABS.some(t => txt.includes(t));
    if (isFullOnly) {
      nav.style.opacity   = isTestsOnly ? '0.35' : '';
      nav.style.pointerEvents = isTestsOnly ? 'none' : '';
    }
  });

  // If currently on a hidden tab, redirect to dashboard
  if (isTestsOnly) {
    const active = document.querySelector('.section.active')?.id?.replace('section-','');
    if (FULL_PIPELINE_TABS.includes(active)) showSection('dashboard');
  }
}

// ── Navigation ─────────────────────────────────────────────────────────────
const TITLES = {
  dashboard:'Dashboard', pipeline:'Run Pipeline', input:'Input Files',
  output:'Output', screenshots:'Screenshots', chart:'Chart Preview',
  projects:'Projects', summary:'All Projects Summary',
  bugs:'Bug Reports', about:'About', release:'Release Readiness',
  schedule:'Scheduled Runs', guide:'📖 User Guide', syscheck:'🩺 System Check'
};

function showGuideTab(tab, btn) {
  document.querySelectorAll('.guide-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.guide-tab').forEach(b => b.classList.remove('active-tab'));
  document.getElementById('gtab-' + tab).style.display = 'block';
  if (btn) btn.classList.add('active-tab');
  if (tab === 'commands') loadCommandsGuide();
}

async function loadCommandsGuide() {
  const body = document.getElementById('commands-guide-body');
  const badge = document.getElementById('cmd-badge');
  if (!body) return;
  body.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(4) + '</div>';
  try {
    const r = await fetch('/api/commands');
    const cmds = await r.json();
    if (!cmds.length) { body.innerHTML = emptyStateHTML('📋', 'ไม่พบ command files', null, 'ตรวจสอบว่า project มีโฟลเดอร์ .claude/commands/'); return; }
    // Group by category
    const groups = {};
    cmds.forEach(c => { (groups[c.category] = groups[c.category] || []).push(c); });
    let html = '';
    Object.entries(groups).forEach(([cat, list]) => {
      html += `<div class="card-title" style="font-size:12px;color:var(--muted);margin-top:12px">${cat}</div>
               <table class="ts-table" style="margin-bottom:12px">
               <thead><tr><th>Command</th><th>ทำอะไร</th></tr></thead><tbody>`;
      list.forEach(c => {
        html += `<tr><td><code>${c.name}</code></td><td>${c.description}</td></tr>`;
      });
      html += '</tbody></table>';
    });
    html += `<div class="divider"></div>
             <div style="background:#FFF8E1;border:1px solid #FFE082;border-radius:8px;padding:12px;font-size:12.5px">
               <b>⚠️ หมายเหตุ:</b> Commands ทำงานใน <b>Claude Code CLI</b> — ต้อง <code>cd</code> เข้า project folder ก่อนรัน<br>
               Hub-level commands (<code>/hub-*</code>, <code>/sync-agents</code>) ต้อง <code>cd</code> เข้า Hub folder
             </div>`;
    body.innerHTML = html;
    if (badge) badge.textContent = `${cmds.length} commands`;
  } catch(e) { body.innerHTML = `<div style="color:var(--danger);font-size:13px">Error loading commands: ${e.message}</div>`; }
}

// ── Branding ───────────────────────────────────────────────────────────────
let _branding = {};

async function applyBranding() {
  try {
    const r = await fetch('/api/config/branding');
    _branding = await r.json();
    _renderBranding(_branding);
    _populateBrandingForm(_branding);
  } catch(e) { console.warn('branding load failed', e); }
}

function _renderBranding(b) {
  const name = b.app_name || 'QA Hub Demo';
  const sub  = b.subtitle  || 'Multi-Project Dashboard';
  const logo = b.logo      || '🔬';
  const co   = b.company   || '';
  const foot = b.footer    || (name + ' v1.0' + (co ? ' · ' + co : ''));
  const col  = b.primary_color;

  // Sidebar
  const sbBrand = document.getElementById('sb-brand');
  if (sbBrand) {
    if (b.logo_url) {
      sbBrand.innerHTML = `<img src="${b.logo_url}" style="height:22px;vertical-align:middle;margin-right:6px;border-radius:4px" onerror="this.style.display='none'">${name}`;
    } else {
      sbBrand.textContent = logo + ' ' + name;
    }
  }
  const sbSub  = document.getElementById('sb-subtitle'); if (sbSub)  sbSub.textContent  = sub;
  const sbFoot = document.getElementById('sb-footer');   if (sbFoot) sbFoot.textContent  = foot;

  // Title tag
  document.title = name + ' | ' + sub;

  // About section
  const aTitle = document.getElementById('about-app-title'); if (aTitle) aTitle.textContent = 'About ' + name;
  const aTool  = document.getElementById('about-tool-name'); if (aTool)  aTool.textContent  = name + ' — ' + sub;

  // Primary color override
  if (col && /^#[0-9A-Fa-f]{6}$/.test(col)) {
    document.documentElement.style.setProperty('--primary-dk', col);
    // lighten for primary
    document.documentElement.style.setProperty('--primary', col + 'CC');
  }
}

function _populateBrandingForm(b) {
  const s = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  s('br-app-name', b.app_name);
  s('br-subtitle', b.subtitle);
  s('br-logo',     b.logo);
  s('br-logo-url', b.logo_url);
  s('br-company',  b.company);
  s('br-color-text', b.primary_color);
  const cp = document.getElementById('br-color-pick');
  if (cp && b.primary_color && /^#[0-9A-Fa-f]{6}$/.test(b.primary_color)) cp.value = b.primary_color;
  _updateBrandingPreview();
}

function _updateBrandingPreview() {
  const name = document.getElementById('br-app-name')?.value  || 'QA Hub Demo';
  const sub  = document.getElementById('br-subtitle')?.value  || 'Multi-Project Dashboard';
  const logo = document.getElementById('br-logo')?.value      || '🔬';
  const url  = document.getElementById('br-logo-url')?.value  || '';
  const co   = document.getElementById('br-company')?.value   || '';
  const foot = name + ' v1.0' + (co ? ' · ' + co : '');
  const pLogo = document.getElementById('br-preview-logo');
  if (pLogo) pLogo.innerHTML = url ? `<img src="${url}" style="max-height:28px;border-radius:4px" onerror="this.outerHTML='${logo}'">` : logo;
  const pName = document.getElementById('br-preview-name'); if (pName) pName.textContent = name;
  const pSub  = document.getElementById('br-preview-sub');  if (pSub)  pSub.textContent  = sub;
  const pFoot = document.getElementById('br-preview-footer'); if (pFoot) pFoot.textContent = foot;
}

// wire live preview — called once about section first shown
function _wireBrandingPreview() {
  ['br-app-name','br-subtitle','br-logo','br-logo-url','br-company'].forEach(id =>
    document.getElementById(id)?.addEventListener('input', _updateBrandingPreview)
  );
}

function syncColorPick(val) {
  if (/^#[0-9A-Fa-f]{6}$/.test(val)) {
    const cp = document.getElementById('br-color-pick');
    if (cp) cp.value = val;
  }
}

async function saveBranding() {
  const payload = {
    app_name:      document.getElementById('br-app-name')?.value.trim(),
    subtitle:      document.getElementById('br-subtitle')?.value.trim(),
    logo:          document.getElementById('br-logo')?.value.trim(),
    logo_url:      document.getElementById('br-logo-url')?.value.trim(),
    primary_color: document.getElementById('br-color-text')?.value.trim(),
    company:       document.getElementById('br-company')?.value.trim(),
  };
  try {
    await apiCall('/api/config/branding/save', {body: payload});
    showToast('✅ Branding บันทึกแล้ว', 'ok');
    _branding = {..._branding, ...payload};
    _renderBranding(_branding);
  } catch(e) { /* apiCall already toasted */ }
}

async function resetBranding() {
  const defaults = { app_name:'QA Hub Demo', subtitle:'Multi-Project Dashboard', logo:'🔬', logo_url:'', primary_color:'', company:'', footer:'' };
  try {
    await apiCall('/api/config/branding/save', {body: defaults});
    _branding = defaults;
    _populateBrandingForm(defaults);
    _renderBranding(defaults);
    document.documentElement.style.removeProperty('--primary-dk');
    document.documentElement.style.removeProperty('--primary');
    showToast('↺ Reset เป็นค่า default แล้ว', 'ok');
  } catch(e) { showToast('Reset ไม่สำเร็จ', 'err'); }
}

// ── Email Settings ────────────────────────────────────────────────────────
let _emailCfg = {};
let _emailProvider = 'smtp';

function switchEmailProvider(prov) {
  _emailProvider = prov;
  document.getElementById('em-smtp-fields').style.display   = prov === 'smtp'   ? 'grid' : 'none';
  document.getElementById('em-resend-fields').style.display  = prov === 'resend' ? 'block' : 'none';
  document.querySelectorAll('.em-prov-btn').forEach(b => {
    b.style.background = '#F0F4F8'; b.style.color = 'var(--text)'; b.style.borderColor = 'var(--border)';
  });
  const active = document.getElementById(`em-prov-${prov}`);
  if (active) { active.style.background = 'var(--primary)'; active.style.color = '#fff'; active.style.borderColor = 'var(--primary)'; }
}

async function _loadEmailSettings() {
  try {
    _emailCfg = await apiCall('/api/config/email');
    _emailProvider = _emailCfg.provider || 'smtp';
    switchEmailProvider(_emailProvider);
    document.getElementById('em-host').value        = _emailCfg.smtp_host || '';
    document.getElementById('em-port').value        = _emailCfg.smtp_port || 587;
    document.getElementById('em-user').value        = _emailCfg.smtp_user || '';
    document.getElementById('em-pass').value        = _emailCfg.smtp_pass || '';
    document.getElementById('em-resend-key').value   = _emailCfg.resend_api_key || '';
    document.getElementById('em-resend-from').value  = _emailCfg.resend_from || '';
    document.getElementById('em-sender').value      = _emailCfg.sender_name || '';
    document.getElementById('em-subject').value     = _emailCfg.subject_template || '';
    _renderRecipientList('to', _emailCfg.to || []);
    _renderRecipientList('cc', _emailCfg.cc || []);
  } catch(e) { console.error('email load:', e); }
}

function _renderRecipientList(type, list) {
  const el = document.getElementById(`em-${type}-list`);
  if (!list.length) { el.innerHTML = '<div style="font-size:12px;color:var(--muted);padding:4px 0">ยังไม่มี</div>'; return; }
  el.innerHTML = list.map((r, i) => `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12.5px">
    <span style="font-weight:600">${r.name || '—'}</span>
    <span style="color:var(--muted)">${r.email}</span>
    <button class="btn btn-sm" onclick="removeRecipient('${type}',${i})" style="padding:1px 6px;font-size:11px;background:#FFEBEE;color:#C62828;border:1px solid #EF9A9A">×</button>
  </div>`).join('');
}

function addEmailRecipient(type) {
  const name  = document.getElementById(`em-${type}-name`).value.trim();
  const email = document.getElementById(`em-${type}-email`).value.trim();
  if (!email) { showToast('กรุณากรอก email', 'err'); return; }
  const list = _emailCfg[type] || [];
  list.push({ name: name || email.split('@')[0], email });
  _emailCfg[type] = list;
  _renderRecipientList(type, list);
  document.getElementById(`em-${type}-name`).value = '';
  document.getElementById(`em-${type}-email`).value = '';
}

function removeRecipient(type, idx) {
  const list = _emailCfg[type] || [];
  list.splice(idx, 1);
  _renderRecipientList(type, list);
}

async function saveEmailSettings() {
  const payload = {
    provider:      _emailProvider,
    smtp_host:     document.getElementById('em-host').value.trim(),
    smtp_port:     parseInt(document.getElementById('em-port').value) || 587,
    smtp_user:     document.getElementById('em-user').value.trim(),
    smtp_pass:     document.getElementById('em-pass').value.trim(),
    resend_api_key: document.getElementById('em-resend-key').value.trim(),
    resend_from:   document.getElementById('em-resend-from').value.trim(),
    sender_name:   document.getElementById('em-sender').value.trim(),
    subject_template: document.getElementById('em-subject').value.trim(),
    to: _emailCfg.to || [],
    cc: _emailCfg.cc || [],
  };
  try {
    await apiCall('/api/config/email/save', {body: payload});
    showToast('💾 Email settings saved — sync ไปทุก project แล้ว', 'ok');
  } catch(e) { /* apiCall already toasted */ }
}

async function testEmailConnection() {
  const btn = document.getElementById('em-test-btn');
  const res = document.getElementById('em-test-result');
  btn.disabled = true; btn.innerHTML = '<span class="spin"></span> Testing...';
  res.innerHTML = '';
  try {
    const d = await apiCall('/api/config/email/test', {
      silent: true,
      body: {
        provider:  _emailProvider,
        smtp_host: document.getElementById('em-host').value.trim(),
        smtp_port: parseInt(document.getElementById('em-port').value) || 587,
        smtp_user: document.getElementById('em-user').value.trim(),
        smtp_pass: document.getElementById('em-pass').value.trim(),
        resend_api_key: document.getElementById('em-resend-key').value.trim(),
      }
    });
    res.innerHTML = `<span style="color:#2E7D32">✅ ${d.detail}</span>`;
  } catch(e) { res.innerHTML = `<span style="color:#C62828">❌ ${e.message || 'Connection failed'}</span>`; }
  btn.disabled = false; btn.textContent = '🔌 Test Connection';
}

// ── Chat Notifications (Slack / Teams / Discord) ──────────────────────────
async function _loadNotificationSettings() {
  try {
    const n = await apiCall('/api/config/notifications');
    document.getElementById('nf-slack').value   = n.slack_webhook   || '';
    document.getElementById('nf-teams').value   = n.teams_webhook   || '';
    document.getElementById('nf-discord').value = n.discord_webhook || '';
    // Map notify_on list back to radio
    const on = n.notify_on || ['fail', 'error'];
    let pick = 'fail-error';
    if (on.includes('all')) pick = 'all';
    else if (on.length === 1 && on[0] === 'error') pick = 'error-only';
    const radio = document.querySelector(`input[name="nf-on"][value="${pick}"]`);
    if (radio) radio.checked = true;
  } catch(e) { /* apiCall toasted */ }
}

function _notifyOnFromRadio() {
  const v = document.querySelector('input[name="nf-on"]:checked')?.value || 'fail-error';
  if (v === 'all')        return ['all'];
  if (v === 'error-only') return ['error'];
  return ['fail', 'error'];
}

async function saveNotificationSettings() {
  const payload = {
    slack_webhook:   document.getElementById('nf-slack').value.trim(),
    teams_webhook:   document.getElementById('nf-teams').value.trim(),
    discord_webhook: document.getElementById('nf-discord').value.trim(),
    notify_on:       _notifyOnFromRadio(),
  };
  try {
    await apiCall('/api/config/notifications/save', {body: payload});
    showToast('💾 Notification settings saved', 'ok');
  } catch(e) { /* apiCall toasted */ }
}

async function testNotification(service) {
  const url = document.getElementById(`nf-${service}`).value.trim();
  const res = document.getElementById(`nf-${service}-result`);
  if (!url) { res.innerHTML = '<span style="color:#C62828">URL ว่าง</span>'; return; }
  res.innerHTML = '<span class="spin" style="display:inline-block;width:10px;height:10px;border:2px solid #ccc;border-top-color:var(--primary);border-radius:50%;animation:spin .6s linear infinite"></span>';
  // Send only that one service's URL so other webhooks don't fire
  const payload = {[`${service}_webhook`]: url};
  try {
    const d = await apiCall('/api/notifications/test', {silent: true, body: payload});
    const ok = d.results?.[service];
    res.innerHTML = ok
      ? '<span style="color:#2E7D32">✅ ส่งสำเร็จ — เช็ค channel</span>'
      : '<span style="color:#C62828">❌ ส่งไม่สำเร็จ</span>';
  } catch(e) {
    res.innerHTML = `<span style="color:#C62828">❌ ${e.message}</span>`;
  }
}

// ── AI Settings + Test Plan Generator ─────────────────────────────────────
async function _loadAiSettings() {
  try {
    const a = await apiCall('/api/config/ai');
    document.getElementById('ai-provider').value = a.provider || 'cli';
    document.getElementById('ai-model').value    = a.model    || '';
    _toggleAiKeyField();
    document.getElementById('ai-key-hint').textContent = a.api_key_set ? '✓ key already configured (เว้นว่างเพื่อใช้ค่าเดิม)' : '';
  } catch(e) { /* apiCall toasted */ }
}

function _toggleAiKeyField() {
  const isApi = document.getElementById('ai-provider').value === 'api';
  document.getElementById('ai-api-key-wrap').style.display = isApi ? 'block' : 'none';
}

async function saveAiSettings() {
  const payload = {
    provider: document.getElementById('ai-provider').value,
    model:    document.getElementById('ai-model').value.trim(),
  };
  // Only send api_key if user typed one — empty means "keep current"
  const key = document.getElementById('ai-api-key').value.trim();
  if (key) payload.api_key = key;
  try {
    await apiCall('/api/config/ai/save', {body: payload});
    showToast('💾 AI settings saved', 'ok');
    document.getElementById('ai-api-key').value = '';
    _loadAiSettings();
  } catch(e) { /* apiCall toasted */ }
}

async function generateTestPlan() {
  const requirement = document.getElementById('ai-req').value.trim();
  if (!requirement) { showToast('Paste requirement ก่อน', 'warn'); return; }

  const btn    = document.getElementById('ai-gen-btn');
  const status = document.getElementById('ai-gen-status');
  const wrap   = document.getElementById('ai-output-wrap');
  const out    = document.getElementById('ai-output');

  btn.disabled = true;
  status.innerHTML = '<span class="spin" style="display:inline-block;width:10px;height:10px;border:2px solid #ccc;border-top-color:var(--primary);border-radius:50%;animation:spin .6s linear infinite"></span> generating... (CLI mode อาจรอ 30-60 วินาที)';
  wrap.style.display = 'block';
  out.textContent = '...';

  const payload = {project_id: currentProject || '', requirement};
  try {
    const d = await apiCall('/api/ai/generate-test-plan', {body: payload, silent: true});
    out.textContent = d.output;
    status.innerHTML = `<span style="color:#2E7D32">✓ generated via ${d.provider}${d.model && d.model !== 'default' ? ' (' + d.model + ')' : ''}</span>`;
  } catch(e) {
    out.textContent = '';
    wrap.style.display = 'none';
    status.innerHTML = `<span style="color:#C62828">❌ ${e.message}</span>`;
  } finally {
    btn.disabled = false;
  }
}

function copyAiOutput() {
  const text = document.getElementById('ai-output').textContent;
  if (!text) return;
  navigator.clipboard.writeText(text)
    .then(() => showToast('📋 คัดลอกแล้ว', 'ok'))
    .catch(() => showToast('คัดลอกไม่สำเร็จ', 'err'));
}

// Wire provider toggle to show/hide API key field
document.addEventListener('DOMContentLoaded', () => {
  const sel = document.getElementById('ai-provider');
  if (sel) sel.addEventListener('change', _toggleAiKeyField);
});

// ── Hub Health (auto-refresh-able snapshot) ───────────────────────────────
function _formatUptime(seconds) {
  if (seconds < 60)    return `${seconds}s`;
  if (seconds < 3600)  return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
}

async function loadHubHealth() {
  const body    = document.getElementById('hub-health-body');
  const summary = document.getElementById('hub-health-summary');
  if (!body) return;
  body.innerHTML = '<div style="padding:6px 0">' + skeletonLinesHTML(3) + '</div>';
  let d;
  try { d = await apiCall('/api/hub/health'); }
  catch(e) { body.innerHTML = emptyStateHTML('⚠️', 'โหลด health ไม่ได้', {text:'ลองใหม่', onclick:'loadHubHealth()'}); return; }

  const errBadge   = d.errors_last_hour > 0   ? `<span style="background:#FFEBEE;color:#C62828;padding:1px 6px;border-radius:8px;font-size:11px;font-weight:700">${d.errors_last_hour} err</span>` : '';
  const warnBadge  = d.warnings_last_hour > 0 ? `<span style="background:#FFF8E1;color:#F57F17;padding:1px 6px;border-radius:8px;font-size:11px;font-weight:700">${d.warnings_last_hour} warn</span>` : '';
  const authBadge  = d.auth_enabled ? '🔐 auth on' : '⚠️ auth off';
  if (summary) summary.innerHTML = `up ${_formatUptime(d.uptime_seconds)} · ${authBadge} ${errBadge} ${warnBadge}`;

  const recent = (d.recent_audit || []).slice().reverse();
  const recentHTML = recent.length
    ? recent.map(e => `<div style="font-size:11.5px;color:var(--muted);font-family:monospace">${e.ts}  <b style="color:var(--primary-dk)">${e.action}</b>  by ${e.user}</div>`).join('')
    : '<div style="font-size:12px;color:var(--muted);font-style:italic">ไม่มี audit เพิ่งเกิด</div>';

  body.innerHTML = `
    <div class="flak-row">
      <div class="flak-stat"><div class="n">${_formatUptime(d.uptime_seconds)}</div><div class="l">uptime</div></div>
      <div class="flak-stat"><div class="n">${d.registered_projects}</div><div class="l">projects</div></div>
      <div class="flak-stat"><div class="n">${d.active_schedules}</div><div class="l">active schedules</div></div>
      <div class="flak-stat"><div class="n" style="color:${d.errors_last_hour > 0 ? '#C62828' : 'var(--text)'}">${d.errors_last_hour}</div><div class="l">errors / 1h</div></div>
      <div class="flak-stat"><div class="n" style="color:${d.warnings_last_hour > 0 ? '#F57F17' : 'var(--text)'}">${d.warnings_last_hour}</div><div class="l">warnings / 1h</div></div>
    </div>
    <div style="font-size:11px;color:var(--muted);margin-top:10px">
      <b>Log sizes:</b> hub.log ${d.log_sizes_kb.hub_log} KB · audit.jsonl ${d.log_sizes_kb.audit_jsonl} KB · schedule.log ${d.log_sizes_kb.schedule_log} KB
    </div>
    <div style="font-size:11px;color:var(--muted);margin-top:4px">
      Started ${d.started_at} · Python ${d.python}
    </div>
    <div style="margin-top:12px">
      <div style="font-size:11.5px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Recent activity</div>
      ${recentHTML}
    </div>
  `;
}

// ── Audit Log Viewer ──────────────────────────────────────────────────────
async function loadAuditLog() {
  const body = document.getElementById('audit-body');
  if (!body) return;
  body.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(5) + '</div>';
  const action = document.getElementById('audit-filter')?.value || '';
  const q = action ? `?limit=100&action=${encodeURIComponent(action)}` : '?limit=100';
  let d;
  try { d = await apiCall('/api/audit' + q); }
  catch(e) { body.innerHTML = emptyStateHTML('⚠️', 'โหลด audit log ไม่ได้', {text: 'ลองใหม่', onclick: 'loadAuditLog()'}); return; }

  if (!d.entries?.length) {
    body.innerHTML = emptyStateHTML('📭', 'ยังไม่มี audit entry', null,
      action ? `ไม่พบ entry สำหรับ '${action}*'` : 'จะปรากฏเมื่อมี mutation บน Hub');
    return;
  }
  // Newest at top
  const rows = d.entries.slice().reverse().map(e => {
    const det = JSON.stringify(e.details || {}, null, 0).slice(0, 120);
    const detTrunc = det.length === 120 ? det + '…' : det;
    return `<tr>
      <td style="font-family:monospace;font-size:11.5px;white-space:nowrap;color:var(--muted)">${e.ts}</td>
      <td style="font-size:12px"><b>${e.user}</b> <span style="color:var(--muted);font-size:11px">${e.ip || ''}</span></td>
      <td style="font-size:12px;font-weight:600;color:var(--primary-dk)">${e.action}</td>
      <td style="font-size:11.5px;color:var(--muted);font-family:monospace">${detTrunc}</td>
    </tr>`;
  }).join('');
  body.innerHTML = `<table style="width:100%;border-collapse:collapse">
    <thead><tr style="background:var(--bg);border-bottom:2px solid var(--border)">
      <th style="text-align:left;padding:6px 8px;font-size:11px;color:var(--muted);text-transform:uppercase">When</th>
      <th style="text-align:left;padding:6px 8px;font-size:11px;color:var(--muted);text-transform:uppercase">Who</th>
      <th style="text-align:left;padding:6px 8px;font-size:11px;color:var(--muted);text-transform:uppercase">Action</th>
      <th style="text-align:left;padding:6px 8px;font-size:11px;color:var(--muted);text-transform:uppercase">Details</th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>
  <div style="font-size:11px;color:var(--muted);margin-top:8px">${d.count} entries · newest first</div>`;
}

// ── Email Template Editor ─────────────────────────────────────────────────
let _tplEditorOpen = false;

async function loadEmailTemplate() {
  const name = document.getElementById('tpl-name').value;
  previewTemplate('pass');
  if (_tplEditorOpen) {
    try {
      const r = await fetch(`/api/email-template?name=${name}`);
      const d = await r.json();
      document.getElementById('tpl-editor').value = d.html || '';
    } catch(e) {}
  }
}

function previewTemplate(scenario) {
  const name = document.getElementById('tpl-name').value;
  document.getElementById('tpl-preview').src = `/api/email-template/preview?name=${name}&scenario=${scenario}`;
}

function toggleTplEditor() {
  const wrap = document.getElementById('tpl-editor-wrap');
  _tplEditorOpen = !_tplEditorOpen;
  wrap.style.display = _tplEditorOpen ? 'block' : 'none';
  document.getElementById('tpl-edit-btn').textContent = _tplEditorOpen ? '✕ Close Editor' : '✏️ Edit Template';
  if (_tplEditorOpen) {
    const name = document.getElementById('tpl-name').value;
    fetch(`/api/email-template?name=${name}`)
      .then(r => r.json())
      .then(d => document.getElementById('tpl-editor').value = d.html || '');
  }
}

async function saveTemplate() {
  const name = document.getElementById('tpl-name').value;
  const html = document.getElementById('tpl-editor').value;
  try {
    const r = await fetch('/api/email-template/save', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name, html })
    });
    const d = await r.json();
    if (d.ok) {
      showToast('💾 Template saved', 'ok');
      previewTemplate('pass');
    } else { showToast(d.error || 'Save failed', 'err'); }
  } catch(e) { showToast('Save failed', 'err'); }
}

async function resetTemplate() {
  const name = document.getElementById('tpl-name').value;
  try {
    const r = await fetch('/api/email-template/reset', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name })
    });
    const d = await r.json();
    if (d.ok) {
      showToast('↺ Template reset to default', 'ok');
      if (_tplEditorOpen) document.getElementById('tpl-editor').value = d.html || '';
      previewTemplate('pass');
    } else { showToast(d.error || 'Reset failed', 'err'); }
  } catch(e) { showToast('Reset failed', 'err'); }
}

function copyCmd(cmd) {
  navigator.clipboard.writeText(cmd).then(() => showToast('คัดลอกแล้ว: ' + cmd, 'ok')).catch(() => showToast('ไม่สามารถคัดลอกได้', 'err'));
}

function runSendReport() {
  if (!currentProject) { showToast('กรุณาเลือก Project ก่อน', 'err'); return; }
  const channel = document.getElementById('send-channel-select')?.value || 'both';
  runStep('send-report', 'Send Report (' + channel + ')', '?channel=' + channel);
}

async function loadMiniGate() {
  if (!currentProject) return;
  const el = document.getElementById('mini-gate-items');
  el.innerHTML = '<div style="color:var(--muted)">กำลังตรวจสอบ...</div>';
  const _projMeta = allProjects.find(p => p.id === currentProject);
  const _miniPassGate = _projMeta?.gates?.pass_rate ?? 80;
  try {
    const [bugsR, histR] = await Promise.all([fetch(pq('/api/bugs')), fetch(pq('/api/run/history'))]);
    const bugs = await bugsR.json();
    const hist = await histR.json();
    const validHist = hist.filter(e => e.pass > 0 || e.fail > 0);
    const last = validHist.length ? validHist[validHist.length - 1] : null;
    const passRate = last ? Math.round(last.pass / (last.pass + last.fail) * 100) : null;
    const openCrit = bugs.filter(b => b.severity === 'Critical' && b.status === 'Open').length;
    const openHigh = bugs.filter(b => b.severity === 'High' && b.status === 'Open').length;
    const TAG_W = {'': 3, regression: 3, e2e: 2, visual: 2, smoke: 1};
    const tagW = TAG_W[last?.tag ?? ''] ?? 0;
    const g = (ok, label, detail) =>
      `<div style="display:flex;align-items:center;gap:6px"><span style="font-size:13px">${ok ? '✅' : '❌'}</span><span style="font-size:12px"><b>${label}</b>${detail ? ' <span style="color:var(--muted)">— ' + detail + '</span>' : ''}</span></div>`;
    el.innerHTML = [
      g(passRate !== null && passRate >= _miniPassGate, `Pass Rate ≥ ${_miniPassGate}%`, passRate !== null ? passRate + '%' : 'ยังไม่มีข้อมูล'),
      g(tagW >= 2, 'Run Scope (@e2e+)', last?.tag ? '@' + last.tag : 'ยังไม่รัน'),
      g(openCrit === 0, 'No Critical Bug', openCrit > 0 ? openCrit + ' open' : ''),
      g(openHigh === 0, 'No High Bug', openHigh > 0 ? openHigh + ' open' : ''),
      g(validHist.length > 0, 'มี Run History', validHist.length ? 'last: ' + (last?.ts?.slice(0,10) || '—') : 'ไม่มี'),
    ].join('');
  } catch(e) { el.innerHTML = '<div style="color:var(--error)">โหลดข้อมูลไม่ได้ — ตรวจสอบว่า Hub รันอยู่</div>'; }
}

function openAssignModal(bugId, bugTitle) {
  const existing = document.getElementById('assign-modal-overlay');
  if (existing) existing.remove();
  const overlay = document.createElement('div');
  overlay.id = 'assign-modal-overlay';
  overlay.className = 'assign-modal';
  overlay.innerHTML = `
    <div class="assign-box">
      <div style="font-weight:700;font-size:14px;margin-bottom:4px">👤 Assign Bug</div>
      <div style="font-size:12.5px;color:var(--muted);margin-bottom:14px">${bugTitle}</div>
      <label style="font-size:12px;font-weight:600;color:var(--muted);display:block;margin-bottom:4px">Assign ให้</label>
      <input id="assign-name-input" type="text" placeholder="ชื่อหรือ email ของผู้รับผิดชอบ"
        style="width:100%;padding:8px 10px;border-radius:7px;border:1px solid var(--border);background:var(--card);color:var(--text);font-size:13px;box-sizing:border-box;margin-bottom:14px">
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-sm" onclick="document.getElementById('assign-modal-overlay').remove()">ยกเลิก</button>
        <button class="btn btn-sm btn-primary" onclick="submitAssign('${bugId}')">✅ Assign</button>
      </div>
    </div>`;
  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
  setTimeout(() => document.getElementById('assign-name-input')?.focus(), 50);
}

async function submitAssign(bugId) {
  const name = document.getElementById('assign-name-input')?.value?.trim();
  if (!name) { showToast('กรุณาระบุชื่อผู้รับผิดชอบ', 'err'); return; }
  const now = new Date().toISOString().slice(0,16).replace('T',' ');
  try {
    const r = await fetch(pq('/api/bugs/update'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: currentProject, id: bugId, related_task: 'Assigned: ' + name + ' (' + now + ')' })
    });
    const d = await r.json();
    if (d.ok) {
      showToast('✅ Assigned ให้ ' + name, 'ok');
      document.getElementById('assign-modal-overlay')?.remove();
      loadBugs();
    } else { showToast('Error: ' + (d.error || 'ไม่สำเร็จ'), 'err'); }
  } catch(e) { showToast('ไม่สามารถเชื่อมต่อ Hub API ได้', 'err'); }
}

function showSection(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('section-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => {
    const txt = n.textContent.trim().toLowerCase();
    if (txt.includes(name.replace('-',' '))) n.classList.add('active');
  });
  document.getElementById('page-title').textContent = TITLES[name] || name;

  if (name === 'chart')       loadChart();
  if (name === 'input')       loadInput();
  if (name === 'output')      loadOutput();
  if (name === 'screenshots') loadScreenshots();
  if (name === 'pipeline')    { loadPipelineStatus(); updatePipelineForType(); loadRunHistory(); _checkWatchStatus(); }
  if (name === 'projects')    loadProjectsGrid();
  if (name === 'summary')     loadSummary();
  if (name === 'bugs')        loadBugs();
  if (name === 'release')     loadRelease();
  if (name === 'schedule')    { loadSchedule(); loadSchedLog(); }
  if (name === 'about')       { _wireBrandingPreview(); _populateBrandingForm(_branding); _loadEmailSettings(); loadEmailTemplate(); _loadNotificationSettings(); loadAuditLog(); loadHubHealth(); _loadAiSettings(); }
}

function refreshCurrent() {
  const name = document.querySelector('.section.active')?.id?.replace('section-','');
  if (name === 'dashboard')   { loadInfo(); loadFlakiness(); }
  if (name === 'pipeline')    loadPipelineStatus();
  if (name === 'chart')       loadChart();
  if (name === 'input')       loadInput();
  if (name === 'output')      loadOutput();
  if (name === 'screenshots') loadScreenshots();
  if (name === 'projects')    loadProjectsGrid();
  if (name === 'bugs')        loadBugs();
  if (name === 'schedule')    { loadSchedule(); loadSchedLog(); }
}

// ── Dashboard ──────────────────────────────────────────────────────────────
async function loadInfo() {
  if (!currentProject) return;
  loadFlakiness();  // fire-and-forget; renders into its own card
  try {
    const envQ = _dashEnvFilter !== 'all' ? `&env=${_dashEnvFilter}` : '';
    const d = await apiCall(pq('/api/info') + envQ);

    const projMeta = allProjects.find(p => p.id === currentProject);
    const isPWOnly = projMeta?.type === 'playwright-only';
    const isPytestOnly = projMeta?.type === 'pytest-only';
    const isTestsOnly = isPWOnly || isPytestOnly;

    if (isTestsOnly) {
      // ── Tests-only dashboard (Playwright or Pytest) ────────────────
      const L = d.pw_last;
      document.getElementById('s-total').textContent = L ? L.total : '—';
      document.getElementById('s-pass').textContent  = L ? L.pass  : '—';
      document.getElementById('s-fail').textContent  = L ? L.fail  : '—';
      document.getElementById('s-pct').textContent   = L ? L.pct + '%' : '—';
      _loadStatDelta();

      // Project info — show basic meta
      const meta = d.project_meta || {};
      document.getElementById('proj-table').innerHTML = [
        ['Project',  meta.name || '—'],
        ['Type',     isPytestOnly ? '🐍 Pytest-Only' : '🎭 Playwright-Only'],
        ['Path',     meta.path || '—'],
        ['Screenshots (test-results)', d.pw_shot_count ?? 0],
      ].map(([k,v]) =>
        `<tr><td style="font-weight:600;width:180px;color:var(--muted);font-size:12px">${k}</td>
         <td style="font-size:13px">${v}</td></tr>`
      ).join('');

      // Stat label อัปเดต
      document.querySelector('#stats-row .stat:nth-child(1) .stat-lbl').textContent = 'Tests (last run)';

      // Run history table แทน TCM table (reuse _rhAllRows + _rhRender via ts-tbody redirect)
      const tbody = document.getElementById('ts-tbody');
      const hist  = d.pw_history || [];
      const validHist = hist.filter(e => e.pass > 0 || e.fail > 0);   // hide ghost by default

      // Replace table headers for PW-only context
      document.querySelector('#ts-table thead tr').innerHTML = `
        <th>Timestamp</th><th>Env</th><th>Scope</th>
        <th style="text-align:center">Pass</th>
        <th style="text-align:center">Fail</th>
        <th style="text-align:center">Pass Rate</th>
        <th style="text-align:center">Result</th>
        <th style="text-align:center">Source</th>`;

      const ghostCount = hist.length - validHist.length;
      const renderHist = rows => {
        if (!rows.length) {
          return `<tr><td colspan="6" style="color:var(--muted);padding:20px;text-align:center">
            ยังไม่มี run history${ghostCount ? ` (ซ่อน ghost runs ${ghostCount} รายการ)` : ''} — กด <b>▶ Run Tests</b> ใน Pipeline ก่อน
          </td></tr>`;
        }
        return [...rows].reverse().map(e => {
          const total    = e.pass + e.fail;
          const pct      = total ? Math.round(e.pass / total * 100) : 0;
          const ok       = e.rc === 0;
          const pctColor = pct >= 80 ? '#2E7D32' : pct >= 60 ? '#E65100' : '#B71C1C';
          const isGhost  = e.pass === 0 && e.fail === 0;
          const envVal   = e.env || 'uat';
          const envBadge = envVal === 'prod'
            ? `<span style="background:#FFEBEE;color:#B71C1C;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:700;border:1px solid #EF9A9A">🔴 PROD</span>`
            : `<span style="background:#E8F5E9;color:#2E7D32;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:600;border:1px solid #A5D6A7">🟢 UAT</span>`;
          const rowBg    = isGhost ? 'opacity:.5;' : envVal === 'prod' ? 'background:rgba(255,235,238,.35);' : '';
          const srcBadge = e.source === 'schedule'
            ? `<span style="background:#FFF3E0;color:#E65100;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:700;border:1px solid #FFB74D" title="Scheduled run: ${e.ts}">🕐 sched</span>`
            : `<span style="color:var(--muted);font-size:11px">manual</span>`;
          return `<tr style="${rowBg}">
            <td style="font-size:12px">${e.ts}</td>
            <td>${envBadge}</td>
            <td>${_rhTagPill(e.tag||'')}</td>
            <td style="text-align:center;color:#2E7D32;font-weight:700">${e.pass}</td>
            <td style="text-align:center;color:${e.fail>0?'#B71C1C':'var(--muted)'};font-weight:700">${e.fail}</td>
            <td style="text-align:center;font-weight:700;color:${pctColor}">${isGhost ? '<span style="color:var(--muted);font-size:11px">ghost</span>' : pct+'%'}</td>
            <td style="text-align:center"><span class="badge ${ok?'badge-ok':'badge-running'}">${ok?'Done ✓':'Error ✗'}</span></td>
            <td style="text-align:center">${srcBadge}</td>
          </tr>`;
        }).join('');
      };

      tbody.innerHTML = renderHist(validHist);
      // Note: ไปจัดการ ghost runs ได้ที่ Pipeline > Run History
      const tsNote = document.getElementById('ts-ghost-note');
      if (tsNote) tsNote.textContent = ghostCount ? `ซ่อน ghost runs ${ghostCount} รายการ — จัดการได้ที่ Pipeline > Run History` : '';
      const retrofitCard = document.getElementById('retrofit-card');
      if (retrofitCard) retrofitCard.style.display = '';
      const eb = document.getElementById('ts-export-btn');
      eb.disabled = false;
      eb.title = 'Export Run History เป็น Excel';
      eb.style.opacity = ''; eb.style.cursor = 'pointer';
      loadTrend();

    } else {
      // ── Full-pipeline dashboard (เดิม) ────────────────────────────
      document.getElementById('s-total').textContent = d.total_tc ?? '—';
      document.getElementById('s-pass').textContent  = d.totals?.pass ?? '—';
      document.getElementById('s-fail').textContent  = d.totals?.fail ?? '—';
      document.getElementById('s-pct').textContent   = d.accuracy != null ? d.accuracy + '%' : '—';
      document.querySelector('#stats-row .stat:nth-child(1) .stat-lbl').textContent = 'Total TCs';
      _loadStatDelta();

      const proj = d.project || {};
      const fields = ['Project Code','Project Name','Topic','Customer','Prepared By','Prepared Date','Sprint / Version'];
      document.getElementById('proj-table').innerHTML = fields.map(f =>
        `<tr><td style="font-weight:600;width:180px;color:var(--muted);font-size:12px">${f}</td>
         <td style="font-size:13px">${proj[f] || '—'}</td></tr>`
      ).join('');

      // Reset table headers to TCM format
      document.querySelector('#ts-table thead tr').innerHTML = `
        <th>TSID</th><th>Description</th>
        <th style="text-align:center">Total</th>
        <th style="text-align:center">Pass</th>
        <th style="text-align:center">Fail</th>
        <th style="text-align:center">In‑Prog</th>
        <th style="text-align:center">Block</th>`;

      const tbody = document.getElementById('ts-tbody');
      const ts_order = d.ts_order || [];
      if (!ts_order.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="color:var(--muted);padding:16px">No TCM data</td></tr>';
      } else {
        tbody.innerHTML = ts_order.map(tsid => {
          const ts = d.ts_data[tsid];
          const c  = ts.counts;
          const total = Object.values(c).reduce((a,b) => a+b, 0);
          return `<tr>
            <td data-label="TSID" style="font-weight:700;font-size:12px">${tsid}</td>
            <td data-label="Description" style="font-size:12.5px">${ts.desc}</td>
            <td data-label="Total" style="text-align:center;font-weight:700">${total}</td>
            <td data-label="Pass" style="text-align:center">${c.pass ? '<span class="pill pill-pass">'+c.pass+'</span>' : '-'}</td>
            <td data-label="Fail" style="text-align:center">${c.fail ? '<span class="pill pill-fail">'+c.fail+'</span>' : '-'}</td>
            <td data-label="In-Prog" style="text-align:center">${c['in-progress'] ? '<span class="pill pill-ip">'+c['in-progress']+'</span>' : '-'}</td>
            <td data-label="Block" style="text-align:center">${c.block ? '<span class="pill pill-blk">'+c.block+'</span>' : '-'}</td>
          </tr>`;
        }).join('');
      }
      if (d.chart_available) loadChart();
      const retrofitCard = document.getElementById('retrofit-card');
      if (retrofitCard) retrofitCard.style.display = 'none';
      const eb2 = document.getElementById('ts-export-btn');
      if (ts_order.length) {
        eb2.disabled = false;
        eb2.title = 'Export Scenario Summary เป็น Excel';
        eb2.style.opacity = ''; eb2.style.cursor = 'pointer';
      } else {
        eb2.disabled = true;
        eb2.title = 'ยังไม่มีข้อมูล TCM — Upload Excel ก่อน';
        eb2.style.opacity = '0.45'; eb2.style.cursor = 'not-allowed';
      }
      loadTrend();
    }

    renderOutput(d.output);

  } catch(e) { console.error('loadInfo:', e); }
}

// ── Scenario Summary Export ────────────────────────────────────────────────
function exportScenarioExcel() {
  if (!currentProject) return;
  const envQ = _dashEnvFilter !== 'all' ? `&env=${_dashEnvFilter}` : '';
  window.location.href = `/api/info/export-excel?p=${encodeURIComponent(currentProject)}${envQ}`;
}

// ── Flakiness ──────────────────────────────────────────────────────────────
// Calls /api/flakiness?p=<id> and renders the verdict badge + stats into the
// #flakiness-card block in dashboard.html.
async function loadFlakiness() {
  const card  = document.getElementById('flakiness-card');
  const body  = document.getElementById('flak-body');
  const badge = document.getElementById('flak-verdict');
  if (!card || !body || !badge || !currentProject) return;

  card.style.display = 'block';
  body.innerHTML = '<div style="padding:8px">' + skeletonLinesHTML(3) + '</div>';
  badge.className = 'flak-badge unknown';
  badge.textContent = 'analysing…';

  let d;
  try {
    d = await apiCall(pq('/api/flakiness') + '&window=20');
  } catch (e) {
    body.innerHTML = emptyStateHTML('⚠️', 'โหลด flakiness ไม่ได้', {text: 'ลองใหม่', onclick: 'loadFlakiness()'});
    return;
  }

  badge.className = 'flak-badge ' + (d.verdict || 'unknown');
  badge.textContent = (d.verdict || 'unknown').toUpperCase();

  if (!d.runs_in_window) {
    body.innerHTML = emptyStateHTML('📭', 'ยังไม่มี run history', null, 'รัน tests ก่อน (Stage 5) แล้วจะมีข้อมูลวิเคราะห์');
    return;
  }

  const clusters = (d.fail_clusters || []).map(c =>
    `<span class="flak-cluster" title="${c.start_ts} → ${c.end_ts}">${c.length === 1 ? '1 fail' : c.length + ' in a row'}</span>`
  ).join('') || '<span style="color:var(--muted);font-size:12px">no failure clusters</span>';

  body.innerHTML = `
    <div style="font-size:12px;color:var(--muted);margin-bottom:8px">${d.verdict_reason || ''}</div>
    <div class="flak-row">
      <div class="flak-stat"><div class="n">${d.runs_in_window}</div><div class="l">runs analysed</div></div>
      <div class="flak-stat"><div class="n">${d.failed_runs}</div><div class="l">failed runs</div></div>
      <div class="flak-stat"><div class="n">${d.fail_rate_pct}%</div><div class="l">run fail rate</div></div>
      <div class="flak-stat"><div class="n">${d.pass_rate_tests ?? '—'}${d.pass_rate_tests !== null ? '%' : ''}</div><div class="l">test pass rate</div></div>
      <div class="flak-stat"><div class="n">${d.flaky_runs}</div><div class="l">flaky-flag hits</div></div>
    </div>
    <div style="font-size:12px;color:var(--muted);margin-top:10px">
      <b>Failure clusters:</b> ${clusters}
    </div>
    <div style="font-size:11px;color:var(--muted);margin-top:6px">Last run: ${d.last_ts || '—'} · ${d.last_status || '—'}</div>
  `;
}

// ── Chart ──────────────────────────────────────────────────────────────────
function loadChart() {
  if (!currentProject) return;
  const proj = allProjects.find(p => p.id === currentProject);
  const w = document.getElementById('chart-wrap');
  if (TESTS_ONLY_TYPES.has(proj?.type)) {
    w.innerHTML = `<div class="chart-placeholder">Chart ไม่มีใน ${proj.type} project</div>`;
    return;
  }
  const img = new Image();
  img.onload  = () => { w.innerHTML = ''; w.appendChild(img); img.style.width = '100%'; };
  img.onerror = () => { w.innerHTML = '<div class="chart-placeholder">Chart not available.<br>Run <b>Generate Report</b> first.</div>'; };
  img.src = pq('/api/chart') + '&t=' + Date.now();
}

// ── Screenshots ────────────────────────────────────────────────────────────
let _allShotFiles = [];

function loadScreenshots() {
  if (!currentProject) return;
  fetch(pq('/api/screenshots/list')).then(r => r.json()).then(files => {
    _allShotFiles = files;
    const search = document.getElementById('shot-search');
    if (search) search.value = '';
    renderShots(files);
  });
}

function openLightbox(src, label) {
  document.getElementById('lb-img').src = src;
  document.getElementById('lb-label').textContent = label;
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox() {
  document.getElementById('lightbox').classList.remove('open');
  document.getElementById('lb-img').src = '';
}

// ── Escape key — close any open modal or lightbox ──────────────────────────
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (document.getElementById('cmd-palette-overlay').style.display === 'flex') { closeCmdPalette(); return; }
  if (document.getElementById('shortcut-help-overlay').style.display === 'flex') { closeShortcutHelp(); return; }
  if (document.getElementById('lightbox').classList.contains('open')) { closeLightbox(); return; }
  if (document.getElementById('bug-modal').style.display !== 'none') { closeBugModal(); return; }
  if (document.getElementById('edit-modal').style.display !== 'none') { closeEditModal(); return; }
  _closeNotifPanel();
});

// ══════════════════════════════════════════════════════════════════════════════
// #14 Mobile — hamburger sidebar toggle
// ══════════════════════════════════════════════════════════════════════════════
function toggleSidebar() {
  const sb  = document.getElementById('sidebar');
  const ov  = document.getElementById('sb-overlay');
  const open = sb.classList.toggle('sb-open');
  ov.style.display = open ? 'block' : 'none';
}

// ══════════════════════════════════════════════════════════════════════════════
// #11 Keyboard Shortcuts
// ══════════════════════════════════════════════════════════════════════════════
let _kbG = false, _kbGTimer = null;
document.addEventListener('keydown', e => {
  const tag = e.target.tagName;
  if (['INPUT','TEXTAREA','SELECT'].includes(tag)) return;
  if (e.key === 'Escape') return;

  // ⌘K / Ctrl+K → Command Palette
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); openCmdPalette(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  // ? → shortcut help
  if (e.key === '?') { showShortcutHelp(); return; }

  // R → refresh
  if (e.key === 'r' || e.key === 'R') { refreshCurrent(); showToast('Refreshed', 'ok', 1500); return; }

  // G-sequence navigation
  if (e.key === 'g' || e.key === 'G') {
    _kbG = true;
    clearTimeout(_kbGTimer);
    _kbGTimer = setTimeout(() => { _kbG = false; }, 600);
    return;
  }
  if (_kbG) {
    _kbG = false; clearTimeout(_kbGTimer);
    const map = {d:'dashboard',D:'dashboard',p:'pipeline',P:'pipeline',b:'bugs',B:'bugs',
                 r:'release',R:'release',s:'screenshots',S:'screenshots',j:'projects',J:'projects',
                 h:'chart',H:'chart'};
    if (map[e.key]) { showSection(map[e.key]); e.preventDefault(); }
  }
});

function showShortcutHelp() {
  document.getElementById('shortcut-help-overlay').style.display = 'flex';
}
function closeShortcutHelp() {
  document.getElementById('shortcut-help-overlay').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════════════════
// #12 Command Palette
// ══════════════════════════════════════════════════════════════════════════════
let _cpIdx = 0;

const _cpStaticCmds = [
  // ── Navigation ─────────────────────────────────────────────
  {icon:'🏠', label:'Dashboard',         desc:'Go to Dashboard',            action:()=>showSection('dashboard')},
  {icon:'⚙️', label:'Pipeline',          desc:'Go to Run Pipeline',         action:()=>showSection('pipeline')},
  {icon:'🚦', label:'Release Readiness', desc:'Release gate criteria',      action:()=>showSection('release')},
  {icon:'🐛', label:'Bug Tracker',       desc:'Go to Bug Tracker',          action:()=>showSection('bugs')},
  {icon:'📷', label:'Screenshots',       desc:'Go to Screenshots',          action:()=>showSection('screenshots')},
  {icon:'📅', label:'Schedule',          desc:'Go to Schedule Runner',      action:()=>showSection('schedule')},
  {icon:'🗂️', label:'Projects',          desc:'Project list + add/edit',    action:()=>showSection('projects')},
  {icon:'📊', label:'All Projects Summary', desc:'Cross-project stats',     action:()=>showSection('summary')},
  {icon:'🩺', label:'System Check',      desc:'Run system health check',    action:()=>{showSection('syscheck');runSystemCheck()}},
  {icon:'📖', label:'User Guide',        desc:'Go to User Guide',           action:()=>showSection('guide')},
  {icon:'ℹ️', label:'About / Settings',  desc:'Branding, Email, etc.',      action:()=>showSection('about')},
  // ── Actions ────────────────────────────────────────────────
  {icon:'▶',  label:'Run Tests',         desc:'Run Tests (current project)',action:()=>runTestsWithTag()},
  {icon:'➕', label:'Add Project',       desc:'Register a new project',     action:()=>{showSection('projects');setTimeout(()=>{const f=document.getElementById('add-form-wrap');if(f){f.style.display='block';window.scrollTo({top:0,behavior:'smooth'});}},80);}},
  {icon:'🔎', label:'Discover Projects', desc:'Scan for unregistered folders', action:()=>{showSection('projects');setTimeout(discoverProjects,80);}},
  {icon:'🐛', label:'Add Bug',           desc:'Open Bug form',              action:()=>{showSection('bugs');setTimeout(openBugModal,80);}},
  {icon:'📤', label:'Send Report',       desc:'Send Word report via email', action:()=>{showSection('pipeline');setTimeout(()=>{const el=document.getElementById('send-report-row');if(el)el.scrollIntoView({behavior:'smooth'});},200);}},
  // ── UI ─────────────────────────────────────────────────────
  {icon:'🔄', label:'Refresh',           desc:'Refresh current view',       action:()=>refreshCurrent()},
  {icon:'🌙', label:'Toggle Dark Mode',  desc:'Light ↔ Dark theme',         action:()=>toggleDark()},
  {icon:'⌨️', label:'Keyboard Shortcuts',desc:'Show shortcut help',         action:()=>showShortcutHelp()},
];

function _cpAllCmds() {
  const cmds = [..._cpStaticCmds];
  (allProjects || []).forEach(p => {
    const dot = {active:'🟢',planning:'🟡',paused:'⚪'}[p.phase]||'🟢';
    cmds.push({icon:dot, label:`Switch → ${p.name}`, desc:`Switch active project`, action:()=>switchProject(p.id)});
  });
  return cmds;
}

function _cpFilter(q) {
  const cmds = _cpAllCmds();
  const filtered = q.trim()
    ? cmds.filter(c => (c.label+c.desc).toLowerCase().includes(q.trim().toLowerCase()))
    : cmds;
  _cpIdx = 0;
  _cpRender(filtered, q.trim());
}

function _cpRender(cmds, q='') {
  const box = document.getElementById('cmd-palette-results');
  if (!cmds.length) {
    box.innerHTML = emptyStateHTML('🔍', 'ไม่พบคำสั่ง', null, `ลองค้นหาอื่น — พิมพ์ "project", "bug", "schedule", ...`);
    return;
  }
  box.innerHTML = cmds.map((c,i) =>
    `<div class="cp-result-item ${i===_cpIdx?'cp-active':''}" onclick="_cpExec(${i})" data-idx="${i}"
      onmouseover="_cpIdx=${i};_cpHighlight()">
      <span class="cp-icon">${c.icon}</span>
      <div><div class="cp-label">${c.label}</div><div class="cp-desc">${c.desc}</div></div>
    </div>`
  ).join('');
  box._cmds = cmds;
}

function _cpHighlight() {
  document.querySelectorAll('.cp-result-item').forEach((el,i) => {
    el.classList.toggle('cp-active', i === _cpIdx);
  });
}

function _cpKey(e) {
  const box  = document.getElementById('cmd-palette-results');
  const cmds = box._cmds || [];
  if (e.key === 'ArrowDown') { e.preventDefault(); _cpIdx = Math.min(_cpIdx+1, cmds.length-1); _cpHighlight(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); _cpIdx = Math.max(_cpIdx-1, 0); _cpHighlight(); }
  else if (e.key === 'Enter') { _cpExec(_cpIdx); }
}

function _cpExec(idx) {
  const box  = document.getElementById('cmd-palette-results');
  const cmds = box._cmds || _cpAllCmds();
  closeCmdPalette();
  if (cmds[idx]) cmds[idx].action();
}

function openCmdPalette() {
  const overlay = document.getElementById('cmd-palette-overlay');
  overlay.style.display = 'flex';
  const inp = document.getElementById('cmd-palette-input');
  inp.value = '';
  _cpFilter('');
  setTimeout(() => inp.focus(), 50);
}

function closeCmdPalette() {
  document.getElementById('cmd-palette-overlay').style.display = 'none';
}

// ══════════════════════════════════════════════════════════════════════════════
// #13 Notification Center
// ══════════════════════════════════════════════════════════════════════════════
let _notifHistory = JSON.parse(localStorage.getItem('fp_notifs') || '[]');
let _notifPanelOpen = false;

function _addNotif(icon, text, sub='') {
  const entry = {icon, text, sub, ts: new Date().toLocaleTimeString('th-TH', {hour:'2-digit',minute:'2-digit'})};
  _notifHistory.unshift(entry);
  if (_notifHistory.length > 50) _notifHistory.pop();
  localStorage.setItem('fp_notifs', JSON.stringify(_notifHistory));
  _updateNotifBadge();
  if (_notifPanelOpen) _renderNotifList();
}

let _notifUnread = 0;
function _updateNotifBadge() {
  _notifUnread++;
  const b = document.getElementById('notif-badge');
  b.textContent  = _notifUnread > 9 ? '9+' : _notifUnread;
  b.style.display = 'block';
}

function _renderNotifList() {
  const el = document.getElementById('notif-list');
  if (!_notifHistory.length) {
    el.innerHTML = emptyStateHTML('📭', 'ยังไม่มี notification', null, 'จะขึ้นเมื่อมี scheduled run เสร็จ');
    return;
  }
  el.innerHTML = _notifHistory.map(n =>
    `<div style="padding:10px 16px;border-bottom:1px solid var(--border);display:flex;gap:10px;align-items:flex-start">
      <span style="font-size:18px;flex-shrink:0">${n.icon}</span>
      <div style="flex:1;min-width:0">
        <div style="font-size:12.5px;font-weight:600;color:var(--text)">${n.text}</div>
        ${n.sub ? `<div style="font-size:11px;color:var(--muted)">${n.sub}</div>` : ''}
      </div>
      <span style="font-size:10.5px;color:var(--muted);white-space:nowrap">${n.ts}</span>
    </div>`
  ).join('');
}

function toggleNotifPanel() {
  const panel = document.getElementById('notif-panel');
  _notifPanelOpen = !_notifPanelOpen;
  panel.style.display = _notifPanelOpen ? 'flex' : 'none';
  if (_notifPanelOpen) {
    _renderNotifList();
    _notifUnread = 0;
    document.getElementById('notif-badge').style.display = 'none';
  }
}

function _closeNotifPanel() {
  const panel = document.getElementById('notif-panel');
  panel.style.display = 'none';
  _notifPanelOpen = false;
}

function clearNotifs() {
  _notifHistory = [];
  localStorage.removeItem('fp_notifs');
  _renderNotifList();
}

// ── Input ──────────────────────────────────────────────────────────────────
function loadInput() {
  if (!currentProject) return;
  fetch(pq('/api/input/list')).then(r => r.json()).then(files => {
    const el = document.getElementById('input-file-list');
    if (!files.length) {
      el.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:12px">No files in <code>input/</code>.</div>';
      return;
    }
    const extIcon = e => e==='.xlsx'?'📊':e==='.json'?'📋':e==='.docx'?'📄':'📎';
    el.innerHTML = files.map(f => `
      <div class="file-card" style="margin-bottom:8px">
        <div class="file-ico">${extIcon(f.ext)}</div>
        <div class="file-info" style="flex:1">
          <h3>${f.name}</h3>
          <p>${f.size_kb} KB · Last saved: ${f.modified}</p>
          <span class="badge badge-ok">${f.ext.replace('.','').toUpperCase()}</span>
        </div>
        ${f.ext==='.xlsx' ? `<a href="${pq('/api/input/download')}" download><button class="btn btn-download btn-sm">⬇️ Download</button></a>` : ''}
      </div>`).join('');
  });
}

async function copyFolderPath(which) {
  if (!currentProject) { showToast('กรุณาเลือก Project ก่อน', 'err'); return; }
  try {
    const r = await apiCall(pq(`/api/path/${which}`), { silent: true });
    await navigator.clipboard.writeText(r.path);
    showToast(`📋 คัดลอก path แล้ว — วางใน Win+R / Explorer address bar:\n${r.path}`, 'ok');
  } catch {
    showToast('คัดลอก path ไม่สำเร็จ', 'err');
  }
}

const openInputFolder       = () => copyFolderPath('input');
const openOutputFolder      = () => copyFolderPath('output');
const openScreenshotsFolder = () => copyFolderPath('screenshots');
const openFolder            = copyFolderPath;

// ── Output ─────────────────────────────────────────────────────────────────
function loadOutput(info) {
  if (!info) {
    if (!currentProject) return;
    fetch(pq('/api/info')).then(r => r.json()).then(d => renderOutput(d.output));
  } else {
    renderOutput(info);
  }
}

function renderOutput(info) {
  const el = document.getElementById('output-file-card');
  if (!info) {
    el.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:12px">No output file yet. Run <b>Generate Report</b> first.</div>';
    return;
  }
  el.innerHTML = `<div class="file-card">
    <div class="file-ico">📄</div>
    <div class="file-info" style="flex:1">
      <h3>${info.name}</h3>
      <p>${info.size_kb} KB · Last saved: ${info.modified}</p>
      <span class="badge badge-ok">Word Document</span>
    </div>
    <a href="${pq('/api/output/download')}" download>
      <button class="btn btn-download">⬇️ Download</button>
    </a>
  </div>`;
}

// ── Projects grid ──────────────────────────────────────────────────────────
function _catBadge(cat) {
  if (!cat) return '';
  const cls = {cr:'cat-cr', incident:'cat-incident', new:'cat-new', regression:'cat-regression'}[cat.toLowerCase()] || 'cat-other';
  return `<span class="cat-badge ${cls}">${cat}</span>`;
}

function _renderProjCard(p) {
  const color = p.color || '#2E75B6';
  const phase = p.phase || 'active';
  const phaseBadge = phase === 'active' ? '' :
    phase === 'planning'
      ? `<span style="background:rgba(255,255,255,.22);color:#fff;font-size:10px;font-weight:700;padding:1px 7px;border-radius:8px;margin-left:6px">🗂 Planning</span>`
      : `<span style="background:rgba(255,255,255,.22);color:#fff;font-size:10px;font-weight:700;padding:1px 7px;border-radius:8px;margin-left:6px">⏸ Paused</span>`;
  return `<div class="proj-card ${p.id === currentProject ? 'current' : ''}" onclick="switchProject('${p.id}')">
    <div class="proj-card-header" style="background:${color}">
      <div class="proj-card-name">${p.name}${phaseBadge}${_catBadge(p.category)}</div>
      <div class="proj-card-type">${
        p.type === 'manual-testing'  ? '📋 Manual Testing' :
        p.type === 'playwright-only' ? '🎭 Playwright Only' :
        p.type === 'pytest-only'     ? '🐍 Pytest Only' :
                                       '🔄 Full Pipeline'
      }</div>
    </div>
    <div class="proj-card-body">
      <div class="proj-stat">📊 Excel TCM: ${p.has_xlsx ? '<span style="color:#2E7D32;font-weight:700">✓</span>' : '<span style="color:var(--muted)">—</span>'}</div>
      <div class="proj-stat">📄 Word Report: ${p.has_docx ? '<span style="color:#2E7D32;font-weight:700">✓</span>' : '<span style="color:var(--muted)">—</span>'}</div>
      <div class="proj-stat">🖼️ Screenshots: <b>${p.screenshot_count}</b></div>
      <div class="proj-stat">🕐 Last run: ${p.last_run ? `<b>${p.last_run}</b>` : '<span style="color:var(--muted)">—</span>'}</div>
      <div class="proj-stat" style="margin-top:4px;color:${p.exists ? '#2E7D32' : '#C62828'}">
        ${p.exists ? '● Path OK' : '● Path not found'}
      </div>
      ${p.figma_url ? `<div class="proj-stat" style="margin-top:4px"><a href="${p.figma_url}" target="_blank" onclick="event.stopPropagation()" style="color:#7B1FA2;font-size:11.5px;text-decoration:none;display:flex;align-items:center;gap:3px"><span style="background:#F3E5F5;border-radius:4px;padding:1px 6px;font-weight:600">🎨 Figma</span></a></div>` : ''}
      <div style="font-size:11px;color:var(--muted);margin-top:6px;word-break:break-all;display:flex;align-items:flex-start;gap:4px">
        <span style="flex:1">${p.path}</span>
        <button title="Copy path" style="flex-shrink:0;background:none;border:none;cursor:pointer;padding:0 2px;color:var(--muted);font-size:12px;line-height:1" onclick="event.stopPropagation();navigator.clipboard.writeText('${p.path.replace(/'/g,"\\'")}').then(()=>showToast('Copied!','ok'))">⧉</button>
      </div>
    </div>
    <div class="proj-card-actions">
      <button class="btn btn-sm btn-primary" onclick="event.stopPropagation();switchProject('${p.id}');showSection('dashboard')">Open</button>
      <button class="btn btn-sm" style="background:#FFF8E1;color:#F57F17;border:1px solid #FFE082" onclick="event.stopPropagation();openEditModal('${p.id}','${p.name.replace(/'/g,"\\'")}','${p.color||'#2E75B6'}','${p.type||'full-pipeline'}')">✏️ Edit</button>
      <button class="btn btn-sm btn-danger" onclick="event.stopPropagation();removeProject('${p.id}','${p.name}')">Remove</button>
    </div>
  </div>`;
}

function _applyProjFilter() {
  const company  = document.getElementById('pf-company')?.value  || 'all';
  const category = document.getElementById('pf-category')?.value || 'all';
  const q        = (document.getElementById('pf-search')?.value  || '').toLowerCase();
  const el       = document.getElementById('proj-grid-container');

  const filtered = allProjects.filter(p => {
    if (company  !== 'all' && (p.company  || '') !== company)  return false;
    if (category !== 'all' && (p.category || '') !== category) return false;
    if (q && !p.name.toLowerCase().includes(q) && !p.id.toLowerCase().includes(q)) return false;
    return true;
  });

  if (!filtered.length) {
    el.innerHTML = `<div style="grid-column:1/-1;text-align:center;padding:32px;color:var(--muted);font-size:13px">ไม่พบ project ที่ตรงกับ filter</div>`;
    return;
  }

  // Group by company
  const groups = {};
  filtered.forEach(p => {
    const key = p.company || 'Other';
    (groups[key] = groups[key] || []).push(p);
  });

  const hasGroups = Object.keys(groups).some(k => k !== 'Other') || Object.keys(groups).length > 1;
  let html = '';
  Object.entries(groups).forEach(([company, projects]) => {
    if (hasGroups) html += `<div class="proj-group-header">🏢 ${company} <span style="font-size:11px;font-weight:400;color:var(--muted)">(${projects.length})</span></div>`;
    html += projects.map(_renderProjCard).join('');
  });
  el.innerHTML = html;
}

async function loadProjectsGrid() {
  allProjects = await apiCall('/api/projects');
  const el = document.getElementById('proj-grid-container');
  if (!allProjects.length) {
    el.innerHTML = `<div style="text-align:center;padding:48px 20px;color:var(--muted)">
      <div style="font-size:36px;margin-bottom:12px">📂</div>
      <div style="font-size:14px;margin-bottom:18px">ยังไม่มี project — เพิ่มหรือ scan หาอัตโนมัติ</div>
      <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
        <button class="btn btn-success btn-sm" onclick="toggleAddForm()">+ Add Project</button>
        <button class="btn btn-sm" style="background:#E3F2FD;color:#1565C0;border:1px solid #90CAF9" onclick="toggleAddForm();discoverProjects()">🔍 Auto Discover</button>
      </div>
    </div>`;
    return;
  }

  // Build filter options from actual data
  const companies  = [...new Set(allProjects.map(p => p.company).filter(Boolean))].sort();
  const categories = [...new Set(allProjects.map(p => p.category).filter(Boolean))].sort();

  // Inject filter bar once (check by id to avoid duplicates on reload)
  const card = el.closest('.card');
  if (card && !card.querySelector('.proj-filter-bar')) {
    const bar = document.createElement('div');
    bar.className = 'proj-filter-bar';
    bar.innerHTML = `
      <select id="pf-company" onchange="_applyProjFilter()">
        <option value="all">🏢 All Companies</option>
        ${companies.map(c => `<option value="${c}">${c}</option>`).join('')}
      </select>
      <select id="pf-category" onchange="_applyProjFilter()">
        <option value="all">📁 All Categories</option>
        ${categories.map(c => `<option value="${c}">${c}</option>`).join('')}
      </select>
      <input id="pf-search" type="text" placeholder="🔍 ค้นหา project..." oninput="_applyProjFilter()" style="min-width:160px">
    `;
    card.insertBefore(bar, el);
  }

  _applyProjFilter();

  // Update switcher dropdown
  const sel = document.getElementById('project-select');
  sel.innerHTML = allProjects.map(p => {
    const dot = {active:'🟢', planning:'🟡', paused:'⚪'}[p.phase] || '🟢';
    return `<option value="${p.id}" ${p.id === currentProject ? 'selected' : ''}>${dot} ${p.name}</option>`;
  }).join('');
}

// ── Add / Remove project ───────────────────────────────────────────────────
function resetAddForm() {
  document.getElementById('f-id').value       = '';
  document.getElementById('f-name').value     = '';
  document.getElementById('f-path').value     = '';
  document.getElementById('f-type').value     = 'full-pipeline';
  document.getElementById('f-color').value    = '#2E75B6';
  document.getElementById('f-company').value  = '';
  document.getElementById('f-category').value = '';
  document.getElementById('f-create-folder').checked   = false;
  document.getElementById('f-has-playwright').checked  = true;
  document.getElementById('f-git-url').value   = '';
  document.getElementById('f-base-url').value  = '';
  document.getElementById('f-figma-url').value = '';
  document.querySelector('input[name="f-init-mode"][value="scaffold"]').checked = true;
  document.getElementById('init-options').style.display    = 'none';
  document.getElementById('git-url-field').style.display   = 'none';
  document.getElementById('base-url-field').style.display  = 'flex';
  const dl = document.querySelector('.discover-list'); if (dl) dl.innerHTML = '';
  // populate company suggestions from existing projects
  const ds = document.getElementById('company-suggestions');
  if (ds) {
    const companies = [...new Set(allProjects.map(p => p.company).filter(Boolean))].sort();
    ds.innerHTML = companies.map(c => `<option value="${c}">`).join('');
  }
}

function toggleAddForm() {
  const f = document.getElementById('add-proj-form');
  const opening = f.style.display === 'none';
  f.style.display = opening ? 'block' : 'none';
  if (opening) resetAddForm();
}

function toggleInitOptions() {
  const checked = document.getElementById('f-create-folder').checked;
  document.getElementById('init-options').style.display = checked ? 'block' : 'none';
}

function onInitModeChange() {
  const mode = document.querySelector('input[name="f-init-mode"]:checked').value;
  document.getElementById('git-url-field').style.display = mode === 'git' ? 'block' : 'none';
}

function toggleBaseUrlField() {
  const hasPw = document.getElementById('f-has-playwright').checked;
  document.getElementById('base-url-field').style.display = hasPw ? 'flex' : 'none';
}

function slugify(str) {
  return str.toLowerCase().trim()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
}

document.addEventListener('DOMContentLoaded', () => {
  const nameEl = document.getElementById('f-name');
  const idEl   = document.getElementById('f-id');
  if (nameEl && idEl) {
    nameEl.addEventListener('input', () => {
      if (!idEl.dataset.userEdited) idEl.value = slugify(nameEl.value);
    });
    idEl.addEventListener('input', () => {
      idEl.dataset.userEdited = idEl.value ? '1' : '';
    });
  }
});

async function addProject() {
  const id             = document.getElementById('f-id').value.trim();
  const name           = document.getElementById('f-name').value.trim();
  const path           = document.getElementById('f-path').value.trim();
  const type           = document.getElementById('f-type').value;
  const color          = document.getElementById('f-color').value;
  const create_folder  = document.getElementById('f-create-folder').checked;
  const has_playwright = document.getElementById('f-has-playwright').checked;
  const base_url       = document.getElementById('f-base-url').value.trim();
  const git_url        = document.getElementById('f-git-url').value.trim();
  const figma_url      = document.getElementById('f-figma-url').value.trim();
  const init_mode      = create_folder
    ? document.querySelector('input[name="f-init-mode"]:checked').value
    : 'none';

  if (!id || !name || !path) { showToast('กรุณากรอก ID, Name และ Path', 'err'); return; }
  if (!/^[a-zA-Z0-9_-]+$/.test(id)) { showToast('ID ต้องเป็นตัวอักษร ตัวเลข - หรือ _ เท่านั้น', 'err'); return; }
  if (init_mode === 'git' && !git_url) { showToast('กรุณาระบุ Git URL', 'err'); return; }

  const btn = document.querySelector('#add-proj-form .btn-success');
  const origText = btn.textContent;
  btn.disabled = true;
  btn.textContent = init_mode === 'git' ? '⏳ Cloning...' : '⏳ Creating...';

  try {
    const r = await fetch('/api/projects/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id, name, path, type, color, create_folder, has_playwright, base_url, git_url, init_mode, figma_url,
        company: document.getElementById('f-company').value.trim(),
        category: document.getElementById('f-category').value,
      }),
    });
    const d = await r.json();
    if (d.error) { showToast('Error: ' + d.error, 'err'); return; }

    let msg = 'Project added ✓';
    if (d.used_git)      msg = `Project added ✓ — cloned from Git`;
    else if (d.used_scaffold) msg = `Project added ✓ — scaffold copied`;

    if ((d.used_git || d.used_scaffold) && d.has_playwright) {
      msg += ' · อย่าลืมรัน npm install ก่อนใช้ Playwright';
      showToast(msg, 'ok', 6000);
    } else {
      showToast(msg);
    }

    toggleAddForm();
    await loadProjectsGrid();
    switchProject(id);
  } finally {
    btn.disabled = false;
    btn.textContent = origText;
  }
}

async function removeProject(id, name) {
  const ok = await showConfirm({
    icon: '📁',
    title: `นำ "${name}" ออกจาก Hub?`,
    desc: 'ไม่ลบไฟล์จริง — เพียงเอาออกจาก config<br><span style="font-size:12px;color:var(--muted)">เพิ่มกลับได้ภายหลังด้วย Auto Discover</span>',
    okLabel: 'นำออก', okColor: '#E53935', danger: true,
  });
  if (!ok) return;
  await apiCall('/api/projects/remove', {body: {id}});
  if (currentProject === id) {
    currentProject = '';
    localStorage.removeItem('fp_project');
  }
  await loadProjectsGrid();
  if (!currentProject && allProjects.length) {
    switchProject(allProjects[0].id);
  }
}

async function discoverProjects() {
  const el = document.querySelector('.discover-list');
  if (!el) return;
  el.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(3) + '</div>';
  const found = await apiCall('/api/projects/discover');
  if (!found.length) {
    el.innerHTML = emptyStateHTML('🔎', 'ไม่พบ project ใหม่', null, 'register ครบแล้ว หรือยังไม่มี folder ใหม่ใน C:\\Automation');
    return;
  }
  el.innerHTML = '<div class="card-title" style="margin:10px 0 8px">พบ project ที่ยังไม่ได้ register:</div>' +
    found.map(f => {
      const safeId = f.path.replace(/[\\/\s]/g,'-').toLowerCase();
      return `<div class="discover-item">
        <div style="flex:1">
          <div class="discover-name">${f.name}</div>
          <div class="discover-path">${f.path} · <span style="color:var(--primary)">${f.type}</span></div>
        </div>
        <button class="btn btn-sm btn-success" onclick="quickAdd('${safeId}','${f.name}','${f.path}','${f.type}')">+ Add</button>
      </div>`;
    }).join('');
}

async function quickAdd(id, name, path, type) {
  const r = await fetch('/api/projects/add', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id, name, path, type, color: '#2E75B6'}),
  });
  const d = await r.json();
  if (d.error) { showToast(d.error, 'err'); return; }
  await discoverProjects();
  await loadProjectsGrid();
}

// ── Run pipeline (SSE) ─────────────────────────────────────────────────────
let activeSource = null;
let activeRunProject = null;  // track which project the run belongs to

function runTestsWithTag(_btn = null) {
  const tag = (document.getElementById('test-tag-select')?.value || '').trim();
  const env = (document.getElementById('test-env-select')?.value || '').trim();
  _lastTestEnv = env;
  const label = tag ? `Stage 5: Run Tests (@${tag})` : 'Stage 5: Run All Tests';
  let qs = '';
  if (tag) qs += `&tag=${encodeURIComponent(tag)}`;
  if (env) qs += `&env=${encodeURIComponent(env)}`;
  runStep('tests', label, qs, _btn);
}

function runStep(step, label, extraQS = '', _btn = null) {
  if (!currentProject) { showToast('กรุณาเลือก Project ก่อน', 'err'); return; }
  if (activeSource) { activeSource.close(); activeSource = null; }
  activeRunProject = currentProject;
  if (_btn) { _btn._origHTML = _btn.innerHTML; _btn.innerHTML = '<span class="spin" style="vertical-align:middle;margin-right:5px"></span>Running…'; }

  showSection('pipeline');

  const logBox      = document.getElementById('log-box');
  const badge       = document.getElementById('run-badge');
  const bar         = document.getElementById('progress-bar');
  const title       = document.getElementById('log-title');
  const cancelBtn   = document.getElementById('cancel-run-btn');
  const postFail    = document.getElementById('post-fail-actions');
  const rerunCount  = document.getElementById('rerun-count');

  logBox.innerHTML = '';
  title.textContent = `📋 Log — ${label}`;
  badge.textContent = 'Running...';
  badge.className   = 'badge badge-running';
  bar.style.width   = '5%';
  if (cancelBtn) cancelBtn.style.display = step === 'tests' ? '' : 'none';
  if (postFail)  postFail.style.display = 'none';

  const counter     = document.getElementById('test-counter');
  const tcPass      = document.getElementById('tc-pass');
  const tcFail      = document.getElementById('tc-fail');
  const tcTotal     = document.getElementById('tc-total');
  const tcFlaky     = document.getElementById('tc-flaky');
  const tcFlakyWrap = document.getElementById('tc-flaky-wrap');
  let passCount = 0, failCount = 0, flakyCount = 0;

  if (step === 'tests') {
    counter.classList.add('visible');
    tcPass.textContent = '0'; tcFail.textContent = '0'; tcTotal.textContent = '—';
    tcFlaky.textContent = '0'; tcFlakyWrap.style.display = 'none';
    fetch(pq('/api/info')).then(r => r.json()).then(d => { tcTotal.textContent = d.total_tc || '—'; });
    _failedTests = [];   // reset on each run
  } else {
    counter.classList.remove('visible');
  }

  document.querySelectorAll('.btn').forEach(b => b.disabled = true);
  if (cancelBtn) cancelBtn.disabled = false;  // Cancel must stay clickable

  const es = new EventSource(pq(`/api/run/${step}`) + extraQS);
  activeSource = es;

  let progress = 5;
  const ticker = setInterval(() => {
    if (progress < 90) { progress += 3; bar.style.width = progress + '%'; }
  }, 400);

  es.onmessage = e => {
    const msg  = JSON.parse(e.data);
    const line = document.createElement('div');
    line.className  = 'log-line l-' + (msg.type || 'info');
    line.textContent = msg.line;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;

    if (step === 'tests') {
      // ── Real-time counters (best-effort, character-dependent) ───────
      if (msg.type === 'warn' && /flaky/i.test(msg.line)) {
        flakyCount++; tcFlaky.textContent = flakyCount; tcFlakyWrap.style.display = '';
      } else if (/[✓✔]/.test(msg.line)) {
        passCount++; tcPass.textContent = passCount;
      } else if (/[✗✘×✕]/.test(msg.line) && /spec\.ts/.test(msg.line)) {
        failCount++; tcFail.textContent = failCount;
        _failedTests.push(_parseTestName(msg.line));
      }
      // ── Playwright summary lines — authoritative, always plain ASCII ─
      // e.g. "  75 passed (2m 30s)"  or  "  2 failed"
      const mPass = msg.line.match(/^\s*(\d+)\s+passed/);
      const mFail = msg.line.match(/^\s*(\d+)\s+failed/);
      if (mPass) { passCount = parseInt(mPass[1]); tcPass.textContent = passCount; }
      if (mFail) { failCount = parseInt(mFail[1]); tcFail.textContent = failCount; }
    }

    if (msg.done) {
      clearInterval(ticker);
      const cancelled = msg.returncode === -9 || msg.line === 'Tests cancelled.';
      bar.style.width   = msg.returncode === 0 ? '100%' : '60%';
      badge.textContent = msg.returncode === 0 ? 'Done ✓' : (cancelled ? 'Cancelled' : 'Error ✗');
      badge.className   = 'badge ' + (msg.returncode === 0 ? 'badge-ok' : 'badge-running');
      if (cancelBtn) cancelBtn.style.display = 'none';
      const ranForProject = activeRunProject;   // snapshot before clearing
      es.close(); activeSource = null; activeRunProject = null;
      document.querySelectorAll('.btn').forEach(b => b.disabled = false);
      if (_btn && _btn._origHTML) { _btn.innerHTML = _btn._origHTML; _btn._origHTML = null; }
      // Only reload if user is still on the same project that ran
      if (currentProject !== ranForProject) return;
      updateDownloadLinks();
      if (['generate','all'].includes(step))                 setTimeout(() => { loadInfo(); loadChart(); loadPipelineStatus(); }, 600);
      if (['inject','all'].includes(step))                   setTimeout(() => { loadOutput(); loadPipelineStatus(); }, 600);
      if (['ba','spec','tests','add-charts'].includes(step)) setTimeout(() => loadPipelineStatus(), 600);
      if (step === 'tests') {
        const _loggedTag = (document.getElementById('test-tag-select')?.value || '').trim();
        fetch('/api/run/log', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({project_id: currentProject, step:'tests', pass: passCount, fail: failCount, flaky: flakyCount, rc: msg.returncode, tag: _loggedTag, env: _lastTestEnv || 'uat'})
        });
        setTimeout(loadRunHistory, 800);
        const projName = allProjects.find(p=>p.id===ranForProject)?.name || ranForProject;
        if (msg.returncode === 0) {
          _addNotif('✅', `Tests Passed — ${projName}`, `${passCount} passed · ${_loggedTag ? '@'+_loggedTag : 'All'}`);
        } else if (!cancelled) {
          _addNotif('❌', `Tests Failed — ${projName}`, `${failCount} failed · ${passCount} passed`);
        }
        if (!cancelled && msg.returncode !== 0 && failCount > 0) {
          _bugDetectFailCount = failCount;
          if (rerunCount) rerunCount.textContent = _failedTests.length;
          if (postFail)   { postFail.style.display = 'flex'; }
          _showBugDetectPanel();
        }
      } else if (msg.returncode === 0) {
        const projName = allProjects.find(p=>p.id===ranForProject)?.name || ranForProject;
        _addNotif('✅', `${label} — Done`, projName);
      }
    }
  };
  es.onerror = () => {
    clearInterval(ticker);
    badge.textContent = 'Error'; badge.className = 'badge badge-running';
    if (cancelBtn) cancelBtn.style.display = 'none';
    document.querySelectorAll('.btn').forEach(b => b.disabled = false);
    if (_btn && _btn._origHTML) { _btn.innerHTML = _btn._origHTML; _btn._origHTML = null; }
    es.close(); activeSource = null;
  };
}

function cancelRun() {
  if (activeSource) { activeSource.close(); activeSource = null; }
  fetch(pq('/api/run/cancel'), {method: 'POST'})
    .then(r => r.json())
    .then(d => {
      const badge = document.getElementById('run-badge');
      badge.textContent = 'Cancelled'; badge.className = 'badge badge-running';
      document.getElementById('cancel-run-btn').style.display = 'none';
      document.querySelectorAll('.btn').forEach(b => b.disabled = false);
      showToast('Test run cancelled.', 'warn');
    });
}

function rerunFailed() {
  if (!_failedTests.length) { showToast('ไม่มี failed tests', 'err'); return; }
  // Build grep pattern: join test names with | (Playwright supports regex)
  const pattern = _failedTests.map(n => {
    // Use the part after › as the test title for grep
    const parts = n.split(' › ');
    return parts[parts.length - 1].replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }).join('|');
  const env = (document.getElementById('test-env-select')?.value || '').trim();
  let qs = `&grep=${encodeURIComponent(pattern)}`;
  if (env) qs += `&env=${encodeURIComponent(env)}`;
  document.getElementById('post-fail-actions').style.display = 'none';
  runStep('tests', `Re-run ${_failedTests.length} Failed Test(s)`, qs);
}

function debugTest(idx) {
  const name = _failedTests[idx];
  if (!name) return;
  // Extract spec filename from "TS_01_foo.spec.ts › ..."
  const specMatch = name.match(/([\w.-]+\.spec\.ts)/);
  const spec = specMatch ? specMatch[1] : name;
  dismissBugDetect();
  showSection('pipeline');
  const logBox = document.getElementById('log-box');
  const badge  = document.getElementById('run-badge');
  const bar    = document.getElementById('progress-bar');
  const title  = document.getElementById('log-title');
  logBox.innerHTML = '';
  title.textContent = `🔍 Debug — ${spec}`;
  badge.textContent = 'Debugging...'; badge.className = 'badge badge-running';
  bar.style.width = '5%';
  document.querySelectorAll('.btn').forEach(b => b.disabled = true);
  let progress = 5;
  const ticker = setInterval(() => { if (progress < 85) { progress += 2; bar.style.width = progress + '%'; } }, 600);
  const es = new EventSource(pq(`/api/run/debug`) + `&spec=${encodeURIComponent(spec)}`);
  activeSource = es;
  es.onmessage = e => {
    const msg = JSON.parse(e.data);
    const line = document.createElement('div');
    line.className = 'log-line l-' + (msg.type || 'info');
    line.textContent = msg.line;
    logBox.appendChild(line);
    logBox.scrollTop = logBox.scrollHeight;
    if (msg.done) {
      clearInterval(ticker);
      bar.style.width = '100%';
      badge.textContent = 'Debug Done'; badge.className = 'badge badge-ok';
      es.close(); activeSource = null;
      document.querySelectorAll('.btn').forEach(b => b.disabled = false);
    }
  };
  es.onerror = () => {
    clearInterval(ticker);
    badge.textContent = 'Error'; badge.className = 'badge badge-running';
    document.querySelectorAll('.btn').forEach(b => b.disabled = false);
    es.close(); activeSource = null;
  };
}

function clearLog() {
  document.getElementById('log-box').innerHTML = '<div class="log-line l-muted">Log cleared.</div>';
  document.getElementById('progress-bar').style.width = '0';
  document.getElementById('test-counter').classList.remove('visible');
  const pf = document.getElementById('post-fail-actions');
  if (pf) pf.style.display = 'none';
}

// ── Pipeline status ────────────────────────────────────────────────────────
function setDot(id, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = 'tl-dot ' + (ok ? 'ok' : 'warn');
  el.title = ok ? '✓ พร้อมแล้ว' : '⚠ ยังไม่ครบ / ต้องดำเนินการ';
}
function fileTag(name) { return `<span class="tag">📄 ${name}</span>`; }

async function loadPipelineStatus() {
  if (!currentProject) return;
  try {
    const r = await fetch(pq('/api/status'));
    const d = await r.json();

    setDot('s1-dot', d.s1.ok);
    document.getElementById('s1-files').innerHTML = d.s1.files.length
      ? d.s1.files.map(fileTag).join('')
      : '<span style="color:var(--muted)">ไม่พบไฟล์ใน requirements/ หรือ figma/</span>';
    // Figma URL hint — show link if project has figma_url set
    const _figmaHint = document.getElementById('s1-figma-hint');
    if (_figmaHint) {
      const _proj = allProjects.find(p => p.id === currentProject);
      if (_proj?.figma_url) {
        _figmaHint.innerHTML = `🎨 <b>Figma:</b> <a href="${_proj.figma_url}" target="_blank" style="color:#7B1FA2">${_proj.figma_url}</a> &nbsp;<span style="color:var(--muted);font-size:11px">— BA Agent จะดึง design data อัตโนมัติผ่าน Figma MCP</span>`;
        _figmaHint.style.display = 'block';
      } else {
        _figmaHint.style.display = 'none';
      }
    }

    setDot('s2-dot', d.s2.ok);
    const noKey = !d.has_api_key;
    document.getElementById('s2-api-warning').style.display = noKey ? 'block' : 'none';
    document.getElementById('s2-run-btn').disabled = false;  // always enabled — fallback to claude CLI
    let s2html = d.s2.file
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s2.file}</span>`
      : '<span style="color:var(--muted)">ยังไม่มี Excel TCM</span>';
    if (d.s2.ba_outputs?.length)
      s2html += ` &nbsp;<span style="color:var(--muted);font-size:11px">${d.s2.ba_outputs[0]}</span>`;
    document.getElementById('s2-files').innerHTML = s2html;

    setDot('s3-dot', d.s3.ok);
    document.getElementById('s3-files').innerHTML = d.s3.file
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s3.file}</span>`
      : '<span style="color:var(--muted)">ยังไม่มี Excel — รัน Stage 2 ก่อน</span>';

    setDot('s4-dot', d.s4.ok);
    const staleTag = d.s4.stale ? ' &nbsp;<span style="color:#E65100;font-size:11px;font-weight:700">⚠️ เก่ากว่า Excel</span>' : '';
    document.getElementById('s4-files').innerHTML = d.s4.ok
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s4.count} spec file(s)</span>${staleTag} &nbsp;` + d.s4.files.map(fileTag).join('')
      : (d.ba_outputs?.length
          ? `<span style="color:var(--muted)">BA output พร้อม: ${d.ba_outputs[0]}</span>`
          : '<span style="color:var(--muted)">ยังไม่มี spec files — รัน Stage 2 ก่อน</span>');

    // P3: Spec staleness warning in Stage 5
    const staleWarn = document.getElementById('s5-stale-warn');
    if (staleWarn) staleWarn.style.display = d.s4.stale ? 'block' : 'none';

    setDot('s5-dot', d.s5.ok);
    document.getElementById('s5-files').innerHTML = d.s5.ok
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s5.count} screenshot(s)</span>`
      : '<span style="color:var(--muted)">ยังไม่มี screenshots — รัน tests ก่อน</span>';

    document.getElementById('s6-files').innerHTML = d.s6.file
      ? `<span style="color:var(--muted);font-size:12px">ไฟล์: <b>${d.s6.file}</b></span>`
      : '';
    // P4: Load Excel validation for Stage 6
    refreshValidate();

    setDot('s7-dot', d.s7.ok);
    document.getElementById('s7-files').innerHTML = d.s7.file
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s7.file}</span>`
      : '<span style="color:var(--muted)">ยังไม่มี Word report</span>';

    setDot('s8-dot', d.s8.ok);
    document.getElementById('s8-files').innerHTML = d.s8.file
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s8.file}</span>`
      : '<span style="color:var(--muted)">ยังไม่มี Word report — รัน Stage 7 ก่อน</span>';

    setDot('s9-dot', d.s9.ok);
    document.getElementById('s9-files').innerHTML = d.s9.file
      ? `<span style="color:#2E7D32;font-weight:700">✓ ${d.s9.file}</span> &nbsp;<span style="color:var(--muted);font-size:11.5px">พร้อม download</span>`
      : '<span style="color:var(--muted)">ยังไม่มีไฟล์ — รัน Stage 7+8 ก่อน</span>';

    _updatePipelineProgress(d);

  } catch(e) { console.error('loadPipelineStatus:', e); }
}

function _updatePipelineProgress(d) {
  const strip = document.getElementById('pipeline-progress-strip');
  if (!strip) return;
  const proj = allProjects.find(p => p.id === currentProject);
  const type = proj?.type || 'full-pipeline';
  const stageMap = {
    'full-pipeline':   [{id:'s1',n:1},{id:'s2',n:2},{id:'s3',n:3},{id:'s4',n:4},{id:'s5',n:5},{id:'s6',n:6},{id:'s7',n:7},{id:'s8',n:8},{id:'s9',n:9}],
    'manual-testing':  [{id:'s1',n:1},{id:'s2',n:2},{id:'s3',n:3},{id:'s7',n:7},{id:'s8',n:8},{id:'s9',n:9}],
    'playwright-only': [{id:'s5',n:5}],
    'pytest-only':     [{id:'s5',n:5},{id:'s7',n:7},{id:'s8',n:8},{id:'s9',n:9}],
  };
  const stages = stageMap[type] || stageMap['full-pipeline'];
  const okCount = stages.filter(s => d[s.id]?.ok).length;
  const total   = stages.length;
  const pct     = total > 0 ? Math.round(okCount / total * 100) : 0;
  strip.style.display = '';
  document.getElementById('pipeline-progress-label').textContent = `${okCount} / ${total} stages ready`;
  document.getElementById('pipeline-progress-pct').textContent   = `${pct}%`;
  document.getElementById('pipeline-progress-bar').style.width   = pct + '%';
  const dotColor = s => d[s.id]?.ok ? '#43A047' : '#CDD5DC';
  document.getElementById('pipeline-stage-dots').innerHTML = stages.map(s =>
    `<span title="Stage ${s.n}" style="width:20px;height:7px;border-radius:3px;background:${dotColor(s)};display:inline-block"></span>`
  ).join('');
}

// ── Pipeline type-awareness ────────────────────────────────────────────────
function markPipelineStages() {
  // Tag each .tl-item with data-stage= from its number badge
  document.querySelectorAll('.tl-num').forEach(el => {
    const num = parseInt(el.textContent.trim());
    const item = el.closest('.tl-item');
    if (item && num) item.dataset.stage = num;
  });
  // Tag connectors sequentially (connector N sits after stage N)
  document.querySelectorAll('.tl-connector').forEach((c, i) => {
    c.dataset.afterStage = i + 1;
  });
}

function updatePipelineForType() {
  const proj = allProjects.find(p => p.id === currentProject);
  const projType        = proj?.type || 'full-pipeline';
  const isPlaywrightOnly  = projType === 'playwright-only';
  const isPytestOnly      = projType === 'pytest-only';
  const isManualTesting   = projType === 'manual-testing';
  const isTestsOnly       = isPlaywrightOnly || isPytestOnly;

  // Stages permanently hidden per type
  const typeHidden = isPlaywrightOnly  ? new Set([0,1,2,3,4,6,7,8,9])
                   : isPytestOnly      ? new Set([0,1,2,3,4,6])
                   : isManualTesting   ? new Set([0, 4, 5])
                   : new Set();

  // Pipeline mode hidden (only for full-pipeline)
  const mode       = localStorage.getItem('fp_pipeline_mode') || 'full';
  const modeHidden = (isTestsOnly || isManualTesting) ? new Set() : new Set(PIPELINE_MODES[mode] || []);
  const hidden     = new Set([...typeHidden, ...modeHidden]);

  document.querySelectorAll('.tl-item[data-stage]').forEach(el => {
    el.style.display = hidden.has(parseInt(el.dataset.stage)) ? 'none' : '';
  });
  document.querySelectorAll('.tl-connector[data-after-stage]').forEach(el => {
    el.style.display = hidden.has(parseInt(el.dataset.afterStage)) ? 'none' : '';
  });

  document.getElementById('playwright-only-banner').style.display  = isPlaywrightOnly ? 'block' : 'none';
  const pytestBanner = document.getElementById('pytest-only-banner');
  if (pytestBanner) pytestBanner.style.display = isPytestOnly ? 'block' : 'none';
  document.getElementById('manual-testing-banner').style.display   = isManualTesting  ? 'block' : 'none';

  const modeBar = document.getElementById('pipeline-mode-bar');
  if (modeBar) modeBar.style.display = (isTestsOnly || isManualTesting) ? 'none' : '';

  // Stage 6: show full controls in full/report mode, show only reminder in manual mode
  const isManual = mode === 'manual';
  document.querySelectorAll('.s6-auto-only').forEach(el => {
    el.style.display = isManual ? 'none' : '';
  });
  document.querySelectorAll('.s6-manual-only').forEach(el => {
    el.style.display = isManual ? '' : 'none';
  });
}

// ── Edit project modal ─────────────────────────────────────────────────────
function _editPhaseHint() {
  const phase = document.getElementById('edit-phase').value;
  const hint  = document.getElementById('edit-phase-hint');
  const cfg = {
    planning: { bg:'#E3F2FD', color:'#1565C0', text:'Release Gate จะแสดงสถานะ "อยู่ใน Planning" — criteria จะไม่ fail' },
    active:   { bg:'#E8F5E9', color:'#2E7D32', text:'Release Gate ทำงานปกติ — ตรวจสอบ criteria ทั้งหมด' },
    paused:   { bg:'#FFF8E1', color:'#E65100', text:'Release Gate จะแสดงสถานะ "หยุดพัฒนา" — criteria จะไม่ fail' },
  };
  const c = cfg[phase] || cfg.active;
  hint.style.cssText = `background:${c.bg};color:${c.color};font-size:11px;margin-top:5px;padding:6px 10px;border-radius:6px;display:block`;
  hint.textContent = c.text;
}

function openEditModal(id, name, color, type) {
  const proj = allProjects.find(p => p.id === id);
  document.getElementById('edit-id').value        = id;
  document.getElementById('edit-name').value      = name;
  document.getElementById('edit-color').value     = color;
  document.getElementById('edit-type').value      = type;
  document.getElementById('edit-phase').value     = proj?.phase || 'active';
  document.getElementById('edit-figma-url').value = proj?.figma_url || '';
  _editPhaseHint();
  document.getElementById('edit-modal').style.display = 'flex';
}

function closeEditModal() {
  document.getElementById('edit-modal').style.display = 'none';
}

async function saveEditProject() {
  const id        = document.getElementById('edit-id').value;
  const name      = document.getElementById('edit-name').value.trim();
  const color     = document.getElementById('edit-color').value;
  const type      = document.getElementById('edit-type').value;
  const phase     = document.getElementById('edit-phase').value;
  const figma_url = document.getElementById('edit-figma-url').value.trim();

  if (!name) { showToast('กรุณากรอก Name', 'err'); return; }

  const r = await fetch('/api/projects/update', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id, name, color, type, phase, figma_url}),
  });
  const d = await r.json();
  if (d.error) { showToast('Error: ' + d.error, 'err'); return; }
  showToast('Project updated ✓');
  closeEditModal();
  await loadProjectsGrid();
  // If editing current project, refresh topbar + pipeline type + release
  if (id === currentProject) {
    updateTopbarProj();
    updatePipelineForType();
    loadRelease();
  }
}

// Close modal on backdrop click
document.getElementById('edit-modal').addEventListener('click', function(e) {
  if (e.target === this) closeEditModal();
});

// ── Bug Reports ────────────────────────────────────────────────────────────
let _bugDetectFailCount = 0;
let _failedTests = [];   // {name, line} collected from SSE
let _lastTestEnv  = '';
let _dashEnvFilter = 'all';   // dashboard: All | uat | prod
let _rhEnvFilter   = 'all';   // pipeline run history: All | uat | prod
let _allBugs = [];
let _bugSort  = { col: 'created_at', dir: 'desc' };

const SEV_COLORS = {
  Critical: '#C62828', High: '#E65100', Medium: '#F57F17', Low: '#2E7D32'
};
const STATUS_COLORS = {
  Open: '#B71C1C', 'In Progress': '#E65100', Resolved: '#2E7D32', Closed: '#607D8B'
};

function _updateBugBadge(openCount) {
  const badge = document.getElementById('nav-bug-badge');
  const dash  = document.getElementById('s-open-bugs');
  if (openCount > 0) {
    badge.textContent = openCount; badge.style.display = '';
  } else {
    badge.style.display = 'none';
  }
  if (dash) dash.textContent = openCount > 0 ? openCount : '0';
}

async function loadBugBadge() {
  if (!currentProject) return;
  try {
    const r = await fetch(pq('/api/bugs'));
    const bugs = await r.json();
    const open = bugs.filter(b => b.status === 'Open').length;
    _updateBugBadge(open);
  } catch(_) {}
}

let _bugView = 'table';

function setBugView(v) {
  _bugView = v;
  const tBtn = document.getElementById('bug-view-table-btn');
  const kBtn = document.getElementById('bug-view-kanban-btn');
  if (tBtn) { tBtn.style.background = v==='table' ? 'var(--primary)' : 'transparent'; tBtn.style.color = v==='table' ? '#fff' : 'var(--muted)'; }
  if (kBtn) { kBtn.style.background = v==='kanban' ? 'var(--primary)' : 'transparent'; kBtn.style.color = v==='kanban' ? '#fff' : 'var(--muted)'; }
  loadBugs();
}

function _renderBugKanban(bugs) {
  const SEV_COLOR = {Critical:'#C62828', High:'#E65100', Medium:'#F57F17', Low:'#2E7D32'};
  const SEV_BG    = {Critical:'#FFEBEE', High:'#FFF3E0', Medium:'#FFFDE7', Low:'#E8F5E9'};
  const cols = ['Open','In Progress','Resolved','Closed'];
  const colColor = {'Open':'#B71C1C','In Progress':'#E65100','Resolved':'#2E7D32','Closed':'#607D8B'};
  return `<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;align-items:start">` +
    cols.map(status => {
      const colBugs = bugs.filter(b => (b.status||'Open') === status);
      const cards = colBugs.length
        ? colBugs.map(b => {
            const age = b.created_at ? Math.floor((Date.now()-new Date(b.created_at))/(1000*86400)) : null;
            return `<div style="background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px;margin-bottom:8px;cursor:pointer;border-left:3px solid ${SEV_COLOR[b.severity]||'#ccc'}"
              onclick="openBugModal(${JSON.stringify(b).replace(/"/g,'&quot;')})">
              <div style="font-size:11px;font-weight:700;color:${SEV_COLOR[b.severity]||'#888'};margin-bottom:4px;background:${SEV_BG[b.severity]||'#f5f5f5'};display:inline-block;padding:1px 7px;border-radius:10px">${b.severity||'—'}</div>
              <div style="font-size:12.5px;font-weight:600;color:var(--text);margin:4px 0;line-height:1.4">${b.title||b.id}</div>
              <div style="font-size:11px;color:var(--muted)">${b.id}${age !== null ? ` · ${age}d` : ''}</div>
            </div>`;
          }).join('')
        : `<div style="color:var(--muted);font-size:12px;padding:12px;text-align:center;border:1.5px dashed var(--border);border-radius:8px">ไม่มี</div>`;
      return `<div>
        <div style="font-size:12px;font-weight:700;color:${colColor[status]};padding:6px 0 8px;border-bottom:2px solid ${colColor[status]};margin-bottom:10px">
          ${status} <span style="font-size:11px;background:var(--bg);padding:1px 7px;border-radius:10px;margin-left:4px;font-weight:600;color:var(--muted)">${colBugs.length}</span>
        </div>
        ${cards}
      </div>`;
    }).join('') + '</div>';
}

async function loadBugs() {
  if (!currentProject) return;
  const proj = allProjects.find(p => p.id === currentProject);
  document.getElementById('bug-project-name').textContent = proj?.name || currentProject;

  const r = await fetch(pq('/api/bugs'));
  _allBugs = await r.json();

  // Stats
  const open     = _allBugs.filter(b => b.status === 'Open').length;
  const critical = _allBugs.filter(b => b.severity === 'Critical').length;
  const high     = _allBugs.filter(b => b.severity === 'High').length;
  const resolved = _allBugs.filter(b => b.status === 'Resolved' || b.status === 'Closed').length;
  document.getElementById('bug-stat-open').textContent     = open;
  document.getElementById('bug-stat-critical').textContent = critical;
  document.getElementById('bug-stat-high').textContent     = high;
  document.getElementById('bug-stat-resolved').textContent = resolved;
  document.getElementById('bug-stat-total').textContent    = _allBugs.length;
  if (_bmVisible) renderBugMetrics();
  _updateBugBadge(open);

  // Filter
  const filterStatus = document.getElementById('bug-filter-status').value;
  const filterSev    = document.getElementById('bug-filter-sev').value;
  let bugs = _allBugs;
  if (filterStatus) bugs = bugs.filter(b => b.status === filterStatus);
  if (filterSev)    bugs = bugs.filter(b => b.severity === filterSev);

  const wrap = document.getElementById('bug-list-wrap');
  if (!bugs.length) {
    const isFiltered = filterStatus || filterSev;
    wrap.innerHTML = `<div style="text-align:center;padding:40px 20px;color:var(--muted)">
      <div style="font-size:30px;margin-bottom:10px">${isFiltered ? '🔍' : '🐛'}</div>
      <div style="font-size:13px;margin-bottom:14px">${isFiltered ? 'ไม่พบ bug ที่ตรงกับ filter' : 'ยังไม่มี bug — เยี่ยมมาก!'}</div>
      ${isFiltered ? '' : '<button class="btn btn-danger btn-sm" onclick="openBugModal()">+ Log Bug</button>'}
    </div>`;
    return;
  }

  // Kanban view
  if (_bugView === 'kanban') {
    wrap.innerHTML = _renderBugKanban(bugs);
    return;
  }

  // Sort
  const SEV_ORDER = {Critical:0, High:1, Medium:2, Low:3};
  bugs = [...bugs].sort((a,b) => {
    let av, bv;
    if (_bugSort.col === 'severity') { av = SEV_ORDER[a.severity]??9; bv = SEV_ORDER[b.severity]??9; }
    else if (_bugSort.col === 'status') { av = a.status||''; bv = b.status||''; }
    else { av = a.created_at||''; bv = b.created_at||''; }
    if (av < bv) return _bugSort.dir === 'asc' ? -1 :  1;
    if (av > bv) return _bugSort.dir === 'asc' ?  1 : -1;
    return 0;
  });

  function _sortTh(col, label) {
    const active = _bugSort.col === col;
    const arrow  = active ? (_bugSort.dir === 'asc' ? ' ↑' : ' ↓') : '';
    return `<th style="cursor:pointer;user-select:none;white-space:nowrap${active?';color:var(--primary)':''}"
      onclick="setBugSort('${col}')">${label}${arrow}</th>`;
  }

  wrap.innerHTML = `
  <table class="ts-table" id="bug-table">
    <thead><tr>
      <th style="width:24px"></th>
      <th>ID</th><th>Title</th>
      ${_sortTh('severity','Severity')}
      <th>Status</th>
      <th>Environment</th>
      ${_sortTh('created_at','Created')}
      <th style="min-width:130px">Actions</th>
    </tr></thead>
    <tbody>
    ${bugs.map(b => {
      const stepsHtml = (b.steps||[]).length
        ? (b.steps||[]).map((s,i)=>`<div style="margin-bottom:3px"><span style="color:var(--muted);margin-right:6px">${i+1}.</span>${_esc(s)}</div>`).join('')
        : '<span style="color:var(--muted)">—</span>';
      const evidenceHtml = (b.evidence||[]).length
        ? (b.evidence||[]).map(e=>`<code style="display:block;font-size:11.5px;background:#F7FAFF;padding:2px 6px;border-radius:4px;margin-bottom:3px">${_esc(e)}</code>`).join('')
        : '<span style="color:var(--muted)">—</span>';
      const statusOpts = ['Open','In Progress','Resolved','Closed']
        .map(s=>`<option value="${s}"${b.status===s?' selected':''}>${s}</option>`).join('');
      return `
      <tr class="bug-row" data-id="${b.id}" onclick="toggleBugDetail('${b.id}')" style="cursor:pointer">
        <td style="color:var(--muted);font-size:11px;padding-right:0" id="bug-chevron-${b.id}">▶</td>
        <td><code style="font-size:11.5px">${b.id}</code></td>
        <td style="max-width:240px">
          <div style="font-weight:600;font-size:13px">${_esc(b.title)}</div>
          ${b.related_task ? `<div style="font-size:11px;color:var(--muted);margin-top:2px">Task: ${_esc(b.related_task)}</div>` : ''}
        </td>
        <td><span style="background:${SEV_COLORS[b.severity]||'#757575'};color:#fff;padding:2px 9px;border-radius:10px;font-size:11.5px;font-weight:600">${b.severity}</span></td>
        <td onclick="event.stopPropagation()">
          <select onchange="changeStatusInline('${b.id}',this.value)"
            style="font-size:11.5px;padding:3px 7px;border-radius:7px;border:2px solid ${STATUS_COLORS[b.status]||'#607D8B'};background:${STATUS_COLORS[b.status]||'#607D8B'}20;color:var(--text);font-weight:600;cursor:pointer">
            ${statusOpts}
          </select>
        </td>
        <td style="font-size:12.5px">${_esc(b.environment)||'—'}</td>
        <td style="font-size:11.5px;color:var(--muted)">${b.created_at?.slice(0,10)||'—'}</td>
        <td onclick="event.stopPropagation()">
          <div style="display:flex;gap:5px;flex-wrap:wrap">
            <button class="btn btn-sm" style="padding:4px 9px;font-size:11px;background:#E3F2FD;color:#1565C0;border:1px solid #90CAF9" onclick="openBugModal('${b.id}')">Edit</button>
            <button class="btn btn-sm" style="padding:4px 9px;font-size:11px;background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7" onclick="openAssignModal('${b.id}','${_esc(b.title).replace(/'/g,"\\'")}')">👤 Assign</button>
            <button class="btn btn-sm" style="padding:4px 9px;font-size:11px;background:#F3E5F5;color:#7B1FA2;border:1px solid #CE93D8" onclick="duplicateBug('${b.id}')">Dup</button>
            <button class="btn btn-sm" style="padding:4px 9px;font-size:11px;background:#FFEBEE;color:#B71C1C;border:1px solid #FFCDD2" onclick="deleteBug('${b.id}')">Del</button>
          </div>
        </td>
      </tr>
      <tr id="bug-detail-${b.id}" style="display:none">
        <td colspan="8" style="padding:0;border-bottom:2px solid var(--border)">
          <div style="background:#F7FBFF;padding:16px 20px 14px 36px;display:grid;grid-template-columns:1fr 1fr;gap:14px 24px">
            <div>
              <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Steps to Reproduce</div>
              <div style="font-size:12.5px;line-height:1.7">${stepsHtml}</div>
            </div>
            <div>
              <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Evidence</div>
              <div style="font-size:12.5px">${evidenceHtml}</div>
            </div>
            <div>
              <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Expected Behavior</div>
              <div style="font-size:12.5px;line-height:1.6">${_esc(b.expected)||'<span style="color:var(--muted)">—</span>'}</div>
            </div>
            <div>
              <div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Actual Behavior</div>
              <div style="font-size:12.5px;line-height:1.6">${_esc(b.actual)||'<span style="color:var(--muted)">—</span>'}</div>
            </div>
            ${b.related_spec ? `<div style="grid-column:1/-1"><div style="font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">Spec / Link</div><code style="font-size:12px">${_esc(b.related_spec)}</code></div>` : ''}
            ${b.updated_at ? `<div style="grid-column:1/-1;font-size:11px;color:var(--muted)">Updated: ${b.updated_at?.slice(0,16)?.replace('T',' ')}</div>` : ''}
          </div>
        </td>
      </tr>`;
    }).join('')}
    </tbody>
  </table>`;
}

function toggleBugDetail(bugId) {
  const detail   = document.getElementById(`bug-detail-${bugId}`);
  const chevron  = document.getElementById(`bug-chevron-${bugId}`);
  const isOpen   = detail.style.display !== 'none';
  detail.style.display  = isOpen ? 'none' : 'table-row';
  chevron.textContent   = isOpen ? '▶' : '▼';
  chevron.style.color   = isOpen ? 'var(--muted)' : 'var(--primary)';
}

function setBugSort(col) {
  if (_bugSort.col === col) {
    _bugSort.dir = _bugSort.dir === 'asc' ? 'desc' : 'asc';
  } else {
    _bugSort.col = col;
    _bugSort.dir = col === 'created_at' ? 'desc' : 'asc';
  }
  loadBugs();
}

async function changeStatusInline(bugId, newStatus) {
  const r = await fetch('/api/bugs/update', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({project_id: currentProject, id: bugId, status: newStatus})
  });
  const d = await r.json();
  if (d.error) { showToast('Error: ' + d.error, 'err'); return; }
  showToast(`${bugId} → ${newStatus} ✓`);
  loadBugs();
}

function duplicateBug(bugId) {
  const src = _allBugs.find(b => b.id === bugId);
  if (!src) return;
  // Open modal pre-filled with cloned data, but cleared ID → will create new
  openBugModal();  // opens blank first
  document.getElementById('bug-title').value       = `[Copy] ${src.title}`;
  document.getElementById('bug-severity').value    = src.severity || 'Medium';
  document.getElementById('bug-status').value      = 'Open';
  document.getElementById('bug-environment').value = src.environment || '';
  document.getElementById('bug-steps').value       = (src.steps||[]).join('\n');
  document.getElementById('bug-expected').value    = src.expected || '';
  document.getElementById('bug-actual').value      = src.actual || '';
  document.getElementById('bug-evidence').value    = (src.evidence||[]).join('\n');
  document.getElementById('bug-task').value        = src.related_task || '';
  document.getElementById('bug-spec').value        = src.related_spec || '';
}

function _esc(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function openBugModal(bugId) {
  const modal = document.getElementById('bug-modal');
  const badge = document.getElementById('bug-modal-id-badge');

  if (bugId) {
    const b = _allBugs.find(x => x.id === bugId);
    if (!b) return;
    document.getElementById('bug-modal-title').textContent = 'Edit Bug Report';
    document.getElementById('bug-edit-id').value  = b.id;
    badge.textContent = b.id; badge.style.display = '';
    document.getElementById('bug-title').value       = b.title || '';
    document.getElementById('bug-severity').value    = b.severity || 'Medium';
    document.getElementById('bug-status').value      = b.status || 'Open';
    document.getElementById('bug-environment').value = b.environment || '';
    document.getElementById('bug-steps').value       = (b.steps||[]).join('\n');
    document.getElementById('bug-expected').value    = b.expected || '';
    document.getElementById('bug-actual').value      = b.actual || '';
    document.getElementById('bug-evidence').value    = (b.evidence||[]).join('\n');
    document.getElementById('bug-task').value        = b.related_task || '';
    document.getElementById('bug-spec').value        = b.related_spec || '';
  } else {
    document.getElementById('bug-modal-title').textContent = 'Log Bug Report';
    document.getElementById('bug-edit-id').value = '';
    badge.style.display = 'none';
    document.getElementById('bug-title').value       = '';
    document.getElementById('bug-severity').value    = 'Medium';
    document.getElementById('bug-status').value      = 'Open';
    document.getElementById('bug-environment').value = '';
    document.getElementById('bug-steps').value       = '';
    document.getElementById('bug-expected').value    = '';
    document.getElementById('bug-actual').value      = '';
    document.getElementById('bug-evidence').value    = '';
    document.getElementById('bug-task').value        = '';
    document.getElementById('bug-spec').value        = '';
  }
  modal.style.display = 'flex';
}

function closeBugModal() {
  document.getElementById('bug-modal').style.display = 'none';
  document.getElementById('shot-picker-grid').style.display = 'none';
  document.getElementById('shot-picker-hint').textContent = '';
}

async function saveBug() {
  const title = document.getElementById('bug-title').value.trim();
  if (!title) { showToast('กรุณากรอก Title', 'err'); return; }

  const editId  = document.getElementById('bug-edit-id').value.trim();
  const stepsRaw = document.getElementById('bug-steps').value.trim();
  const evRaw    = document.getElementById('bug-evidence').value.trim();

  const payload = {
    project_id:   currentProject,
    title,
    severity:     document.getElementById('bug-severity').value,
    status:       document.getElementById('bug-status').value,
    environment:  document.getElementById('bug-environment').value.trim(),
    steps:        stepsRaw ? stepsRaw.split('\n').map(s=>s.trim()).filter(Boolean) : [],
    expected:     document.getElementById('bug-expected').value.trim(),
    actual:       document.getElementById('bug-actual').value.trim(),
    evidence:     evRaw ? evRaw.split('\n').map(s=>s.trim()).filter(Boolean) : [],
    related_task: document.getElementById('bug-task').value.trim(),
    related_spec: document.getElementById('bug-spec').value.trim(),
  };

  const url = editId ? '/api/bugs/update' : '/api/bugs/add';
  if (editId) payload.id = editId;

  const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
  const d = await r.json();
  if (d.error) { showToast('Error: ' + d.error, 'err'); return; }
  showToast(editId ? `Bug ${d.bug.id} updated ✓` : `Bug ${d.bug.id} logged ✓`);
  _addNotif(editId?'✏️':'🐛', editId?`Bug ${d.bug.id} updated`:`Bug ${d.bug.id} logged`, `${payload.severity||''} · ${payload.title||''}`);
  closeBugModal();
  loadBugs();
}

async function deleteBug(bugId) {
  const ok = await showConfirm({
    icon: '🐛',
    title: `ลบ Bug ${bugId}?`,
    desc: 'ลบรายการนี้ออกจาก Bug Tracker<br><span style="font-size:12px;color:var(--muted)">ไม่สามารถย้อนกลับได้</span>',
    okLabel: 'ลบ Bug', okColor: '#E53935', danger: true,
  });
  if (!ok) return;
  const r = await fetch('/api/bugs/delete', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({project_id: currentProject, id: bugId})
  });
  const d = await r.json();
  if (d.error) { showToast('Error: ' + d.error, 'err'); return; }
  showToast(`${bugId} deleted`);
  loadBugs();
}

async function exportBugsExcel() {
  if (!currentProject) { showToast('กรุณาเลือก Project ก่อน', 'err'); return; }
  showToast('Generating Excel...', 'info');
  window.location.href = pq('/api/bugs/export');
}

async function loadShotPicker() {
  const grid = document.getElementById('shot-picker-grid');
  const hint = document.getElementById('shot-picker-hint');
  const isVisible = grid.style.display === 'flex';
  if (isVisible) { grid.style.display = 'none'; hint.textContent = ''; return; }

  hint.textContent = 'Loading...';
  try {
    const r = await fetch(pq('/api/screenshots/list'));
    const d = await r.json();
    const shots = d.screenshots || d || [];
    if (!shots.length) { hint.textContent = 'No screenshots found'; return; }
    hint.textContent = `${shots.length} screenshot(s) — click to add`;
    grid.innerHTML = shots.map(s => {
      const name = s.name || s.filename || s.path?.split('/').pop() || '?';
      const src  = `/api/screenshots/${encodeURIComponent(s.path || s.filename || name)}?p=${encodeURIComponent(currentProject)}`;
      return `<div title="${_esc(name)}" onclick="addShotToEvidence('${_esc(s.path||s.filename||name)}')"
        style="cursor:pointer;border:2px solid var(--border);border-radius:6px;overflow:hidden;width:80px;flex-shrink:0;transition:border-color .15s"
        onmouseover="this.style.borderColor='var(--primary)'" onmouseout="this.style.borderColor='var(--border)'">
        <img src="${src}" style="width:80px;height:55px;object-fit:cover;display:block">
        <div style="font-size:10px;padding:2px 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted)">${_esc(name)}</div>
      </div>`;
    }).join('');
    grid.style.display = 'flex';
  } catch(e) { hint.textContent = 'Error loading screenshots'; }
}

function addShotToEvidence(path) {
  const ta = document.getElementById('bug-evidence');
  const cur = ta.value.trim();
  ta.value = cur ? cur + '\n' + path : path;
  // Visual feedback
  const hint = document.getElementById('shot-picker-hint');
  hint.textContent = `Added: ${path.split('/').pop()}`;
  setTimeout(() => { hint.textContent = ''; }, 2000);
}

function _parseTestName(line) {
  // Extract readable test name from Playwright list-reporter line
  // e.g. "  ✘  1) [chromium] › tests/e2e/login.spec.ts:10:5 › Login › should fail"
  // → "login.spec.ts › Login › should fail"
  const parts = line.split('›');
  if (parts.length >= 2) {
    // grab spec filename + remaining test name parts
    const specPart = parts[0].match(/[\w.-]+\.spec\.ts/);
    const testParts = parts.slice(specPart ? 1 : 1).map(s => s.trim()).filter(Boolean);
    const spec = specPart ? specPart[0] : '';
    return [spec, ...testParts].filter(Boolean).join(' › ');
  }
  // fallback: strip leading symbols/whitespace
  return line.replace(/^[\s✗✘×✕\d\)\[]+/, '').trim();
}

function _showBugDetectPanel() {
  const list = document.getElementById('bug-detect-list');
  const msg  = document.getElementById('bug-detect-msg');
  msg.textContent = `${_failedTests.length} failure(s) found — select which to log as bug reports`;

  list.innerHTML = _failedTests.map((name, i) => `
    <div style="display:flex;align-items:flex-start;gap:6px;padding:7px 10px;background:rgba(255,255,255,.05);border-radius:8px;border:1px solid rgba(255,255,255,.08)">
      <label style="display:flex;align-items:flex-start;gap:8px;cursor:pointer;flex:1;min-width:0">
        <input type="checkbox" class="bug-detect-cb" data-idx="${i}" checked style="margin-top:2px;accent-color:#ef5350;flex-shrink:0">
        <span style="font-size:12px;line-height:1.5;word-break:break-word">${_esc(name)}</span>
      </label>
      <button onclick="debugTest(${i})" title="Debug this test via /debug-test" style="flex-shrink:0;background:#1565C0;color:#fff;border:none;border-radius:5px;padding:2px 8px;font-size:11px;cursor:pointer;white-space:nowrap">🔍 Debug</button>
    </div>`).join('');

  document.getElementById('bug-detect-banner').style.display = 'block';
}

async function logSelectedBugs() {
  const checks = document.querySelectorAll('.bug-detect-cb:checked');
  if (!checks.length) { showToast('ยังไม่ได้เลือก test ใด', 'err'); return; }

  let created = 0;
  for (const cb of checks) {
    const name = _failedTests[parseInt(cb.dataset.idx)];
    const payload = {
      project_id:  currentProject,
      title:       name,
      severity:    'High',
      status:      'Open',
      environment: _lastTestEnv || '',
      steps:       [],
      expected:    '',
      actual:      '',
      evidence:    [],
      related_task:'',
      related_spec:'',
    };
    const r = await fetch('/api/bugs/add', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload)
    });
    const d = await r.json();
    if (!d.error) created++;
  }

  dismissBugDetect();
  showToast(`${created} bug(s) logged ✓`, 'ok');
  // Refresh bug tab if open, else just update badge
  const active = document.querySelector('.section.active')?.id?.replace('section-','');
  if (active === 'bugs') loadBugs(); else loadBugBadge();
}

function toggleSelectAllBugs() {
  const cbs = document.querySelectorAll('.bug-detect-cb');
  const allChecked = [...cbs].every(c => c.checked);
  cbs.forEach(c => c.checked = !allChecked);
}

function dismissBugDetect() {
  document.getElementById('bug-detect-banner').style.display = 'none';
}

// Close bug modal on backdrop click
document.getElementById('bug-modal').addEventListener('click', function(e) {
  if (e.target === this) closeBugModal();
});

// ── Auto-refresh dashboard ────────────────────────────────────────────────
let _autoRefreshTimer = null;

function startAutoRefresh() {
  stopAutoRefresh();
  _autoRefreshTimer = setInterval(() => {
    const name = document.querySelector('.section.active')?.id?.replace('section-','');
    if (name === 'dashboard') loadInfo();
  }, 30000); // every 30s
}

function stopAutoRefresh() {
  if (_autoRefreshTimer) { clearInterval(_autoRefreshTimer); _autoRefreshTimer = null; }
}

// ── Screenshot filter ──────────────────────────────────────────────────────
function shotUrl(f) {
  // filepath may include subdirs (playwright-only): "test-results/xxx/shot.png"
  return pq('/api/screenshots/' + (f.filepath || f.name));
}

function renderShots(files) {
  const grid  = document.getElementById('shot-grid');
  const count = document.getElementById('shot-count');
  if (!files.length) {
    grid.innerHTML = `<div style="text-align:center;padding:40px 20px;color:var(--muted)">
      <div style="font-size:32px;margin-bottom:10px">🖼️</div>
      <div style="font-size:13px;margin-bottom:14px">ยังไม่มี screenshots — รัน tests ก่อน</div>
      <button class="btn btn-primary btn-sm" onclick="showSection('pipeline')">→ ไปหน้า Pipeline</button>
    </div>`;
    count.textContent = '';
    return;
  }
  count.textContent = `(${files.length} / ${_allShotFiles.length})`;
  grid.innerHTML = files.map(f => `
    <div class="shot-card" onclick="openLightbox('${shotUrl(f)}','${f.tcid.replace(/'/g,"\\'")}')">
      <img src="${shotUrl(f)}" alt="${f.tcid}" loading="lazy">
      <div class="shot-label" title="${f.tcid}">${f.tcid}</div>
      <div class="shot-meta">${f.size_kb} KB · ${f.modified}</div>
    </div>`).join('');
}

function filterShots(q) {
  const filtered = q ? _allShotFiles.filter(f => f.tcid.toLowerCase().includes(q.toLowerCase())) : _allShotFiles;
  renderShots(filtered);
}

// ── Multi-project Summary ─────────────────────────────────────────────────
let _summaryData = [];

function _applySummaryFilter() {
  const company  = document.getElementById('sf-company')?.value  || 'all';
  const category = document.getElementById('sf-category')?.value || 'all';
  const type     = document.getElementById('sf-type')?.value     || 'all';
  const status   = document.getElementById('sf-status')?.value   || 'all';
  const q        = (document.getElementById('sf-search')?.value  || '').toLowerCase();

  const filtered = _summaryData.filter(p => {
    if (company  !== 'all' && (p.company  || '') !== company)  return false;
    if (category !== 'all' && (p.category || '') !== category) return false;
    if (type     !== 'all' && p.type !== type)                 return false;
    if (status === 'pass'   && !(p.pass > 0))       return false;
    if (status === 'fail'   && !(p.fail > 0))       return false;
    if (status === 'no-tcm' && p.has_xlsx)          return false;
    if (q && !p.name.toLowerCase().includes(q) && !(p.company||'').toLowerCase().includes(q)) return false;
    return true;
  });

  const wrap = document.getElementById('summary-table-wrap');
  const countEl = document.getElementById('summary-count');
  if (countEl) countEl.textContent = `${filtered.length} / ${_summaryData.length} projects`;

  if (!filtered.length) {
    wrap.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:12px;text-align:center">ไม่พบ project ที่ตรงกับ filter</div>';
    return;
  }

  const pill = (val, cls) => val ? `<span class="pill ${cls}">${val}</span>` : '-';
  const typeLabel = t =>
    t === 'manual-testing'  ? '📋 Manual'   :
    t === 'playwright-only' ? '🎭 PW Only'  :
    t === 'pytest-only'     ? '🐍 Pytest'   : '🔄 Full';
  const phaseTag = ph =>
    ph === 'planning' ? '<span style="font-size:10px;background:#E3F2FD;color:#1565C0;padding:1px 6px;border-radius:6px;margin-left:4px">Planning</span>' :
    ph === 'paused'   ? '<span style="font-size:10px;background:#FFF8E1;color:#E65100;padding:1px 6px;border-radius:6px;margin-left:4px">Paused</span>' : '';

  wrap.innerHTML = `<table class="ts-table">
    <thead><tr>
      <th>Project</th>
      <th>Company</th>
      <th>Category</th>
      <th>Type</th>
      <th style="text-align:center">TCs</th>
      <th style="text-align:center">Pass</th>
      <th style="text-align:center">Fail</th>
      <th style="text-align:center">Pass Rate</th>
      <th style="text-align:center">Excel</th>
      <th style="text-align:center">Word</th>
      <th>Last Run</th>
      <th></th>
    </tr></thead>
    <tbody>${filtered.map(p => `<tr>
      <td>
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${p.color};margin-right:6px;vertical-align:middle"></span>
        <b>${p.name}</b>${phaseTag(p.phase)}
        ${!p.exists ? '<span style="font-size:11px;color:#C62828;margin-left:4px">⚠ path not found</span>' : ''}
      </td>
      <td style="font-size:11.5px">${p.company || '<span style="color:var(--muted)">—</span>'}</td>
      <td style="font-size:11.5px">${p.category ? `<span class="cat-badge ${({'CR':'cat-cr','Incident':'cat-incident','New':'cat-new','Regression':'cat-regression'}[p.category]||'cat-other')}">${p.category}</span>` : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="font-size:11.5px;white-space:nowrap">${typeLabel(p.type)}</td>
      <td style="text-align:center;font-weight:700">${p.total_tc || '-'}</td>
      <td style="text-align:center">${p.pass ? pill(p.pass,'pill-pass') : '-'}</td>
      <td style="text-align:center">${p.fail ? pill(p.fail,'pill-fail') : '-'}</td>
      <td style="text-align:center;font-weight:700;color:var(--purple)">${p.accuracy != null ? p.accuracy+'%' : '-'}</td>
      <td style="text-align:center">${p.has_xlsx ? '<span style="color:#2E7D32">✓</span>' : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="text-align:center">${p.has_docx ? '<span style="color:#2E7D32">✓</span>' : '<span style="color:var(--muted)">—</span>'}</td>
      <td style="font-size:11.5px;color:var(--muted);white-space:nowrap">${p.last_run || '—'}</td>
      <td><button class="btn btn-sm btn-primary" onclick="switchProject('${p.id}');showSection('dashboard')">Open</button></td>
    </tr>`).join('')}</tbody>
  </table>`;
}

async function loadSummary() {
  const wrap = document.getElementById('summary-table-wrap');
  if (!wrap) return;
  wrap.innerHTML = '<div style="padding:12px">' + skeletonLinesHTML(6) + '</div>';
  _summaryData = await apiCall('/api/summary');
  if (!_summaryData.length) {
    wrap.innerHTML = emptyStateHTML('📂', 'ยังไม่มี project', null, 'เพิ่มที่ Projects tab');
    return;
  }
  // Populate filter dropdowns from data
  const companies  = [...new Set(_summaryData.map(p => p.company).filter(Boolean))].sort();
  const categories = [...new Set(_summaryData.map(p => p.category).filter(Boolean))].sort();
  const sfCo  = document.getElementById('sf-company');
  const sfCat = document.getElementById('sf-category');
  if (sfCo) {
    const cur = sfCo.value;
    sfCo.innerHTML  = '<option value="all">🏢 All Companies</option>'  + companies.map(c  => `<option value="${c}" ${c===cur?'selected':''}>${c}</option>`).join('');
  }
  if (sfCat) {
    const cur = sfCat.value;
    sfCat.innerHTML = '<option value="all">📁 All Categories</option>' + categories.map(c => `<option value="${c}" ${c===cur?'selected':''}>${c}</option>`).join('');
  }
  _applySummaryFilter();
}

// ── Config import ──────────────────────────────────────────────────────────
async function importConfig(input) {
  const file = input.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch('/api/config/import', {method:'POST', body: fd});
  const d = await r.json();
  if (d.error) { showToast('Error: ' + d.error, 'err'); return; }
  showToast(`Import สำเร็จ — ${d.count} projects`);
  input.value = '';
  await loadProjectsGrid();
  await init();
}

// ── Pipeline mode selector ─────────────────────────────────────────────────
const PIPELINE_MODES = {
  full:   [],                         // show all
  manual: [0, 1, 2, 4, 5, 8],        // skip Explore/BA/Spec/Tests/Inject — เน้น Excel + Report
  report: [0, 1, 2, 3, 4, 5, 6],     // report + inject only
};

function setPipelineMode(mode) {
  localStorage.setItem('fp_pipeline_mode', mode);
  document.querySelectorAll('.pipeline-mode').forEach(b => b.classList.remove('active'));
  const btn = document.getElementById('mode-' + mode);
  if (btn) btn.classList.add('active');
  updatePipelineForType();
}

(function applyPipelineMode() {
  const m = localStorage.getItem('fp_pipeline_mode') || 'full';
  document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.pipeline-mode').forEach(b => b.classList.remove('active'));
    const btn = document.getElementById('mode-' + m);
    if (btn) btn.classList.add('active');
  });
})();

// ── Run step with guard ─────────────────────────────────────────────────────
async function runStepGuarded(step, label, _btn = null) {
  if (step === 'generate') {
    try {
      const r = await fetch(pq('/api/validate/excel'));
      const d = await r.json();
      if (!d.error && d.total > 0 && d.not_started === d.total) {
        const proceed = await showConfirm({
          icon: '⚠️',
          title: 'ยังไม่ได้กรอกผลการทดสอบ',
          desc: `Test Case ทั้งหมด <b>${d.total} รายการ</b> ยังเป็น "Not Start"<br><span style="font-size:12px;color:var(--muted)">ยังไม่ได้กรอกผลใน Excel — ต้องการ Generate Report ต่อหรือไม่?</span>`,
          okLabel: 'Generate ต่อ', okColor: '#E65100',
        });
        if (!proceed) return;
      }
    } catch(e) { /* proceed anyway */ }
  }
  runStep(step, label, '', _btn);
}

// ── Watch mode ─────────────────────────────────────────────────────────────
let _watchRunning = false;

async function toggleWatch() {
  const r = await fetch(pq('/api/run/watch'), {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action: 'toggle'}),
  });
  const d = await r.json();
  if (d.error) { showToast(d.error, 'err'); return; }
  _watchRunning = d.running;
  _updateWatchBtn();
  showToast(_watchRunning ? '👁 Watch mode started — กำลังรอการบันทึก Excel' : 'Watch mode stopped', _watchRunning ? 'ok' : 'info');
}

function _updateWatchBtn() {
  const btn = document.getElementById('watch-btn');
  if (!btn) return;
  if (_watchRunning) {
    btn.textContent = '🟢 Watch (On)';
    btn.style.cssText = 'background:#E8F5E9;color:#2E7D32;border:1px solid #A5D6A7';
  } else {
    btn.textContent = '👁 Watch Mode';
    btn.style.cssText = 'background:#F3E5F5;color:#6A1B9A;border:1px solid #CE93D8';
  }
}

async function _checkWatchStatus() {
  if (!currentProject) return;
  const r = await fetch(pq('/api/run/watch/status'));
  const d = await r.json();
  _watchRunning = d.running;
  _updateWatchBtn();
}

// ── Stage 6 validate helper ────────────────────────────────────────────────
async function refreshValidate() {
  const wrap = document.getElementById('s6-validate');
  if (!wrap || !currentProject) return;
  try {
    const r = await fetch(pq('/api/validate/excel'));
    const d = await r.json();
    if (d.error) { wrap.innerHTML = `<span style="color:var(--muted)">${d.error}</span>`; return; }
    const pct = d.total ? Math.round(d.filled / d.total * 100) : 0;
    const color = d.filled === d.total ? '#2E7D32' : d.filled > 0 ? '#E65100' : 'var(--muted)';
    wrap.innerHTML = `<span style="color:${color};font-weight:600">กรอกแล้ว ${d.filled}/${d.total} รายการ (${pct}%)</span>`
      + (d.counts.pass  ? ` &nbsp;<span class="pill pill-pass">Pass ${d.counts.pass}</span>` : '')
      + (d.counts.fail  ? ` &nbsp;<span class="pill pill-fail">Fail ${d.counts.fail}</span>` : '')
      + (d.counts['in-progress'] ? ` &nbsp;<span class="pill pill-ip">In-Progress ${d.counts['in-progress']}</span>` : '')
      + (d.missing_shots.length  ? `<br><span style="color:#E65100;font-size:11.5px">⚠️ Screenshots ขาด ${d.missing_shots.length} รายการ</span>` : '');
  } catch(e) {}
}

// ── Dark mode ──────────────────────────────────────────────────────────────
function toggleDark() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const next = isDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  document.getElementById('dark-toggle').textContent = next === 'dark' ? '☀️' : '🌙';
  localStorage.setItem('fp_theme', next);
}
(function applyTheme() {
  const t = localStorage.getItem('fp_theme') || 'light';
  document.documentElement.setAttribute('data-theme', t);
  // button may not exist yet — set after DOM ready
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('dark-toggle');
    if (btn) btn.textContent = t === 'dark' ? '☀️' : '🌙';
  });
})();

// ── Page Visibility — pause auto-refresh when tab is hidden ────────────────
document.addEventListener('visibilitychange', () => {
  if (document.hidden) stopAutoRefresh(); else startAutoRefresh();
});

// ── Confirm modal ──────────────────────────────────────────────────────────
// Usage: const ok = await showConfirm({ title, desc, icon, okLabel, okColor, danger })
function showConfirm({ title='ยืนยันการดำเนินการ', desc='', icon='⚠️',
                       okLabel='ยืนยัน', okColor='#E53935', danger=false } = {}) {
  return new Promise(resolve => {
    const overlay = document.getElementById('confirm-overlay');
    document.getElementById('confirm-icon').textContent  = icon;
    document.getElementById('confirm-title').textContent = title;
    document.getElementById('confirm-desc').innerHTML    = desc;
    document.getElementById('confirm-ok').textContent   = okLabel;
    document.getElementById('confirm-ok').style.background = okColor;

    overlay.classList.add('open');

    const close = val => {
      overlay.classList.remove('open');
      okBtn.removeEventListener('click', onOk);
      cancelBtn.removeEventListener('click', onCancel);
      overlay.removeEventListener('click', onBg);
      document.removeEventListener('keydown', onKey);
      resolve(val);
    };
    const onOk     = () => close(true);
    const onCancel = () => close(false);
    const onBg     = e => { if (e.target === overlay) close(false); };
    const onKey    = e => { if (e.key === 'Escape') close(false); if (e.key === 'Enter') close(true); };

    const okBtn     = document.getElementById('confirm-ok');
    const cancelBtn = document.getElementById('confirm-cancel');
    okBtn.addEventListener('click', onOk);
    cancelBtn.addEventListener('click', onCancel);
    overlay.addEventListener('click', onBg);
    document.addEventListener('keydown', onKey);

    // Focus cancel by default (safe), ok for non-danger
    setTimeout(() => (danger ? cancelBtn : okBtn).focus(), 50);
  });
}

// ── Run history ────────────────────────────────────────────────────────────
let _rhShowGhost = false;   // default: hide ghost runs (pass=0 & fail=0)
let _rhAllRows   = [];      // cache from last fetch
let _rhTagFilter = '';      // tag filter: '' = all, or tag string
let _rhDateFrom  = '';      // date filter from (YYYY-MM-DD)
let _rhDateTo    = '';      // date filter to (YYYY-MM-DD)

function _rhTagPill(t) {
  if (!t) return '<span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">All</span>';
  const clean = t.replace(/^@+/, '');   // strip leading @ (defensive for old entries)
  const palette = {smoke:'#E3F2FD|#1565C0', e2e:'#FFF8E1|#F57F17', regression:'#F3E5F5|#6A1B9A', visual:'#E8EAF6|#3949AB'};
  const [bg,fg] = (palette[clean] || '#F5F5F5|#616161').split('|');
  return `<span style="background:${bg};color:${fg};padding:2px 8px;border-radius:10px;font-size:11px;font-weight:700">@${clean}</span>`;
}

function _rhRender(rows) {
  const wrap = document.getElementById('run-history-wrap');
  if (!wrap) return;
  let visible = _rhShowGhost ? rows : rows.filter(e => e.pass > 0 || e.fail > 0);
  const ghostCount = rows.filter(e => e.pass === 0 && e.fail === 0).length;

  // Apply tag filter
  if (_rhTagFilter) visible = visible.filter(e => (e.tag||'').replace(/^@+/,'') === _rhTagFilter.replace(/^@+/,''));
  // Apply date filters
  if (_rhDateFrom) visible = visible.filter(e => e.ts >= _rhDateFrom);
  if (_rhDateTo)   visible = visible.filter(e => e.ts <= _rhDateTo + ' 23:59:59');

  const allTags = [...new Set(rows.map(e => (e.tag||'').replace(/^@+/,'')).filter(Boolean))];

  const _rhEnvStyles = (env) => {
    const map = {all:'#E3F2FD|#1565C0|#90CAF9', uat:'#E8F5E9|#2E7D32|#A5D6A7', prod:'#FFEBEE|#B71C1C|#EF9A9A'};
    const [bg,c,br] = (map[env]||map.all).split('|');
    return _rhEnvFilter===env ? `background:${bg};color:${c};border-color:${br}` : 'background:var(--bg);color:var(--muted);border-color:var(--border)';
  };
  const toolbar = `
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;flex-wrap:wrap">
      <label style="display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted);cursor:pointer;user-select:none">
        <input type="checkbox" id="rh-show-ghost" ${_rhShowGhost?'checked':''} onchange="_rhShowGhost=this.checked;_rhRender(_rhAllRows)">
        ghost runs${ghostCount ? ` <span style="background:#FFF8E1;color:#E65100;border-radius:8px;padding:0 6px;font-size:11px">${ghostCount}</span>` : ''}
      </label>
      <div style="display:flex;gap:4px">
        <button class="rh-env-btn" data-env="all"  onclick="setRhEnv('all')"  style="padding:3px 10px;border-radius:20px;border:1px solid;font-size:11.5px;font-weight:600;cursor:pointer;${_rhEnvStyles('all')}">All</button>
        <button class="rh-env-btn" data-env="uat"  onclick="setRhEnv('uat')"  style="padding:3px 10px;border-radius:20px;border:1px solid;font-size:11.5px;font-weight:600;cursor:pointer;${_rhEnvStyles('uat')}">🟢 UAT</button>
        <button class="rh-env-btn" data-env="prod" onclick="setRhEnv('prod')" style="padding:3px 10px;border-radius:20px;border:1px solid;font-size:11.5px;font-weight:600;cursor:pointer;${_rhEnvStyles('prod')}">🔴 Prod</button>
      </div>
      <select style="padding:3px 8px;border-radius:7px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:12px;cursor:pointer"
        onchange="_rhTagFilter=this.value;_rhRender(_rhAllRows)">
        <option value="">All Tags</option>
        ${allTags.map(t => `<option value="${t}" ${_rhTagFilter===t?'selected':''}>@${t}</option>`).join('')}
      </select>
      <input type="date" value="${_rhDateFrom}" title="From date"
        style="padding:3px 7px;border-radius:7px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:12px"
        onchange="_rhDateFrom=this.value;_rhRender(_rhAllRows)">
      <span style="font-size:11px;color:var(--muted)">–</span>
      <input type="date" value="${_rhDateTo}" title="To date"
        style="padding:3px 7px;border-radius:7px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:12px"
        onchange="_rhDateTo=this.value;_rhRender(_rhAllRows)">
      ${(_rhTagFilter||_rhDateFrom||_rhDateTo) ? `<button class="btn btn-sm" style="font-size:11px;padding:2px 8px;background:var(--bg);border:1px solid var(--border)" onclick="_rhTagFilter='';_rhDateFrom='';_rhDateTo='';_rhRender(_rhAllRows)">✕ Clear</button>` : ''}
      <div style="margin-left:auto;display:flex;gap:6px">
        ${ghostCount ? `<button class="btn btn-sm" style="background:#FFF3E0;color:#E65100;border:1px solid #FFCC80;font-size:12px" onclick="_rhPurge('ghost')">🗑 ghost (${ghostCount})</button>` : ''}
        <button class="btn btn-sm" style="background:#FFEBEE;color:#B71C1C;border:1px solid #FFCDD2;font-size:12px" onclick="_rhPurge('all')">ล้างทั้งหมด</button>
      </div>
    </div>`;

  const activeFilters = _rhTagFilter || _rhDateFrom || _rhDateTo;
  if (!visible.length) {
    wrap.innerHTML = toolbar + `<div style="text-align:center;padding:32px 20px;color:var(--muted)">
      <div style="font-size:28px;margin-bottom:8px">${activeFilters ? '🔍' : '📋'}</div>
      <div style="font-size:13px;margin-bottom:12px">${activeFilters ? 'ไม่พบข้อมูลที่ตรงกับ filter' : 'ยังไม่มีประวัติการรัน'}</div>
      ${activeFilters ? '' : '<button class="btn btn-primary btn-sm" onclick="runTestsWithTag(this)">▶ Run Tests แรก</button>'}
    </div>`;
    return;
  }

  const tbody = [...visible].reverse().map(e => {
    const ok      = e.rc === 0;
    const isGhost = e.pass === 0 && e.fail === 0;
    const total   = e.pass + e.fail;
    const pct     = total > 0 ? Math.round(e.pass / total * 100) : null;
    const rowStyle = isGhost ? 'opacity:.55;' : '';
    const envVal    = e.env || 'uat';
    const envBadge  = envVal === 'prod'
      ? `<span style="background:#FFEBEE;color:#B71C1C;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:700;border:1px solid #EF9A9A">🔴 PROD</span>`
      : `<span style="background:#E8F5E9;color:#2E7D32;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:600;border:1px solid #A5D6A7">🟢 UAT</span>`;
    const prodTint  = envVal === 'prod' && !isGhost ? 'background:rgba(255,235,238,.3);' : '';
    const srcBadge  = e.source === 'schedule'
      ? `<span style="background:#FFF3E0;color:#E65100;padding:2px 7px;border-radius:10px;font-size:10.5px;font-weight:700;border:1px solid #FFB74D" title="Scheduled run: ${e.ts}">🕐 sched</span>`
      : `<span style="color:var(--muted);font-size:11px">manual</span>`;
    return `<tr style="${rowStyle}${prodTint}">
      <td data-label="Timestamp" style="padding:6px 10px;border-bottom:1px solid var(--border);font-size:12px;white-space:nowrap">${e.ts}</td>
      <td data-label="Env" style="padding:6px 10px;border-bottom:1px solid var(--border)">${envBadge}</td>
      <td data-label="Scope" style="padding:6px 10px;border-bottom:1px solid var(--border)">${_rhTagPill(e.tag||'')}</td>
      <td data-label="Pass" style="padding:6px 10px;border-bottom:1px solid var(--border);color:#22a55b;font-weight:700;text-align:center">${e.pass}</td>
      <td data-label="Fail" style="padding:6px 10px;border-bottom:1px solid var(--border);color:${e.fail>0?'#e53e3e':'var(--muted)'};font-weight:700;text-align:center">${e.fail}</td>
      <td data-label="Rate" style="padding:6px 10px;border-bottom:1px solid var(--border);text-align:center">
        ${pct !== null ? `<span style="font-size:12px;font-weight:700;color:${pct>=80?'#43A047':pct>=60?'#FB8C00':'#E53935'}">${pct}%</span>` : '<span style="color:var(--muted);font-size:11px">—</span>'}
      </td>
      <td data-label="Result" style="padding:6px 10px;border-bottom:1px solid var(--border)">
        <span class="badge ${ok?'badge-ok':'badge-running'}" style="font-size:11px">${ok?'Done ✓':'Error ✗'}</span>
      </td>
      <td data-label="Source" style="padding:6px 10px;border-bottom:1px solid var(--border);text-align:center">${srcBadge}</td>
      <td data-label="" style="padding:6px 4px;border-bottom:1px solid var(--border)">
        <button onclick="_rhDeleteRow('${e.ts.replace(/'/g,"\\'")}')"
          title="ลบรายการนี้"
          style="background:none;border:none;cursor:pointer;color:var(--muted);font-size:15px;line-height:1;padding:2px 6px;border-radius:4px"
          onmouseover="this.style.color='#E53935';this.style.background='#FFEBEE'"
          onmouseout="this.style.color='var(--muted)';this.style.background='none'">×</button>
      </td>
    </tr>`;
  }).join('');

  wrap.innerHTML = toolbar + `
    <div style="overflow-x:auto">
    <table class="table-stack" style="width:100%;border-collapse:collapse;font-size:12.5px">
      <thead><tr>
        <th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Timestamp</th>
        <th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Env</th>
        <th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Scope</th>
        <th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Pass</th>
        <th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Fail</th>
        <th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Rate</th>
        <th style="text-align:left;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Result</th>
        <th style="text-align:center;padding:6px 10px;border-bottom:1px solid var(--border);color:var(--muted);font-weight:600">Source</th>
        <th style="width:32px;border-bottom:1px solid var(--border)"></th>
      </tr></thead>
      <tbody>${tbody}</tbody>
    </table></div>`;
}

async function loadRunHistory() {
  if (!currentProject) return;
  const wrap = document.getElementById('run-history-wrap');
  if (!wrap) return;
  wrap.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:8px">Loading...</div>';
  const envQ = _rhEnvFilter !== 'all' ? `&env=${_rhEnvFilter}` : '';
  const r = await fetch(pq('/api/run/history') + envQ);
  _rhAllRows = await r.json();
  _rhRender(_rhAllRows);
}

async function _rhDeleteRow(ts) {
  if (!currentProject) return;
  const ok = await showConfirm({
    icon: '🗑️',
    title: 'ลบ record นี้?',
    desc: `<span style="font-family:monospace;font-size:12px;background:var(--bg);padding:3px 8px;border-radius:5px">${ts}</span><br><br>การลบนี้ไม่สามารถย้อนกลับได้`,
    okLabel: 'ลบ', okColor: '#E53935', danger: true,
  });
  if (!ok) return;
  const r = await fetch(pq('/api/run/history/delete'), {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({project_id: currentProject, ts}),
  });
  const d = await r.json();
  if (d.ok) {
    _rhAllRows = _rhAllRows.filter(e => e.ts !== ts);
    _rhRender(_rhAllRows);
    loadTrend();
    showToast('ลบ record แล้ว', 'ok');
  } else {
    showToast('ลบไม่สำเร็จ', 'error');
  }
}

async function _rhPurge(mode) {
  if (!currentProject) return;
  const cfg = {
    ghost: {
      icon: '🧹', title: 'ล้าง Ghost Runs?',
      desc: 'ลบ records ที่ <b>pass = 0 และ fail = 0</b> ทั้งหมด<br><span style="font-size:12px;color:var(--muted)">เกิดจากการรันที่ไม่ได้ผลลัพธ์ เช่น crash ก่อนเริ่ม test</span>',
      okLabel: 'ล้าง Ghost Runs', okColor: '#E65100',
    },
    failed: {
      icon: '⚠️', title: 'ล้าง Failed Runs?',
      desc: 'ลบ records ที่ <b>exit code ≠ 0</b> ทั้งหมด',
      okLabel: 'ล้าง', okColor: '#E53935',
    },
    all: {
      icon: '🚨', title: 'ล้างประวัติทั้งหมด?',
      desc: `ลบ <b>ประวัติการรัน tests ทั้งหมด</b> ของ project นี้<br><span style="font-size:12px;color:#E53935">⚠ Trend chart และ Release Readiness จะ reset — ไม่สามารถย้อนกลับได้</span>`,
      okLabel: 'ลบทั้งหมด', okColor: '#B71C1C',
    },
  };
  const c = cfg[mode] || {icon:'⚠️', title:'ยืนยัน?', desc:'', okLabel:'ยืนยัน', okColor:'#E53935'};
  const ok = await showConfirm({ ...c, danger: true });
  if (!ok) return;
  const r = await fetch(pq('/api/run/history/purge'), {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({project_id: currentProject, mode}),
  });
  const d = await r.json();
  if (d.ok) {
    showToast(`ลบแล้ว ${d.removed} รายการ (เหลือ ${d.remaining})`, 'ok');
    await loadRunHistory();
    loadTrend();
    if (mode === 'all') loadRelease();
  } else {
    showToast('ลบไม่สำเร็จ: ' + (d.error||''), 'error');
  }
}

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(msg, type='ok', duration=5000) {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  const span = document.createElement('span');
  span.style.flex = '1';
  span.textContent = msg;
  const x = document.createElement('button');
  x.className = 'toast-dismiss';
  x.innerHTML = '×';
  x.onclick = () => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); };
  t.appendChild(span); t.appendChild(x);
  document.getElementById('toast-container').appendChild(t);
  requestAnimationFrame(() => { requestAnimationFrame(() => t.classList.add('show')); });
  const timer = setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, duration);
  x.addEventListener('click', () => clearTimeout(timer), {once: true});
}

// ── ZIP download ───────────────────────────────────────────────────────────
function downloadShots() {
  if (!_allShotFiles.length) { showToast('No screenshots to download', 'info'); return; }
  window.location.href = pq('/api/screenshots/download');
}

function runReviewExcel() {
  const resultBox = document.getElementById('s3-review-result');
  resultBox.style.display = 'block';
  resultBox.textContent = '▶ กำลัง review TCM...';
  const es = new EventSource(pq('/api/run/review-excel'));
  const lines = [];
  es.onmessage = e => {
    const d = JSON.parse(e.data);
    if (d.line) lines.push(d.line);
    resultBox.textContent = lines.join('\n');
    resultBox.scrollTop = resultBox.scrollHeight;
    if (d.done) {
      es.close();
      if (d.returncode === 0) showToast('TCM Review เสร็จแล้ว — ดูผลด้านบน', 'ok');
      else showToast('Review เจอ error — ตรวจ log', 'err');
    }
  };
  es.onerror = () => { es.close(); showToast('Connection error', 'err'); };
}

// ── Release Readiness ─────────────────────────────────────────────────────
async function loadRelease() {
  if (!currentProject) return;
  const verdict = document.getElementById('rr-verdict');
  const list    = document.getElementById('rr-checklist');
  const lastRun = document.getElementById('rr-lastrun');
  verdict.className = 'rr-verdict loading';
  verdict.innerHTML = '<div class="rr-icon">⏳</div><div><div class="rr-title" style="color:var(--muted)">กำลังตรวจสอบ...</div></div>';
  list.innerHTML = '';

  const projMeta      = allProjects.find(p => p.id === currentProject);
  const isPWOnly      = projMeta?.type === 'playwright-only';
  const isPytestOnly  = projMeta?.type === 'pytest-only';
  const isTestsOnly   = isPWOnly || isPytestOnly;
  const isManualTest  = projMeta?.type === 'manual-testing';
  const phase         = projMeta?.phase || 'active';

  // Per-project gate thresholds (override defaults via config.json projects[].gates)
  const _gates          = projMeta?.gates || {};
  const GATE_PASS_RATE  = _gates.pass_rate           ?? 80;
  const GATE_TCM_PASS   = _gates.tcm_pass_rate       ?? 80;
  const GATE_SHOT_COV   = _gates.screenshot_coverage ?? 80;
  // warn band = 20 points below hard gate (floor at 0)
  const _warnBand = (g) => Math.max(g - 20, 0);

  // ── Non-active phases: show neutral state immediately ──────────────
  if (phase !== 'active') {
    const phaseCfg = {
      planning: {
        icon: '🗂',
        cls:  'rr-verdict warn',
        title: 'อยู่ใน Planning Phase',
        sub:  'ยังไม่เริ่มเขียน test — Release Gate ถูกยกเว้น',
        color: '#1565C0', bg: '#E3F2FD',
        note: 'เริ่มเขียน Playwright spec แล้วเปลี่ยน Phase เป็น Active เพื่อเปิด Gate',
      },
      paused: {
        icon: '⏸',
        cls:  'rr-verdict',
        title: 'Project หยุดพัฒนา (Paused)',
        sub:  'Release Gate ถูกยกเว้น — ไม่มีการ release ในขณะนี้',
        color: '#E65100', bg: '#FFF8E1',
        note: 'เปลี่ยน Phase เป็น Active เพื่อเปิด Gate อีกครั้ง',
      },
    };
    const c = phaseCfg[phase] || phaseCfg.planning;
    verdict.className = c.cls;
    verdict.innerHTML = `
      <div class="rr-icon">${c.icon}</div>
      <div>
        <div class="rr-title" style="color:${c.color}">${c.title}</div>
        <div class="rr-sub">${c.sub}</div>
      </div>`;
    list.innerHTML = `
      <div style="background:${c.bg};border-radius:8px;padding:12px 16px;font-size:13px;color:${c.color};line-height:1.6">
        💡 ${c.note}<br>
        <span style="font-size:12px;opacity:.8">แก้ไขได้ที่ <b>Projects → ✏️ Edit → Project Phase</b></span>
      </div>`;
    if (lastRun) lastRun.textContent = '';
    return;
  }

  try {
    // ── fetch data (skip TCM-only APIs for tests-only types) ───────
    const fetches = [
      fetch(pq('/api/bugs')),
      fetch(pq('/api/run/history')),
      fetch(pq('/api/screenshots/list')),
    ];
    if (isTestsOnly) {
      fetches.push(fetch(pq('/api/info')));
    } else {
      // full-pipeline and manual-testing both need TCM data
      fetches.push(fetch(pq('/api/status')));
      fetches.push(fetch(pq('/api/validate/excel')).catch(() => null));
    }
    const results  = await Promise.all(fetches);
    const bugs     = await results[0].json();
    const hist     = await results[1].json();
    const shotList = await results[2].json();
    const d_info   = isTestsOnly              ? await results[3].json() : null;
    const st       = !isTestsOnly             ? await results[3].json() : null;
    const val      = !isTestsOnly && results[4]?.ok ? await results[4].json() : null;

    // ── shared metrics ──────────────────────────────────────────────
    const openCritical = bugs.filter(b => b.severity === 'Critical' && b.status === 'Open').length;
    const openHigh     = bugs.filter(b => b.severity === 'High'     && b.status === 'Open').length;
    const shotCount    = Array.isArray(shotList) ? shotList.length : 0;

    // Filter out ghost runs (pass=0 & fail=0) — use only runs with actual results
    const validHist = hist.filter(e => e.pass > 0 || e.fail > 0);
    const lastTest  = validHist.length ? validHist[validHist.length - 1] : null;
    const passRate  = lastTest ? Math.round(lastTest.pass / (lastTest.pass + lastTest.fail) * 100) : null;

    // tag weight: all/regression=3 (release-ready), e2e/visual=2 (acceptable), smoke=1 (insufficient)
    const TAG_WEIGHT = {'': 3, 'regression': 3, 'e2e': 2, 'visual': 2, 'smoke': 1};
    const lastTag    = lastTest?.tag ?? '';
    const tagWeight  = TAG_WEIGHT[lastTag] ?? 2;
    const tagLabel   = lastTag ? `@${lastTag}` : 'All tests';

    // ── Auto-detect "no test activity yet" — Playwright/Pytest projects only ─
    if (!validHist.length && !isManualTest) {
      verdict.className = 'rr-verdict warn';
      verdict.innerHTML = `
        <div class="rr-icon">🚦</div>
        <div>
          <div class="rr-title" style="color:#1565C0">ยังไม่มีข้อมูลการทดสอบ</div>
          <div class="rr-sub">รัน tests ก่อน เพื่อให้ Release Gate ประเมินผลได้</div>
        </div>`;
      list.innerHTML = `
        <div style="background:#E3F2FD;border-radius:8px;padding:12px 16px;font-size:13px;color:#1565C0;line-height:1.8">
          📋 ขั้นตอนถัดไป:<br>
          1. เปิด <b>Pipeline</b> → <b>▶ Run Tests</b><br>
          2. กลับมาหน้า <b>Release</b> เพื่อดูผล Gate<br>
          ${!isTestsOnly ? '3. อัปโหลด TCM Excel ใน Stage 1 ก่อน ถ้ายังไม่มี<br>' : ''}
          <span style="font-size:11px;opacity:.8">หากยังไม่ได้เขียน test เลย เปลี่ยน Phase เป็น Planning ได้ที่ Projects → ✏️ Edit</span>
        </div>`;
      if (lastRun) lastRun.textContent = '';
      return;
    }

    // ── build criteria per type ─────────────────────────────────────
    let items;

    if (isPytestOnly) {
      // ── Pytest-only criteria (5 items — no PW report/screenshots) ─
      items = [
        {
          label: 'มี Test Run อย่างน้อย 1 ครั้ง',
          ok: lastTest !== null,
          detail: lastTest ? `Last run: ${lastTest.ts}` : 'ยังไม่มี run history — รัน tests ก่อน',
        },
        {
          label: 'Run Scope — ต้องรันอย่างน้อย @e2e หรือ All',
          ok:   lastTest !== null && tagWeight >= 2,
          warn: lastTest !== null && tagWeight === 2,
          detail: lastTest === null
            ? 'ยังไม่มี run history'
            : tagWeight >= 3
              ? `✓ ${tagLabel} · ${lastTest.ts}`
              : tagWeight === 2
                ? `⚠ ${tagLabel} — พอสำหรับ minor release, ควรรัน All ก่อน major`
                : `✗ ${tagLabel} เท่านั้น — ไม่เพียงพอสำหรับ release`,
        },
        {
          label: `Pass Rate ≥ ${GATE_PASS_RATE}%`,
          ok:   passRate !== null && passRate >= GATE_PASS_RATE,
          warn: passRate !== null && passRate >= _warnBand(GATE_PASS_RATE) && passRate < GATE_PASS_RATE,
          detail: passRate === null
            ? 'ยังไม่มี run history — รัน tests ก่อนแล้ว log ผล'
            : `${passRate}% (${lastTest.pass} pass / ${lastTest.fail} fail) · ${lastTest.ts}`,
        },
        {
          label: 'ไม่มี Critical Bug ที่ยัง Open',
          ok:   openCritical === 0,
          detail: openCritical === 0
            ? 'ไม่มี Critical open bug' + (openHigh > 0 ? ` (High: ${openHigh} — ควรแก้ก่อน)` : '')
            : `มี ${openCritical} Critical bug ที่ยัง Open`,
        },
        {
          label: 'ไม่มี High Bug ที่ยัง Open',
          ok:   openHigh === 0,
          warn: openHigh > 0 && openHigh <= 2,
          detail: openHigh === 0
            ? 'ไม่มี High open bug'
            : `มี ${openHigh} High bug ที่ยัง Open`,
        },
      ];

    } else if (isPWOnly) {
      // ── Playwright-only criteria (5 items) ────────────────────────
      items = [
        {
          label: 'Run Scope — ต้องรันอย่างน้อย @e2e หรือ All',
          ok:   lastTest !== null && tagWeight >= 2,
          warn: lastTest !== null && tagWeight === 2,   // @e2e: acceptable แต่ warn ว่ายังไม่สมบูรณ์
          detail: lastTest === null
            ? 'ยังไม่มี run history'
            : tagWeight >= 3
              ? `✓ ${tagLabel} · ${lastTest.ts}`
              : tagWeight === 2
                ? `⚠ ${tagLabel} — พอสำหรับ minor release, ควรรัน All ก่อน major`
                : `✗ ${tagLabel} เท่านั้น — ไม่เพียงพอสำหรับ release`,
        },
        {
          label: `Pass Rate ≥ ${GATE_PASS_RATE}%`,
          ok:   passRate !== null && passRate >= GATE_PASS_RATE,
          warn: passRate !== null && passRate >= _warnBand(GATE_PASS_RATE) && passRate < GATE_PASS_RATE,
          detail: passRate === null
            ? 'ยังไม่มี run history — รัน tests ก่อนแล้ว log ผล'
            : `${passRate}% (${lastTest.pass} pass / ${lastTest.fail} fail) · ${lastTest.ts}`,
        },
        {
          label: 'ไม่มี Critical Bug ที่ยัง Open',
          ok:   openCritical === 0,
          detail: openCritical === 0
            ? 'ไม่มี Critical open bug' + (openHigh > 0 ? ` (High: ${openHigh} — ควรแก้ก่อน)` : '')
            : `มี ${openCritical} Critical bug ที่ยัง Open`,
        },
        {
          label: 'ไม่มี High Bug ที่ยัง Open',
          ok:   openHigh === 0,
          warn: openHigh > 0 && openHigh <= 2,
          detail: openHigh === 0
            ? 'ไม่มี High open bug'
            : `มี ${openHigh} High bug ที่ยัง Open`,
        },
        {
          label: 'มี Screenshots จากการรัน',
          ok:   shotCount > 0,
          detail: shotCount > 0
            ? `${shotCount} screenshot(s) พร้อมแล้ว`
            : 'ยังไม่มี screenshot — รัน tests ก่อน',
        },
        {
          label: 'Playwright HTML Report พร้อม',
          ok:   d_info?.pw_report_ok === true,
          warn: !d_info?.pw_report_ok && passRate !== null,
          detail: d_info?.pw_report_ok
            ? `playwright-report/index.html พร้อม · ${d_info.pw_report_ts}`
            : 'รัน tests ก่อนเพื่อ generate playwright-report/',
        },
      ];

    } else if (isManualTest) {
      // ── Manual-testing criteria (6 items — no Playwright) ─────────
      const total      = val?.total ?? 0;
      const notStarted = val?.not_started ?? 0;
      const tcmPass    = val ? (val.counts?.pass ?? 0) : 0;
      const tcmPassPct = total > 0 ? Math.round(tcmPass / total * 100) : null;

      items = [
        {
          label: 'TCM Excel อัปโหลดแล้ว',
          ok:   st.s2.ok,
          detail: st.s2.file || 'ยังไม่มีไฟล์ใน input/',
        },
        {
          label: 'Test Cases ไม่มี Not Start (ทดสอบครบแล้ว)',
          ok:   total > 0 && notStarted === 0,
          warn: total > 0 && notStarted > 0 && notStarted < total * 0.2,
          detail: total === 0 ? 'ไม่พบ TCM'
            : notStarted === 0 ? `ทุก TC มีสถานะแล้ว (${total} TCs)`
            : `ยังไม่ได้ทดสอบ ${notStarted}/${total} TCs — กรอกผลใน Excel ก่อน`,
        },
        {
          label: `TCM Pass Rate ≥ ${GATE_TCM_PASS}%`,
          ok:   tcmPassPct !== null && tcmPassPct >= GATE_TCM_PASS,
          warn: tcmPassPct !== null && tcmPassPct >= _warnBand(GATE_TCM_PASS) && tcmPassPct < GATE_TCM_PASS,
          detail: tcmPassPct === null ? 'ไม่พบ TCM'
            : `${tcmPassPct}% (${tcmPass}/${total} TCs marked Pass)`,
        },
        {
          label: 'ไม่มี Critical Bug ที่ยัง Open',
          ok:   openCritical === 0,
          detail: openCritical === 0
            ? 'ไม่มี Critical open bug' + (openHigh > 0 ? ` (High: ${openHigh} — ควรแก้ก่อน)` : '')
            : `มี ${openCritical} Critical bug ที่ยัง Open`,
        },
        {
          label: 'ไม่มี High Bug ที่ยัง Open',
          ok:   openHigh === 0,
          warn: openHigh > 0 && openHigh <= 2,
          detail: openHigh === 0
            ? 'ไม่มี High open bug'
            : `มี ${openHigh} High bug ที่ยัง Open`,
        },
        {
          label: 'Word Report พร้อม',
          ok:   st.s7.ok,
          detail: st.s7.file || 'ยังไม่มี report — รัน Stage 7 ก่อน',
        },
      ];

    } else {
      // ── Full-pipeline criteria (8 items) ─────────────────────────
      const total      = val?.total ?? 0;
      const notStarted = val?.not_started ?? 0;
      const shotCov    = (val && total > 0) ? Math.round(val.shot_coverage / total * 100) : null;
      const tcmPass    = val ? (val.counts?.pass ?? 0) : 0;
      const tcmPassPct = total > 0 ? Math.round(tcmPass / total * 100) : null;

      items = [
        {
          label: 'TCM Excel อัปโหลดแล้ว',
          ok:   st.s2.ok,
          detail: st.s2.file || 'ยังไม่มีไฟล์ใน input/',
        },
        {
          label: 'Test Spec ครบ (Stage 4)',
          ok:   st.s4.ok && !st.s4.stale,
          warn: st.s4.ok && st.s4.stale,
          detail: st.s4.ok
            ? (st.s4.stale ? `⚠ ${st.s4.count} spec — เก่ากว่า Excel` : `${st.s4.count} spec file(s)`)
            : 'ยังไม่มี spec — รัน Stage 2 ก่อน',
        },
        {
          label: 'Test Cases ไม่มี Not Start',
          ok:   total > 0 && notStarted === 0,
          warn: total > 0 && notStarted > 0 && notStarted < total * 0.2,
          detail: total === 0 ? 'ไม่พบ TCM'
            : notStarted === 0 ? `ทุก TC มีสถานะแล้ว (${total} TCs)`
            : `ยังไม่รัน ${notStarted}/${total} TCs`,
        },
        {
          label: 'Run Scope — ต้องรันอย่างน้อย @e2e หรือ All',
          ok:   lastTest !== null && tagWeight >= 2,
          warn: lastTest !== null && tagWeight === 2,
          detail: lastTest === null
            ? 'ยังไม่มี run history'
            : tagWeight >= 3
              ? `✓ ${tagLabel} · ${lastTest.ts}`
              : tagWeight === 2
                ? `⚠ ${tagLabel} — พอสำหรับ minor release, ควรรัน All ก่อน major`
                : `✗ ${tagLabel} เท่านั้น — ไม่เพียงพอสำหรับ release`,
        },
        {
          label: `Pass Rate ≥ ${GATE_PASS_RATE}%`,
          ok:   passRate !== null && passRate >= GATE_PASS_RATE,
          warn: passRate !== null && passRate >= _warnBand(GATE_PASS_RATE) && passRate < GATE_PASS_RATE,
          detail: passRate === null ? 'ยังไม่มี run history'
            : `${passRate}% (${lastTest.pass} pass / ${lastTest.fail} fail) · ${lastTest.ts}`,
        },
        {
          label: `TCM Pass Rate ≥ ${GATE_TCM_PASS}%`,
          ok:   tcmPassPct !== null && tcmPassPct >= GATE_TCM_PASS,
          warn: tcmPassPct !== null && tcmPassPct >= _warnBand(GATE_TCM_PASS) && tcmPassPct < GATE_TCM_PASS,
          detail: tcmPassPct === null ? 'ไม่พบ TCM'
            : `${tcmPassPct}% (${tcmPass}/${total} TCs marked Pass)`,
        },
        {
          label: 'ไม่มี Critical Bug ที่ยัง Open',
          ok:   openCritical === 0,
          detail: openCritical === 0
            ? 'ไม่มี Critical open bug' + (openHigh > 0 ? ` (High: ${openHigh})` : '')
            : `มี ${openCritical} Critical bug ที่ยัง Open`,
        },
        {
          label: `Screenshot Coverage ≥ ${GATE_SHOT_COV}%`,
          ok:   shotCov !== null && shotCov >= GATE_SHOT_COV,
          warn: shotCov !== null && shotCov >= _warnBand(GATE_SHOT_COV) && shotCov < GATE_SHOT_COV,
          detail: shotCov === null ? 'ไม่พบ TCM'
            : `${shotCov}% (${val.shot_coverage}/${total} TCs มี screenshot)`,
        },
        {
          label: 'Word Report พร้อม',
          ok:   st.s7.ok,
          detail: st.s7.file || 'ยังไม่มี report — รัน Stage 7 ก่อน',
        },
      ];
    }

    // ── render checklist ────────────────────────────────────────────
    list.innerHTML = items.map(it => {
      const cls  = it.ok ? 'pass' : (it.warn ? 'warn' : 'fail');
      const icon = it.ok ? '✅' : (it.warn ? '⚠️' : '❌');
      return `<div class="rr-item ${cls}">
        <span class="rr-chk">${icon}</span>
        <span class="rr-label">${it.label}</span>
        <span class="rr-detail">${it.detail}</span>
      </div>`;
    }).join('');

    // ── verdict ─────────────────────────────────────────────────────
    const hardFail = items.filter(it => !it.ok && !it.warn);
    const warnings = items.filter(it => it.warn);
    const isGo     = hardFail.length === 0;
    const typeTag  = isPytestOnly ? '🐍 Pytest-Only'
                   : isPWOnly      ? '🎭 Playwright-Only'
                   : isManualTest  ? '📋 Manual Testing'
                   : '🔄 Full Pipeline';
    verdict.className = `rr-verdict ${isGo ? 'go' : 'nogo'}`;
    verdict.innerHTML = isGo
      ? `<div class="rr-icon">🟢</div>
         <div>
           <div class="rr-title">GO — พร้อม Release</div>
           <div class="rr-sub">${warnings.length > 0 ? `ผ่านทุกเกณฑ์ (มี ${warnings.length} ข้อควรระวัง)` : 'ผ่านทุกเกณฑ์ครบถ้วน'} · ${typeTag}</div>
         </div>`
      : `<div class="rr-icon">🔴</div>
         <div>
           <div class="rr-title">NO-GO — ยังไม่พร้อม</div>
           <div class="rr-sub">ไม่ผ่าน ${hardFail.length} เกณฑ์ · ${typeTag}</div>
         </div>`;

    lastRun.textContent = lastTest
      ? `ข้อมูล ณ ${new Date().toLocaleString('th-TH')} · Run ล่าสุด: ${lastTest.ts}`
      : `ข้อมูล ณ ${new Date().toLocaleString('th-TH')} · ยังไม่มี run history`;

  } catch(e) {
    verdict.className = 'rr-verdict loading';
    verdict.innerHTML = '<div class="rr-icon">⚠️</div><div><div class="rr-title" style="color:var(--muted)">โหลดข้อมูลไม่ได้</div></div>';
    console.error('loadRelease:', e);
  }
}

// ── Bug Metrics ────────────────────────────────────────────────────────────
let _bmVisible = false;

function toggleBugMetrics() {
  _bmVisible = !_bmVisible;
  document.getElementById('bm-panel').style.display = _bmVisible ? '' : 'none';
  document.getElementById('bm-toggle-btn').textContent = _bmVisible ? '📊 Hide Metrics' : '📊 Show Metrics';
  if (_bmVisible) renderBugMetrics();
}

function renderBugMetrics() {
  if (!_allBugs.length) {
    document.getElementById('bm-panel').innerHTML = '<div style="color:var(--muted);font-size:13px;padding:16px;text-align:center">ยังไม่มีข้อมูล bug</div>';
    return;
  }
  const total = _allBugs.length;

  // ── Severity bars ───────────────────────────────────────────────
  const sevColors = {Critical:'#C62828', High:'#E65100', Medium:'#F57F17', Low:'#2E7D32'};
  const sevCounts = {Critical:0, High:0, Medium:0, Low:0};
  _allBugs.forEach(b => { if (sevCounts[b.severity] !== undefined) sevCounts[b.severity]++; });
  const maxSev = Math.max(...Object.values(sevCounts), 1);
  document.getElementById('bm-severity-bars').innerHTML = Object.entries(sevCounts).map(([sev, cnt]) =>
    `<div class="bar-row">
      <span class="bar-label" style="color:${sevColors[sev]}">${sev}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(cnt/maxSev*100)}%;background:${sevColors[sev]}"></div></div>
      <span class="bar-val" style="color:${sevColors[sev]}">${cnt}</span>
    </div>`
  ).join('');

  // ── Status bars ─────────────────────────────────────────────────
  const stColors = {Open:'#B71C1C','In Progress':'#E65100', Resolved:'#2E7D32', Closed:'#607D8B'};
  const stCounts = {Open:0,'In Progress':0, Resolved:0, Closed:0};
  _allBugs.forEach(b => { if (stCounts[b.status] !== undefined) stCounts[b.status]++; });
  const maxSt = Math.max(...Object.values(stCounts), 1);
  document.getElementById('bm-status-bars').innerHTML = Object.entries(stCounts).map(([st, cnt]) =>
    `<div class="bar-row">
      <span class="bar-label" style="color:${stColors[st]}">${st}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(cnt/maxSt*100)}%;background:${stColors[st]}"></div></div>
      <span class="bar-val" style="color:${stColors[st]}">${cnt}</span>
    </div>`
  ).join('');

  // ── Aging: oldest open bugs ──────────────────────────────────────
  const today    = new Date();
  const openBugs = _allBugs
    .filter(b => b.status === 'Open' && b.created_at)
    .map(b => ({ ...b, days: Math.floor((today - new Date(b.created_at)) / 86400000) }))
    .sort((a, b) => b.days - a.days)
    .slice(0, 5);

  if (!openBugs.length) {
    document.getElementById('bm-aging').innerHTML = '<div style="color:var(--muted);font-size:13px;padding:8px">ไม่มี Open bug 🎉</div>';
  } else {
    const sevC = {Critical:'#C62828', High:'#E65100', Medium:'#F57F17', Low:'#2E7D32'};
    document.getElementById('bm-aging').innerHTML = openBugs.map(b => {
      const ageCls = b.days >= 14 ? 'critical-age' : b.days >= 7 ? 'high-age' : 'ok-age';
      return `<div class="aging-row">
        <div class="aging-days ${ageCls}" title="${b.days} วัน">${b.days}d</div>
        <div style="flex:1;min-width:0">
          <div style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="${_esc(b.title)}">${_esc(b.title)}</div>
          <div style="font-size:11.5px;color:var(--muted)">${b.id} · <span style="color:${sevC[b.severity]}">${b.severity}</span></div>
        </div>
        <div style="font-size:11.5px;color:var(--muted);flex-shrink:0">${b.created_at?.slice(0,10) || '—'}</div>
      </div>`;
    }).join('');
  }
}

// ── Trend Chart ────────────────────────────────────────────────────────────
async function loadTrend() {
  if (!currentProject) return;
  const wrap   = document.querySelector('#trend-card .trend-wrap');
  const statsEl  = document.getElementById('trend-stats');
  const legendEl = document.getElementById('trend-legend');
  const badgeEl  = document.getElementById('trend-badge');
  if (!wrap) return;

  const envQ = _dashEnvFilter !== 'all' ? `&env=${_dashEnvFilter}` : '';
  const r = await fetch(pq('/api/run/trend') + envQ);
  const data = await r.json();

  if (!data.length) {
    wrap.innerHTML = '<div class="trend-empty">📊<br>ยังไม่มี run history<br><span style="font-size:12px">รัน tests ก่อน แล้วกลับมาดู trend</span></div>';
    if (statsEl)  statsEl.style.display  = 'none';
    if (legendEl) legendEl.style.display = 'none';
    if (badgeEl)  badgeEl.style.display  = 'none';
    return;
  }

  // ── Layout constants ──────────────────────────────────────────────────────
  const W = 620, H = 190, PL = 42, PR = 18, PT = 16, PB = 38;
  const iW = W - PL - PR, iH = H - PT - PB;
  const n = data.length;
  const xStep = n > 1 ? iW / (n - 1) : iW;

  // ── Tag colour palette ────────────────────────────────────────────────────
  const TAG_C = {
    '':           '#4CAF50',
    'regression': '#9C27B0',
    'e2e':        '#FF7043',
    'visual':     '#2196F3',
    'smoke':      '#FF9800',
  };
  const TAG_LABEL = {
    '': 'All tests', 'regression': '@regression',
    'e2e': '@e2e', 'visual': '@visual', 'smoke': '@smoke',
  };

  // ── Data points ───────────────────────────────────────────────────────────
  const pts = data.map((d, i) => ({
    x: PL + (n > 1 ? i * xStep : iW / 2),
    y: PT + iH - (d.pct / 100 * iH),
    pct: d.pct, tag: d.tag || '', ts: d.ts, pass: d.pass, fail: d.fail, rc: d.rc,
  }));

  // ── Smooth cubic-bezier path ──────────────────────────────────────────────
  function makePath(pts) {
    if (pts.length === 1) return `M${pts[0].x},${pts[0].y}`;
    let d = `M${pts[0].x},${pts[0].y}`;
    for (let i = 0; i < pts.length - 1; i++) {
      const dx = (pts[i+1].x - pts[i].x) / 3;
      d += ` C${pts[i].x+dx},${pts[i].y} ${pts[i+1].x-dx},${pts[i+1].y} ${pts[i+1].x},${pts[i+1].y}`;
    }
    return d;
  }

  const linePath = makePath(pts);
  const areaPath = `${linePath} L${pts[pts.length-1].x},${PT+iH} L${pts[0].x},${PT+iH} Z`;

  // Line colour = based on latest pass rate
  const lastPct   = data[data.length - 1].pct;
  const lineColor = lastPct >= 80 ? '#43A047' : lastPct >= 60 ? '#FB8C00' : '#E53935';
  const gradId    = 'tg' + Math.random().toString(36).slice(2, 8);

  // ── Y axis ────────────────────────────────────────────────────────────────
  const yLabels = [0, 50, 80, 100].map(v => {
    const y     = PT + iH - (v / 100 * iH);
    const is80  = v === 80;
    return `<line x1="${PL}" y1="${y}" x2="${W-PR}" y2="${y}"
              stroke="${is80 ? '#FFCDD2' : '#EEF1F5'}"
              stroke-width="${is80 ? 1.5 : 1}"
              stroke-dasharray="${is80 ? '5,4' : ''}"/>
            <text x="${PL-7}" y="${y+4}" text-anchor="end" font-size="10"
              fill="${is80 ? '#EF9A9A' : '#C4CBD6'}" font-family="system-ui,sans-serif">${v}%</text>`;
  }).join('');

  // 80% label on right
  const refY   = PT + iH - (80 / 100 * iH);
  const refLabel = `<text x="${W-PR}" y="${refY-5}" text-anchor="end" font-size="9"
    fill="#EF9A9A" font-family="system-ui,sans-serif" font-weight="600">80% target</text>`;

  // ── X axis labels ─────────────────────────────────────────────────────────
  const maxTicks = 6;
  const tickIdxs = n <= maxTicks
    ? data.map((_,i) => i)
    : Array.from({length: maxTicks}, (_, k) => Math.round(k * (n-1) / (maxTicks-1)));
  const xLabels  = [...new Set(tickIdxs)].map(i => {
    const p = pts[i], raw = data[i].ts;
    // prefer HH:MM if same-day data, else MM-DD
    const label = raw.slice(5, 10);
    return `<text x="${p.x}" y="${H-8}" text-anchor="middle" font-size="10"
      fill="#C4CBD6" font-family="system-ui,sans-serif">${label}</text>`;
  }).join('');

  // ── Dots ──────────────────────────────────────────────────────────────────
  const dots = pts.map((p, i) => {
    const c    = TAG_C[p.tag] || '#4CAF50';
    const last = i === pts.length - 1;
    const tip  = JSON.stringify({ts:p.ts, tag:p.tag, pass:p.pass, fail:p.fail, pct:p.pct, rc:p.rc});
    // latest dot = slightly larger ring
    return `<circle class="trend-dot" cx="${p.x}" cy="${p.y}"
      r="${last ? 6 : 4.5}" fill="${c}"
      stroke="${last ? '#fff' : 'rgba(255,255,255,0.8)'}"
      stroke-width="${last ? 2.5 : 1.8}"
      data-tip='${tip.replace(/'/g, "&#39;")}' />`;
  }).join('');

  wrap.innerHTML = `
    <svg class="trend-svg" viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stop-color="${lineColor}" stop-opacity="0.22"/>
          <stop offset="100%" stop-color="${lineColor}" stop-opacity="0.01"/>
        </linearGradient>
        <filter id="dot-glow">
          <feGaussianBlur stdDeviation="2" result="blur"/>
          <feComposite in="SourceGraphic" in2="blur" operator="over"/>
        </filter>
      </defs>
      ${yLabels}
      <path d="${areaPath}" fill="url(#${gradId})"/>
      <path d="${linePath}" fill="none" stroke="${lineColor}" stroke-width="2.5"
        stroke-linecap="round" stroke-linejoin="round"/>
      ${xLabels}
      ${refLabel}
      ${dots}
    </svg>`;

  // ── Floating tooltip ──────────────────────────────────────────────────────
  let tt = document.getElementById('trend-tooltip');
  if (!tt) {
    tt = document.createElement('div');
    tt.id = 'trend-tooltip';
    document.body.appendChild(tt);
  }
  wrap.querySelectorAll('.trend-dot').forEach(dot => {
    dot.addEventListener('mouseenter', e => {
      const d   = JSON.parse(e.target.dataset.tip.replace(/&#39;/g, "'"));
      const tl  = d.tag ? `@${d.tag}` : 'All tests';
      const tot = d.pass + d.fail;
      const pc  = d.pct >= 80 ? '#69F0AE' : d.pct >= 60 ? '#FFD740' : '#FF6E6E';
      tt.innerHTML = `
        <div style="font-weight:700;font-size:14px;color:${pc}">${d.pct}%<span style="font-size:11px;font-weight:400;color:#aaa;margin-left:4px">passed</span></div>
        <div style="margin-top:4px;color:#ddd">${d.pass} pass &nbsp;·&nbsp; ${d.fail} fail &nbsp;·&nbsp; ${tot} total</div>
        <div style="color:#888;font-size:11px;margin-top:5px;border-top:1px solid rgba(255,255,255,.1);padding-top:5px">${tl} &nbsp;·&nbsp; ${d.ts}</div>
        ${d.rc !== 0 ? `<div style="color:#FF6E6E;font-size:11px;margin-top:3px">⚠ exit code ${d.rc}</div>` : ''}`;
      tt.style.display = 'block';
    });
    dot.addEventListener('mousemove', e => {
      tt.style.left = (e.clientX + 16) + 'px';
      tt.style.top  = (e.clientY - 14) + 'px';
    });
    dot.addEventListener('mouseleave', () => { tt.style.display = 'none'; });
  });

  // ── Summary stats row ─────────────────────────────────────────────────────
  const avgPct   = Math.round(data.reduce((s,d) => s + d.pct, 0) / data.length);
  const prevPct  = data.length > 1 ? data[data.length - 2].pct : null;
  const delta    = prevPct !== null ? lastPct - prevPct : null;
  const trendArrow = delta === null ? '' : delta > 0 ? ' ↑' : delta < 0 ? ' ↓' : ' →';
  const trendColor = delta === null ? '' : delta > 0 ? '#43A047' : delta < 0 ? '#E53935' : '#90A4AE';
  const lastTag    = data[data.length - 1].tag;
  const tagBg      = (TAG_C[lastTag] || '#4CAF50') + '22';
  const tagFg      = TAG_C[lastTag] || '#4CAF50';

  if (statsEl) {
    statsEl.innerHTML = `
      <div class="trend-stat">
        <div class="trend-stat-label">Runs</div>
        <div class="trend-stat-value">${n}</div>
      </div>
      <div class="trend-stat">
        <div class="trend-stat-label">Avg Pass Rate</div>
        <div class="trend-stat-value">${avgPct}%</div>
      </div>
      <div class="trend-stat">
        <div class="trend-stat-label">Latest</div>
        <div class="trend-stat-value" style="color:${lineColor}">${lastPct}%<span style="font-size:14px;margin-left:3px;color:${trendColor}">${trendArrow}</span></div>
      </div>
      <div class="trend-stat">
        <div class="trend-stat-label">Last Scope</div>
        <div style="margin-top:4px">
          <span style="font-size:12px;font-weight:600;padding:3px 10px;border-radius:10px;background:${tagBg};color:${tagFg}">${TAG_LABEL[lastTag] || lastTag}</span>
        </div>
      </div>`;
    statsEl.style.display = '';
  }

  // ── Legend (only tags present in data) ────────────────────────────────────
  const usedTags = [...new Set(data.map(d => d.tag || ''))];
  if (legendEl) {
    if (usedTags.length > 1) {
      legendEl.innerHTML = usedTags.map(t => {
        const c = TAG_C[t] || '#4CAF50';
        return `<span class="trend-legend-item">
          <svg width="10" height="10"><circle cx="5" cy="5" r="4.5" fill="${c}"/></svg>
          ${TAG_LABEL[t] || t}</span>`;
      }).join('');
      legendEl.style.display = '';
    } else {
      legendEl.style.display = 'none';
    }
  }

  // ── Status badge ──────────────────────────────────────────────────────────
  if (badgeEl) {
    const [bTxt, bBg, bFg] = lastPct >= 80
      ? ['On Track', '#E8F5E9', '#2E7D32']
      : lastPct >= 60
      ? ['Below Target', '#FFF8E1', '#E65100']
      : ['Failing', '#FFEBEE', '#B71C1C'];
    badgeEl.textContent = bTxt;
    badgeEl.style.background = bBg;
    badgeEl.style.color = bFg;
    badgeEl.style.display = '';
  }
}

// ── Retrofit TCM ────────────────────────────────────────────────────────────
async function retrofitTCM() {
  const btn = document.getElementById('retrofit-btn');
  const res = document.getElementById('retrofit-result');
  btn.disabled = true; btn.textContent = '⏳ Generating...';
  res.style.display = 'none';
  try {
    const r = await fetch(pq('/api/tools/retrofit-tcm'), {method:'POST'});
    const d = await r.json();
    if (d.error) {
      res.style.display = '';
      res.innerHTML = `<div style="color:#B71C1C;font-size:13px">❌ ${d.error}</div>`;
    } else {
      res.style.display = '';
      res.innerHTML = `<div style="color:#2E7D32;font-size:13px;line-height:1.8">
        ✅ สร้างสำเร็จ: <b>${d.file}</b><br>
        ${d.ts_count} Test Scenarios · ${d.tc_count} Test Cases<br>
        <span style="color:var(--muted);font-size:12px">เปลี่ยน project type เป็น full-pipeline แล้ว Refresh เพื่อใช้งาน</span>
      </div>`;
      showToast(`TCM สร้างแล้ว — ${d.tc_count} TCs`, 'ok');
      setTimeout(loadInfo, 1000);
    }
  } catch(e) {
    res.style.display = '';
    res.innerHTML = `<div style="color:#B71C1C;font-size:13px">❌ ${e.message}</div>`;
  }
  btn.disabled = false; btn.textContent = '⚡ Generate TCM Excel';
}

// ── Schedule ───────────────────────────────────────────────────────────────
const WEEKDAY_NAMES = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const ACTION_LABELS = { tests:'▶ Run Tests', generate:'📄 Generate TCM', inject:'🖼 Screenshot Inject', 'add-charts':'📊 Add Charts' };

function scToggleFields() {
  const t = document.getElementById('sc-type').value;
  document.getElementById('sc-time-wrap').style.display    = t === 'cron' ? 'none' : '';
  document.getElementById('sc-weekday-wrap').style.display = t === 'weekly' ? '' : 'none';
  document.getElementById('sc-cron-wrap').style.display    = t === 'cron' ? '' : 'none';
}

function scCheckProdWarn() {
  const env = document.getElementById('sc-env')?.value;
  const tag = document.getElementById('sc-tag')?.value;
  const warn = document.getElementById('sc-prod-warn');
  if (!warn) return;
  const isProd    = env === 'prod';
  const nonSmoke  = tag !== '@smoke';
  warn.style.display = (isProd && nonSmoke) ? '' : 'none';
}

function _scEnvBadge(s) {
  const isProd = s.env === 'prod';
  return isProd
    ? '<span style="background:#FFEBEE;color:#B71C1C;padding:2px 8px;border-radius:10px;font-size:11.5px;font-weight:700;border:1px solid #EF9A9A">🔴 PROD</span>'
    : '<span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:10px;font-size:11.5px;font-weight:600;border:1px solid #A5D6A7">🟢 UAT</span>';
}

function _scDescribe(s) {
  if (s.schedule_type === 'daily')  return `Every day at ${s.time}`;
  if (s.schedule_type === 'weekly') return `Every ${WEEKDAY_NAMES[s.weekday] || s.weekday} at ${s.time}`;
  if (s.schedule_type === 'cron')   return `Cron: <code>${s.cron}</code>`;
  return s.schedule_type;
}

function _scStatusBadge(s) {
  if (!s.last_status) return '<span style="color:var(--muted);font-size:12px">—</span>';
  if (s.last_status === 'ok')
    return '<span style="background:#E8F5E9;color:#2E7D32;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">✓ ok</span>';
  if (s.last_status === 'skipped')
    return '<span style="background:#E3F2FD;color:#1565C0;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">⏭ skipped</span>';
  return `<span style="background:#FFEBEE;color:#C62828;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">✗ ${s.last_status}</span>`;
}

async function loadSchedule() {
  // Populate project dropdown (always rebuild to stay in sync)
  const sel = document.getElementById('sc-project');
  if (sel) {
    sel.innerHTML = '';
    allProjects.forEach(p => {
      const o = document.createElement('option');
      o.value = p.id; o.textContent = p.name;
      sel.appendChild(o);
    });
    if (currentProject) sel.value = currentProject;
  }

  const list = document.getElementById('sc-list');
  try {
    const r = await fetch('/api/schedules');
    const data = await r.json();
    if (!data.length) {
      list.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:12px 0">No schedules yet. Add one above.</div>';
      return;
    }
    list.innerHTML = `
      <table class="ts-table table-stack">
        <thead><tr>
          <th>Project</th><th>Env</th><th>Action</th><th>Tag</th><th>Schedule</th>
          <th>Last Run</th><th>Status</th><th>Enabled</th><th></th>
        </tr></thead>
        <tbody>
        ${data.map(s => `
          <tr>
            <td data-label="Project" style="font-weight:600;font-size:13px">${s.project_name || s.project_id}</td>
            <td data-label="Env">${_scEnvBadge(s)}</td>
            <td data-label="Action">${ACTION_LABELS[s.action] || s.action}</td>
            <td data-label="Tag"><code>${s.tag || 'all'}</code></td>
            <td data-label="Schedule">${_scDescribe(s)}</td>
            <td data-label="Last Run" style="font-size:12px;color:var(--muted)">${s.last_run || '—'}</td>
            <td data-label="Status">${_scStatusBadge(s)}</td>
            <td data-label="Enabled">
              <label style="display:inline-flex;align-items:center;gap:6px;cursor:pointer">
                <input type="checkbox" ${s.enabled ? 'checked' : ''} onchange="toggleSchedule('${s.id}',this)">
                <span style="font-size:12px">${s.enabled ? 'On' : 'Off'}</span>
              </label>
            </td>
            <td data-label="" style="display:flex;gap:4px">
              <button class="btn btn-sm" style="background:#E3F2FD;color:#1565C0;border:1px solid #90CAF9;padding:4px 10px"
                onclick="runNow('${s.id}')" title="Run immediately">▶</button>
              <button class="btn btn-sm" style="background:#FFEBEE;color:#C62828;border:1px solid #EF9A9A;padding:4px 10px"
                onclick="deleteSchedule('${s.id}')">🗑</button>
            </td>
          </tr>`).join('')}
        </tbody>
      </table>`;
  } catch(e) {
    list.innerHTML = `<div style="color:var(--danger);font-size:13px">Error: ${e.message}</div>`;
  }
}

async function addSchedule() {
  const pid   = document.getElementById('sc-project').value;
  const stype = document.getElementById('sc-type').value;
  if (!pid) return showToast('กรุณาเลือก Project', 'warn');
  const env = document.getElementById('sc-env').value;
  const tag = document.getElementById('sc-tag').value;
  if (env === 'prod' && tag !== '@smoke') {
    if (!confirm('⚠️ Production + non-@smoke tag\ntest อาจ write data จริงบน Production\nยืนยันที่จะเพิ่ม schedule นี้?')) return;
  }
  const body = {
    project_id:    pid,
    action:        document.getElementById('sc-action').value,
    tag:           tag,
    env:           env,
    schedule_type: stype,
    time:          document.getElementById('sc-time').value,
    weekday:       parseInt(document.getElementById('sc-weekday').value),
    cron:          document.getElementById('sc-cron').value,
  };
  // Per-schedule notify_on override (empty = use global)
  const notifyOnRaw = document.getElementById('sc-notify-on')?.value || '';
  if (notifyOnRaw) {
    body.notify_on = notifyOnRaw === 'all' ? ['all']
                   : notifyOnRaw === 'error-only' ? ['error']
                   : ['fail', 'error'];
  }
  try {
    await apiCall('/api/schedules/add', {body});
    showToast('Schedule added', 'ok');
    loadSchedule();
  } catch(e) { /* apiCall toasted */ }
}

async function toggleSchedule(id, cb) {
  const r = await fetch('/api/schedules/toggle', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})
  });
  const d = await r.json();
  if (!d.ok) { cb.checked = !cb.checked; showToast('Error toggling', 'err'); }
  else { cb.nextElementSibling.textContent = d.enabled ? 'On' : 'Off'; }
}

async function deleteSchedule(id) {
  if (!confirm('ลบ schedule นี้?')) return;
  await fetch('/api/schedules/delete', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})
  });
  loadSchedule();
}

async function runNow(id) {
  showToast('Starting run...', 'info', 2000);
  const r = await fetch('/api/schedules/run-now', {
    method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id})
  });
  const d = await r.json();
  if (d.ok) showToast('Run started — ดู Log ด้านล่าง', 'ok', 4000);
  else      showToast(d.error || 'Error', 'err');
  setTimeout(loadSchedLog, 2000);
}

async function loadSchedLog() {
  const el = document.getElementById('sc-log');
  if (!el) return;
  try {
    const r = await fetch('/api/schedules/log');
    const d = await r.json();
    if (!d.lines.length) { el.textContent = '(ยังไม่มี log)'; return; }
    el.textContent = d.lines.join('\n');
    el.scrollTop = el.scrollHeight;
  } catch(e) { el.textContent = 'Error loading log'; }
}

// ── ENV filter helpers ─────────────────────────────────────────────────────
function _applyEnvBtnStyle(selector, activeEnv) {
  document.querySelectorAll(selector).forEach(b => {
    const isActive = b.dataset.env === activeEnv;
    const envMap = {
      all:  {bg:'#E3F2FD', color:'#1565C0', border:'#90CAF9'},
      uat:  {bg:'#E8F5E9', color:'#2E7D32', border:'#A5D6A7'},
      prod: {bg:'#FFEBEE', color:'#B71C1C', border:'#EF9A9A'},
    };
    const s = isActive ? envMap[b.dataset.env] : null;
    b.style.background   = s ? s.bg    : 'var(--bg)';
    b.style.color        = s ? s.color : 'var(--muted)';
    b.style.borderColor  = s ? s.border : 'var(--border)';
  });
}

function setDashEnv(v) {
  _dashEnvFilter = v;
  _applyEnvBtnStyle('.dash-env-btn', v);
  _applyEnvBtnStyle('.ts-env-btn',   v);
  loadInfo();
  loadTrend();
}

function setRhEnv(v) {
  _rhEnvFilter = v;
  _applyEnvBtnStyle('.rh-env-btn', v);
  loadRunHistory();
}

// ── Schedule notifications ─────────────────────────────────────────────────
let _schedBadgeCount = 0;

function clearSchedBadge() {
  _schedBadgeCount = 0;
  const b = document.getElementById('nav-sched-badge');
  if (b) b.style.display = 'none';
  // Also reload the list so status is fresh
  const active = document.querySelector('.section.active')?.id?.replace('section-','');
  if (active === 'schedule') loadSchedule();
}

async function pollSchedNotifications() {
  try {
    const r = await fetch('/api/schedules/notifications');
    const items = await r.json();
    if (!items.length) return;

    _schedBadgeCount += items.length;
    const b = document.getElementById('nav-sched-badge');
    if (b) { b.textContent = _schedBadgeCount; b.style.display = ''; }

    items.forEach(n => {
      const isOk   = n.status === 'ok';
      const icon   = isOk ? '✅' : n.status === 'skipped' ? '⏭️' : '❌';
      const tag    = n.tag && n.tag !== 'all' ? ` [${n.tag}]` : '';
      const envLbl = n.env === 'prod' ? ' 🔴PROD' : ' 🟢UAT';
      const msg    = `${icon} Schedule: ${n.project_name}${tag}${envLbl} — ${n.status}`;
      showToast(msg, isOk ? 'ok' : 'err', 6000);
    });

    // If Schedule section is open, refresh the table
    const active = document.querySelector('.section.active')?.id?.replace('section-','');
    if (active === 'schedule') loadSchedule();
    // Also refresh run history if pipeline is open
    if (active === 'pipeline') loadRunHistory();
  } catch(e) { /* silent */ }
}

// ── System Check ──────────────────────────────────────────────────────────
function runSystemCheck() {
  const btn     = document.getElementById('syscheck-btn');
  const results = document.getElementById('syscheck-results');
  const summary = document.getElementById('syscheck-summary');
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> Running...';
  results.innerHTML = '';
  summary.style.display = 'none';

  const es = new EventSource('/api/system-check');
  es.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.done) {
      es.close();
      btn.disabled = false;
      btn.textContent = '▶ Run Again';
      const allOk = d.passed === d.total;
      summary.style.display = 'block';
      summary.style.background = allOk ? '#E8F5E9' : '#FFF3E0';
      summary.style.color      = allOk ? '#2E7D32' : '#E65100';
      summary.style.border     = allOk ? '1px solid #A5D6A7' : '1px solid #FFE0B2';
      summary.innerHTML = allOk
        ? `✅ ${d.passed}/${d.total} passed — System ready`
        : `⚠️ ${d.passed}/${d.total} passed — ${d.total - d.passed} issue(s) found`;
      return;
    }
    const icon = d.status === 'ok' ? '✅' : '❌';
    const color = d.status === 'ok' ? 'var(--text)' : '#C62828';
    const detail = d.detail ? `<span style="color:var(--muted);font-size:12px;margin-left:8px">${d.detail}</span>` : '';
    results.innerHTML += `<div style="padding:8px 12px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;font-size:13px">
      <span style="font-size:16px;flex-shrink:0">${icon}</span>
      <span style="font-weight:600;color:${color};min-width:180px">${d.check}</span>
      ${detail}
    </div>`;
  };
  es.onerror = () => {
    es.close();
    btn.disabled = false;
    btn.textContent = '▶ Run Again';
  };
}

// ── Boot ───────────────────────────────────────────────────────────────────
init().then(() => {
  startAutoRefresh();
  loadBugBadge();
  setInterval(pollSchedNotifications, 60000);  // poll every 60s
});