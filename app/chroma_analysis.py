"""
Chroma Cloud Database Analysis & Optimization Guide
untuk DIKLAT-STN collection 'documents'
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# ============================================================================
# PART 1: DATABASE ANALYSIS TOOLS
# ============================================================================

class ChromaCollectionAnalyzer:
    """
    Analyze existing Chroma Cloud collection untuk memahami:
    - Total documents stored
    - Document quality dan structure
    - Language composition (if mixed)
    - Domain distribution
    - Gaps dalam knowledge base
    """
    
    def __init__(self, 
                 api_key: str = None,
                 database: str = 'DIKLAT-STN',
                 collection: str = 'documents'):
        """Initialize analyzer dengan Chroma Cloud connection"""
        
        try:
            import chromadb
            self.client = chromadb.CloudClient(api_key=api_key or os.getenv('CHROMA_API_KEY'))
            self.collection = self.client.get_collection(name=collection)
            self.db_name = database
            self.col_name = collection
            print(f"✅ Connected to Chroma Cloud")
            print(f"   Database: {database}")
            print(f"   Collection: {collection}")
        
        except Exception as e:
            print(f"❌ Error connecting to Chroma: {e}")
            self.client = None
            self.collection = None
    
    def get_collection_stats(self) -> Dict:
        """Get basic statistics tentang collection"""
        
        if not self.collection:
            return {}
        
        try:
            # Get all documents
            all_docs = self.collection.get(
                include=['documents', 'metadatas', 'distances'],
                limit=10000  # Chroma max limit per query
            )
            
            total_docs = self.collection.count()
            
            stats = {
                'total_documents': total_docs,
                'documents_retrieved': len(all_docs['documents']),
                'metadata_sample': all_docs['metadatas'][:3] if all_docs['metadatas'] else [],
                'avg_doc_length': sum(len(doc) for doc in all_docs['documents']) // len(all_docs['documents']) if all_docs['documents'] else 0,
                'vector_dimension': len(self.collection.get(limit=1)['embeddings'][0]) if self.collection.get(limit=1)['embeddings'] else 0
            }
            
            return stats
        
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {}
    
    def export_collection_sample(self, sample_size: int = 20) -> List[Dict]:
        """
        Export sample documents dari collection untuk review
        
        Gunakan untuk:
        - Quality check dokumen yang ada
        - Understand current structure
        - Check language composition
        - Identify gaps
        """
        
        if not self.collection:
            return []
        
        try:
            docs = self.collection.get(
                include=['documents', 'metadatas', 'ids'],
                limit=sample_size
            )
            
            samples = []
            for i, (doc_id, document, metadata) in enumerate(zip(
                docs['ids'],
                docs['documents'],
                docs.get('metadatas', [])
            )):
                samples.append({
                    'id': doc_id,
                    'preview': document[:200] + '...' if len(document) > 200 else document,
                    'length': len(document),
                    'metadata': metadata,
                    'detected_language': self._detect_language_simple(document)
                })
            
            return samples
        
        except Exception as e:
            print(f"❌ Error exporting sample: {e}")
            return []
    
    def analyze_document_quality(self) -> Dict:
        """Analyze quality dari documents dalam collection"""
        
        if not self.collection:
            return {}
        
        try:
            docs = self.collection.get(
                include=['documents'],
                limit=100  # Sample 100 for quality check
            )
            
            quality_metrics = {
                'total_sampled': len(docs['documents']),
                'avg_length': sum(len(d) for d in docs['documents']) / len(docs['documents']),
                'min_length': min(len(d) for d in docs['documents']),
                'max_length': max(len(d) for d in docs['documents']),
                'empty_docs': sum(1 for d in docs['documents'] if len(d.strip()) == 0),
                'quality_issues': {
                    'very_short': sum(1 for d in docs['documents'] if len(d) < 100),
                    'very_long': sum(1 for d in docs['documents'] if len(d) > 5000),
                }
            }
            
            return quality_metrics
        
        except Exception as e:
            print(f"❌ Error analyzing quality: {e}")
            return {}
    
    def test_multilingual_search(self) -> Dict[str, List]:
        """Test apakah search bekerja dengan Indonesian queries pada English docs"""
        
        if not self.collection:
            return {'error': 'Collection not available'}
        
        test_queries = {
            'english': [
                "spark plug replacement procedure",
                "engine ignition system",
                "maintenance schedule"
            ],
            'indonesian': [
                "cara mengganti busi",
                "sistem ignition engine",
                "jadwal maintenance"
            ]
        }
        
        results = {
            'english_queries': [],
            'indonesian_queries': [],
            'cross_language_working': False
        }
        
        try:
            # Test English queries
            for query in test_queries['english']:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=3
                )
                results['english_queries'].append({
                    'query': query,
                    'found': len(res['documents'][0]) if res['documents'] else 0,
                    'distances': res.get('distances', [[]])[0][:3] if res.get('distances') else []
                })
            
            # Test Indonesian queries
            for query in test_queries['indonesian']:
                res = self.collection.query(
                    query_texts=[query],
                    n_results=3
                )
                results['indonesian_queries'].append({
                    'query': query,
                    'found': len(res['documents'][0]) if res['documents'] else 0,
                    'distances': res.get('distances', [[]])[0][:3] if res.get('distances') else []
                })
            
            # Check if both work
            eng_working = any(r['found'] > 0 for r in results['english_queries'])
            id_working = any(r['found'] > 0 for r in results['indonesian_queries'])
            results['cross_language_working'] = eng_working and id_working
            
            return results
        
        except Exception as e:
            print(f"❌ Error testing multilingual search: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def _detect_language_simple(text: str) -> str:
        """Simple language detection based on character patterns"""
        
        # Indonesian indicator words
        id_indicators = ['yang', 'dan', 'di', 'ke', 'untuk', 'adalah', 'dengan']
        id_count = sum(1 for word in id_indicators if word in text.lower())
        
        # English indicator words
        en_indicators = ['the', 'and', 'is', 'are', 'in', 'to', 'of', 'for']
        en_count = sum(1 for word in en_indicators if word in text.lower())
        
        if id_count > en_count and id_count > 0:
            return 'id'
        elif en_count > id_count and en_count > 0:
            return 'en'
        else:
            return 'unknown'


# ============================================================================
# PART 2: OPTIMIZATION RECOMMENDATIONS
# ============================================================================

class ChromaOptimizationAdvisor:
    """
    Memberikan rekomendasi optimasi berdasarkan collection analysis
    """
    
    @staticmethod
    def analyze_and_recommend(stats: Dict, quality_metrics: Dict) -> Dict:
        """
        Analyze stats dan provide optimization recommendations
        """
        
        recommendations = {
            'storage_optimization': [],
            'search_optimization': [],
            'multilingual_setup': []
        }
        
        # Storage recommendations
        if quality_metrics.get('quality_issues', {}).get('very_short', 0) > 10:
            recommendations['storage_optimization'].append({
                'issue': 'Many very short documents detected',
                'action': 'Merge small chunks dengan neighbor chunks untuk better context',
                'priority': 'high'
            })
        
        if quality_metrics.get('quality_issues', {}).get('very_long', 0) > 10:
            recommendations['storage_optimization'].append({
                'issue': 'Many very long documents detected',
                'action': 'Re-chunk documents menggunakan SmartChunker dengan target 1500 chars',
                'priority': 'medium'
            })
        
        # Search recommendations
        recommendations['search_optimization'].append({
            'issue': 'Default Chroma embedding may not be optimal per domain',
            'action': 'Consider fine-tuning all-MiniLM-L6-v2 dengan domain-specific pairs',
            'priority': 'low',
            'effort': 'high',
            'benefit': 'Improved specificity dalam automotive domain'
        })
        
        # Multilingual recommendations
        recommendations['multilingual_setup'].append({
            'issue': 'Knowledge base English, users Indonesian',
            'action': 'Implement multilingual RAG pipeline (see MULTILINGUAL_KNOWLEDGE_BASE_STRATEGY.md)',
            'priority': 'high',
            'effort': 'medium',
            'benefit': 'Users dapat query dalam Indonesian, dapat jawaban dalam Indonesian'
        })
        
        recommendations['multilingual_setup'].append({
            'issue': 'No translation layer implemented',
            'action': 'Add LLM translation layer menggunakan Groq (sudah connected)',
            'priority': 'high',
            'effort': 'low',
            'benefit': 'Professional Indonesian responses dari English context'
        })
        
        return recommendations


# ============================================================================
# PART 3: QUICK START ANALYSIS SCRIPT
# ============================================================================

def run_database_analysis():
    """
    CLI-friendly script untuk analyze Chroma collection
    Run ini untuk understand existing setup
    
    Usage:
    python3 -c "from app.chroma_analysis import run_database_analysis; run_database_analysis()"
    """
    
    print("\n" + "="*70)
    print("🔍 CHROMA CLOUD DATABASE ANALYSIS")
    print("="*70 + "\n")
    
    # Initialize
    analyzer = ChromaCollectionAnalyzer()
    
    if not analyzer.collection:
        print("❌ Could not connect to collection. Check credentials.")
        return
    
    # Get stats
    print("\n📊 COLLECTION STATISTICS")
    print("-" * 70)
    stats = analyzer.get_collection_stats()
    print(f"Total documents: {stats.get('total_documents', 'N/A')}")
    print(f"Average document length: {stats.get('avg_doc_length', 'N/A')} characters")
    print(f"Vector dimension: {stats.get('vector_dimension', 'N/A')}D")
    
    # Sample documents
    print("\n📄 SAMPLE DOCUMENTS (First 5)")
    print("-" * 70)
    samples = analyzer.export_collection_sample(sample_size=5)
    for i, sample in enumerate(samples, 1):
        print(f"\n{i}. ID: {sample['id']}")
        print(f"   Length: {sample['length']} chars")
        print(f"   Detected Language: {sample['detected_language']}")
        print(f"   Preview: {sample['preview']}")
        if sample['metadata']:
            print(f"   Metadata: {json.dumps(sample['metadata'], indent=8)[:200]}...")
    
    # Quality analysis
    print("\n\n🔬 DOCUMENT QUALITY ANALYSIS")
    print("-" * 70)
    quality = analyzer.analyze_document_quality()
    print(f"Documents analyzed: {quality.get('total_sampled', 'N/A')}")
    print(f"Average length: {quality.get('avg_length', 0):.0f} characters")
    print(f"Min/Max length: {quality.get('min_length', 'N/A')} - {quality.get('max_length', 'N/A')}")
    print(f"Empty documents: {quality.get('empty_docs', 0)}")
    issues = quality.get('quality_issues', {})
    print(f"Very short docs (<100 chars): {issues.get('very_short', 0)}")
    print(f"Very long docs (>5000 chars): {issues.get('very_long', 0)}")
    
    # Multilingual test
    print("\n\n🌍 MULTILINGUAL SEARCH TEST")
    print("-" * 70)
    ml_test = analyzer.test_multilingual_search()
    
    print("\nEnglish Queries:")
    for res in ml_test.get('english_queries', [])[:3]:
        print(f"  Query: '{res['query']}' → Found: {res['found']} results")
    
    print("\nIndonesian Queries:")
    for res in ml_test.get('indonesian_queries', [])[:3]:
        print(f"  Query: '{res['query']}' → Found: {res['found']} results")
    
    if ml_test.get('cross_language_working'):
        print("\n✅ Cross-language search WORKING! Indonesian queries find English docs.")
    else:
        print("\n⚠️  Cross-language search may need optimization.")
    
    # Recommendations
    print("\n\n💡 OPTIMIZATION RECOMMENDATIONS")
    print("-" * 70)
    advisor = ChromaOptimizationAdvisor()
    recommendations = advisor.analyze_and_recommend(stats, quality)
    
    for category, recs in recommendations.items():
        print(f"\n{category.upper().replace('_', ' ')}:")
        for rec in recs:
            print(f"\n  Issue: {rec['issue']}")
            print(f"  Action: {rec['action']}")
            print(f"  Priority: {rec['priority']}")
            if 'effort' in rec:
                print(f"  Effort: {rec['effort']} | Benefit: {rec['benefit']}")
    
    print("\n" + "="*70 + "\n")


# ============================================================================
# SCRIPT EXECUTION GUIDE
# ============================================================================

"""
HOW TO USE THIS FILE:

1. BASIC ANALYSIS:
   python3 -c "from app.chroma_analysis import run_database_analysis; run_database_analysis()"

2. MANUAL ANALYSIS:
   from app.chroma_analysis import ChromaCollectionAnalyzer
   
   analyzer = ChromaCollectionAnalyzer()
   
   # Get basics
   stats = analyzer.get_collection_stats()
   print(f"Total docs: {stats['total_documents']}")
   
   # Sample documents
   samples = analyzer.export_collection_sample()
   for s in samples:
       print(s['preview'])
   
   # Quality check
   quality = analyzer.analyze_document_quality()
   print(f"Quality issues: {quality['quality_issues']}")
   
   # Test multilingual
   ml_results = analyzer.test_multilingual_search()
   print(f"Cross-language search working: {ml_results['cross_language_working']}")

3. OPTIMIZATION RECOMMENDATIONS:
   from app.chroma_analysis import ChromaOptimizationAdvisor
   
   advisor = ChromaOptimizationAdvisor()
   recs = advisor.analyze_and_recommend(stats, quality)
   
   for category, recommendations in recs.items():
       print(f"\n{category}:")
       for rec in recommendations:
           print(f"  - {rec['action']}")
"""

# ============================================================================
# Export Analysis Results to JSON
# ============================================================================

def export_analysis_to_json(filename: str = 'chroma_analysis_report.json') -> str:
    """
    Run analysis dan export results ke JSON file untuk record keeping
    """
    
    analyzer = ChromaCollectionAnalyzer()
    
    report = {
        'timestamp': datetime.utcnow().isoformat(),
        'database': 'DIKLAT-STN',
        'collection': 'documents',
        'statistics': analyzer.get_collection_stats(),
        'quality_metrics': analyzer.analyze_document_quality(),
        'sample_documents': analyzer.export_collection_sample(sample_size=10),
        'multilingual_test': analyzer.test_multilingual_search(),
        'recommendations': ChromaOptimizationAdvisor.analyze_and_recommend(
            analyzer.get_collection_stats(),
            analyzer.analyze_document_quality()
        )
    }
    
    # Save to file
    filepath = os.path.join(os.path.dirname(__file__), '..', filename)
    with open(filepath, 'w') as f:
        json.dump(report, f, indent=2, default=str)
    
    print(f"✅ Analysis exported to {filepath}")
    return filepath


if __name__ == '__main__':
    run_database_analysis()
