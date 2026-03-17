"""
Admin routes untuk manage Chroma Vector Database indexing
"""

from flask import Blueprint, request, jsonify
from functools import wraps
from datetime import datetime
from .models import db, GoogleDriveFile, ChromaDocument
from .smart_search import ChromaDocumentSearch
import os

admin_chroma = Blueprint('admin_chroma', __name__, url_prefix='/api/admin/chroma')

# Admin authentication
def require_admin(f):
    """Decorator untuk memastikan admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-Admin-Key')
        expected_key = os.getenv('ADMIN_API_KEY', 'admin-key-change-me')
        
        if api_key != expected_key:
            return jsonify({'error': 'Unauthorized'}), 401
        
        return f(*args, **kwargs)
    return decorated_function


@admin_chroma.route('/stats', methods=['GET'])
@require_admin
def get_chroma_stats():
    """Get Chroma vector database statistics"""
    try:
        credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        search = ChromaDocumentSearch(credentials_path)
        stats = search.get_stats()
        
        # Get database tracking
        indexed_count = ChromaDocument.query.filter_by(status='indexed').count()
        pending_count = ChromaDocument.query.filter_by(status='pending').count()
        failed_count = ChromaDocument.query.filter_by(status='failed').count()
        
        return jsonify({
            'success': True,
            'vector_store_stats': stats,
            'database_tracking': {
                'total_indexed': indexed_count,
                'total_pending': pending_count,
                'total_failed': failed_count
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_chroma.route('/index-all', methods=['POST'])
@require_admin
def index_all_documents():
    """Index all Google Drive documents to Chroma (heavy operation)"""
    try:
        credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        search = ChromaDocumentSearch(credentials_path)
        
        # Get all supported file types
        supported_types = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain'
        ]
        
        files = GoogleDriveFile.query.filter(
            GoogleDriveFile.mime_type.in_(supported_types)
        ).all()
        
        indexed = 0
        failed = 0
        
        for file_obj in files:
            try:
                # Index to Chroma
                success = search.index_document_from_drive(file_obj.drive_id, file_obj.name)
                
                # Track in database
                if success:
                    chroma_doc = ChromaDocument.query.filter_by(drive_id=file_obj.drive_id).first()
                    if not chroma_doc:
                        chroma_doc = ChromaDocument(
                            file_id=file_obj.id,
                            drive_id=file_obj.drive_id,
                            file_name=file_obj.name,
                            status='indexed'
                        )
                        db.session.add(chroma_doc)
                    else:
                        chroma_doc.status = 'indexed'
                        chroma_doc.updated_at = datetime.utcnow()
                    
                    db.session.commit()
                    indexed += 1
                else:
                    failed += 1
            except Exception as e:
                print(f"Error indexing {file_obj.name}: {e}")
                failed += 1
        
        return jsonify({
            'success': True,
            'message': f'Indexed {indexed} documents, {failed} failed'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_chroma.route('/index-file/<file_id>', methods=['POST'])
@require_admin
def index_single_file(file_id):
    """Index single file to Chroma"""
    try:
        file_obj = GoogleDriveFile.query.get(file_id)
        
        if not file_obj:
            return jsonify({'error': 'File not found'}), 404
        
        credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        search = ChromaDocumentSearch(credentials_path)
        
        success = search.index_document_from_drive(file_obj.drive_id, file_obj.name)
        
        if success:
            chroma_doc = ChromaDocument.query.filter_by(drive_id=file_obj.drive_id).first()
            if not chroma_doc:
                chroma_doc = ChromaDocument(
                    file_id=file_obj.id,
                    drive_id=file_obj.drive_id,
                    file_name=file_obj.name,
                    status='indexed'
                )
                db.session.add(chroma_doc)
            else:
                chroma_doc.status = 'indexed'
                chroma_doc.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Successfully indexed {file_obj.name}'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to index {file_obj.name}'
            }), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_chroma.route('/delete-file/<file_id>', methods=['DELETE'])
@require_admin
def delete_file_from_chroma(file_id):
    """Delete file from Chroma"""
    try:
        file_obj = GoogleDriveFile.query.get(file_id)
        
        if not file_obj:
            return jsonify({'error': 'File not found'}), 404
        
        credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        search = ChromaDocumentSearch(credentials_path)
        
        success = search.delete_document(file_obj.drive_id)
        
        if success:
            chroma_doc = ChromaDocument.query.filter_by(drive_id=file_obj.drive_id).first()
            if chroma_doc:
                db.session.delete(chroma_doc)
                db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Deleted {file_obj.name} from Chroma'
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Failed to delete {file_obj.name}'
            }), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@admin_chroma.route('/list-indexed', methods=['GET'])
@require_admin
def list_indexed_documents():
    """List all indexed documents"""
    try:
        documents = ChromaDocument.query.all()
        
        docs_list = [
            {
                'id': doc.id,
                'file_name': doc.file_name,
                'drive_id': doc.drive_id,
                'chunk_count': doc.chunk_count,
                'status': doc.status,
                'indexed_at': doc.indexed_at.isoformat(),
                'updated_at': doc.updated_at.isoformat()
            }
            for doc in documents
        ]
        
        return jsonify({
            'success': True,
            'total': len(docs_list),
            'documents': docs_list
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def register_admin_chroma_routes(app):
    """Register admin Chroma routes"""
    app.register_blueprint(admin_chroma)
    print("✅ Admin Chroma routes registered")
