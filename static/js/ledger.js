/**
 * STOCKSENSE - Immutable Stock Ledger & Move History Module
 */

const ledger = {
  records: [],
  filters: {
    type: '',
    warehouse_id: '',
    search: ''
  },

  async init() {
    await this.loadLedger();
  },

  async loadLedger() {
    try {
      let query = '?';
      if (this.filters.type) query += `transaction_type=${encodeURIComponent(this.filters.type)}&`;
      if (this.filters.warehouse_id) query += `warehouse_id=${this.filters.warehouse_id}&`;
      if (this.filters.search) query += `search=${encodeURIComponent(this.filters.search)}&`;

      this.records = await api.get(`/api/ledger${query}`);
      this.renderTable();
    } catch (e) {
      console.error('Failed to load ledger', e);
      showToast('Error loading stock ledger', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('ledger-table-body');
    if (!tbody) return;

    if (!this.records.length) {
      tbody.innerHTML = `
        <tr>
          <td colspan="9" style="text-align:center;padding:2.5rem;color:var(--text-muted);">
            <i data-lucide="history" style="width:36px;height:36px;margin-bottom:0.5rem;opacity:0.5;"></i>
            <div>No ledger records found. Every transaction performed across StockSense writes an immutable audit record here.</div>
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    this.records.forEach(r => {
      let badgeClass = 'badge-ready';
      let flowHtml = '';

      if (r.transaction_type === 'Receipt') {
        badgeClass = 'badge-done';
        flowHtml = `<span style="color:var(--status-done);font-weight:700;">+${r.qty_in}</span>`;
      } else if (r.transaction_type === 'Delivery') {
        badgeClass = 'badge-danger';
        flowHtml = `<span style="color:var(--status-danger);font-weight:700;">-${r.qty_out}</span>`;
      } else if (r.transaction_type === 'Internal Transfer') {
        badgeClass = 'badge-ready';
        flowHtml = r.qty_in > 0 ? `<span style="color:var(--status-done);font-weight:700;">+${r.qty_in}</span>` : `<span style="color:var(--status-danger);font-weight:700;">-${r.qty_out}</span>`;
      } else if (r.transaction_type === 'Adjustment') {
        badgeClass = 'badge-waiting';
        flowHtml = r.qty_in > 0 ? `<span style="color:var(--status-done);font-weight:700;">+${r.qty_in}</span>` : `<span style="color:var(--status-danger);font-weight:700;">-${r.qty_out}</span>`;
      } else {
        badgeClass = 'badge-draft';
        flowHtml = `<span style="color:var(--text-primary);font-weight:700;">+${r.qty_in}</span>`;
      }

      html += `
        <tr>
          <td>
            <div style="font-family:monospace;font-size:0.75rem;color:var(--text-muted);">${r.timestamp}</div>
            <div style="font-size:0.7rem;color:var(--text-muted);">${r.transaction_id}</div>
          </td>
          <td>
            <span class="badge ${badgeClass}">${r.transaction_type}</span>
          </td>
          <td>
            <div style="font-weight:600;color:var(--text-primary);">${r.product_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${r.sku}</div>
          </td>
          <td>
            <div>${r.warehouse_name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${r.location_name}</div>
          </td>
          <td style="text-align:center;">
            ${flowHtml}
          </td>
          <td>
            <strong style="color:var(--text-primary);font-size:0.95rem;">${r.balance_after}</strong>
          </td>
          <td>
            <strong style="color:var(--accent-primary);">${r.reference_no}</strong>
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-secondary);">${r.reason || '—'}</span>
          </td>
          <td>
            <span style="font-size:0.8rem;color:var(--text-muted);">${r.user_name || 'Staff'}</span>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  exportCSV() {
    if (!this.records.length) {
      showToast('No records to export', 'warning');
      return;
    }

    const headers = ['Timestamp', 'Transaction ID', 'Type', 'Product', 'SKU', 'Warehouse', 'Location', 'Qty In', 'Qty Out', 'Balance After', 'Reference', 'Reason', 'User'];
    const rows = this.records.map(r => [
      `"${r.timestamp}"`,
      `"${r.transaction_id}"`,
      `"${r.transaction_type}"`,
      `"${r.product_name}"`,
      `"${r.sku}"`,
      `"${r.warehouse_name}"`,
      `"${r.location_name}"`,
      r.qty_in,
      r.qty_out,
      r.balance_after,
      `"${r.reference_no}"`,
      `"${r.reason || ''}"`,
      `"${r.user_name || ''}"`
    ]);

    const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `StockSense_Ledger_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    showToast('Stock ledger exported to CSV successfully!', 'success');
  }
};
