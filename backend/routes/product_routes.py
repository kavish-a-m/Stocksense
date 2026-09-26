from flask import Blueprint, request, jsonify
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import log_audit, get_or_create_stock

product_bp = Blueprint('products', __name__)

# ==================== CATEGORIES ====================

@product_bp.route('/api/categories', methods=['GET'])
def get_categories():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.*, COUNT(p.id) as product_count
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        GROUP BY c.id
        ORDER BY c.name ASC
    """)
    cats = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(cats)

@product_bp.route('/api/categories', methods=['POST'])
def create_category():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    code = data.get('code', '').strip().upper()
    description = data.get('description', '')
    color = data.get('color', '#4f46e5')

    if not name or not code:
        return jsonify({'error': 'Category name and code are required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO categories (name, code, description, color)
            VALUES (?, ?, ?, ?)
        """, (name, code, description, color))
        cat_id = cursor.lastrowid
        log_audit(conn, 1, 'Admin', 'Admin', 'CREATE_CATEGORY', 'Category', cat_id, new_values={'name': name, 'code': code})
        conn.commit()
        return jsonify({'id': cat_id, 'name': name, 'code': code, 'description': description, 'color': color}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Category creation failed: {str(e)}'}), 400
    finally:
        conn.close()

# ==================== PRODUCTS ====================

@product_bp.route('/api/products', methods=['GET'])
def get_products():
    search = request.args.get('search', '').strip().lower()
    category_id = request.args.get('category_id')
    warehouse_id = request.args.get('warehouse_id')
    stock_status = request.args.get('stock_status')
    
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT p.*, c.name as category_name, c.color as category_color,
               w.name as default_warehouse_name, l.name as default_location_name,
               COALESCE(SUM(s.on_hand), 0) as total_on_hand,
               COALESCE(SUM(s.reserved), 0) as total_reserved
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN warehouses w ON p.default_warehouse_id = w.id
        LEFT JOIN locations l ON p.default_location_id = l.id
        LEFT JOIN stock s ON p.id = s.product_id
        WHERE 1=1
    """
    params = []

    if category_id:
        query += " AND p.category_id = ?"
        params.append(category_id)

    query += " GROUP BY p.id ORDER BY p.name ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()

    products = []
    for r in rows:
        item = dict(r)
        on_hand = item['total_on_hand']
        reserved = item['total_reserved']
        available = max(0.0, on_hand - reserved)
        reorder_level = item['reorder_level']

        status = 'In Stock'
        if on_hand == 0:
            status = 'Out of Stock'
        elif available <= reorder_level:
            status = 'Low Stock'
        elif available > (reorder_level * 4) and reorder_level > 0:
            status = 'Overstocked'

        item['available_stock'] = available
        item['stock_status'] = status
        item['inventory_value'] = round(on_hand * item['cost_price'], 2)

        # Filters on computed status or search
        if stock_status and item['stock_status'] != stock_status:
            continue

        if search:
            if search not in item['name'].lower() and search not in item['sku'].lower() and search not in item['barcode'].lower():
                continue

        products.append(item)

    conn.close()
    return jsonify(products)

@product_bp.route('/api/products/<int:prod_id>', methods=['GET'])
def get_product(prod_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.*, c.name as category_name, c.color as category_color,
               w.name as default_warehouse_name, l.name as default_location_name,
               COALESCE(SUM(s.on_hand), 0) as total_on_hand,
               COALESCE(SUM(s.reserved), 0) as total_reserved
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN warehouses w ON p.default_warehouse_id = w.id
        LEFT JOIN locations l ON p.default_location_id = l.id
        LEFT JOIN stock s ON p.id = s.product_id
        WHERE p.id = ?
        GROUP BY p.id
    """, (prod_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': 'Product not found.'}), 404

    prod = dict(row)
    prod['available_stock'] = max(0.0, prod['total_on_hand'] - prod['total_reserved'])
    
    # Stock status
    if prod['total_on_hand'] == 0:
        prod['stock_status'] = 'Out of Stock'
    elif prod['available_stock'] <= prod['reorder_level']:
        prod['stock_status'] = 'Low Stock'
    else:
        prod['stock_status'] = 'In Stock'

    # Fetch location breakdowns
    cursor.execute("""
        SELECT s.*, w.name as warehouse_name, w.code as warehouse_code,
               l.name as location_name, l.code as location_code, l.type as location_type
        FROM stock s
        JOIN warehouses w ON s.warehouse_id = w.id
        JOIN locations l ON s.location_id = l.id
        WHERE s.product_id = ?
        ORDER BY w.name, l.name
    """, (prod_id,))
    prod['locations'] = [dict(r) for r in cursor.fetchall()]

    # Fetch recent movements
    cursor.execute("""
        SELECT * FROM stock_ledger
        WHERE product_id = ?
        ORDER BY timestamp DESC
        LIMIT 15
    """, (prod_id,))
    prod['recent_movements'] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify(prod)

@product_bp.route('/api/products', methods=['POST'])
def create_product():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    sku = data.get('sku', '').strip().upper()
    barcode = data.get('barcode', '').strip()
    category_id = data.get('category_id')
    uom = data.get('uom', 'Units')
    cost_price = float(data.get('cost_price', 0.0))
    selling_price = float(data.get('selling_price', 0.0))
    reorder_level = float(data.get('reorder_level', 10.0))
    reorder_qty = float(data.get('reorder_qty', 50.0))
    lead_time_days = int(data.get('lead_time_days', 5))
    default_warehouse_id = data.get('default_warehouse_id', 1)
    default_location_id = data.get('default_location_id', 1)
    initial_stock = float(data.get('initial_stock', 0.0))
    user_id = data.get('user_id', 1)
    user_name = data.get('user_name', 'Admin')

    if not name or not sku:
        return jsonify({'error': 'Product name and SKU are required.'}), 400

    if not barcode:
        barcode = f"890{datetime.now().strftime('%m%d%H%M%S')}"

    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        # Check SKU uniqueness
        cursor.execute("SELECT id FROM products WHERE sku = ?", (sku,))
        if cursor.fetchone():
            return jsonify({'error': f'Product with SKU {sku} already exists.'}), 400

        cursor.execute("""
            INSERT INTO products (
                name, sku, barcode, category_id, uom, cost_price, selling_price,
                reorder_level, reorder_qty, lead_time_days, default_warehouse_id, default_location_id, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
        """, (name, sku, barcode, category_id, uom, cost_price, selling_price,
              reorder_level, reorder_qty, lead_time_days, default_warehouse_id, default_location_id))
        
        prod_id = cursor.lastrowid
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Add initial stock if provided
        if initial_stock > 0 and default_location_id:
            cursor.execute("""
                INSERT INTO stock (product_id, warehouse_id, location_id, on_hand, reserved, updated_at)
                VALUES (?, ?, ?, ?, 0.0, ?)
            """, (prod_id, default_warehouse_id, default_location_id, initial_stock, now_str))

            cursor.execute("SELECT name FROM warehouses WHERE id = ?", (default_warehouse_id,))
            wh_name = cursor.fetchone()['name']
            cursor.execute("SELECT name FROM locations WHERE id = ?", (default_location_id,))
            loc_name = cursor.fetchone()['name']

            cursor.execute("""
                INSERT INTO stock_ledger (
                    timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                    warehouse_id, warehouse_name, location_id, location_name,
                    qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
                ) VALUES (?, ?, 'Initial Stock', ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, 'INIT-PROD', 'Initial product creation balance')
            """, (now_str, f"TX-INIT-{prod_id}", prod_id, name, sku,
                  default_warehouse_id, wh_name, default_location_id, loc_name, initial_stock, initial_stock, user_id, user_name))

        log_audit(conn, user_id, user_name, 'Manager', 'CREATE_PRODUCT', 'Product', prod_id, new_values={'name': name, 'sku': sku, 'initial_stock': initial_stock})

        conn.commit()
        return jsonify({'id': prod_id, 'name': name, 'sku': sku, 'barcode': barcode, 'initial_stock': initial_stock}), 201
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@product_bp.route('/api/products/<int:prod_id>', methods=['PUT'])
def update_product(prod_id):
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM products WHERE id = ?", (prod_id,))
        old_prod = cursor.fetchone()
        if not old_prod:
            return jsonify({'error': 'Product not found.'}), 404

        name = data.get('name', old_prod['name'])
        sku = data.get('sku', old_prod['sku'])
        barcode = data.get('barcode', old_prod['barcode'])
        category_id = data.get('category_id', old_prod['category_id'])
        uom = data.get('uom', old_prod['uom'])
        cost_price = float(data.get('cost_price', old_prod['cost_price']))
        selling_price = float(data.get('selling_price', old_prod['selling_price']))
        reorder_level = float(data.get('reorder_level', old_prod['reorder_level']))
        reorder_qty = float(data.get('reorder_qty', old_prod['reorder_qty']))
        lead_time_days = int(data.get('lead_time_days', old_prod['lead_time_days']))
        status = data.get('status', old_prod['status'])

        cursor.execute("""
            UPDATE products SET
                name = ?, sku = ?, barcode = ?, category_id = ?, uom = ?,
                cost_price = ?, selling_price = ?, reorder_level = ?, reorder_qty = ?,
                lead_time_days = ?, status = ?, updated_at = ?
            WHERE id = ?
        """, (name, sku, barcode, category_id, uom, cost_price, selling_price,
              reorder_level, reorder_qty, lead_time_days, status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), prod_id))

        log_audit(conn, 1, 'Manager', 'Inventory Manager', 'UPDATE_PRODUCT', 'Product', prod_id,
                  old_values=dict(old_prod), new_values=data)

        conn.commit()
        return jsonify({'success': True, 'message': 'Product updated successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()

@product_bp.route('/api/products/<int:prod_id>', methods=['DELETE'])
def delete_product(prod_id):
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()
        cursor.execute("SELECT name, sku FROM products WHERE id = ?", (prod_id,))
        prod = cursor.fetchone()
        if not prod:
            return jsonify({'error': 'Product not found.'}), 404

        # Check if there is remaining stock
        cursor.execute("SELECT SUM(on_hand) as total FROM stock WHERE product_id = ?", (prod_id,))
        stk = cursor.fetchone()
        if stk and stk['total'] and stk['total'] > 0:
            return jsonify({'error': f"Cannot delete product with active on-hand stock ({stk['total']} units). Adjust stock to 0 first."}), 400

        cursor.execute("DELETE FROM products WHERE id = ?", (prod_id,))
        log_audit(conn, 1, 'Admin', 'Admin', 'DELETE_PRODUCT', 'Product', prod_id, old_values=dict(prod))
        conn.commit()
        return jsonify({'success': True, 'message': f"Product {prod['name']} deleted."})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()
