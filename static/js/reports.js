/**
 * STOCKSENSE - Reports & Financial Inventory Valuation Module
 */

const reports = {
  currentTab: 'valuation',

  async init() {
    await this.loadValuationReport();
  },

  switchTab(tab) {
    this.currentTab = tab;
    document.querySelectorAll('.report-tab-btn').forEach(btn => {
      btn.classList.toggle('btn-primary', btn.dataset.tab === tab);
      btn.classList.toggle('btn-outline', btn.dataset.tab !== tab);
    });

    if (tab === 'valuation') this.loadValuationReport();
    else if (tab === 'movements') this.loadMovementsReport();
    else if (tab === 'summary') this.loadSummaryReport();
  },

  async loadValuationReport() {
    try {
      const data = await api.get('/api/reports/valuation');
      const container = document.getElementById('report-content-area');
      if (!container) return;

      const sum = data.summary;
      let html = `
        <div class="kpi-grid" style="margin-bottom:1.5rem;">
          <div class="kpi-card" style="border-left:4px solid var(--accent-primary);">
            <div class="kpi-title">Total Cost Valuation</div>
            <div class="kpi-value" style="color:var(--accent-primary);">$${sum.total_cost_valuation.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            <div class="kpi-meta">Calculated at purchase cost</div>
          </div>
          <div class="kpi-card" style="border-left:4px solid var(--status-done);">
            <div class="kpi-title">Estimated Retail Value</div>
            <div class="kpi-value" style="color:var(--status-done);">$${sum.total_retail_valuation.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            <div class="kpi-meta">Selling price potential</div>
          </div>
          <div class="kpi-card" style="border-left:4px solid var(--status-waiting);">
            <div class="kpi-title">Potential Margin</div>
            <div class="kpi-value" style="color:var(--status-waiting);">$${sum.potential_margin.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
            <div class="kpi-meta">Gross profit buffer</div>
          </div>
          <div class="kpi-card" style="border-left:4px solid #8b5cf6;">
            <div class="kpi-title">Total Physical Stock</div>
            <div class="kpi-value" style="color:#8b5cf6;">${sum.total_units.toLocaleString()}</div>
            <div class="kpi-meta">Aggregated units across network</div>
          </div>
        </div>

        <div class="data-card" style="margin-bottom:1.5rem;">
          <div class="data-card-header">
            <h3><i data-lucide="layers" style="width:18px;height:18px;display:inline-block;vertical-align:middle;margin-right:6px;"></i> Valuation by Category</h3>
          </div>
          <div class="data-table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Product Count</th>
                  <th>Total Units</th>
                  <th>Cost Valuation</th>
                </tr>
              </thead>
              <tbody>
                ${data.by_category.map(c => `
                  <tr>
                    <td><strong style="color:${c.color};">${c.name}</strong></td>
                    <td>${c.product_count} SKUs</td>
                    <td><strong>${c.total_units}</strong> units</td>
                    <td><strong style="color:var(--text-primary);">$${c.total_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>

        <div class="data-card">
          <div class="data-card-header">
            <h3><i data-lucide="package" style="width:18px;height:18px;display:inline-block;vertical-align:middle;margin-right:6px;"></i> Product Level Valuation & Margin Breakdown</h3>
            <button class="btn btn-sm btn-outline" onclick="reports.exportValuationCSV()">
              <i data-lucide="download" style="width:12px;height:12px;"></i> Export CSV
            </button>
          </div>
          <div class="data-table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Product</th>
                  <th>Category</th>
                  <th>Unit Cost</th>
                  <th>Selling Price</th>
                  <th>On Hand</th>
                  <th>Total Cost Value</th>
                  <th>Potential Retail Value</th>
                </tr>
              </thead>
              <tbody>
                ${data.by_product.map(p => `
                  <tr>
                    <td>
                      <div style="font-weight:600;">${p.name}</div>
                      <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${p.sku}</div>
                    </td>
                    <td>${p.category_name || 'General'}</td>
                    <td>$${p.cost_price.toFixed(2)}</td>
                    <td>$${p.selling_price.toFixed(2)}</td>
                    <td><strong>${p.total_on_hand}</strong> ${p.uom}</td>
                    <td><strong style="color:var(--text-primary);">$${p.total_cost_value.toFixed(2)}</strong></td>
                    <td><strong style="color:var(--status-done);">$${p.total_retail_value.toFixed(2)}</strong></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;

      container.innerHTML = html;
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      showToast('Error loading valuation report', 'error');
    }
  },

  async loadMovementsReport() {
    try {
      const moves = await api.get('/api/reports/movements');
      const container = document.getElementById('report-content-area');
      if (!container) return;

      let html = `
        <div class="data-card">
          <div class="data-card-header">
            <h3><i data-lucide="trending-up" style="width:18px;height:18px;display:inline-block;vertical-align:middle;margin-right:6px;"></i> Daily Movement Aggregates</h3>
          </div>
          <div class="data-table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Operation Type</th>
                  <th>Transactions Count</th>
                  <th>Total Inflow (+In)</th>
                  <th>Total Outflow (-Out)</th>
                </tr>
              </thead>
              <tbody>
                ${moves.map(m => `
                  <tr>
                    <td><strong>${m.move_date}</strong></td>
                    <td><span class="badge badge-ready">${m.transaction_type}</span></td>
                    <td>${m.tx_count}</td>
                    <td><strong style="color:var(--status-done);">+${m.total_qty_in}</strong></td>
                    <td><strong style="color:var(--status-danger);">${m.total_qty_out > 0 ? `-${m.total_qty_out}` : '0'}</strong></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;

      container.innerHTML = html;
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      showToast('Error loading movements report', 'error');
    }
  },

  async loadSummaryReport() {
    try {
      const summary = await api.get('/api/dashboard/summary');
      const container = document.getElementById('report-content-area');
      if (!container) return;

      let html = `
        <div class="data-card">
          <div class="data-card-header">
            <h3><i data-lucide="bar-chart-2" style="width:18px;height:18px;display:inline-block;vertical-align:middle;margin-right:6px;"></i> Warehouse Network Utilization</h3>
          </div>
          <div class="data-table-wrapper">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Warehouse Code</th>
                  <th>Facility Name</th>
                  <th>Active SKUs</th>
                  <th>Stocked Units</th>
                  <th>Inventory Value</th>
                </tr>
              </thead>
              <tbody>
                ${summary.warehouse_stats.map(w => `
                  <tr>
                    <td><code>${w.code}</code></td>
                    <td><strong>${w.name}</strong></td>
                    <td>${w.product_count} SKUs</td>
                    <td><strong>${w.total_stock}</strong> units</td>
                    <td><strong style="color:var(--status-done);">$${w.total_value.toLocaleString('en-US', { minimumFractionDigits: 2 })}</strong></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        </div>
      `;

      container.innerHTML = html;
      if (window.lucide) lucide.createIcons();
    } catch (e) {
      showToast('Error loading summary report', 'error');
    }
  },

  exportValuationCSV() {
    api.get('/api/reports/valuation').then(data => {
      const headers = ['Product Name', 'SKU', 'Category', 'Unit Cost', 'Selling Price', 'On Hand Stock', 'Total Cost Value', 'Total Retail Value'];
      const rows = data.by_product.map(p => [
        `"${p.name}"`,
        `"${p.sku}"`,
        `"${p.category_name || ''}"`,
        p.cost_price,
        p.selling_price,
        p.total_on_hand,
        p.total_cost_value,
        p.total_retail_value
      ]);

      const csvContent = 'data:text/csv;charset=utf-8,' + [headers.join(','), ...rows.map(e => e.join(','))].join('\n');
      const encodedUri = encodeURI(csvContent);
      const link = document.createElement('a');
      link.setAttribute('href', encodedUri);
      link.setAttribute('download', `StockSense_Valuation_Report_${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      showToast('Valuation report exported successfully!', 'success');
    });
  }
};
