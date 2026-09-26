/**
 * STOCKSENSE - Inventory Adjustments (Physical Count vs System Stock) Module
 */

const adjustments = {
  list: [],

  async init() {
    await this.loadAdjustments();
  },

  async loadAdjustments() {
    try {
      this.list = await api.get('/api/adjustments');
      this.renderTable();
    } catch (e) {
      console.error('Failed to load adjustments', e);
      showToast('Error loading adjustments', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('adjustments-table-body');
    if (!tbody) return;

    if (!this.list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="sliders" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No inventory adjustments recorded. Perform an adjustment to reconcile physical stock discrepancies.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.list.forEach(a => {
      const diffColor = a.diff_qty > 0 ? 'var(--status-done)' : (a.diff_qty < 0 ? 'var(--status-danger)' : 'var(--text-muted)');
      const diffSign = a.diff_qty > 0 ? '+' : '';

      html += `
        <tr>
          <td>
            <strong>${a.reference_no}</strong>
            <div style="font-size:0.75rem;color:var(--text-muted);">${a.created_at}</div>
          </td>
          <td>
            <div style="font-weight:600;">${a.product_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${a.sku}</div>
          </td>
          <td>
            <div>${a.warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${a.location_name}</div>
          </td>
          <td>
            ${a.system_qty} ${a.uom || ''}
          </td>
          <td>
            <strong>${a.counted_qty}</strong> ${a.uom || ''}
          </td>
          <td>
            <strong style="color:${diffColor};">${diffSign}${a.diff_qty}</strong>
          </td>
          <td>
            <span class="badge badge-waiting">${a.reason}</span>
            ${a.notes ? `<div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">${a.notes}</div>` : ''}
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-muted);">${a.user_name || 'Staff'}</span>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  async openCreateModal(prefillProductId = null) {
    if (!products.warehouses.length) await products.loadWarehouses();
    if (!products.list.length) await products.loadProducts();

    document.getElementById('adj-form-reason').value = 'Counting Error';
    document.getElementById('adj-form-notes').value = '';

    // Populate Warehouses & Products
    const whSelect = document.getElementById('adj-form-warehouse');
    whSelect.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    this.updateLocations();

    const prodSelect = document.getElementById('adj-form-product');
    prodSelect.innerHTML = products.list.map(p => `
      <option value="${p.id}" ${p.id === prefillProductId ? 'selected' : ''}>
        ${p.name} (${p.sku})
      </option>
    `).join('');

    this.fetchSystemStock();
    modals.open('modal-adjustment-create');
  },

  updateLocations() {
    const whId = parseInt(document.getElementById('adj-form-warehouse').value);
    const locSelect = document.getElementById('adj-form-location');
    const matched = products.locations.filter(l => l.warehouse_id === whId);
    locSelect.innerHTML = matched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
    this.fetchSystemStock();
  },

  async fetchSystemStock() {
    const pId = parseInt(document.getElementById('adj-form-product').value);
    const locId = parseInt(document.getElementById('adj-form-location').value);
    
    if (!pId || !locId) return;

    try {
      const p = await api.get(`/api/products/${pId}`);
      const locMatch = p.locations ? p.locations.find(l => l.location_id === locId) : null;
      const systemQty = locMatch ? locMatch.on_hand : 0;

      document.getElementById('adj-form-system-qty').value = systemQty;
      document.getElementById('adj-form-counted-qty').value = systemQty;
      this.recalculateDiff();
    } catch (e) {
      console.warn(e);
    }
  },

  recalculateDiff() {
    const system = parseFloat(document.getElementById('adj-form-system-qty').value) || 0;
    const counted = parseFloat(document.getElementById('adj-form-counted-qty').value) || 0;
    const diff = counted - system;

    const diffEl = document.getElementById('adj-form-diff-display');
    if (diffEl) {
      const sign = diff > 0 ? '+' : '';
      const color = diff > 0 ? 'var(--status-done)' : (diff < 0 ? 'var(--status-danger)' : 'var(--text-muted)');
      diffEl.innerHTML = `<span style="color:${color};font-weight:700;font-size:1.1rem;">${sign}${diff} units</span>`;
    }
  },

  async saveAdjustment(e) {
    if (e) e.preventDefault();

    const productId = parseInt(document.getElementById('adj-form-product').value);
    const warehouseId = parseInt(document.getElementById('adj-form-warehouse').value);
    const locationId = parseInt(document.getElementById('adj-form-location').value);
    const countedQty = parseFloat(document.getElementById('adj-form-counted-qty').value);
    const reason = document.getElementById('adj-form-reason').value;
    const notes = document.getElementById('adj-form-notes').value.trim();

    if (isNaN(countedQty) || countedQty < 0) {
      showToast('Please enter a valid non-negative counted stock quantity', 'warning');
      return;
    }

    try {
      const res = await api.post('/api/adjustments', {
        product_id: productId,
        warehouse_id: warehouseId,
        location_id: locationId,
        counted_qty: countedQty,
        reason: reason,
        notes: notes,
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Inventory Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message || 'Stock adjustment applied!', 'success');
      modals.close('modal-adjustment-create');
      await this.loadAdjustments();
      products.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
};
