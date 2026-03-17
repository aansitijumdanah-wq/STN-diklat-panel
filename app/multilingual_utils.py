"""
Simple Multilingual Chunking Helper
Menambahkan language metadata ke existing chunks tanpa mengubah Chroma storage
"""

from typing import List, Dict, Optional
import re
from datetime import datetime

def add_multilingual_metadata_to_chunks(chunks: List[Dict], 
                                        source_language: str = 'en',
                                        target_language: str = 'id') -> List[Dict]:
    """
    Tambahkan language metadata ke chunk yang sudah ada
    Menggunakan existing SmartChunker output dari rag_intelligence.py
    
    Input: Chunks dari SmartChunker.chunk_by_structure()
    Output: Same chunks dengan tambahan language metadata
    
    Usage:
    >>> chunks = smart_chunker.chunk_by_structure(text)
    >>> chunks_with_metadata = add_multilingual_metadata_to_chunks(chunks)
    >>> # Sekarang chunks siap untuk multilingual RAG
    """
    
    for chunk in chunks:
        # Tambahkan language info
        chunk['source_language'] = source_language
        chunk['target_language'] = target_language
        
        # Extract technical terms untuk preservation
        chunk['technical_terms'] = extract_technical_terms(chunk['text'])
        
        # Add metadata untuk translation
        chunk['metadata'] = chunk.get('metadata', {})
        chunk['metadata'].update({
            'source_language': source_language,
            'target_language': target_language,
            'supports_indonesian_translation': True,
            'preserve_terms': chunk['technical_terms'][:10],  # Top 10 terms
            'chunk_language': source_language,
            'domain': extract_domain(chunk['text'])
        })
    
    return chunks


def extract_technical_terms(text: str) -> List[str]:
    """Extract technical terms dari text untuk preservation dalam translation"""
    
    patterns = {
        'acronyms': r'\b[A-Z]{2,}\b',  # ECU, OEM, EFI, dll
        'product_codes': r'\b[A-Z]\d+[A-Z]*\d*\b',  # ZX2, KW4, etc
        'measurements': r'\d+\s*(?:nm|rmin|psi|kg|mm|cm|inches?)',
    }
    
    terms = set()
    
    for pattern_name, pattern in patterns.items():
        matches = re.findall(pattern, text)
        terms.update(matches)
    
    return list(terms)


def extract_domain(text: str) -> str:
    """Detect domain dari text (automotive, electrical, mechanical, etc)"""
    
    domain_keywords = {
        'automotive': ['engine', 'fueling', 'ignition', 'transmission', 'brake', 'suspension', 'wheel'],
        'electrical': ['circuit', 'voltage', 'amperage', 'battery', 'alternator', 'starter'],
        'mechanical': ['bearing', 'gear', 'shaft', 'coupling', 'clutch', 'flywheel'],
        'hydraulic': ['pump', 'pressure', 'hose', 'valve', 'cylinder'],
    }
    
    text_lower = text.lower()
    
    for domain, keywords in domain_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            return domain
    
    return 'general'


# ============================================================================
# EXAMPLE USAGE IN EXISTING CODE
# ============================================================================

def example_integration_with_existing_rag():
    """
    Cara integrate ke existing SmartChunker dalam rag_intelligence.py
    Minimal changes, maximum benefit
    """
    
    from app.rag_intelligence import SmartChunker
    
    # Step 1: Chunk dokumen seperti biasa
    chunker = SmartChunker()
    text = """
    Engine Ignition System Diagnosis
    
    The ignition system consists of spark plugs, ignition coil, and ECU.
    When diagnosing misfire, check electrode gap first (0.8-1.0mm).
    Common problems include carbon buildup and worn spark plugs.
    """
    
    chunks = chunker.chunk_by_structure(text)
    
    # Step 2: Tambahkan language metadata (NEW!)
    chunks = add_multilingual_metadata_to_chunks(chunks)
    
    # Step 3: Sekarang chunks siap untuk multilingual search & translation
    for chunk in chunks:
        print(f"Chunk {chunk['chunk_index']}:")
        print(f"  Domain: {chunk['metadata']['domain']}")
        print(f"  Terms to preserve: {chunk['metadata']['preserve_terms']}")
        print(f"  Text: {chunk['text'][:100]}...")
    
    return chunks


# ============================================================================
# FOR CHROMA STORAGE: Metadata yang akan di-store
# ============================================================================

"""
RECOMMENDED Metadata untuk store ke Chroma Cloud:

{
    'chunk_index': int,
    'heading_hierarchy': List[str],
    'source_language': 'en',
    'target_language': 'id',
    'domain': 'automotive',  # atau electrical, mechanical, etc
    'technical_terms': ['ECU', 'OEM', 'spark plug', ...],
    'preserve_terms': ['ECU', 'OEM', 'spark plug'],  # Top N terms
    'supports_indonesian_translation': true,
    'chunk_language': 'en',
    'created_at': '2026-03-10T10:30:00Z',
    'source_file': 'technical_manual_v2.pdf',
    'domain_category': 'workshop_training'
}

Ini akan di-store sebagai metadatas di Chroma ketika Anda add documents.
"""
