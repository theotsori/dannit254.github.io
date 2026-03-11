from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, uuid, re
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dannit-media-secret-2024-change-in-prod')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
MAX_CONTENT_LENGTH = 20 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

DB_PATH = os.path.join(BASE_DIR, 'instance', 'dannit.db')

# Default seed data — only written to DB on first run
DEFAULT_CATEGORIES = {
    'studio': {
        'label': 'Studio Portraits',
        'subcategories': ['Birthday Shoots', 'Couple Shoots', 'Family Shoots',
                          'Baby Bump Shoots', 'Wrap Photoshoots', 'Graduation Shoots']
    },
    'outdoor': {
        'label': 'Outdoor Portraits',
        'subcategories': ['Engagement Shoots', 'Nature Portraits', 'Urban Portraits']
    },
    'events': {
        'label': 'Events',
        'subcategories': ['Weddings', 'Pre-Weddings', 'Corporate Events', 'Team Building']
    }
}

# ─── Database ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def get_categories():
    """Return all categories + subcategories from the DB at runtime.
    Returns an empty dict gracefully if the table doesn't exist yet."""
    try:
        db = get_db()
        cats = db.execute('SELECT * FROM categories ORDER BY sort_order ASC, label ASC').fetchall()
        result = {}
        for cat in cats:
            subs = db.execute(
                'SELECT name FROM subcategories WHERE category_key=? ORDER BY sort_order ASC, name ASC',
                (cat['key'],)
            ).fetchall()
            result[cat['key']] = {
                'label': cat['label'],
                'subcategories': [s['name'] for s in subs]
            }
        db.close()
        return result
    except Exception:
        return {}


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS categories (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS subcategories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_key TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (category_key) REFERENCES categories(key) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            category TEXT NOT NULL,
            subcategory TEXT,
            caption TEXT,
            description TEXT,
            featured INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            service TEXT,
            message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'new'
        );
    ''')

    # Seed admin
    if not db.execute('SELECT id FROM admin WHERE username=?', ('admin',)).fetchone():
        db.execute('INSERT INTO admin (username,password) VALUES (?,?)',
                   ('admin', generate_password_hash('dannit2024')))

    # Seed settings
    defaults = {
        'site_name': 'Dannit Media Studios',
        'tagline': 'Where Every Frame Tells a Story',
        'location': 'Nairobi, Kenya',
        'phone': '+254 700 000 000',
        'email': 'hello@dannitmedia.com',
        'instagram': '#', 'tiktok': '#', 'youtube': '#', 'facebook': '#',
        'whatsapp': '+254700000000',
        'hero_text': 'Luxury Photography & Videography'
    }
    for k, v in defaults.items():
        db.execute('INSERT OR IGNORE INTO site_settings (key,value) VALUES (?,?)', (k, v))

    # Seed default categories
    for i, (key, cat) in enumerate(DEFAULT_CATEGORIES.items()):
        os.makedirs(os.path.join(UPLOAD_FOLDER, key), exist_ok=True)
        db.execute('INSERT OR IGNORE INTO categories (key,label,sort_order) VALUES (?,?,?)',
                   (key, cat['label'], i))
        for j, sub in enumerate(cat['subcategories']):
            if not db.execute('SELECT id FROM subcategories WHERE category_key=? AND name=?',
                              (key, sub)).fetchone():
                db.execute('INSERT INTO subcategories (category_key,name,sort_order) VALUES (?,?,?)',
                           (key, sub, j))

    db.commit()
    db.close()


def get_settings():
    db = get_db()
    rows = db.execute('SELECT key,value FROM site_settings').fetchall()
    db.close()
    return {r['key']: r['value'] for r in rows}


@app.context_processor
def inject_globals():
    ctx = {'categories': get_categories()}
    if 'admin_logged_in' in session:
        try:
            db = get_db()
            ctx['stats'] = {
                'bookings': db.execute(
                    "SELECT COUNT(*) as c FROM bookings WHERE status='new'"
                ).fetchone()['c']
            }
            db.close()
        except Exception:
            ctx['stats'] = {'bookings': 0}
    return ctx


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── Auth ─────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated

# ─── Public Routes ────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    featured = db.execute(
        'SELECT * FROM photos WHERE featured=1 ORDER BY sort_order ASC LIMIT 12'
    ).fetchall()
    settings = get_settings()
    db.close()
    return render_template('index.html', featured=featured, settings=settings)


@app.route('/portfolio')
def portfolio():
    db = get_db()
    settings = get_settings()
    categories = get_categories()
    photos_by_cat = {
        key: db.execute(
            'SELECT * FROM photos WHERE category=? ORDER BY sort_order ASC, created_at DESC',
            (key,)
        ).fetchall()
        for key in categories
    }
    db.close()
    return render_template('portfolio.html', photos_by_cat=photos_by_cat, settings=settings)


@app.route('/portfolio/<category>')
def portfolio_category(category):
    categories = get_categories()
    if category not in categories:
        return redirect(url_for('portfolio'))
    db = get_db()
    settings = get_settings()
    sub = request.args.get('sub', '')
    if sub:
        photos = db.execute(
            'SELECT * FROM photos WHERE category=? AND subcategory=? ORDER BY sort_order ASC, created_at DESC',
            (category, sub)
        ).fetchall()
    else:
        photos = db.execute(
            'SELECT * FROM photos WHERE category=? ORDER BY sort_order ASC, created_at DESC',
            (category,)
        ).fetchall()
    db.close()
    return render_template('gallery.html', photos=photos, category=category,
                           cat_info=categories[category], settings=settings, active_sub=sub)


@app.route('/api/photos')
def api_photos():
    category = request.args.get('category', '')
    sub = request.args.get('sub', '')
    db = get_db()
    if sub:
        photos = db.execute(
            'SELECT * FROM photos WHERE category=? AND subcategory=? ORDER BY sort_order ASC, created_at DESC',
            (category, sub)
        ).fetchall()
    elif category:
        photos = db.execute(
            'SELECT * FROM photos WHERE category=? ORDER BY sort_order ASC, created_at DESC',
            (category,)
        ).fetchall()
    else:
        photos = db.execute('SELECT * FROM photos ORDER BY created_at DESC').fetchall()
    db.close()
    return jsonify([dict(p) for p in photos])


@app.route('/contact', methods=['POST'])
def contact():
    data = request.get_json(silent=True) or request.form
    db = get_db()
    db.execute(
        'INSERT INTO bookings (name,email,phone,service,message) VALUES (?,?,?,?,?)',
        (data.get('name'), data.get('email'), data.get('phone'),
         data.get('service'), data.get('message'))
    )
    db.commit()
    db.close()
    if request.is_json:
        return jsonify({'message': "Thank you! We'll be in touch shortly."})
    return redirect(url_for('index') + '#contact')


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ─── Admin ─── Auth ──────────────────────────────────────────────────────────

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if "admin_logged_in" in session:
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        db = get_db()
        admin = db.execute("SELECT * FROM admin WHERE username=?", (username,)).fetchone()
        db.close()
        if admin and check_password_hash(admin["password"], password):
            session["admin_logged_in"] = True
            session["admin_username"] = username
            return redirect(url_for("admin_dashboard"))
        return render_template("admin/login.html", error="Invalid username or password.")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ─── Admin — Dashboard ────────────────────────────────────────────────────────

@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    db = get_db()
    categories = get_categories()
    stats = {
        'total':    db.execute('SELECT COUNT(*) as c FROM photos').fetchone()['c'],
        'featured': db.execute("SELECT COUNT(*) as c FROM photos WHERE featured=1").fetchone()['c'],
        'bookings': db.execute("SELECT COUNT(*) as c FROM bookings WHERE status='new'").fetchone()['c'],
    }
    for cat_key in categories:
        stats[cat_key] = db.execute(
            "SELECT COUNT(*) as c FROM photos WHERE category=?", (cat_key,)
        ).fetchone()['c']
    recent_photos   = db.execute('SELECT * FROM photos ORDER BY created_at DESC LIMIT 8').fetchall()
    recent_bookings = db.execute('SELECT * FROM bookings ORDER BY created_at DESC LIMIT 5').fetchall()
    db.close()
    return render_template('admin/dashboard.html', stats=stats,
                           recent_photos=recent_photos, recent_bookings=recent_bookings)

# ─── Admin — Photos ───────────────────────────────────────────────────────────

@app.route('/admin/upload', methods=['GET', 'POST'])
@login_required
def admin_upload():
    if request.method == 'POST':
        files       = request.files.getlist('photos')
        category    = request.form.get('category', 'studio')
        subcategory = request.form.get('subcategory', '')
        caption     = request.form.get('caption', '')
        description = request.form.get('description', '')
        featured    = 1 if request.form.get('featured') else 0
        uploaded = 0
        db = get_db()
        for file in files:
            if file and allowed_file(file.filename):
                ext      = file.filename.rsplit('.', 1)[1].lower()
                uid      = str(uuid.uuid4())
                new_name = f"{uid}.{ext}"
                cat_folder = os.path.join(app.config['UPLOAD_FOLDER'], category)
                os.makedirs(cat_folder, exist_ok=True)
                file.save(os.path.join(cat_folder, new_name))
                db.execute(
                    'INSERT INTO photos (uuid,filename,original_name,category,subcategory,caption,description,featured) '
                    'VALUES (?,?,?,?,?,?,?,?)',
                    (uid, f"{category}/{new_name}", secure_filename(file.filename),
                     category, subcategory, caption, description, featured)
                )
                uploaded += 1
        db.commit()
        db.close()
        flash(f'Successfully uploaded {uploaded} photo(s)!', 'success')
        return redirect(url_for('admin_photos'))
    return render_template('admin/upload.html')


@app.route('/admin/photos')
@login_required
def admin_photos():
    db = get_db()
    category = request.args.get('category', '')
    if category:
        photos = db.execute(
            'SELECT * FROM photos WHERE category=? ORDER BY created_at DESC', (category,)
        ).fetchall()
    else:
        photos = db.execute('SELECT * FROM photos ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('admin/photos.html', photos=photos, active_cat=category)


@app.route('/admin/photos/<int:photo_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_photo(photo_id):
    db = get_db()
    photo = db.execute('SELECT * FROM photos WHERE id=?', (photo_id,)).fetchone()
    if not photo:
        db.close()
        return redirect(url_for('admin_photos'))
    if request.method == 'POST':
        db.execute(
            'UPDATE photos SET category=?,subcategory=?,caption=?,description=?,featured=?,sort_order=? WHERE id=?',
            (request.form.get('category'), request.form.get('subcategory'),
             request.form.get('caption'), request.form.get('description'),
             1 if request.form.get('featured') else 0,
             int(request.form.get('sort_order', 0)), photo_id)
        )
        db.commit()
        db.close()
        flash('Photo updated successfully!', 'success')
        return redirect(url_for('admin_photos'))
    db.close()
    return render_template('admin/edit_photo.html', photo=photo)


@app.route('/admin/photos/<int:photo_id>/delete', methods=['POST'])
@login_required
def admin_delete_photo(photo_id):
    db = get_db()
    photo = db.execute('SELECT * FROM photos WHERE id=?', (photo_id,)).fetchone()
    if photo:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], photo['filename'])
        if os.path.exists(filepath):
            os.remove(filepath)
        db.execute('DELETE FROM photos WHERE id=?', (photo_id,))
        db.commit()
    db.close()
    flash('Photo deleted.', 'success')
    return redirect(url_for('admin_photos'))


@app.route('/admin/photos/<int:photo_id>/toggle-featured', methods=['POST'])
@login_required
def toggle_featured(photo_id):
    db = get_db()
    photo = db.execute('SELECT featured FROM photos WHERE id=?', (photo_id,)).fetchone()
    if photo:
        db.execute('UPDATE photos SET featured=? WHERE id=?',
                   (0 if photo['featured'] else 1, photo_id))
        db.commit()
    db.close()
    return jsonify({'success': True})

# ─── Admin — Category Management ─────────────────────────────────────────────

@app.route('/admin/categories')
@login_required
def admin_categories():
    db = get_db()
    categories = get_categories()
    cat_counts = {
        key: db.execute('SELECT COUNT(*) as c FROM photos WHERE category=?', (key,)).fetchone()['c']
        for key in categories
    }
    db.close()
    return render_template('admin/categories.html', categories=categories, cat_counts=cat_counts)


@app.route('/admin/categories/add', methods=['POST'])
@login_required
def admin_add_category():
    label = request.form.get('label', '').strip()
    key   = request.form.get('key', '').strip().lower()
    if not label or not key:
        flash('Both a label and a URL key are required.', 'error')
        return redirect(url_for('admin_categories'))
    if not re.match(r'^[a-z0-9_]+$', key):
        flash('URL key must be lowercase letters, numbers, and underscores only.', 'error')
        return redirect(url_for('admin_categories'))
    db = get_db()
    try:
        max_order = db.execute('SELECT MAX(sort_order) as m FROM categories').fetchone()['m'] or 0
        db.execute('INSERT INTO categories (key,label,sort_order) VALUES (?,?,?)',
                   (key, label, max_order + 1))
        db.commit()
        os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], key), exist_ok=True)
        flash(f'Category "{label}" added!', 'success')
    except sqlite3.IntegrityError:
        flash(f'A category with the key "{key}" already exists.', 'error')
    db.close()
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<key>/delete', methods=['POST'])
@login_required
def admin_delete_category(key):
    db = get_db()
    count = db.execute('SELECT COUNT(*) as c FROM photos WHERE category=?', (key,)).fetchone()['c']
    if count > 0:
        flash(f'Cannot delete: {count} photo(s) still belong to this category. '
              'Reassign or delete them first.', 'error')
        db.close()
        return redirect(url_for('admin_categories'))
    db.execute('DELETE FROM subcategories WHERE category_key=?', (key,))
    db.execute('DELETE FROM categories WHERE key=?', (key,))
    db.commit()
    db.close()
    flash('Category deleted.', 'success')
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<key>/add-sub', methods=['POST'])
@login_required
def admin_add_subcategory(key):
    name = request.form.get('name', '').strip()
    if not name:
        flash('Subcategory name cannot be empty.', 'error')
        return redirect(url_for('admin_categories'))
    db = get_db()
    if db.execute('SELECT id FROM subcategories WHERE category_key=? AND name=?',
                  (key, name)).fetchone():
        flash(f'"{name}" already exists in this category.', 'error')
    else:
        db.execute('INSERT INTO subcategories (category_key,name) VALUES (?,?)', (key, name))
        db.commit()
        flash(f'Subcategory "{name}" added.', 'success')
    db.close()
    return redirect(url_for('admin_categories'))


@app.route('/admin/categories/<key>/delete-sub', methods=['POST'])
@login_required
def admin_delete_subcategory(key):
    name = request.form.get('name', '').strip()
    db = get_db()
    db.execute('DELETE FROM subcategories WHERE category_key=? AND name=?', (key, name))
    db.commit()
    db.close()
    flash(f'Subcategory "{name}" removed.', 'success')
    return redirect(url_for('admin_categories'))

# ─── Admin — Bookings ─────────────────────────────────────────────────────────

@app.route('/admin/bookings')
@login_required
def admin_bookings():
    db = get_db()
    bookings = db.execute('SELECT * FROM bookings ORDER BY created_at DESC').fetchall()
    db.execute("UPDATE bookings SET status='read' WHERE status='new'")
    db.commit()
    db.close()
    return render_template('admin/bookings.html', bookings=bookings)


@app.route('/admin/bookings/<int:booking_id>')
@login_required
def admin_booking_detail(booking_id):
    db = get_db()
    booking = db.execute('SELECT * FROM bookings WHERE id=?', (booking_id,)).fetchone()
    if not booking:
        db.close()
        return redirect(url_for('admin_bookings'))
    db.execute("UPDATE bookings SET status='read' WHERE id=?", (booking_id,))
    db.commit()
    db.close()
    return render_template('admin/booking_detail.html', booking=booking)


@app.route('/admin/bookings/<int:booking_id>/delete', methods=['POST'])
@login_required
def admin_delete_booking(booking_id):
    db = get_db()
    db.execute('DELETE FROM bookings WHERE id=?', (booking_id,))
    db.commit()
    db.close()
    flash('Enquiry deleted.', 'success')
    return redirect(url_for('admin_bookings'))

# ─── Admin — Settings ─────────────────────────────────────────────────────────

@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    db = get_db()
    if request.method == 'POST':
        for key in request.form:
            db.execute('UPDATE site_settings SET value=? WHERE key=?', (request.form[key], key))
        db.commit()
        flash('Settings saved!', 'success')
    settings = get_settings()
    db.close()
    return render_template('admin/settings.html', settings=settings)


@app.route('/admin/change-password', methods=['POST'])
@login_required
def change_password():
    db = get_db()
    current = request.form.get('current_password')
    new_pw  = request.form.get('new_password')
    admin   = db.execute('SELECT * FROM admin WHERE username=?',
                         (session['admin_username'],)).fetchone()
    if admin and check_password_hash(admin['password'], current):
        db.execute('UPDATE admin SET password=? WHERE username=?',
                   (generate_password_hash(new_pw), session['admin_username']))
        db.commit()
        flash('Password changed successfully!', 'success')
    else:
        flash('Current password is incorrect.', 'error')
    db.close()
    return redirect(url_for('admin_settings'))


# Initialise DB unconditionally when the module loads.
# This covers: `python app.py`, `flask run`, gunicorn/waitress,
# AND Flask's debug reloader child process (where __name__ != '__main__').
init_db()

if __name__ == '__main__':
    app.run(debug=True, port=5000)