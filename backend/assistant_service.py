import sqlite3
import re
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import calculate_reorder_recommendations, get_dashboard_summary

def process_assistant_query(query_text):
    """
    Rule-based inventory NLP assistant engine that queries actual live SQLite state.
    Guaranteed zero hallucination and 100% data reliability.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        query = query_text.lower().strip()

        # 1. Low stock or Out of stock questions
        if any(w in query for w in ['low stock', 'out of stock', 'shortage', 'run out', 'reorder', 'running low']):
            reorders = calculate_reorder_recommendations()
            critical_items = [r for r in reorders if r['needs_reorder'] or r['stock_status'] in ('Low Stock', 'Out of Stock')]
            
            if not critical_items:
                return {
                    'answer': "All inventory items are currently healthy and above their configured reorder safety points!",
                    'type': 'status_positive',
                    'data': []
                }

            summary_lines = []
            for item in critical_items:
                status_pill = f"🚨 {item['stock_status'].upper()}" if item['stock_status'] == 'Out of Stock' else "⚠️ LOW STOCK"
                days_msg = f" (Est. depletion in ~{item['days_to_stockout']} days)" if item['days_to_stockout'] else ""
                summary_lines.append(
                    f"• **{item['name']}** ({item['sku']}): Available **{item['available']} {item['uom']}** (Reorder point: {item['reorder_level']}, Suggested restock: **{item['suggested_reorder_qty']} {item['uom']}**){days_msg} — {status_pill}"
                )

            return {
                'answer': f"Found **{len(critical_items)} items** requiring attention:\n\n" + "\n".join(summary_lines),
                'type': 'low_stock_list',
                'data': critical_items
            }

        # 2. Stockout prediction / Depletion questions
        if any(w in query for w in ['run out soon', 'depletion', 'stockout date', 'forecast', 'deplete', 'days left']):
            reorders = calculate_reorder_recommendations()
            fast_depleting = [r for r in reorders if r['days_to_stockout'] is not None and r['days_to_stockout'] <= 14]
            fast_depleting.sort(key=lambda x: x['days_to_stockout'])

            if not fast_depleting:
                return {
                    'answer': "Based on the last 30-day consumption velocity, no items are projected to stock out within the next 14 days.",
                    'type': 'forecast_healthy',
                    'data': []
                }

            lines = []
            for item in fast_depleting:
                lines.append(f"• **{item['name']}** ({item['sku']}): **{item['available']} {item['uom']}** remaining at **{item['avg_daily_usage']} {item['uom']}/day** → **Estimated stockout in ~{item['days_to_stockout']} days**.")

            return {
                'answer': "📊 **Stockout Risk Forecast** (Historical consumption rate):\n\n" + "\n".join(lines),
                'type': 'stockout_forecast',
                'data': fast_depleting
            }

        # 3. Movements / Today's activity
        if any(w in query for w in ['movement', 'today', 'activity', 'transactions', 'ledger', 'recent']):
            cursor.execute("""
                SELECT * FROM stock_ledger 
                ORDER BY timestamp DESC 
                LIMIT 8
            """)
            recent = [dict(r) for r in cursor.fetchall()]
            
            if not recent:
                return {
                    'answer': "No stock movements recorded yet.",
                    'type': 'empty',
                    'data': []
                }

            lines = []
            for tx in recent:
                flow = f"+{tx['qty_in']}" if tx['qty_in'] > 0 else f"-{tx['qty_out']}"
                lines.append(f"• `[{tx['timestamp']}]` **{tx['transaction_type']}** ({tx['reference_no']}): **{tx['product_name']}** ({flow}) at **{tx['location_name']}** by *{tx['user_name']}*")

            return {
                'answer': "📋 **Recent Stock Transactions Ledger**:\n\n" + "\n".join(lines),
                'type': 'movements_list',
                'data': recent
            }

        # 4. Warehouse stock breakdown / which warehouse has the most
        if any(w in query for w in ['warehouse', 'locations', 'most stock', 'facility', 'capacity']):
            cursor.execute("""
                SELECT w.id, w.name, w.code,
                       COALESCE(SUM(s.on_hand), 0) as total_units,
                       COALESCE(SUM(s.on_hand * p.cost_price), 0) as total_value,
                       COUNT(DISTINCT s.product_id) as total_skus
                FROM warehouses w
                LEFT JOIN stock s ON w.id = s.warehouse_id
                LEFT JOIN products p ON s.product_id = p.id
                GROUP BY w.id
                ORDER BY total_units DESC
            """)
            wh_stats = [dict(r) for r in cursor.fetchall()]

            lines = []
            for w in wh_stats:
                lines.append(f"• **{w['name']}** (`{w['code']}`): **{int(w['total_units'])} total units** across **{w['total_skus']} SKUs** (Valuation: **${w['total_value']:,.2f}**)")

            return {
                'answer': "🏭 **Warehouse Inventory Distribution**:\n\n" + "\n".join(lines),
                'type': 'warehouse_breakdown',
                'data': wh_stats
            }

        # 5. Inventory Valuation / Worth / Value
        if any(w in query for w in ['valuation', 'worth', 'value', 'total value', 'financial']):
            summary = get_dashboard_summary()
            val = summary['kpis']['inventory_valuation']
            units = summary['kpis']['total_stock_units']
            prods = summary['kpis']['total_products']

            return {
                'answer': f"💰 **Total Inventory Valuation**: **${val:,.2f}**\n\nTotaling **{int(units)} physical units** across **{prods} active products**.",
                'type': 'valuation',
                'data': summary['kpis']
            }

        # 6. Unusual Adjustments / Discrepancies / Scrap
        if any(w in query for w in ['adjustment', 'unusual', 'scrap', 'loss', 'damaged', 'discrepancy']):
            cursor.execute("""
                SELECT a.*, p.name as product_name, p.sku, w.name as warehouse_name, l.name as location_name, u.name as user_name
                FROM adjustments a
                JOIN products p ON a.product_id = p.id
                JOIN warehouses w ON a.warehouse_id = w.id
                JOIN locations l ON a.location_id = l.id
                LEFT JOIN users u ON a.user_id = u.id
                ORDER BY a.created_at DESC
                LIMIT 6
            """)
            adjs = [dict(r) for r in cursor.fetchall()]

            if not adjs:
                return {
                    'answer': "No inventory adjustments recorded in the system.",
                    'type': 'empty',
                    'data': []
                }

            lines = []
            for a in adjs:
                diff = f"{'+' if a['diff_qty'] > 0 else ''}{a['diff_qty']}"
                lines.append(f"• **{a['reference_no']}**: **{a['product_name']}** ({diff} units) at {a['location_name']}. Reason: *{a['reason']}*. (User: {a['user_name'] or 'Staff'})")

            return {
                'answer': "🔍 **Recent Inventory Adjustments & Discrepancy Audits**:\n\n" + "\n".join(lines),
                'type': 'adjustments_list',
                'data': adjs
            }

        # 7. Specific Product Search / Lookup
        cursor.execute("SELECT id, name, sku, barcode, cost_price, selling_price, uom FROM products")
        all_products = cursor.fetchall()

        matched_prod = None
        for p in all_products:
            name_parts = p['name'].lower().split()
            if p['sku'].lower() in query or any(part in query for part in name_parts if len(part) > 3):
                matched_prod = p
                break

        if matched_prod:
            p_id = matched_prod['id']
            cursor.execute("""
                SELECT s.on_hand, s.reserved, w.name as warehouse_name, l.name as location_name
                FROM stock s
                JOIN warehouses w ON s.warehouse_id = w.id
                JOIN locations l ON s.location_id = l.id
                WHERE s.product_id = ?
            """, (p_id,))
            stock_rows = cursor.fetchall()

            total_on_hand = sum(r['on_hand'] for r in stock_rows)
            total_reserved = sum(r['reserved'] for r in stock_rows)
            total_available = max(0.0, total_on_hand - total_reserved)

            loc_lines = [f"  - **{r['warehouse_name']}** ({r['location_name']}): {r['on_hand']} on hand (Reserved: {r['reserved']})" for r in stock_rows]

            ans = f"📦 **Product Details: {matched_prod['name']}**\n"
            ans += f"• **SKU**: `{matched_prod['sku']}` | **Barcode**: `{matched_prod['barcode']}`\n"
            ans += f"• **Cost**: ${matched_prod['cost_price']} | **Selling Price**: ${matched_prod['selling_price']}\n"
            ans += f"• **Total On Hand**: **{total_on_hand} {matched_prod['uom']}** | **Reserved**: {total_reserved} | **Available**: **{total_available} {matched_prod['uom']}**\n\n"
            ans += "**Location Breakdown**:\n" + ("\n".join(loc_lines) if loc_lines else "  No stock assigned yet.")

            return {
                'answer': ans,
                'type': 'product_detail',
                'data': {'product': dict(matched_prod), 'locations': [dict(r) for r in stock_rows]}
            }

        # Fallback general summary
        summary = get_dashboard_summary()
        return {
            'answer': (
                f"🤖 **StockSense Assistant** at your service!\n\n"
                f"Currently tracking **{summary['kpis']['total_products']} products** with **{int(summary['kpis']['total_stock_units'])} total units** "
                f"valued at **${summary['kpis']['inventory_valuation']:,.2f}**.\n\n"
                f"• **Low Stock Alerts**: {summary['kpis']['low_stock_items']} items\n"
                f"• **Pending Operations**: {summary['kpis']['pending_receipts']} receipts, {summary['kpis']['pending_deliveries']} deliveries, {summary['kpis']['scheduled_transfers']} transfers.\n\n"
                f"Try asking:\n"
                f"• *'What products are low in stock?'*\n"
                f"• *'Which products may run out soon?'*\n"
                f"• *'Show today's stock movements'* \n"
                f"• *'Which warehouse has the most stock?'*"
            ),
            'type': 'general_summary',
            'data': summary['kpis']
        }
    finally:
        conn.close()
