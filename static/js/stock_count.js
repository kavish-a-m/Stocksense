/**
 * STOCKSENSE - Warehouse Physical Stock Count Mode (Cycle Counting)
 */

const stockCount = {
  currentLocationItems: [],

  async init() {
    this.populateSelectors();
  },

  populateSelectors() {
    const whSelect = document.getElementById('count-select-warehouse');
    if (!whSelect) return;

    whSelect.innerHTML = products.warehouses.map(w => `<option value="${w.id}">${w.name} (${w.code})</option>`).join('');
    this.updateLocations();
  },

  updateLocations() {
    const whId = parseInt(document.getElementById('count-select-warehouse').value);
    const locSelect = document.getElementById('count-select-location');
    const matched = products.locations.filter(l => l.warehouse_id === whId);
    locSelect.innerHTML = matched.map(l => `<option value="${l.id}">${l.name} (${l.code})</option>`).join('');
  },

  async loadLocationProducts() {
    const whId = parseInt(document.getElementById('count-select-warehouse').value);
    const locId = parseInt(document.getElementById('count-select-location').value);

    if (!locId) {
      showToast('Please select a location', 'warning');
      return;
    }

    try {
      // Fetch all products with location stock
      const allProds = await api.get('/api/products');
      const items = [];

      for (const p of allProds) {
        const pDetail = await api.get(`/api/products/${p.id}`);
        const locStock = pDetail.locations ? pDetail.locations.find(l => l.location_id === locId) : null;
        items.push({
          product_id: p.id,
          name: p.name,
          sku: p.sku,
          barcode: p.barcode,
          uom: p.uom,
          system_qty: locStock ? locStock.on_hand : 0,
          counted_qty: locStock ? locStock.on_hand : 0
        });
      }

      this.currentLocationItems = items;
      this.renderCountTable();
      showToast(`Loaded ${items.length} items for cycle counting at selected location.`, 'info');
    } catch (e) {
      showToast('Failed to load items for cycle count', 'error');
    }
  },

  renderCountTable() {
    const tbody = document.getElementById('stock-count-table-body');
    if (!tbody) return;

    if (!this.currentLocationItems.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:2rem;color:var(--text-muted);">Select a warehouse and location above, then click "Start Cycle Count".</td></tr>';
      return;
    }

    let html = '';
    this.currentLocationItems.forEach((item, idx) => {
      const diff = item.counted_qty - item.system_qty;
      const diffColor = diff === 0 ? 'var(--status-done)' : (diff > 0 ? '#3b82f6' : 'var(--status-danger)');

      html += `
        <tr id="count-row-${idx}">
          <td>
            <div style="font-weight:600;">${item.name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${item.sku}</div>
          </td>
          <td><code>${item.barcode}</code></td>
          <td><strong>${item.system_qty}</strong> ${item.uom}</td>
          <td style="width:140px;">
            <input type="number" class="form-control form-control-sm count-input-val" value="${item.counted_qty}" min="0" oninput="stockCount.onCountChange(${idx}, this.value)" style="font-weight:700;">
          </td>
          <td id="count-diff-${idx}">
            <strong style="color:${diffColor};">${diff > 0 ? '+' : ''}${diff} ${item.uom}</strong>
          </td>
          <td>
            <select class="form-control form-control-sm count-reason-select" style="font-size:0.78rem;">
              <option value="Counting Error">Counting Error</option>
              <option value="Damaged">Damaged</option>
              <option value="Lost">Lost</option>
              <option value="Expired">Expired</option>
              <option value="Theft">Theft</option>
              <option value="Data Correction">Data Correction</option>
            </select>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  },

  onCountChange(idx, val) {
    const item = this.currentLocationItems[idx];
    if (!item) return;

    const counted = parseFloat(val) || 0;
    item.counted_qty = counted;
    const diff = counted - item.system_qty;

    const diffEl = document.getElementById(`count-diff-${idx}`);
    if (diffEl) {
      const diffColor = diff === 0 ? 'var(--status-done)' : (diff > 0 ? '#3b82f6' : 'var(--status-danger)');
      diffEl.innerHTML = `<strong style="color:${diffColor};">${diff > 0 ? '+' : ''}${diff} ${item.uom}</strong>`;
    }
  },

  async applyAllCounts() {
    const whId = parseInt(document.getElementById('count-select-warehouse').value);
    const locId = parseInt(document.getElementById('count-select-location').value);

    const rows = document.querySelectorAll('#stock-count-table-body > tr');
    const itemsToSubmit = [];

    rows.forEach((row, idx) => {
      const item = this.currentLocationItems[idx];
      if (item && item.counted_qty !== item.system_qty) {
        const reasonSelect = row.querySelector('.count-reason-select');
        itemsToSubmit.push({
          product_id: item.product_id,
          system_qty: item.system_qty,
          counted_qty: item.counted_qty,
          reason: reasonSelect ? reasonSelect.value : 'Counting Error',
          notes: 'Batch physical cycle count'
        });
      }
    });

    if (!itemsToSubmit.length) {
      showToast('All counted stock matches system records. No adjustments needed!', 'success');
      return;
    }

    try {
      const res = await api.post('/api/adjustments/bulk-count', {
        warehouse_id: whId,
        location_id: locId,
        items: itemsToSubmit,
        user_id: auth.currentUser ? auth.currentUser.id : 1,
        user_name: auth.currentUser ? auth.currentUser.name : 'Warehouse Staff',
        role: auth.currentUser ? auth.currentUser.role : 'Warehouse Staff'
      });

      showToast(res.message, 'success');
      await this.loadLocationProducts();
      products.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
};
