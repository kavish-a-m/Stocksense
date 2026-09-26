import sqlite3
import hashlib
import uuid
from datetime import datetime, timedelta
from backend.database import get_db_connection, init_db

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def seed_database():
    """Wipes and seeds the database with rich, realistic, consistent demo data."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing tables
    tables = [
        'stock_ledger', 'audit_logs', 'notifications',
        'receipt_items', 'receipts',
        'delivery_items', 'deliveries',
        'transfer_items', 'transfers',
        'adjustments', 'stock',
        'products', 'locations', 'warehouses', 'categories', 'users'
    ]
    for tbl in tables:
        cursor.execute(f"DELETE FROM {tbl};")
        cursor.execute(f"DELETE FROM sqlite_sequence WHERE name = '{tbl}';")

    now = datetime.now()
    d_minus = lambda days, hours=0, minutes=0: (now - timedelta(days=days, hours=hours, minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')

    # 1. Users
    users_data = [
        ('Kavish Admin', 'admin@stocksense.com', hash_pw('admin123'), 'Admin', 1, 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100'),
        ('Rahul Sharma', 'manager@stocksense.com', hash_pw('manager123'), 'Inventory Manager', 1, 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100'),
        ('Arjun Singh', 'staff@stocksense.com', hash_pw('staff123'), 'Warehouse Staff', 1, 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100'),
        ('Priya Verma', 'viewer@stocksense.com', hash_pw('viewer123'), 'Viewer', 2, 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100')
    ]
    cursor.executemany("""
        INSERT INTO users (name, email, password_hash, role, warehouse_id, avatar)
        VALUES (?, ?, ?, ?, ?, ?)
    """, users_data)

    # 2. Categories
    categories_data = [
        ('Raw Materials', 'RAW', 'Metals, rods, bulk wire, raw materials', '#3b82f6'),
        ('Finished Goods', 'FNG', 'Manufactured items ready for retail', '#10b981'),
        ('Electronics', 'ELE', 'Hardware, computers, printers, and scanners', '#8b5cf6'),
        ('Office Supplies', 'OFC', 'Stationery, packaging boxes, and tape', '#f59e0b'),
        ('Safety Equipment', 'SAF', 'PPE, helmets, vests, and protective gear', '#ef4444')
    ]
    cursor.executemany("""
        INSERT INTO categories (name, code, description, color)
        VALUES (?, ?, ?, ?)
    """, categories_data)

    # 3. Warehouses
    warehouses_data = [
        ('WH-MAIN', 'Main Central Warehouse', 'Sector 4 Industrial Focal Point, Jalandhar, Punjab', 1),
        ('WH-PROD', 'LPU Production Plant', 'Campus Hub Zone B, Phagwara, Punjab', 1)
    ]
    cursor.executemany("""
        INSERT INTO warehouses (code, name, address, is_active)
        VALUES (?, ?, ?, ?)
    """, warehouses_data)

    # 4. Locations
    locations_data = [
        # Main Warehouse (ID 1)
        (1, 'LOC-MAIN-RACKA', 'Rack A - Heavy Metals', 'internal', 1),
        (1, 'LOC-MAIN-RACKB', 'Rack B - Components & Parts', 'internal', 1),
        (1, 'LOC-MAIN-RECV', 'Inbound Receiving Bay', 'internal', 1),
        (1, 'LOC-MAIN-QUAR', 'Quality Quarantine Bay', 'quarantine', 1),
        # Production Warehouse (ID 2)
        (2, 'LOC-PROD-FLR', 'Production Assembly Floor', 'production', 1),
        (2, 'LOC-PROD-FG', 'Finished Goods Staging', 'internal', 1),
        (2, 'LOC-PROD-RACK1', 'Storage Rack 1 - Tools & Safety', 'internal', 1),
        (2, 'LOC-PROD-LOSS', 'Damaged / Scrap Area', 'loss', 1)
    ]
    cursor.executemany("""
        INSERT INTO locations (warehouse_id, code, name, type, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, locations_data)

    # 5. Products (10 realistic items)
    products_data = [
        # id, name, sku, barcode, category_id, uom, cost_price, selling_price, reorder_level, reorder_qty, lead_time_days, def_wh, def_loc
        ('Steel Rods (12mm TMT)', 'RAW-STL-001', '890123456701', 1, 'kg', 45.0, 65.0, 25.0, 100.0, 4, 1, 1),
        ('Industrial Bearings (6205)', 'ENG-BRG-002', '890123456702', 1, 'Units', 120.0, 180.0, 15.0, 50.0, 5, 1, 2),
        ('Copper Wire Spool (100m)', 'RAW-CPR-003', '890123456703', 1, 'Meters', 80.0, 120.0, 50.0, 200.0, 3, 1, 1),
        ('Ergonomic Office Chair', 'FUR-CHR-004', '890123456704', 2, 'Units', 2500.0, 4200.0, 8.0, 20.0, 7, 2, 6),
        ('Dell Latitude 5420 Laptop', 'ELE-LAP-005', '890123456705', 3, 'Units', 48000.0, 62000.0, 4.0, 10.0, 10, 1, 2),
        ('Laser Jet Pro Printer', 'ELE-PRN-006', '890123456706', 3, 'Units', 14000.0, 19500.0, 3.0, 8.0, 6, 2, 6),
        ('Industrial Safety Helmet', 'SAF-HLM-007', '890123456707', 5, 'Units', 350.0, 550.0, 20.0, 60.0, 3, 2, 7),
        ('Heavy Duty Corrugated Box', 'PKG-BOX-008', '890123456708', 4, 'Packs', 15.0, 30.0, 100.0, 500.0, 2, 1, 3),
        ('High-Vis Reflective Vest', 'SAF-VST-009', '890123456709', 5, 'Units', 180.0, 320.0, 15.0, 50.0, 4, 2, 7),
        ('Wireless 2D Barcode Scanner', 'ELE-SCN-010', '890123456710', 3, 'Units', 3200.0, 4800.0, 5.0, 15.0, 5, 1, 2)
    ]
    cursor.executemany("""
        INSERT INTO products (
            name, sku, barcode, category_id, uom, cost_price, selling_price,
            reorder_level, reorder_qty, lead_time_days, default_warehouse_id, default_location_id, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Active')
    """, products_data)

    # 6. Initial Stock Setup & Ledger Entries
    initial_stocks = [
        # (product_id, wh_id, loc_id, on_hand, reserved)
        (1, 1, 1, 150.0, 20.0), # Steel Rods @ Rack A
        (1, 2, 5, 60.0, 0.0),   # Steel Rods @ Prod Floor
        (2, 1, 2, 45.0, 5.0),   # Bearings @ Rack B
        (3, 1, 1, 220.0, 0.0),  # Copper Wire @ Rack A
        (4, 2, 6, 18.0, 2.0),   # Chairs @ FG Staging
        (5, 1, 2, 8.0, 1.0),    # Laptops @ Rack B
        (6, 2, 6, 2.0, 0.0),    # Printers @ FG (Low Stock!)
        (7, 2, 7, 75.0, 10.0),  # Helmets @ Safety Rack
        (8, 1, 3, 400.0, 50.0), # Packaging Boxes @ Inbound
        (9, 2, 7, 12.0, 0.0),   # Safety Vests @ Safety Rack (Low Stock!)
        (10, 1, 2, 14.0, 0.0)   # Scanners @ Rack B
    ]
    for s in initial_stocks:
        cursor.execute("""
            INSERT INTO stock (product_id, warehouse_id, location_id, on_hand, reserved, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (s[0], s[1], s[2], s[3], s[4], d_minus(15)))

        # Add initial ledger record
        cursor.execute("SELECT name, sku FROM products WHERE id = ?", (s[0],))
        p_info = cursor.fetchone()
        cursor.execute("SELECT name FROM warehouses WHERE id = ?", (s[1],))
        wh_name = cursor.fetchone()['name']
        cursor.execute("SELECT name FROM locations WHERE id = ?", (s[2],))
        loc_name = cursor.fetchone()['name']

        cursor.execute("""
            INSERT INTO stock_ledger (
                timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                warehouse_id, warehouse_name, location_id, location_name,
                qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
            ) VALUES (?, ?, 'Initial Stock', ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, 1, 'System Admin', 'INIT-STOCK', 'Opening Stock Balance')
        """, (d_minus(15), f"TX-INIT-{uuid.uuid4().hex[:6].upper()}", s[0], p_info['name'], p_info['sku'],
              s[1], wh_name, s[2], loc_name, s[3], s[3]))

    # 7. Receipts (10 receipts)
    receipts_seed = [
        ('WH/IN/0001', 'Tata Steel Ltd', 1, 1, d_minus(12), 2, 'Done', 'Bulk steel shipment batch 1', d_minus(12)),
        ('WH/IN/0002', 'SKF Bearings India', 1, 2, d_minus(10), 2, 'Done', 'Precision bearings delivery', d_minus(10)),
        ('WH/IN/0003', 'Havells Electricals', 1, 1, d_minus(8), 2, 'Done', 'Copper coils and spools', d_minus(8)),
        ('WH/IN/0004', 'Dell Commercial Partner', 1, 2, d_minus(6), 2, 'Done', 'Laptops for IT depot', d_minus(6)),
        ('WH/IN/0005', 'Karam Safety Solutions', 2, 7, d_minus(4), 3, 'Done', 'Personal protective equipment', d_minus(4)),
        ('WH/IN/0006', 'ABC Metals Corp', 1, 1, d_minus(2), 2, 'Ready', 'Scheduled incoming rods', None),
        ('WH/IN/0007', 'Century Packaging', 1, 3, d_minus(1), 3, 'Waiting', 'Corrugated packaging batch', None),
        ('WH/IN/0008', 'HP Enterprise Sales', 2, 6, (now + timedelta(days=2)).strftime('%Y-%m-%d'), 2, 'Draft', 'Next week printer supply', None),
        ('WH/IN/0009', 'Apex Wire Works', 1, 1, (now + timedelta(days=3)).strftime('%Y-%m-%d'), 2, 'Draft', 'Copper wire restock', None),
        ('WH/IN/0010', 'Honeywell Industrial', 2, 7, (now + timedelta(days=5)).strftime('%Y-%m-%d'), 3, 'Draft', 'Safety gear restocking', None)
    ]
    for r in receipts_seed:
        cursor.execute("""
            INSERT INTO receipts (reference_no, supplier_name, warehouse_id, destination_location_id, scheduled_date, responsible_user_id, status, notes, validated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, r)

    # Receipt Items
    receipt_items_seed = [
        (1, 1, 100.0, 100.0, 45.0),
        (2, 2, 40.0, 40.0, 120.0),
        (3, 3, 150.0, 150.0, 80.0),
        (4, 5, 10.0, 10.0, 48000.0),
        (5, 7, 50.0, 50.0, 350.0),
        (5, 9, 20.0, 20.0, 180.0),
        (6, 1, 100.0, 0.0, 45.0),
        (7, 8, 300.0, 0.0, 15.0),
        (8, 6, 10.0, 0.0, 14000.0),
        (9, 3, 100.0, 0.0, 80.0),
        (10, 7, 40.0, 0.0, 350.0)
    ]
    cursor.executemany("""
        INSERT INTO receipt_items (receipt_id, product_id, expected_qty, received_qty, unit_cost)
        VALUES (?, ?, ?, ?, ?)
    """, receipt_items_seed)

    # 8. Deliveries (10 deliveries)
    deliveries_seed = [
        ('WH/OUT/0001', 'LPU Mechanical Labs', 1, 1, d_minus(9), 2, 'Done', 'Lab structural project dispatch', d_minus(9)),
        ('WH/OUT/0002', 'TechCorp Jalandhar', 1, 2, d_minus(7), 2, 'Done', 'Client workstation upgrade', d_minus(7)),
        ('WH/OUT/0003', 'Punjab Infra Projects', 1, 1, d_minus(5), 2, 'Done', 'Construction reinforcement bars', d_minus(5)),
        ('WH/OUT/0004', 'Apex Robotics Club', 1, 2, d_minus(3), 3, 'Done', 'Component supplies for hackathon', d_minus(3)),
        ('WH/OUT/0005', 'Campus Administration', 2, 6, d_minus(1), 2, 'Packed', 'Executive office setup chairs', None),
        ('WH/OUT/0006', 'Smart City Corp', 1, 1, (now + timedelta(days=1)).strftime('%Y-%m-%d'), 2, 'Picked', 'Underground wiring order', None),
        ('WH/OUT/0007', 'Engineering Workshop', 2, 7, (now + timedelta(days=2)).strftime('%Y-%m-%d'), 3, 'Ready', 'Safety gear for student batch', None),
        ('WH/OUT/0008', 'Logistics Hub North', 1, 3, (now + timedelta(days=3)).strftime('%Y-%m-%d'), 2, 'Waiting', 'Cartons dispatch', None),
        ('WH/OUT/0009', 'Faculty Staff Office', 2, 6, (now + timedelta(days=4)).strftime('%Y-%m-%d'), 2, 'Draft', 'Printer requirements', None),
        ('WH/OUT/0010', 'Precision Tools Ltd', 1, 2, (now + timedelta(days=5)).strftime('%Y-%m-%d'), 2, 'Draft', 'Bearings order', None)
    ]
    for d in deliveries_seed:
        cursor.execute("""
            INSERT INTO deliveries (reference_no, customer_name, source_warehouse_id, source_location_id, scheduled_date, responsible_user_id, status, notes, validated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, d)

    # Delivery items
    delivery_items_seed = [
        (1, 1, 20.0, 0.0, 20.0, 20.0, 65.0),
        (2, 5, 2.0, 0.0, 2.0, 2.0, 62000.0),
        (3, 1, 30.0, 0.0, 30.0, 30.0, 65.0),
        (4, 2, 10.0, 0.0, 10.0, 10.0, 180.0),
        (5, 4, 2.0, 2.0, 2.0, 2.0, 4200.0),
        (6, 1, 20.0, 20.0, 20.0, 0.0, 65.0),
        (7, 7, 10.0, 10.0, 0.0, 0.0, 550.0),
        (8, 8, 50.0, 50.0, 0.0, 0.0, 30.0),
        (9, 6, 1.0, 0.0, 0.0, 0.0, 19500.0),
        (10, 2, 5.0, 5.0, 0.0, 0.0, 180.0)
    ]
    cursor.executemany("""
        INSERT INTO delivery_items (delivery_id, product_id, requested_qty, reserved_qty, picked_qty, packed_qty, unit_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, delivery_items_seed)

    # 9. Transfers (5 transfers)
    transfers_seed = [
        ('WH/INT/0001', 1, 1, 2, 5, d_minus(6), 2, 'Done', 'Shift steel rods to production plant', d_minus(6)),
        ('WH/INT/0002', 1, 2, 2, 6, d_minus(4), 3, 'Done', 'Printers transferred to FG staging', d_minus(4)),
        ('WH/INT/0003', 1, 1, 1, 2, d_minus(2), 2, 'Ready', 'Rebalance Rack A to Rack B', None),
        ('WH/INT/0004', 2, 6, 1, 3, (now + timedelta(days=1)).strftime('%Y-%m-%d'), 2, 'Waiting', 'Chairs moved to Main Warehouse', None),
        ('WH/INT/0005', 2, 7, 1, 2, (now + timedelta(days=3)).strftime('%Y-%m-%d'), 3, 'Draft', 'Safety kits sent to IT depot', None)
    ]
    for t in transfers_seed:
        cursor.execute("""
            INSERT INTO transfers (reference_no, source_warehouse_id, source_location_id, dest_warehouse_id, dest_location_id, scheduled_date, responsible_user_id, status, notes, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, t)

    transfer_items_seed = [
        (1, 1, 40.0),
        (2, 6, 2.0),
        (3, 1, 15.0),
        (4, 4, 5.0),
        (5, 7, 10.0)
    ]
    cursor.executemany("""
        INSERT INTO transfer_items (transfer_id, product_id, quantity)
        VALUES (?, ?, ?)
    """, transfer_items_seed)

    # 10. Adjustments (5 adjustments)
    adjustments_seed = [
        ('ADJ-20260915-01', 1, 1, 1, 153.0, 150.0, -3.0, 'Damaged', 2, 'Rods bent during crane unloading', d_minus(11)),
        ('ADJ-20260918-02', 1, 2, 2, 44.0, 45.0, 1.0, 'Counting Error', 3, 'Misplaced bearing box recovered', d_minus(8)),
        ('ADJ-20260920-03', 2, 7, 9, 15.0, 12.0, -3.0, 'Damaged', 3, 'Vests torn packaging', d_minus(5)),
        ('ADJ-20260922-04', 1, 3, 8, 410.0, 400.0, -10.0, 'Lost', 2, 'Water dampness carton write-off', d_minus(3)),
        ('ADJ-20260924-05', 2, 6, 4, 17.0, 18.0, 1.0, 'Data Correction', 2, 'Physical recount after assembly', d_minus(1))
    ]
    cursor.executemany("""
        INSERT INTO adjustments (reference_no, warehouse_id, location_id, product_id, system_qty, counted_qty, diff_qty, reason, user_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, adjustments_seed)

    # 11. Add historical transactions to Stock Ledger for realistic analytics
    historical_ledger = [
        (d_minus(12), 'TX-REC-TATA01', 'Receipt', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 100.0, 0.0, 100.0, 2, 'Rahul Sharma', 'WH/IN/0001', 'Tata Steel Ltd receipt'),
        (d_minus(11), 'TX-ADJ-STLDMG', 'Adjustment', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 0.0, 3.0, 97.0, 2, 'Rahul Sharma', 'ADJ-20260915-01', 'Damaged: Crane unloading'),
        (d_minus(10), 'TX-REC-SKF01', 'Receipt', 2, 'Industrial Bearings (6205)', 'ENG-BRG-002', 1, 'Main Central Warehouse', 2, 'Rack B - Components & Parts', 40.0, 0.0, 40.0, 2, 'Rahul Sharma', 'WH/IN/0002', 'SKF Bearings delivery'),
        (d_minus(9), 'TX-DEL-LPUMEC', 'Delivery', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 0.0, 20.0, 77.0, 2, 'Rahul Sharma', 'WH/OUT/0001', 'Dispatched to LPU Mechanical Labs'),
        (d_minus(8), 'TX-REC-HVL01', 'Receipt', 3, 'Copper Wire Spool (100m)', 'RAW-CPR-003', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 150.0, 0.0, 150.0, 2, 'Rahul Sharma', 'WH/IN/0003', 'Havells Electricals shipment'),
        (d_minus(7), 'TX-DEL-TECHCP', 'Delivery', 5, 'Dell Latitude 5420 Laptop', 'ELE-LAP-005', 1, 'Main Central Warehouse', 2, 'Rack B - Components & Parts', 0.0, 2.0, 8.0, 2, 'Rahul Sharma', 'WH/OUT/0002', 'Dispatched to TechCorp Jalandhar'),
        (d_minus(6), 'TX-TRF-STL01', 'Internal Transfer', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 0.0, 40.0, 37.0, 2, 'Rahul Sharma', 'WH/INT/0001', 'Transferred to LPU Production Plant'),
        (d_minus(6), 'TX-TRF-STL02', 'Internal Transfer', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 2, 'LPU Production Plant', 5, 'Production Assembly Floor', 40.0, 0.0, 60.0, 2, 'Rahul Sharma', 'WH/INT/0001', 'Received from Main Central Warehouse'),
        (d_minus(5), 'TX-DEL-PNJINF', 'Delivery', 1, 'Steel Rods (12mm TMT)', 'RAW-STL-001', 1, 'Main Central Warehouse', 1, 'Rack A - Heavy Metals', 0.0, 30.0, 150.0, 2, 'Rahul Sharma', 'WH/OUT/0003', 'Dispatched to Punjab Infra Projects'),
        (d_minus(4), 'TX-REC-DELL01', 'Receipt', 5, 'Dell Latitude 5420 Laptop', 'ELE-LAP-005', 1, 'Main Central Warehouse', 2, 'Rack B - Components & Parts', 10.0, 0.0, 10.0, 2, 'Rahul Sharma', 'WH/IN/0004', 'Dell Commercial Partner'),
        (d_minus(3), 'TX-DEL-ROBOT', 'Delivery', 2, 'Industrial Bearings (6205)', 'ENG-BRG-002', 1, 'Main Central Warehouse', 2, 'Rack B - Components & Parts', 0.0, 10.0, 45.0, 3, 'Arjun Singh', 'WH/OUT/0004', 'Dispatched to Apex Robotics Club'),
        (d_minus(1), 'TX-ADJ-CHRA01', 'Adjustment', 4, 'Ergonomic Office Chair', 'FUR-CHR-004', 2, 'LPU Production Plant', 6, 'Finished Goods Staging', 1.0, 0.0, 18.0, 2, 'Rahul Sharma', 'ADJ-20260924-05', 'Data Correction: Physical recount')
    ]
    cursor.executemany("""
        INSERT INTO stock_ledger (
            timestamp, transaction_id, transaction_type, product_id, product_name, sku,
            warehouse_id, warehouse_name, location_id, location_name,
            qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, historical_ledger)

    # 12. Audit Logs
    audit_seed = [
        (d_minus(15), 1, 'Kavish Admin', 'Admin', 'SYSTEM_INITIALIZATION', 'System', 'STOCKSENSE-01', None, '{"status": "initialized", "version": "1.0.0"}', '127.0.0.1', 'Desktop Admin Console'),
        (d_minus(12), 2, 'Rahul Sharma', 'Inventory Manager', 'VALIDATE_RECEIPT', 'Receipt', 'WH/IN/0001', '{"status": "Ready"}', '{"status": "Done", "received_qty": 100}', '192.168.1.102', 'Chrome Windows'),
        (d_minus(9), 2, 'Rahul Sharma', 'Inventory Manager', 'VALIDATE_DELIVERY', 'Delivery', 'WH/OUT/0001', '{"status": "Packed"}', '{"status": "Done", "shipped_qty": 20}', '192.168.1.102', 'Chrome Windows'),
        (d_minus(6), 2, 'Rahul Sharma', 'Inventory Manager', 'COMPLETE_TRANSFER', 'Transfer', 'WH/INT/0001', '{"status": "Ready"}', '{"status": "Done", "qty": 40}', '192.168.1.105', 'Firefox Windows'),
        (d_minus(5), 3, 'Arjun Singh', 'Warehouse Staff', 'APPLY_ADJUSTMENT', 'Adjustment', 'ADJ-20260920-03', '{"system": 15}', '{"counted": 12, "reason": "Damaged"}', '192.168.1.110', 'Tablet Zebra Scanner'),
        (d_minus(3), 3, 'Arjun Singh', 'Warehouse Staff', 'VALIDATE_DELIVERY', 'Delivery', 'WH/OUT/0004', '{"status": "Packed"}', '{"status": "Done", "shipped_qty": 10}', '192.168.1.110', 'Tablet Zebra Scanner'),
        (d_minus(1), 2, 'Rahul Sharma', 'Inventory Manager', 'APPLY_ADJUSTMENT', 'Adjustment', 'ADJ-20260924-05', '{"system": 17}', '{"counted": 18, "reason": "Data Correction"}', '192.168.1.102', 'Chrome Windows')
    ]
    cursor.executemany("""
        INSERT INTO audit_logs (timestamp, user_id, user_name, role, action, object_type, object_id, old_values, new_values, ip_address, device)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, audit_seed)

    # 13. Notifications
    notifs_seed = [
        (d_minus(2), 'stock_alert', 'LOW STOCK ALERT: Laser Jet Pro Printer', 'Laser Jet Pro Printer (SKU: ELE-PRN-006) stock reached 2 units (Reorder level: 3 units). Recommended reorder: 8 units.', 'warning', 0, '/products?id=6'),
        (d_minus(1), 'stock_alert', 'LOW STOCK ALERT: High-Vis Reflective Vest', 'High-Vis Reflective Vest (SKU: SAF-VST-009) stock reached 12 units (Reorder level: 15 units).', 'warning', 0, '/products?id=9'),
        (d_minus(1), 'receipt', 'Incoming Shipment Ready: WH/IN/0006', 'ABC Metals Corp shipment of 100 Steel Rods is ready for receiving at Inbound Receiving Bay.', 'info', 0, '/receipts?id=6'),
        (d_minus(0, 3), 'delivery', 'Delivery Ready for Packing: WH/OUT/0006', 'Smart City Corp order has 20 units of Copper Wire ready to pack at Main Warehouse.', 'info', 0, '/deliveries?id=6')
    ]
    cursor.executemany("""
        INSERT INTO notifications (timestamp, type, title, message, severity, is_read, link)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, notifs_seed)

    conn.commit()
    conn.close()
    print("StockSense seed data populated successfully!")

if __name__ == '__main__':
    seed_database()
