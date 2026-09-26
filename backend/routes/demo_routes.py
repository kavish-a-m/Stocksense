from flask import Blueprint, request, jsonify
from backend.seed_data import seed_database
from backend.database import get_db_connection
from backend.inventory_service import log_audit

demo_bp = Blueprint('demo', __name__)

@demo_bp.route('/api/demo/reset', methods=['POST'])
def reset_demo():
    try:
        seed_database()
        return jsonify({
            'success': True,
            'message': 'StockSense demo database reset and reseeded with clean realistic inventory data!'
        })
    except Exception as e:
        return jsonify({'error': f'Failed to reset demo data: {str(e)}'}), 500

@demo_bp.route('/api/settings', methods=['GET'])
def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM settings")
    rows = cursor.fetchall()
    settings = {r['key']: r['value'] for r in rows}
    conn.close()
    return jsonify(settings)

@demo_bp.route('/api/settings', methods=['PUT'])
def update_settings():
    data = request.get_json() or {}
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        for k, v in data.items():
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, str(v)))
        log_audit(conn, 1, 'Admin', 'Admin', 'UPDATE_SETTINGS', 'Settings', 'SYSTEM', new_values=data)
        conn.commit()
        return jsonify({'success': True, 'message': 'System settings updated successfully.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        conn.close()
