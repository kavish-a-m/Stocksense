from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from backend.inventory_service import log_audit

warehouse_bp = Blueprint('warehouses', __name__)

@warehouse_bp.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT w.*, 
               COUNT(DISTINCT l.id) as location_count,
               COALESCE(SUM(s.on_hand), 0) as total_stock_units,
               COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_valuation,
               COUNT(DISTINCT s.product_id) as total_skus
        FROM warehouses w
        LEFT JOIN locations l ON w.id = l.warehouse_id
        LEFT JOIN stock s ON w.id = s.warehouse_id
        LEFT JOIN products p ON s.product_id = p.id
        GROUP BY w.id
        ORDER BY w.name ASC
    """)
    whs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(whs)

@warehouse_bp.route('/api/warehouses', methods=['POST'])
def create_warehouse():
    data = request.get_json() or {}
    code = data.get('code', '').strip().upper()
    name = data.get('name', '').strip()
    address = data.get('address', '').strip()

    if not code or not name:
        return jsonify({'error': 'Warehouse code and name are required.'}), 400

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO warehouses (code, name, address, is_active)
            VALUES (?, ?, ?, 1)
        """, (code, name, address))
        wh_id = cursor.lastrowid

        # Auto-create default location for this warehouse
        cursor.execute("""
            INSERT INTO locations (warehouse_id, code, name, type)
            VALUES (?, ?, ?, 'internal')
        """, (wh_id, f"LOC-{code}-MAIN", f"{name} Default Storage"))

        log_audit(conn, 1, 'Admin', 'Admin', 'CREATE_WAREHOUSE', 'Warehouse', wh_id, new_values={'code': code, 'name': name})
        conn.commit()
        return jsonify({'id': wh_id, 'code': code, 'name': name, 'address': address}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@warehouse_bp.route('/api/locations', methods=['GET'])
def get_locations():
    wh_id = request.args.get('warehouse_id')
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT l.*, w.name as warehouse_name, w.code as warehouse_code,
               COALESCE(SUM(s.on_hand), 0) as total_stock_units,
               COUNT(DISTINCT s.product_id) as total_skus
        FROM locations l
        JOIN warehouses w ON l.warehouse_id = w.id
        LEFT JOIN stock s ON l.id = s.location_id
    """
    params = []
    if wh_id:
        query += " WHERE l.warehouse_id = ?"
        params.append(wh_id)

    query += " GROUP BY l.id ORDER BY w.name, l.name ASC"
    cursor.execute(query, params)
    locs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(locs)

@warehouse_bp.route('/api/locations', methods=['POST'])
def create_location():
    data = request.get_json() or {}
    warehouse_id = data.get('warehouse_id')
    code = data.get('code', '').strip().upper()
    name = data.get('name', '').strip()
    loc_type = data.get('type', 'internal')

    if not warehouse_id or not code or not name:
        return jsonify({'error': 'Warehouse ID, code, and name are required.'}), 400

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO locations (warehouse_id, code, name, type)
            VALUES (?, ?, ?, ?)
        """, (warehouse_id, code, name, loc_type))
        loc_id = cursor.lastrowid
        log_audit(conn, 1, 'Admin', 'Admin', 'CREATE_LOCATION', 'Location', loc_id, new_values={'code': code, 'name': name})
        conn.commit()
        return jsonify({'id': loc_id, 'warehouse_id': warehouse_id, 'code': code, 'name': name, 'type': loc_type}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()
