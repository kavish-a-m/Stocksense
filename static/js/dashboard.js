/**
 * STOCKSENSE - Real-time Dashboard & KPI Visualizations
 */

const dashboard = {
  movementChart: null,
  warehouseChart: null,

  async init() {
    await this.loadData();
  },

  async loadData() {
    try {
      const summary = await api.get('/api/dashboard/summary');
      this.renderKPIs(summary.kpis);
      this.renderCharts(summary);
      this.renderLowStock(summary.low_stock_items);
      this.renderRecentActivity(summary.recent_activities);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      showToast('Error loading dashboard metrics', 'error');
    }
  },

  renderKPIs(kpis) {
    if (!kpis) return;

    document.getElementById('kpi-total-products').textContent = kpis.total_products || 0;
    document.getElementById('kpi-total-stock').textContent = (kpis.total_stock_units || 0).toLocaleString();
    document.getElementById('kpi-low-stock').textContent = kpis.low_stock_items || 0;
    document.getElementById('kpi-out-of-stock').textContent = kpis.out_of_stock_items || 0;
    document.getElementById('kpi-pending-receipts').textContent = kpis.pending_receipts || 0;
    document.getElementById('kpi-pending-deliveries').textContent = kpis.pending_deliveries || 0;
    document.getElementById('kpi-scheduled-transfers').textContent = kpis.scheduled_transfers || 0;
    document.getElementById('kpi-inventory-valuation').textContent = `$${(kpis.inventory_valuation || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;
  },

  renderCharts(summary) {
    // 1. Stock Movements Timeline (In vs Out)
    const moveCanvas = document.getElementById('chart-movements');
    if (moveCanvas && window.Chart) {
      const timeline = summary.timeline || [];
      const labels = timeline.map(t => t.day);
      const dataIn = timeline.map(t => t.total_in);
      const dataOut = timeline.map(t => t.total_out);

      if (this.movementChart) this.movementChart.destroy();

      this.movementChart = new Chart(moveCanvas, {
        type: 'bar',
        data: {
          labels: labels.length ? labels : ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
          datasets: [
            {
              label: 'Incoming Stock (+In)',
              data: dataIn.length ? dataIn : [120, 80, 150, 60, 90, 110, 45],
              backgroundColor: 'rgba(16, 185, 129, 0.75)',
              borderRadius: 6
            },
            {
              label: 'Outgoing Stock (-Out)',
              data: dataOut.length ? dataOut : [40, 65, 90, 30, 70, 50, 20],
              backgroundColor: 'rgba(239, 68, 68, 0.75)',
              borderRadius: 6
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } }
          },
          scales: {
            x: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
            y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } }
          }
        }
      });
    }

    // 2. Warehouse Stock Distribution (Doughnut Chart)
    const whCanvas = document.getElementById('chart-warehouses');
    if (whCanvas && window.Chart) {
      const whStats = summary.warehouse_stats || [];
      const labels = whStats.map(w => w.name);
      const data = whStats.map(w => w.total_stock);

      if (this.warehouseChart) this.warehouseChart.destroy();

      this.warehouseChart = new Chart(whCanvas, {
        type: 'doughnut',
        data: {
          labels: labels.length ? labels : ['Main Warehouse', 'Production Plant'],
          datasets: [{
            data: data.length ? data : [650, 280],
            backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#8b5cf6'],
            borderWidth: 0
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } } }
          },
          cutout: '70%'
        }
      });
    }
  },

  renderLowStock(items) {
    const container = document.getElementById('dashboard-low-stock-list');
    if (!container) return;

    if (!items || !items.length) {
      container.innerHTML = `
        <tr>
          <td colspan="5" style="text-align:center;color:var(--text-muted);padding:1.5rem;">
            <i data-lucide="check-circle" style="color:var(--status-done);width:20px;height:20px;display:inline-block;vertical-align:middle;margin-right:6px;"></i>
            All inventory levels are optimal and above reorder thresholds!
          </td>
        </tr>
      `;
      if (window.lucide) lucide.createIcons();
      return;
    }

    let html = '';
    items.forEach(item => {
      const isOut = item.on_hand === 0;
      const statusClass = isOut ? 'badge-danger' : 'badge-low-stock';
      const statusText = isOut ? 'Out of Stock' : 'Low Stock';

      html += `
        <tr>
          <td>
            <div style="font-weight:600;color:var(--text-primary);">${item.name}</div>
            <div style="font-size:0.75rem;color:var(--text-muted);font-family:monospace;">${item.sku}</div>
          </td>
          <td>
            <span class="badge ${statusClass}">${statusText}</span>
          </td>
          <td>
            <strong>${item.available}</strong> / <span style="color:var(--text-muted);">${item.reorder_level} ${item.uom}</span>
          </td>
          <td>
            <span style="color:var(--accent-primary);font-weight:600;">+${item.suggested_reorder_qty} ${item.uom}</span>
          </td>
          <td style="text-align:right;">
            <button class="btn btn-sm btn-primary" onclick="receipts.quickCreateFromReorder(${item.product_id}, '${item.name}', ${item.suggested_reorder_qty})">
              <i data-lucide="plus" style="width:12px;height:12px;"></i> Restock
            </button>
          </td>
        </tr>
      `;
    });

    container.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  },

  renderRecentActivity(activities) {
    const container = document.getElementById('dashboard-recent-activity');
    if (!container) return;

    if (!activities || !activities.length) {
      container.innerHTML = '<div style="color:var(--text-muted);padding:1rem;text-align:center;">No recent activities found.</div>';
      return;
    }

    let html = '';
    activities.forEach(act => {
      let icon = 'arrow-right-left';
      let iconColor = 'var(--status-ready)';
      let badge = `<span class="badge badge-ready">${act.transaction_type}</span>`;
      let flow = ``;

      if (act.transaction_type === 'Receipt') {
        icon = 'arrow-down-left';
        iconColor = 'var(--status-done)';
        badge = `<span class="badge badge-done">Receipt</span>`;
        flow = `<span style="color:var(--status-done);font-weight:600;">+${act.qty_in}</span>`;
      } else if (act.transaction_type === 'Delivery') {
        icon = 'arrow-up-right';
        iconColor = 'var(--status-danger)';
        badge = `<span class="badge badge-danger">Delivery</span>`;
        flow = `<span style="color:var(--status-danger);font-weight:600;">-${act.qty_out}</span>`;
      } else if (act.transaction_type === 'Adjustment') {
        icon = 'sliders';
        iconColor = 'var(--status-waiting)';
        badge = `<span class="badge badge-waiting">Adjustment</span>`;
        flow = act.qty_in > 0 ? `<span style="color:var(--status-done);">+${act.qty_in}</span>` : `<span style="color:var(--status-danger);">-${act.qty_out}</span>`;
      }

      html += `
        <div style="display:flex;align-items:flex-start;gap:0.75rem;padding:0.75rem 0;border-bottom:1px solid var(--border-color);">
          <div style="width:32px;height:32px;border-radius:50%;background:rgba(255,255,255,0.05);display:flex;align-items:center;justify-content:center;color:${iconColor};flex-shrink:0;">
            <i data-lucide="${icon}" style="width:16px;height:16px;"></i>
          </div>
          <div style="flex:1;font-size:0.825rem;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:2px;">
              <span style="font-weight:600;color:var(--text-primary);">${act.reference_no}</span>
              ${badge}
            </div>
            <div style="color:var(--text-secondary);">${act.product_name} ${flow} at <strong>${act.location_name}</strong></div>
            <div style="font-size:0.7rem;color:var(--text-muted);display:flex;justify-content:space-between;margin-top:2px;">
              <span>By ${act.user_name || 'Staff'}</span>
              <span>${act.timestamp}</span>
            </div>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  }
};
