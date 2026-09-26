import sqlite3
import json
import uuid
from datetime import datetime, timedelta
from backend.database import get_db_connection

def log_audit(conn, user_id, user_name, role, action, object_type, object_id, old_values=None, new_values=None, ip='127.0.0.1', ip_address=None, device='Web Client', **kwargs):
    """Records an audit log entry in the database."""
    cursor = conn.cursor()
    actual_ip = ip_address or ip or '127.0.0.1'
    cursor.execute("""
        INSERT INTO audit_logs (timestamp, user_id, user_name, role, action, object_type, object_id, old_values, new_values, ip_address, device)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        user_id,
        user_name,
        role,
        action,
        object_type,
        str(object_id) if object_id else None,
        json.dumps(old_values) if old_values else None,
        json.dumps(new_values) if new_values else None,
        actual_ip,
        device
    ))

def create_notification(conn, notif_type, title, message, severity='info', link=None):
    """Creates a persistent notification."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO notifications (timestamp, type, title, message, severity, is_read, link)
        VALUES (?, ?, ?, ?, ?, 0, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        notif_type,
        title,
        message,
        severity,
        link
    ))

def get_or_create_stock(conn, product_id, warehouse_id, location_id):
    """Ensures a stock row exists for the given product and location, returning the row."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM stock WHERE product_id = ? AND location_id = ?
    """, (product_id, location_id))
    row = cursor.fetchone()
    if row:
        return dict(row)
    
    cursor.execute("""
        INSERT INTO stock (product_id, warehouse_id, location_id, on_hand, reserved, updated_at)
        VALUES (?, ?, ?, 0.0, 0.0, ?)
    """, (product_id, warehouse_id, location_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    cursor.execute("SELECT * FROM stock WHERE id = last_insert_rowid()")
    return dict(cursor.fetchone())

def check_allow_negative_stock(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = 'allow_negative_stock'")
    row = cursor.fetchone()
    return row and row['value'].lower() == 'true'

# ==================== RECEIPTS (INCOMING) ====================

def validate_receipt(receipt_id, user_id=1, user_name='Inventory Manager', role='Inventory Manager'):
    """
    Validates a receipt:
    1. Checks receipt exists and is in ready/draft/waiting state.
    2. Atomically increments stock for each item at destination location.
    3. Writes immutable stock ledger records (+qty_in).
    4. Marks receipt as 'Done' with validated_at timestamp.
    5. Writes audit log & notification.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT r.*, w.name as warehouse_name, l.name as location_name
            FROM receipts r
            JOIN warehouses w ON r.warehouse_id = w.id
            JOIN locations l ON r.destination_location_id = l.id
            WHERE r.id = ?
        """, (receipt_id,))
        receipt = cursor.fetchone()

        if not receipt:
            raise ValueError(f"Receipt ID {receipt_id} not found.")
        
        if receipt['status'] == 'Done':
            raise ValueError(f"Receipt {receipt['reference_no']} is already validated and Done.")
        if receipt['status'] == 'Cancelled':
            raise ValueError(f"Receipt {receipt['reference_no']} has been cancelled.")

        # Fetch receipt items
        cursor.execute("""
            SELECT ri.*, p.name as product_name, p.sku
            FROM receipt_items ri
            JOIN products p ON ri.product_id = p.id
            WHERE ri.receipt_id = ?
        """, (receipt_id,))
        items = cursor.fetchall()

        if not items:
            raise ValueError("Cannot validate receipt with no product items.")

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for item in items:
            p_id = item['product_id']
            qty = item['expected_qty'] if item['received_qty'] == 0 else item['received_qty']
            if qty <= 0:
                continue

            # Update receipt item received_qty if not set
            cursor.execute("""
                UPDATE receipt_items SET received_qty = ? WHERE id = ?
            """, (qty, item['id']))

            # Ensure stock row exists
            stock_row = get_or_create_stock(conn, p_id, receipt['warehouse_id'], receipt['destination_location_id'])
            new_on_hand = stock_row['on_hand'] + qty

            cursor.execute("""
                UPDATE stock 
                SET on_hand = ?, updated_at = ?
                WHERE id = ?
            """, (new_on_hand, now_str, stock_row['id']))

            # Get overall product on hand across all locations
            cursor.execute("SELECT SUM(on_hand) as total_on_hand FROM stock WHERE product_id = ?", (p_id,))
            total_stock_row = cursor.fetchone()
            total_balance = total_stock_row['total_on_hand'] or new_on_hand

            # Write to immutable stock ledger
            tx_id = f"TX-REC-{uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO stock_ledger (
                    timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                    warehouse_id, warehouse_name, location_id, location_name,
                    qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
                ) VALUES (?, ?, 'Receipt', ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?)
            """, (
                now_str, tx_id, p_id, item['product_name'], item['sku'],
                receipt['warehouse_id'], receipt['warehouse_name'],
                receipt['destination_location_id'], receipt['location_name'],
                qty, new_on_hand, user_id, user_name, receipt['reference_no'], f"Supplier receipt from {receipt['supplier_name']}"
            ))

        # Update receipt status to Done
        cursor.execute("""
            UPDATE receipts 
            SET status = 'Done', validated_at = ?
            WHERE id = ?
        """, (now_str, receipt_id))

        # Log audit
        log_audit(conn, user_id, user_name, role, 'VALIDATE_RECEIPT', 'Receipt', receipt['reference_no'], 
                  old_values={'status': receipt['status']}, 
                  new_values={'status': 'Done', 'validated_at': now_str})

        # Notification
        create_notification(conn, 'receipt', f"Receipt {receipt['reference_no']} Received", 
                            f"Successfully received {len(items)} items from {receipt['supplier_name']} into {receipt['location_name']}.", 'success', 
                            link=f"/receipts?id={receipt_id}")

        conn.commit()
        return {'success': True, 'message': f"Receipt {receipt['reference_no']} successfully validated and stock updated."}

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ==================== DELIVERIES (OUTGOING) ====================

def check_delivery_stock_availability(delivery_id):
    """
    Checks stock availability for a delivery order.
    Returns: { available: bool, items: [ { product_id, product_name, sku, requested, on_hand, reserved, available, shortage } ] }
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT d.*, w.name as warehouse_name, l.name as location_name
            FROM deliveries d
            JOIN warehouses w ON d.source_warehouse_id = w.id
            JOIN locations l ON d.source_location_id = l.id
            WHERE d.id = ?
        """, (delivery_id,))
        delivery = cursor.fetchone()
        if not delivery:
            raise ValueError(f"Delivery ID {delivery_id} not found.")

        cursor.execute("""
            SELECT di.*, p.name as product_name, p.sku
            FROM delivery_items di
            JOIN products p ON di.product_id = p.id
            WHERE di.delivery_id = ?
        """, (delivery_id,))
        items = cursor.fetchall()

        all_available = True
        item_reports = []

        for item in items:
            p_id = item['product_id']
            cursor.execute("""
                SELECT on_hand, reserved 
                FROM stock 
                WHERE product_id = ? AND location_id = ?
            """, (p_id, delivery['source_location_id']))
            stock_row = cursor.fetchone()
            on_hand = stock_row['on_hand'] if stock_row else 0.0
            reserved = stock_row['reserved'] if stock_row else 0.0
            
            # If item is already reserved by this delivery, available should consider that
            current_item_reserved = item['reserved_qty'] or 0.0
            effective_reserved = max(0.0, reserved - current_item_reserved)
            available_qty = max(0.0, on_hand - effective_reserved)
            shortage = max(0.0, item['requested_qty'] - (available_qty if current_item_reserved == 0 else on_hand))

            is_item_available = (available_qty >= item['requested_qty']) or (current_item_reserved >= item['requested_qty'])
            if not is_item_available:
                all_available = False

            item_reports.append({
                'product_id': p_id,
                'product_name': item['product_name'],
                'sku': item['sku'],
                'requested_qty': item['requested_qty'],
                'on_hand': on_hand,
                'reserved': reserved,
                'available': available_qty,
                'shortage': shortage,
                'is_available': is_item_available,
                'picked_qty': item['picked_qty'],
                'packed_qty': item['packed_qty']
            })

        return {
            'all_available': all_available,
            'delivery_reference': delivery['reference_no'],
            'warehouse': delivery['warehouse_name'],
            'location': delivery['location_name'],
            'items': item_reports
        }
    finally:
        conn.close()

def reserve_delivery_stock(delivery_id, user_id=1, user_name='Inventory Manager', role='Inventory Manager'):
    """Reserves the required stock for a delivery order if available."""
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        avail_check = check_delivery_stock_availability(delivery_id)
        if not avail_check['all_available']:
            allow_neg = check_allow_negative_stock(conn)
            if not allow_neg:
                shortages = [f"{i['product_name']} (Shortage: {i['shortage']})" for i in avail_check['items'] if not i['is_available']]
                raise ValueError(f"Insufficient stock for reservation: {', '.join(shortages)}")

        cursor.execute("SELECT source_warehouse_id, source_location_id, reference_no, status FROM deliveries WHERE id = ?", (delivery_id,))
        delivery = cursor.fetchone()

        cursor.execute("SELECT * FROM delivery_items WHERE delivery_id = ?", (delivery_id,))
        items = cursor.fetchall()

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        for item in items:
            p_id = item['product_id']
            qty = item['requested_qty']
            already_res = item['reserved_qty'] or 0.0
            diff_res = qty - already_res

            if diff_res > 0:
                stock_row = get_or_create_stock(conn, p_id, delivery['source_warehouse_id'], delivery['source_location_id'])
                cursor.execute("""
                    UPDATE stock SET reserved = reserved + ?, updated_at = ? WHERE id = ?
                """, (diff_res, now_str, stock_row['id']))

                cursor.execute("""
                    UPDATE delivery_items SET reserved_qty = ? WHERE id = ?
                """, (qty, item['id']))

        cursor.execute("UPDATE deliveries SET status = 'Ready' WHERE id = ?", (delivery_id,))
        log_audit(conn, user_id, user_name, role, 'RESERVE_DELIVERY_STOCK', 'Delivery', delivery['reference_no'],
                  old_values={'status': delivery['status']}, new_values={'status': 'Ready'})

        conn.commit()
        return {'success': True, 'message': f"Stock reserved successfully for Delivery {delivery['reference_no']}."}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def validate_delivery(delivery_id, user_id=1, user_name='Inventory Manager', role='Inventory Manager'):
    """
    Validates a delivery:
    1. Checks stock availability.
    2. Atomically decrements on_hand stock and releases reserved stock.
    3. Writes immutable stock ledger records (-qty_out).
    4. Marks delivery as 'Done'.
    5. Writes audit log & notification (with low-stock checks).
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT d.*, w.name as warehouse_name, l.name as location_name
            FROM deliveries d
            JOIN warehouses w ON d.source_warehouse_id = w.id
            JOIN locations l ON d.source_location_id = l.id
            WHERE d.id = ?
        """, (delivery_id,))
        delivery = cursor.fetchone()

        if not delivery:
            raise ValueError(f"Delivery ID {delivery_id} not found.")
        if delivery['status'] == 'Done':
            raise ValueError(f"Delivery {delivery['reference_no']} is already delivered and Done.")
        if delivery['status'] == 'Cancelled':
            raise ValueError(f"Delivery {delivery['reference_no']} is cancelled.")

        cursor.execute("""
            SELECT di.*, p.name as product_name, p.sku, p.reorder_level
            FROM delivery_items di
            JOIN products p ON di.product_id = p.id
            WHERE di.delivery_id = ?
        """, (delivery_id,))
        items = cursor.fetchall()

        if not items:
            raise ValueError("Cannot deliver an empty order with no items.")

        allow_neg = check_allow_negative_stock(conn)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check stock for all items
        for item in items:
            p_id = item['product_id']
            qty = item['requested_qty']
            stock_row = get_or_create_stock(conn, p_id, delivery['source_warehouse_id'], delivery['source_location_id'])
            
            if stock_row['on_hand'] < qty and not allow_neg:
                raise ValueError(f"Insufficient stock for {item['product_name']} at {delivery['location_name']}. Required: {qty}, On Hand: {stock_row['on_hand']}, Shortage: {qty - stock_row['on_hand']}")

        # Deduct stock and write ledger
        for item in items:
            p_id = item['product_id']
            qty = item['requested_qty']
            res_qty = item['reserved_qty'] or 0.0

            stock_row = get_or_create_stock(conn, p_id, delivery['source_warehouse_id'], delivery['source_location_id'])
            new_on_hand = max(0.0, stock_row['on_hand'] - qty) if not allow_neg else stock_row['on_hand'] - qty
            new_reserved = max(0.0, stock_row['reserved'] - res_qty)

            cursor.execute("""
                UPDATE stock 
                SET on_hand = ?, reserved = ?, updated_at = ?
                WHERE id = ?
            """, (new_on_hand, new_reserved, now_str, stock_row['id']))

            # Mark item picked and packed as complete
            cursor.execute("""
                UPDATE delivery_items 
                SET picked_qty = ?, packed_qty = ?, reserved_qty = 0.0
                WHERE id = ?
            """, (qty, qty, item['id']))

            # Write to stock ledger
            tx_id = f"TX-DEL-{uuid.uuid4().hex[:8].upper()}"
            cursor.execute("""
                INSERT INTO stock_ledger (
                    timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                    warehouse_id, warehouse_name, location_id, location_name,
                    qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
                ) VALUES (?, ?, 'Delivery', ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, ?)
            """, (
                now_str, tx_id, p_id, item['product_name'], item['sku'],
                delivery['source_warehouse_id'], delivery['warehouse_name'],
                delivery['source_location_id'], delivery['location_name'],
                qty, new_on_hand, user_id, user_name, delivery['reference_no'], f"Customer delivery to {delivery['customer_name']}"
            ))

            # Low stock check
            cursor.execute("SELECT SUM(on_hand) as total_on_hand FROM stock WHERE product_id = ?", (p_id,))
            tot_row = cursor.fetchone()
            current_tot = tot_row['total_on_hand'] or 0.0
            if current_tot <= item['reorder_level']:
                severity = 'danger' if current_tot == 0 else 'warning'
                status_text = 'OUT OF STOCK' if current_tot == 0 else 'LOW STOCK'
                create_notification(conn, 'stock_alert', f"{status_text}: {item['product_name']}",
                                    f"{item['product_name']} (SKU: {item['sku']}) stock reached {current_tot} units (Reorder level: {item['reorder_level']}).",
                                    severity=severity, link=f"/products?id={p_id}")

        cursor.execute("""
            UPDATE deliveries 
            SET status = 'Done', validated_at = ?
            WHERE id = ?
        """, (now_str, delivery_id))

        log_audit(conn, user_id, user_name, role, 'VALIDATE_DELIVERY', 'Delivery', delivery['reference_no'],
                  old_values={'status': delivery['status']},
                  new_values={'status': 'Done', 'validated_at': now_str})

        create_notification(conn, 'delivery', f"Delivery {delivery['reference_no']} Dispatched",
                            f"Successfully shipped {len(items)} items to {delivery['customer_name']}.", 'success',
                            link=f"/deliveries?id={delivery_id}")

        conn.commit()
        return {'success': True, 'message': f"Delivery {delivery['reference_no']} successfully validated and dispatched."}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ==================== INTERNAL TRANSFERS ====================

def validate_transfer(transfer_id, user_id=1, user_name='Inventory Manager', role='Inventory Manager'):
    """
    Executes an internal transfer:
    1. Checks stock availability at source location.
    2. Decrements source location stock.
    3. Increments destination location stock.
    4. Total company stock remains unchanged!
    5. Writes 2 ledger entries (one for source reduction, one for dest addition) or a transfer ledger entry.
    6. Marks transfer as 'Done'.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.*, 
                   sw.name as src_warehouse_name, sl.name as src_location_name,
                   dw.name as dst_warehouse_name, dl.name as dst_location_name
            FROM transfers t
            JOIN warehouses sw ON t.source_warehouse_id = sw.id
            JOIN locations sl ON t.source_location_id = sl.id
            JOIN warehouses dw ON t.dest_warehouse_id = dw.id
            JOIN locations dl ON t.dest_location_id = dl.id
            WHERE t.id = ?
        """, (transfer_id,))
        transfer = cursor.fetchone()

        if not transfer:
            raise ValueError(f"Transfer ID {transfer_id} not found.")
        if transfer['status'] == 'Done':
            raise ValueError(f"Transfer {transfer['reference_no']} is already completed.")
        if transfer['source_location_id'] == transfer['dest_location_id']:
            raise ValueError("Source location and destination location cannot be the same.")

        cursor.execute("""
            SELECT ti.*, p.name as product_name, p.sku
            FROM transfer_items ti
            JOIN products p ON ti.product_id = p.id
            WHERE ti.transfer_id = ?
        """, (transfer_id,))
        items = cursor.fetchall()

        if not items:
            raise ValueError("Transfer has no items.")

        allow_neg = check_allow_negative_stock(conn)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Check source stocks
        for item in items:
            p_id = item['product_id']
            qty = item['quantity']
            src_stock = get_or_create_stock(conn, p_id, transfer['source_warehouse_id'], transfer['source_location_id'])
            avail = max(0.0, src_stock['on_hand'] - src_stock['reserved'])
            if avail < qty and not allow_neg:
                raise ValueError(f"Cannot transfer {qty} units of {item['product_name']}. Only {avail} available at {transfer['src_location_name']} (On hand: {src_stock['on_hand']}, Reserved: {src_stock['reserved']}).")

        # Execute transfer
        for item in items:
            p_id = item['product_id']
            qty = item['quantity']

            # Source location decrement
            src_stock = get_or_create_stock(conn, p_id, transfer['source_warehouse_id'], transfer['source_location_id'])
            new_src_on_hand = max(0.0, src_stock['on_hand'] - qty) if not allow_neg else src_stock['on_hand'] - qty
            cursor.execute("""
                UPDATE stock SET on_hand = ?, updated_at = ? WHERE id = ?
            """, (new_src_on_hand, now_str, src_stock['id']))

            # Destination location increment
            dst_stock = get_or_create_stock(conn, p_id, transfer['dest_warehouse_id'], transfer['dest_location_id'])
            new_dst_on_hand = dst_stock['on_hand'] + qty
            cursor.execute("""
                UPDATE stock SET on_hand = ?, updated_at = ? WHERE id = ?
            """, (new_dst_on_hand, now_str, dst_stock['id']))

            # Ledger entry for Source (Outflow)
            tx_id_src = f"TX-TRF-SRC-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT INTO stock_ledger (
                    timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                    warehouse_id, warehouse_name, location_id, location_name,
                    qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
                ) VALUES (?, ?, 'Internal Transfer', ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?, ?)
            """, (
                now_str, tx_id_src, p_id, item['product_name'], item['sku'],
                transfer['source_warehouse_id'], transfer['src_warehouse_name'],
                transfer['source_location_id'], transfer['src_location_name'],
                qty, new_src_on_hand, user_id, user_name, transfer['reference_no'],
                f"Transferred to {transfer['dst_warehouse_name']} ({transfer['dst_location_name']})"
            ))

            # Ledger entry for Destination (Inflow)
            tx_id_dst = f"TX-TRF-DST-{uuid.uuid4().hex[:6].upper()}"
            cursor.execute("""
                INSERT INTO stock_ledger (
                    timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                    warehouse_id, warehouse_name, location_id, location_name,
                    qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
                ) VALUES (?, ?, 'Internal Transfer', ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, ?, ?, ?)
            """, (
                now_str, tx_id_dst, p_id, item['product_name'], item['sku'],
                transfer['dest_warehouse_id'], transfer['dst_warehouse_name'],
                transfer['dest_location_id'], transfer['dst_location_name'],
                qty, new_dst_on_hand, user_id, user_name, transfer['reference_no'],
                f"Transferred from {transfer['src_warehouse_name']} ({transfer['src_location_name']})"
            ))

        cursor.execute("""
            UPDATE transfers 
            SET status = 'Done', completed_at = ?
            WHERE id = ?
        """, (now_str, transfer_id))

        log_audit(conn, user_id, user_name, role, 'COMPLETE_TRANSFER', 'Transfer', transfer['reference_no'],
                  old_values={'status': transfer['status']},
                  new_values={'status': 'Done', 'completed_at': now_str})

        create_notification(conn, 'transfer', f"Transfer {transfer['reference_no']} Completed",
                            f"Successfully transferred items from {transfer['src_location_name']} to {transfer['dst_location_name']}.", 'success',
                            link=f"/transfers?id={transfer_id}")

        conn.commit()
        return {'success': True, 'message': f"Transfer {transfer['reference_no']} completed successfully."}
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ==================== INVENTORY ADJUSTMENTS ====================

def apply_adjustment(product_id, warehouse_id, location_id, counted_qty, reason, user_id=1, user_name='Inventory Manager', role='Inventory Manager', notes=''):
    """
    Applies physical count inventory adjustment:
    1. Fetches current system stock.
    2. Calculates difference = counted_qty - system_qty.
    3. Requires mandatory reason (Damaged, Lost, Expired, Counting Error, Theft, Data Correction, Other).
    4. Updates location on_hand stock to counted_qty.
    5. Writes immutable stock ledger record.
    6. Writes audit log & notification.
    """
    conn = get_db_connection()
    try:
        conn.execute("BEGIN TRANSACTION;")
        cursor = conn.cursor()

        valid_reasons = ['Damaged', 'Lost', 'Expired', 'Counting Error', 'Theft', 'Data Correction', 'Other']
        if reason not in valid_reasons:
            raise ValueError(f"Invalid adjustment reason '{reason}'. Must be one of: {', '.join(valid_reasons)}")

        cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        product = cursor.fetchone()
        if not product:
            raise ValueError(f"Product ID {product_id} not found.")

        cursor.execute("SELECT * FROM warehouses WHERE id = ?", (warehouse_id,))
        warehouse = cursor.fetchone()
        cursor.execute("SELECT * FROM locations WHERE id = ?", (location_id,))
        location = cursor.fetchone()

        stock_row = get_or_create_stock(conn, product_id, warehouse_id, location_id)
        system_qty = stock_row['on_hand']
        counted_qty = float(counted_qty)
        diff_qty = counted_qty - system_qty

        ref_no = f"ADJ-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Record adjustment
        cursor.execute("""
            INSERT INTO adjustments (
                reference_no, warehouse_id, location_id, product_id,
                system_qty, counted_qty, diff_qty, reason, user_id, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ref_no, warehouse_id, location_id, product_id,
            system_qty, counted_qty, diff_qty, reason, user_id, notes, now_str
        ))
        adj_id = cursor.lastrowid

        # Update stock on hand
        cursor.execute("""
            UPDATE stock SET on_hand = ?, updated_at = ? WHERE id = ?
        """, (counted_qty, now_str, stock_row['id']))

        # Write to immutable stock ledger
        tx_id = f"TX-ADJ-{uuid.uuid4().hex[:8].upper()}"
        qty_in = diff_qty if diff_qty > 0 else 0.0
        qty_out = abs(diff_qty) if diff_qty < 0 else 0.0

        cursor.execute("""
            INSERT INTO stock_ledger (
                timestamp, transaction_id, transaction_type, product_id, product_name, sku,
                warehouse_id, warehouse_name, location_id, location_name,
                qty_in, qty_out, balance_after, user_id, user_name, reference_no, reason
            ) VALUES (?, ?, 'Adjustment', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_str, tx_id, product_id, product['name'], product['sku'],
            warehouse_id, warehouse['name'], location_id, location['name'],
            qty_in, qty_out, counted_qty, user_id, user_name, ref_no, f"Reason: {reason}. {notes}".strip()
        ))

        log_audit(conn, user_id, user_name, role, 'APPLY_ADJUSTMENT', 'Adjustment', ref_no,
                  old_values={'system_qty': system_qty, 'location': location['name']},
                  new_values={'counted_qty': counted_qty, 'diff': diff_qty, 'reason': reason})

        create_notification(conn, 'adjustment', f"Stock Adjustment {ref_no}",
                            f"{product['name']} at {location['name']} adjusted from {system_qty} to {counted_qty} ({'+' if diff_qty > 0 else ''}{diff_qty}). Reason: {reason}.",
                            'warning' if diff_qty < 0 else 'info',
                            link=f"/adjustments?id={adj_id}")

        conn.commit()
        return {
            'success': True,
            'message': f"Stock adjusted for {product['name']}. New balance: {counted_qty} units ({'+' if diff_qty > 0 else ''}{diff_qty} diff).",
            'adjustment_id': adj_id,
            'reference_no': ref_no,
            'difference': diff_qty
        }
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ==================== SMART REORDER & PREDICTIONS ====================

def calculate_reorder_recommendations():
    """
    Calculates intelligent reorder suggestions for all active products:
    - Current On Hand Stock
    - Reserved Stock
    - Available Stock = On Hand - Reserved
    - Average Daily Consumption (derived from past 30 days of deliveries & negative adjustments)
    - Supplier Lead Time
    - Safety Stock = Average Daily Usage * Lead Time Buffer (or default safety factor)
    - Reorder Point = (Avg Daily Usage * Lead Time) + Safety Stock
    - Recommended Reorder Qty = max(Reorder Qty, Reorder Point - Available Stock)
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.name as category_name, w.name as default_warehouse_name,
                   COALESCE(SUM(s.on_hand), 0) as total_on_hand,
                   COALESCE(SUM(s.reserved), 0) as total_reserved
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN warehouses w ON p.default_warehouse_id = w.id
            LEFT JOIN stock s ON p.id = s.product_id
            WHERE p.status = 'Active'
            GROUP BY p.id
        """)
        products = cursor.fetchall()

        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

        results = []
        for p in products:
            p_id = p['id']
            # Compute past 30 day outbound velocity
            cursor.execute("""
                SELECT SUM(qty_out) as total_outbound, COUNT(DISTINCT DATE(timestamp)) as active_days
                FROM stock_ledger
                WHERE product_id = ? AND timestamp >= ? AND transaction_type IN ('Delivery', 'Adjustment')
            """, (p_id, thirty_days_ago))
            usage_row = cursor.fetchone()
            total_outbound = usage_row['total_outbound'] or 0.0

            # Daily usage
            avg_daily_usage = round(total_outbound / 30.0, 2)
            if avg_daily_usage == 0.0 and p['reorder_level'] > 0:
                # Fallback baseline rate for estimation if brand new system
                avg_daily_usage = round(p['reorder_level'] / 10.0, 2)

            on_hand = p['total_on_hand']
            reserved = p['total_reserved']
            available = max(0.0, on_hand - reserved)
            lead_time = p['lead_time_days'] or 5

            # Safety stock calculation: 2 days buffer of usage
            safety_stock = round(avg_daily_usage * 2.0, 1)
            calculated_reorder_point = round((avg_daily_usage * lead_time) + safety_stock, 1)
            effective_reorder_point = max(p['reorder_level'], calculated_reorder_point)

            needs_reorder = available <= effective_reorder_point
            suggested_reorder_qty = max(p['reorder_qty'], round(effective_reorder_point - available + (avg_daily_usage * 7), 0))

            # Stockout prediction
            days_to_stockout = None
            if avg_daily_usage > 0:
                days_to_stockout = round(available / avg_daily_usage, 1)
            
            stock_status = 'In Stock'
            if on_hand == 0:
                stock_status = 'Out of Stock'
            elif available <= p['reorder_level']:
                stock_status = 'Low Stock'
            elif available > (p['reorder_level'] * 4) and p['reorder_level'] > 0:
                stock_status = 'Overstocked'

            results.append({
                'product_id': p_id,
                'name': p['name'],
                'sku': p['sku'],
                'category': p['category_name'],
                'uom': p['uom'],
                'cost_price': p['cost_price'],
                'on_hand': on_hand,
                'reserved': reserved,
                'available': available,
                'reorder_level': p['reorder_level'],
                'avg_daily_usage': avg_daily_usage,
                'lead_time_days': lead_time,
                'safety_stock': safety_stock,
                'effective_reorder_point': effective_reorder_point,
                'needs_reorder': needs_reorder,
                'suggested_reorder_qty': suggested_reorder_qty if needs_reorder else 0,
                'days_to_stockout': days_to_stockout,
                'stock_status': stock_status
            })

        return results
    finally:
        conn.close()

# ==================== DASHBOARD KPIs ====================

def get_dashboard_summary():
    """Calculates all real-time dashboard KPIs, charts data, and status pipeline."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        # Total products count
        cursor.execute("SELECT COUNT(*) as count FROM products WHERE status = 'Active'")
        total_products = cursor.fetchone()['count']

        # Total stock units and total inventory valuation
        cursor.execute("""
            SELECT COALESCE(SUM(s.on_hand), 0) as total_units,
                   COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_valuation,
                   COALESCE(SUM(s.reserved), 0) as total_reserved
            FROM stock s
            JOIN products p ON s.product_id = p.id
        """)
        stock_sum = cursor.fetchone()
        total_units = stock_sum['total_units']
        total_valuation = round(stock_sum['total_valuation'], 2)
        total_reserved = stock_sum['total_reserved']

        # Low stock and out of stock counts
        reorders = calculate_reorder_recommendations()
        out_of_stock_count = sum(1 for r in reorders if r['on_hand'] == 0)
        low_stock_count = sum(1 for r in reorders if r['stock_status'] == 'Low Stock')

        # Pending operations
        cursor.execute("SELECT COUNT(*) as count FROM receipts WHERE status IN ('Draft', 'Waiting', 'Ready')")
        pending_receipts = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM deliveries WHERE status IN ('Draft', 'Waiting', 'Ready', 'Picked', 'Packed')")
        pending_deliveries = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) as count FROM transfers WHERE status IN ('Draft', 'Waiting', 'Ready')")
        scheduled_transfers = cursor.fetchone()['count']

        # Stock by warehouse
        cursor.execute("""
            SELECT w.id, w.name, w.code,
                   COALESCE(SUM(s.on_hand), 0) as total_stock,
                   COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_value,
                   COUNT(DISTINCT s.product_id) as product_count
            FROM warehouses w
            LEFT JOIN stock s ON w.id = s.warehouse_id
            LEFT JOIN products p ON s.product_id = p.id
            GROUP BY w.id
        """)
        warehouse_stats = [dict(r) for r in cursor.fetchall()]

        # Top 5 moving products (last 30 days)
        cursor.execute("""
            SELECT product_id, product_name, sku, SUM(qty_out) as total_moved
            FROM stock_ledger
            WHERE transaction_type = 'Delivery'
            GROUP BY product_id
            ORDER BY total_moved DESC
            LIMIT 5
        """)
        top_moving = [dict(r) for r in cursor.fetchall()]

        # Recent activities (last 10)
        cursor.execute("""
            SELECT * FROM stock_ledger
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        recent_ledger = [dict(r) for r in cursor.fetchall()]

        # Past 7 days movement timeline
        cursor.execute("""
            SELECT DATE(timestamp) as day,
                   SUM(qty_in) as total_in,
                   SUM(qty_out) as total_out
            FROM stock_ledger
            WHERE timestamp >= DATE('now', '-7 days')
            GROUP BY DATE(timestamp)
            ORDER BY day ASC
        """)
        timeline_rows = [dict(r) for r in cursor.fetchall()]

        return {
            'kpis': {
                'total_products': total_products,
                'total_stock_units': total_units,
                'total_reserved_units': total_reserved,
                'available_stock_units': max(0.0, total_units - total_reserved),
                'low_stock_items': low_stock_count,
                'out_of_stock_items': out_of_stock_count,
                'pending_receipts': pending_receipts,
                'pending_deliveries': pending_deliveries,
                'scheduled_transfers': scheduled_transfers,
                'inventory_valuation': total_valuation
            },
            'warehouse_stats': warehouse_stats,
            'top_moving': top_moving,
            'recent_activities': recent_ledger,
            'timeline': timeline_rows,
            'low_stock_items': [r for r in reorders if r['stock_status'] in ('Low Stock', 'Out of Stock')][:6]
        }
    finally:
        conn.close()
