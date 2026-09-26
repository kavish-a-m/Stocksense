/**
 * STOCKSENSE - Product Catalog & Management Module
 */

const products = {
  list: [],
  categories: [],
  warehouses: [],
  locations: [],
  currentFilter: {
    search: '',
    category_id: '',
    stock_status: '',
    warehouse_id: ''
  },

  async init() {
    await Promise.all([
      this.loadCategories(),
      this.loadWarehouses(),
      this.loadProducts()
    ]);
    this.populateCategorySelects();
    this.populateWarehouseSelects();
  },

  async loadCategories() {
    try {
      this.categories = await api.get('/api/categories');
    } catch (e) {
      console.error('Failed to load categories', e);
    }
  },

  async loadWarehouses() {
    try {
      this.warehouses = await api.get('/api/warehouses');
      this.locations = await api.get('/api/locations');
    } catch (e) {
      console.error('Failed to load warehouses/locations', e);
    }
  },

  async loadProducts() {
    try {
      let query = '?';
      if (this.currentFilter.search) query += `search=${encodeURIComponent(this.currentFilter.search)}&`;
      if (this.currentFilter.category_id) query += `category_id=${this.currentFilter.category_id}&`;
      if (this.currentFilter.stock_status) query += `stock_status=${encodeURIComponent(this.currentFilter.stock_status)}&`;
      if (this.currentFilter.warehouse_id) query += `warehouse_id=${this.currentFilter.warehouse_id}&`;

      this.list = await api.get(`/api/products${query}`);
      this.renderTable();
    } catch (e) {
      console.error('Failed to load products', e);
      showToast('Error loading products catalog', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('products-table-body');
    if (!tbody) return;

    if (!this.list.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="8" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="package-search" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No products found matching your search and filter criteria.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.list.forEach(p => {
      let badgeClass = 'badge-in-stock';
      if (p.stock_status === 'Out of Stock') badgeClass = 'badge-danger';
      else if (p.stock_status === 'Low Stock') badgeClass = 'badge-low-stock';
      else if (p.stock_status === 'Overstocked') badgeClass = 'badge-overstocked';

      html += `
        <tr>
          <td>
            <div style="font-weight:600;color:var(--text-primary);cursor:pointer;" onclick="products.openDetailModal(${p.id})">
              ${p.name}
            </div>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">
              SKU: ${p.sku} | Barcode: ${p.barcode}
            </div>
          </td>
          <td>
            <span class="badge" style="background:${p.category_color}20;color:${p.category_color};border:1px solid ${p.category_color}40;">
              ${p.category_name || 'General'}
            </span>
          </td>
          <td>
            <strong>${p.total_on_hand}</strong> ${p.uom}
          </td>
          <td>
            <span style="color:${p.total_reserved > 0 ? 'var(--status-waiting)' : 'var(--text-muted)'};font-weight:500;">
              ${p.total_reserved} ${p.uom}
            </span>
          </td>
          <td>
            <span style="color:var(--status-done);font-weight:700;">
              ${p.available_stock} ${p.uom}
            </span>
          </td>
          <td>
            <span class="badge ${badgeClass}">${p.stock_status}</span>
          </td>
          <td>
            $${p.cost_price.toFixed(2)} / <span style="color:var(--text-muted);">$${p.selling_price.toFixed(2)}</span>
          </td>
          <td style="text-align:right;">
            <div style="display:inline-flex;gap:0.35rem;">
              <button class="btn btn-sm btn-outline" title="View Details & QR" onclick="products.openDetailModal(${p.id})">
                <i data-lucide="eye" style="width:14px;height:14px;"></i>
              </button>
              <button class="btn btn-sm btn-outline" title="Edit Product" data-permission="edit_product" onclick="products.openEditModal(${p.id})">
                <i data-lucide="edit-2" style="width:14px;height:14px;"></i>
              </button>
              <button class="btn btn-sm btn-danger" title="Delete Product" data-permission="manage_products" onclick="products.deleteProduct(${p.id}, '${p.name}')">
                <i data-lucide="trash-2" style="width:14px;height:14px;"></i>
              </button>
            </div>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
    auth.enforceRBAC();
  },

  populateCategorySelects() {
    const filterCat = document.getElementById('filter-product-category');
    const formCat = document.getElementById('prod-form-category');

    const options = this.categories.map(c => `<option value="${c.id}">${c.name}</option>`).join('');

    if (filterCat) filterCat.innerHTML = `<option value="">All Categories</option>${options}`;
    if (formCat) formCat.innerHTML = `<option value="">Select Category</option>${options}`;
  },

  populateWarehouseSelects() {
    const whSelect = document.getElementById('prod-form-warehouse');
    if (whSelect) {
      whSelect.innerHTML = this.warehouses.map(w => `<option value="${w.id}">${w.name} (${w.code})</option>`).join('');
    }
  },

  openCreateModal() {
    document.getElementById('product-modal-title').textContent = 'Create New Product';
    document.getElementById('prod-form-id').value = '';
    document.getElementById('prod-form-name').value = '';
    document.getElementById('prod-form-sku').value = `PRD-${Date.now().toString().slice(-4)}`;
    document.getElementById('prod-form-barcode').value = `890${Date.now().toString().slice(-9)}`;
    document.getElementById('prod-form-cost').value = '50';
    document.getElementById('prod-form-price').value = '85';
    document.getElementById('prod-form-reorder').value = '10';
    document.getElementById('prod-form-reorder-qty').value = '50';
    document.getElementById('prod-form-lead').value = '5';
    document.getElementById('prod-form-initial-stock').value = '0';
    document.getElementById('prod-initial-stock-group').style.display = 'block';

    modals.open('modal-product');
  },

  async openEditModal(prodId) {
    try {
      const p = await api.get(`/api/products/${prodId}`);
      document.getElementById('product-modal-title').textContent = `Edit Product: ${p.name}`;
      document.getElementById('prod-form-id').value = p.id;
      document.getElementById('prod-form-name').value = p.name;
      document.getElementById('prod-form-sku').value = p.sku;
      document.getElementById('prod-form-barcode').value = p.barcode;
      document.getElementById('prod-form-category').value = p.category_id;
      document.getElementById('prod-form-uom').value = p.uom;
      document.getElementById('prod-form-cost').value = p.cost_price;
      document.getElementById('prod-form-price').value = p.selling_price;
      document.getElementById('prod-form-reorder').value = p.reorder_level;
      document.getElementById('prod-form-reorder-qty').value = p.reorder_qty;
      document.getElementById('prod-form-lead').value = p.lead_time_days;
      document.getElementById('prod-initial-stock-group').style.display = 'none';

      modals.open('modal-product');
    } catch (e) {
      showToast('Failed to fetch product details', 'error');
    }
  },

  async saveProduct(e) {
    if (e) e.preventDefault();

    const id = document.getElementById('prod-form-id').value;
    const body = {
      name: document.getElementById('prod-form-name').value.trim(),
      sku: document.getElementById('prod-form-sku').value.trim().toUpperCase(),
      barcode: document.getElementById('prod-form-barcode').value.trim(),
      category_id: parseInt(document.getElementById('prod-form-category').value) || 1,
      uom: document.getElementById('prod-form-uom').value,
      cost_price: parseFloat(document.getElementById('prod-form-cost').value) || 0,
      selling_price: parseFloat(document.getElementById('prod-form-price').value) || 0,
      reorder_level: parseFloat(document.getElementById('prod-form-reorder').value) || 10,
      reorder_qty: parseFloat(document.getElementById('prod-form-reorder-qty').value) || 50,
      lead_time_days: parseInt(document.getElementById('prod-form-lead').value) || 5,
      default_warehouse_id: parseInt(document.getElementById('prod-form-warehouse').value) || 1,
      default_location_id: 1,
      initial_stock: parseFloat(document.getElementById('prod-form-initial-stock').value) || 0,
      user_id: auth.currentUser ? auth.currentUser.id : 1,
      user_name: auth.currentUser ? auth.currentUser.name : 'Manager'
    };

    if (!body.name || !body.sku) {
      showToast('Product name and SKU are required', 'warning');
      return;
    }

    try {
      if (id) {
        await api.put(`/api/products/${id}`, body);
        showToast(`Product ${body.name} updated successfully!`, 'success');
      } else {
        await api.post('/api/products', body);
        showToast(`Product ${body.name} created successfully!`, 'success');
      }
      modals.close('modal-product');
      await this.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async deleteProduct(id, name) {
    try {
      await api.delete(`/api/products/${id}`);
      showToast(`Product '${name}' deleted successfully.`, 'success');
      await this.loadProducts();
      dashboard.loadData();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async openDetailModal(prodId) {
    try {
      const p = await api.get(`/api/products/${prodId}`);
      
      document.getElementById('pdetail-name').textContent = p.name;
      document.getElementById('pdetail-sku').textContent = p.sku;
      document.getElementById('pdetail-barcode').textContent = p.barcode;
      document.getElementById('pdetail-category').textContent = p.category_name || 'General';
      document.getElementById('pdetail-uom').textContent = p.uom;
      document.getElementById('pdetail-cost').textContent = `$${p.cost_price.toFixed(2)}`;
      document.getElementById('pdetail-price').textContent = `$${p.selling_price.toFixed(2)}`;
      document.getElementById('pdetail-onhand').textContent = `${p.total_on_hand} ${p.uom}`;
      document.getElementById('pdetail-reserved').textContent = `${p.total_reserved} ${p.uom}`;
      document.getElementById('pdetail-available').textContent = `${p.available_stock} ${p.uom}`;
      document.getElementById('pdetail-reorder').textContent = `${p.reorder_level} ${p.uom}`;

      // Render Locations breakdown table
      const locTbody = document.getElementById('pdetail-locations-body');
      if (locTbody) {
        if (!p.locations || !p.locations.length) {
          locTbody.innerHTML = '<tr><td colspan="4" style="color:var(--text-muted);text-align:center;">No warehouse locations assigned yet.</td></tr>';
        } else {
          locTbody.innerHTML = p.locations.map(l => `
            <tr>
              <td><strong>${l.warehouse_name}</strong></td>
              <td>${l.location_name} (<code>${l.location_code}</code>)</td>
              <td><strong>${l.on_hand}</strong> ${p.uom}</td>
              <td><span style="color:${l.reserved > 0 ? 'var(--status-waiting)' : 'var(--text-muted)'};">${l.reserved} ${p.uom}</span></td>
            </tr>
          `).join('');
        }
      }

      // Render Movements history table
      const moveTbody = document.getElementById('pdetail-movements-body');
      if (moveTbody) {
        if (!p.recent_movements || !p.recent_movements.length) {
          moveTbody.innerHTML = '<tr><td colspan="6" style="color:var(--text-muted);text-align:center;">No movement history found.</td></tr>';
        } else {
          moveTbody.innerHTML = p.recent_movements.map(m => {
            const flow = m.qty_in > 0 ? `<span style="color:var(--status-done);font-weight:600;">+${m.qty_in}</span>` : `<span style="color:var(--status-danger);font-weight:600;">-${m.qty_out}</span>`;
            return `
              <tr>
                <td><small>${m.timestamp}</small></td>
                <td><span class="badge badge-ready">${m.transaction_type}</span></td>
                <td><strong>${m.reference_no}</strong></td>
                <td>${m.location_name}</td>
                <td>${flow}</td>
                <td><strong>${m.balance_after}</strong></td>
              </tr>
            `;
          }).join('');
        }
      }

      // Generate QR Code
      const qrContainer = document.getElementById('pdetail-qrcode');
      if (qrContainer && window.QRCode) {
        qrContainer.innerHTML = '';
        new QRCode(qrContainer, {
          text: JSON.stringify({ id: p.id, sku: p.sku, name: p.name, barcode: p.barcode }),
          width: 120,
          height: 120,
          colorDark: '#0f172a',
          colorLight: '#ffffff',
          correctLevel: QRCode.CorrectLevel.H
        });
      }

      modals.open('modal-product-detail');
    } catch (e) {
      showToast('Error opening product details', 'error');
    }
  }
};
