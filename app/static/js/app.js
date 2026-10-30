/**
 * app.js — LoopClose client-side logic
 * Scope: toasts, tabs, copy-to-clipboard, "Viewing as" change, auto-dismiss.
 * Target: ≤ 80 lines; no framework.
 */

/* ── Toasts ────────────────────────────────────────────── */
function showToast({ type = 'info', message = '' }) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'status');
  toast.innerHTML = `
    <div class="toast-accent"></div>
    <div class="toast-body">${escapeHtml(message)}</div>
    <button class="toast-close" aria-label="Dismiss" onclick="this.closest('.toast').remove()">
      <svg width="14" height="14"><use href="#icon-x"/></svg>
    </button>`;
  container.appendChild(toast);

  // Auto-dismiss after 5 s
  setTimeout(() => toast.remove(), 5000);
}

// HTMX event → toast (server sends: HX-Trigger: {"toast": {"type":"success","message":"…"}})
document.body.addEventListener('toast', (e) => showToast(e.detail));

/* ── Tabs (active state via URL hash / hx-push-url) ─────── */
function activateTab(href) {
  document.querySelectorAll('.tab-link').forEach(el => {
    el.classList.toggle('active', el.getAttribute('href') === href);
    el.setAttribute('aria-selected', el.classList.contains('active') ? 'true' : 'false');
  });
}

// Activate the tab matching the current URL on load and popstate
function syncTabsToUrl() {
  const tabLinks = document.querySelectorAll('.tab-link');
  if (!tabLinks.length) return;
  const current = window.location.pathname + window.location.search;
  let matched = false;
  tabLinks.forEach(el => {
    const active = el.getAttribute('href') === current || el.getAttribute('hx-get') === current;
    el.classList.toggle('active', active);
    if (active) matched = true;
  });
  if (!matched && tabLinks[0]) tabLinks[0].classList.add('active');
}

window.addEventListener('popstate', syncTabsToUrl);
document.addEventListener('DOMContentLoaded', syncTabsToUrl);

/* ── Copy to clipboard ──────────────────────────────────── */
function copyText(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.textContent || el.value || '';
  navigator.clipboard.writeText(text).then(() => {
    showToast({ type: 'success', message: 'Copied to clipboard.' });
  }).catch(() => {
    showToast({ type: 'info', message: 'Could not copy — please select and copy manually.' });
  });
}

/* ── Utility ────────────────────────────────────────────── */
function escapeHtml(str) {
  return str.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
