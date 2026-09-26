import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'stocksense.db')

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('Admin', 'Inventory Manager', 'Warehouse Staff', 'Viewer')),
        warehouse_id INTEGER,
        avatar TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Categories table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        code TEXT UNIQUE NOT NULL,
        description TEXT,
        color TEXT DEFAULT '#4f46e5',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Warehouses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        address TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Locations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        warehouse_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        type TEXT DEFAULT 'internal' CHECK(type IN ('internal', 'vendor', 'customer', 'production', 'loss', 'quarantine')),
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
        UNIQUE(warehouse_id, code)
    );
    """)

    # Products table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT UNIQUE NOT NULL,
        barcode TEXT UNIQUE NOT NULL,
        category_id INTEGER NOT NULL,
        uom TEXT NOT NULL DEFAULT 'Units',
        cost_price REAL NOT NULL DEFAULT 0.0,
        selling_price REAL NOT NULL DEFAULT 0.0,
        reorder_level REAL NOT NULL DEFAULT 10.0,
        reorder_qty REAL NOT NULL DEFAULT 50.0,
        lead_time_days INTEGER NOT NULL DEFAULT 5,
        default_warehouse_id INTEGER,
        default_location_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Active' CHECK(status IN ('Active', 'Archived', 'Discontinued')),
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(category_id) REFERENCES categories(id),
        FOREIGN KEY(default_warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(default_location_id) REFERENCES locations(id)
    );
    """)

    # Stock table (per product and location)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        warehouse_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        on_hand REAL NOT NULL DEFAULT 0.0,
        reserved REAL NOT NULL DEFAULT 0.0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id) ON DELETE CASCADE,
        FOREIGN KEY(location_id) REFERENCES locations(id) ON DELETE CASCADE,
        UNIQUE(product_id, location_id)
    );
    """)

    # Receipts table (Incoming)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE NOT NULL,
        supplier_name TEXT NOT NULL,
        warehouse_id INTEGER NOT NULL,
        destination_location_id INTEGER NOT NULL,
        scheduled_date TEXT NOT NULL,
        responsible_user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Waiting', 'Ready', 'Done', 'Cancelled')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        validated_at TIMESTAMP,
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(destination_location_id) REFERENCES locations(id),
        FOREIGN KEY(responsible_user_id) REFERENCES users(id)
    );
    """)

    # Receipt Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS receipt_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        receipt_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        expected_qty REAL NOT NULL,
        received_qty REAL NOT NULL DEFAULT 0.0,
        unit_cost REAL DEFAULT 0.0,
        FOREIGN KEY(receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)

    # Deliveries table (Outgoing)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE NOT NULL,
        customer_name TEXT NOT NULL,
        source_warehouse_id INTEGER NOT NULL,
        source_location_id INTEGER NOT NULL,
        scheduled_date TEXT NOT NULL,
        responsible_user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Waiting', 'Ready', 'Picked', 'Packed', 'Done', 'Cancelled')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        validated_at TIMESTAMP,
        FOREIGN KEY(source_warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(source_location_id) REFERENCES locations(id),
        FOREIGN KEY(responsible_user_id) REFERENCES users(id)
    );
    """)

    # Delivery Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS delivery_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        delivery_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        requested_qty REAL NOT NULL,
        reserved_qty REAL NOT NULL DEFAULT 0.0,
        picked_qty REAL NOT NULL DEFAULT 0.0,
        packed_qty REAL NOT NULL DEFAULT 0.0,
        unit_price REAL DEFAULT 0.0,
        FOREIGN KEY(delivery_id) REFERENCES deliveries(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)

    # Internal Transfers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE NOT NULL,
        source_warehouse_id INTEGER NOT NULL,
        source_location_id INTEGER NOT NULL,
        dest_warehouse_id INTEGER NOT NULL,
        dest_location_id INTEGER NOT NULL,
        scheduled_date TEXT NOT NULL,
        responsible_user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'Draft' CHECK(status IN ('Draft', 'Waiting', 'Ready', 'Done', 'Cancelled')),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        FOREIGN KEY(source_warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(source_location_id) REFERENCES locations(id),
        FOREIGN KEY(dest_warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(dest_location_id) REFERENCES locations(id),
        FOREIGN KEY(responsible_user_id) REFERENCES users(id)
    );
    """)

    # Transfer Items table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transfer_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity REAL NOT NULL,
        FOREIGN KEY(transfer_id) REFERENCES transfers(id) ON DELETE CASCADE,
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)

    # Inventory Adjustments table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS adjustments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE NOT NULL,
        warehouse_id INTEGER NOT NULL,
        location_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        system_qty REAL NOT NULL,
        counted_qty REAL NOT NULL,
        diff_qty REAL NOT NULL,
        reason TEXT NOT NULL CHECK(reason IN ('Damaged', 'Lost', 'Expired', 'Counting Error', 'Theft', 'Data Correction', 'Other')),
        user_id INTEGER,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(location_id) REFERENCES locations(id),
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)

    # Stock Ledger (Immutable stock move history)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stock_ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        transaction_id TEXT NOT NULL,
        transaction_type TEXT NOT NULL CHECK(transaction_type IN ('Receipt', 'Delivery', 'Internal Transfer', 'Adjustment', 'Initial Stock')),
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        sku TEXT NOT NULL,
        warehouse_id INTEGER NOT NULL,
        warehouse_name TEXT NOT NULL,
        location_id INTEGER NOT NULL,
        location_name TEXT NOT NULL,
        qty_in REAL NOT NULL DEFAULT 0.0,
        qty_out REAL NOT NULL DEFAULT 0.0,
        balance_after REAL NOT NULL,
        user_id INTEGER,
        user_name TEXT,
        reference_no TEXT NOT NULL,
        reason TEXT,
        FOREIGN KEY(product_id) REFERENCES products(id),
        FOREIGN KEY(warehouse_id) REFERENCES warehouses(id),
        FOREIGN KEY(location_id) REFERENCES locations(id)
    );
    """)

    # Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        user_name TEXT,
        role TEXT,
        action TEXT NOT NULL,
        object_type TEXT NOT NULL,
        object_id TEXT,
        old_values TEXT,
        new_values TEXT,
        ip_address TEXT DEFAULT '127.0.0.1',
        device TEXT DEFAULT 'Desktop Browser'
    );
    """)

    # Notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        type TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT DEFAULT 'info' CHECK(severity IN ('info', 'success', 'warning', 'danger')),
        is_read INTEGER DEFAULT 0,
        link TEXT
    );
    """)

    # Create Indexes for maximum query performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_prod_loc ON stock(product_id, location_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_prod ON stock_ledger(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_timestamp ON stock_ledger(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_ref ON receipts(reference_no);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_deliveries_ref ON deliveries(reference_no);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transfers_ref ON transfers(reference_no);")

    # Set default system settings
    default_settings = {
        'company_name': 'StockSense Enterprise Logistics',
        'allow_negative_stock': 'false',
        'low_stock_auto_alert': 'true',
        'currency_symbol': '$',
        'date_format': 'YYYY-MM-DD',
        'reorder_lead_time_buffer': '2'
    }
    for k, v in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?);", (k, v))

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized successfully at", DB_PATH)
