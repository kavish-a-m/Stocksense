from flask import Blueprint, request, jsonify
from backend.database import get_db_connection
from backend.inventory_service import calculate_reorder_recommendations

report_bp = Blueprint('reports', __name__)

@report_bp.route('/api/reports/valuation', methods=['GET'])
def get_valuation_report():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Total valuation per product
    cursor.execute("""
        SELECT p.id, p.name, p.sku, c.name as category_name, p.cost_price, p.selling_price, p.uom,
               COALESCE(SUM(s.on_hand), 0) as total_on_hand,
               COALESCE(SUM(s.reserved), 0) as total_reserved,
               COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_cost_value,
               COALESCE(SUM(s.on_hand * p.selling_price), 0) as total_retail_value
        FROM products p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN stock s ON p.id = s.product_id
        GROUP BY p.id
        ORDER BY total_cost_value DESC
    """)
    product_valuations = [dict(r) for r in cursor.fetchall()]

    # Valuation per category
    cursor.execute("""
        SELECT c.id, c.name, c.color,
               COUNT(DISTINCT p.id) as product_count,
               COALESCE(SUM(s.on_hand), 0) as total_units,
               COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_value
        FROM categories c
        LEFT JOIN products p ON c.id = p.category_id
        LEFT JOIN stock s ON p.id = s.product_id
        GROUP BY c.id
        ORDER BY total_value DESC
    """)
    category_valuations = [dict(r) for r in cursor.fetchall()]

    # Valuation per warehouse
    cursor.execute("""
        SELECT w.id, w.name, w.code,
               COUNT(DISTINCT s.product_id) as product_count,
               COALESCE(SUM(s.on_hand), 0) as total_units,
               COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_value
        FROM warehouses w
        LEFT JOIN stock s ON w.id = s.warehouse_id
        LEFT JOIN products p ON s.product_id = p.id
        GROUP BY w.id
        ORDER BY total_value DESC
    """)
    warehouse_valuations = [dict(r) for r in cursor.fetchall()]

    total_cost_val = sum(p['total_cost_value'] for p in product_valuations)
    total_retail_val = sum(p['total_retail_value'] for p in product_valuations)
    total_units = sum(p['total_on_hand'] for p in product_valuations)

    conn.close()
    return jsonify({
        'summary': {
            'total_cost_valuation': round(total_cost_val, 2),
            'total_retail_valuation': round(total_retail_val, 2),
            'total_units': total_units,
            'potential_margin': round(total_retail_val - total_cost_val, 2)
        },
        'by_product': product_valuations,
        'by_category': category_valuations,
        'by_warehouse': warehouse_valuations
    })

@report_bp.route('/api/reports/movements', methods=['GET'])
def get_movements_report():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    product_id = request.args.get('product_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT DATE(timestamp) as move_date,
               transaction_type,
               COUNT(*) as tx_count,
               SUM(qty_in) as total_qty_in,
               SUM(qty_out) as total_qty_out
        FROM stock_ledger
        WHERE 1=1
    """
    params = []
    if date_from:
        query += " AND DATE(timestamp) >= ?"
        params.append(date_from)
    if date_to:
        query += " AND DATE(timestamp) <= ?"
        params.append(date_to)
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)

    query += " GROUP BY DATE(timestamp), transaction_type ORDER BY move_date DESC"
    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)
