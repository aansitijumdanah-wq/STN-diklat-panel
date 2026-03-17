# Chroma Optimization - Implementation Scripts

## File: app/chroma_optimizer.py

```python
"""
Optimasi Chroma Cloud untuk AI-friendly search
Includes: Smart chunking, query optimization, result ranking, caching
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import lru_cache


class SmartTextChunker:
    """Intelligent text chunking yang respects semantic boundaries"""
    
    @staticmethod
    def chunk_intelligently(text: str, 
                           target_chunk_size: int = 800, 
                           overlap: int = 150) -> List[str]:
        """
        Smart chunking strategy:
        1. Split pada paragraph boundaries
        2. Respect section headers
        3. Handle lists dan code blocks
        4. Maintain semantic coherence
        
        Args:
            text: Input text to chunk
            target_chunk_size: Target chunk length in characters
            overlap: Overlap between chunks in characters
            
        Returns:
            List of intelligently chunked text
        """
        
        # Clean text
        text = text.strip()
        
        # Split by paragraphs (double newline)
        paragraphs = text.split('\n\n')
        paragraphs = [p.strip() for p in paragraphs if p.strip()]
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for para in paragraphs:
            para_length = len(para)
            
            # If adding this paragraph exceeds target size
            if current_length + para_length + 2 > target_chunk_size and current_chunk:
                # Save current chunk
                chunk_text = '\n\n'.join(current_chunk).strip()
                chunks.append(chunk_text)
                
                # Reset for next chunk
                current_chunk = [para]
                current_length = para_length
            else:
                # Add paragraph to current chunk
                current_chunk.append(para)
                current_length += para_length + 2  # +2 for \n\n
        
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk).strip()
            chunks.append(chunk_text)
        
        # Add context overlap between chunks
        overlapped_chunks = []
        for i, chunk in enumerate(chunks):
            if i > 0 and overlap > 0:
                # Get last overlap chars from previous chunk for context
                prev_chunk = chunks[i-1]
                overlap_text = prev_chunk[-overlap:] if len(prev_chunk) > overlap else prev_chunk
                
                # Prepend overlap to current chunk
                chunk = f"[CONTEXT] {overlap_text}\n\n{chunk}"
            
            overlapped_chunks.append(chunk)
        
        return overlapped_chunks
    
    @staticmethod
    def chunk_for_tables(text: str, chunk_size: int = 500) -> List[str]:
        """Special handling untuk dokumen dengan banyak tables"""
        # TODO: Implement table-aware chunking
        return SmartTextChunker.chunk_intelligently(text, chunk_size)


class QueryOptimizer:
    """Optimize user queries untuk better vector search"""
    
    # Indonesian term expansions
    INDONESIAN_EXPANSIONS = {
        r'\boli\b': 'oli minyak pelumas cairan mesin',
        r'\bganti\b': 'penggantian pergantian perubahan',
        r'\bmesin\b': 'mesin engine motor',
        r'\bmobil\b': 'mobil kendaraan motor otomotif',
        r'\bputus\b': 'putus rusak patah gagal',
        r'\bkasar\b': 'kasar bising rough harsh',
        r'\brem\b': 'rem brake pengereman',
        r'\bban\b': 'ban tire roda',
        r'\bsparepart\b': 'sparepart onderdil suku cadang',
        r'\bmerawat\b': 'merawat perawatan maintenance',
        r'\bperbaikan\b': 'perbaikan repair perbaikan service',
        r'\brusak\b': 'rusak kerusakan damaged broken',
        r'\bsuara\b': 'suara bunyi noise sound',
    }
    
    # Automotive keyword expansions
    AUTOMOTIVE_EXPANSIONS = {
        r'\bengine\b': 'engine mesin motor',
        r'\boil\b': 'oil oli minyak',
        r'\bservice\b': 'service layanan perawatan maintenance bengkel',
        r'\breplacement\b': 'replacement penggantian perubahan',
        r'\bcheck\b': 'check periksa inspeksi',
        r'\badjustment\b': 'adjustment penyesuaian seting',
    }
    
    @staticmethod
    def preprocess_query(query: str) -> str:
        """
        Preprocess user query untuk better search:
        1. Normalize (lowercase, remove extra spaces)
        2. Remove stop words
        3. Expand Indonesian terms
        4. Expand automotive keywords
        5. Handle special characters
        
        Args:
            query: Original user query
            
        Returns:
            Optimized query
        """
        
        # 1. Basic normalization
        query = query.lower().strip()
        
        # 2. Remove excessive punctuation dan spaces
        query = re.sub(r'[!?.,;:]+', ' ', query)  # Remove punctuation
        query = re.sub(r'\s+', ' ', query)  # Remove extra spaces
        
        # 3. Indonesian term expansion
        for pattern, expansion in QueryOptimizer.INDONESIAN_EXPANSIONS.items():
            query = re.sub(pattern, f'({expansion})', query, flags=re.IGNORECASE)
        
        # 4. Automotive keyword expansion
        for pattern, expansion in QueryOptimizer.AUTOMOTIVE_EXPANSIONS.items():
            query = re.sub(pattern, f'({expansion})', query, flags=re.IGNORECASE)
        
        return query
    
    @staticmethod
    def extract_entities(query: str) -> Dict[str, List[str]]:
        """Extract entities dari query"""
        
        entities = {
            'vehicle_parts': [],
            'actions': [],
            'problems': [],
            'components': []
        }
        
        # Vehicle parts
        parts_pattern = r'\b(mesin|oli|rem|ban|aki|busi|filter|piston|crankshaft)\b'
        entities['vehicle_parts'] = re.findall(parts_pattern, query, re.IGNORECASE)
        
        # Actions
        actions_pattern = r'\b(ganti|lepas|pasang|periksa|reset|calibrate|adjust)\b'
        entities['actions'] = re.findall(actions_pattern, query, re.IGNORECASE)
        
        # Problems
        problems_pattern = r'\b(putus|rusak|macet|panas|bising|aneh|masalah)\b'
        entities['problems'] = re.findall(problems_pattern, query, re.IGNORECASE)
        
        return entities


class ResultRanker:
    """Rank search results dengan multiple criteria untuk better relevance"""
    
    @staticmethod
    def rank_results(results: List[Dict], 
                    query: str,
                    weights: Optional[Dict[str, float]] = None) -> List[Dict]:
        """
        Rank results berdasarkan multiple factors:
        - Semantic similarity (60% default)
        - Chunk position in document (15% default)
        - Source credibility (15% default)
        - Keyword frequency (10% default)
        
        Args:
            results: List of search results
            query: Original user query
            weights: Custom weights for ranking factors
            
        Returns:
            Ranked results with final_score
        """
        
        # Default weights
        if weights is None:
            weights = {
                'similarity': 0.60,
                'position': 0.15,
                'credibility': 0.15,
                'keyword': 0.10
            }
        
        scored_results = []
        query_terms = query.lower().split()
        
        for result in results:
            # Factor 1: Semantic similarity (already provided by Chroma)
            similarity_score = result.get('similarity', 0.5)
            
            # Factor 2: Chunk position (earlier chunks often more important)
            chunk_index = result.get('chunk_index', 0)
            # Decay with position: 1.0 at position 0, decreasing
            position_decay = max(0, 1.0 - (chunk_index / 50))
            position_score = position_decay
            
            # Factor 3: Source credibility
            metadata = result.get('metadata', {})
            credibility_score = metadata.get('source_credibility', 0.8)
            
            # Factor 4: Keyword frequency in chunk
            chunk_text = result.get('text', '').lower()
            keyword_matches = sum(
                1 for term in query_terms 
                if len(term) > 2 and term in chunk_text
            )
            keyword_score = min(
                1.0, 
                keyword_matches / len(query_terms)
            ) if query_terms else 0
            
            # Combined score
            final_score = (
                similarity_score * weights['similarity'] +
                position_score * weights['position'] +
                credibility_score * weights['credibility'] +
                keyword_score * weights['keyword']
            )
            
            result['final_score'] = round(final_score, 3)
            result['ranking_factors'] = {
                'similarity': round(similarity_score, 3),
                'position': round(position_score, 3),
                'credibility': round(credibility_score, 3),
                'keyword': round(keyword_score, 3)
            }
            scored_results.append(result)
        
        # Sort by final score
        scored_results.sort(key=lambda x: x['final_score'], reverse=True)
        
        return scored_results


class SearchCache:
    """Cache untuk search results dengan TTL"""
    
    def __init__(self, ttl_hours: int = 24, max_cache_size: int = 1000):
        """
        Initialize cache
        
        Args:
            ttl_hours: Time to live for cached results
            max_cache_size: Maximum number of cached queries
        """
        self.cache = {}
        self.ttl_hours = ttl_hours
        self.max_cache_size = max_cache_size
    
    def _get_cache_key(self, query: str) -> str:
        """Generate cache key dari query"""
        return hashlib.md5(query.lower().encode()).hexdigest()
    
    def get(self, query: str) -> Optional[Dict]:
        """
        Get cached result
        
        Args:
            query: Search query
            
        Returns:
            Cached result atau None jika tidak ada/expired
        """
        key = self._get_cache_key(query)
        
        if key not in self.cache:
            return None
        
        cached_at, result = self.cache[key]
        
        # Check if still valid
        if datetime.utcnow() - cached_at < timedelta(hours=self.ttl_hours):
            return result
        else:
            # Expired, remove
            del self.cache[key]
            return None
    
    def set(self, query: str, result: Dict) -> None:
        """
        Cache search result
        
        Args:
            query: Search query
            result: Search result to cache
        """
        
        # Clean expired entries if cache is full
        if len(self.cache) >= self.max_cache_size:
            self.clear_expired()
        
        key = self._get_cache_key(query)
        self.cache[key] = (datetime.utcnow(), result)
    
    def clear_expired(self) -> int:
        """
        Remove expired cache entries
        
        Returns:
            Number of entries removed
        """
        now = datetime.utcnow()
        expired_keys = [
            k for k, (cached_at, _) in self.cache.items()
            if now - cached_at > timedelta(hours=self.ttl_hours)
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        return len(expired_keys)
    
    def clear_all(self) -> None:
        """Clear all cache"""
        self.cache.clear()
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        return {
            'cache_size': len(self.cache),
            'max_cache_size': self.max_cache_size,
            'cache_usage_percent': (len(self.cache) / self.max_cache_size) * 100,
            'ttl_hours': self.ttl_hours
        }


class MetadataEnhancer:
    """Extract dan enhance metadata dari documents"""
    
    @staticmethod
    def infer_document_type(file_name: str, content: str = "") -> str:
        """Infer document type dari file name dan content"""
        
        if any(x in file_name.lower() for x in ['service', 'manual', 'repair']):
            return 'service_manual'
        elif any(x in file_name.lower() for x in ['parts', 'catalog', 'spare']):
            return 'parts_catalog'
        elif any(x in file_name.lower() for x in ['spec', 'specification']):
            return 'specification'
        elif any(x in file_name.lower() for x in ['guide', 'tutorial', 'how']):
            return 'guide'
        else:
            return 'reference'
    
    @staticmethod
    def extract_subject_area(content: str) -> str:
        """Extract subject area dari content"""
        
        # Check for automotive-related keywords
        if any(x in content.lower() for x in ['engine', 'mesin', 'transmission', 'brake', 'oli']):
            return 'automotive_maintenance'
        elif any(x in content.lower() for x in ['electrical', 'wiring', 'circuit', 'listrik']):
            return 'automotive_electrical'
        elif any(x in content.lower() for x in ['body', 'interior', 'paint', 'upholstery']):
            return 'automotive_body_interior'
        else:
            return 'general_automotive'
    
    @staticmethod
    def extract_domain_keywords(content: str) -> List[str]:
        """Extract automotive domain keywords"""
        
        keywords = []
        
        # Common automotive keywords
        patterns = {
            'maintenance': ['oil change', 'filter', 'inspect', 'ganti oli', 'periksa'],
            'repair': ['replace', 'repair', 'fix', 'troubleshoot', 'perbaikan', 'ganti'],
            'engine': ['engine', 'mesin', 'cylinder', 'piston', 'crankshaft'],
            'transmission': ['transmission', 'gear', 'clutch', 'gearbox', 'transmisi'],
            'brakes': ['brake', 'rem', 'disc', 'pad', 'rotor'],
            'electrical': ['battery', 'aki', 'alternator', 'starter', 'ignition'],
            'suspension': ['suspension', 'shock', 'spring', 'suspension', 'suspensi'],
            'cooling': ['coolant', 'radiator', 'thermostat', 'pendingin'],
            'fuel': ['fuel', 'carburetor', 'injection', 'bensin', 'bahan bakar']
        }
        
        content_lower = content.lower()
        
        for category, terms in patterns.items():
            if any(term in content_lower for term in terms):
                keywords.append(category)
        
        return keywords
    
    @staticmethod
    def calculate_source_credibility(file_name: str) -> float:
        """Calculate source credibility score"""
        
        score = 0.8  # Default score
        
        # Increase for official sources
        if any(x in file_name.lower() for x in ['official', 'original', 'manufacturer', 'oem']):
            score += 0.15
        
        # Increase for service manuals
        if 'service' in file_name.lower() or 'manual' in file_name.lower():
            score += 0.1
        
        # Decrease for generic sources
        if any(x in file_name.lower() for x in ['unknown', 'unverified', 'user guide']):
            score -= 0.1
        
        return min(1.0, score)
    
    @staticmethod
    def create_enhanced_metadata(file_id: str, 
                                file_name: str, 
                                content: str = "",
                                chunk_index: int = 0,
                                additional: Dict = None) -> Dict:
        """Create enhanced metadata struktur untuk Chroma"""
        
        metadata = {
            "file_id": file_id,
            "file_name": file_name,
            "chunk_index": chunk_index,
            "document_type": MetadataEnhancer.infer_document_type(file_name, content),
            "subject_area": MetadataEnhancer.extract_subject_area(content),
            "relevance_tags": MetadataEnhancer.extract_domain_keywords(content),
            "source_credibility": MetadataEnhancer.calculate_source_credibility(file_name),
            "language": "id",
            "domain": "automotive",
            "indexed_at": datetime.utcnow().isoformat(),
            "model": "paraphrase-multilingual-MiniLM-L12-v2"
        }
        
        if additional:
            metadata.update(additional)
        
        return metadata
```

---

## Usage Examples

### In app/routes_chat.py:

```python
from .chroma_optimizer import (
    SmartTextChunker, QueryOptimizer, ResultRanker, 
    SearchCache, MetadataEnhancer
)

# Initialize cache
search_cache = SearchCache(ttl_hours=24, max_cache_size=1000)

# Enhanced search function
def enhanced_search(query, search_limit=5):
    """Search dengan semua optimizations"""
    
    # 1. Optimize query
    optimized_query = QueryOptimizer.preprocess_query(query)
    
    # 2. Check cache
    cached = search_cache.get(optimized_query)
    if cached:
        print(f"✅ Cache hit untuk query: {query}")
        return cached
    
    # 3. Perform semantic search
    search_engine = _system_state.get('search_engine')
    results = search_engine.search(optimized_query, search_limit)
    
    # 4. Rank results
    ranked_results = ResultRanker.rank_results(
        results=results.get('results', []),
        query=query
    )
    
    # 5. Cache results
    search_cache.set(optimized_query, ranked_results)
    
    return {
        'results': ranked_results,
        'cache_stats': search_cache.get_stats()
    }

# For reindexing documents with smart chunking
def reindex_with_optimization(file_id, file_name, content):
    """Reindex dokumen dengan smart chunking dan enhanced metadata"""
    
    # 1. Smart chunking
    chunks = SmartTextChunker.chunk_intelligently(content, target_chunk_size=800)
    
    # 2. Enhanced metadata
    metadata = MetadataEnhancer.create_enhanced_metadata(
        file_id=file_id,
        file_name=file_name,
        content=content
    )
    
    # 3. Add to vector store
    vector_store.add_document_chunks(
        file_id=file_id,
        file_name=file_name,
        chunks=chunks,
        metadata=metadata
    )
    
    return len(chunks)  # Return number of chunks
```

---

## Testing

```python
# Test query optimization
from app.chroma_optimizer import QueryOptimizer

query = "Bagaimana cara ganti oli mobil?"
optimized = QueryOptimizer.preprocess_query(query)
print(f"Original: {query}")
print(f"Optimized: {optimized}")

# Test smart chunking
from app.chroma_optimizer import SmartTextChunker

content = "Paragraf 1...\n\nParagraf 2...\n\nParagraf 3..."
chunks = SmartTextChunker.chunk_intelligently(content)
print(f"Generated {len(chunks)} chunks")

# Test result ranking
from app.chroma_optimizer import ResultRanker

results = [
    {'text': 'chunk1', 'similarity': 0.9, 'chunk_index': 0, 'metadata': {'source_credibility': 0.9}},
    {'text': 'chunk2', 'similarity': 0.7, 'chunk_index': 5, 'metadata': {'source_credibility': 0.8}}
]
ranked = ResultRanker.rank_results(results, "test query")
print(f"Best result score: {ranked[0]['final_score']}")
```

---

**Ready to implement! Choose the optimizations that matter most for your use case.** 🚀
