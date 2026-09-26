/**
 * STOCKSENSE - Internal Transfers (Odoo WH/INT) Module
 */

const transfers = {
  list: [],
  selectedTransfer: null,

  async init() {
    await this.loadTransfers();
  },

  async loadTransfers() {
    try {
      this.list = await api.get('/api/transfers');
      this.renderTable();
    } catch (e) {
      console.error('Failed to load transfers', e);
      showToast('Error loading internal transfers', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('transfers-table-body');
    if (!tbody) return;

    if (!this.list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="arrow-right-left" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No internal transfers found. Move stock between warehouses and locations effortlessly.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.list.forEach(t => {
      let badgeClass = 'badge-draft';
      if (t.status === 'Waiting') badgeClass = 'badge-waiting';
      else if (t.status === 'Ready') badgeClass = 'badge-ready';
      else if (t.status === 'Done') badgeClass = 'badge-done';
      else if (t.status === 'Cancelled') badgeClass = 'badge-danger';

      html += `
        <tr>
          <td>
            <strong style="color:var(--text-primary);cursor:pointer;" onclick="transfers.openProcessModal(${t.id})">
              ${t.reference_no}
            </strong>
          </td>
          <td>
            <div style="font-weight:600;">${t.src_warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${t.src_location_name}</div>
          </td>
          <td>
            <i data-lucide="arrow-right" style="width:16px;height:16px;color:var(--accent-primary);display:inline-block;vertical-align:middle;"></i>
          </td>
          <td>
            <div style="font-weight:600;">${t.dst_warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${t.dst_location_name}</div>
          </td>
          <td>
            <strong>${t.total_quantity}</strong> units (${t.item_count} items)
          </td>
          <td>
            <span class="badge ${badgeClass}">${t.status}</span>
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-muted);">${t.responsible_user_name || 'Staff'}</span>
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:0.35rem;">
              <button class="btn btn-sm btn-outline" title="View Transfer" onclick="transfers.openProcessModal(${t.id})">
                <i data-lucide="external-link" style="width:14px;height:14px;"></i> View
              </button>
              ${t.status !== 'Done' && t.status !== 'Cancelled' ? `
                <button class="btn btn-sm btn-primary" title="Complete Transfer" data-permission="validate_transfer" onclick="transfers.validateTransfer(${t.id})">
                  <i data-lucide="check" style="width:14px;height:14px;"></i> Complete
                </button>
              ` : ''}
            </div>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
    auth.enforceRBAC();
  },

  async openCreateModal() {
    if (!products.warehouses.length) await products.loadWarehouses();
    if (!products.list.length) await products.loadProducts();

    document.getElementById('transfer-modal-title').textContent = 'Create Internal Stock Transfer';
    document.getElementById('trf-form-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('trf-form-notes').value = '';

    const srcWh = document.getElementById('trf-form-src-wh');
    const dstWh = document.getElementById('trf-form-dst-wh');

    srcWh.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    dstWh.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');

    if (products.warehouses.length > 1) {
      dstWh.selectedIndex = 1;
    }

    this.updateLocations();

    const linesContainer = document.getElementById('transfer-items-lines');
    linesContainer.innerHTML = '';
    this.addItemLine();

    modals.open('modal-transfer-create');
  },

  updateLocations() {
    const srcWhId = parseInt(document.getElementById('trf-form-src-wh').value);
    const dstWhId = parseInt(document.getElementById('trf-form-dst-wh').value);

    const srcLoc = document.getElementById('trf-form-src-loc');
    const dstLoc = document.getElementById('trf-form-dst-loc');

    const srcMatched = products.locations.filter(l => l.warehouse_id === srcWhId);
    const dstMatched = products.locations.filter(l => l.warehouse_id === dstWhId);

    srcLoc.innerHTML = srcMatched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
    dstLoc.innerHTML = dstMatched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
  },

  addItemLine(productId = '', quantity = 10) {
    const linesContainer = document.getElementById('transfer-items-lines');
    const rowId = `trf-row-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;

    const prodOptions = products.list.map(p => `
      <option value="${p.id}" ${p.id == productId ? 'selected' : ''}>
        ${p.name} (${p.sku}) - Avail: ${p.available_stock}
      </option>
    `).join('');

    const row = document.createElement('div');
    row.id = rowId;
    row.className = 'form-grid-2';
    row.style.marginBottom = '0.5rem';
    row.innerHTML = `
      <div>
        <select class="form-control trf-item-product">
          <option value="">Select Product...</option>
          ${prodOptions}
        </select>
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <input type="number" class="form-control trf-item-qty" value="${quantity}" min="1" placeholder="Quantity" style="flex:1;">
        <button type="button" class="btn btn-sm btn-danger" onclick="document.getElementById('${rowId}').remove()">
          <i data-lucide="x" style="width:12px;height:12px;"></i>
        </button>
      </div>
    `;

    linesContainer.appendChild(row);
    if (window.lucide) lucide.createIcons();
  },

  async saveTransfer(e) {
    if (e) e.preventDefault();

    const srcWhId = parseInt(document.getElementById('trf-form-src-wh').value);
    const srcLocId = parseInt(document.getElementById('trf-form-src-loc').value);
    const dstWhId = parseInt(document.getElementById('trf-form-dst-wh').value);
    const dstLocId = parseInt(document.getElementById('trf-form-dst-loc').value);
    const date = document.getElementById('trf-form-date').value;
    const notes = document.getElementById('trf-form-notes').value.trim();

    if (srcLocId === dstLocId) {
      showToast('Source location and Destination location cannot be the same', 'warning');
      return;
    }

    const rows = document.querySelectorAll('#transfer-items-lines > div');
    const items = [];

    rows.forEach(r => {
      const pId = parseInt(r.querySelector('.trf-item-product').value);
      const qty = parseFloat(r.querySelector('.trf-item-qty').value);
      if (pId && qty > 0) {
        items.push({ product_id: pId, quantity: qty });
      }
    });

    if (!items.length) {
      showToast('Please add at least one product item to transfer', 'warning');
      return;
    }

    try {
      const res = await api.post('/api/transfers', {
        source_warehouse_id: srcWhId,
        source_location_id: srcLocId,
        dest_warehouse_id: dstWhId,
        dest_location_id: dstLocId,
        scheduled_date: date,
        notes: notes,
        items: items,
        responsible_user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message || 'Transfer order created!', 'success');
      modals.close('modal-transfer-create');
      await this.loadTransfers();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async openProcessModal(transferId) {
    try {
      const t = await api.get(`/api/transfers/${transferId}`);
      this.selectedTransfer = t;

      document.getElementById('tproc-ref').textContent = t.reference_no;
      document.getElementById('tproc-status').innerHTML = `<span class="badge badge-${t.status.toLowerCase()}">${t.status}</span>`;
      document.getElementById('tproc-src-wh').textContent = t.src_warehouse_name;
      document.getElementById('tproc-src-loc').textContent = t.src_location_name;
      document.getElementById('tproc-dst-wh').textContent = t.dst_warehouse_name;
      document.getElementById('tproc-dst-loc').textContent = t.dst_location_name;
      document.getElementById('tproc-date').textContent = t.scheduled_date;

      const tbody = document.getElementById('tproc-items-body');
      tbody.innerHTML = t.items.map(item => `
        <tr>
          <td>
            <div style="font-weight:600;">${item.product_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${item.sku}</div>
          </td>
          <td><strong>${item.quantity}</strong> ${item.uom}</td>
          <td>${item.src_on_hand || 0} ${item.uom}</td>
        </tr>
      `).join('');

      const readyBtn = document.getElementById('btn-transfer-ready');
      const validateBtn = document.getElementById('btn-transfer-validate');

      if (readyBtn) readyBtn.style.display = (t.status === 'Draft' || t.status === 'Waiting') ? 'inline-flex' : 'none';
      if (validateBtn) validateBtn.style.display = (t.status !== 'Done' && t.status !== 'Cancelled') ? 'inline-flex' : 'none';

      modals.open('modal-transfer-process');
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      showToast('Error opening transfer order', 'error');
    }
  },

  async validateTransfer(transferId) {
    const id = transferId || (this.selectedTransfer ? this.selectedTransfer.id : null);
    if (!id) return;

    try {
      const res = await api.post(`/api/transfers/${id}/validate`, {
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Inventory Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message, 'success');
      modals.close('modal-transfer-process');
      await this.loadTransfers();
      products.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
};
