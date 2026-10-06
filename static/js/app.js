/**
 * Rangrag Archviz Studio CRM — Core Frontend Controller
 * Handles real-time analytics, Kanban drag/inspection, Gemini generation,
 * SMTP dispatch ticker, IMAP scan, and Instant WhatsApp Handoff.
 */

// Global State
const state = {
  currentView: 'dashboard',
  analytics: {},
  senderStatus: {},
  activeEditingThreadId: null,
  activeEditingLeadId: null,
  leads: [],
  pollingInterval: null
};

// DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  initLucide();
  initNavigation();
  initDispatcherControls();
  initSettingsForm();
  initDropzone();
  initModals();
  initTopbarActions();
  
  // Initial Data Fetch
  loadAnalytics();
  loadKanban();
  loadSettings();
  loadLeads();
  startStatusPolling();
});

function initLucide() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

// ----------------- TOAST NOTIFICATIONS -----------------
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <i data-lucide="${type === 'success' ? 'check-circle-2' : (type === 'error' ? 'alert-triangle' : 'info')}" style="width:16px; height:16px;"></i>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  initLucide();

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    setTimeout(() => toast.remove(), 200);
  }, 4000);
}

// ----------------- NAVIGATION -----------------
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const targetView = item.dataset.view;
      switchView(targetView);
    });
  });
}

function switchView(viewName) {
  state.currentView = viewName;
  document.querySelectorAll('.nav-item').forEach(i => i.classList.toggle('active', i.dataset.view === viewName));
  document.querySelectorAll('.view-container').forEach(c => c.style.display = 'none');

  const targetEl = document.getElementById(`view-${viewName}`);
  if (targetEl) targetEl.style.display = 'flex';

  const titles = {
    dashboard: { title: 'Analytics & Dashboard', desc: 'Real-time outreach performance, domain health, and conversion metrics' },
    kanban: { title: 'Review Kanban Queue', desc: 'Inspect, edit bespoke email copy inline, and approve drafts before dispatch' },
    hotleads: { title: 'Hot WhatsApp Handoffs', desc: 'High-intent responses with instant 1-click closing chats' },
    upload: { title: 'Data Cleaning & Validation', desc: 'Upload raw architect CSVs, clean multi-emails, and generate fresh outreach dataset' },
    leads: { title: 'All Leads Database', desc: 'Directory of all verified architectural practices and studios' },
    settings: { title: 'Domain Mail & Handshake', desc: 'Configure outbound SMTP, inbound IMAP, daily limits, and live handshake test' }
  };

  if (titles[viewName]) {
    document.getElementById('page-title').textContent = titles[viewName].title;
    document.getElementById('page-desc').textContent = titles[viewName].desc;
  }

  if (viewName === 'kanban') loadKanban();
  if (viewName === 'hotleads') loadHotLeads();
  if (viewName === 'dashboard') loadAnalytics();
  if (viewName === 'leads') loadLeads();
  initLucide();
}

// ----------------- TOPBAR ACTIONS -----------------
function initTopbarActions() {
  document.getElementById('btn-scan-imap').addEventListener('click', async () => {
    const btn = document.getElementById('btn-scan-imap');
    btn.disabled = true;
    showToast('Scanning connected IMAP inbox for replies and bounces...', 'info');
    try {
      const res = await fetch('/api/campaign/monitor');
      const data = await res.json();
      if (data.success) {
        showToast(`Inbox Scan Complete: ${data.replies_detected} replies found, ${data.bounces_detected} bounces.`, 'success');
        loadAnalytics();
        loadKanban();
      } else {
        showToast(`Scan error: ${data.error}`, 'error');
      }
    } catch (e) {
      showToast(`Scan failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById('btn-trigger-followup').addEventListener('click', async () => {
    showToast('Checking for leads eligible for gentle follow-up (>3 days)...', 'info');
    try {
      const res = await fetch('/api/campaign/followup', { method: 'POST' });
      const data = await res.json();
      if (data.success) {
        showToast(`Follow-up Check: ${data.followups_created} follow-ups drafted!`, 'success');
        loadKanban();
        loadAnalytics();
      }
    } catch (e) {
      showToast(`Follow-up trigger failed: ${e.message}`, 'error');
    }
  });

  document.getElementById('btn-generate-ai-batch').addEventListener('click', async () => {
    const btn = document.getElementById('btn-generate-ai-batch');
    btn.disabled = true;
    showToast('Connecting to Gemini AI to generate customized collaboration drafts...', 'info');
    try {
      const res = await fetch('/api/generate-drafts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ limit: 50 })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Batch Generated: ${data.drafts_created} drafts created with Gemini 2.5 Flash!`, 'success');
        loadKanban();
        loadAnalytics();
      }
    } catch (e) {
      showToast(`Generation failed: ${e.message}`, 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

// ----------------- DISPATCHER CONTROLS -----------------
function initDispatcherControls() {
  document.getElementById('btn-sender-start').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/campaign/send', { method: 'POST' });
      const data = await res.json();
      showToast(data.message, data.success ? 'success' : 'error');
      pollDispatcherStatus();
    } catch (e) {
      showToast(e.message, 'error');
    }
  });

  document.getElementById('btn-sender-pause').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/campaign/pause', { method: 'POST' });
      const data = await res.json();
      showToast(data.message, 'info');
      pollDispatcherStatus();
    } catch (e) {
      showToast(e.message, 'error');
    }
  });

  document.getElementById('btn-sender-stop').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/campaign/stop', { method: 'POST' });
      const data = await res.json();
      showToast(data.message, 'info');
      pollDispatcherStatus();
    } catch (e) {
      showToast(e.message, 'error');
    }
  });
}

function startStatusPolling() {
  pollDispatcherStatus();
  state.pollingInterval = setInterval(() => {
    pollDispatcherStatus();
    if (state.currentView === 'dashboard') loadAnalytics();
  }, 4000);
}

async function pollDispatcherStatus() {
  try {
    const res = await fetch('/api/campaign/status');
    const s = await res.json();
    state.senderStatus = s;

    const pulseDot = document.getElementById('sender-pulse-dot');
    const title = document.getElementById('sender-status-title');
    const desc = document.getElementById('sender-status-desc');
    const btnStart = document.getElementById('btn-sender-start');
    const btnPause = document.getElementById('btn-sender-pause');
    const btnStop = document.getElementById('btn-sender-stop');

    if (s.is_running && !s.is_paused) {
      pulseDot.className = 'pulse-dot active';
      title.textContent = `Dispatcher: ${s.status_message}`;
      btnStart.style.display = 'none';
      btnPause.style.display = 'inline-flex';
      btnStop.style.display = 'inline-flex';
    } else if (s.is_paused) {
      pulseDot.className = 'pulse-dot';
      pulseDot.style.background = 'var(--accent)';
      title.textContent = `Dispatcher Paused: ${s.status_message}`;
      btnStart.style.display = 'inline-flex';
      btnStart.querySelector('span').textContent = 'Resume';
      btnPause.style.display = 'none';
      btnStop.style.display = 'inline-flex';
    } else {
      pulseDot.className = 'pulse-dot';
      pulseDot.style.background = '#64748b';
      title.textContent = `Dispatcher: Idle`;
      btnStart.style.display = 'inline-flex';
      btnStart.querySelector('span').textContent = 'Start Dispatcher';
      btnPause.style.display = 'none';
      btnStop.style.display = 'none';
    }

    const modeText = s.simulation_mode ? '🔒 Zero-Risk Simulation Mode' : '🚀 Live SMTP Domain Mode';
    desc.textContent = `Daily Quota: ${s.sent_today}/${s.daily_limit} | Queue: ${s.ready_to_send} ready | ${modeText}`;

    // Update ready count badge in sidebar
    document.getElementById('badge-ready').textContent = s.ready_to_send || '0';
  } catch (e) {
    console.error('Failed to poll status', e);
  }
}

// ----------------- ANALYTICS & DASHBOARD -----------------
async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    state.analytics = data;

    document.getElementById('metric-total-leads').textContent = data.total_clean_leads;
    document.getElementById('metric-quota').textContent = `${data.sent_today} / ${data.daily_limit}`;
    document.getElementById('metric-quota-sub').textContent = `${data.remaining_quota} emails remaining today`;
    document.getElementById('metric-ready-to-send').textContent = data.ready_to_send;
    document.getElementById('metric-total-sent').textContent = data.total_sent;
    document.getElementById('metric-sent-today').textContent = `${data.sent_today} dispatched today`;
    document.getElementById('metric-reply-rate').textContent = `${data.reply_rate}%`;
    document.getElementById('metric-replies-count').textContent = `${data.total_replies} replies (${data.interested_count} interested)`;
    document.getElementById('metric-deliverability').textContent = `${data.deliverability_rate}%`;
    document.getElementById('metric-bounces').textContent = `${data.bounces} delivery bounces`;
    document.getElementById('metric-hot-leads').textContent = data.hot_leads;
    document.getElementById('metric-whatsapp-converted').textContent = `${data.whatsapp_converted} WhatsApp chats launched`;

    document.getElementById('badge-hot').textContent = data.hot_leads || '0';
    document.getElementById('badge-leads').textContent = data.total_clean_leads || '0';

    // Render Funnel
    const funnelContainer = document.getElementById('funnel-container');
    if (funnelContainer && data.funnel) {
      const maxCount = Math.max(...data.funnel.map(f => f.count), 1);
      funnelContainer.innerHTML = data.funnel.map(f => {
        const pct = Math.round((f.count / maxCount) * 100);
        return `
          <div style="display:flex; flex-direction:column; gap:4px;">
            <div style="display:flex; justify-content:space-between; font-size:12px;">
              <span style="color:var(--text-muted);">${f.stage}</span>
              <strong style="color:#fff; font-family:'JetBrains Mono', monospace;">${f.count}</strong>
            </div>
            <div style="width:100%; height:6px; background:#1a1e2b; border-radius:3px; overflow:hidden;">
              <div style="width:${pct}%; height:100%; background:linear-gradient(90deg, #f59e0b, #10b981); border-radius:3px;"></div>
            </div>
          </div>
        `;
      }).join('');
    }

    // Render Logs
    const logContainer = document.getElementById('activity-log-container');
    if (logContainer && data.logs) {
      logContainer.innerHTML = data.logs.map(log => `
        <div style="font-size:12px; padding:8px 10px; background:#161924; border-radius:6px; border-left:3px solid ${
          log.status === 'success' ? 'var(--emerald)' : (log.status === 'error' ? 'var(--rose)' : 'var(--accent)')
        };">
          <div style="color:#fff; line-height:1.4;">${log.details}</div>
          <div style="color:var(--text-dim); font-size:10px; margin-top:2px;">${new Date(log.created_at).toLocaleTimeString()}</div>
        </div>
      `).join('');
    }
  } catch (e) {
    console.error('Error loading analytics', e);
  }
}

// ----------------- KANBAN REVIEW QUEUE -----------------
async function loadKanban() {
  try {
    const res = await fetch('/api/kanban');
    const board = await res.json();

    document.getElementById('kanban-count-pending').textContent = board.pending_ai.length;
    document.getElementById('kanban-count-ready').textContent = board.ready_to_review.length;
    document.getElementById('kanban-count-dispatched').textContent = board.dispatched.length;
    document.getElementById('kanban-count-hot').textContent = board.hot_leads.length;

    // Col 1: Pending AI
    const colPending = document.getElementById('col-pending-ai');
    colPending.innerHTML = board.pending_ai.map(lead => `
      <div class="kanban-card">
        <div class="card-firm">
          <span>${escapeHtml(lead.firm_name)}</span>
        </div>
        <div class="card-meta">
          <span class="meta-tag">📍 ${escapeHtml(lead.city || 'City')}</span>
          <span class="meta-tag">${escapeHtml(lead.category || 'Architecture')}</span>
        </div>
        <div style="font-size:12px; color:var(--text-dim);">${escapeHtml(lead.email)}</div>
        <div class="card-footer">
          <button class="btn btn-secondary btn-sm" onclick="generateSingleDraft(${lead.id})">
            <i data-lucide="sparkles" style="width:12px; height:12px;"></i>
            <span>Generate Draft</span>
          </button>
        </div>
      </div>
    `).join('') || '<div style="font-size:12px; color:var(--text-dim); padding:16px; text-align:center;">No pending leads. Upload a CSV to begin!</div>';

    // Col 2: Ready to Review
    const colReady = document.getElementById('col-ready-review');
    colReady.innerHTML = board.ready_to_review.map(lead => {
      const thread = lead.latest_thread || {};
      return `
        <div class="kanban-card" onclick="openEditModal(${thread.id || 0}, ${lead.id})">
          <div class="card-firm">
            <span>${escapeHtml(lead.firm_name)}</span>
            <span class="status-pill ready">Ready</span>
          </div>
          <div class="card-meta">
            <span class="meta-tag">👤 ${escapeHtml(lead.contact_name || 'Architect')}</span>
            <span class="meta-tag">📍 ${escapeHtml(lead.city || 'City')}</span>
          </div>
          <div class="card-subject">
            <strong>${escapeHtml(thread.subject || 'Collaboration Draft')}</strong>
          </div>
          <div class="card-footer">
            <span style="color:var(--accent);">Click to Inspect & Edit</span>
            <button class="btn btn-emerald btn-sm" onclick="event.stopPropagation(); approveDraft(${thread.id})">
              Approve
            </button>
          </div>
        </div>
      `;
    }).join('') || '<div style="font-size:12px; color:var(--text-dim); padding:16px; text-align:center;">All drafts approved!</div>';

    // Col 3: Dispatched
    const colDispatched = document.getElementById('col-dispatched');
    colDispatched.innerHTML = board.dispatched.map(lead => {
      const thread = lead.latest_thread || {};
      const statusPillClass = lead.status === 'Bounced' ? 'bounce' : (lead.status === 'Not Interested' ? 'not_interested' : 'dispatched');
      return `
        <div class="kanban-card" onclick="openEditModal(${thread.id || 0}, ${lead.id})">
          <div class="card-firm">
            <span>${escapeHtml(lead.firm_name)}</span>
            <span class="status-pill ${statusPillClass}">${lead.status}</span>
          </div>
          <div class="card-meta">
            <span class="meta-tag">✉️ ${escapeHtml(lead.email)}</span>
          </div>
          <div class="card-subject">${escapeHtml(thread.subject || 'Sent Outreach')}</div>
          <div class="card-footer">
            <span style="color:var(--text-dim);">Sent: ${thread.sent_at ? new Date(thread.sent_at).toLocaleDateString() : 'Recent'}</span>
          </div>
        </div>
      `;
    }).join('') || '<div style="font-size:12px; color:var(--text-dim); padding:16px; text-align:center;">No dispatched emails yet.</div>';

    // Col 4: Hot Leads
    const colHot = document.getElementById('col-hot-leads');
    colHot.innerHTML = board.hot_leads.map(lead => `
      <div class="kanban-card hot-card">
        <div class="card-firm" style="color:var(--emerald);">
          <span>🔥 ${escapeHtml(lead.firm_name)}</span>
          <span class="status-pill interested">HOT LEAD</span>
        </div>
        <div class="card-meta">
          <span class="meta-tag">👤 ${escapeHtml(lead.contact_name)}</span>
          <span class="meta-tag">📱 ${escapeHtml(lead.mobile || 'No Mobile')}</span>
        </div>
        <div style="font-size:12px; color:var(--text-muted); background:rgba(16,185,129,0.1); padding:8px; border-radius:6px;">
          "${escapeHtml(lead.latest_thread?.reply_content || 'Expressed positive interest in 3D viz lookbook!')}"
        </div>
        <div class="card-footer" style="padding-top:10px;">
          <button class="btn btn-emerald btn-sm" style="width:100%; justify-content:center;" onclick="initiateWhatsApp(${lead.id})">
            <i data-lucide="message-circle" style="width:14px; height:14px;"></i>
            <span>Instant WhatsApp Closing Chat &rarr;</span>
          </button>
        </div>
      </div>
    `).join('') || '<div style="font-size:12px; color:var(--text-dim); padding:16px; text-align:center;">Awaiting positive lead replies.</div>';

    initLucide();
  } catch (e) {
    console.error('Error loading Kanban board', e);
  }
}

// ----------------- HOT LEADS VIEW -----------------
async function loadHotLeads() {
  try {
    const res = await fetch('/api/leads?is_hot=true');
    const data = await res.json();
    const container = document.getElementById('hot-leads-container');

    if (!data.leads || data.leads.length === 0) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; padding:48px 24px; text-align:center; background:var(--bg-card); border-radius:var(--radius-lg); border:1px solid var(--border-card);">
          <i data-lucide="flame" style="width:48px; height:48px; color:var(--emerald); margin-bottom:12px;"></i>
          <h3 style="font-size:16px; font-weight:700; color:#fff;">No Hot Leads Yet</h3>
          <p style="font-size:13px; color:var(--text-dim); max-width:440px; margin:6px auto 16px auto;">
            When an architect responds asking for lookbooks, render quotes, or portfolio review, they are automatically tagged here with instant WhatsApp handoff.
          </p>
          <button class="btn btn-secondary btn-sm" onclick="openSimulateModal()">Simulate an Interested Lead Reply</button>
        </div>
      `;
      initLucide();
      return;
    }

    container.innerHTML = data.leads.map(lead => `
      <div class="metric-card" style="border-color: rgba(16, 185, 129, 0.4); background: linear-gradient(135deg, rgba(16, 185, 129, 0.06), var(--bg-card));">
        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
          <div>
            <div style="font-size:16px; font-weight:800; color:#fff;">${escapeHtml(lead.firm_name)}</div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Contact: ${escapeHtml(lead.contact_name || 'Architect')} • ${escapeHtml(lead.city || 'City')}</div>
          </div>
          <span class="status-pill interested">🔥 HOT CONVERSION</span>
        </div>

        <div style="margin: 12px 0; font-size:12px; color:var(--text-main); background:#0c1017; padding:10px 14px; border-radius:8px; border:1px solid rgba(255,255,255,0.06);">
          <div style="color:var(--text-dim); font-size:11px; margin-bottom:4px;">Lead Contact Coordinates:</div>
          <div>✉️ <strong>${escapeHtml(lead.email)}</strong></div>
          <div>📱 <strong>${escapeHtml(lead.mobile || 'Needs Mobile')}</strong></div>
        </div>

        <div style="display:flex; gap:10px;">
          <button class="btn btn-emerald" style="flex:1; justify-content:center;" onclick="initiateWhatsApp(${lead.id})">
            <i data-lucide="message-circle"></i>
            <span>Launch WhatsApp Closing Chat</span>
          </button>
        </div>
      </div>
    `).join('');

    initLucide();
  } catch (e) {
    console.error('Error loading hot leads', e);
  }
}

// ----------------- INSTANT WHATSAPP HANDOFF -----------------
window.initiateWhatsApp = async function(leadId) {
  try {
    const res = await fetch(`/api/leads/${leadId}/whatsapp-handoff`, { method: 'POST' });
    const data = await res.json();
    if (data.success && data.whatsapp_url) {
      showToast('Opening WhatsApp closing chat with prefilled lookbook pitch...', 'success');
      window.open(data.whatsapp_url, '_blank');
      loadAnalytics();
      loadKanban();
    }
  } catch (e) {
    showToast(`WhatsApp handoff failed: ${e.message}`, 'error');
  }
};

// ----------------- CSV UPLOAD & CLEANING -----------------
function initDropzone() {
  const dropzone = document.getElementById('csv-dropzone');
  const fileInput = document.getElementById('csv-file-input');

  dropzone.addEventListener('click', () => fileInput.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('dragover');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  });

  fileInput.addEventListener('change', () => {
    if (fileInput.files.length > 0) {
      uploadFile(fileInput.files[0]);
    }
  });
}

async function uploadFile(file) {
  showToast(`Parsing and validating ${file.name}...`, 'info');
  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload-csv', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      showToast(`Cleaned & Imported ${data.valid_leads_count} valid leads!`, 'success');
      
      const summaryCard = document.getElementById('clean-summary-card');
      summaryCard.style.display = 'block';
      document.getElementById('sum-total-rows').textContent = data.total_rows;
      document.getElementById('sum-valid-rows').textContent = data.valid_leads_count;
      document.getElementById('sum-bad-emails').textContent = data.dropped_invalid_email;
      document.getElementById('sum-duplicates').textContent = data.dropped_duplicates;

      loadAnalytics();
      loadKanban();
      loadLeads();
    } else {
      showToast(`Error: ${data.detail || data.error}`, 'error');
    }
  } catch (e) {
    showToast(`Upload failed: ${e.message}`, 'error');
  }
}

// ----------------- LEADS DATABASE -----------------
async function loadLeads() {
  try {
    const res = await fetch('/api/leads');
    const data = await res.json();
    state.leads = data.leads || [];

    const tbody = document.getElementById('leads-table-body');
    if (!tbody) return;

    tbody.innerHTML = state.leads.map(lead => `
      <tr>
        <td><strong>${escapeHtml(lead.firm_name)}</strong></td>
        <td>${escapeHtml(lead.contact_name || '—')}</td>
        <td style="font-family:'JetBrains Mono', monospace; font-size:12px;">${escapeHtml(lead.email)}</td>
        <td>${escapeHtml(lead.city || '—')}</td>
        <td>${escapeHtml(lead.mobile || '—')}</td>
        <td>
          <span class="status-pill ${lead.is_hot ? 'interested' : 'ready'}">${lead.status}</span>
        </td>
        <td>
          ${lead.is_hot ? `
            <button class="btn btn-emerald btn-sm" onclick="initiateWhatsApp(${lead.id})">WhatsApp</button>
          ` : `
            <button class="btn btn-secondary btn-sm" onclick="generateSingleDraft(${lead.id})">Draft</button>
          `}
        </td>
      </tr>
    `).join('') || '<tr><td colspan="7" style="text-align:center; padding:24px; color:var(--text-dim);">No leads in database. Upload raw CSV to start.</td></tr>';
  } catch (e) {
    console.error('Error loading leads', e);
  }
}

// ----------------- EDIT DRAFT & MODAL -----------------
function initModals() {
  document.getElementById('btn-close-edit-modal').addEventListener('click', closeEditModal);
  document.getElementById('btn-cancel-draft').addEventListener('click', closeEditModal);

  document.getElementById('tab-btn-text').addEventListener('click', () => {
    document.getElementById('tab-btn-text').classList.add('active');
    document.getElementById('tab-btn-html').classList.remove('active');
    document.getElementById('tab-content-text').style.display = 'flex';
    document.getElementById('tab-content-html').style.display = 'none';
  });

  document.getElementById('tab-btn-html').addEventListener('click', () => {
    document.getElementById('tab-btn-html').classList.add('active');
    document.getElementById('tab-btn-text').classList.remove('active');
    document.getElementById('tab-content-text').style.display = 'none';
    document.getElementById('tab-content-html').style.display = 'block';
  });

  document.getElementById('btn-save-draft').addEventListener('click', saveDraftChanges);
  document.getElementById('btn-approve-draft').addEventListener('click', async () => {
    await saveDraftChanges();
    if (state.activeEditingThreadId) {
      await approveDraft(state.activeEditingThreadId);
      closeEditModal();
    }
  });

  // Batch approve
  document.getElementById('btn-batch-approve-all').addEventListener('click', async () => {
    try {
      const res = await fetch('/api/threads/batch-approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ all_drafts: true })
      });
      const data = await res.json();
      showToast(`Batch approved ${data.approved_count} drafts for sending!`, 'success');
      loadKanban();
      loadAnalytics();
    } catch (e) {
      showToast(e.message, 'error');
    }
  });

  // Simulate reply modal
  document.getElementById('btn-open-simulate-modal')?.addEventListener('click', openSimulateModal);
  document.getElementById('btn-close-sim-modal').addEventListener('click', closeSimulateModal);
  document.getElementById('btn-cancel-sim').addEventListener('click', closeSimulateModal);
  document.getElementById('btn-execute-sim').addEventListener('click', executeSimulateReply);
}

window.openEditModal = async function(threadId, leadId) {
  if (!threadId) {
    // Generate draft first
    await generateSingleDraft(leadId);
    return;
  }

  state.activeEditingThreadId = threadId;
  state.activeEditingLeadId = leadId;

  try {
    const res = await fetch(`/api/threads/${threadId}`);
    const thread = await res.json();

    document.getElementById('modal-lead-firm').textContent = thread.lead?.firm_name || 'Studio Draft';
    document.getElementById('modal-lead-meta').textContent = `${thread.lead?.email || ''} • ${thread.lead?.city || ''}`;
    document.getElementById('modal-subject-input').value = thread.subject || '';
    document.getElementById('modal-body-input').value = thread.body_text || '';

    // Set iframe HTML
    const iframe = document.getElementById('modal-html-iframe');
    iframe.srcdoc = thread.body_html || '';

    document.getElementById('modal-edit-draft').classList.add('active');
  } catch (e) {
    showToast(`Failed to load thread: ${e.message}`, 'error');
  }
};

function closeEditModal() {
  document.getElementById('modal-edit-draft').classList.remove('active');
}

async function saveDraftChanges() {
  if (!state.activeEditingThreadId) return;

  const subject = document.getElementById('modal-subject-input').value;
  const bodyText = document.getElementById('modal-body-input').value;

  try {
    const res = await fetch(`/api/threads/${state.activeEditingThreadId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subject, body_text: bodyText })
    });
    const data = await res.json();
    if (data.success) {
      showToast('Draft changes saved!', 'success');
      loadKanban();
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

window.approveDraft = async function(threadId) {
  try {
    const res = await fetch(`/api/threads/${threadId}/approve`, { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('Email draft approved for automated dispatch!', 'success');
      loadKanban();
      loadAnalytics();
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.generateSingleDraft = async function(leadId) {
  showToast('Connecting to Gemini AI to craft bespoke partnership email...', 'info');
  try {
    const res = await fetch('/api/generate-drafts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Draft generated for lead #${leadId}!`, 'success');
      loadKanban();
      loadAnalytics();
      if (data.thread_id) {
        openEditModal(data.thread_id, leadId);
      }
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
};

// ----------------- SIMULATE REPLY MODAL -----------------
function openSimulateModal() {
  const select = document.getElementById('sim-lead-select');
  select.innerHTML = state.leads.map(l => `
    <option value="${l.id}">${escapeHtml(l.firm_name)} (${escapeHtml(l.email)})</option>
  `).join('') || '<option value="">No leads available</option>';

  document.getElementById('modal-simulate-reply').classList.add('active');
}

function closeSimulateModal() {
  document.getElementById('modal-simulate-reply').classList.remove('active');
}

async function executeSimulateReply() {
  const leadId = parseInt(document.getElementById('sim-lead-select').value);
  const sentiment = document.getElementById('sim-sentiment-select').value;
  const sampleText = document.getElementById('sim-message-input').value.trim() || null;

  if (!leadId) {
    showToast('Please select a lead', 'error');
    return;
  }

  showToast(`Simulating ${sentiment} reply...`, 'info');
  try {
    const res = await fetch('/api/campaign/simulate-reply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lead_id: leadId, sentiment, sample_text: sampleText })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Reply Simulated: Tagged as '${data.sentiment}'. Hot Lead: ${data.is_hot}`, 'success');
      closeSimulateModal();
      loadAnalytics();
      loadKanban();
      if (data.is_hot) {
        switchView('hotleads');
      }
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ----------------- DOMAIN SETTINGS & HANDSHAKE -----------------
function initSettingsForm() {
  const dailyRange = document.getElementById('setting-daily-limit');
  const dailyVal = document.getElementById('val-daily-limit');
  dailyRange.addEventListener('input', () => {
    dailyVal.textContent = dailyRange.value;
  });

  const form = document.getElementById('settings-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('btn-save-settings');
    btn.disabled = true;
    showToast('Saving settings & testing live domain handshake...', 'info');

    const payload = {
      smtp_server: document.getElementById('setting-smtp-server').value,
      smtp_port: parseInt(document.getElementById('setting-smtp-port').value),
      smtp_email: document.getElementById('setting-smtp-email').value,
      smtp_password: document.getElementById('setting-smtp-password').value,
      smtp_use_tls: document.getElementById('setting-smtp-tls').checked,
      sender_name: document.getElementById('setting-sender-name').value,
      imap_server: document.getElementById('setting-imap-server').value,
      imap_port: parseInt(document.getElementById('setting-imap-port').value),
      imap_email: document.getElementById('setting-imap-email').value,
      imap_password: document.getElementById('setting-imap-password').value,
      imap_use_ssl: true,
      simulation_mode: document.getElementById('setting-simulation-mode').checked,
      gemini_api_key: document.getElementById('setting-gemini-key').value,
      gemini_model: document.getElementById('setting-gemini-model').value,
      daily_send_limit: parseInt(document.getElementById('setting-daily-limit').value),
      min_delay_seconds: parseInt(document.getElementById('setting-min-delay').value),
      max_delay_seconds: parseInt(document.getElementById('setting-max-delay').value),
      follow_up_days: parseInt(document.getElementById('setting-followup-days').value),
      raj_whatsapp_number: '+919876543210'
    };

    try {
      const res = await fetch('/api/settings/domain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      const resultCard = document.getElementById('handshake-result-card');
      resultCard.style.display = 'block';
      const details = document.getElementById('handshake-details');

      details.innerHTML = `
        <div style="display:flex; justify-content:space-between; padding:8px; background:#161924; border-radius:6px;">
          <span>SMTP Outbound Handshake:</span>
          <strong style="color:${data.smtp_status?.includes('Failed') ? 'var(--rose)' : 'var(--emerald)'};">${data.smtp_status}</strong>
        </div>
        <div style="display:flex; justify-content:space-between; padding:8px; background:#161924; border-radius:6px;">
          <span>IMAP Inbound Handshake:</span>
          <strong style="color:${data.imap_status?.includes('Failed') ? 'var(--rose)' : 'var(--emerald)'};">${data.imap_status}</strong>
        </div>
        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">${data.message}</div>
      `;

      showToast('Domain settings saved successfully!', 'success');
      loadAnalytics();
    } catch (err) {
      showToast(`Handshake failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
    }
  });
}

async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const s = await res.json();

    if (s.smtp_server) document.getElementById('setting-smtp-server').value = s.smtp_server;
    if (s.smtp_port) document.getElementById('setting-smtp-port').value = s.smtp_port;
    if (s.smtp_email) document.getElementById('setting-smtp-email').value = s.smtp_email;
    if (s.sender_name) document.getElementById('setting-sender-name').value = s.sender_name;
    if (s.imap_server) document.getElementById('setting-imap-server').value = s.imap_server;
    if (s.imap_port) document.getElementById('setting-imap-port').value = s.imap_port;
    if (s.imap_email) document.getElementById('setting-imap-email').value = s.imap_email;
    
    if (s.gemini_api_key_masked) document.getElementById('setting-gemini-key').placeholder = s.gemini_api_key_masked;
    if (s.gemini_model) document.getElementById('setting-gemini-model').value = s.gemini_model;

    if (s.daily_send_limit) {
      document.getElementById('setting-daily-limit').value = s.daily_send_limit;
      document.getElementById('val-daily-limit').textContent = s.daily_send_limit;
    }
    if (s.min_delay_seconds) document.getElementById('setting-min-delay').value = s.min_delay_seconds;
    if (s.max_delay_seconds) document.getElementById('setting-max-delay').value = s.max_delay_seconds;
    if (s.follow_up_days) document.getElementById('setting-followup-days').value = s.follow_up_days;
    if (s.simulation_mode !== undefined) document.getElementById('setting-simulation-mode').checked = (s.simulation_mode === 'true');
  } catch (e) {
    console.error('Failed to load settings', e);
  }
}

// Helper: Escape HTML
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
