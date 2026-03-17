"""
Chat Routes untuk RAG-based Question Answering dengan Chroma Vector Database
Menggunakan advanced RAG intelligence dan enhanced search dengan fallback strategies
"""

from flask import Blueprint, request, jsonify, render_template, session
from functools import wraps
from datetime import datetime
from .smart_search import ChromaDocumentSearch
from .groq_integration import GroqChatManager  # Primary AI provider (Gemini free tier API not available)
from .rag_intelligence import ContextExpander, RetrievalEnhancer, ContextOptimizer
from .enhanced_search import EnhancedChromaSearch, GoogleDriveSyncEnforcer
from .chroma_optimizer import QueryOptimizer, SearchCache, ResultRanker  # PHASE 1: Query optimization, caching, ranking
from .models import db, ChatSession, ChatMessage, ChatMessageSource, ChatFeedback, GoogleDriveFile
from .drive_sync import get_folder_id
import os

# Global instances - using dictionary to avoid scoping issues
_system_state = {
    'chat_manager': None,
    'fallback_chat_manager': None,  # Groq is primary AI
    'search_engine': None,
    'enhanced_search': None,  # NEW: Fallback search strategies
    'search_cache': None,  # PHASE 1: Search result caching
    'last_drive_sync': None   # Track last Google Drive sync
}

# Initialize search cache (PHASE 1 Optimization)
search_cache = SearchCache(ttl_hours=24, max_cache_size=1000)
_system_state['search_cache'] = search_cache

def initialize_chat_system():
    """Initialize chat system dengan Groq (PRIMARY) dan Chroma dengan fallback search"""
    global _system_state

    try:
        # Initialize Groq as PRIMARY AI (RECOMMENDED: proven working)
        print("⏳ Initializing Groq AI Manager...")
        groq_manager = GroqChatManager()
        print(f"✅ Groq Manager created. Initialized: {groq_manager.initialized}")

        if not groq_manager.initialized:
            print(f"❌ CRITICAL: Groq not initialized - checking API key and SDK...")
            print(f"   GROQ_API_KEY env: {bool(os.getenv('GROQ_API_KEY'))}")
            print(f"   API Key length: {len(os.getenv('GROQ_API_KEY', '')) if os.getenv('GROQ_API_KEY') else 0}")

        # Initialize Chroma-based search engine
        # Wrap dengan try-except untuk prevent hanging pada Chroma initialization
        credentials_path = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
        chroma_engine = None
        enhanced_search = None

        try:
            print("⏳ Initializing Chroma document search...")
            chroma_engine = ChromaDocumentSearch(credentials_path)

            # Initialize ENHANCED search dengan fallback strategies
            if chroma_engine and chroma_engine.vector_store:
                enhanced_search = EnhancedChromaSearch(chroma_engine.vector_store)
                print(f"✅ Enhanced search system initialized (dengan fallback strategies)")
        except Exception as chroma_error:
            print(f"⚠️  Chroma initialization warning: {chroma_error}")
            print(f"    System will continue without Chroma search (Groq only)")
            chroma_engine = None
            enhanced_search = None

        # Store in global state
        # Groq is PRIMARY AI provider (not fallback)
        _system_state['chat_manager'] = groq_manager
        _system_state['fallback_chat_manager'] = groq_manager  # Same as primary for now
        _system_state['search_engine'] = chroma_engine
        _system_state['enhanced_search'] = enhanced_search  # NEW: Fallback search

        # Status
        groq_ok = groq_manager.initialized

        print(f"✅ Chat system initialized")
        print(f"   AI Provider (Groq PRIMARY): {'✅' if groq_ok else '❌ NOT INITIALIZED'}")
        print(f"   Vector DB (Chroma): {'✅' if chroma_engine else '⚠️  Disabled/Error'}")
        print(f"   Enhanced Search (fallbacks): {'✅' if enhanced_search else '⚠️  Disabled'}")
        print(f"   System state updated successfully")

        if not groq_ok:
            print(f"⚠️  WARNING: Groq initialization failed - chat will not work!")

    except Exception as e:
        print(f"❌ Error initializing chat system: {e}")
        import traceback
        traceback.print_exc()


def get_google_drive_file_info(file_id: str):
    """
    Get Google Drive file information dengan link untuk membuka di Google Drive

    Args:
        file_id: Google Drive file ID (drive_id)

    Returns:
        Dictionary dengan: name, link, folder_path, atau None jika tidak ditemukan
    """
    try:
        # Lookup di database
        file_obj = GoogleDriveFile.query.filter_by(drive_id=file_id).first()

        if file_obj:
            # Get folder path untuk context
            folder_path = ""
            if file_obj.folder:
                folder_path = file_obj.folder.name

            return {
                'name': file_obj.name,
                'link': file_obj.web_view_link if file_obj.web_view_link else f"https://drive.google.com/file/d/{file_id}/view",
                'folder_path': folder_path,
                'drive_id': file_id
            }
        return None
    except Exception as e:
        print(f"⚠️  Error getting file info: {e}")
        # Return fallback link
        return {
            'name': 'Dokumen',
            'link': f"https://drive.google.com/file/d/{file_id}/view",
            'folder_path': '',
            'drive_id': file_id
        }


def get_dokumen_bengkel_folder_info():
    """
    Get informasi folder Dokumen Bengkel dari Google Drive

    Returns:
        Dictionary dengan: name, link, folder_id, atau None jika tidak ditemukan
    """
    try:
        folder_id = get_folder_id('Dokumen Bengkel')

        if folder_id:
            return {
                'name': '📁 Dokumen Bengkel',
                'link': f"https://drive.google.com/drive/folders/{folder_id}",
                'folder_id': folder_id
            }
        return None
    except Exception as e:
        print(f"⚠️  Error getting Dokumen Bengkel folder: {e}")
        return None


def require_login(f):
    """Decorator untuk memastikan user sudah login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_or_create_active_session(user_id: int) -> ChatSession:
    """Get atau create active chat session untuk user"""
    session_obj = ChatSession.query.filter_by(
        peserta_id=user_id,
        is_active=True
    ).order_by(ChatSession.updated_at.desc()).first()

    if not session_obj:
        session_obj = ChatSession(peserta_id=user_id)
        db.session.add(session_obj)
        db.session.commit()

    return session_obj


chat = Blueprint('chat', __name__, url_prefix='/api/chat')


@chat.route('/health', methods=['GET'])
def chat_health():
    """Check chat system health"""
    groq_mgr = _system_state.get('fallback_chat_manager')
    return jsonify({
        'status': 'ok',
        'groq_available': groq_mgr.initialized if groq_mgr else False,
        'search_available': _system_state['search_engine'] is not None
    })


@chat.route('/topics', methods=['GET'])
def get_suggested_topics():
    """Get suggested topics based on automotive/bengkel knowledge base"""
    # Curated topics untuk dunia perbengkelan & otomotif
    topics = [
        {
            'id': 'diagnosis',
            'label': 'Diagnosis & Troubleshooting',
            'icon': 'fa-stethoscope',
            'color': 'danger',
            'description': 'Identifikasi masalah kendaraan',
            'examples': [
                'Mesin berbunyi kasar saat start',
                'Lampu check engine menyala',
                'Rem berseret saat berkendara'
            ]
        },
        {
            'id': 'maintenance',
            'label': 'Perawatan & Service',
            'icon': 'fa-wrench',
            'color': 'primary',
            'description': 'Maintenance rutin & berkala',
            'examples': [
                'Interval penggantian oli',
                'Service filter udara',
                'Pengecekan sistem kelistrikan'
            ]
        },
        {
            'id': 'engine',
            'label': 'Mesin & Engine',
            'icon': 'fa-cog',
            'color': 'info',
            'description': 'Spesifikasi & prosedur mesin',
            'examples': [
                'Valve clearance adjustment',
                'Carburetor tuning',
                'Ignition timing setup'
            ]
        },
        {
            'id': 'transmission',
            'label': 'Transmisi & Gear',
            'icon': 'fa-gears',
            'color': 'warning',
            'description': 'Masalah & perbaikan transmisi',
            'examples': [
                'Gigi berat saat masuk',
                'Oli transmisi kotor',
                'Clutch perlu diganti'
            ]
        },
        {
            'id': 'suspension',
            'label': 'Suspensi & Steering',
            'icon': 'fa-arrows',
            'color': 'success',
            'description': 'Sistem suspensi & kemudi',
            'examples': [
                'Shock wear signs',
                'Steering wheel vibration',
                'Suspension noise diagnosis'
            ]
        },
        {
            'id': 'electrical',
            'label': 'Kelistrikan & Battery',
            'icon': 'fa-bolt',
            'color': 'warning',
            'description': 'Sistem kelistrikan kendaraan',
            'examples': [
                'Battery tidak dapat dicharge',
                'Alternator error diagnosis',
                'Starter motor repair'
            ]
        },
        {
            'id': 'brakes',
            'label': 'Rem & Braking',
            'icon': 'fa-hand-paper',
            'color': 'danger',
            'description': 'Sistem pengereman',
            'examples': [
                'Brake pad wear indicators',
                'Brake fluid leaks',
                'ABS system troubleshooting'
            ]
        },
        {
            'id': 'cooling',
            'label': 'Pendinginan & Radiator',
            'icon': 'fa-thermometer-half',
            'color': 'info',
            'description': 'Sistem pendingin mesin',
            'examples': [
                'Overheating diagnosis',
                'Coolant circulation check',
                'Thermostat replacement'
            ]
        },
        {
            'id': 'safety',
            'label': 'Keselamatan Kerja',
            'icon': 'fa-shield',
            'color': 'danger',
            'description': 'Prosedur aman di bengkel',
            'examples': [
                'Penggunaan alat safety',
                'Prosedur jacking kendaraan',
                'Emergency response'
            ]
        },
        {
            'id': 'parts',
            'label': 'Sparepart & OEM',
            'icon': 'fa-cube',
            'color': 'secondary',
            'description': 'Identifikasi & spesifikasi part',
            'examples': [
                'OEM part numbering',
                'Sparepart compatibility',
                'Quality assessment'
            ]
        },
        {
            'id': 'technology',
            'label': 'Teknologi Kendaraan',
            'icon': 'fa-microchip',
            'color': 'info',
            'description': 'Teknologi modern & fitur canggih',
            'examples': [
                'Apa itu teknologi ABS?',
                'Sistem traksi control (TCS) bagaimana cara kerjanya?',
                'Electronic Stability Control (ESC) penjelasan'
            ]
        },
        {
            'id': 'fuel',
            'label': 'Sistem Bahan Bakar',
            'icon': 'fa-gas-pump',
            'color': 'warning',
            'description': 'Fuel system & fuel injection',
            'examples': [
                'Fuel pump tidak bekerja',
                'Injector carbon cleaning procedure',
                'Fuel pressure regulator testing'
            ]
        },
        {
            'id': 'climate',
            'label': 'AC & Pendingin Ruang',
            'icon': 'fa-wind',
            'color': 'info',
            'description': 'Air conditioning system',
            'examples': [
                'AC tidak dingin lagi',
                'Freon charging procedure',
                'Compressor clutch diagnosis'
            ]
        },
        {
            'id': 'lighting',
            'label': 'Sistem Penerangan',
            'icon': 'fa-lightbulb',
            'color': 'warning',
            'description': 'Headlight & lighting system',
            'examples': [
                'Headlight adjustment & aim',
                'LED vs Halogen comparison',
                'Tail light bulb replacement'
            ]
        },
        {
            'id': 'body',
            'label': 'Body & Exterior',
            'icon': 'fa-paint-brush',
            'color': 'secondary',
            'description': 'Bodywork & exterior maintenance',
            'examples': [
                'Dent repair & repainting',
                'Rust prevention & treatment',
                'Trim & molding replacement'
            ]
        },
        {
            'id': 'interior',
            'label': 'Interior & Audio',
            'icon': 'fa-home',
            'color': 'secondary',
            'description': 'Cabin comfort & entertainment',
            'examples': [
                'Seat upholstery repair',
                'Sound system installation',
                'Dashboard creaking fix'
            ]
        }
    ]

    return jsonify({
        'success': True,
        'topics': topics,
        'total': len(topics)
    })


@chat.route('/ask', methods=['POST'])
@require_login
def ask_question():
    """
    Main endpoint untuk tanya-jawab dengan RAG + Chroma Vector DB

    POST /api/chat/ask
    {
        'question': str,
        'use_documents': bool (default: True),
        'search_limit': int (default: 5)
    }
    """
    try:
        data = request.get_json()
        user_id = session.get('user_id')
        question = data.get('question', '').strip()
        use_documents = data.get('use_documents', True)
        search_limit = data.get('search_limit', 3)  # OPTIMIZED: 5 → 3 untuk faster search

        # Validasi input
        if not question or len(question) < 2:
            return jsonify({'error': 'Pertanyaan terlalu pendek. Minimal 2 karakter.'}), 400

        if len(question) > 1000:
            return jsonify({'error': 'Pertanyaan terlalu panjang. Maksimal 1000 karakter.'}), 400

        # Get atau create active chat session
        chat_session = get_or_create_active_session(user_id)

        # Save user message to database
        user_msg = ChatMessage(
            session_id=chat_session.id,
            role='user',
            content=question
        )
        db.session.add(user_msg)
        db.session.commit()

        # Search documents dari Chroma dengan RAG intelligence + ENHANCED SEARCH (fallback strategies)
        context = ""
        sources = []
        context_metadata = {}
        search_strategy = "none"

        search_engine = _system_state.get('search_engine')
        enhanced_search = _system_state.get('enhanced_search')

        if use_documents and search_engine:
            try:
                # PHASE 1: Optimize query dengan QueryOptimizer
                optimized_question = QueryOptimizer.preprocess_query(question)
                print(f"✨ Query optimization: '{question}' → '{optimized_question[:100]}...'")

                # PHASE 1: Check cache sebelum search
                cache = _system_state.get('search_cache')
                cached_result = None
                if cache:
                    cached_result = cache.get(optimized_question)
                    if cached_result:
                        print(f"✅ Cache HIT! Using cached result")
                        search_results = cached_result
                        search_strategy = "cached"
                    else:
                        print(f"❌ Cache MISS - will search and cache")

                # If not cached, do actual search
                if not cached_result:
                    # TRY 1: Use enhanced search dengan fallback strategies
                    # Ini memastikan selalu ada hasil, bahkan jika semantic search tidak menemukan
                    if enhanced_search:
                        print(f"🔍 Searching dengan ENHANCED SEARCH (multiple strategies)...")
                        search_results = enhanced_search.search_with_fallbacks(
                            query=optimized_question,  # Use optimized question
                            search_limit=search_limit,
                            results_limit=8,
                            force_include_results=True  # IMPORTANT: Always return something!
                        )
                        search_strategy = search_results.get('search_strategy', 'unknown')
                        print(f"   Strategy used: {search_strategy}")
                    else:
                        # Fallback ke original search jika enhanced search tidak available
                        print(f"🔍 Using standard search...")
                        search_results = search_engine.search(
                            query=optimized_question,  # Use optimized question
                            search_limit=search_limit,
                            results_limit=8
                        )
                        search_strategy = "standard"

                    # PHASE 1: Cache search results
                    if cache and search_results:
                        cache.set(optimized_question, search_results)
                        print(f"💾 Result cached for future queries")

                # ADVANCED: Process dengan RAG intelligence untuk konteks lebih baik
                if search_results.get('results'):
                    # Convert search results ke format chunks untuk RAG processing
                    chunks = []
                    for result in search_results.get('results', []):
                        for i, chunk_data in enumerate(result.get('chunks', [])):
                            chunks.append({
                                'text': chunk_data.get('text', chunk_data.get('chunk', '')),
                                'heading_hierarchy': result.get('heading_hierarchy', []),
                                'file_name': result.get('file_name', 'Unknown'),
                                'file_id': result.get('file_id', ''),
                                'chunk_index': i,
                                'similarity': chunk_data.get('similarity', 0),
                                'preview': chunk_data.get('text', '')[:60] if 'text' in chunk_data else chunk_data.get('chunk', '')[:60]
                            })

                    if chunks:
                        # 🚫 STEP 1: DOMAIN FILTER - Remove non-automotive chunks
                        # This prevents using documents about plants, cooking, health, etc.
                        groq_manager = _system_state.get('chat_manager')
                        if groq_manager:
                            original_count = len(chunks)
                            chunks = groq_manager._filter_non_automotive_context(chunks)
                            filtered_count = len(chunks)
                            if filtered_count < original_count:
                                print(f"🚫 Domain filter: Removed {original_count - filtered_count} non-automotive chunks")

                        # STEP 2: Rank dengan hierarchy relevance (bonus untuk chunks dalam heading yang relevan)
                        chunks = RetrievalEnhancer.rank_by_hierarchy(chunks, question)

                        # PHASE 1: STEP 2.5 - Quick ranking dengan ResultRanker (multi-factor scoring)
                        # Rank berdasarkan: similarity (60%) + position (15%) + credibility (15%) + keyword (10%)
                        chunks_for_ranking = []
                        for chunk in chunks:
                            chunks_for_ranking.append({
                                'text': chunk.get('text', ''),
                                'similarity': chunk.get('similarity', 0.5),
                                'chunk_index': chunk.get('chunk_index', 0),
                                'metadata': {
                                    'source_credibility': 0.9,  # Documents from Google Drive have high credibility
                                    'file_name': chunk.get('file_name', '')
                                }
                            })

                        ranked_chunks = ResultRanker.rank_results(chunks_for_ranking, question)

                        # Map ranking back to original chunks
                        ranked_chunk_indices = [chunks_for_ranking.index(r) for r in chunks_for_ranking]
                        chunks = [chunks[i] for i in range(len(chunks))]
                        for i, ranked in enumerate(ranked_chunks):
                            if i < len(chunks):
                                chunks[i]['final_ranking_score'] = ranked.get('final_score', 0)
                                chunks[i]['ranking_factors'] = ranked.get('ranking_factors', {})

                        if chunks:
                            top_score = chunks[0].get('final_ranking_score', 0)
                            print(f"✨ PHASE 1: ResultRanker applied - Top chunk score: {top_score:.3f}")

                        # STEP 3: Optimize context untuk AI consumption
                        optimized = ContextOptimizer.optimize_context(
                            chunks=chunks,
                            query=question,
                            max_context_chars=12000,  # Lebih besar untuk konteks lebih lengkap
                            strategy='quality'
                        )

                        context = optimized['primary_context']
                        context_metadata = optimized['metadata']

                        # Add coverage estimate ke logs
                        coverage = context_metadata.get('coverage_estimate', 0)
                        print(f"📊 Context Coverage: {coverage*100:.0f}% ({context_metadata.get('num_chunks_used', 0)} chunks dari {context_metadata.get('chunks_available', 0)})")
                    else:
                        # No chunks meaningful - use search results directly
                        context = search_engine.format_context_for_ai(search_results)
                else:
                    # No results dari enhanced search - use fallback context
                    context = "Data yang relevan sedang dicari dari knowledge base. Jika tidak menemukan, AI akan memberikan jawaban general."

                # Collect sources dari search results
                for result in search_results.get('results', []):
                    for chunk in result.get('chunks', []):
                        file_id = result.get('file_id', '')
                        file_name = result.get('file_name', 'Unknown source')

                        # Get Google Drive file info (link dan folder path)
                        file_info = get_google_drive_file_info(file_id)

                        sources.append({
                            'file_id': file_id,
                            'name': file_info['name'] if file_info else file_name,
                            'link': file_info['link'] if file_info else f"https://drive.google.com/file/d/{file_id}/view",
                            'relevance': chunk.get('similarity', chunk.get('chunk_similarity', 0)),
                            'folder_path': file_info.get('folder_path', '') if file_info else ''
                        })

                # Log search strategy used
                print(f"✅ Search complete via {search_strategy} strategy ({len(sources)} sources found)")
                # PHASE 1: Log cache statistics
                cache = _system_state.get('search_cache')
                if cache:
                    stats = cache.get_stats()
                    cache_info = f"💾 Cache stats: {stats['cache_size']}/{stats['max_cache_size']} entries ({stats['cache_usage_percent']:.1f}% usage)"
                    print(cache_info)
            except Exception as e:
                print(f"⚠️  Error searching documents: {e}")
                # Ensure context at least exists even with error
                context = f"Informasi sedang diambil dari knowledge base. Error: {str(e)[:100]}"


        # Generate answer dengan Groq (ONLY AI provider)
        # Groq: FREE tier dengan 1000 req/hari, super cepat, reliable
        result = {'success': False, 'error': 'Groq AI provider not available'}

        # Get Groq manager from system state
        groq_manager = _system_state.get('fallback_chat_manager')

        # Use Groq ONLY (Gemini free tier tidak support v1beta API)
        if groq_manager and groq_manager.initialized:
            try:
                print(f"🚀 Using Groq AI for response...")
                result = groq_manager.generate_answer(
                    query=question,
                    context=context
                )
                if result['success']:
                    print(f"✅ Groq response generated successfully")
            except Exception as e:
                print(f"❌ Groq error: {e}")
                result = {'success': False, 'error': f'Groq API error: {str(e)[:100]}'}
        else:
            print(f"❌ Groq chat manager not initialized! State: {_system_state}")
            return jsonify({
                'success': False,
                'error': 'AI provider not initialized. Please restart the application.',
                'answer': None
            }), 500

        # If Groq fails, return error (no fallback to Gemini)
        if not result.get('success'):
            error_msg = result.get('error', 'Groq API error')
            return jsonify({
                'success': False,
                'error': error_msg,
                'answer': None
            }), 500

        # Save assistant message to database
        if result['success']:
            assistant_msg = ChatMessage(
                session_id=chat_session.id,
                role='assistant',
                content=result['answer'],
                tokens_used=result.get('tokens')
            )
            db.session.add(assistant_msg)
            db.session.flush()  # Get the ID

            # Save sources
            for source in sources[:5]:  # Limit to top 5 sources
                source_record = ChatMessageSource(
                    message_id=assistant_msg.id,
                    file_name=source['file_name'],
                    relevance_score=source['relevance']
                )
                db.session.add(source_record)

            db.session.commit()

        # Update session timestamp
        chat_session.updated_at = datetime.utcnow()
        db.session.commit()

        # Get Dokumen Bengkel folder info untuk ditampilkan di sidebar
        dokumen_bengkel = get_dokumen_bengkel_folder_info()

        return jsonify({
            'success': result['success'],
            'answer': result.get('answer'),
            'sources': sources,
            'dokumen_bengkel': dokumen_bengkel,
            'with_rag': result.get('with_rag', False),
            'model': result.get('model'),
            'error': result.get('error'),
            'generated_at': result.get('generated_at'),
            'session_id': chat_session.id
        })

    except Exception as e:
        print(f"❌ Error in ask endpoint: {e}")
        return jsonify({'error': str(e)}), 500


@chat.route('/history', methods=['GET'])
@require_login
def get_history():
    """Get persistent chat history dari database"""
    try:
        user_id = session.get('user_id')
        limit = request.args.get('limit', 20, type=int)

        # Get active chat session
        chat_session = ChatSession.query.filter_by(
            peserta_id=user_id,
            is_active=True
        ).order_by(ChatSession.updated_at.desc()).first()

        if not chat_session:
            return jsonify({
                'success': True,
                'history': [],
                'session_id': None
            })

        # Get messages dari session
        messages = ChatMessage.query.filter_by(
            session_id=chat_session.id
        ).order_by(ChatMessage.timestamp.asc()).limit(limit).all()

        history = []
        for msg in messages:
            msg_data = {
                'id': msg.id,
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'sources': []
            }

            # Get sources jika ada
            if msg.sources:
                msg_data['sources'] = [
                    {
                        'file_name': s.file_name,
                        'relevance': s.relevance_score
                    }
                    for s in msg.sources
                ]

            history.append(msg_data)

        return jsonify({
            'success': True,
            'history': history,
            'session_id': chat_session.id,
            'total_messages': len(history)
        })
    except Exception as e:
        print(f"❌ Error getting history: {e}")
        return jsonify({'error': str(e)}), 500


@chat.route('/history/clear', methods=['POST'])
@require_login
def clear_history():
    """Close active chat session dan start new one"""
    try:
        user_id = session.get('user_id')

        # Get active session
        chat_session = ChatSession.query.filter_by(
            peserta_id=user_id,
            is_active=True
        ).first()

        if chat_session:
            chat_session.is_active = False
            db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Chat session closed. New session will be created on next question.'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat.route('/stats', methods=['GET'])
def get_chat_stats():
    """Get Chroma vector database statistics"""
    try:
        search_engine = _system_state.get('search_engine')
        if not search_engine:
            return jsonify({'error': 'Search engine not available'}), 503

        stats = search_engine.get_stats()

        return jsonify({
            'success': True,
            'vector_store': stats,
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat.route('/search', methods=['POST'])
@require_login
def search_documents():
    """
    Direct document search endpoint menggunakan Chroma

    POST /api/chat/search
    {
        'query': str,
        'limit': int (default: 5)
    }
    """
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        limit = data.get('limit', 5)

        if not query:
            return jsonify({'error': 'Query tidak boleh kosong'}), 400

        search_engine = _system_state.get('search_engine')
        if not search_engine:
            return jsonify({'error': 'Search engine tidak tersedia'}), 503

        results = search_engine.search(query, search_limit=limit, results_limit=10)

        return jsonify({
            'success': True,
            'query': query,
            'results': results.get('results', []),
            'total_documents': results.get('total_results', 0)
        })

    except Exception as e:
        print(f"❌ Error in search endpoint: {e}")
        return jsonify({'error': str(e)}), 500


@chat.route('/extract-key-points', methods=['POST'])
@require_login
def extract_key_points():
    """
    Extract key points dari text

    POST /api/chat/extract-key-points
    {
        'text': str
    }
    """
    try:
        data = request.get_json()
        text = data.get('text', '').strip()

        if not text:
            return jsonify({'error': 'Text tidak boleh kosong'}), 400

        if not chat_manager:
            return jsonify({'error': 'AI engine tidak tersedia'}), 503

        result = chat_manager.extract_key_points(text)

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@chat.route('/suggest-questions', methods=['POST'])
@require_login
def suggest_questions():
    """
    Suggest pertanyaan berdasarkan context

    POST /api/chat/suggest-questions
    {
        'document_name': str (optional)
    }
    """
    try:
        # List pertanyaan umum untuk mekanik
        suggestions = {
            'umum': [
                'Bagaimana cara perawatan berkala kendaraan?',
                'Apa saja persiapan sebelum service?',
                'Bagaimana cara mendiagnosa masalah mesin?',
                'Berapa interval penggantian oli standar?',
                'Bagaimana cara setting timing ignition?',
            ],
            'teknis': [
                'Apa perbedaan sistem direct injection vs indirect injection?',
                'Bagaimana cara membaca kode error pada OBD?',
                'Bagaimana cara tune-up kendaraan?',
                'Apa tanda-tanda clutch yang perlu diganti?',
                'Bagaimana cara check dan set valve clearance?',
            ]
        }

        return jsonify({
            'success': True,
            'suggestions': suggestions
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# UI Route
@chat.route('/page', methods=['GET'])
def chat_page():
    """Render chat page"""
    from flask import current_app
    from flask_wtf.csrf import generate_csrf
    try:
        return render_template('user/chat.html', csrf_token=generate_csrf())
    except Exception as e:
        print(f"❌ Error rendering chat page: {e}")
        return jsonify({'error': 'Could not render chat page'}), 500


def register_chat_routes(app):
    """Register chat routes ke app"""
    initialize_chat_system()
    app.register_blueprint(chat)
    print("✅ Chat routes registered")
