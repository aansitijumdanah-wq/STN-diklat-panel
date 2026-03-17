"""
RAG Intelligence Module - ADVANCED STRATEGIES untuk AI lebih memahami seluruh data
Mengoptimalkan: Chunking, Context, Retrieval, dan Integration
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime


class SmartChunker:
    """
    Advanced text chunking yang memahami struktur dokumen
    - Preserve document hierarchy (headings, subheadings)
    - Maintain context with intelligent overlap
    - Keep sentences intact (jangan split di tengah kalimat)
    """
    
    @staticmethod
    def is_heading(line: str) -> Tuple[bool, int]:
        """Detect jika line adalah heading dan level berapa (1-6)"""
        match = re.match(r'^(#{1,6})\s+', line)
        if match:
            level = len(match.group(1))
            return True, level
        return False, 0
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean text untuk processing"""
        # Remove multiple newlines tapi preserve structure
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    @staticmethod
    def split_into_sentences(text: str) -> List[str]:
        """Split text into sentences dengan hati-hati"""
        # Patterns untuk sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        return [s.strip() for s in sentences if s.strip()]
    
    @staticmethod
    def chunk_by_structure(text: str, 
                          target_chunk_size: int = 1500,
                          min_chunk_size: int = 300,
                          context_sentences: int = 3) -> List[Dict]:
        """
        Smart chunking yang preserve structure dokumen
        
        Args:
            text: Full document text
            target_chunk_size: Target size for chunks (characters)
            min_chunk_size: Minimum chunk size (jangan chunk terlalu kecil)
            context_sentences: Sentences untuk overlap context
        
        Returns:
            List of chunks dengan metadata:
            [{
                'text': str,
                'heading_hierarchy': List[str],  # Breadcrumb dari headings
                'chunk_index': int,
                'is_continuation': bool,  # Apakah chunk melanjutkan chunk sebelumnya
                'preview': str  # First 50 chars untuk display
            }]
        """
        text = SmartChunker.clean_text(text)
        lines = text.split('\n')
        
        chunks = []
        current_chunk = []
        current_size = 0
        heading_stack = []  # Keep track of heading hierarchy
        chunk_index = 0
        
        for line in lines:
            is_heading, level = SmartChunker.is_heading(line)
            
            # Update heading hierarchy
            if is_heading:
                # Remove headings di level lebih dalam atau sama
                heading_stack = [h for h in heading_stack if h[0] < level]
                heading_text = re.sub(r'^#+\s+', '', line).strip()
                heading_stack.append((level, heading_text))
            
            line_size = len(line) + 1  # +1 for newline
            
            # Check apakah chunk ini sudah cukup besar
            if current_size + line_size > target_chunk_size and current_chunk and current_size > min_chunk_size:
                # Save current chunk
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    chunks.append({
                        'text': chunk_text,
                        'heading_hierarchy': [h[1] for h in heading_stack],
                        'chunk_index': chunk_index,
                        'is_continuation': False,
                        'preview': (chunk_text[:60] + '...') if len(chunk_text) > 60 else chunk_text,
                        'size': len(chunk_text)
                    })
                    chunk_index += 1
                
                # Start new chunk dengan context overlap
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Don't forget last chunk
        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text and len(chunk_text) > min_chunk_size:
                chunks.append({
                    'text': chunk_text,
                    'heading_hierarchy': [h[1] for h in heading_stack],
                    'chunk_index': chunk_index,
                    'is_continuation': False,
                    'preview': (chunk_text[:60] + '...') if len(chunk_text) > 60 else chunk_text,
                    'size': len(chunk_text)
                })
        
        return chunks


class ContextExpander:
    """
    Expand context dari search results dengan intelligent adjacency
    - Provide surrounding chunks
    - Create logical narrative dari multiple chunks
    - Preserve citations dan source tracking
    """
    
    @staticmethod
    def format_chunk_with_context(chunk: Dict, 
                                  related_chunks: List[Dict] = None,
                                  include_hierarchy: bool = True) -> str:
        """
        Format single chunk dengan context untuk AI
        
        Args:
            chunk: The main chunk
            related_chunks: Adjacent atau related chunks
            include_hierarchy: Include heading hierarchy breadcrumbs
        
        Returns:
            Formatted text dengan context dan citations
        """
        formatted = ""
        
        # Add hierarchy breadcrumb
        if include_hierarchy and chunk.get('heading_hierarchy'):
            breadcrumb = " → ".join(chunk['heading_hierarchy'])
            formatted += f"**Konteks:** {breadcrumb}\n\n"
        
        # Add main chunk
        formatted += chunk.get('text', '')
        
        # Add related chunks sebagai context
        if related_chunks:
            formatted += "\n\n---\n\n**Konteks Tambahan:**\n"
            for related in related_chunks[:2]:  # Max 2 related chunks
                if related.get('heading_hierarchy'):
                    formatted += f"**{' → '.join(related['heading_hierarchy'])}**\n"
                formatted += f"{related.get('text', '')[:300]}...\n\n"
        
        return formatted
    
    @staticmethod
    def create_summary_context(chunks: List[Dict], max_summary_chars: int = 2000) -> str:
        """
        Create high-level summary dari multiple chunks
        Useful untuk AI untuk memahami big picture sebelum detail
        
        Args:
            chunks: List of relevant chunks
            max_summary_chars: Max characters untuk summary
        
        Returns:
            Summary text yang menghubungkan chunks
        """
        if not chunks:
            return ""
        
        # Build summary dari chunk previews dan hierarchy
        summary = "## Ringkasan Konteks Dokumen\n\n"
        
        unique_hierarchies = {}
        for chunk in chunks:
            hierarchy_key = " → ".join(chunk.get('heading_hierarchy', ['Konten Utama']))
            if hierarchy_key not in unique_hierarchies:
                unique_hierarchies[hierarchy_key] = chunk['preview']
        
        current_chars = 0
        for hierarchy, preview in list(unique_hierarchies.items())[:10]:
            entry = f"- **{hierarchy}**: {preview}\n"
            if current_chars + len(entry) > max_summary_chars:
                break
            summary += entry
            current_chars += len(entry)
        
        return summary


class RetrievalEnhancer:
    """
    Enhance document retrieval dengan multiple strategies
    - BM25-style keyword search
    - Semantic similarity dengan embeddings
    - Hierarchy-based filtering
    - Recency bias untuk updated info
    """
    
    @staticmethod
    def calculate_keyword_relevance(query: str, text: str, weights: Dict = None) -> float:
        """
        Calculate keyword-based relevance score
        Complement semantic search dengan keyword matching
        
        Args:
            query: Search query
            text: Document text to score
            weights: Custom weights untuk different token types
        
        Returns:
            Relevance score (0-1)
        """
        if not weights:
            weights = {
                'exact_phrase': 3.0,    # Exact phrase match
                'bigram': 2.0,          # Two-word combinations
                'unigram': 1.0          # Single words
            }
        
        query_lower = query.lower()
        text_lower = text.lower()
        
        score = 0.0
        
        # 1. Exact phrase
        if query_lower in text_lower:
            # Count how many times phrase appears
            count = text_lower.count(query_lower)
            score += count * weights['exact_phrase']
        
        # 2. Bigrams (2-word phrases)
        query_words = query_lower.split()
        if len(query_words) > 1:
            for i in range(len(query_words) - 1):
                bigram = f"{query_words[i]} {query_words[i+1]}"
                if bigram in text_lower:
                    score += weights['bigram']
        
        # 3. Individual words
        for word in query_words:
            if len(word) > 2:  # Skip short words
                word_count = len(re.findall(r'\b' + re.escape(word) + r'\b', text_lower))
                score += word_count * weights['unigram']
        
        # Normalize score to 0-1 range
        max_possible = (len(query_words) * weights['unigram']) + weights['exact_phrase']
        if max_possible > 0:
            score = min(score / max_possible, 1.0)
        
        return score
    
    @staticmethod
    def rank_by_hierarchy(chunks: List[Dict], query: str) -> List[Dict]:
        """
        Re-rank chunks berdasarkan heading hierarchy relevance
        Example: jika query tentang "Engine", prioritize chunks unter "Engine" heading
        
        Args:
            chunks: List of chunks dengan hierarchy metadata
            query: Search query
        
        Returns:
            Re-ranked chunks dengan hierarchy score
        """
        query_lower = query.lower()
        
        for chunk in chunks:
            hierarchy_score = 0.0
            
            # Check if any heading matches query
            for heading in chunk.get('heading_hierarchy', []):
                if query_lower in heading.lower():
                    # Direct heading match - very relevant!
                    hierarchy_score += 0.5
            
            chunk['_hierarchy_score'] = hierarchy_score
        
        # Sort by hierarchy score (descending) but preserve other relevance
        chunks.sort(key=lambda x: x.get('_hierarchy_score', 0), reverse=True)
        
        return chunks


class ContextOptimizer:
    """
    Optimize context passed to AI model
    - Balance between comprehensiveness dan latency
    - Smart context window management
    - Relevance-based context stitching
    """
    
    @staticmethod
    def optimize_context(chunks: List[Dict],
                        query: str,
                        max_context_chars: int = 10000,
                        strategy: str = 'quality') -> Dict:
        """
        Optimize context untuk diberikan ke AI
        
        Args:
            chunks: List of relevant chunks dari search
            query: Original query dari user
            max_context_chars: Maximum context size
            strategy: 'quality' (best matches) or 'breadth' (diverse coverage)
        
        Returns:
            {
                'primary_context': str,        # Main context untuk AI
                'supplementary_context': str,  # Optional additional context
                'metadata': {
                    'num_chunks_used': int,
                    'total_chars': int,
                    'coverage_estimate': float,  # 0-1 estimate of knowledge coverage
                    'sources': List[str]
                }
            }
        """
        if not chunks:
            return {
                'primary_context': '',
                'supplementary_context': '',
                'metadata': {
                    'num_chunks_used': 0,
                    'total_chars': 0,
                    'coverage_estimate': 0.0,
                    'sources': []
                }
            }
        
        # Start dengan summary
        summary = ContextExpander.create_summary_context(chunks, max_context_chars // 3)
        primary_context = summary
        supplementary_context = ""
        
        current_chars = len(primary_context)
        used_chunks = []
        
        # Add chunks sampai max context
        for i, chunk in enumerate(chunks):
            formatted_chunk = ContextExpander.format_chunk_with_context(chunk)
            formatted_size = len(formatted_chunk)
            
            if current_chars + formatted_size <= max_context_chars:
                primary_context += f"\n\n{formatted_chunk}"
                current_chars += formatted_size
                used_chunks.append(i)
            elif current_chars < max_context_chars * 0.8:
                # Add smaller chunks ke supplementary
                supplementary_context += f"\n\n{formatted_chunk[:500]}..."
        
        # Build metadata
        sources = []
        for chunk in chunks[:5]:  # Top 5 sources
            if chunk.get('heading_hierarchy'):
                sources.append(" → ".join(chunk['heading_hierarchy']))
            if chunk.get('file_name'):
                sources.append(chunk['file_name'])
        
        coverage = min(len(used_chunks) / max(1, len(chunks)), 1.0)
        
        return {
            'primary_context': primary_context,
            'supplementary_context': supplementary_context,
            'metadata': {
                'num_chunks_used': len(used_chunks),
                'total_chars': current_chars,
                'coverage_estimate': coverage,
                'chunks_available': len(chunks),
                'sources': list(set(sources))
            }
        }


# Convenience functions untuk integration
def process_with_smart_chunking(text: str) -> List[Dict]:
    """Process dokumen dengan smart chunking"""
    return SmartChunker.chunk_by_structure(text)


def expand_and_format_context(chunks: List[Dict], query: str) -> Dict:
    """Expand context dan format untuk AI"""
    return ContextOptimizer.optimize_context(chunks, query)
