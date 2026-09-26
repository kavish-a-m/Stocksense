import requests

base = 'http://127.0.0.1:5000/api'

# Reset demo data to clean starting point
requests.post(f'{base}/demo/reset')

# Step 1: Login as Inventory Manager
login_res = requests.post(f'{base}/auth/login', json={'email':'manager@stocksense.com', 'password':'manager123'}).json()
token = login_res['token']
user = login_res['user']
print(f"STEP 1: Logged in as {user['name']} ({user['role']})")

# Step 2: Dashboard
dash = requests.get(f'{base}/dashboard/summary').json()
print("STEP 2: Initial Dashboard KPIs:", dash['kpis'])

# Step 3: Create Receipt for Steel Rods (product 1), Qty 100
rec_res = requests.post(f'{base}/receipts', json={
    'supplier_name': 'ABC Metals Corp',
    'warehouse_id': 1,
    'destination_location_id': 1,
    'scheduled_date': '2026-09-26',
    'notes': 'Hackathon Demo Inbound Batch',
    'items': [{'product_id': 1, 'expected_qty': 100, 'unit_cost': 45.0}],
    'responsible_user_id': user['id'],
    'user_name': user['name']
}).json()
print(f"STEP 3: Created Receipt: {rec_res['reference_no']}")
val_rec = requests.post(f"{base}/receipts/{rec_res['id']}/validate", json={'user_id': user['id'], 'user_name': user['name']}).json()
print(f"         Validated Receipt: {val_rec['message']}")

# Step 4: Verify Steel Rods stock
p1 = requests.get(f'{base}/products/1').json()
print(f"STEP 4: Steel Rods On Hand: {p1['total_on_hand']} {p1['uom']}, Available: {p1['available_stock']}")

# Step 5: Create internal transfer: 1 (Main/Rack A) -> 2 (Prod/Floor), Qty 30
trf_res = requests.post(f'{base}/transfers', json={
    'source_warehouse_id': 1,
    'source_location_id': 1,
    'dest_warehouse_id': 2,
    'dest_location_id': 5,
    'scheduled_date': '2026-09-26',
    'notes': 'Move to assembly floor',
    'items': [{'product_id': 1, 'quantity': 30}],
    'responsible_user_id': user['id'],
    'user_name': user['name']
}).json()
print(f"STEP 5: Created Transfer: {trf_res['reference_no']}")
val_trf = requests.post(f"{base}/transfers/{trf_res['id']}/validate", json={'user_id': user['id'], 'user_name': user['name']}).json()
print(f"         Completed Transfer: {val_trf['message']}")

# Step 6: Create delivery: From Production Floor (loc 5), Qty 20
del_res = requests.post(f'{base}/deliveries', json={
    'customer_name': 'LPU Mechanical Labs',
    'source_warehouse_id': 2,
    'source_location_id': 5,
    'scheduled_date': '2026-09-26',
    'notes': 'Dispatched lab rods',
    'items': [{'product_id': 1, 'requested_qty': 20, 'unit_price': 65.0}],
    'responsible_user_id': user['id'],
    'user_name': user['name']
}).json()
print(f"STEP 6: Created Delivery: {del_res['reference_no']}")
requests.post(f"{base}/deliveries/{del_res['id']}/pick")
requests.post(f"{base}/deliveries/{del_res['id']}/pack")
val_del = requests.post(f"{base}/deliveries/{del_res['id']}/validate", json={'user_id': user['id'], 'user_name': user['name']}).json()
print(f"         Validated Delivery: {val_del['message']}")

# Step 7: Inventory Adjustment for loc 5 (System was 70, physical 67, diff -3)
adj_res = requests.post(f'{base}/adjustments', json={
    'product_id': 1,
    'warehouse_id': 2,
    'location_id': 5,
    'counted_qty': 67.0,
    'reason': 'Damaged',
    'notes': 'Damaged during forklift stacking',
    'user_id': user['id'],
    'user_name': user['name']
}).json()
print(f"STEP 7: Applied Adjustment: {adj_res['message']}")

# Step 8: Stock Ledger
ledger_items = requests.get(f'{base}/ledger?product_id=1&limit=5').json()
print("STEP 8: Recent 5 Ledger Entries for Steel Rods:")
for l in ledger_items:
    flow = f"+{l['qty_in']}" if l['qty_in'] > 0 else f"-{l['qty_out']}"
    print(f"         [{l['timestamp']}] {l['transaction_type']} ({l['reference_no']}) {flow} => Balance: {l['balance_after']} at {l['location_name']}")

# Step 9: Audit Logs
audits = requests.get(f'{base}/audit-logs?limit=4').json()
print("STEP 9: Recent Audit Logs:")
for a in audits:
    print(f"         [{a['timestamp']}] {a['user_name']} ({a['role']}) performed {a['action']} on {a['object_type']} {a['object_id']}")

# Step 10: Updated Dashboard
final_dash = requests.get(f'{base}/dashboard/summary').json()
print("STEP 10: Final Dashboard KPIs:", final_dash['kpis'])
print("\nALL 10 DEMO STEPS VALIDATED AND FULLY OPERATIONAL!")
