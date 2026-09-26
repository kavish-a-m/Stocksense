from flask import Blueprint, request, jsonify
import hashlib
from datetime import datetime
from backend.database import get_db_connection
from backend.inventory_service import log_audit

auth_bp = Blueprint('auth', __name__)

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# In-memory OTP store for simulated OTP resets
OTP_STORE = {}

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'error': 'Email and password are required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.*, w.name as warehouse_name
        FROM users u
        LEFT JOIN warehouses w ON u.warehouse_id = w.id
        WHERE LOWER(u.email) = ?
    """, (email,))
    user = cursor.fetchone()

    if not user or user['password_hash'] != hash_pw(password):
        conn.close()
        return jsonify({'error': 'Invalid email or password.'}), 401

    log_audit(conn, user['id'], user['name'], user['role'], 'USER_LOGIN', 'User', user['id'],
              ip_address=request.remote_addr or '127.0.0.1', device=request.headers.get('User-Agent', 'Web Browser')[:50])
    conn.commit()
    conn.close()

    user_dict = dict(user)
    del user_dict['password_hash']
    # Generate simple session token
    token = f"tk_{user_dict['id']}_{hashlib.md5(f'{user_dict['email']}_{datetime.now()}'.encode()).hexdigest()[:16]}"
    
    return jsonify({
        'token': token,
        'user': user_dict
    })

@auth_bp.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'Warehouse Staff')
    warehouse_id = data.get('warehouse_id', 1)

    if not name or not email or not password:
        return jsonify({'error': 'Name, email, and password are required.'}), 400

    if role not in ['Admin', 'Inventory Manager', 'Warehouse Staff', 'Viewer']:
        return jsonify({'error': 'Invalid role specified.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'An account with this email already exists.'}), 400

    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, warehouse_id)
        VALUES (?, ?, ?, ?, ?)
    """, (name, email, hash_pw(password), role, warehouse_id))
    user_id = cursor.lastrowid

    log_audit(conn, user_id, name, role, 'USER_SIGNUP', 'User', user_id)
    conn.commit()

    cursor.execute("SELECT u.*, w.name as warehouse_name FROM users u LEFT JOIN warehouses w ON u.warehouse_id = w.id WHERE u.id = ?", (user_id,))
    new_user = dict(cursor.fetchone())
    conn.close()
    del new_user['password_hash']

    token = f"tk_{new_user['id']}_{hashlib.md5(f'{new_user['email']}_{datetime.now()}'.encode()).hexdigest()[:16]}"
    return jsonify({'token': token, 'user': new_user}), 201

@auth_bp.route('/api/auth/users', methods=['GET'])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.name, u.email, u.role, u.warehouse_id, u.avatar, u.created_at, w.name as warehouse_name
        FROM users u
        LEFT JOIN warehouses w ON u.warehouse_id = w.id
        ORDER BY u.id ASC
    """)
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(users)

@auth_bp.route('/api/auth/reset-password-otp', methods=['POST'])
def request_password_reset():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'error': 'Email is required.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'No user account found with that email.'}), 404

    # Simulated 6-digit OTP
    otp = "482910"  # deterministic for smooth hackathon demo testing
    OTP_STORE[email] = otp

    return jsonify({
        'success': True,
        'message': f"OTP verification code sent to {email}. (For demo: use code 482910)",
        'demo_otp': otp
    })

@auth_bp.route('/api/auth/verify-otp-reset', methods=['POST'])
def verify_otp_and_reset():
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()
    new_password = data.get('new_password', '')

    if not email or not otp or not new_password:
        return jsonify({'error': 'Email, OTP, and new password are required.'}), 400

    if OTP_STORE.get(email) != otp and otp != '482910':
        return jsonify({'error': 'Invalid or expired OTP code.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET password_hash = ? WHERE LOWER(email) = ?", (hash_pw(new_password), email))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': 'User not found.'}), 404

    cursor.execute("SELECT id, name, role FROM users WHERE LOWER(email) = ?", (email,))
    user = cursor.fetchone()
    log_audit(conn, user['id'], user['name'], user['role'], 'PASSWORD_RESET_OTP', 'User', user['id'])
    
    conn.commit()
    conn.close()

    OTP_STORE.pop(email, None)
    return jsonify({'success': True, 'message': 'Password has been reset successfully. Please log in.'})
