import os
import time
from datetime import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from .models import db, GoogleDriveFolder, GoogleDriveFile, DocumentSyncLog, ChromaDocument
from apscheduler.schedulers.background import BackgroundScheduler
from .documents_handler import ROOT_FOLDERS

# --- Konfigurasi --- #
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# Get credentials path from environment, with fallback
SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

# Try to import Chroma integration
try:
    from .smart_search import ChromaDocumentSearch
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("⚠️  Chroma not available for indexing")


def get_drive_service():
    """Get Google Drive service with credentials from environment"""
    credentials_file = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

    if not os.path.exists(credentials_file):
        raise FileNotFoundError(
            f"Google credentials file not found at: {credentials_file}\n"
            f"Set GOOGLE_CREDENTIALS_PATH environment variable or provide credentials.json"
        )

    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)


def index_document_to_chroma(file_id: str, file_name: str) -> bool:
    """
    Index dokumen ke Chroma vector database

    Args:
        file_id: Google Drive file ID
        file_name: File name

    Returns:
        Success status
    """
    if not CHROMA_AVAILABLE:
        return False

    try:
        search = ChromaDocumentSearch(SERVICE_ACCOUNT_FILE)
        success = search.index_document_from_drive(file_id, file_name)

        if success:
            # Track in database
            chroma_doc = ChromaDocument.query.filter_by(drive_id=file_id).first()
            if not chroma_doc:
                db_file = GoogleDriveFile.query.filter_by(drive_id=file_id).first()
                if db_file:
                    chroma_doc = ChromaDocument(
                        file_id=db_file.id,
                        drive_id=file_id,
                        file_name=file_name,
                        status='indexed'
                    )
                    db.session.add(chroma_doc)
            else:
                chroma_doc.updated_at = datetime.utcnow()
                chroma_doc.status = 'indexed'

            db.session.commit()
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ Error indexing to Chroma: {e}")
        return False


def sync_drive_files(folder_id):
    """Sync Google Drive files dengan batching untuk efficiency"""
    drive_service = get_drive_service()
    start_time = time.time()
    docs_indexed = 0

    # Batch size untuk commits (reduce frequent DB operations)
    BATCH_SIZE = 10

    try:
        # --- Recursive sync function dengan batching --- #
        def _sync_folder(folder_id, parent_id=None, path='/', batch_items=None):
            if batch_items is None:
                batch_items = []

            nonlocal docs_indexed
            folder_count = 0
            file_count = 0

            # --- Get folder details --- #
            folder = drive_service.files().get(fileId=folder_id, fields='id, name').execute()
            folder_name = folder.get('name')
            current_path = os.path.join(path, folder_name)

            # --- Update or create folder in db --- #
            db_folder = GoogleDriveFolder.query.filter_by(drive_id=folder_id).first()
            if not db_folder:
                db_folder = GoogleDriveFolder(
                    drive_id=folder_id,
                    name=folder_name,
                    parent_id=parent_id,
                    path=current_path
                )
                db.session.add(db_folder)
                folder_count += 1
            else:
                db_folder.name = folder_name
                db_folder.path = current_path
                db_folder.last_synced = datetime.utcnow()

            db.session.commit()

            # --- Get all files and folders in the current folder --- #
            query = f"'{folder_id}' in parents"
            results = drive_service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, webViewLink)",
                pageSize=50  # Batch API requests
            ).execute()
            items = results.get('files', [])

            # --- Sync subfolders and files dengan batching --- #
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder':
                    sub_folder_count, sub_file_count = _sync_folder(item['id'], db_folder.id, current_path, batch_items)
                    folder_count += sub_folder_count
                    file_count += sub_file_count
                else:
                    # Check if file is indexable
                    is_indexable = item['mimeType'] in [
                        'application/pdf',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'text/plain'
                    ]

                    db_file = GoogleDriveFile.query.filter_by(drive_id=item['id']).first()
                    if not db_file:
                        db_file = GoogleDriveFile(
                            drive_id=item['id'],
                            name=item['name'],
                            mime_type=item['mimeType'],
                            folder_id=db_folder.id,
                            web_view_link=item.get('webViewLink'),
                            download_link=item.get('webContentLink')
                        )
                        batch_items.append((db_file, is_indexable, item['id'], item['name']))
                        file_count += 1
                    else:
                        db_file.name = item['name']
                        db_file.last_synced = datetime.utcnow()
                        # Re-index if needed
                        if is_indexable:
                            batch_items.append((db_file, True, item['id'], item['name']))

                    # Batch commit setiap BATCH_SIZE items
                    if len(batch_items) >= BATCH_SIZE:
                        _process_batch(batch_items)
                        docs_indexed += len([1 for _, is_ind, _, _ in batch_items if is_ind])
                        batch_items.clear()

            return folder_count, file_count

        # --- Helper function untuk batch indexing --- #
        def _process_batch(batch_items):
            """Process batch items untuk DB dan Chroma"""
            for db_file, is_indexable, file_id, file_name in batch_items:
                try:
                    db.session.add(db_file)
                    db.session.commit()

                    # Index to Chroma if applicable
                    if is_indexable:
                        try:
                            index_document_to_chroma(file_id, file_name)
                        except Exception as e:
                            print(f"⚠️  Could not index {file_name}: {e}")
                except Exception as e:
                    print(f"⚠️  Batch processing error: {e}")

        # --- Start the sync --- #
        total_folders, total_files = _sync_folder(folder_id)

        # --- Log the sync --- #
        sync_log = DocumentSyncLog(
            status='success',
            folder_baru=total_folders,
            file_baru=total_files,
            durasi_detik=time.time() - start_time
        )
        db.session.add(sync_log)
        db.session.commit()

        print(f"✅ Sync completed: {total_folders} folders, {total_files} files, {docs_indexed} indexed")

    except Exception as e:
        sync_log = DocumentSyncLog(
            status='failed',
            error_message=str(e),
            durasi_detik=time.time() - start_time
        )
        db.session.add(sync_log)
        db.session.commit()
        print(f"❌ Error during Google Drive sync: {e}")


def get_folder_id(folder_name):
    drive_service = get_drive_service()
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    return None

def sync_all_folders():
    from . import create_app
    app = create_app()
    with app.app_context():
        for folder_name, folder_id in ROOT_FOLDERS.items():
            print(f"Syncing folder: {folder_name}")
            sync_drive_files(folder_id)

def setup_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(sync_all_folders, 'cron', day_of_week='sun', hour=2)

    # Add cleanup job for old payment proofs - runs every hour
    from .cron_jobs import cleanup_old_payment_proofs
    scheduler.add_job(cleanup_old_payment_proofs, 'interval', hours=1, args=[None])

    return scheduler
