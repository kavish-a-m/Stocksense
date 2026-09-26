from flask import Blueprint, request, jsonify
from backend.inventory_service import get_dashboard_summary, calculate_reorder_recommendations
from backend.assistant_service import process_assistant_query

analytics_bp = Blueprint('analytics', __name__)

@analytics_bp.route('/api/dashboard/summary', methods=['GET'])
def dashboard_summary():
    try:
        summary = get_dashboard_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@analytics_bp.route('/api/analytics/reorders', methods=['GET'])
def get_reorder_recommendations():
    try:
        reorders = calculate_reorder_recommendations()
        return jsonify(reorders)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@analytics_bp.route('/api/assistant/query', methods=['POST'])
def assistant_query():
    data = request.get_json() or {}
    query_text = data.get('query', '').strip()

    if not query_text:
        return jsonify({'error': 'Query text cannot be empty.'}), 400

    try:
        response = process_assistant_query(query_text)
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 400
