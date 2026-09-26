import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

from backend.database import init_db
from backend.routes.auth_routes import auth_bp
from backend.routes.product_routes import product_bp
from backend.routes.warehouse_routes import warehouse_bp
from backend.routes.receipt_routes import receipt_bp
from backend.routes.delivery_routes import delivery_bp
from backend.routes.transfer_routes import transfer_bp
from backend.routes.adjustment_routes import adjustment_bp
from backend.routes.ledger_routes import ledger_bp
from backend.routes.report_routes import report_bp
from backend.routes.analytics_routes import analytics_bp
from backend.routes.demo_routes import demo_bp

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static')

def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR)
    CORS(app)

    # Initialize database
    init_db()

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(warehouse_bp)
    app.register_blueprint(receipt_bp)
    app.register_blueprint(delivery_bp)
    app.register_blueprint(transfer_bp)
    app.register_blueprint(adjustment_bp)
    app.register_blueprint(ledger_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(demo_bp)

    @app.route('/')
    def index():
        return send_from_directory(STATIC_DIR, 'index.html')

    @app.route('/<path:path>')
    def serve_static(path):
        full_path = os.path.join(STATIC_DIR, path)
        if os.path.exists(full_path):
            return send_from_directory(STATIC_DIR, path)
        return send_from_directory(STATIC_DIR, 'index.html')

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'error': 'Resource not found.'}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({'error': 'Internal server error.'}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    print(f"==================================================")
    print(f"StockSense Server starting on http://127.0.0.1:{port}")
    print(f"==================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
