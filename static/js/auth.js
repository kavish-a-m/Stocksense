/**
 * STOCKSENSE - Authentication & Role-Based Access Control (RBAC)
 */

const auth = {
  currentUser: null,
  usersList: [],

  init() {
    const savedUser = localStorage.getItem('stocksense_user');
    if (savedUser) {
      try {
        this.currentUser = JSON.parse(savedUser);
      } catch (e) {
        this.currentUser = null;
      }
    }
    this.fetchUsers();
    this.updateUI();
  },

  async fetchUsers() {
    try {
      this.usersList = await api.get('/api/auth/users');
      this.renderRoleSwitcher();
    } catch (e) {
      console.warn('Could not fetch users list:', e);
    }
  },

  isLoggedIn() {
    return !!this.currentUser;
  },

  getRole() {
    return this.currentUser ? this.currentUser.role : 'Viewer';
  },

  hasPermission(permission) {
    const role = this.getRole();
    if (role === 'Admin') return true;

    const rolePermissions = {
      'Inventory Manager': [
        'view_dashboard', 'manage_products', 'create_product', 'edit_product',
        'manage_receipts', 'validate_receipt',
        'manage_deliveries', 'validate_delivery', 'reserve_delivery',
        'manage_transfers', 'validate_transfer',
        'manage_adjustments', 'apply_adjustment',
        'view_ledger', 'view_reports', 'view_analytics', 'view_warehouses'
      ],
      'Warehouse Staff': [
        'view_dashboard', 'view_products',
        'manage_receipts', 'validate_receipt',
        'manage_deliveries', 'pick_delivery', 'pack_delivery', 'validate_delivery',
        'manage_transfers', 'validate_transfer',
        'apply_adjustment', 'stock_count',
        'view_ledger', 'scan_barcode'
      ],
      'Viewer': [
        'view_dashboard', 'view_products', 'view_ledger', 'view_reports'
      ]
    };

    const allowed = rolePermissions[role] || [];
    return allowed.includes(permission);
  },

  async login(email, password) {
    try {
      const res = await api.post('/api/auth/login', { email, password });
      this.currentUser = res.user;
      localStorage.setItem('stocksense_token', res.token);
      localStorage.setItem('stocksense_user', JSON.stringify(res.user));
      showToast(`Welcome back, ${res.user.name}! (${res.user.role})`, 'success');
      this.updateUI();
      router.navigate('dashboard');
      return true;
    } catch (err) {
      showToast(err.message || 'Login failed', 'error');
      return false;
    }
  },

  async quickSwitchUser(userId) {
    const target = this.usersList.find(u => u.id === userId);
    if (!target) return;

    this.currentUser = target;
    localStorage.setItem('stocksense_user', JSON.stringify(target));
    showToast(`Switched active role to: ${target.name} (${target.role})`, 'info');
    sounds.click();
    this.updateUI();
    router.refreshCurrentView();
  },

  logout() {
    this.currentUser = null;
    localStorage.removeItem('stocksense_token');
    localStorage.removeItem('stocksense_user');
    showToast('Logged out successfully.', 'info');
    this.updateUI();
    router.navigate('login');
  },

  renderRoleSwitcher() {
    const selector = document.getElementById('role-switcher-dropdown');
    if (!selector) return;

    if (!this.usersList.length) return;

    let html = '';
    this.usersList.forEach(u => {
      const isCurrent = this.currentUser && this.currentUser.id === u.id;
      html += `
        <div class="user-switch-item ${isCurrent ? 'selected' : ''}" onclick="auth.quickSwitchUser(${u.id})" style="padding:0.5rem 0.75rem;cursor:pointer;display:flex;align-items:center;gap:0.6rem;border-radius:6px;margin-bottom:2px;background:${isCurrent ? 'var(--bg-tertiary)' : 'transparent'};">
          <img src="${u.avatar || 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=50'}" style="width:24px;height:24px;border-radius:50%;object-fit:cover;">
          <div style="flex:1;">
            <div style="font-size:0.8rem;font-weight:600;color:var(--text-primary);">${u.name}</div>
            <div style="font-size:0.7rem;color:var(--text-muted);">${u.role}</div>
          </div>
          ${isCurrent ? '<i data-lucide="check" style="width:14px;height:14px;color:var(--status-done);"></i>' : ''}
        </div>
      `;
    });
    selector.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  updateUI() {
    const authWrapper = document.getElementById('app-main-view');
    const loginWrapper = document.getElementById('auth-view');
    const userDisplay = document.getElementById('top-user-name');
    const roleDisplay = document.getElementById('top-user-role');
    const avatarDisplay = document.getElementById('top-user-avatar');

    if (this.isLoggedIn()) {
      if (authWrapper) authWrapper.style.display = 'flex';
      if (loginWrapper) loginWrapper.style.display = 'none';

      if (userDisplay) userDisplay.textContent = this.currentUser.name;
      if (roleDisplay) roleDisplay.textContent = this.currentUser.role;
      if (avatarDisplay) avatarDisplay.src = this.currentUser.avatar || 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100';

      this.enforceRBAC();
    } else {
      if (authWrapper) authWrapper.style.display = 'none';
      if (loginWrapper) loginWrapper.style.display = 'flex';
    }
  },

  enforceRBAC() {
    const rbacElements = document.querySelectorAll('[data-permission]');
    rbacElements.forEach(el => {
      const perm = el.getAttribute('data-permission');
      if (!this.hasPermission(perm)) {
        el.style.display = 'none';
      } else {
        el.style.display = '';
      }
    });
  }
};
