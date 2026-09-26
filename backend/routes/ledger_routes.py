from flask import Blueprint, request, jsonify
from backend.database import get_db_connection

ledger_bp = Blueprint('ledger', __name__)

@ledger_bp.route('/api/ledger', methods=['GET'])
def get_ledger():
    transaction_type = request.args.get('transaction_type')
    product_id = request.args.get('product_id')
    warehouse_id = request.args.get('warehouse_id')
    search = request.args.get('search', '').strip().lower()
    limit = int(request.args.get('limit', 100))

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM stock_ledger WHERE 1=1"
    params = []

    if transaction_type:
        query += " AND transaction_type = ?"
        params.append(transaction_type)
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)
    if warehouse_id:
        query += " AND warehouse_id = ?"
        params.append(warehouse_id)

    query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()

    records = []
    for r in rows:
        item = dict(r)
        if search:
            if (search not in item['product_name'].lower() and
                search not in item['sku'].lower() and
                search not in item['reference_no'].lower() and
                search not in item['transaction_id'].lower()):
                continue
        records.append(item)

    conn.close()
    return jsonify(records)

@ledger_bp.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    action = request.args.get('action')
    object_type = request.args.get('object_type')
    limit = int(request.args.get('limit', 100))

    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM audit_logs WHERE 1=1"
    params = []

    if action:
        query += " AND action = ?"
        params.append(action)
    if object_type:
        query += " AND object_type = ?"
        params.append(object_type)

    query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@ledger_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications ORDER BY timestamp DESC LIMIT 30")
    rows = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT COUNT(*) as unread FROM notifications WHERE is_read = 0")
    unread_count = cursor.fetchone()['unread']

    conn.close()
    return jsonify({'notifications': rows, 'unread_count': unread_count})

@ledger_bp.route('/api/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1")
    conn.commit()
    conn.close()
    return jsonify({'success': True})
