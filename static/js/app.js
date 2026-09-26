/**
 * STOCKSENSE - Master Application Orchestrator & SPA Router
 */

// Modal Management
const modals = {
  open(modalId) {
    const el = document.getElementById(modalId);
    if (el) {
      el.classList.add('active');
      sounds.click();
    }
  },

  close(modalId) {
    const el = document.getElementById(modalId);
    if (el) {
      el.classList.remove('active');
    }
  },

  closeAll() {
    document.querySelectorAll('.modal-overlay').forEach(m => m.classList.remove('active'));
    barcodeScanner.stopCamera();
  }
};

// Router
const router = {
  currentView: 'dashboard',

  navigate(viewName) {
    this.currentView = viewName;

    // Update nav items active state
    document.querySelectorAll('.nav-item').forEach(item => {
      item.classList.toggle('active', item.dataset.view === viewName);
    });

    // Toggle view containers
    document.querySelectorAll('.view-container').forEach(view => {
      view.style.display = (view.id === `view-${viewName}`) ? 'flex' : 'none';
    });

    // Trigger view-specific data refresh
    if (viewName === 'dashboard') dashboard.loadData();
    else if (viewName === 'products') products.loadProducts();
    else if (viewName === 'receipts') receipts.loadReceipts();
    else if (viewName === 'deliveries') deliveries.loadDeliveries();
    else if (viewName === 'transfers') transfers.loadTransfers();
    else if (viewName === 'adjustments') adjustments.loadAdjustments();
    else if (viewName === 'stock-count') stockCount.init();
    else if (viewName === 'ledger') ledger.loadLedger();
    else if (viewName === 'warehouses') warehouses.loadAll();
    else if (viewName === 'reports') reports.init();
    else if (viewName === 'analytics') analytics.init();
    else if (viewName === 'audit') audit.loadLogs();

    sounds.click();
    window.scrollTo(0, 0);
  },

  refreshCurrentView() {
    this.navigate(this.currentView);
  }
};

// Notification Dropdown Manager
const notifications = {
  isOpen: false,

  async toggle() {
    this.isOpen = !this.isOpen;
    const drop = document.getElementById('notifications-dropdown');
    if (drop) {
      drop.style.display = this.isOpen ? 'block' : 'none';
      if (this.isOpen) {
        await this.loadList();
      }
    }
  },

  async loadList() {
    try {
      const data = await api.get('/api/notifications');
      const container = document.getElementById('notif-list-container');
      const badge = document.getElementById('notif-unread-badge');

      if (badge) {
        badge.style.display = data.unread_count > 0 ? 'block' : 'none';
        badge.textContent = data.unread_count || '';
      }

      if (!container) return;

      if (!data.notifications.length) {
        container.innerHTML = '<div style="color:var(--text-muted);padding:1rem;text-align:center;font-size:0.8rem;">No notifications.</div>';
        return;
      }

      container.innerHTML = data.notifications.map(n => `
        <div style="padding:0.6rem 0.75rem;border-bottom:1px solid var(--border-color);display:flex;gap:0.6rem;align-items:flex-start;">
          <div style="width:8px;height:8px;border-radius:50%;background:${n.severity === 'danger' ? 'var(--status-danger)' : (n.severity === 'warning' ? 'var(--status-waiting)' : 'var(--status-done)')};margin-top:5px;flex-shrink:0;"></div>
          <div style="flex:1;font-size:0.8rem;">
            <div style="font-weight:600;color:var(--text-primary);">${n.title}</div>
            <div style="color:var(--text-secondary);font-size:0.75rem;margin-top:2px;">${n.message}</div>
            <div style="font-size:0.65rem;color:var(--text-muted);margin-top:3px;">${n.timestamp}</div>
          </div>
        </div>
      `).join('');
    } catch (e) {
      console.warn('Failed to load notifications', e);
    }
  },

  async markAllRead() {
    try {
      await api.post('/api/notifications/mark-read');
      this.loadList();
      showToast('All notifications marked as read.', 'info');
    } catch (e) {
      console.warn(e);
    }
  }
};

// Theme Switcher (Dark / Light)
const theme = {
  current: localStorage.getItem('stocksense_theme') || 'dark',

  init() {
    document.documentElement.setAttribute('data-theme', this.current);
    this.updateIcon();
  },

  toggle() {
    this.current = this.current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', this.current);
    localStorage.setItem('stocksense_theme', this.current);
    this.updateIcon();
    sounds.click();
  },

  updateIcon() {
    const icon = document.getElementById('theme-toggle-icon');
    if (icon) {
      icon.setAttribute('data-lucide', this.current === 'dark' ? 'sun' : 'moon');
      if (window.lucide) lucide.createIcons();
    }
  }
};

// Global Hotkeys & Setup
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    modals.closeAll();
    const chat = document.getElementById('chat-drawer');
    if (chat && chat.classList.contains('open')) assistant.toggle();
    const notif = document.getElementById('notifications-dropdown');
    if (notif && notif.style.display === 'block') notifications.toggle();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const s = document.getElementById('global-search-input');
    if (s) s.focus();
  }
});

// App Bootstrapper
window.addEventListener('DOMContentLoaded', async () => {
  theme.init();
  auth.init();

  // If user is already logged in, initialize all modules
  if (auth.isLoggedIn()) {
    await Promise.all([
      products.init(),
      receipts.init(),
      deliveries.init(),
      transfers.init(),
      adjustments.init(),
      ledger.init(),
      warehouses.init(),
      dashboard.init()
    ]);
    demoGuide.renderBanner();
  }

  // Periodic notification checker (every 30s)
  setInterval(() => {
    if (auth.isLoggedIn()) notifications.loadList();
  }, 30000);

  if (window.lucide) lucide.createIcons();
});
