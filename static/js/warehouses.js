/**
 * STOCKSENSE - Multi-Warehouse & Locations Management Module
 */

const warehouses = {
  list: [],
  locations: [],

  async init() {
    await this.loadAll();
  },

  async loadAll() {
    try {
      this.list = await api.get('/api/warehouses');
      this.locations = await api.get('/api/locations');
      this.renderWarehouses();
      this.renderLocations();
    } catch (e) {
      console.error('Failed to load warehouses', e);
      showToast('Error loading warehouse data', 'error');
    }
  },

  renderWarehouses() {
    const container = document.getElementById('warehouses-card-grid');
    if (!container) return;

    let html = '';
    this.list.forEach(w => {
      html += `
        <div class="kpi-card" style="border-left:4px solid var(--accent-primary);">
          <div class="kpi-header">
            <div>
              <span class="badge badge-ready" style="margin-bottom:4px;">${w.code}</span>
              <h3 style="font-size:1.1rem;margin-top:2px;">${w.name}</h3>
            </div>
            <div class="kpi-icon-wrap" style="background:rgba(99, 102, 241, 0.15);color:var(--accent-primary);">
              <i data-lucide="building-2"></i>
            </div>
          </div>
          <div style="font-size:0.8rem;color:var(--text-muted);">${w.address || 'Central Logistic Zone'}</div>
          
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-top:0.5rem;padding-top:0.75rem;border-top:1px solid var(--border-color);">
            <div>
              <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;">Stock Units</div>
              <div style="font-size:1.2rem;font-weight:700;color:var(--text-primary);">${(w.total_stock_units || 0).toLocaleString()}</div>
            </div>
            <div>
              <div style="font-size:0.7rem;color:var(--text-muted);text-transform:uppercase;">Valuation</div>
              <div style="font-size:1.2rem;font-weight:700;color:var(--status-done);">$${(w.total_valuation || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            </div>
          </div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.5rem;font-size:0.75rem;color:var(--text-secondary);">
            <span>${w.location_count || 0} Storage Locations</span>
            <span>${w.total_skus || 0} Unique SKUs</span>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  renderLocations() {
    const tbody = document.getElementById('locations-table-body');
    if (!tbody) return;

    let html = '';
    this.locations.forEach(l => {
      let typeBadge = 'badge-ready';
      if (l.type === 'quarantine') typeBadge = 'badge-waiting';
      else if (l.type === 'loss') typeBadge = 'badge-danger';
      else if (l.type === 'production') typeBadge = 'badge-packed';

      html += `
        <tr>
          <td>
            <strong>${l.name}</strong>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${l.code}</div>
          </td>
          <td>
            <div style="font-weight:600;">${l.warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${l.warehouse_code}</div>
          </td>
          <td>
            <span class="badge ${typeBadge}">${l.type}</span>
          </td>
          <td>
            <strong>${l.total_stock_units || 0}</strong> units
          </td>
          <td>
            ${l.total_skus || 0} SKUs
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  openCreateWarehouseModal() {
    document.getElementById('wh-form-code').value = `WH-${Math.random().toString(36).substring(2, 5).toUpperCase()}`;
    document.getElementById('wh-form-name').value = '';
    document.getElementById('wh-form-address').value = '';
    modals.open('modal-warehouse-create');
  },

  async saveWarehouse(e) {
    if (e) e.preventDefault();

    const code = document.getElementById('wh-form-code').value.trim().toUpperCase();
    const name = document.getElementById('wh-form-name').value.trim();
    const address = document.getElementById('wh-form-address').value.trim();

    if (!code || !name) {
      showToast('Warehouse code and name are required', 'warning');
      return;
    }

    try {
      await api.post('/api/warehouses', { code, name, address });
      showToast(`Warehouse ${name} created successfully!`, 'success');
      modals.close('modal-warehouse-create');
      await this.loadAll();
      await products.loadWarehouses();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  openCreateLocationModal() {
    const whSelect = document.getElementById('loc-form-warehouse');
    whSelect.innerHTML = this.list.map(w => `<option value="${w.id}">${w.name} (${w.code})</option>`).join('');
    
    document.getElementById('loc-form-code').value = `LOC-${Math.random().toString(36).substring(2, 6).toUpperCase()}`;
    document.getElementById('loc-form-name').value = '';
    document.getElementById('loc-form-type').value = 'internal';

    modals.open('modal-location-create');
  },

  async saveLocation(e) {
    if (e) e.preventDefault();

    const whId = parseInt(document.getElementById('loc-form-warehouse').value);
    const code = document.getElementById('loc-form-code').value.trim().toUpperCase();
    const name = document.getElementById('loc-form-name').value.trim();
    const locType = document.getElementById('loc-form-type').value;

    if (!whId || !code || !name) {
      showToast('Warehouse, location code, and location name are required', 'warning');
      return;
    }

    try {
      await api.post('/api/locations', {
        warehouse_id: whId,
        code,
        name,
        type: locType
      });
      showToast(`Location ${name} added successfully!`, 'success');
      modals.close('modal-location-create');
      await this.loadAll();
      await products.loadWarehouses();
    } catch (err) {
      showToast(err.message, 'error');
    }
  }
};
