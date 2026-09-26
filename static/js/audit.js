/**
 * STOCKSENSE - Security & Operations Audit Trail Module
 */

const audit = {
  logs: [],

  async init() {
    await this.loadLogs();
  },

  async loadLogs() {
    try {
      this.logs = await api.get('/api/audit-logs');
      this.renderTable();
    } catch (e) {
      console.error('Failed to load audit logs', e);
      showToast('Error loading audit trail', 'error');
    }
  },

  renderTable() {
    const tbody = document.getElementById('audit-table-body');
    if (!tbody) return;

    if (!this.logs.length) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:2rem;color:var(--text-muted);">No audit logs recorded.</td></tr>';
      return;
    }

    let html = '';
    this.logs.forEach(l => {
      let actionBadge = 'badge-ready';
      if (l.action.includes('DELETE') || l.action.includes('CANCEL')) actionBadge = 'badge-danger';
      else if (l.action.includes('VALIDATE') || l.action.includes('COMPLETE')) actionBadge = 'badge-done';
      else if (l.action.includes('CREATE')) actionBadge = 'badge-picked';

      html += `
        <tr>
          <td>
            <div style="font-family:monospace;font-size:0.75rem;color:var(--text-muted);">${l.timestamp}</div>
          </td>
          <td>
            <div style="font-weight:600;color:var(--text-primary);">${l.user_name || 'System'}</div>
            <div style="font-size:0.7rem;color:var(--text-muted);">${l.role || 'Staff'}</div>
          </td>
          <td>
            <span class="badge ${actionBadge}">${l.action}</span>
          </td>
          <td>
            <strong>${l.object_type}</strong>: <code>${l.object_id || ''}</code>
          </td>
          <td>
            <div style="font-size:0.75rem;font-family:monospace;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-secondary);" title='${l.new_values || ''}'>
              ${l.new_values || '—'}
            </div>
          </td>
          <td>
            <small style="color:var(--text-muted);">${l.ip_address}</small>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
    if (window.lucide) lucide.createIcons();
  }
};
