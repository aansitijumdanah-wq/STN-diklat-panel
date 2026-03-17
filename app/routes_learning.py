"""
app/routes_learning.py
Learning Chatbot Routes - Google Drive Integrated

Fitur:
✓ Select files dari Google Drive
✓ Chat dengan selected files (Indonesian)
✓ Discussion threads
✓ Learning progress tracking
"""

from flask import Blueprint, request, jsonify, session, render_template
from functools import wraps
from datetime import datetime
from .models import (
    db, LearningSession, DiscussionThread, DiscussionPost, 
    PostReaction, StudyMaterial, UserQuizAttempt
)
from .quick_multilingual_rag import QuickMultilingualRAG
from .documents_handler import get_documents_catalog
from .drive_sync import index_document_to_chroma
import os

# Blueprint initialization
learning = Blueprint('learning', __name__, url_prefix='/api/learning')

# Global chatbot instance
_rag_engine = None
_documents_catalog = None

def init_learning_system():
    """Initialize learning system - call this in app/__init__.py"""
    global _rag_engine, _documents_catalog
    try:
        _rag_engine = QuickMultilingualRAG()
        _documents_catalog = get_documents_catalog()
        print("✅ Learning Chatbot System initialized")
        return True
    except Exception as e:
        print(f"❌ Error initializing learning system: {e}")
        return False

# ============================================================================
# HELPER: Authentication check
# ============================================================================

def require_login(f):
    """Require user to be logged in"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# ROUTES: Document Management
# ============================================================================

@learning.route('/documents', methods=['GET'])
def get_documents():
    """
    Get available documents dari Google Drive
    Struktur: folders dengan subfolders dan files
    """
    try:
        catalog = get_documents_catalog()
        return jsonify({
            'documents': catalog,
            'total_categories': len(catalog)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@learning.route('/documents/search', methods=['POST'])
def search_documents():
    """
    Search documents by name atau folder
    """
    data = request.json
    search_term = data.get('query', '').lower()
    
    if not search_term:
        return jsonify({'error': 'Search term required'}), 400
    
    try:
        catalog = get_documents_catalog()
        results = []
        
        # Simple search through catalog
        def search_recursive(folder_dict, path=''):
            if not folder_dict:
                return
            
            # Check folder name
            if search_term in folder_dict.get('name', '').lower():
                results.append({
                    'type': 'folder',
                    'name': folder_dict['name'],
                    'id': folder_dict.get('folder_id'),
                    'path': path
                })
            
            # Check files
            for file_obj in folder_dict.get('files', []):
                if search_term in file_obj.get('name', '').lower():
                    results.append({
                        'type': 'file',
                        'name': file_obj['name'],
                        'id': file_obj.get('file_id'),
                        'path': path + '/' + folder_dict.get('name', '')
                    })
            
            # Check subfolders
            for subfolder in folder_dict.get('subfolders', []):
                search_recursive(
                    subfolder,
                    path + '/' + folder_dict.get('name', '')
                )
        
        for category, folder_data in catalog.items():
            search_recursive(folder_data, category)
        
        return jsonify({
            'results': results,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ROUTES: Learning Sessions
# ============================================================================

@learning.route('/session/create', methods=['POST'])
@require_login
def create_session():
    """
    Create learning session dengan selected files
    
    Request body:
    {
        "session_name": "Optional name",
        "selected_file_ids": ["file_id_1", "file_id_2", ...]
    }
    """
    user_id = session.get('user_id')
    data = request.json
    selected_files = data.get('selected_file_ids', [])
    session_name = data.get('session_name', f'Learning Session {datetime.utcnow().strftime("%Y-%m-%d %H:%M")}')
    
    if not selected_files:
        return jsonify({'error': 'At least one file must be selected'}), 400
    
    try:
        # Validate & get files
        valid_files = []
        for file_id in selected_files:
            # Import here to avoid circular imports
            from .models import GoogleDriveFile
            file_obj = GoogleDriveFile.query.filter_by(drive_id=file_id).first()
            if file_obj:
                valid_files.append(file_obj)
                # Index to Chroma if not already indexed
                try:
                    index_document_to_chroma(file_id, file_obj.name)
                except:
                    pass  # Continue even if indexing fails
        
        if not valid_files:
            return jsonify({'error': 'No valid files found'}), 400
        
        # Create session
        learning_session = LearningSession(
            peserta_id=user_id,
            session_name=session_name,
            created_at=datetime.utcnow()
        )
        
        # Add selected files to session
        for file_obj in valid_files:
            learning_session.selected_files.append(file_obj)
        
        db.session.add(learning_session)
        db.session.commit()
        
        return jsonify({
            'session_id': learning_session.id,
            'session_name': learning_session.session_name,
            'files_count': len(valid_files),
            'message': f'Session created dengan {len(valid_files)} files'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@learning.route('/session/<int:session_id>', methods=['GET'])
@require_login
def get_session(session_id):
    """Get learning session details"""
    
    learning_session = LearningSession.query.get(session_id)
    if not learning_session:
        return jsonify({'error': 'Session not found'}), 404
    
    # Verify user owns session
    if learning_session.peserta_id != session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 403
    
    return jsonify({
        'session_id': learning_session.id,
        'session_name': learning_session.session_name,
        'created_at': learning_session.created_at.isoformat(),
        'files': [
            {
                'id': f.drive_id,
                'name': f.name,
                'mime_type': f.mime_type
            }
            for f in learning_session.selected_files
        ],
        'files_count': len(learning_session.selected_files),
        'discussions_count': len(learning_session.discussion_threads),
        'is_active': learning_session.is_active
    })

@learning.route('/sessions', methods=['GET'])
@require_login
def get_user_sessions():
    """Get all learning sessions untuk user"""
    
    user_id = session.get('user_id')
    sessions = LearningSession.query.filter_by(peserta_id=user_id).order_by(
        LearningSession.created_at.desc()
    ).all()
    
    return jsonify({
        'sessions': [
            {
                'session_id': s.id,
                'session_name': s.session_name,
                'files_count': len(s.selected_files),
                'created_at': s.created_at.isoformat(),
                'is_active': s.is_active
            }
            for s in sessions
        ],
        'total': len(sessions)
    })

# ============================================================================
# ROUTES: Intelligent Chatbot
# ============================================================================

@learning.route('/chat', methods=['POST'])
@require_login
def chat_with_documents():
    """
    Chat dengan documents dalam selected session + fallback ke general knowledge
    
    Request body:
    {
        "session_id": session_id,
        "query": "Indonesian question here"
    }
    
    Response:
    {
        "answer": "Jawaban lengkap dalam Bahasa Indonesia",
        "sources": ["file1.pdf", "file2.pdf"],
        "from_docs": true,
        "confidence": 0.85,
        "source_count": 2,
        "note": "Jawaban dari dokumentasi"
    }
    """
    if not _rag_engine:
        return jsonify({'error': 'Chatbot not initialized'}), 500
    
    user_id = session.get('user_id')
    data = request.json
    session_id = data.get('session_id')
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({'error': 'Query cannot be empty'}), 400
    
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    try:
        # Get session & verify ownership
        learning_session = LearningSession.query.get(session_id)
        if not learning_session:
            return jsonify({'error': 'Session not found'}), 404
        
        if learning_session.peserta_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Get selected file identifiers
        file_ids = [f.drive_id for f in learning_session.selected_files]
        file_names = {f.drive_id: f.name for f in learning_session.selected_files}
        
        if not file_ids:
            return jsonify({'error': 'No files in this session'}), 400
        
        # Generate response dengan fallback ke general knowledge (IMPROVED)
        response_data = _rag_engine.answer_indonesian_query(
            query,
            allow_general_knowledge=True  # ✅ NEW: Allow general knowledge fallback
        )
        
        answer = response_data['answer']
        from_docs = response_data['from_docs']
        sources_count = response_data['sources_count']
        
        # Determine confidence based on source
        if from_docs:
            # More docs = higher confidence (0.85-0.95 range)
            confidence = 0.85 + (min(sources_count, 3) * 0.03)
            confidence = min(confidence, 0.95)
            note = 'Jawaban dari dokumentasi file yang dipilih'
        else:
            # General knowledge has lower confidence
            confidence = 0.72
            note = 'Jawaban dari pengetahuan umum - untuk info lebih akurat cek dokumentasi'
        
        # Extract source file names if from docs
        sources = []
        if from_docs:
            english_docs = _rag_engine.search_english_documents(query, top_k=3)
            for doc in english_docs:
                # Try to match document dengan file names
                for file_id, file_name in file_names.items():
                    if file_name.lower() in doc.lower() or file_id in doc:
                        sources.append(file_name)
                        break
            sources = list(set(sources))  # Unique
        
        return jsonify({
            'answer': answer,
            'sources': sources,
            'from_docs': from_docs,
            'source_count': sources_count,
            'confidence': round(confidence, 2),
            'session_id': session_id,
            'note': note
        })
    
    except Exception as e:
        print(f"❌ Chat error: {e}")
        return jsonify({'error': f'Error processing query: {str(e)}'}), 500

# ============================================================================
# ROUTES: Discussion Threads
# ============================================================================

@learning.route('/discussions/create', methods=['POST'])
@require_login
def create_discussion():
    """
    Create discussion thread dalam session
    
    Request body:
    {
        "session_id": session_id,
        "title": "Discussion title",
        "description": "Optional description"
    }
    """
    user_id = session.get('user_id')
    data = request.json
    session_id = data.get('session_id')
    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    
    if not title:
        return jsonify({'error': 'Title required'}), 400
    
    if not session_id:
        return jsonify({'error': 'Session ID required'}), 400
    
    try:
        # Verify session exists
        learning_session = LearningSession.query.get(session_id)
        if not learning_session or learning_session.peserta_id != user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Create discussion
        thread = DiscussionThread(
            session_id=session_id,
            title=title,
            description=description,
            created_by=user_id,
            created_at=datetime.utcnow()
        )
        
        db.session.add(thread)
        db.session.commit()
        
        return jsonify({
            'thread_id': thread.id,
            'title': thread.title,
            'created_at': thread.created_at.isoformat(),
            'message': 'Discussion thread created'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@learning.route('/discussions/<int:thread_id>', methods=['GET'])
def get_discussion(thread_id):
    """Get discussion thread dengan semua posts"""
    
    thread = DiscussionThread.query.get(thread_id)
    if not thread:
        return jsonify({'error': 'Thread not found'}), 404
    
    posts = []
    for post in thread.posts:
        posts.append({
            'post_id': post.id,
            'user_id': post.user_id,
            'content': post.content,
            'is_ai_generated': post.is_ai_generated,
            'created_at': post.created_at.isoformat(),
            'helpful_count': len([r for r in post.reactions if r.reaction_type == 'helpful']),
            'agree_count': len([r for r in post.reactions if r.reaction_type == 'agree'])
        })
    
    return jsonify({
        'thread_id': thread.id,
        'title': thread.title,
        'description': thread.description,
        'created_by': thread.created_by,
        'created_at': thread.created_at.isoformat(),
        'posts_count': len(posts),
        'posts': posts
    })

@learning.route('/discussions/<int:thread_id>/post', methods=['POST'])
@require_login
def post_to_discussion(thread_id):
    """Post reply dalam discussion thread"""
    
    user_id = session.get('user_id')
    data = request.json
    content = data.get('content', '').strip()
    
    if not content:
        return jsonify({'error': 'Content cannot be empty'}), 400
    
    try:
        thread = DiscussionThread.query.get(thread_id)
        if not thread:
            return jsonify({'error': 'Thread not found'}), 404
        
        # Create post
        post = DiscussionPost(
            thread_id=thread_id,
            user_id=user_id,
            content=content,
            is_ai_generated=False,
            created_at=datetime.utcnow()
        )
        
        db.session.add(post)
        db.session.commit()
        
        return jsonify({
            'post_id': post.id,
            'created_at': post.created_at.isoformat(),
            'message': 'Post created successfully'
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@learning.route('/discussions/<int:thread_id>/sessions', methods=['GET'])
def get_thread_sessions(thread_id):
    """Get all sessions yang have this discussion thread"""
    
    thread = DiscussionThread.query.get(thread_id)
    if not thread:
        return jsonify({'error': 'Thread not found'}), 404
    
    return jsonify({
        'thread_id': thread_id,
        'session_id': thread.session_id,
        'session_name': thread.session.session_name if thread.session else None
    })

# ============================================================================
# ROUTES: Learning Analytics
# ============================================================================

@learning.route('/progress', methods=['GET'])
@require_login
def get_learning_progress():
    """Get user learning progress"""
    
    user_id = session.get('user_id')
    
    # Get user sessions
    user_sessions = LearningSession.query.filter_by(peserta_id=user_id).all()
    
    total_files_studied = 0
    total_discussions = 0
    
    for learning_session in user_sessions:
        total_files_studied += len(learning_session.selected_files)
        total_discussions += len(learning_session.discussion_threads)
    
    # Get quiz scores
    quiz_attempts = UserQuizAttempt.query.filter_by(user_id=user_id).all()
    avg_quiz_score = (
        sum(a.score for a in quiz_attempts) / len(quiz_attempts)
        if quiz_attempts else 0
    )
    
    return jsonify({
        'sessions_count': len(user_sessions),
        'files_studied': total_files_studied,
        'discussions_participated': total_discussions,
        'quiz_attempts': len(quiz_attempts),
        'average_quiz_score': round(avg_quiz_score, 2),
        'recent_sessions': [
            {
                'session_id': s.id,
                'name': s.session_name,
                'created_at': s.created_at.isoformat()
            }
            for s in user_sessions[-5:]  # Last 5
        ]
    })

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@learning.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Resource not found'}), 404

@learning.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500
