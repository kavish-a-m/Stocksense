from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from backend.inventory_service import apply_adjustment

adjustment_bp = Blueprint('adjustments', __name__)

@adjustment_bp.route('/api/adjustments', methods=['GET'])
def get_adjustments():
    product_id = request.args.get('product_id')
    warehouse_id = request.args.get('warehouse_id')
    reason = request.args.get('reason')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT a.*, p.name as product_name, p.sku, p.uom,
               w.name as warehouse_name, w.code as warehouse_code,
               l.name as location_name, l.code as location_code,
               u.name as user_name
        FROM adjustments a
        JOIN products p ON a.product_id = p.id
        JOIN warehouses w ON a.warehouse_id = w.id
        JOIN locations l ON a.location_id = l.id
        LEFT JOIN users u ON a.user_id = u.id
        WHERE 1=1
    """
    params = []

    if product_id:
        query += " AND a.product_id = ?"
        params.append(product_id)
    if warehouse_id:
        query += " AND a.warehouse_id = ?"
        params.append(warehouse_id)
    if reason:
        query += " AND a.reason = ?"
        params.append(reason)

    query += " ORDER BY a.id DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@adjustment_bp.route('/api/adjustments', methods=['POST'])
def create_adjustment():
    data = request.get_json() or {}
    product_id = data.get('product_id')
    warehouse_id = data.get('warehouse_id')
    location_id = data.get('location_id')
    counted_qty = data.get('counted_qty')
    reason = data.get('reason', 'Counting Error')
    notes = data.get('notes', '')
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Inventory Manager')
    role = data.get('role', 'Inventory Manager')

    if not product_id or not warehouse_id or not location_id or counted_qty is None:
        return jsonify({'error': 'Product, warehouse, location, and counted quantity are required.'}), 400

    try:
        res = apply_adjustment(
            product_id=product_id,
            warehouse_id=warehouse_id,
            location_id=location_id,
            counted_qty=counted_qty,
            reason=reason,
            user_id=user_id,
            user_name=user_name,
            role=role,
            notes=notes
        )
        return jsonify(res), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@adjustment_bp.route('/api/adjustments/bulk-count', methods=['POST'])
def bulk_stock_count():
    """
    Stock Count Mode: Accepts a list of product adjustments for a specific location.
    Applies each adjustment where difference != 0.
    """
    data = request.get_json() or {}
    warehouse_id = data.get('warehouse_id')
    location_id = data.get('location_id')
    items = data.get('items', [])
    reason = data.get('reason', 'Counting Error')
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Warehouse Staff')
    role = data.get('role', 'Warehouse Staff')

    if not warehouse_id or not location_id or not items:
        return jsonify({'error': 'Warehouse, location, and items list are required.'}), 400

    applied_count = 0
    results = []

    for item in items:
        p_id = item.get('product_id')
        system_qty = float(item.get('system_qty', 0.0))
        counted_qty = float(item.get('counted_qty', system_qty))
        item_reason = item.get('reason', reason)
        notes = item.get('notes', 'Physical stock cycle count')

        if system_qty != counted_qty:
            try:
                res = apply_adjustment(
                    product_id=p_id,
                    warehouse_id=warehouse_id,
                    location_id=location_id,
                    counted_qty=counted_qty,
                    reason=item_reason,
                    user_id=user_id,
                    user_name=user_name,
                    role=role,
                    notes=notes
                )
                results.append(res)
                applied_count += 1
            except Exception as e:
                return jsonify({'error': f"Failed adjusting item {p_id}: {str(e)}"}), 400

    return jsonify({
        'success': True,
        'message': f"Cycle count completed. {applied_count} discrepancies adjusted in stock ledger.",
        'applied_adjustments': results
    })
