"""
Advanced Search & Integration Module
Memastikan AI selalu menemukan data dari Chroma Cloud dan Google Drive
Dengan fallback strategies dan aggressive matching
"""

import os
import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import time


class EnhancedChromaSearch:
    """
    Enhanced search untuk Chroma Cloud dengan multiple strategies
    - Primary: Semantic search dengan embeddings
    - Secondary: Keyword-based search
    - Tertiary: Broad category matching
    - Quaternary: Return all available if nothing else works
    """
    
    # MECHANIC SYNONYMS - Expand queries dengan bengkel terminology
    MECHANIC_SYNONYMS = {
        # Masalah Engine
        "mogok": ["tidak bisa start", "susah start", "tidak hidup", "starter berbunyi tapi tidak start"],
        "rpm tinggi": ["idle tinggi", "mesin rpm naik", "idle tidak stabil"],
        "rpm rendah": ["idle rendah", "mesin mati saat berhenti"],
        "mati saat berjalan": ["engine stall", "mesin mati di jalanan"],
        "boros bbm": ["konsumsi bbm tinggi", "galak bbm", "jelek bensin"],
        "tarikan tidak ada": ["performa menurun", "tenaga berkurang", "tidak kebut"],
        "berisik": ["mesin berisik", "knocking", "detonasi", "mesin kopong"],
        "asap hitam": ["exhaust hitam", "misfire", "pembakaran tidak sempurna"],
        "overheating": ["mesin panas", "coolant tinggi", "radiator panas"],
        
        # Masalah Transmisi
        "sulit ganti gigi": ["gigi susah masuk", "gear berat", "perpindahan berat"],
        "meloncat gigi": ["gigi loncat", "transmisi skipping"],
        "bocor minyak": ["oli tumpah", "leak"],
        "getaran transmisi": ["getaran saat perpindahan", "shudder"],
        
        # Masalah Suspensi/Steering
        "kemudi keras": ["steering berat", "setir berat"],
        "kemudi ringan": ["steering ringan", "setir ringan"],
        "bunyi dari suspensi": ["bunyi klonk", "suara dari bawah", "creaking"],
        "mobil turun": ["suspensi turun", "empuk"],
        
        # Masalah Brake
        "rem blong": ["rem tidak bekerja", "brake failure", "pedal lembek"],
        "rem bunyi": ["brake squeal", "rem berisik"],
        "rem panas": ["overheating brake", "brake fade"],
        "pedal berat": ["brake pedal keras", "rem keras"],
        
        # Masalah Listrik
        "aki mati": ["battery habis", "aki soak", "alternator tidak charge"],
        "lampu tidak nyala": ["light issue", "lampu mati"],
        "wiper tidak jalan": ["wiper issue"],
        "power window tidak fungsi": ["kaca otomatis tidak bekerja"],
        "ac tidak dingin": ["pendingin tidak bekerja", "ac mati"],
        
        # Masalah Umum
        "air radiator berkurang": ["leak coolant", "coolant habis"],
        "oli gelap": ["oli hitam", "oli kotor"],
        "spark plug": ["busi", "ignition"],
        "filter udara": ["air filter", "saringan udara"],
        "fuel pump": ["pompa bensin"],
        
        # Prosedur
        "tune up": ["servis rutin", "perawatan berkala", "overhaul kecil"],
        "general overhaul": ["GO", "overhaul total", "rebuild"],
        "ganti oli": ["oil change", "oil service"],
        
        # Komponen
        "bearing": ["laher", "main bearing", "connecting rod bearing"],
        "piston": ["piston ring"],
        "valve": ["katup", "intake valve", "exhaust valve"],
        "gasket": ["packing", "seal", "joint"],
        "timing belt": ["tali kampak", "serpentine belt"],
        "starter motor": ["motor starter"],
        "alternator": ["pengisi aki"],
        "ignition coil": ["koil pengapian"],
        "fuel injector": ["injector", "injeksi"],
    }
    
    def __init__(self, vector_store):
        """
        Initialize dengan existing vector store
        
        Args:
            vector_store: ChromaVectorStore instance
        """
        self.vector_store = vector_store
        self.search_history = []  # Log search attempts
        self.cache = {}  # Cache query results
    
    def _expand_query_with_synonyms(self, query: str) -> str:
        """Expand user query dengan mechanic synonyms untuk better search results"""
        expanded = query
        query_lower = query.lower()
        
        # Check each standard term's aliases
        for standard_term, aliases in self.MECHANIC_SYNONYMS.items():
            for alias in aliases:
                if alias.lower() in query_lower:
                    # Found an alias, add standard term jika belum ada
                    if standard_term.lower() not in query_lower:
                        expanded += f" {standard_term}"
                    break  # Found this term, move to next standard term
        
        return expanded
    
    def search_with_fallbacks(self, 
                             query: str,
                             search_limit: int = 3,
                             results_limit: int = 8,
                             force_include_results: bool = True) -> Dict:
        """
        Search dengan multiple fallback strategies
        Jaminkan selalu ada hasil kecuali collection truly empty
        
        Args:
            query: Search query
            search_limit: Max documents to search
            results_limit: Max chunks per search
            force_include_results: Force hasil bahkan dengan low confidence
        
        Returns:
            Search results dengan at least some chunks
        """
        
        # STEP 1: Expand query dengan mechanic synonyms
        expanded_query = self._expand_query_with_synonyms(query)
        if expanded_query != query:
            print(f"🔍 Query expanded: '{query}' → '{expanded_query}'")
        
        # Check cache first (gunakan expanded query)
        cache_key = f"{expanded_query}:{search_limit}:{results_limit}"
        if cache_key in self.cache:
            cached_result = self.cache[cache_key]
            if (datetime.utcnow() - cached_result['timestamp']).seconds < 300:  # 5 min cache
                return cached_result['result']
        
        results = {'query': query, 'results': [], 'search_strategy': 'initial', 'chunks_found': 0}
        
        # STRATEGY 1: Direct semantic search dengan query
        print(f"🔍 STRATEGY 1: Semantic search untuk '{query}'")
        strategy1_result = self._semantic_search(query, search_limit, results_limit)
        if strategy1_result['results']:
            results = strategy1_result
            results['search_strategy'] = 'semantic'
            self._cache_result(cache_key, results)
            return results
        
        # STRATEGY 2: Keyword-based search (boostkan relevance)
        print(f"🔍 STRATEGY 2: Keyword search")
        strategy2_result = self._keyword_search(query, search_limit, results_limit)
        if strategy2_result['results']:
            results = strategy2_result
            results['search_strategy'] = 'keyword'
            self._cache_result(cache_key, results)
            return results
        
        # STRATEGY 3: Broad category matching (extract main topics)
        print(f"🔍 STRATEGY 3: Category matching")
        strategy3_result = self._category_search(query, search_limit, results_limit)
        if strategy3_result['results']:
            results = strategy3_result
            results['search_strategy'] = 'category'
            self._cache_result(cache_key, results)
            return results
        
        # STRATEGY 4: Return recent/popular documents (if force_include_results)
        if force_include_results:
            print(f"🔍 STRATEGY 4: Fallback to recent documents")
            strategy4_result = self._get_recent_documents(results_limit)
            if strategy4_result['results']:
                results = strategy4_result
                results['search_strategy'] = 'fallback_recent'
                self._cache_result(cache_key, results)
                return results
        
        # STRATEGY 5: Last resort - return absolute all documents
        if force_include_results:
            print(f"🔍 STRATEGY 5: Fallback to ALL documents")
            strategy5_result = self._get_all_documents(results_limit)
            if strategy5_result['results']:
                results = strategy5_result
                results['search_strategy'] = 'fallback_all'
                self._cache_result(cache_key, results)
                return results
        
        # Log this search for debugging
        self._log_search(query, 'NO_RESULTS', None)
        
        return results
    
    def _semantic_search(self, query: str, search_limit: int, results_limit: int) -> Dict:
        """Semantic search using embeddings"""
        try:
            if not self.vector_store:
                return {'results': []}
            
            # Use existing search method jika ada
            if hasattr(self.vector_store, 'search_documents'):
                result = self.vector_store.search_documents(
                    query=query,
                    search_limit=search_limit,
                    results_limit=results_limit
                )
                return result
            
            return {'results': []}
        except Exception as e:
            print(f"⚠️  Semantic search error: {e}")
            return {'results': []}
    
    def _keyword_search(self, query: str, search_limit: int, results_limit: int) -> Dict:
        """
        Keyword-based search
        Extract key terms dan search untuk exact/partial matches
        """
        try:
            # Extract key terms dari query
            # Remove common words, extract meaningful terms
            stop_words = {'apa', 'yang', 'ini', 'untuk', 'dari', 'ke', 'di', 'adalah', 'dan', 'atau', 'ada'}
            keywords = [w.lower() for w in query.split() if w.lower() not in stop_words and len(w) > 2]
            
            if not keywords:
                return {'results': []}
            
            print(f"   Keywords extracted: {keywords}")
            
            # Try get all documents and filter
            if not self.vector_store or not self.vector_store.client:
                return {'results': []}
            
            try:
                # Get collection
                collection = self.vector_store.get_or_create_collection()
                if not collection:
                    return {'results': []}
                
                # Get all documents dengan default limit
                all_docs = collection.get(limit=results_limit * 5)
                
                if not all_docs or not all_docs.get('documents'):
                    return {'results': []}
                
                # Score documents by keyword presence
                scored_docs = []
                for idx, doc in enumerate(all_docs['documents']):
                    score = 0
                    for keyword in keywords:
                        # Exact phrase match
                        if keyword in doc.lower():
                            score += 3
                        # Partial match
                        elif any(keyword[:3] in word for word in doc.lower().split()):
                            score += 1
                    
                    if score > 0:
                        scored_docs.append({
                            'text': doc,
                            'metadata': all_docs['metadatas'][idx] if all_docs.get('metadatas') else {},
                            'score': score / 100  # Normalize
                        })
                
                # Sort by score descending
                scored_docs.sort(key=lambda x: x['score'], reverse=True)
                
                # Format as search results
                results = []
                for doc in scored_docs[:results_limit]:
                    results.append({
                        'text': doc['text'],
                        'chunk': doc['text'],
                        'similarity': doc['score'],
                        'file_name': doc['metadata'].get('file_name', 'Unknown'),
                        'file_id': doc['metadata'].get('file_id', '')
                    })
                
                return {
                    'query': query,
                    'results': [{'chunks': results, 'file_name': 'Multiple sources'}],
                    'total_results': len(results)
                }
            
            except Exception as e:
                print(f"   Keyword search error: {e}")
                return {'results': []}
        
        except Exception as e:
            print(f"⚠️  Keyword search error: {e}")
            return {'results': []}
    
    def _category_search(self, query: str, search_limit: int, results_limit: int) -> Dict:
        """
        Search berdasarkan kategori dokumen
        Extract main topic dan cari dokumen dalam kategori tersebut
        """
        try:
            # Common categories dalam dokumen mekanik
            categories = {
                'engine': ['mesin', 'engine', 'rpm', 'minyak', 'oli', 'karburator', 'carb'],
                'transmission': ['transmisi', 'gear', 'gigi', 'clutch', 'kopling'],
                'electrical': ['listrik', 'aki', 'baterai', 'alternator', 'starter'],
                'cooling': ['pendingin', 'radiator', 'coolant', 'kipas', 'fan', 'coolant'],
                'brake': ['rem', 'brake', 'brek', 'disc', 'pad'],
                'maintenance': ['perawatan', 'maintenance', 'servis', 'service', 'service interval'],
                'parts': ['suku cadang', 'spare parts', 'komponen', 'part', 'component']
            }
            
            # Detect category dari query
            query_lower = query.lower()
            detected_category = None
            
            for category, keywords in categories.items():
                if any(kw in query_lower for kw in keywords):
                    detected_category = category
                    print(f"   Category detected: {category}")
                    break
            
            if not detected_category:
                return {'results': []}
            
            # Get all documents dan filter by category
            if not self.vector_store or not self.vector_store.client:
                return {'results': []}
            
            collection = self.vector_store.get_or_create_collection()
            if not collection:
                return {'results': []}
            
            # Get documents
            all_docs = collection.get(limit=results_limit * 10)
            
            # Filter by category keywords
            category_keywords = categories[detected_category]
            filtered = []
            
            for idx, doc in enumerate(all_docs.get('documents', [])):
                if any(kw in doc.lower() for kw in category_keywords):
                    filtered.append({
                        'text': doc,
                        'metadata': all_docs['metadatas'][idx] if all_docs.get('metadatas') else {},
                        'doc_id': all_docs['ids'][idx] if all_docs.get('ids') else idx
                    })
            
            if filtered:
                results = []
                for doc in filtered[:results_limit]:
                    results.append({
                        'text': doc['text'],
                        'chunk': doc['text'],
                        'similarity': 0.7,  # Category match score
                        'file_name': doc['metadata'].get('file_name', 'Multiple sources'),
                        'file_id': doc['metadata'].get('file_id', '')
                    })
                
                return {
                    'query': query,
                    'results': [{'chunks': results, 'file_name': f'{detected_category} documents'}],
                    'total_results': len(results)
                }
            
            return {'results': []}
        
        except Exception as e:
            print(f"⚠️  Category search error: {e}")
            return {'results': []}
    
    def _get_recent_documents(self, limit: int) -> Dict:
        """Get recently indexed/updated documents as fallback"""
        try:
            if not self.vector_store or not self.vector_store.client:
                return {'results': []}
            
            collection = self.vector_store.get_or_create_collection()
            if not collection:
                return {'results': []}
            
            # Get recent documents (by ID order, assuming IDs are time-based)
            recent = collection.get(limit=limit)
            
            if not recent or not recent.get('documents'):
                return {'results': []}
            
            results = []
            for idx, doc in enumerate(recent['documents']):
                results.append({
                    'text': doc,
                    'chunk': doc,
                    'similarity': 0.5,  # Fallback score
                    'file_name': recent['metadatas'][idx].get('file_name', 'Recent document') if recent.get('metadatas') else 'Document',
                    'file_id': recent['metadatas'][idx].get('file_id', '') if recent.get('metadatas') else ''
                })
            
            return {
                'query': 'fallback_recent',
                'results': [{'chunks': results, 'file_name': 'Recent documents'}],
                'total_results': len(results)
            }
        
        except Exception as e:
            print(f"⚠️  Recent documents error: {e}")
            return {'results': []}
    
    def _get_all_documents(self, limit: int) -> Dict:
        """Get ALL documents - absolute fallback"""
        try:
            if not self.vector_store or not self.vector_store.client:
                return {'results': []}
            
            collection = self.vector_store.get_or_create_collection()
            if not collection:
                return {'results': []}
            
            # Get all
            all_docs = collection.get(limit=limit * 20)  # Get more since it's fallback
            
            if not all_docs or not all_docs.get('documents'):
                return {'results': []}
            
            results = []
            for idx, doc in enumerate(all_docs['documents']):
                results.append({
                    'text': doc[:1000],  # Truncate untuk efficiency
                    'chunk': doc,
                    'similarity': 0.3,  # Fallback score
                    'file_name': all_docs['metadatas'][idx].get('file_name', 'Document') if all_docs.get('metadatas') else 'Document',
                    'file_id': all_docs['metadatas'][idx].get('file_id', '') if all_docs.get('metadatas') else ''
                })
            
            return {
                'query': 'fallback_all',
                'results': [{'chunks': results, 'file_name': 'ALL available documents'}],
                'total_results': len(results),
                'note': 'Fallback: returning all available documents'
            }
        
        except Exception as e:
            print(f"⚠️  All documents error: {e}")
            return {'results': []}
    
    def _cache_result(self, key: str, result: Dict):
        """Cache search result"""
        self.cache[key] = {
            'result': result,
            'timestamp': datetime.utcnow()
        }
    
    def _log_search(self, query: str, strategy: str, result_count: Optional[int]):
        """Log search attempt untuk debugging"""
        self.search_history.append({
            'timestamp': datetime.utcnow().isoformat(),
            'query': query,
            'strategy': strategy,
            'results': result_count
        })
        
        # Keep only last 100 searches
        if len(self.search_history) > 100:
            self.search_history = self.search_history[-100:]
    
    def get_search_stats(self) -> Dict:
        """Get search statistics untuk debugging"""
        return {
            'total_searches': len(self.search_history),
            'cache_size': len(self.cache),
            'recent_searches': self.search_history[-10:] if self.search_history else []
        }


class GoogleDriveSyncEnforcer:
    """
    Ensure Google Drive sync selalu up-to-date
    - Check sync status
    - Force re-sync jika needed
    - Provide sync status to frontend
    """
    
    @staticmethod
    def ensure_drive_synced(root_folder_id: str = None, force_resync: bool = False) -> Dict:
        """
        Ensure Google Drive is synced to Chroma
        
        Args:
            root_folder_id: Root folder ID to sync
            force_resync: Force complete resync
        
        Returns:
            Status dict dengan sync info
        """
        try:
            # Import drive sync module
            from .drive_sync import sync_drive_files
            
            print("🔄 Ensuring Google Drive sync...")
            
            # Get status first
            status = {
                'synced': False,
                'last_sync': None,
                'documents_count': 0,
                'action_taken': 'none'
            }
            
            # Try sync
            if root_folder_id:
                start_time = datetime.utcnow()
                try:
                    result = sync_drive_files(root_folder_id)
                    status['last_sync'] = start_time.isoformat()
                    status['synced'] = True
                    status['documents_count'] = result.get('total_synced', 0) if result else 0
                    status['action_taken'] = 'synced'
                    print(f"✅ Sync complete. Documents: {status['documents_count']}")
                except Exception as e:
                    print(f"⚠️  Sync error: {e}")
                    status['error'] = str(e)
            
            return status
        
        except ImportError:
            print("⚠️  Drive sync module not available")
            return {
                'synced': False,
                'error': 'Drive sync module not available'
            }


# Convenience function untuk integrate ke routes
def create_enhanced_search(vector_store) -> EnhancedChromaSearch:
    """Create enhanced search instance"""
    return EnhancedChromaSearch(vector_store)
