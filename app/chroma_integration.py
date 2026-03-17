"""
Chroma Vector Database Integration (Cloud & Local)
Menyimpan dokumen dan chunks sebagai vectors untuk semantic search
Supports both Chroma Cloud dan Local instances
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️  chromadb not available")

try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    print("⚠️  sentence-transformers not available")

from app.api_key_manager import get_api_key, report_api_error, report_api_success, APIProvider


class ChromaVectorStore:
    """
    Manage Chroma Vector Database untuk document storage dan retrieval
    Support both Chroma Cloud dan Local instance
    """

    def __init__(self,
                 use_cloud: bool = True,
                 cloud_host: str = None,
                 cloud_api_key: str = None,
                 cloud_tenant: str = None,
                 cloud_database: str = None,
                 persist_dir: str = None,
                 model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize Chroma Vector Store (Cloud atau Local) dengan multi-key support

        Args:
            use_cloud: True untuk Chroma Cloud, False untuk local
            cloud_host: Chroma Cloud API host (e.g., api.trychroma.com)
            cloud_api_key: Chroma Cloud API key
            cloud_tenant: Chroma Cloud tenant ID
            cloud_database: Chroma Cloud database name
            persist_dir: Directory untuk local persistence (jika use_cloud=False)
            model_name: Sentence transformer model untuk embeddings
        """
        self.use_cloud = use_cloud
        self.cloud_host = cloud_host
        self.cloud_api_key = cloud_api_key
        self.cloud_tenant = cloud_tenant
        self.cloud_database = cloud_database
        self.client = None
        self.embedding_model = None
        self.use_multi_key_manager = False

        # Load dari environment variables jika tidak disediakan
        if use_cloud:
            self.cloud_host = cloud_host or os.getenv('CHROMA_HOST', 'api.trychroma.com')

            # Priority: 1. Passed argument, 2. Multi-key manager, 3. Env var
            if cloud_api_key:
                self.cloud_api_key = cloud_api_key
                self.use_multi_key_manager = False
            else:
                try:
                    self.cloud_api_key = get_api_key('chroma', prefer_primary=True)
                    self.use_multi_key_manager = True
                except:
                    # Fallback to env var
                    self.cloud_api_key = os.getenv('CHROMA_API_KEY')
                    self.use_multi_key_manager = False

            self.cloud_tenant = cloud_tenant or os.getenv('CHROMA_TENANT')
            self.cloud_database = cloud_database or os.getenv('CHROMA_DATABASE', 'default')

            try:
                self._initialize_cloud_client()
                # Only mark as using cloud if initialization succeeded
                if self.client is None:
                    print("⚠️  Cloud initialization failed, falling back to local storage...")
                    self.use_cloud = False
                    persist_dir = persist_dir or os.path.join(os.path.dirname(__file__), '..', 'chroma_data')
                    os.makedirs(persist_dir, exist_ok=True)
                    self._initialize_local_client(persist_dir)
            except Exception as e:
                print(f"⚠️  Cloud initialization error: {e}, falling back to local storage...")
                if self.use_multi_key_manager:
                    report_api_error('chroma', error_type='connection_error')
        # Initialize embedding model
        self._initialize_embedding_model(model_name)

    def _initialize_cloud_client(self):
        """Initialize Chroma Cloud client"""
        if not CHROMADB_AVAILABLE:
            print("❌ chromadb not available for Chroma Cloud")
            return

        if not all([self.cloud_api_key, self.cloud_database]):
            print("❌ Missing Chroma Cloud credentials")
            print("Required: CHROMA_API_KEY, CHROMA_DATABASE")
            return

        try:
            # Initialize Chroma Cloud client with all required parameters
            self.client = chromadb.CloudClient(
                api_key=self.cloud_api_key,
                tenant=self.cloud_tenant or "default",
                database=self.cloud_database or "default"
            )

            # In newer chromadb versions, use client directly
            # The database context is handled by the client
            self.db = self.client

            print(f"✅ Chroma Cloud connected")
            print(f"   API Key: {self.cloud_api_key[:20]}...")
            print(f"   Database: {self.cloud_database}")

        except Exception as e:
            print(f"❌ Error connecting to Chroma Cloud: {e}")
            import traceback
            traceback.print_exc()
            self.client = None

    def _initialize_local_client(self, persist_dir: str):
        """Initialize local Chroma client"""
        if not CHROMADB_AVAILABLE:
            print("❌ chromadb not available for local Chroma")
            return

        try:
            # Create persist directory if it doesn't exist
            os.makedirs(persist_dir, exist_ok=True)

            # Use new Persistent Client API
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.db = None

            print(f"✅ Local Chroma initialized")
            print(f"   Persist dir: {persist_dir}")

        except Exception as e:
            print(f"❌ Error initializing local Chroma: {e}")
            self.client = None

    def _initialize_embedding_model(self, model_name: str):
        """Initialize embedding model - CLOUD ONLY (no local downloads)

        When using Chroma Cloud, we don't need local embeddings.
        Chroma Cloud handles all embedding operations server-side.
        """
        # Check if embedding downloads are disabled
        if os.getenv('DISABLE_EMBEDDINGS_DOWNLOAD', 'false').lower() == 'true':
            print("✅ Embedding model disabled (using Chroma Cloud embeddings)")
            self.model_name = model_name
            self.embedding_model = None
            return

        if not EMBEDDINGS_AVAILABLE:
            print("⚠️  sentence-transformers not available (lazy load)")
            return

        # Store model name for lazy loading, don't load yet
        self.model_name = model_name
        self.embedding_model = None  # Will be loaded on first use if needed
        print(f"⏳ Embedding model will be lazy-loaded on first use: {model_name}")

    def get_or_create_collection(self, collection_name: str = "documents"):
        """Get atau create Chroma collection dengan caching"""
        # Cache collection untuk menghindari repeated API calls
        cache_key = f"_collection_{collection_name}"
        if hasattr(self, cache_key):
            return getattr(self, cache_key)

        if not self.client:
            print("❌ Chroma client not available")
            return None

        try:
            if self.use_cloud:
                # Cloud: use client directly
                try:
                    collection = self.client.get_collection(name=collection_name)
                except:
                    collection = self.client.create_collection(
                        name=collection_name,
                        metadata={"hnsw:space": "cosine"}
                    )
            else:
                # Local: use client directly with new API
                try:
                    collection = self.client.get_collection(name=collection_name)
                except:
                    collection = self.client.create_collection(
                        name=collection_name,
                        metadata={"hnsw:space": "cosine"}
                    )

            print(f"✅ Collection '{collection_name}' ready")
            # Cache collection untuk performa
            setattr(self, cache_key, collection)
            return collection

        except Exception as e:
            print(f"❌ Error creating collection: {e}")
            return None

    def _get_embedding_model(self):
        """Lazy load embedding model on first use"""
        if self.embedding_model is None and EMBEDDINGS_AVAILABLE:
            try:
                print(f"📥 Loading embedding model on first use: {self.model_name}...")
                from sentence_transformers import SentenceTransformer
                self.embedding_model = SentenceTransformer(self.model_name)
                print(f"✅ Embedding model loaded successfully")
            except Exception as e:
                print(f"⚠️  Failed to load embedding model: {e}")
                return None
        return self.embedding_model

    def add_document_chunks(self,
                           file_id: str,
                           file_name: str,
                           chunks: List[str],
                           metadata: Dict = None) -> bool:
        """
        Add document chunks to vector store

        Args:
            file_id: Unique Google Drive file ID
            file_name: Name of the document
            chunks: List of text chunks to add
            metadata: Additional metadata

        Returns:
            Success status
        """
        try:
            collection = self.get_or_create_collection()
            model = self._get_embedding_model()
            if not collection or not model:
                return False

            # Generate embeddings
            embeddings = model.encode(chunks, convert_to_tensor=True).cpu().tolist()

            # Create unique IDs
            ids = [f"{file_id}_{i}" for i in range(len(chunks))]

            # Prepare metadata
            base_metadata = {
                "file_id": file_id,
                "file_name": file_name,
                "indexed_at": datetime.utcnow().isoformat(),
                "model": "paraphrase-multilingual-MiniLM-L12-v2"
            }

            if metadata:
                base_metadata.update(metadata)

            # Add to collection
            metadatas = [
                {
                    **base_metadata,
                    "chunk_index": i,
                    "chunk_size": len(chunk)
                }
                for i, chunk in enumerate(chunks)
            ]

            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )

            print(f"✅ Added {len(chunks)} chunks for '{file_name}' (ID: {file_id})")
            return True

        except Exception as e:
            print(f"❌ Error adding document chunks: {e}")
            return False

    def search_documents(self,
                        query: str,
                        search_limit: int = 5,
                        results_limit: int = 10) -> Dict:
        """
        Search untuk dokumen relevan menggunakan vector similarity

        Args:
            query: Search query (pertanyaan user)
            search_limit: Max documents to return
            results_limit: Max chunks per document

        Returns:
            Search results dengan chunks dan similarity scores
        """
        try:
            collection = self.get_or_create_collection()
            if not collection:
                return {'query': query, 'results': [], 'total_results': 0}

            # Try semantic search with embeddings (if model available)
            model = self._get_embedding_model()
            if model:
                try:
                    # Generate query embedding
                    query_embedding = model.encode([query], convert_to_tensor=True).cpu().tolist()[0]

                    # Search with embeddings
                    results = collection.query(
                        query_embeddings=[query_embedding],
                        n_results=results_limit,
                        include=['documents', 'metadatas', 'distances']
                    )
                except Exception as e:
                    print(f"⚠️  Semantic search failed: {e}. Using text search fallback.")
                    # Fallback to text search (Chroma Cloud handles this)
                    results = collection.query(
                        query_texts=[query],
                        n_results=results_limit,
                        include=['documents', 'metadatas', 'distances']
                    )
            else:
                # Use text-based search (Chroma Cloud will handle semantics)
                results = collection.query(
                    query_texts=[query],
                    n_results=results_limit,
                    include=['documents', 'metadatas', 'distances']
                )

            # Process results
            processed_results = []
            seen_files = set()

            if results['documents'] and len(results['documents']) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i] if results['metadatas'] else {}
                    distance = results['distances'][0][i] if results['distances'] else 1.0

                    # Convert distance to similarity (1 - distance for cosine)
                    similarity = 1 - (distance / 2)
                    similarity = max(0, min(1, similarity))

                    file_id = metadata.get('file_id', 'unknown')
                    file_name = metadata.get('file_name', 'Unknown Document')
                    chunk_index = metadata.get('chunk_index', 0)

                    # Group by file
                    if file_id not in seen_files:
                        processed_results.append({
                            'file_id': file_id,
                            'file_name': file_name,
                            'chunks': []
                        })
                        seen_files.add(file_id)

                    # Find file result and add chunk
                    file_result = next((r for r in processed_results if r['file_id'] == file_id), None)
                    if file_result:
                        file_result['chunks'].append({
                            'text': doc,
                            'similarity': round(similarity, 3),
                            'chunk_index': chunk_index
                        })

            # Limit results
            processed_results = processed_results[:search_limit]

            return {
                'query': query,
                'results': processed_results,
                'total_results': len(processed_results)
            }

        except Exception as e:
            print(f"❌ Error searching documents: {e}")
            return {'query': query, 'results': [], 'total_results': 0}

    def delete_document(self, file_id: str) -> bool:
        """Delete semua chunks untuk dokumen"""
        try:
            collection = self.get_or_create_collection()
            if not collection:
                return False

            # Find dan delete all items dengan file_id ini
            results = collection.get(
                where={"file_id": file_id}
            )

            if results['ids']:
                collection.delete(ids=results['ids'])
                print(f"✅ Deleted {len(results['ids'])} chunks for file {file_id}")
                return True

            return False

        except Exception as e:
            print(f"❌ Error deleting document: {e}")
            return False

    def update_document(self,
                       file_id: str,
                       file_name: str,
                       chunks: List[str],
                       metadata: Dict = None) -> bool:
        """Update dokumen (delete old + add new)"""
        self.delete_document(file_id)
        return self.add_document_chunks(file_id, file_name, chunks, metadata)

    def get_collection_stats(self) -> Dict:
        """Get statistics tentang collection"""
        try:
            collection = self.get_or_create_collection()
            if not collection:
                return {}

            count = collection.count()

            # Get unique files
            all_items = collection.get()
            file_ids = set()
            if all_items['metadatas']:
                for metadata in all_items['metadatas']:
                    file_ids.add(metadata.get('file_id', 'unknown'))

            return {
                'total_chunks': count,
                'total_documents': len(file_ids),
                'model': 'paraphrase-multilingual-MiniLM-L12-v2',
                'collection_name': collection.name,
                'server': 'Chroma Cloud' if self.use_cloud else 'Local',
                'host': self.cloud_host if self.use_cloud else 'localhost'
            }

        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}

    def persist(self):
        """Manually persist to disk (local only)"""
        if self.use_cloud:
            print("ℹ️ Chroma Cloud auto-persists, no action needed")
            return

        try:
            self.client.persist()
            print("✅ Local Chroma data persisted to disk")
        except Exception as e:
            print(f"⚠️  Error persisting: {e}")

    def is_healthy(self) -> bool:
        """Check jika connection sehat"""
        try:
            collection = self.get_or_create_collection()
            return collection is not None
        except:
            return False


# Global instance
_vector_store = None


def get_vector_store() -> ChromaVectorStore:
    """Get global ChromaVectorStore instance"""
    global _vector_store
    if _vector_store is None:
        # Load configuration dari environment
        use_cloud = os.getenv('CHROMA_CLOUD', 'true').lower() == 'true'

        if use_cloud:
            _vector_store = ChromaVectorStore(use_cloud=True)
        else:
            _vector_store = ChromaVectorStore(use_cloud=False)

    return _vector_store


def initialize_vector_store(use_cloud: bool = True, **kwargs) -> ChromaVectorStore:
    """Initialize global vector store"""
    global _vector_store
    _vector_store = ChromaVectorStore(use_cloud=use_cloud, **kwargs)
    return _vector_store

