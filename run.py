import os
from app import create_app
from app.models import db, Admin
from apscheduler.schedulers.background import BackgroundScheduler
from app.cron_jobs import revoke_expired_access
from app.drive_sync import sync_drive_files, get_folder_id

app = create_app()

def run_revoke_job():
    """Wrapper to run the job within the app context."""
    with app.app_context():
        print("Running scheduled job: revoke_expired_access")
        revoke_expired_access()

def run_drive_sync_job():
    """Wrapper for the Google Drive sync job."""
    with app.app_context():
        print("Running scheduled job: sync_drive_files")
        folder_id = get_folder_id('Dokumen Bengkel')
        if folder_id:
            sync_drive_files(folder_id)
        else:
            print("Google Drive folder 'Dokumen Bengkel' not found.")

# --- Job Scheduler Setup ---
# DISABLED DURING DOCKER STARTUP - will be managed separately
# if os.environ.get('FLASK_ENV') != 'testing':
scheduler = None  # Will initialize separately if needed
print("\033[93m⏳ Background scheduler disabled during startup (use separate worker)\033[0m")

# --- Secure Admin User Initialization ---
def setup_admin():
    admin_user = os.getenv('ADMIN_USERNAME', 'admin')
    admin_pass = os.getenv('ADMIN_PASSWORD', 'admin123')

    with app.app_context():
        admin = Admin.query.filter_by(username=admin_user).first()

        if not os.getenv('ADMIN_USERNAME') and not os.getenv('ADMIN_PASSWORD'):
            print("\033[93mWARNING: Using default admin credentials. Set ADMIN_USERNAME and ADMIN_PASSWORD environment variables for production.\033[0m")

        if admin:
            print(f"Admin user '{admin_user}' already exists. Updating password.")
            admin.set_password(admin_pass)
        else:
            print(f"Creating new admin user: '{admin_user}'")
            admin = Admin(username=admin_user)
            admin.set_password(admin_pass)
            db.session.add(admin)
        
        db.session.commit()
        print("\033[92mAdmin user is configured.\033[0m")

if __name__ == '__main__':
    with app.app_context():
        setup_admin()
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
