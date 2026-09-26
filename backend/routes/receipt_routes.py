from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import validate_receipt, log_audit, create_notification

receipt_bp = Blueprint('receipts', __name__)

@receipt_bp.route('/api/receipts', methods=['GET'])
def get_receipts():
    status = request.args.get('status')
    warehouse_id = request.args.get('warehouse_id')
    search = request.args.get('search', '').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT r.*, w.name as warehouse_name, w.code as warehouse_code,
               l.name as destination_location_name, l.code as destination_location_code,
               u.name as responsible_user_name,
               COUNT(ri.id) as item_count,
               COALESCE(SUM(ri.expected_qty), 0) as total_expected_qty,
               COALESCE(SUM(ri.received_qty), 0) as total_received_qty
        FROM receipts r
        JOIN warehouses w ON r.warehouse_id = w.id
        JOIN locations l ON r.destination_location_id = l.id
        LEFT JOIN users u ON r.responsible_user_id = u.id
        LEFT JOIN receipt_items ri ON r.id = ri.receipt_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND r.status = ?"
        params.append(status)
    if warehouse_id:
        query += " AND r.warehouse_id = ?"
        params.append(warehouse_id)

    query += " GROUP BY r.id ORDER BY r.id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    receipts = []
    for r in rows:
        item = dict(r)
        if search:
            if search not in item['reference_no'].lower() and search not in item['supplier_name'].lower():
                continue
        receipts.append(item)

    conn.close()
    return jsonify(receipts)

@receipt_bp.route('/api/receipts/<int:receipt_id>', methods=['GET'])
def get_receipt(receipt_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT r.*, w.name as warehouse_name, w.code as warehouse_code,
               l.name as destination_location_name, l.code as destination_location_code,
               u.name as responsible_user_name
        FROM receipts r
        JOIN warehouses w ON r.warehouse_id = w.id
        JOIN locations l ON r.destination_location_id = l.id
        LEFT JOIN users u ON r.responsible_user_id = u.id
        WHERE r.id = ?
    """, (receipt_id,))
    receipt = cursor.fetchone()

    if not receipt:
        conn.close()
        return jsonify({'error': 'Receipt not found.'}), 404

    res = dict(receipt)

    cursor.execute("""
        SELECT ri.*, p.name as product_name, p.sku, p.barcode, p.uom, p.cost_price
        FROM receipt_items ri
        JOIN products p ON ri.product_id = p.id
        WHERE ri.receipt_id = ?
    """, (receipt_id,))
    res['items'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(res)

@receipt_bp.route('/api/receipts', methods=['POST'])
def create_receipt():
    data = request.get_json() or {}
    supplier_name = data.get('supplier_name', '').strip()
    warehouse_id = data.get('warehouse_id')
    destination_location_id = data.get('destination_location_id')
    scheduled_date = data.get('scheduled_date', datetime.now().strftime('%Y-%m-%d'))
    responsible_user_id = data.get('responsible_user_id', 1)
    notes = data.get('notes', '')
    items = data.get('items', [])
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    if not supplier_name or not warehouse_id or not destination_location_id:
        return jsonify({'error': 'Supplier name, warehouse, and destination location are required.'}), 400

    if not items:
        return jsonify({'error': 'At least one product item is required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        # Generate reference number WH/IN/XXXX
        cursor.execute("SELECT MAX(id) as max_id FROM receipts")
        max_id = (cursor.fetchone()['max_id'] or 0) + 1
        ref_no = f"WH/IN/{max_id:04d}"

        cursor.execute("""
            INSERT INTO receipts (reference_no, supplier_name, warehouse_id, destination_location_id, scheduled_date, responsible_user_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Draft', ?)
        """, (ref_no, supplier_name, warehouse_id, destination_location_id, scheduled_date, responsible_user_id, notes))
        receipt_id = cursor.lastrowid

        for item in items:
            p_id = item.get('product_id')
            qty = float(item.get('expected_qty', 1.0))
            cost = float(item.get('unit_cost', 0.0))
            cursor.execute("""
                INSERT INTO receipt_items (receipt_id, product_id, expected_qty, received_qty, unit_cost)
                VALUES (?, ?, ?, 0.0, ?)
            """, (receipt_id, p_id, qty, cost))

        log_audit(conn, responsible_user_id, user_name, role, 'CREATE_RECEIPT', 'Receipt', ref_no,
                  new_values={'supplier': supplier_name, 'items_count': len(items)})

        create_notification(conn, 'receipt', f"Receipt Created: {ref_no}", f"Draft receipt created for {supplier_name} with {len(items)} items.", 'info', link=f"/receipts?id={receipt_id}")

        conn.commit()
        return jsonify({'id': receipt_id, 'reference_no': ref_no, 'status': 'Draft', 'message': f'Receipt {ref_no} created successfully.'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@receipt_bp.route('/api/receipts/<int:receipt_id>/ready', methods=['POST'])
def mark_receipt_ready(receipt_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE receipts SET status = 'Ready' WHERE id = ? AND status IN ('Draft', 'Waiting')", (receipt_id,))
        if cursor.rowcount == 0:
            return jsonify({'error': 'Receipt is not in Draft or Waiting state.'}), 400
        conn.commit()
        return jsonify({'success': True, 'message': 'Receipt marked as Ready for receiving.'})
    finally:
        conn.close()

@receipt_bp.route('/api/receipts/<int:receipt_id>/validate', methods=['POST'])
def validate_receipt_endpoint(receipt_id):
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    try:
        result = validate_receipt(receipt_id, user_id=user_id, user_name=user_name, role=role)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@receipt_bp.route('/api/receipts/<int:receipt_id>/cancel', methods=['POST'])
def cancel_receipt(receipt_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status, reference_no FROM receipts WHERE id = ?", (receipt_id,))
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'Receipt not found.'}), 404
        if r['status'] == 'Done':
            return jsonify({'error': 'Cannot cancel a completed receipt.'}), 400

        cursor.execute("UPDATE receipts SET status = 'Cancelled' WHERE id = ?", (receipt_id,))
        log_audit(conn, 1, 'Manager', 'Inventory Manager', 'CANCEL_RECEIPT', 'Receipt', r['reference_no'])
        conn.commit()
        return jsonify({'success': True, 'message': f"Receipt {r['reference_no']} cancelled."})
    finally:
        conn.close()
