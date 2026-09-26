/**
 * STOCKSENSE - Delivery Orders (Outgoing Stock - Odoo WH/OUT) Module
 */

const deliveries = {
  list: [],
  selectedDelivery: null,

  async init() {
    await this.loadDeliveries();
  },

  async loadDeliveries() {
    try {
      this.list = await api.get('/api/deliveries');
      this.renderTable();
    } catch (e) {
      console.error('Failed to load deliveries', e);
      showToast('Error loading delivery orders', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('deliveries-table-body');
    if (!tbody) return;

    if (!this.list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="truck" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No delivery orders found. Create a new delivery order to ship products to customers.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.list.forEach(d => {
      let badgeClass = 'badge-draft';
      if (d.status === 'Waiting') badgeClass = 'badge-waiting';
      else if (d.status === 'Ready') badgeClass = 'badge-ready';
      else if (d.status === 'Picked') badgeClass = 'badge-picked';
      else if (d.status === 'Packed') badgeClass = 'badge-packed';
      else if (d.status === 'Done') badgeClass = 'badge-done';
      else if (d.status === 'Cancelled') badgeClass = 'badge-danger';

      html += `
        <tr>
          <td>
            <strong style="color:var(--text-primary);cursor:pointer;" onclick="deliveries.openProcessModal(${d.id})">
              ${d.reference_no}
            </strong>
          </td>
          <td>
            <div style="font-weight:500;">${d.customer_name}</div>
          </td>
          <td>
            <div>${d.warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${d.source_location_name}</div>
          </td>
          <td>
            ${d.scheduled_date}
          </td>
          <td>
            <strong>${d.total_requested_qty}</strong> units (${d.item_count} items)
          </td>
          <td>
            <span class="badge ${badgeClass}">${d.status}</span>
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-muted);">${d.responsible_user_name || 'Staff'}</span>
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:0.35rem;">
              <button class="btn btn-sm btn-outline" title="Process & Check Availability" onclick="deliveries.openProcessModal(${d.id})">
                <i data-lucide="external-link" style="width:14px;height:14px;"></i> View
              </button>
              ${d.status !== 'Done' && d.status !== 'Cancelled' ? `
                <button class="btn btn-sm btn-primary" title="Validate & Ship" data-permission="validate_delivery" onclick="deliveries.validateDelivery(${d.id})">
                  <i data-lucide="send" style="width:14px;height:14px;"></i> Ship
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

    document.getElementById('delivery-modal-title').textContent = 'Create Outbound Delivery Order';
    document.getElementById('del-form-customer').value = '';
    document.getElementById('del-form-date').value = new Date().toISOString().split('T')[0];
    document.getElementById('del-form-notes').value = '';

    const whSelect = document.getElementById('del-form-warehouse');
    whSelect.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    this.updateSourceLocations();

    const linesContainer = document.getElementById('delivery-items-lines');
    linesContainer.innerHTML = '';
    this.addItemLine();

    modals.open('modal-delivery-create');
  },

  updateSourceLocations() {
    const whId = parseInt(document.getElementById('del-form-warehouse').value);
    const locSelect = document.getElementById('del-form-location');
    const matched = products.locations.filter(l => l.warehouse_id === whId);
    locSelect.innerHTML = matched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
  },

  addItemLine(productId = '', requestedQty = 10) {
    const linesContainer = document.getElementById('delivery-items-lines');
    const rowId = `del-row-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;

    const prodOptions = products.list.map(p => `
      <option value="${p.id}" ${p.id == productId ? 'selected' : ''} data-price="${p.selling_price}">
        ${p.name} (${p.sku}) - Avail: ${p.available_stock}
      </option>
    `).join('');

    const row = document.createElement('div');
    row.id = rowId;
    row.className = 'form-grid-3';
    row.style.marginBottom = '0.5rem';
    row.innerHTML = `
      <div>
        <select class="form-control del-item-product" onchange="deliveries.onProductSelect('${rowId}')">
          <option value="">Select Product...</option>
          ${prodOptions}
        </select>
      </div>
      <div>
        <input type="number" class="form-control del-item-qty" value="${requestedQty}" min="1" placeholder="Quantity">
      </div>
      <div style="display:flex;gap:0.5rem;align-items:center;">
        <input type="number" class="form-control del-item-price" value="0.00" step="0.01" placeholder="Unit Price ($)" style="flex:1;">
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
    const select = row.querySelector('.del-item-product');
    const priceInput = row.querySelector('.del-item-price');
    const selectedOpt = select.options[select.selectedIndex];
    if (selectedOpt && selectedOpt.dataset.price) {
      priceInput.value = selectedOpt.dataset.price;
    }
  },

  async saveDelivery(e) {
    if (e) e.preventDefault();

    const customer = document.getElementById('del-form-customer').value.trim();
    const warehouseId = parseInt(document.getElementById('del-form-warehouse').value);
    const locationId = parseInt(document.getElementById('del-form-location').value);
    const date = document.getElementById('del-form-date').value;
    const notes = document.getElementById('del-form-notes').value.trim();

    const rows = document.querySelectorAll('#delivery-items-lines > div');
    const items = [];

    rows.forEach(r => {
      const pId = parseInt(r.querySelector('.del-item-product').value);
      const qty = parseFloat(r.querySelector('.del-item-qty').value);
      const price = parseFloat(r.querySelector('.del-item-price').value) || 0;
      if (pId && qty > 0) {
        items.push({ product_id: pId, requested_qty: qty, unit_price: price });
      }
    });

    if (!customer) {
      showToast('Customer name is required', 'warning');
      return;
    }

    if (!items.length) {
      showToast('Please add at least one product item', 'warning');
      return;
    }

    try {
      const res = await api.post('/api/deliveries', {
        customer_name: customer,
        source_warehouse_id: warehouseId,
        source_location_id: locationId,
        scheduled_date: date,
        notes: notes,
        items: items,
        responsible_user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message || 'Delivery order created!', 'success');
      modals.close('modal-delivery-create');
      await this.loadDeliveries();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async openProcessModal(deliveryId) {
    try {
      const d = await api.get(`/api/deliveries/${deliveryId}`);
      this.selectedDelivery = d;

      document.getElementById('dproc-ref').textContent = d.reference_no;
      document.getElementById('dproc-status').innerHTML = `<span class="badge badge-${d.status.toLowerCase()}">${d.status}</span>`;
      document.getElementById('dproc-customer').textContent = d.customer_name;
      document.getElementById('dproc-warehouse').textContent = d.warehouse_name;
      document.getElementById('dproc-location').textContent = d.source_location_name;
      document.getElementById('dproc-date').textContent = d.scheduled_date;
      document.getElementById('dproc-user').textContent = d.responsible_user_name || 'Staff';

      // Check stock availability
      const availCheck = await api.get(`/api/deliveries/${deliveryId}/check-availability`);
      const alertBox = document.getElementById('dproc-stock-alert');
      
      if (!availCheck.all_available && d.status !== 'Done') {
        alertBox.style.display = 'block';
        alertBox.className = 'badge-danger';
        alertBox.style.padding = '0.75rem';
        alertBox.style.borderRadius = '8px';
        alertBox.innerHTML = `
          <strong><i data-lucide="alert-triangle" style="width:16px;height:16px;display:inline-block;vertical-align:middle;"></i> Insufficient Stock Detected!</strong>
          <div style="font-size:0.8rem;margin-top:4px;">One or more items in this order exceed available inventory at ${d.source_location_name}.</div>
        `;
      } else {
        alertBox.style.display = 'none';
      }

      const tbody = document.getElementById('dproc-items-body');
      tbody.innerHTML = (availCheck.items || []).map(item => {
        const statusBadge = item.is_available 
          ? `<span class="badge badge-in-stock">Available</span>`
          : `<span class="badge badge-danger">Shortage: ${item.shortage}</span>`;

        return `
          <tr>
            <td>
              <div style="font-weight:600;">${item.product_name}</div>
              <div style="font-size:0.75rem;color:var(--text-muted);">${item.sku}</div>
            </td>
            <td><strong>${item.requested_qty}</strong></td>
            <td>${item.on_hand}</td>
            <td><span style="color:var(--status-waiting);">${item.reserved}</span></td>
            <td><strong style="color:var(--status-done);">${item.available}</strong></td>
            <td>${statusBadge}</td>
          </tr>
        `;
      }).join('');

      // Workflow buttons
      const reserveBtn = document.getElementById('btn-delivery-reserve');
      const pickBtn = document.getElementById('btn-delivery-pick');
      const packBtn = document.getElementById('btn-delivery-pack');
      const validateBtn = document.getElementById('btn-delivery-validate');

      if (reserveBtn) reserveBtn.style.display = (d.status === 'Draft' || d.status === 'Waiting') ? 'inline-flex' : 'none';
      if (pickBtn) pickBtn.style.display = (d.status === 'Ready') ? 'inline-flex' : 'none';
      if (packBtn) packBtn.style.display = (d.status === 'Picked') ? 'inline-flex' : 'none';
      if (validateBtn) validateBtn.style.display = (d.status !== 'Done' && d.status !== 'Cancelled') ? 'inline-flex' : 'none';

      modals.open('modal-delivery-process');
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      showToast('Error opening delivery order', 'error');
    }
  },

  async reserveStock() {
    if (!this.selectedDelivery) return;
    try {
      const res = await api.post(`/api/deliveries/${this.selectedDelivery.id}/reserve`, {
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });
      showToast(res.message, 'success');
      this.openProcessModal(this.selectedDelivery.id);
      this.loadDeliveries();
      products.loadProducts();
    } catch (e) {
      showToast(e.message, 'error');
    }
  },

  async pickItems() {
    if (!this.selectedDelivery) return;
    try {
      await api.post(`/api/deliveries/${this.selectedDelivery.id}/pick`);
      showToast('Items marked as Picked.', 'success');
      this.openProcessModal(this.selectedDelivery.id);
      this.loadDeliveries();
    } catch (e) {
      showToast(e.message, 'error');
    }
  },

  async packItems() {
    if (!this.selectedDelivery) return;
    try {
      await api.post(`/api/deliveries/${this.selectedDelivery.id}/pack`);
      showToast('Items packed and staged for dispatch.', 'success');
      this.openProcessModal(this.selectedDelivery.id);
      this.loadDeliveries();
    } catch (e) {
      showToast(e.message, 'error');
    }
  },

  async validateDelivery(deliveryId) {
    const id = deliveryId || (this.selectedDelivery ? this.selectedDelivery.id : null);
    if (!id) return;

    try {
      const res = await api.post(`/api/deliveries/${id}/validate`, {
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Inventory Manager',
        role: auth.currentUser ? auth.currentUser.role : 'Inventory Manager'
      });

      showToast(res.message, 'success');
      modals.close('modal-delivery-process');
      await this.loadDeliveries();
      products.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  printSlip() {
    if (!this.selectedDelivery) return;
    window.print();
  }
};
