from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import validate_transfer, log_audit, create_notification

transfer_bp = Blueprint('transfers', __name__)

@transfer_bp.route('/api/transfers', methods=['GET'])
def get_transfers():
    status = request.args.get('status')
    search = request.args.get('search', '').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT t.*, 
               sw.name as src_warehouse_name, sw.code as src_warehouse_code,
               sl.name as src_location_name, sl.code as src_location_code,
               dw.name as dst_warehouse_name, dw.code as dst_warehouse_code,
               dl.name as dst_location_name, dl.code as dst_location_code,
               u.name as responsible_user_name,
               COUNT(ti.id) as item_count,
               COALESCE(SUM(ti.quantity), 0) as total_quantity
        FROM transfers t
        JOIN warehouses sw ON t.source_warehouse_id = sw.id
        JOIN locations sl ON t.source_location_id = sl.id
        JOIN warehouses dw ON t.dest_warehouse_id = dw.id
        JOIN locations dl ON t.dest_location_id = dl.id
        LEFT JOIN users u ON t.responsible_user_id = u.id
        LEFT JOIN transfer_items ti ON t.id = ti.transfer_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND t.status = ?"
        params.append(status)

    query += " GROUP BY t.id ORDER BY t.id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    transfers = []
    for r in rows:
        item = dict(r)
        if search:
            if search not in item['reference_no'].lower() and search not in item['src_warehouse_name'].lower() and search not in item['dst_warehouse_name'].lower():
                continue
        transfers.append(item)

    conn.close()
    return jsonify(transfers)

@transfer_bp.route('/api/transfers/<int:transfer_id>', methods=['GET'])
def get_transfer(transfer_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, 
               sw.name as src_warehouse_name, sw.code as src_warehouse_code,
               sl.name as src_location_name, sl.code as src_location_code,
               dw.name as dst_warehouse_name, dw.code as dst_warehouse_code,
               dl.name as dst_location_name, dl.code as dst_location_code,
               u.name as responsible_user_name
        FROM transfers t
        JOIN warehouses sw ON t.source_warehouse_id = sw.id
        JOIN locations sl ON t.source_location_id = sl.id
        JOIN warehouses dw ON t.dest_warehouse_id = dw.id
        JOIN locations dl ON t.dest_location_id = dl.id
        LEFT JOIN users u ON t.responsible_user_id = u.id
        WHERE t.id = ?
    """, (transfer_id,))
    transfer = cursor.fetchone()

    if not transfer:
        conn.close()
        return jsonify({'error': 'Transfer not found.'}), 404

    res = dict(transfer)

    cursor.execute("""
        SELECT ti.*, p.name as product_name, p.sku, p.uom,
               s.on_hand as src_on_hand, s.reserved as src_reserved
        FROM transfer_items ti
        JOIN products p ON ti.product_id = p.id
        LEFT JOIN stock s ON (p.id = s.product_id AND s.location_id = ?)
        WHERE ti.transfer_id = ?
    """, (transfer['source_location_id'], transfer_id))
    res['items'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(res)

@transfer_bp.route('/api/transfers', methods=['POST'])
def create_transfer():
    data = request.get_json() or {}
    source_warehouse_id = data.get('source_warehouse_id')
    source_location_id = data.get('source_location_id')
    dest_warehouse_id = data.get('dest_warehouse_id')
    dest_location_id = data.get('dest_location_id')
    scheduled_date = data.get('scheduled_date', datetime.now().strftime('%Y-%m-%d'))
    responsible_user_id = data.get('responsible_user_id', 1)
    notes = data.get('notes', '')
    items = data.get('items', [])
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    if not source_warehouse_id or not source_location_id or not dest_warehouse_id or not dest_location_id:
        return jsonify({'error': 'Source and destination warehouses & locations are required.'}), 400

    if source_location_id == dest_location_id:
        return jsonify({'error': 'Source location and destination location must be different.'}), 400

    if not items:
        return jsonify({'error': 'At least one product item is required for transfer.'}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        # Generate reference number WH/INT/XXXX
        cursor.execute("SELECT MAX(id) as max_id FROM transfers")
        max_id = (cursor.fetchone()['max_id'] or 0) + 1
        ref_no = f"WH/INT/{max_id:04d}"

        cursor.execute("""
            INSERT INTO transfers (reference_no, source_warehouse_id, source_location_id, dest_warehouse_id, dest_location_id, scheduled_date, responsible_user_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Draft', ?)
        """, (ref_no, source_warehouse_id, source_location_id, dest_warehouse_id, dest_location_id, scheduled_date, responsible_user_id, notes))
        transfer_id = cursor.lastrowid

        for item in items:
            p_id = item.get('product_id')
            qty = float(item.get('quantity', 1.0))
            cursor.execute("""
                INSERT INTO transfer_items (transfer_id, product_id, quantity)
                VALUES (?, ?, ?)
            """, (transfer_id, p_id, qty))

        log_audit(conn, responsible_user_id, user_name, role, 'CREATE_TRANSFER', 'Transfer', ref_no,
                  new_values={'items_count': len(items)})

        create_notification(conn, 'transfer', f"Internal Transfer Created: {ref_no}",
                            f"Transfer order {ref_no} created with {len(items)} items.", 'info',
                            link=f"/transfers?id={transfer_id}")

        conn.commit()
        return jsonify({'id': transfer_id, 'reference_no': ref_no, 'status': 'Draft', 'message': f'Transfer {ref_no} created successfully.'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@transfer_bp.route('/api/transfers/<int:transfer_id>/ready', methods=['POST'])
def mark_transfer_ready(transfer_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE transfers SET status = 'Ready' WHERE id = ? AND status IN ('Draft', 'Waiting')", (transfer_id,))
        if cursor.rowcount == 0:
            return jsonify({'error': 'Transfer not in Draft or Waiting state.'}), 400
        conn.commit()
        return jsonify({'success': True, 'message': 'Transfer marked as Ready to execute.'})
    finally:
        conn.close()

@transfer_bp.route('/api/transfers/<int:transfer_id>/validate', methods=['POST'])
def validate_transfer_endpoint(transfer_id):
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    try:
        result = validate_transfer(transfer_id, user_id=user_id, user_name=user_name, role=role)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@transfer_bp.route('/api/transfers/<int:transfer_id>/cancel', methods=['POST'])
def cancel_transfer(transfer_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, reference_no FROM transfers WHERE id = ?", (transfer_id,))
        t = cursor.fetchone()
        if not t:
            return jsonify({'error': 'Transfer not found.'}), 404
        if t['status'] == 'Done':
            return jsonify({'error': 'Cannot cancel a completed transfer.'}), 400

        cursor.execute("UPDATE transfers SET status = 'Cancelled' WHERE id = ?", (transfer_id,))
        log_audit(conn, 1, 'Manager', 'Inventory Manager', 'CANCEL_TRANSFER', 'Transfer', t['reference_no'])
        conn.commit()
        return jsonify({'success': True, 'message': f"Transfer {t['reference_no']} cancelled."})
    finally:
        conn.close()
