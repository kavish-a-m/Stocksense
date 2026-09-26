/**
 * STOCKSENSE - Smart Reorder & Stockout Analytics Module
 */

const analytics = {
  reorders: [],

  async init() {
    await this.loadAnalytics();
  },

  async loadAnalytics() {
    try {
      this.reorders = await api.get('/api/analytics/reorders');
      this.renderReorderTable();
      this.renderForecastTable();
    } catch (e) {
      console.error('Failed to load analytics', e);
      showToast('Error loading inventory analytics', 'error');
    }
  },

  renderReorderTable() {
    const tbody = document.getElementById('analytics-reorder-table-body');
    if (!tbody) return;

    let html = '';
    this.reorders.forEach(r => {
      const needsReorder = r.needs_reorder;
      const rowStyle = needsReorder ? 'background:rgba(239, 68, 68, 0.05);' : '';

      html += `
        <tr style="${rowStyle}">
          <td>
            <div style="font-weight:600;color:var(--text-primary);">${r.name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${r.sku} (${r.category})</div>
          </td>
          <td>
            <strong>${r.available}</strong> ${r.uom}
            <div style="font-size:0.7rem;color:var(--text-muted);">On hand: ${r.on_hand}</div>
          </td>
          <td>
            <strong>${r.avg_daily_usage}</strong> ${r.uom}/day
          </td>
          <td>
            ${r.lead_time_days} days
          </td>
          <td>
            ${r.safety_stock} ${r.uom}
          </td>
          <td>
            <strong style="color:var(--accent-primary);">${r.effective_reorder_point}</strong> ${r.uom}
          </td>
          <td>
            ${needsReorder 
              ? `<span class="badge badge-danger">Reorder Required</span>`
              : `<span class="badge badge-in-stock">Sufficient</span>`
            }
          </td>
          <td>
            ${needsReorder 
              ? `<strong style="color:var(--status-done);font-size:1rem;">+${r.suggested_reorder_qty} ${r.uom}</strong>`
              : `<span style="color:var(--text-muted);">0</span>`
            }
          </td>
          <td style="text-align:right;">
            ${needsReorder ? `
              <button class="btn btn-sm btn-primary" onclick="receipts.quickCreateFromReorder(${r.product_id}, '${r.name}', ${r.suggested_reorder_qty})">
                <i data-lucide="shopping-cart" style="width:12px;height:12px;"></i> Order Now
              </button>
            ` : '—'}
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  renderForecastTable() {
    const tbody = document.getElementById('analytics-forecast-table-body');
    if (!tbody) return;

    const fastDepleting = this.reorders.filter(r => r.avg_daily_usage > 0);
    fastDepleting.sort((a, b) => (a.days_to_stockout || 999) - (b.days_to_stockout || 999));

    let html = '';
    fastDepleting.forEach(f => {
      let riskBadge = '<span class="badge badge-in-stock">Low Risk</span>';
      if (f.days_to_stockout <= 3) riskBadge = '<span class="badge badge-danger">CRITICAL: &le; 3 Days</span>';
      else if (f.days_to_stockout <= 7) riskBadge = '<span class="badge badge-waiting">HIGH: &le; 7 Days</span>';
      else if (f.days_to_stockout <= 14) riskBadge = '<span class="badge badge-ready">MODERATE</span>';

      html += `
        <tr>
          <td>
            <div style="font-weight:600;">${f.name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);">${f.sku}</div>
          </td>
          <td><strong>${f.available}</strong> ${f.uom}</td>
          <td>${f.avg_daily_usage} ${f.uom}/day</td>
          <td>
            <strong style="font-size:1.05rem;color:${f.days_to_stockout <= 7 ? 'var(--status-danger)' : 'var(--text-primary)'};">
              ~${f.days_to_stockout} days
            </strong>
          </td>
          <td>${riskBadge}</td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  }
};
