import os
import json
import requests
from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from .models import db, Peserta, Batch, Admin, DocumentAccess, Announcement
from werkzeug.utils import secure_filename
from flask import current_app
import time
import mimetypes
from datetime import datetime
from .security import rate_limit_login, validate_password_strength
from flask_wtf.csrf import generate_csrf
from . import documents_handler

# Helper function
def validate_input_length(value, field_name, max_length=255):
    """Validate input length"""
    value = str(value).strip()
    if len(value) > max_length:
        return False, f"{field_name} terlalu panjang (max {max_length} chars)"
    return True, value

main = Blueprint('main', __name__)

# ============================================================================
# PERMISSION DECORATOR FOR DOCUMENTS
# ============================================================================

def document_access_required(f):
    """
    Decorator to check if a user has permission to access the documents section.
    Handles both web page requests and API (JSON) requests.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('main.login'))

        peserta = Peserta.query.get(session['user_id'])
        if not peserta:
            if request.is_json:
                return jsonify({'error': 'User not found'}), 404
            session.clear()
            return redirect(url_for('main.login'))

        # Centralized access logic
        has_access, access_reason = check_document_access(peserta)

        if not has_access:
            if request.is_json:
                return jsonify({'error': 'Permission denied'}), 403
            flash('Anda tidak memiliki izin akses Dokumen. Hubungi admin untuk mendapatkan akses.', 'warning')
            return redirect(url_for('main.dashboard'))

        # Make peserta and access_reason available to the route
        kwargs['peserta'] = peserta
        kwargs['access_reason'] = access_reason
        return f(*args, **kwargs)
    return decorated_function

def check_document_access(peserta):
    """Central function to check all document access conditions for a Peserta."""
    # 1. Check individual access from DocumentAccess
    individual_access = DocumentAccess.query.filter_by(peserta_id=peserta.id, tipe_akses='individual').first()
    if individual_access and individual_access.is_aktif():
        return True, "Individual"

    # 2. Check group access from DocumentAccess
    if peserta.batch:
        batch = Batch.query.filter_by(nama=peserta.batch).first()
        if batch:
            group_access = DocumentAccess.query.filter_by(batch_id=batch.id, tipe_akses='group').first()
            if group_access and group_access.is_aktif():
                return True, f"Batch: {peserta.batch}"

    # 3. Check legacy field (backward compatibility)
    if peserta.akses_dokumen_bengkel:
        return True, "Legacy"

    # 4. Check workshop access
    if session.get('akses_workshop', False):
        return True, "Workshop"

    return False, ""

# ============================================================================
# CORE ROUTES (Login, Register, Dashboard, etc.)
# ============================================================================

# ... (other routes like landing, login, register, dashboard remain the same) ...
@main.route('/')
def landing():
    return render_template('landing.html')

# === PENDAFTARAN ===
@main.route('/daftar', methods=['GET', 'POST'])
def daftar():
    # Arahkan semua ke route pendaftaran utama `/register` untuk konsistensi
    return redirect(url_for('main.register'))


# === LOGIN USER ===
@main.route('/login', methods=['GET', 'POST'])
@rate_limit_login
def login():
    if request.method == 'POST':
        try:
            wa = request.form.get('whatsapp', '').strip()
            pwd = request.form.get('password', '').strip()

            # Validasi input
            if not wa or not pwd:
                flash('Nomor WhatsApp dan password harus diisi!')
                return render_template('user/login.html')

            # Validasi format WhatsApp
            if len(wa) < 10 or len(wa) > 15 or not wa.isdigit():
                flash('Format nomor WhatsApp tidak valid!')
                return render_template('user/login.html')

            peserta = Peserta.query.filter_by(whatsapp=wa).first()

            if not peserta:
                flash('Nomor WhatsApp tidak ditemukan!')
                return render_template('user/login.html')

            if not peserta.check_password(pwd):
                flash('Password salah!')
                return render_template('user/login.html')

            # Login berhasil
            # Regenerate session after login
            session.clear()  # ✅ Clear old session
            session['user_id'] = peserta.id
            session['nama'] = peserta.nama
            session['akses_workshop'] = peserta.akses_workshop
            return redirect('/dashboard')
        except Exception as e:
            print(f"❌ Error dalam login: {e}")
            flash('Terjadi kesalahan saat login. Silakan coba lagi.')
            return render_template('user/login.html')

    return render_template('user/login.html', csrf_token=generate_csrf())

# === DASHBOARD USER ===
@main.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')

    peserta = Peserta.query.get(session['user_id'])

    # Get announcements for user's batch
    announcements = []
    if peserta.batch:
        batch = Batch.query.filter_by(nama=peserta.batch).first()
        if batch:
            announcements = Announcement.query.filter_by(
                batch_id=batch.id,
                aktif=True
            ).order_by(Announcement.tanggal_dibuat.desc()).all()

    # simple weekly schedule reminder (static for now)
    weekly_schedule = [
        {'day': 'Senin', 'time': '19:00', 'topic': 'Sesi 1'},
        {'day': 'Rabu', 'time': '19:00', 'topic': 'Sesi 2'},
        {'day': 'Jumat', 'time': '19:00', 'topic': 'Sesi 3'},
    ]

    # Kumpulan Referensi: muat langsung di dashboard
    ref_folder_id = documents_handler.ROOT_FOLDERS.get('Referensi')
    reference_items = []
    if ref_folder_id:
        _, reference_items = documents_handler.get_folder_contents(ref_folder_id)
        if reference_items is None:
            reference_items = []

        # Ubah path default agar tampil di dashboard
        for item in reference_items:
            if 'folder_path' not in item:
                item['folder_path'] = 'Kumpulan Referensi'

    categories = ['EBOOKS', 'Pengetahuan', 'Service Manual 1', 'Service Manual 2', 'Referensi']
    return render_template('user/dashboard.html', peserta=peserta, weekly_schedule=weekly_schedule,
                           categories=categories, announcements=announcements,
                           reference_items=reference_items, csrf_token=generate_csrf())


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@main.route('/dashboard/upload-payment', methods=['POST'])
def upload_payment():
    try:
        if 'user_id' not in session:
            return redirect('/login')

        peserta = Peserta.query.get(session['user_id'])
        if not peserta:
            flash('Peserta tidak ditemukan')
            return redirect('/dashboard')

        if 'proof' not in request.files:
            flash('File bukti transfer tidak ditemukan')
            return redirect('/dashboard')

        file = request.files['proof']
        if file.filename == '':
            flash('Nama file kosong')
            return redirect('/dashboard')

        # ✅ Validate MIME type
        if file and allowed_file(file.filename):
            mime_type = file.content_type
            allowed_mimes = ['image/png', 'image/jpeg', 'application/pdf']

            if mime_type not in allowed_mimes:
                flash(f'File type tidak diizinkan: {mime_type}')
                return redirect('/dashboard')

            # ✅ Also check file size (max 5MB)
            file.seek(0, 2)  # Seek to end
            file_size = file.tell()
            file.seek(0)  # Reset to start

            if file_size > 5 * 1024 * 1024:  # 5MB
                flash('File terlalu besar (max 5MB)')
                return redirect('/dashboard')

            # ✅ Ensure upload folder exists
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)

            filename = secure_filename(file.filename)
            timestamp = int(time.time())
            saved_name = f"peserta_{peserta.id}_{timestamp}_{filename}"
            save_path = os.path.join(upload_folder, saved_name)

            # ✅ Validate path (prevent directory traversal)
            if not os.path.abspath(save_path).startswith(os.path.abspath(upload_folder)):
                flash('Path traversal terdeteksi!')
                return redirect('/dashboard')

            file.save(save_path)
            peserta.payment_proof = saved_name
            peserta.status_pembayaran = 'Menunggu'
            db.session.commit()
            flash('Bukti transfer berhasil diunggah. Status: Menunggu verifikasi.')
            return redirect('/dashboard')
        else:
            flash('Format file tidak didukung. Gunakan png/jpg/pdf')
            return redirect('/dashboard')
    except Exception as e:
        print(f"❌ Error dalam upload payment: {e}")
        flash('Terjadi kesalahan saat upload file. Silakan coba lagi.')
        return redirect('/dashboard')


@main.route('/uploads/<filename>')
def download_upload(filename):
    """
    Serve uploaded files (payment proofs, etc)
    """
    try:
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename:
            return jsonify({'error': 'Invalid filename'}), 403

        upload_folder = current_app.config['UPLOAD_FOLDER']
        file_path = os.path.join(upload_folder, filename)

        # Ensure file is within upload folder
        if not os.path.abspath(file_path).startswith(os.path.abspath(upload_folder)):
            return jsonify({'error': 'Access denied'}), 403

        # Check file exists
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        return send_file(file_path, as_attachment=False)
    except Exception as e:
        print(f"❌ Error serving upload: {e}")
        return jsonify({'error': 'Error serving file'}), 500


@main.route('/dashboard/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/login')

    peserta = Peserta.query.get(session['user_id'])
    if request.method == 'POST':
        peserta.nama_bengkel = request.form.get('nama_bengkel', peserta.nama_bengkel)
        peserta.alamat_bengkel = request.form.get('alamat_bengkel', peserta.alamat_bengkel)
        peserta.alamat = request.form.get('alamat', peserta.alamat)
        db.session.commit()
        flash('Profil berhasil diperbarui')
        return redirect('/dashboard')

    return render_template('user/profile.html', peserta=peserta, csrf_token=generate_csrf())


@main.route('/dashboard/change-password', methods=['POST'])
def change_password():
    try:
        if 'user_id' not in session:
            return redirect('/login')

        peserta = Peserta.query.get(session['user_id'])
        if not peserta:
            flash('Peserta tidak ditemukan')
            return redirect('/dashboard')

        current = request.form.get('current_password', '').strip()
        new = request.form.get('new_password', '').strip()
        confirm = request.form.get('confirm_password', '').strip()

        if not current or not new or not confirm:
            flash('Semua field password harus diisi')
            return redirect('/dashboard')

        if not peserta.check_password(current):
            flash('Password saat ini salah')
            return redirect('/dashboard')

        if new != confirm:
            flash('Password baru dan konfirmasi tidak cocok')
            return redirect('/dashboard')

        if len(new) < 6:
            flash('Password minimal 6 karakter')
            return redirect('/dashboard')

        # Validasi password strength
        is_valid, message = validate_password_strength(new)
        if not is_valid:
            flash(f'⚠️ {message}')
            return redirect('/dashboard')

        peserta.set_password(new)
        db.session.commit()
        flash('Password berhasil diubah')
        return redirect('/dashboard')
    except Exception as e:
        print(f"❌ Error dalam change password: {e}")
        flash('Terjadi kesalahan saat mengubah password. Silakan coba lagi.')
        return redirect('/dashboard')

# === WORKSHOP REDIRECT ===
@main.route('/workshop')
def workshop():
    """Redirect ke halaman dokumen - workshop sudah digabung"""
    return redirect('/documents')

# === LOGOUT ===
@main.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# === DOKUMEN BENGKEL (REFACTORED) ===
@main.route('/documents')
@document_access_required
def documents(peserta, access_reason):
    """Main documents page, protected by the central permission decorator."""
    catalog = documents_handler.get_documents_catalog()
    return render_template('user/documents.html',
                         peserta=peserta,
                         catalog=catalog,
                         access_reason=access_reason)


@main.route('/references')
@document_access_required
def references(peserta, access_reason):
    """Dedicated Kumpulan Referensi page with reference items."""
    reference_items = documents_handler.get_reference_items()
    return render_template('user/references.html',
                           peserta=peserta,
                           reference_items=reference_items,
                           access_reason=access_reason)


@main.route('/documents/folder/<folder_id>')
@document_access_required
def documents_folder(peserta, access_reason, folder_id):
    """API endpoint to get folder contents, protected by decorator."""
    folder_name, items = documents_handler.get_folder_contents(folder_id)
    if folder_name is None:
        return jsonify({'error': 'Folder not found'}), 404
    return jsonify({
        'folder_name': folder_name,
        'items': items
    })

@main.route('/documents/search', methods=['GET'])
@document_access_required
def documents_search(peserta, access_reason):
    """API endpoint for searching files, returns JSON."""
    query = request.args.get('q', '').strip()

    if not query or len(query) < 2:
        return jsonify({'search_query': query, 'results': [], 'message': 'Masukkan minimal 2 karakter'})

    results = documents_handler.search_files(query)

    return jsonify({
        'search_query': query,
        'results': results
    })

@main.route('/documents/file/<file_id>')
@document_access_required
def documents_file_info(peserta, access_reason, file_id):
    """Redirects to the actual file view/download link, protected by decorator."""
    file_info = documents_handler.get_file_info(file_id)
    if not file_info:
        flash('File tidak ditemukan')
        return redirect(url_for('main.documents'))

    # Prioritaskan web_view_link untuk pratinjau
    if file_info.get('web_view_link'):
        return redirect(file_info['web_view_link'])
    elif file_info.get('download_link'):
        return redirect(file_info['download_link'])
    else:
        # Fallback jika link tidak ada di database
        drive_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        return redirect(drive_url)


# ============================================================================
# ADMIN ROUTES
# ============================================================================

# ... (all admin routes remain the same) ...
# === ADMIN: LOGIN ===
@main.route('/admin')
def admin_login():
    return render_template('admin/login.html', csrf_token=generate_csrf())

@main.route('/admin/login', methods=['POST'])
@rate_limit_login
def admin_do_login():
    try:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        # Validasi input tidak kosong
        if not username or not password:
            flash('Username dan password harus diisi!')
            return redirect('/admin')

        # Validasi panjang username/password untuk mencegah injection
        if len(username) > 50 or len(password) > 255:
            flash('Username atau password terlalu panjang!')
            return redirect('/admin')

        # Pastikan kita tidak menggunakan object yang di-cache oleh SQLAlchemy
        # (misalnya jika database diubah dari luar proses ini)
        db.session.expire_all()

        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            session.clear()  # Clear session lama
            session['admin'] = True
            session['admin_username'] = username
            return redirect('/admin/dashboard')
        else:
            flash('Login admin gagal! Username atau password salah.')
            return redirect('/admin')
    except Exception as e:
        print(f"❌ Error dalam admin login: {e}")
        flash('Terjadi kesalahan saat login. Silakan coba lagi.')
        return redirect('/admin')

# === ADMIN: DASHBOARD ===
@main.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin')

    total_peserta = Peserta.query.count()
    belum_bayar = Peserta.query.filter_by(status_pembayaran='Belum').count()
    batches = Batch.query.all()

    return render_template('admin/dashboard.html',
                          total_peserta=total_peserta,
                          belum_bayar=belum_bayar,
                          batches=batches)

# === ADMIN: KELOLA PESERTA ===
@main.route('/admin/peserta')
def kelola_peserta():
    if not session.get('admin'):
        return redirect('/admin')

    status = request.args.get('status', 'semua')
    search = request.args.get('search', '').strip()

    # ✅ Validate search input
    if search:
        if len(search) > 100:
            search = search[:100]
            flash('Search terlalu panjang, dipotong 100 karakter')

        # Only allow alphanumeric, spaces, dash, underscore
        if not all(c.isalnum() or c in ' -_' for c in search):
            flash('Search hanya bisa berisi huruf, angka, spasi, dash, underscore')
            search = ''

    # Add pagination
    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = Peserta.query

    # Filter by payment status
    if status == 'belum':
        query = query.filter_by(status_pembayaran='Belum')
    elif status == 'menunggu':
        query = query.filter_by(status_pembayaran='Menunggu')
    elif status == 'lunas':
        query = query.filter_by(status_pembayaran='Lunas')
    elif status == 'ditolak':
        query = query.filter_by(status_pembayaran='Ditolak')

    # Search by name or phone
    if search:
        query = query.filter(
            (Peserta.nama.ilike(f'%{search}%')) |
            (Peserta.whatsapp.ilike(f'%{search}%'))
        )

    peserta_list = query.paginate(page=page, per_page=per_page)
    total = Peserta.query.count()

    return render_template('admin/kelola_peserta.html', peserta=peserta_list.items, pagination=peserta_list, current_page=page, status_filter=status, search=search, total=total, csrf_token=generate_csrf())

@main.route('/admin/peserta/<int:id>')
def peserta_detail(id):
    if not session.get('admin'):
        return redirect('/admin')

    peserta = Peserta.query.get_or_404(id)
    return render_template('admin/peserta_detail.html', peserta=peserta, csrf_token=generate_csrf())

@main.route('/admin/peserta/<int:id>/edit', methods=['GET', 'POST'])
def edit_peserta(id):
    if not session.get('admin'):
        return redirect('/admin')

    peserta = Peserta.query.get_or_404(id)

    if request.method == 'POST':
        peserta.nama = request.form.get('nama', peserta.nama)
        peserta.whatsapp = request.form.get('whatsapp', peserta.whatsapp)
        peserta.email = request.form.get('email', peserta.email)
        peserta.alamat = request.form.get('alamat', peserta.alamat)
        peserta.nama_bengkel = request.form.get('nama_bengkel', peserta.nama_bengkel)
        peserta.alamat_bengkel = request.form.get('alamat_bengkel', peserta.alamat_bengkel)
        peserta.status_pekerjaan = request.form.get('status_pekerjaan', peserta.status_pekerjaan)
        peserta.alasan = request.form.get('alasan', peserta.alasan)
        peserta.batch = request.form.get('batch', peserta.batch)
        peserta.status_pembayaran = request.form.get('status_pembayaran', peserta.status_pembayaran)
        peserta.akses_workshop = 'akses_workshop' in request.form

        db.session.commit()
        flash(f'Data peserta {peserta.nama} berhasil diperbarui!')
        return redirect(f'/admin/peserta/{id}')

    batches = Batch.query.all()
    return render_template('admin/peserta_edit.html', peserta=peserta, batches=batches, csrf_token=generate_csrf())

@main.route('/admin/peserta/<int:id>/toggle-akses', methods=['POST'])
def toggle_akses(id):
    if not session.get('admin'):
        return redirect('/admin')

    peserta = Peserta.query.get_or_404(id)
    peserta.akses_workshop = not peserta.akses_workshop
    db.session.commit()
    flash(f"Akses workshop {peserta.nama} diubah menjadi {'Aktif' if peserta.akses_workshop else 'Tidak Aktif'}")
    return redirect(f'/admin/peserta/{id}')


@main.route('/admin/peserta/<int:id>/toggle-dokumen', methods=['POST'])
def toggle_akses_dokumen(id):
    """Toggle akses Dokumen Bengkel untuk peserta, admin always allowed"""
    try:
        if not session.get('admin'):
            flash('Akses hanya untuk admin!')
            return redirect('/admin')

        peserta = Peserta.query.get_or_404(id)
        peserta.akses_dokumen_bengkel = not peserta.akses_dokumen_bengkel

        if peserta.akses_dokumen_bengkel:
            peserta.tanggal_izin_dokumen = datetime.utcnow()
            status_msg = 'DIBERIKAN'
        else:
            peserta.tanggal_izin_dokumen = None
            status_msg = 'DICABUT'

        db.session.commit()
        flash(f"Akses Dokumen Bengkel {peserta.nama} {status_msg}")
        return redirect(f'/admin/peserta/{id}')
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error toggle akses dokumen: {e}")
        flash('Terjadi error saat mengubah hak akses dokumen.')
        return redirect(f'/admin/peserta/{id}')


@main.route('/admin/dokumen-permission')
def dokumen_permission():
    """Halaman manage akses Dokumen Bengkel untuk semua peserta"""
    if not session.get('admin'):
        return redirect('/admin')

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    filter_akses = request.args.get('filter', 'semua')  # semua, memiliki, tidak

    query = Peserta.query

    # Filter search
    if search:
        query = query.filter(
            (Peserta.nama.ilike(f'%{search}%')) |
            (Peserta.whatsapp.ilike(f'%{search}%')) |
            (Peserta.email.ilike(f'%{search}%'))
        )

    # Filter akses
    if filter_akses == 'memiliki':
        query = query.filter_by(akses_dokumen_bengkel=True)
    elif filter_akses == 'tidak':
        query = query.filter_by(akses_dokumen_bengkel=False)

    # Pagination
    peserta_list = query.order_by(Peserta.tanggal_daftar.desc()).paginate(page=page, per_page=50)

    return render_template('admin/dokumen_permission.html',
                         peserta_list=peserta_list,
                         search=search,
                         filter_akses=filter_akses,
                         total_peserta=Peserta.query.count(),
                         peserta_dengan_akses=Peserta.query.filter_by(akses_dokumen_bengkel=True).count(),
                         peserta_tanpa_akses=Peserta.query.filter_by(akses_dokumen_bengkel=False).count())

@main.route('/admin/peserta/<int:id>/hapus', methods=['POST'])
def hapus_peserta(id):
    if not session.get('admin'):
        return redirect('/admin')

    peserta = Peserta.query.get_or_404(id)
    nama = peserta.nama
    db.session.delete(peserta)
    db.session.commit()
    flash(f'Peserta {nama} berhasil dihapus!')
    return redirect('/admin/peserta')


# === ADMIN: GRUP DIKLAT (rename dari batch) ===
@main.route('/admin/grup')
def kelola_grup():
    if not session.get('admin'):
        return redirect('/admin')
    grups = Batch.query.all()
    return render_template('admin/grup_list.html', grups=grups, csrf_token=generate_csrf())


@main.route('/admin/grup/<int:id>/toggle-akses', methods=['POST'])
def toggle_akses_grup(id):
    try:
        if not session.get('admin'):
            flash('Akses hanya untuk admin!')
            return redirect('/admin')
        grup = Batch.query.get_or_404(id)
        grup.akses_workshop_default = not grup.akses_workshop_default
        db.session.commit()
        # Apply group access setting to all peserta in this grup
        peserta_list = Peserta.query.filter_by(batch=grup.nama).all()
        for p in peserta_list:
            p.akses_workshop = grup.akses_workshop_default
        db.session.commit()
        flash(f"Akses workshop untuk grup '{grup.nama}' diubah menjadi {'Aktif' if grup.akses_workshop_default else 'Non-Aktif'} dan diterapkan ke peserta grup.")
        return redirect('/admin/dashboard')
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error toggle akses grup: {e}")
        flash('Terjadi error saat mengubah hak akses grup.')
        return redirect('/admin/dashboard')

# === ADMIN: VERIFIKASI PEMBAYARAN ===
@main.route('/admin/pembayaran')
def verifikasi_pembayaran():
    if not session.get('admin'):
        return redirect('/admin')

    status = request.args.get('status', 'menunggu')

    query = Peserta.query
    if status == 'menunggu':
        query = query.filter_by(status_pembayaran='Menunggu')
    elif status == 'lunas':
        query = query.filter_by(status_pembayaran='Lunas')
    elif status == 'ditolak':
        query = query.filter_by(status_pembayaran='Ditolak')
    else:
        query = query.filter(Peserta.status_pembayaran.in_(['Menunggu', 'Lunas', 'Ditolak']))

    peserta_list = query.all()
    return render_template('admin/verifikasi_pembayaran.html', peserta=peserta_list, status_filter=status, csrf_token=generate_csrf())

@main.route('/admin/peserta/<int:id>/verifikasi', methods=['POST'])
def verifikasi_status(id):
    if not session.get('admin'):
        return redirect('/admin')

    peserta = Peserta.query.get_or_404(id)
    status = request.form.get('status', 'Menunggu')

    if status in ['Belum', 'Menunggu', 'Lunas', 'Ditolak']:
        peserta.status_pembayaran = status
        # Track verification timestamp for auto-cleanup
        if status in ['Lunas', 'Ditolak']:
            peserta.tanggal_verifikasi_pembayaran = datetime.utcnow()
        db.session.commit()

        # Send notification with photo to Telegram
        from app.notification_manager import NotificationManager
        import os

        photo_path = None
        if peserta.payment_proof:
            # Construct full path to payment proof
            upload_folder = current_app.config['UPLOAD_FOLDER']
            photo_path = os.path.join(upload_folder, peserta.payment_proof)

        # Send notification with photo
        NotificationManager.notify_payment_verification_with_photo(
            peserta_data={
                'id': peserta.id,
                'nama': peserta.nama,
                'whatsapp': peserta.whatsapp,
                'batch': peserta.batch
            },
            status=status,
            photo_path=photo_path
        )

        flash(f'Status pembayaran {peserta.nama} diubah menjadi {status}. Notifikasi telah dikirim ke Telegram.')
    else:
        flash('Status tidak valid!')

    return redirect('/admin/pembayaran')

# === ADMIN: BUAT GRUP DIKLAT BARU ===
@main.route('/admin/grup/buat', methods=['GET', 'POST'])
def buat_grup():
    if not session.get('admin'):
        return redirect('/admin')

    if request.method == 'POST':
        batch = Batch(
            nama=request.form['nama'],
            whatsapp_link=request.form['whatsapp_link'],
            akses_workshop_default='akses_workshop' in request.form
        )
        db.session.add(batch)
        db.session.commit()
        flash('Grup diklat baru berhasil dibuat!')
        return redirect('/admin/grup')

    return render_template('admin/buat_batch.html', csrf_token=generate_csrf())

# === ADMIN: LOGOUT ===
@main.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')
@main.route('/register', methods=['GET', 'POST'])
def register():
    # CSRF disabled for testing
    if request.method == 'POST':
        # Ambil data
        nama = request.form.get('nama', '').strip()
        wa = request.form.get('whatsapp', '').strip()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        nama_bengkel = request.form.get('nama_bengkel', '').strip()
        alamat_bengkel = request.form.get('alamat_bengkel', '').strip()
        status = request.form.get('status_pekerjaan', '')
        alamat = request.form.get('alamat', '').strip()
        alasan = request.form.get('alasan', '').strip()

        # Persiapkan data untuk form (jika ada error)
        form_data = {
            'nama': nama,
            'whatsapp': wa,
            'nama_bengkel': nama_bengkel,
            'alamat_bengkel': alamat_bengkel,
            'status_pekerjaan': status,
            'alamat': alamat,
            'alasan': alasan,
            'csrf_token': generate_csrf()
        }

        # Validate inputs
        is_valid, nama = validate_input_length(nama, 'Nama', 100)
        if not is_valid:
            flash(is_valid)  # Error message
            return render_template('user/register.html', **form_data)

        # Validasi
        if password != confirm:
            flash('Password dan konfirmasi tidak cocok!')
            return render_template('user/register.html', **form_data)

        is_valid, message = validate_password_strength(password)
        if not is_valid:
            flash(f'⚠️ {message}')
            return render_template('user/register.html', **form_data)

        if Peserta.query.filter_by(whatsapp=wa).first():
            flash('Nomor WhatsApp sudah terdaftar!')
            return render_template('user/register.html', **form_data)

        # Buat & simpan peserta
        peserta = Peserta(
            nama=nama,
            whatsapp=wa,
            alamat=alamat,
            nama_bengkel=nama_bengkel,
            alamat_bengkel=alamat_bengkel,
            status_pekerjaan=status,
            alasan=alasan,
            batch="Menunggu Verifikasi"
        )
        peserta.set_password(password)

        db.session.add(peserta)
        db.session.commit()  # 🔥 INI KUNCI — JANGAN LUPA!

        flash('Pendaftaran berhasil! Silakan login.')
        return redirect('/login')

    return render_template('user/register.html', csrf_token=generate_csrf())

# ============================================================================
# DOCUMENT ACCESS MANAGEMENT (Admin)
# ============================================================================

@main.route('/admin/dokumen')
def admin_dokumen():
    """Halaman utama untuk manage akses Dokumen Bengkel"""
    if 'admin' not in session:
        return redirect(url_for('main.admin_login'))

    from .models import DocumentAccess, DocumentSyncLog, Batch

    # Get document access statistics
    total_akses = DocumentAccess.query.count()
    akses_group = DocumentAccess.query.filter_by(tipe_akses='group').count()
    akses_individual = DocumentAccess.query.filter_by(tipe_akses='individual').count()

    # Get latest sync log
    latest_sync = DocumentSyncLog.query.order_by(DocumentSyncLog.tanggal_sync.desc()).first()

    # Get batches for dropdown
    batches = Batch.query.filter_by(aktif=True).all()

    return render_template(
        'admin/dokumen_management.html',
        total_akses=total_akses,
        akses_group=akses_group,
        akses_individual=akses_individual,
        latest_sync=latest_sync,
        batches=batches
    )


@main.route('/admin/dokumen/batch-access')
def admin_dokumen_batch():
    """Halaman manage akses dokumen per Batch/Grup"""
    if 'admin' not in session:
        return redirect(url_for('main.admin_login'))

    from .models import DocumentAccess, Batch

    batches = Batch.query.filter_by(aktif=True).all()
    batch_accesses = DocumentAccess.query.filter_by(tipe_akses='group').all()

    # Create dict untuk mapping batch -> access
    batch_access_dict = {ba.batch_id: ba for ba in batch_accesses}

    return render_template(
        'admin/dokumen_batch_access.html',
        batches=batches,
        batch_access_dict=batch_access_dict
    )


@main.route('/admin/dokumen/grant-batch', methods=['POST'])
def admin_grant_batch_access():
    """Grant akses dokumen untuk seluruh batch/grup"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    from .models import DocumentAccess, Batch
    from datetime import datetime, timedelta

    batch_id = request.json.get('batch_id')
    grant = request.json.get('grant', True)
    tanggal_kadaluarsa = request.json.get('tanggal_kadaluarsa')
    catatan = request.json.get('catatan', '')

    try:
        batch = Batch.query.get(batch_id)
        if not batch:
            return jsonify({'error': 'Batch tidak ditemukan'}), 404

        # Cek apakah sudah ada
        existing = DocumentAccess.query.filter_by(
            batch_id=batch_id,
            tipe_akses='group'
        ).first()

        if existing:
            # Update existing
            existing.akses_diberikan = grant
            existing.tanggal_kadaluarsa = datetime.fromisoformat(tanggal_kadaluarsa) if tanggal_kadaluarsa else None
            existing.catatan = catatan
            existing.tanggal_diubah = datetime.utcnow()
        else:
            # Create new
            access = DocumentAccess(
                tipe_akses='group',
                batch_id=batch_id,
                akses_diberikan=grant,
                tanggal_kadaluarsa=datetime.fromisoformat(tanggal_kadaluarsa) if tanggal_kadaluarsa else None,
                catatan=catatan,
                dibuat_oleh=session.get('admin', 'unknown')
            )
            db.session.add(access)

        db.session.commit()

        peserta_count = Peserta.query.filter_by(batch=batch.nama).count()

        return jsonify({
            'success': True,
            'message': f'Akses {"diberikan" if grant else "dicabut"} untuk {peserta_count} peserta di batch {batch.nama}',
            'peserta_affected': peserta_count
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/admin/dokumen/individual-access')
def admin_dokumen_individual():
    """Halaman manage akses dokumen per Peserta"""
    if 'admin' not in session:
        return redirect(url_for('main.admin_login'))

    from .models import DocumentAccess

    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '', type=str)

    # Base query
    query = Peserta.query

    if search:
        query = query.filter(
            (Peserta.nama.ilike(f'%{search}%')) |
            (Peserta.whatsapp.ilike(f'%{search}%'))
        )

    peserta = query.paginate(page=page, per_page=50)

    # Get document access untuk semua peserta
    individual_accesses = DocumentAccess.query.filter_by(tipe_akses='individual').all()
    access_dict = {ba.peserta_id: ba for ba in individual_accesses}

    return render_template(
        'admin/dokumen_individual_access.html',
        peserta=peserta,
        access_dict=access_dict,
        search=search
    )


@main.route('/admin/dokumen/grant-individual', methods=['POST'])
def admin_grant_individual_access():
    """Grant akses dokumen untuk peserta individual"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    from .models import DocumentAccess
    from datetime import datetime

    peserta_id = request.json.get('peserta_id')
    grant = request.json.get('grant', True)
    tanggal_kadaluarsa = request.json.get('tanggal_kadaluarsa')
    catatan = request.json.get('catatan', '')

    try:
        peserta = Peserta.query.get(peserta_id)
        if not peserta:
            return jsonify({'error': 'Peserta tidak ditemukan'}), 404

        # Cek apakah sudah ada
        existing = DocumentAccess.query.filter_by(
            peserta_id=peserta_id,
            tipe_akses='individual'
        ).first()

        if existing:
            # Update existing
            existing.akses_diberikan = grant
            existing.tanggal_kadaluarsa = datetime.fromisoformat(tanggal_kadaluarsa) if tanggal_kadaluarsa else None
            existing.catatan = catatan
            existing.tanggal_diubah = datetime.utcnow()
        else:
            # Create new
            access = DocumentAccess(
                tipe_akses='individual',
                peserta_id=peserta_id,
                akses_diberikan=grant,
                tanggal_kadaluarsa=datetime.fromisoformat(tanggal_kadaluarsa) if tanggal_kadaluarsa else None,
                catatan=catatan,
                dibuat_oleh=session.get('admin', 'unknown')
            )
            db.session.add(access)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Akses {"diberikan" if grant else "dicabut"} untuk {peserta.nama}',
            'peserta_name': peserta.nama
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@main.route('/admin/dokumen/sync-status')
def admin_sync_status():
    """Get status sinkronisasi Google Drive"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    from .models import DocumentSyncLog

    # Get last 10 sync logs
    logs = DocumentSyncLog.query.order_by(DocumentSyncLog.tanggal_sync.desc()).limit(10).all()

    return jsonify({
        'logs': [{
            'id': log.id,
            'tanggal': log.tanggal_sync.isoformat(),
            'status': log.status,
            'folder_baru': log.folder_baru,
            'file_baru': log.file_baru,
            'durasi': log.durasi_detik,
            'error': log.error_message
        } for log in logs]
    })


@main.route('/admin/dokumen/manual-sync', methods=['POST'])
def admin_manual_sync():
    """Trigger manual sync untuk Google Drive"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from .drive_sync import sync_google_drive_documents
        from threading import Thread

        # Run sync di background thread
        thread = Thread(target=sync_google_drive_documents)
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Sinkronisasi dimulai... Silakan cek status dalam beberapa menit'
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ANNOUNCEMENT ROUTES (ADMIN & USER)
# ============================================================================

@main.route('/admin/announcements', methods=['GET'])
def admin_announcements():
    """Daftar semua pengumuman dengan filter batch"""
    if 'admin' not in session:
        return redirect('/admin')

    batch_filter = request.args.get('batch', '')

    query = Announcement.query
    if batch_filter:
        batch = Batch.query.filter_by(nama=batch_filter).first()
        if batch:
            query = query.filter_by(batch_id=batch.id)

    announcements = query.order_by(Announcement.tanggal_dibuat.desc()).all()
    batches = Batch.query.filter_by(aktif=True).all()

    return render_template('admin/pengumuman_list.html',
                         announcements=announcements,
                         batches=batches,
                         selected_batch=batch_filter,
                         csrf_token=generate_csrf())


@main.route('/admin/announcements/create', methods=['GET', 'POST'])
def admin_create_announcement():
    """Buat pengumuman baru"""
    if 'admin' not in session:
        return redirect('/admin')

    if request.method == 'POST':
        try:
            judul = request.form.get('judul', '').strip()
            isi = request.form.get('isi', '').strip()
            batch_id = request.form.get('batch_id')

            if not judul or len(judul) > 255:
                flash('Judul harus diisi dan maksimal 255 karakter')
                return redirect(url_for('admin_create_announcement'))

            if not isi or len(isi) > 5000:
                flash('Isi harus diisi dan maksimal 5000 karakter')
                return redirect(url_for('admin_create_announcement'))

            announcement = Announcement(
                judul=judul,
                isi=isi,
                batch_id=int(batch_id) if batch_id else None,
                dibuat_oleh=session.get('admin', 'unknown'),
                aktif=True
            )

            db.session.add(announcement)
            db.session.commit()

            flash('Pengumuman berhasil dibuat')
            return redirect(url_for('admin_announcements'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}')
            return redirect(url_for('admin_create_announcement'))

    batches = Batch.query.filter_by(aktif=True).all()
    return render_template('admin/pengumuman_create.html',
                         batches=batches,
                         csrf_token=generate_csrf())


@main.route('/admin/announcements/<int:id>/edit', methods=['GET', 'POST'])
def admin_edit_announcement(id):
    """Edit pengumuman"""
    if 'admin' not in session:
        return redirect('/admin')

    announcement = Announcement.query.get(id)
    if not announcement:
        flash('Pengumuman tidak ditemukan')
        return redirect(url_for('admin_announcements'))

    if request.method == 'POST':
        try:
            judul = request.form.get('judul', '').strip()
            isi = request.form.get('isi', '').strip()
            batch_id = request.form.get('batch_id')
            aktif = request.form.get('aktif') == 'on'

            if not judul or len(judul) > 255:
                flash('Judul harus diisi dan maksimal 255 karakter')
                return redirect(url_for('admin_edit_announcement', id=id))

            if not isi or len(isi) > 5000:
                flash('Isi harus diisi dan maksimal 5000 karakter')
                return redirect(url_for('admin_edit_announcement', id=id))

            announcement.judul = judul
            announcement.isi = isi
            announcement.batch_id = int(batch_id) if batch_id else None
            announcement.aktif = aktif
            announcement.tanggal_diubah = datetime.utcnow()

            db.session.commit()

            flash('Pengumuman berhasil diperbarui')
            return redirect(url_for('admin_announcements'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}')
            return redirect(url_for('admin_edit_announcement', id=id))

    batches = Batch.query.filter_by(aktif=True).all()
    return render_template('admin/pengumuman_edit.html',
                         announcement=announcement,
                         batches=batches,
                         csrf_token=generate_csrf())


@main.route('/admin/announcements/<int:id>/delete', methods=['POST'])
def admin_delete_announcement(id):
    """Hapus pengumuman"""
    if 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        announcement = Announcement.query.get(id)
        if not announcement:
            return jsonify({'error': 'Pengumuman tidak ditemukan'}), 404

        db.session.delete(announcement)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Pengumuman berhasil dihapus'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
