from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session, Response
import random
import time
import sqlite3
import io
import csv
from werkzeug.security import generate_password_hash, check_password_hash
from email_service import send_inquiry_confirmation
from email_service import send_real_otp, send_inquiry_confirmation


app = Flask(__name__)
app.secret_key = "super-secret-key-123"

DB_NAME = "database.db"
otp_store = {}

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                email TEXT,
                phone TEXT,
                message TEXT,
                password TEXT,
                status TEXT DEFAULT 'Pending',
                is_admin INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Ensure schema migrations run smoothly
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'status' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'Pending'")
        if 'password' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN password TEXT")
        if 'phone' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if 'is_admin' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")

        # Create default admin if not existing
        cursor.execute("SELECT id FROM users WHERE email = 'yadavprince773899@gmail.com'")
        if not cursor.fetchone():
            default_pw = generate_password_hash("admin123")
            cursor.execute(
                "INSERT INTO users (name, email, phone, message, password, status, is_admin) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("Administrator", "yadavprince773899@gmail.com", "7738990481", "System Admin", default_pw, 'Resolved', 1)
            )
        conn.commit()

init_db()

# --- User Portal & Admin Dashboard ---
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (name, email, phone, message, status) VALUES (?, ?, ?, ?, 'Pending')",
                (name, email, phone, message)
            )
        conn.commit()
        send_inquiry_confirmation(email, name)
        flash("Your message has been submitted successfully!", "success")
        return redirect(url_for('index'))

    records = []
    stats = {'total': 0, 'pending': 0, 'resolved': 0}

    if session.get('is_admin'):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name, email, phone, message, status, created_at FROM users WHERE is_admin = 0 ORDER BY id DESC")
            records = cursor.fetchall()

            cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 0")
            stats['total'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'Pending' AND is_admin = 0")
            stats['pending'] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM users WHERE status = 'Resolved' AND is_admin = 0")
            stats['resolved'] = cursor.fetchone()[0]

    return render_template('index.html', records=records, stats=stats)

# --- Toggle Status (Pending / Resolved) ---
@app.route('/toggle-status/<int:user_id>', methods=['POST'])
def toggle_status(user_id):
    if not session.get('is_admin'):
        return jsonify({'status': 'unauthorized'}), 401

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            new_status = 'Resolved' if row[0] == 'Pending' else 'Pending'
            cursor.execute("UPDATE users SET status = ? WHERE id = ?", (new_status, user_id))
            conn.commit()
            return jsonify({'status': 'success', 'new_status': new_status})
    return jsonify({'status': 'not_found'}), 404

# --- Admin Login ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')

        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, name, password, is_admin FROM users WHERE (email = ? OR phone = ?)",
                (identifier, identifier)
            )
            user = cursor.fetchone()

        if user and user[2] and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['is_admin'] = bool(user[3])
            flash("Logged in successfully!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid email/phone or password.", "danger")

    return render_template('login.html')

# --- Send Real Email OTP ---
@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json() or {}
    identifier = data.get('identifier', '').strip()

    if not identifier:
        return jsonify({'error': 'Please provide email or phone number'}), 400

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE email = ? OR phone = ?", (identifier, identifier))
        user = cursor.fetchone()

    if not user:
        return jsonify({'error': 'No account found with this Email / Phone'}), 404

    target_email = user[1]  # Database se user ka real email nikala

    # Real Gmail par OTP dispatch karein
    success, otp = send_real_otp(target_email)

    if not success:
        return jsonify({'error': 'Failed to send OTP email. Please check server setup.'}), 500

    # Verification ke liye OTP memory me save karein
    otp_store[identifier] = {
        'otp': str(otp),
        'expires_at': time.time() + 300
    }

    return jsonify({'message': f'Real OTP successfully sent to {target_email}'}), 200

# --- Reset Password ---
@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        entered_otp = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return render_template('reset_password.html')

        stored = otp_store.get(identifier)
        if not stored:
            flash('Please request an OTP first.', 'danger')
            return render_template('reset_password.html')

        if time.time() > stored['expires_at']:
            flash('OTP has expired. Please request a new one.', 'danger')
            return render_template('reset_password.html')

        if stored['otp'] != entered_otp:
            flash('Invalid OTP entered.', 'danger')
            return render_template('reset_password.html')

        hashed_pw = generate_password_hash(new_password)
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password = ? WHERE email = ? OR phone = ?", (hashed_pw, identifier, identifier))
            conn.commit()
        
        otp_store.pop(identifier, None)
        flash('Password successfully reset! Please login now.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

# --- Edit Record (Admin Only) ---
@app.route('/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_record(user_id):
    if not session.get('is_admin'):
        flash("Unauthorized access. Please log in first.", "danger")
        return redirect(url_for('login'))

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            message = request.form.get('message')

            cursor.execute(
                "UPDATE users SET name = ?, email = ?, phone = ?, message = ? WHERE id = ?",
                (name, email, phone, message, user_id)
            )
            conn.commit()
            flash(f"Record #{user_id} updated successfully!", "success")
            return redirect(url_for('index'))

        cursor.execute("SELECT id, name, email, phone, message FROM users WHERE id = ?", (user_id,))
        record = cursor.fetchone()

    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for('index'))

    return render_template('edit.html', record=record)

# --- Delete Record (Admin Only) ---
@app.route('/delete/<int:user_id>', methods=['GET', 'POST'])
def delete_record(user_id):
    if not session.get('is_admin'):
        flash("Unauthorized access. Please log in first.", "danger")
        return redirect(url_for('login'))

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    flash(f"Record #{user_id} deleted successfully!", "success")
    return redirect(url_for('index'))

# --- Logout ---
@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

# --- Export CSV (Admin Only) ---
@app.route('/export')
def export_csv():
    if not session.get('is_admin'):
        flash("Unauthorized access.", "danger")
        return redirect(url_for('login'))

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, phone, message, status, created_at FROM users WHERE is_admin = 0 ORDER BY id DESC")
        records = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Phone', 'Message', 'Status', 'Timestamp'])
    for row in records:
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=portal_records.csv'}
    )

if __name__ == '__main__':
    app.run(debug=True)
    