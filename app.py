from flask import Flask, render_template, request, redirect, url_for, session, flash, Response, jsonify
import sqlite3
import csv
import io
import math

app = Flask(__name__)
app.secret_key = "super_secret_flask_key_123"
DB_NAME = "database.db"

# Admin Credentials
ADMIN_USERNAME = "Sunny"
ADMIN_PASSWORD = "Sunny@123"

# Initialize SQLite database
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass
        conn.commit()

init_db()

# Main Portal (Form Submission + Admin Dashboard)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')

        if name and email and message:
            with sqlite3.connect(DB_NAME, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO users (name, email, message) VALUES (?, ?, ?)",
                    (name, email, message)
                )
                conn.commit()
            flash("Your response has been submitted successfully!", "success")
        else:
            flash("All fields are required.", "danger")

        return redirect(url_for('index'))

    # Admin Search & Pagination
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 5
    offset = (page - 1) * per_page

    records = []
    total_pages = 1
    total_records = 0

    if session.get('is_admin'):
        with sqlite3.connect(DB_NAME, timeout=10) as conn:
            cursor = conn.cursor()
            if search_query:
                wildcard = f"%{search_query}%"
                cursor.execute(
                    "SELECT COUNT(*) FROM users WHERE name LIKE ? OR email LIKE ? OR message LIKE ?",
                    (wildcard, wildcard, wildcard)
                )
                total_records = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT id, name, email, message, created_at FROM users WHERE name LIKE ? OR email LIKE ? OR message LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (wildcard, wildcard, wildcard, per_page, offset)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM users")
                total_records = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT id, name, email, message, created_at FROM users ORDER BY id DESC LIMIT ? OFFSET ?",
                    (per_page, offset)
                )
            records = cursor.fetchall()

        total_pages = math.ceil(total_records / per_page) if total_records > 0 else 1

    return render_template(
        'index.html',
        records=records,
        search_query=search_query,
        page=page,
        total_pages=total_pages,
        total_records=total_records,
        is_admin=session.get('is_admin', False)
    )

# Admin Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('is_admin'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash("Welcome back, Admin!", "success")
            return redirect(url_for('index'))
        else:
            flash("Invalid Username or Password.", "danger")

    return render_template('login.html')

# Admin Logout
@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('index'))

# Edit Record (Admin Only)
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
            message = request.form.get('message')

            cursor.execute(
                "UPDATE users SET name = ?, email = ?, message = ? WHERE id = ?",
                (name, email, message, user_id)
            )
            conn.commit()
            flash(f"Record #{user_id} updated successfully!", "success")
            return redirect(url_for('index'))

        cursor.execute("SELECT id, name, email, message FROM users WHERE id = ?", (user_id,))
        record = cursor.fetchone()

    if not record:
        flash("Record not found.", "danger")
        return redirect(url_for('index'))

    return render_template('edit.html', record=record)

# Delete Record (Admin Only)
@app.route('/delete/<int:user_id>', methods=['POST'])
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

# Export CSV (Admin Only)
@app.route('/export')
def export_csv():
    if not session.get('is_admin'):
        flash("Unauthorized access. Please log in first.", "danger")
        return redirect(url_for('login'))

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, message, created_at FROM users ORDER BY id DESC")
        records = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Name', 'Email', 'Message', 'Timestamp'])

    for row in records:
        writer.writerow(row)

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=portal_records.csv'}
    )

# Real-Time Polling for Popup (Admin Only)
@app.route('/api/latest-record')
def get_latest_record():
    if not session.get('is_admin'):
        return jsonify({"status": "unauthorized"}), 401

    with sqlite3.connect(DB_NAME, timeout=10) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, message, created_at FROM users ORDER BY id DESC LIMIT 1")
        record = cursor.fetchone()

    if record:
        return jsonify({
            "status": "success",
            "id": record[0],
            "name": record[1],
            "email": record[2],
            "message": record[3],
            "created_at": record[4]
        })
    return jsonify({"status": "empty"})

if __name__ == '__main__':
    app.run(debug=True)