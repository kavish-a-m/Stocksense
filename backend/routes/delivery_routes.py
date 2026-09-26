from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import (
    check_delivery_stock_availability,
    reserve_delivery_stock,
    validate_delivery,
    log_audit,
    create_notification
)

delivery_bp = Blueprint('deliveries', __name__)

@delivery_bp.route('/api/deliveries', methods=['GET'])
def get_deliveries():
    status = request.args.get('status')
    warehouse_id = request.args.get('warehouse_id')
    search = request.args.get('search', '').strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT d.*, w.name as warehouse_name, w.code as warehouse_code,
               l.name as source_location_name, l.code as source_location_code,
               u.name as responsible_user_name,
               COUNT(di.id) as item_count,
               COALESCE(SUM(di.requested_qty), 0) as total_requested_qty,
               COALESCE(SUM(di.reserved_qty), 0) as total_reserved_qty
        FROM deliveries d
        JOIN warehouses w ON d.source_warehouse_id = w.id
        JOIN locations l ON d.source_location_id = l.id
        LEFT JOIN users u ON d.responsible_user_id = u.id
        LEFT JOIN delivery_items di ON d.id = di.delivery_id
        WHERE 1=1
    """
    params = []

    if status:
        query += " AND d.status = ?"
        params.append(status)
    if warehouse_id:
        query += " AND d.source_warehouse_id = ?"
        params.append(warehouse_id)

    query += " GROUP BY d.id ORDER BY d.id DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    deliveries = []
    for r in rows:
        item = dict(r)
        if search:
            if search not in item['reference_no'].lower() and search not in item['customer_name'].lower():
                continue
        deliveries.append(item)

    conn.close()
    return jsonify(deliveries)

@delivery_bp.route('/api/deliveries/<int:delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT d.*, w.name as warehouse_name, w.code as warehouse_code,
               l.name as source_location_name, l.code as source_location_code,
               u.name as responsible_user_name
        FROM deliveries d
        JOIN warehouses w ON d.source_warehouse_id = w.id
        JOIN locations l ON d.source_location_id = l.id
        LEFT JOIN users u ON d.responsible_user_id = u.id
        WHERE d.id = ?
    """, (delivery_id,))
    delivery = cursor.fetchone()

    if not delivery:
        conn.close()
        return jsonify({'error': 'Delivery not found.'}), 404

    res = dict(delivery)

    cursor.execute("""
        SELECT di.*, p.name as product_name, p.sku, p.barcode, p.uom, p.selling_price,
               s.on_hand as current_location_on_hand, s.reserved as current_location_reserved
        FROM delivery_items di
        JOIN products p ON di.product_id = p.id
        LEFT JOIN stock s ON (p.id = s.product_id AND s.location_id = ?)
        WHERE di.delivery_id = ?
    """, (delivery['source_location_id'], delivery_id))
    res['items'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(res)

@delivery_bp.route('/api/deliveries', methods=['POST'])
def create_delivery():
    data = request.get_json() or {}
    customer_name = data.get('customer_name', '').strip()
    source_warehouse_id = data.get('source_warehouse_id')
    source_location_id = data.get('source_location_id')
    scheduled_date = data.get('scheduled_date', datetime.now().strftime('%Y-%m-%d'))
    responsible_user_id = data.get('responsible_user_id', 1)
    notes = data.get('notes', '')
    items = data.get('items', [])
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    if not customer_name or not source_warehouse_id or not source_location_id:
        return jsonify({'error': 'Customer name, source warehouse, and source location are required.'}), 400

    if not items:
        return jsonify({'error': 'At least one product item is required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        # Generate reference number WH/OUT/XXXX
        cursor.execute("SELECT MAX(id) as max_id FROM deliveries")
        max_id = (cursor.fetchone()['max_id'] or 0) + 1
        ref_no = f"WH/OUT/{max_id:04d}"

        cursor.execute("""
            INSERT INTO deliveries (reference_no, customer_name, source_warehouse_id, source_location_id, scheduled_date, responsible_user_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, 'Draft', ?)
        """, (ref_no, customer_name, source_warehouse_id, source_location_id, scheduled_date, responsible_user_id, notes))
        delivery_id = cursor.lastrowid

        for item in items:
            p_id = item.get('product_id')
            qty = float(item.get('requested_qty', 1.0))
            price = float(item.get('unit_price', 0.0))
            cursor.execute("""
                INSERT INTO delivery_items (delivery_id, product_id, requested_qty, reserved_qty, picked_qty, packed_qty, unit_price)
                VALUES (?, ?, ?, 0.0, 0.0, 0.0, ?)
            """, (delivery_id, p_id, qty, price))

        log_audit(conn, responsible_user_id, user_name, role, 'CREATE_DELIVERY', 'Delivery', ref_no,
                  new_values={'customer': customer_name, 'items_count': len(items)})

        create_notification(conn, 'delivery', f"Delivery Order Created: {ref_no}",
                            f"Draft delivery created for {customer_name} ({len(items)} line items).", 'info',
                            link=f"/deliveries?id={delivery_id}")

        conn.commit()
        return jsonify({'id': delivery_id, 'reference_no': ref_no, 'status': 'Draft', 'message': f'Delivery {ref_no} created successfully.'}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@delivery_bp.route('/api/deliveries/<int:delivery_id>/check-availability', methods=['GET'])
def check_availability(delivery_id):
    try:
        result = check_delivery_stock_availability(delivery_id)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/api/deliveries/<int:delivery_id>/reserve', methods=['POST'])
def reserve_stock_endpoint(delivery_id):
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    try:
        result = reserve_delivery_stock(delivery_id, user_id=user_id, user_name=user_name, role=role)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/api/deliveries/<int:delivery_id>/pick', methods=['POST'])
def pick_items_endpoint(delivery_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE delivery_items SET picked_qty = requested_qty WHERE delivery_id = ?", (delivery_id,))
        cursor.execute("UPDATE deliveries SET status = 'Picked' WHERE id = ? AND status IN ('Draft', 'Waiting', 'Ready')", (delivery_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'All items picked from storage.'})
    finally:
        conn.close()

@delivery_bp.route('/api/deliveries/<int:delivery_id>/pack', methods=['POST'])
def pack_items_endpoint(delivery_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE delivery_items SET packed_qty = requested_qty WHERE delivery_id = ?", (delivery_id,))
        cursor.execute("UPDATE deliveries SET status = 'Packed' WHERE id = ? AND status IN ('Ready', 'Picked')", (delivery_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'All items packed and staged for shipment.'})
    finally:
        conn.close()

@delivery_bp.route('/api/deliveries/<int:delivery_id>/validate', methods=['POST'])
def validate_delivery_endpoint(delivery_id):
    data = request.get_json() or {}
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    try:
        result = validate_delivery(delivery_id, user_id=user_id, user_name=user_name, role=role)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@delivery_bp.route('/api/deliveries/<int:delivery_id>/cancel', methods=['POST'])
def cancel_delivery(delivery_id):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deliveries WHERE id = ?", (delivery_id,))
        d = cursor.fetchone()
        if not d:
            return jsonify({'error': 'Delivery not found.'}), 404
        if d['status'] == 'Done':
            return jsonify({'error': 'Cannot cancel a delivered order.'}), 400

        # Release any reserved stock
        cursor.execute("SELECT * FROM delivery_items WHERE delivery_id = ?", (delivery_id,))
        items = cursor.fetchall()
        for item in items:
            res_qty = item['reserved_qty'] or 0.0
            if res_qty > 0:
                cursor.execute("""
                    UPDATE stock SET reserved = MAX(0.0, reserved - ?)
                    WHERE product_id = ? AND location_id = ?
                """, (res_qty, item['product_id'], d['source_location_id']))

        cursor.execute("UPDATE deliveries SET status = 'Cancelled' WHERE id = ?", (delivery_id,))
        log_audit(conn, 1, 'Manager', 'Inventory Manager', 'CANCEL_DELIVERY', 'Delivery', d['reference_no'])
        conn.commit()
        return jsonify({'success': True, 'message': f"Delivery {d['reference_no']} cancelled and reservations released."})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()
