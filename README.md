# 📦 StockSense — Enterprise Smart Inventory Management System
> **Odoo × LPU Jalandhar Hackathon — Production-Grade Solution**

---

## 🌟 Executive Summary & Problem Statement

Modern manufacturing, retail, and logistics enterprises lose billions annually due to **phantom inventory**, **unrecorded shrinkage**, **overselling during peak demand**, and **disjointed spreadsheet registers**. Traditional single-entry databases allow arbitrary row edits, leaving financial auditors with zero traceability when physical shelf stock fails to match ledger balances.

**StockSense** solves this by implementing an enterprise-grade inventory operating system inspired by **Odoo's Double-Entry Logistics Engine**. Every movement of physical goods—whether receiving from a supplier, moving between warehouse aisles, reserving for customer dispatch, or writing off damaged stock—is recorded as an **immutable, append-only ledger transaction** backed by **atomic SQLite ACID operations**.

---

## 🏗️ System Architecture & Data Flow

```mermaid
graph TD
    subgraph Frontend [Modern Single Page Application (SPA)]
        UI[Glassmorphic UI / Vanilla JS]
        DC[Executive Dashboard & Charts]
        CM[Physical Cycle Count Mode]
        BC[Barcode & QR Engine]
        AI[AI Assistant Drawer]
        RBAC[1-Click Persona Switcher]
    end

    subgraph Backend [Modular Python Flask API]
        APP[app.py / Application Gateway]
        AUTH[Auth & RBAC Middleware]
        SVC[inventory_service.py / Business Engine]
        AI_SVC[assistant_service.py / NLP & Analytics]
        
        subgraph Blueprints [REST Blueprints]
            R_PROD[/api/products]
            R_REC[/api/receipts]
            R_DEL[/api/deliveries]
            R_TRA[/api/transfers]
            R_ADJ[/api/adjustments]
            R_LED[/api/ledger]
        end
    end

    subgraph Database [ACID Relational Storage Engine]
        DB[(stocksense.db)]
        T_STOCK[stock table: on_hand, reserved]
        T_LEDGER[stock_ledger table: immutable]
        T_AUDIT[audit_logs table: forensic diffs]
    end

    UI --> APP
    APP --> Blueprints
    Blueprints --> AUTH
    AUTH --> SVC
    SVC --> DB
    AI --> AI_SVC
    AI_SVC --> DB
    SVC --> T_STOCK
    SVC --> T_LEDGER
    SVC --> T_AUDIT
```

---

## ⚡ Core Pillars & Differentiators

### 1. 🧮 Mathematical Inventory & Double-Entry Allocation Model
StockSense strictly enforces real-time stock separation:
$$\text{Available Stock} = \text{On-Hand Stock} - \text{Reserved Stock}$$

* **Inbound Receipts (`WH/IN`)**: 
  $$\text{On-Hand}_{\text{destination}} \mathrel{+}= \text{Quantity}$$
  *Atomic stock increment with vendor traceability and Goods Receipt Note (GRN) generation.*
* **Outbound Deliveries (`WH/OUT`)**:
  * **Step 1 (Check & Reserve)**: Validates $\text{Available} \ge \text{Quantity}$; locks stock:
    $$\text{Reserved}_{\text{source}} \mathrel{+}= \text{Quantity}$$
  * **Step 2 (Pick, Pack & Ship)**: Dispatches goods from warehouse floor:
    $$\text{On-Hand}_{\text{source}} \mathrel{-}= \text{Quantity}, \quad \text{Reserved}_{\text{source}} \mathrel{-}= \text{Quantity}$$
* **Internal Transfers (`WH/INT`)**:
  $$\text{On-Hand}_{\text{source}} \mathrel{-}= \text{Quantity}, \quad \text{On-Hand}_{\text{destination}} \mathrel{+}= \text{Quantity}$$
  *Total company inventory remains perfectly conserved ($\Delta \text{Total} = 0$).*
* **Stock Adjustments (`ADJ`)**:
  $$\text{Difference} = \text{Counted Quantity} - \text{System On-Hand}$$
  $$\text{On-Hand}_{\text{location}} = \text{Counted Quantity}$$

---

### 2. 📜 Immutable Stock Ledger & Forensic Audit Trail
* **Append-Only Ledger**: No `UPDATE` or `DELETE` operations are ever executed on historical transaction records.
* **Running Balances**: Every entry logs timestamp, unique transaction ID (`TX-XXX-XXXX`), document reference (`WH/IN/0006`, `WH/OUT/0011`), user attribution, quantity in/out, and new balance after movement.
* **Security Audit Logs**: Forensic records capturing operator identity, IP/session, timestamp, action type, and before/after JSON diffs.
* **One-Click Compliance Export**: Instant CSV and print-ready reports for external audits.

---

### 3. 🔍 Warehouse Stock Count Mode (Cycle Counting)
* Integrated physical shelf-audit tool located in [`static/js/stock_count.js`](file:///d:/Odoo%20hackathon%20LPU/static/js/stock_count.js).
* Staff select a warehouse rack to load all resident product SKUs.
* **Reactive Discrepancy Highlighting**: As staff input real counts, the UI dynamically calculates variances with live color coding:
  * 🟢 **Green ($0$)**: Physical count matches database.
  * 🔵 **Blue ($>0$)**: Surplus / Unrecorded receipt.
  * 🔴 **Red ($<0$)**: Deficit / Shrinkage / Damage.
* **Mandatory Reason Gating**: Adjustments require an auditable reason classification (*Counting Error, Damaged, Lost, Expired, Theft, Data Correction*).
* **Batch Reconcile**: Submits only discrepant items in a single atomic transaction.

---

### 4. 📈 Smart Replenishment & Reorder Intelligence
StockSense computes predictive replenishment metrics directly against transaction histories:
* **Average Daily Usage (ADU)**:
  $$\text{ADU} = \frac{\text{Total Outbound Units in Last 30 Days}}{30}$$
* **Dynamic Safety Stock Buffer**:
  $$\text{Safety Stock} = \text{Supplier Lead Time (Days)} \times \text{ADU} \times 1.5$$
* **Estimated Days to Stockout**:
  $$\text{Days to Depletion} = \frac{\text{Available Units}}{\text{ADU}}$$
* Automatically flags items needing replenishment and triggers visual alerts across the dashboard.

---

### 5. 🤖 Embedded AI Inventory Assistant
* Conversational AI engine querying live database state via [`backend/assistant_service.py`](file:///d:/Odoo%20hackathon%20LPU/backend/assistant_service.py).
* Answers operational questions in natural language:
  * *"What products are low in stock?"*
  * *"Which warehouse holds the highest inventory valuation?"*
  * *"Show me fast-depleting items and reorder recommendations."*
  * *"Summarize today's stock movements."*

---

### 6. 📷 Barcode & QR Code Integration
* Generates live printable QR tags and alphanumeric barcodes for all master SKUs and transfer slips.
* Built-in browser camera scanner leveraging WebRTC webcam streams + simulated SKU scanner for instant warehouse lookups.

---

## 👥 Role-Based Access Control (RBAC) Matrix

| Feature / Permission | Admin | Inventory Manager | Warehouse Staff | Viewer |
|---|:---:|:---:|:---:|:---:|
| **View Dashboard & KPIs** | ✅ | ✅ | ✅ | ✅ |
| **View Products & Locations** | ✅ | ✅ | ✅ | ✅ |
| **Create & Validate Receipts** | ✅ | ✅ | ✅ | ❌ |
| **Create & Process Deliveries** | ✅ | ✅ | ✅ | ❌ |
| **Execute Internal Transfers** | ✅ | ✅ | ✅ | ❌ |
| **Physical Stock Count / Adjustments** | ✅ | ✅ | ✅ (Count only) | ❌ |
| **Stock Ledger & Audit Logs** | ✅ | ✅ | ❌ | ✅ (Read) |
| **System Settings & DB Reset** | ✅ | ❌ | ❌ | ❌ |

---

## 📂 Project Directory Structure

```
d:/Odoo hackathon LPU/
├── backend/
│   ├── app.py                      # Flask Server entrypoint & Blueprint registry
│   ├── database.py                 # SQLite connection manager & helper utilities
│   ├── inventory_service.py        # Core ACID inventory business logic & ledger engine
│   ├── assistant_service.py        # AI Assistant engine & stockout analytics
│   ├── seed_data.py                # Enterprise demo seed generator
│   ├── test_demo_flow.py           # Automated 10-step verification test script
│   └── routes/
│       ├── auth_routes.py          # Authentication & persona management
│       ├── product_routes.py       # Products, categories & reorder logic
│       ├── receipt_routes.py       # Inbound PO receiving (WH/IN)
│       ├── delivery_routes.py      # Outbound sales dispatch & reservation (WH/OUT)
│       ├── transfer_routes.py      # Internal inter-warehouse moves (WH/INT)
│       ├── adjustment_routes.py    # Discrepancy reconciliation & bulk cycle count
│       ├── ledger_routes.py        # Immutable stock ledger & audit trail
│       └── dashboard_routes.py     # Real-time KPIs & valuation analytics
├── static/
│   ├── css/
│   │   └── styles.css              # Custom responsive glassmorphic design system
│   ├── js/
│   │   ├── api.js                  # Frontend HTTP client with error handling
│   │   ├── app.js                  # Main SPA router & persona switcher
│   │   ├── dashboard.js            # KPI rendering, Chart.js analytics & alerts
│   │   ├── products.js             # Product catalog, multi-rack stock & QR tags
│   │   ├── receipts.js             # Receiving workflow & validation UI
│   │   ├── deliveries.js           # Reservation, picking & shipping UI
│   │   ├── transfers.js            # Inter-warehouse transfer UI
│   │   ├── adjustments.js          # Adjustment logging & reason gating
│   │   ├── stock_count.js          # Warehouse physical count & live variance grid
│   │   ├── ledger.js               # Immutable ledger viewer & CSV export
│   │   ├── audit.js                # Security audit log inspector
│   │   ├── barcode.js              # Camera QR/barcode scanner
│   │   ├── assistant.js            # AI conversational assistant drawer
│   │   └── demo_guide.js           # Guided 10-step hackathon walkthrough banner
│   └── index.html                  # Single-Page Application root interface
├── stocksense.db                   # SQLite relational database
├── README.md                       # Comprehensive documentation
└── requirements.txt                # Python dependencies
```

---

## 🚀 Quickstart & Setup Guide

### 1. Prerequisites
* Python 3.10 or higher
* Modern web browser (Chrome, Edge, Firefox, Safari)

### 2. Installation
Clone the repository and install the lightweight dependencies:
```bash
# Clone the repository
git clone https://github.com/your-repo/stocksense.git
cd "Odoo hackathon LPU"

# Install dependencies
pip install flask flask-cors requests
```

### 3. Start the Server
Launch the Flask backend server:
```bash
python -m backend.app
```
*The server will start at **[http://127.0.0.1:5000](http://127.0.0.1:5000)**.*

### 4. Open Application
Navigate to [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## 🏆 10-Step Hackathon Demonstration Script (Section 42)

The application includes an **interactive Guided Demo Banner** at the top of the interface. Here is the complete end-to-end verification walkthrough:

| Step | Action | Expected System Result |
|:---:|---|---|
| **1** | **Role-Based Login** | Click `Manager (Full Ops)` on login screen. Logs in as Rahul Sharma (`Inventory Manager`). |
| **2** | **Executive Dashboard** | Inspect real-time KPI cards: **10 Products**, **1,004 Stock Units**, **$568,660.00 Valuation**, and 7-day movement velocity charts. |
| **3** | **Inbound Receipt (`WH/IN`)** | Navigate to `Receipts (In)` &rarr; Click `+ New Inbound Receipt` &rarr; Supplier: **ABC Metals Corp**, Product: **Steel Rods**, Qty: **100** &rarr; Click **Validate & Accept Stock**. Stock increments atomically. |
| **4** | **Product Master Data** | Open `Products` &rarr; Select **Steel Rods**. Verify on-hand stock increased to **310 units** across storage locations with live QR code tag. |
| **5** | **Internal Transfer (`WH/INT`)** | Navigate to `Transfers` &rarr; Move **30 units** from *Main Warehouse (Rack A)* to *Production Plant (Floor)* &rarr; Click **Complete Transfer**. Location balances update while total company stock remains 310 units. |
| **6** | **Outbound Delivery (`WH/OUT`)** | Navigate to `Deliveries` &rarr; Create delivery of **20 units** for *LPU Mechanical Labs* from *Production Floor* &rarr; Click **Check Availability** (reserves stock) &rarr; **Pick** &rarr; **Pack** &rarr; **Validate & Ship**. |
| **7** | **Physical Stock Count** | Open `Adjustments` &rarr; Cycle Count Mode &rarr; Select *Production Floor*. System Stock: 70 &rarr; Enter Physical Count: 67 &rarr; Discrepancy: **-3 kg** &rarr; Select Reason: `Damaged` &rarr; Click **Apply Adjustments**. |
| **8** | **Immutable Stock Ledger** | Navigate to `Stock Ledger`. Verify full chronological transaction trail: `+100 Receipt`, `Transfer 30`, `-20 Delivery`, `-3 Adjustment` with running balances. Click **Export CSV**. |
| **9** | **Security Audit Trail** | Navigate to `Audit Trail`. Verify complete digital footprint tracking user `Rahul Sharma`, timestamp, and before/after JSON diff payloads. |
| **10** | **AI Assistant & Summary** | Open `AI Assistant` in top navbar &rarr; Ask *"What products are low in stock?"* &rarr; Verify instant real-time replenishment advice and updated dashboard valuation. |

---

## 🧪 Automated Testing & Continuous Verification

StockSense includes an end-to-end automated verification script that executes all 10 steps via HTTP API calls and asserts database integrity, stock calculations, and ledger balances:

```bash
python -m backend.test_demo_flow
```

**Expected Test Output:**
```
STEP 1: Logged in as Rahul Sharma (Inventory Manager)
STEP 2: Initial Dashboard KPIs: {'total_products': 10, 'total_stock_units': 1004.0, 'inventory_valuation': 568660.0, ...}
STEP 3: Created Receipt: WH/IN/0011 -> Validated Receipt successfully.
STEP 4: Steel Rods On Hand: 310.0 kg, Available: 290.0
STEP 5: Created Transfer: WH/INT/0006 -> Completed Transfer successfully.
STEP 6: Created Delivery: WH/OUT/0011 -> Validated Delivery and dispatched.
STEP 7: Applied Adjustment: Stock adjusted for Steel Rods. New balance: 67.0 units (-3.0 diff).
STEP 8: Recent 5 Ledger Entries verified with running balance tracking.
STEP 9: Audit Trail logs verified with user identity and diffs.
STEP 10: Final Dashboard KPIs updated with new valuation.

ALL 10 DEMO STEPS VALIDATED AND FULLY OPERATIONAL!
```

---

## 📡 REST API Reference

### 1. Products (`/api/products`)
* `GET /api/products`: Retrieve all products with aggregated on-hand and reserved stock.
* `GET /api/products/<id>`: Retrieve granular multi-location stock breakdown and reorder metrics.
* `POST /api/products`: Create a new master product SKU.

### 2. Receipts (`/api/receipts`)
* `GET /api/receipts`: List all inbound supplier purchase receipts.
* `POST /api/receipts`: Create a draft inbound receipt (`WH/IN`).
* `POST /api/receipts/<id>/validate`: Atomically validate receipt, increment on-hand stock, and write ledger entry.

### 3. Deliveries (`/api/deliveries`)
* `GET /api/deliveries`: List all outbound customer delivery orders.
* `POST /api/deliveries`: Create a draft outbound delivery (`WH/OUT`).
* `POST /api/deliveries/<id>/check-availability`: Check stock and lock units into `reserved`.
* `POST /api/deliveries/<id>/validate`: Dispatch goods, decrement physical stock, and write ledger entry.

### 4. Transfers (`/api/transfers`)
* `GET /api/transfers`: List internal inter-warehouse transfers.
* `POST /api/transfers`: Create an internal move request (`WH/INT`).
* `POST /api/transfers/<id>/complete`: Execute atomic transfer between locations.

### 5. Adjustments (`/api/adjustments`)
* `POST /api/adjustments`: Record individual stock discrepancy with mandatory reason code.
* `POST /api/adjustments/bulk-count`: Batch cycle-count endpoint for multi-item reconciliation.

### 6. Ledger & Analytics (`/api/ledger`, `/api/dashboard`)
* `GET /api/ledger`: Retrieve immutable audit ledger entries.
* `GET /api/dashboard/summary`: Aggregate real-time KPIs, movement velocity, and total valuation.
* `POST /api/assistant/query`: NLP AI assistant query endpoint.

---

## 📄 Hackathon Submission & Authors
* **Event**: Odoo × LPU Jalandhar Hackathon
* **Project Name**: StockSense — Smart Inventory Management System
* **Architecture**: Vanilla JS SPA + Python Flask REST API + SQLite ACID Ledger
* **License**: MIT
