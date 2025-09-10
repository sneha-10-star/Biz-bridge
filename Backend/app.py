# Backend/app.py (updated)
import os
import re
import time
import json
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template, redirect, url_for,
    session, flash, send_from_directory
)
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
import bcrypt
from werkzeug.utils import secure_filename
from urllib.parse import quote_plus

# ---------- App setup ----------
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_this_to_a_secure_random_value")
CORS(app)


DB_CONFIG = {
    'host': 'localhost',
    'database': 'biz_bridge',
    'user': 'root',
    'password': 'sneha@10',
    'port': 3306
}


DEMO_QR_LINK = "/static/images/qr.png"


# Uploads
UPLOAD_FOLDER = os.path.join(app.static_folder, "images", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  


def get_database_connection():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        print("DB connect error:", e)
    return None

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, (email or "").strip()))

def validate_phone(phone):
    digits = re.sub(r'\D', '', (phone or ""))
    return len(digits) == 10

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------- API: Signup ----------
@app.route('/api/signup', methods=['POST'])
def api_signup():
    
    data = request.get_json(force=True, silent=True) or {}
    role = (data.get("role") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    password = data.get("password") or ""

    if not role or not email or not password:
        return jsonify({"error": "Missing required fields"}), 400
    if not validate_email(email):
        return jsonify({"error": "Invalid email"}), 400
    if not validate_phone(phone):
        return jsonify({"error": "Invalid phone (10 digits)"}), 400

    conn = get_database_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500

    cur = conn.cursor()
    try:
        table = 'experts' if role == 'expert' else 'business'
        cur.execute(f"SELECT id FROM {table} WHERE email = %s", (email,))
        if cur.fetchone():
            return jsonify({"error": "Email already exists"}), 400

        hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        hashed_str = hashed_bytes.decode('utf-8')

        if role == 'expert':
            full_name = data.get("full_name") or ''
            expertise = data.get("expertise") or ''
            experience_years = int(data.get("experience_years") or 0)
            cur.execute("""
                INSERT INTO experts (full_name, email, password_hash, phone, expertise, experience_years, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (full_name, email, hashed_str, phone, expertise, experience_years, datetime.utcnow()))
            conn.commit()
            new_id = cur.lastrowid
            cur2 = conn.cursor(dictionary=True)
            cur2.execute("SELECT id, full_name AS name, email FROM experts WHERE id=%s", (new_id,))
            user_row = cur2.fetchone()
            cur2.close()
            session['user'] = {'id': user_row['id'], 'role': 'expert', 'name': user_row['name'], 'email': user_row['email']}
            return jsonify({"message": "Signup successful", "user": user_row, "role": "expert"}), 201

        else:
            name = data.get("name") or ''
            cur.execute("""
                INSERT INTO business (name, email, password_hash, phone, created_at)
                VALUES (%s,%s,%s,%s,%s)
            """, (name, email, hashed_str, phone, datetime.utcnow()))
            conn.commit()
            new_id = cur.lastrowid
            cur2 = conn.cursor(dictionary=True)
            cur2.execute("SELECT id, name, email FROM business WHERE id=%s", (new_id,))
            user_row = cur2.fetchone()
            cur2.close()
            session['user'] = {'id': user_row['id'], 'role': 'business', 'name': user_row['name'], 'email': user_row['email']}
            return jsonify({"message": "Signup successful", "user": user_row, "role": "business"}), 201

    except Exception as e:
        print("Signup error:", repr(e))
        return jsonify({"error": "Internal server error"}), 500
    finally:
        try:
            cur.close()
        except: pass
        try:
            conn.close()
        except: pass

# ---------- API: Signin ----------
@app.route('/api/signin', methods=['POST'])
def api_signin():
    
    data = request.get_json(force=True, silent=True) or {}
    role = (data.get("role") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not role or not email or not password:
        return jsonify({"error": "Missing credentials"}), 400

    conn = get_database_connection()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500

    cur = conn.cursor(dictionary=True)
    try:
        table = "experts" if role == "expert" else "business"
        cur.execute(f"SELECT * FROM {table} WHERE email = %s", (email,))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        stored_hash = user.get("password_hash")
        if not stored_hash:
            return jsonify({"error": "No password stored"}), 500

        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            display = user.get('full_name') or user.get('name') or user.get('email')
            session['user'] = {'id': user.get('id'), 'role': role, 'name': display, 'email': user.get('email')}
            
            if role == 'expert' and user.get('profile_image'):
                session['user']['photo'] = user.get('profile_image')
            if role == 'business' and user.get('photo'):
                session['user']['photo'] = user.get('photo')
            user['role'] = role
            return jsonify({"message": "Signin successful", "user": user}), 200
        else:
            return jsonify({"error": "Invalid email or password"}), 401

    except Exception as e:
        print("Signin error:", repr(e))
        return jsonify({"error": "Internal server error"}), 500
    finally:
        try:
            cur.close()
        except: pass
        try:
            conn.close()
        except: pass

# ---------- Frontend pages ----------
@app.route('/')
@app.route('/home')
def home_page():
    return render_template('home.html', user=session.get('user'))

@app.route('/signup')
def signup_page():
    return render_template('signup.html', user=session.get('user'))

@app.route('/signin')
def signin_page():
    return render_template('signin.html', user=session.get('user'))

@app.route('/home1.html')
def home1_page():
    return render_template('home1.html', user=session.get('user'))

# ---------- Profile complete (GET & POST) ----------
@app.route('/profilecomplete', methods=['GET', 'POST'])
def complete_profile():
    user = session.get('user')
    if not user:
        flash("Please sign in first.", "warning")
        return redirect(url_for('signin_page'))

    role = user.get('role')
    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))

    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()

        # handle file
        profile_file = request.files.get('profile_image')
        saved_filename = None
        if profile_file and profile_file.filename:
            if allowed_file(profile_file.filename):
                fname = secure_filename(profile_file.filename)
                ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
                saved_filename = f"{role}_{user['id']}_{ts}_{fname}"
                profile_file.save(os.path.join(app.config['UPLOAD_FOLDER'], saved_filename))
            else:
                flash("Invalid image type.", "danger")
                cur.close()
                conn.close()
                return redirect(url_for('complete_profile'))

        try:
            if role == 'expert':
                expertise = request.form.get('expertise', '').strip()
                experience_years = int(request.form.get('experience_years') or 0)
                availability = request.form.get('availability', '').strip()
                bio = request.form.get('bio', '').strip()
                fee = request.form.get('fee') or 0

                updates = []
                values = []
                if phone:
                    updates.append("phone=%s"); values.append(phone)
                if expertise:
                    updates.append("expertise=%s"); values.append(expertise)
                updates.append("experience_years=%s"); values.append(experience_years)
                if availability:
                    updates.append("availability=%s"); values.append(availability)
                if bio:
                    updates.append("bio=%s"); values.append(bio)
                
                try:
                    fee_val = float(fee)
                    updates.append("fee=%s"); values.append(fee_val)
                except Exception:
                    pass
                if saved_filename:
                    updates.append("profile_image=%s"); values.append(saved_filename)

                if updates:
                    updates_sql = ", ".join(updates) + ", updated_at=%s"
                    values.append(datetime.utcnow())
                    values.append(user['id'])
                    sql = f"UPDATE experts SET {updates_sql} WHERE id=%s"
                    cur.execute(sql, tuple(values))
                    conn.commit()

            else: 
                business_name = request.form.get('business_name', '').strip()
                bio = request.form.get('bio', '').strip()
                updates = []
                values = []
                if phone:
                    updates.append("phone=%s"); values.append(phone)
                if business_name:
                    updates.append("business_name=%s"); values.append(business_name)
                if bio:
                    updates.append("bio=%s"); values.append(bio)
                if saved_filename:
                    updates.append("photo=%s"); values.append(saved_filename)

                if updates:
                    updates_sql = ", ".join(updates) + ", updated_at=%s"
                    values.append(datetime.utcnow())
                    values.append(user['id'])
                    sql = f"UPDATE business SET {updates_sql} WHERE id=%s"
                    cur.execute(sql, tuple(values))
                    conn.commit()

            
            if role == 'expert':
                cur.execute("SELECT id, full_name AS name, email, profile_image FROM experts WHERE id=%s", (user['id'],))
                r = cur.fetchone()
                if r:
                    session['user']['name'] = r.get('name') or session['user']['name']
                    session['user']['email'] = r.get('email') or session['user']['email']
                    if r.get('profile_image'):
                        session['user']['photo'] = r.get('profile_image')
            else:
                cur.execute("SELECT id, name, email, photo FROM business WHERE id=%s", (user['id'],))
                r = cur.fetchone()
                if r:
                    session['user']['name'] = r.get('name') or session['user']['name']
                    session['user']['email'] = r.get('email') or session['user']['email']
                    if r.get('photo'):
                        session['user']['photo'] = r.get('photo')

            flash("Profile saved.", "success")
            cur.close()
            conn.close()

            if role == 'expert':
                return redirect(url_for('experts_directory'))
            else:
                return redirect(url_for('home1_page'))

        except Exception as e:
            print("Profile save error:", repr(e))
            flash("Could not save profile.", "danger")
            cur.close()
            conn.close()
            return redirect(url_for('complete_profile'))

    # GET: fetch profile to prefill
    try:
        if role == 'expert':
            cur.execute("SELECT id, full_name AS name, email, phone, expertise, experience_years, availability, profile_image, bio, fee FROM experts WHERE id=%s", (user['id'],))
            profile = cur.fetchone() or {}
        else:
            cur.execute("SELECT id, name, email, phone, business_name, bio, photo FROM business WHERE id=%s", (user['id'],))
            profile = cur.fetchone() or {}
    except Exception as e:
        print("Profile fetch error:", repr(e))
        profile = {}
    finally:
        cur.close()
        conn.close()

    return render_template('profilecomplete.html', user=session.get('user'), profile=profile)

# ---------- Experts directory ----------
@app.route('/experts')
def experts_directory():
    user = session.get('user')
    
    search_term = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    
    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))
    
    cur = conn.cursor(dictionary=True)
    try:
        base_query = """
            SELECT id, full_name AS name, email, phone, expertise, 
                   experience_years, availability, profile_image, bio, fee 
            FROM experts
        """
        
        # Build WHERE conditions
        conditions = []
        params = []
        
        # Add search condition if search term exists
        if search_term:
            conditions.append("(full_name LIKE %s OR expertise LIKE %s OR bio LIKE %s)")
            search_pattern = f'%{search_term}%'
            params.extend([search_pattern, search_pattern, search_pattern])
        
        # Add category condition if category filter exists
        if category_filter and category_filter.lower() != 'all':
            conditions.append("expertise LIKE %s")
            category_pattern = f'%{category_filter}%'
            params.append(category_pattern)
        
        # Build final query
        if conditions:
            query = base_query + " WHERE " + " AND ".join(conditions) + " ORDER BY created_at DESC"
            cur.execute(query, tuple(params))
        else:
            query = base_query + " ORDER BY created_at DESC"
            cur.execute(query)
        
        experts = cur.fetchall()
        
    except Exception as e:
        print("Experts fetch error:", repr(e))
        experts = []
    finally:
        cur.close()
        conn.close()
    
    return render_template('experts.html', user=user, experts=experts)
# ---------- Expert detail page ----------
@app.route('/expert/<int:expert_id>')
def expert_detail(expert_id):
    user = session.get('user')
    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('experts_directory'))
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, full_name AS name, email, phone, expertise, experience_years, availability, profile_image, bio, fee FROM experts WHERE id=%s", (expert_id,))
        expert = cur.fetchone()
        if not expert:
            flash("Expert not found.", "warning")
            return redirect(url_for('experts_directory'))
    except Exception as e:
        print("Expert fetch error:", repr(e))
        expert = None
    finally:
        cur.close()
        conn.close()
    return render_template('expert_profile.html', user=user, expert=expert)

# ---------- Checkout (booking form) ----------
@app.route('/checkout/<int:expert_id>', methods=['GET'])
def checkout(expert_id):
    user = session.get('user')
    if not user or user.get('role') != 'business':
        flash("Please sign in as a business to book.", "warning")
        return redirect(url_for('signin_page'))
    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT id, full_name AS name, expertise, profile_image, fee FROM experts WHERE id=%s", (expert_id,))
        expert = cur.fetchone()
        if not expert:
            flash("Expert not found.", "warning")
            return redirect(url_for('experts_directory'))
    except Exception as e:
        print("Checkout: expert fetch error:", repr(e))
        expert = None
    finally:
        cur.close()
        conn.close()
    return render_template('checkout.html', user=user, expert=expert)

# ---------- Start payment (show QR) ----------
# ---------- Start payment (show QR) ----------

@app.route('/pay/qr', methods=['POST'])
def pay_qr():
    user = session.get('user')
    if not user or user.get('role') != 'business':
        flash("Please sign in as a business to pay.", "warning")
        return redirect(url_for('signin_page'))

    expert_id = request.form.get('expert_id')
    booking_date = request.form.get('booking_date', '').strip()
    notes = request.form.get('notes', '').strip()

    if not expert_id or not booking_date:
        flash("Please provide booking date.", "danger")
        return redirect(url_for('checkout', expert_id=expert_id or 0))

    # ✅ Get expert fee from DB
    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))
    cur = conn.cursor()
    cur.execute("SELECT fee FROM experts WHERE id=%s", (expert_id,))
    row = cur.fetchone()
    cur.close(); conn.close()
    fee = float(row[0]) if row and row[0] else 0.0

    # ✅ Build UPI URI
    vpa = "st898376-1@okhdfcbank"   # your UPI ID
    name = "Biz bridge"
    order_id = f"ORDER-{expert_id}-{int(time.time())}"
    upi_uri = f"upi://pay?pa={vpa}&pn={quote_plus(name)}&am={fee:.2f}&cu=INR&tn={quote_plus(order_id)}"

    # ✅ Generate QR URL
    qr_link = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote_plus(upi_uri)}"

    # Store in session for confirm step
    session['pending_payment'] = {
        'expert_id': int(expert_id),
        'booking_date': booking_date,
        'notes': notes,
        'fee': fee,
        'upi_uri': upi_uri,
        'qr_link': qr_link
    }
    return render_template(
        'payment.html',
        user=user,
        qr_link=qr_link,
        upi_uri=upi_uri,
        fee=fee,
        order_id=order_id
    )


# ---------- Confirm payment & create booking ----------
@app.route('/pay/confirm', methods=['POST'])
def pay_confirm():
    user = session.get('user')
    pending = session.get('pending_payment')
    if not user or user.get('role') != 'business' or not pending:
        flash("No pending payment found.", "danger")
        return redirect(url_for('home1_page'))

    expert_id = pending.get('expert_id')
    booking_date_str = pending.get('booking_date')
    notes = pending.get('notes')
    qr_link = pending.get('qr_link')

    booking_date = booking_date_str  # store free-text as your schema uses varchar

    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))
    cur = conn.cursor()
    try:
        cur.execute("SELECT fee FROM experts WHERE id=%s", (expert_id,))
        row = cur.fetchone()
        fee = float(row[0]) if row and row[0] is not None else 0.0

        ts = int(time.time())
        payment_id = f"QR-{ts}"
        payment_status = 'paid'

        cur.execute("""
            INSERT INTO bookings
            (expert_id, business_id, booking_date, notes, fee, payment_status, qr_link, status, created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (expert_id, user['id'], booking_date, notes or None, fee, payment_status, qr_link, 'confirmed', datetime.utcnow()))
        conn.commit()
        flash("Booking confirmed. Payment marked as paid.", "success")
        session.pop('pending_payment', None)
    except Exception as e:
        print("Pay confirm error:", repr(e))
        flash("Could not create booking.", "danger")
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass

    return redirect(url_for('booking_details'))

# ---------- Booking display (business or expert) ----------
@app.route('/booking')
def booking_details():
    user = session.get('user')
    if not user:
        flash("Please sign in.", "warning")
        return redirect(url_for('signin_page'))

    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))

    cur = conn.cursor(dictionary=True)
    role = (user.get('role') or '').lower()

    try:
        if role == 'business':
            cur.execute("""
                SELECT b.id, b.booking_date, b.status, b.notes, b.fee, b.payment_status, b.qr_link, b.created_at,
                       e.id AS expert_id, e.full_name AS expert_name, e.expertise AS expert_expertise,
                       e.profile_image AS expert_photo, e.email AS expert_email, e.phone AS expert_phone
                FROM bookings b
                JOIN experts e ON b.expert_id = e.id
                WHERE b.business_id = %s
                ORDER BY b.created_at DESC
            """, (user['id'],))
            bookings = cur.fetchall()
        else:
            cur.execute("""
                SELECT b.id, b.booking_date, b.status, b.notes, b.fee, b.payment_status, b.qr_link, b.created_at,
                       biz.id AS business_id, biz.name AS business_name, biz.email AS business_email,
                       biz.phone AS business_phone, biz.photo AS business_photo
                FROM bookings b
                JOIN business biz ON b.business_id = biz.id
                WHERE b.expert_id = %s
                ORDER BY b.created_at DESC
            """, (user['id'],))
            bookings = cur.fetchall()

        cur.close()
        conn.close()
        return render_template('booking.html', user=user, role=role, bookings=bookings)
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            cur.close()
        except: pass
        try:
            conn.close()
        except: pass
        flash("Could not load bookings.", "danger")
        return render_template('booking.html', user=user, role=role, bookings=[])

# ---------- Cancel booking ----------
@app.route('/booking/cancel/<int:booking_id>', methods=['POST'])
def cancel_booking(booking_id):
    user = session.get('user')
    if not user:
        flash("Please sign in.", "warning")
        return redirect(url_for('signin_page'))

    conn = get_database_connection()
    if not conn:
        flash("DB error.", "danger")
        return redirect(url_for('home1_page'))

    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT * FROM bookings WHERE id=%s", (booking_id,))
        booking = cur.fetchone()
        if not booking:
            flash("Booking not found.", "warning")
            cur.close(); conn.close(); return redirect(url_for('booking_details'))

        owner_ok = False
        if user['role'] == 'business' and booking['business_id'] == user['id']:
            owner_ok = True
        if user['role'] == 'expert' and booking['expert_id'] == user['id']:
            owner_ok = True
        if not owner_ok:
            flash("Not authorized to cancel.", "danger")
            cur.close(); conn.close(); return redirect(url_for('booking_details'))

        cur.execute("UPDATE bookings SET status=%s, updated_at=%s WHERE id=%s", ('cancelled', datetime.utcnow(), booking_id))
        conn.commit()
        flash("Booking cancelled.", "info")
    except Exception as e:
        print("Cancel booking error:", repr(e))
        flash("Could not cancel booking.", "danger")
    finally:
        cur.close(); conn.close()
        return redirect(url_for('booking_details'))

# ---------- Serve uploads ----------
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------- Logout ----------
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('home_page'))

# ---------- Run ----------
if __name__ == '__main__':
    print("Starting Biz Bridge server...")
    app.run(host='0.0.0.0', port=5000, debug=True)
