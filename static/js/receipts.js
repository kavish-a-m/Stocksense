/**
 * STOCKSENSE - Receipts (Incoming Goods - Odoo WH/IN) Module
 */

const receipts = {
  list: [],
  selectedReceipt: null,

  async init() {
    await this.loadReceipts();
  },

  async loadReceipts() {
    try {
      this.list = await api.get('/api/receipts');
      this.renderTable();
    } catch (e) {
      console.error('Failed to load receipts', e);
      showToast('Error loading receipts', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('receipts-table-body');
    if (!tbody) return;

    if (!this.list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="inbox" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No incoming receipts found. Create a new receipt to accept goods from vendors.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.list.forEach(r => {
      let badgeClass = 'badge-draft';
      if (r.status === 'Waiting') badgeClass = 'badge-waiting';
      else if (r.status === 'Ready') badgeClass = 'badge-ready';
      else if (r.status === 'Done') badgeClass = 'badge-done';
      else if (r.status === 'Cancelled') badgeClass = 'badge-danger';

      html += `
        <tr>
          <td>
            <strong style="color:var(--text-primary);cursor:pointer;" onclick="receipts.openProcessModal(${r.id})">
              ${r.reference_no}
            </strong>
          </td>
          <td>
            <div style="font-weight:500;">${r.supplier_name}</div>
          </td>
          <td>
            <div>${r.warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${r.destination_location_name}</div>
          </td>
          <td>
            ${r.scheduled_date}
          </td>
          <td>
            <strong>${r.total_expected_qty}</strong> units (${r.item_count} items)
          </td>
          <td>
            <span class="badge ${badgeClass}">${r.status}</span>
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-muted);">${r.responsible_user_name || 'Staff'}</span>
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:0.35rem;">
              <button class="btn btn-sm btn-outline" title="Process & View" onclick="receipts.openProcessModal(${r.id})">
                <i data-lucide="external-link" style="width:14px;height:14px;"></i> View
              </button>
              ${r.status !== 'Done' && r.status !== 'Cancelled' ? `
                <button class="btn btn-sm btn-success" title="Validate & Receive Stock" data-permission="validate_receipt" onclick="receipts.validateReceipt(${r.id})">
                  <i data-lucide="check" style="width:14px;height:14px;"></i> Validate
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

    document.getElementById('receipt-modal-title').textContent = 'Create Inbound Receipt';
    document.getElementById('rec-form-supplier').value = '';
    document.getElementById('rec-form-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('rec-form-notes').value = '';

    // Populate Warehouses & Locations
    const whSelect = document.getElementById('rec-form-warehouse');
    whSelect.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    this.updateDestinationLocations();

    // Reset Item rows
    const linesContainer = document.getElementById('receipt-items-lines');
    linesContainer.innerHTML = '';
    this.addItemLine();

    modals.open('modal-receipt-create');
  },

  updateDestinationLocations() {
    const whId = parseInt(document.getElementById('rec-form-warehouse').value);
    const locSelect = document.getElementById('rec-form-location');
    const matched = products.locations.filter(l => l.warehouse_id === whId);
    locSelect.innerHTML = matched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
  },

  addItemLine(productId = '', expectedQty = 50) {
    const linesContainer = document.getElementById('receipt-items-lines');
    const rowId = `rec-row-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;

    const prodOptions = products.list.map(p => `
      <option value="${p.id}" ${p.id == productId ? 'selected' : ''} data-cost="${p.cost_price}">
        ${p.name} (${p.sku})
      </option>
    `).join('');

    const row = document.createElement('div');
    row.id = rowId;
    row.className = 'form-grid-3';
    row.style.marginBottom = '0.5rem';
    row.innerHTML = `
      <div>
        <select class="form-control rec-item-product" onchange="receipts.onProductSelect('${rowId}')">
          <option value="">Select Product...</option>
          ${prodOptions}
        </select>
      </div>
      <div>
        <input type="number" class="form-control rec-item-qty" value="${expectedQty}" min="1" placeholder="Quantity">
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <input type="number" class="form-control rec-item-cost" value="0.00" step="0.01" placeholder="Unit Cost ($)" style="flex:1;">
        <button type="button" class="btn btn-sm btn-danger" onclick="document.getElementById('${rowId}').remove()">
          <i data-lucide="x" style="width:12px;height:12px;"></i>
        </button>
      </div>
    `;

    linesContainer.appendChild(row);
    this.onProductSelect(rowId);
    if (window.lucide) lucide.createIcons();
  },

  onProductSelect(rowId) {
    const row = document.getElementById(rowId);
    if (!row) return;
    const select = row.querySelector('.rec-item-product');
    const costInput = row.querySelector('.rec-item-cost');
    const selectedOpt = select.options[select.selectedIndex];
    if (selectedOpt && selectedOpt.dataset.cost) {
      costInput.value = selectedOpt.dataset.cost;
    }
  },

  quickCreateFromReorder(productId, productName, suggestedQty) {
    this.openCreateModal();
    document.getElementById('rec-form-supplier').value = 'Quick Restock Vendor';
    document.getElementById('rec-form-notes').value = `Automated restock order based on Smart Reorder calculation.`;

    const linesContainer = document.getElementById('receipt-items-lines');
    linesContainer.innerHTML = '';
    this.addItemLine(productId, suggestedQty);
  },

  async saveReceipt(e) {
    if (e) e.preventDefault();

    const supplier = document.getElementById('rec-form-supplier').value.trim();
    const warehouseId = parseInt(document.getElementById('rec-form-warehouse').value);
    const locationId = parseInt(document.getElementById('rec-form-location').value);
    const date = document.getElementById('rec-form-date').value;
    const notes = document.getElementById('rec-form-notes').value.trim();

    const rows = document.querySelectorAll('#receipt-items-lines > div');
    const items = [];

    rows.forEach(r => {
      const pId = parseInt(r.querySelector('.rec-item-product').value);
      const qty = parseFloat(r.querySelector('.rec-item-qty').value);
      const cost = parseFloat(r.querySelector('.rec-item-cost').value) || 0;
      if (pId && qty > 0) {
        items.push({ product_id: pId, expected_qty: qty, unit_cost: cost });
      }
    });

    if (!supplier) {
      showToast('Supplier name is required', 'warning');
      return;
    }

    if (!items.length) {
      showToast('Please add at least one valid product and quantity', 'warning');
      return;
    }

    try {
      const res = await api.post('/api/receipts', {
        supplier_name: supplier,
        warehouse_id: warehouseId,
        destination_location_id: locationId,
        scheduled_date: date,
        notes: notes,
        items: items,
        responsible_user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message || 'Receipt created successfully!', 'success');
      modals.close('modal-receipt-create');
      await this.loadReceipts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async openProcessModal(receiptId) {
    try {
      const r = await api.get(`/api/receipts/${receiptId}`);
      this.selectedReceipt = r;

      document.getElementById('rproc-ref').textContent = r.reference_no;
      document.getElementById('rproc-status').innerHTML = `<span class="badge badge-${r.status.toLowerCase()}">${r.status}</span>`;
      document.getElementById('rproc-supplier').textContent = r.supplier_name;
      document.getElementById('rproc-warehouse').textContent = r.warehouse_name;
      document.getElementById('rproc-location').textContent = r.destination_location_name;
      document.getElementById('rproc-date').textContent = r.scheduled_date;
      document.getElementById('rproc-user').textContent = r.responsible_user_name || 'Staff';
      document.getElementById('rproc-notes').textContent = r.notes || 'None';

      const tbody = document.getElementById('rproc-items-body');
      tbody.innerHTML = r.items.map(item => `
        <tr>
          <td>
            <div style="font-weight:600;">${item.product_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${item.sku}</div>
          </td>
          <td>${item.expected_qty} ${item.uom}</td>
          <td><strong>${item.received_qty || item.expected_qty}</strong> ${item.uom}</td>
          <td>$${item.unit_cost.toFixed(2)}</td>
        </tr>
      `).join('');

      // Toggle action buttons
      const readyBtn = document.getElementById('btn-receipt-mark-ready');
      const validateBtn = document.getElementById('btn-receipt-validate');
      const printBtn = document.getElementById('btn-receipt-print');

      if (readyBtn) readyBtn.style.display = (r.status === 'Draft' || r.status === 'Waiting') ? 'inline-flex' : 'none';
      if (validateBtn) validateBtn.style.display = (r.status !== 'Done' && r.status !== 'Cancelled') ? 'inline-flex' : 'none';
      if (printBtn) printBtn.style.display = 'inline-flex';

      modals.open('modal-receipt-process');
    } catch (e) {
      showToast('Error opening receipt', 'error');
    }
  },

  async markReady(receiptId) {
    const id = receiptId || (this.selectedReceipt ? this.selectedReceipt.id : null);
    if (!id) return;
    try {
      await api.post(`/api/receipts/${id}/ready`);
      showToast('Receipt marked as Ready for receiving.', 'success');
      modals.close('modal-receipt-process');
      await this.loadReceipts();
      dashboard.loadData();
    } catch (e) {
      showToast(e.message, 'error');
    }
  },

  async validateReceipt(receiptId) {
    const id = receiptId || (this.selectedReceipt ? this.selectedReceipt.id : null);
    if (!id) return;

    try {
      const res = await api.post(`/api/receipts/${id}/validate`, {
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Inventory Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message, 'success');
      modals.close('modal-receipt-process');
      await this.loadReceipts();
      products.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  printSlip() {
    if (!this.selectedReceipt) return;
    window.print();
  }
};
