"""
QUICK START: Indonesian AI Interaction dengan English Knowledge Base
3 Simple Steps untuk setup multilingual RAG sekarang juga
"""

import os
from typing import List, Dict
from .groq_integration import GroqChatManager
from .chroma_integration import ChromaVectorStore

class QuickMultilingualRAG:
    """
    Minimal implementation untuk multilingual RAG
    English documents + Indonesian queries + Indonesian responses

    Ini adalah "quick win" sebelum full implementation
    """

    def __init__(self,
                 chroma_api_key: str = None,
                 groq_api_key: str = None):
        """Initialize dengan credentials dari environment"""

        # Groq untuk LLM
        self.groq = GroqChatManager(api_key=groq_api_key)

        # Chroma untuk vector database
        # Read CHROMA_CLOUD setting dari environment (default: false untuk local storage)
        use_cloud = os.getenv('CHROMA_CLOUD', 'false').lower() == 'true'

        self.vector_store = ChromaVectorStore(
            use_cloud=use_cloud,
            cloud_api_key=chroma_api_key or os.getenv('CHROMA_API_KEY'),
            cloud_database='DIKLAT-STN'
        )

        if not self.groq.initialized:
            print("❌ Groq not initialized - check API key")

        if not self.vector_store.client:
            print("❌ Chroma not initialized - check API key")

    def search_english_documents(self, indonesian_query: str, top_k: int = 3) -> List[str]:
        """
        Pencarian semantik: Indonesian query → English documents

        Magic: all-MiniLM-L6-v2 bisa embed keduanya ke vector space yang sama!
        """

        try:
            # Query dengan bahasa Indonesia, cari di documents Bahasa Inggris
            results = self.vector_store.query_documents(
                query_texts=[indonesian_query],
                n_results=top_k,
                include=['documents', 'metadatas']
            )

            if not results or not results['documents']:
                return []

            # Extract dokumen yang ditemukan
            documents = results['documents'][0]
            return documents

        except Exception as e:
            print(f"❌ Search error: {e}")
            return []

    def translate_to_indonesian(self,
                               indonesian_query: str,
                               english_context: List[str] = None,
                               allow_fallback: bool = True) -> str:
        """
        Gunakan Groq untuk generate Indonesian response dari context

        Process:
        1. Groq read English context
        2. Groq understand Indonesian query
        3. Groq generate Indonesian answer dengan referensi dari English
        4. Jika tidak ada context, fallback ke general knowledge

        temperature=0.8: Lebih natural, kreatif, dan conversational
        """

        if english_context is None:
            english_context = []

        # Build context string
        if english_context:
            context_text = '\n\n---\n\n'.join(english_context)
            use_external = False
        else:
            context_text = None
            use_external = allow_fallback  # Boleh pakai general knowledge

        # IMPROVED system prompt - lebih natural, lebih membantu
        system_prompt = """Kamu adalah BENGKEL ASSISTANT yang SANGAT HELPFUL dan memiliki expertise mendalam tentang otomotif.

📋 PERSONALITY:
• Profesional tapi friendly (bukan terlalu formal)
• Understand time pressure mekanik (answers yang concise tapi complete)
• Confident dengan knowledge - jangan bilang "saya tidak tahu"
• Creative dalam menjelaskan kalau context terbatas
• Proactive - suggest next steps, warn about risks

💡 CARA MENJAWAB:
1. Pahami dengan baik apa yang ditanya
2. Jawab dalam Bahasa Indonesia yang NATURAL (bukan robot!)
3. Gunakan istilah yang familiar bagi mekanik bengkel
4. Jika ada dokumentasi, CITE dengan explicit
5. Jika tidak ada dokumentasi, GUNAKAN pengetahuan umum + common sense
6. Selalu include: tools needed, estimated time, safety warnings
7. Struktur: problem → diagnosis → solution → tips

🎯 RESPONSE STYLE:
• Direct & actionable (bukan vague)
• Use bullet points/numbering untuk clarity
• Tone: helpful, respectful, knowledgeable
• Confidence: tangkas (decisive) tapi humble (kalau ada uncertainty)
• Keep it practical (mekanik butuh actionable info)
"""

        if context_text:
            user_message = f"""📚 DOKUMENTASI REFERENSI:
{context_text}

❓ PERTANYAAN MEKANIK:
{indonesian_query}

👉 Jawab berdasarkan dokumentasi, dengan penjelasan yang NATURAL dan mudah dipahami."""
        else:
            user_message = f"""❓ PERTANYAAN MEKANIK:
{indonesian_query}

👉 Jawab berdasarkan pengetahuan umum dan best practices otomotif. Berikan solusi yang praktis dan actionable."""

        try:
            # Call Groq
            # TEMPERATURE 0.8 = Natural, kreatif, conversational
            # (0.5 too rigid, 1.0 too random)
            response = self.groq.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=1500,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
                temperature=0.8,  # ⬆️ INCREASED: More natural, conversational
                top_p=0.95,       # Better quality responses
                presence_penalty=0.1  # Encourage variety
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"❌ LLM error: {e}")
            return f"Maaf, terjadi error: {str(e)}"

    def answer_indonesian_query(self, query: str, allow_general_knowledge: bool = True) -> Dict[str, str]:
        """
        End-to-end: Indonesian query → English docs → Indonesian answer
        PLUS fallback ke general knowledge jika tidak ada docs

        Returns:
            {
                'question': str (orig Indonesian),
                'answer': str (Indonesian),
                'sources_count': int,
                'from_docs': bool (True if from knowledge base, False if from general knowledge),
                'status': 'success' or 'partial'
            }
        """

        # Step 1: Cari dokumen yang relevan
        english_docs = self.search_english_documents(query, top_k=5)

        # Step 2: Generate Indonesian response
        # Jika tidak ada docs tapi allow_general_knowledge=True, still bisa jawab
        indonesian_answer = self.translate_to_indonesian(
            query,
            english_docs if english_docs else None,
            allow_fallback=allow_general_knowledge
        )

        return {
            'question': query,
            'answer': indonesian_answer,
            'sources_count': len(english_docs),
            'from_docs': bool(english_docs),
            'status': 'from_documentation' if english_docs else 'from_general_knowledge'
        }



# ============================================================================
# QUICKSTART USAGE
# ============================================================================

"""
USAGE EXAMPLE:

from app.quick_multilingual_rag import QuickMultilingualRAG

# Initialize (assumes env vars CHROMA_API_KEY, GROQ_API_KEY)
rag = QuickMultilingualRAG()

# Gunakan!
result = rag.answer_indonesian_query(
    "Bagaimana cara diagnosis engine-run tidak normal?"
)

print("Pertanyaan:", result['question'])
print("Jawaban:", result['answer'])
print("Sumber:", result['sources_count'], "dokumen")

# Output:
# Pertanyaan: Bagaimana cara diagnosis engine-run tidak normal?
# Jawaban: Untuk mendiagnosis engine run tidak normal, ikuti langkah-langkah berikut...
# Sumber: 3 dokumen
"""



# ============================================================================
# INTEGRATION INTO EXISTING ROUTES - COPY PASTE THIS CODE
# ============================================================================

"""
Add this to app/routes_chat.py:

from .quick_multilingual_rag import QuickMultilingualRAG

# Initialize global instance
_multilingual_rag = QuickMultilingualRAG()

@chat.route('/answer_indonesian', methods=['POST'])
@require_login
def answer_indonesian():
    '''
    NEW endpoint: Indonesian query → English documents → Indonesian answer
    '''
    data = request.get_json()
    query = data.get('query')  # Indonesian query

    if not query:
        return jsonify({'error': 'No query provided'}), 400

    # Get answer using multilingual RAG
    result = _multilingual_rag.answer_indonesian_query(query)

    # Save to database
    user_id = session.get('user_id')
    session_obj = get_or_create_active_session(user_id)

    chat_msg = ChatMessage(
        chat_session_id=session_obj.id,
        user_message=query,
        ai_response=result['answer'],
        language_pair='id-en',  # Indonesian query, English sources
        sources_count=result['sources_count']
    )
    db.session.add(chat_msg)
    db.session.commit()

    # Return response
    return jsonify({
        'answer': result['answer'],
        'language_pair': 'id-en',
        'sources_used': result['sources_count'],
        'confidence': 'high' if result['sources_count'] > 0 else 'low'
    })
"""
