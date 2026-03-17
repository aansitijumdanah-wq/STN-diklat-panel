"""
Handler for Workshop Documents - Integrated with the main Flask app
"""

from .models import db, GoogleDriveFolder, GoogleDriveFile

# --- Root Folder Configuration --- #
# These are the specific Google Drive folder IDs for the main categories
ROOT_FOLDERS = {
    "EBOOKS": "12ffd7GqHAiy3J62Vu65LbVt6-ultog5Z",
    "Pengetahuan": "1Y2SLCbyHoB53BaQTTwRta2T6dv_drRll",
    "Service_Manual_1": "1CHz8UWZXfJtXlcjp9-FPAo-t_KkfTztW",
    "Service_Manual_2": "1_SsZ7SkaZxvXUZ6RUAA_o7WR_GAtgEwT",
    "Referensi": "19jcIVXJt5lFShQOYGcwBjmhZSPNo0EE-"
}

DISPLAY_NAMES = {
    "EBOOKS": "📚 EBOOKS",
    "Pengetahuan": "🧠 Pengetahuan",
    "Service_Manual_1": "🔧 Service Manual (1)",
    "Service_Manual_2": "⚙️ Service Manual (2)",
    "Referensi": "📘 Kumpulan Referensi"
}

def _get_folder_structure_recursively(folder):
    """
    Helper function to recursively build a hierarchical structure of folders and files.
    Now handles dynamic query objects from lazy='dynamic'.
    """
    if not folder:
        return None

    subfolders = []
    # Execute the query to get subfolders, and sort them
    sorted_subfolders = folder.subfolders.order_by(GoogleDriveFolder.name).all()
    for subfolder in sorted_subfolders:
        subfolders.append(_get_folder_structure_recursively(subfolder))

    files = []
    # Execute the query to get files, and sort them
    sorted_files = folder.files.order_by(GoogleDriveFile.name).all()
    for file in sorted_files:
        files.append({
            'name': file.name,
            'file_id': file.drive_id,
            'mime_type': file.mime_type,
            'web_view_link': file.web_view_link,
            'download_link': file.download_link
        })

    return {
        'name': folder.name,
        'folder_id': folder.drive_id,
        'path': folder.path,
        'subfolders': subfolders,
        'files': files
    }

def get_documents_catalog():
    """
    Generate a full document catalog from the database with a hierarchical folder structure.
    """
    catalog = {}
    for key, folder_id in ROOT_FOLDERS.items():
        display_name = DISPLAY_NAMES.get(key, key)
        root_folder_obj = GoogleDriveFolder.query.filter_by(drive_id=folder_id).first()

        if root_folder_obj:
            catalog[display_name] = _get_folder_structure_recursively(root_folder_obj)

    return catalog

def get_root_list():
    """Get the list of root folders with file counts from the database."""
    root_list = []
    for key, folder_id in ROOT_FOLDERS.items():
        folder = GoogleDriveFolder.query.filter_by(drive_id=folder_id).first()
        if folder:
            # Execute the query to get the count
            count = folder.files.count()
            name = DISPLAY_NAMES.get(key, key)
            root_list.append({
                'name': name,
                'folder_id': folder.drive_id,
                'count': count,
                'key': key
            })
    return root_list

def get_folder_contents(folder_id):
    """Get the contents of a folder by its Google Drive ID."""
    folder = GoogleDriveFolder.query.filter_by(drive_id=folder_id).first()
    if not folder:
        return None, None

    items_list = []
    # Execute the query for subfolders
    for subfolder in folder.subfolders.order_by(GoogleDriveFolder.name).all():
        items_list.append({
            'id': subfolder.drive_id,
            'name': subfolder.name,
            'is_directory': True,
            'file_id': subfolder.drive_id
        })

    # Execute the query for files
    for file in folder.files.order_by(GoogleDriveFile.name).all():
        items_list.append({
            'id': file.drive_id,
            'name': file.name,
            'is_directory': False,
            'mime_type': file.mime_type,
            'file_id': file.drive_id,
            'web_view_link': file.web_view_link
        })

    return folder.name, items_list

def get_file_info(file_id):
    """Get file information by its Google Drive ID."""
    file = GoogleDriveFile.query.filter_by(drive_id=file_id).first()
    if not file:
        return None

    return {
        'id': file.drive_id,
        'name': file.name,
        'mime_type': file.mime_type,
        'folder_id': file.folder.drive_id if file.folder else None,
        'web_view_link': file.web_view_link,
        'download_link': file.download_link
    }

def get_reference_items():
    """Get all files from the reference folder (Kumpulan Referensi)."""
    folder_id = ROOT_FOLDERS.get('Referensi', '19jcIVXJt5lFShQOYGcwBjmhZSPNo0EE-')
    folder = GoogleDriveFolder.query.filter_by(drive_id=folder_id).first()

    if not folder:
        return []

    items_list = []
    # Get all files from reference folder, ordered by name
    for file in folder.files.order_by(GoogleDriveFile.name).all():
        items_list.append({
            'id': file.drive_id,
            'name': file.name,
            'mime_type': file.mime_type,
            'folder_path': folder.name,
            'file_id': file.drive_id,
            'web_view_link': file.web_view_link
        })

    return items_list

def search_files(query):
    """Search for files in the database based on a query string."""
    if not query or len(query.strip()) < 2:
        return []

    search_query = f"%{query}%"
    results = GoogleDriveFile.query.filter(GoogleDriveFile.name.ilike(search_query)).limit(50).all()

    results_list = []
    for r in results:
        results_list.append({
            'id': r.drive_id,
            'name': r.name,
            'is_directory': False,
            'mime_type': r.mime_type,
            'folder_path': r.folder.path if r.folder else '/'
        })

    return results_list
