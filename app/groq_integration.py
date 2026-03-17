"""
Groq API Integration - Primary AI Provider
Groq menyediakan free tier yang generous: 1000+ requests/hari
Model: llama-3.3-70b-versatile - latest Groq model yang tersedia
"""

import os
import json
import re
from typing import Optional, Dict
from datetime import datetime

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️  Groq SDK not available")

from app.api_key_manager import get_api_key, report_api_error, report_api_success, APIProvider

# Import mechanic reference database untuk fallback knowledge
try:
    from .mechanic_reference_database import (
        get_valve_clearance_spec,
        format_valve_clearance_response,
        find_similar_engines
    )
    MECHANIC_DB_AVAILABLE = True
except ImportError:
    MECHANIC_DB_AVAILABLE = False


class GroqChatManager:
    """Manager untuk Groq API integration (FREE & RELIABLE) dengan multi-key support"""

    def __init__(self, api_key: str = None):
        # Priority: 1. Passed argument, 2. Multi-API manager, 3. Environment variable, 4. credentials.json
        if api_key:
            self.api_key = api_key
            self.use_multi_key_manager = False
        else:
            # Try get from multi-key manager (with fallback support)
            try:
                self.api_key = get_api_key('groq', prefer_primary=True)
                self.use_multi_key_manager = True
            except:
                # Fallback: use old method
                self.api_key = os.getenv('GROQ_API_KEY') or self._get_api_key_from_credentials()
                self.use_multi_key_manager = False

        # Model untuk Groq
        self.model = "llama-3.3-70b-versatile"  # Latest Groq model, free tier

        self.initialized = False
        self.client = None

        # Debug info
        print(f"🔍 GroqChatManager init:")
        print(f"   GROQ SDK available: {GROQ_AVAILABLE}")
        print(f"   API key provided: {bool(self.api_key)}")
        if self.api_key:
            print(f"   API key (masked): {self.api_key[:20]}...{self.api_key[-10:]}")

        if self.api_key and GROQ_AVAILABLE:
            try:
                print(f"   Attempting to create Groq client...")
                self.client = Groq(api_key=self.api_key)
                self.initialized = True
                print(f"✅ Groq API READY")
                print(f"   Model: {self.model}")
                print(f"   Free tier: 1000 requests/day")
            except Exception as e:
                print(f"❌ Error initializing Groq client: {e}")
                print(f"   Error type: {type(e).__name__}")
                import traceback
                traceback.print_exc()
        elif not GROQ_AVAILABLE:
            print("❌ CRITICAL: Groq SDK not installed (pip install groq)")
        else:
            print("❌ CRITICAL: Groq API key not found. Set GROQ_API_KEY environment variable")

    @staticmethod
    def _get_api_key_from_credentials() -> Optional[str]:
        """Get Groq API key dari credentials.json file (fallback only)"""
        try:
            # Use environment variable for path, with fallback to credentials.json
            credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

            if os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                    api_key = creds.get('groq_api_key')
                    if api_key:
                        print(f"✅ Groq API key loaded from credentials file (fallback)")
                        return api_key
        except Exception as e:
            # Silently fail - prefer environment variables
            pass
        return None

    def _build_system_prompt(self) -> str:
        """System prompt - CONCISE & ACTIONABLE untuk Groq"""
        return """Kamu adalah ASISTEN BENGKEL MEKANIK - berpengalaman, praktis, to-the-point.

⛔ HANYA jawab tentang OTOMOTIF & BENGKEL! (Reject non-automotive)

🎯 GAYA: TO-THE-POINT (langsung poin) | TRAINER-LIKE (arahkan & guide) | KONKRET (actionable)

─────────────────────────────────────────────
📋 FORMAT RESPONS (Sesuai tipe pertanyaan)
─────────────────────────────────────────────

🆘 UNTUK DIAGNOSIS:
[JUDUL SINGKAT]

🔍 Penyebab Paling Likely: [Apa] (~70%)
  → Cara check: [1-2 langkah konkret]
  → Tools: [exact tools]
  → Waktu: ~X min

🔍 Alternatif: [Apa] (~25%)
  → Cara check: [1-2 langkah]

🔧 NEXT STEPS SEGERA:
1. [Langkah pertama]
2. [Langkah kedua]
(jika diagnosis #1 tidak cocok)

⚠️  SAFETY: [Jika ada risiko]

─────────────────────────────────────────────

🔧 UNTUK PROSEDUR:
[JUDUL: Apa yg dikerjakan]
⏱️  ~X jam | 🛠️  Tools: [list] | 💰 Parts: [jika ada]

LANGKAH:
1. [Judul] → [singkat, konkret] (Torque: X Nm jika relevan)
2. [Judul] → [singkat, konkret]
3. [dst...]

⚠️  PENTING: [Safety/caution]

─────────────────────────────────────────────

❓ UNTUK PERTANYAAN SINGKAT:
[Jawab direct, 1-3 sentences]
💡 Tips: [1-2 saran praktis]

─────────────────────────────────────────────

💪 RULES:
✗ JANGAN: Long rambling, vague, "saya tidak tahu"
✓ SELALU: konkret, actionable, safety-first, waktu estimasi
✓ Reference specs:
  - 2NR/1NR: Valve 0.20/0.30mm (saat dingin)
  - 3NR: Valve 0.25/0.35mm
  - Carburetor screw: 1.5 turns
  - Idle: 700-900 rpm

TONE: Profesional tapi approachable. Percaya diri, humble jika uncertain.
"""

    def _detect_engine_query(self, query: str) -> Optional[str]:
        """
        IMPROVED: Detect jika pertanyaan tentang spesifik engine
        Return engine code jika ditemukan, None otherwise
        """
        # Pattern untuk common engine codes
        engine_patterns = [
            r'\b(2nr|1nr|3nr|4g15|4a90|f10a)\b',  # Popular engines
            r'engine\s+([2-4][a-z0-9]{1,3})',       # engine XXX format
            r'mesin\s+([2-4][a-z0-9]{1,3})',        # mesin XXX format
        ]

        query_lower = query.lower()
        for pattern in engine_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1).lower()

        return None

    def _validate_automotive_response(self, query: str, response: str) -> bool:
        """
        DOMAIN FILTER: Check if response is about automotive/mechanics topics
        Return True if valid, False if off-topic

        This prevents AI from answering about plants, cooking, health, etc.
        """
        # Keywords yang indicate OFF-TOPIC responses (non-automotive)
        non_automotive_keywords = [
            # Plants, cooking
            r'tanaman\s+(yang|ini|adalah)',
            r'ilmiah\s+foeniculum',
            r'bumbu\s+masak',
            r'obat\s+tradisional\s+(untuk|mengobati)',
            r'tanaman\s+hias',
            r'resep',
            r'memasak',
            # Health/medical
            r'penyakit',
            r'kesehatan\s+(umum|tubuh)',
            r'vitamin\s+dan\s+mineral',
            # Non-automotive
            r'olahraga',
            r'musik',
            r'film\s+(atau|dan)',
            r'politics|politik',
            r'entertainment',
        ]

        response_lower = response.lower()

        # Check for non-automotive keywords
        for pattern in non_automotive_keywords:
            if re.search(pattern, response_lower):
                print(f"⚠️  Domain filter triggered for pattern: {pattern}")
                return False

        # Automotive keywords yang HARUS ada (at least some)
        automotive_keywords = [
            r'mesin|engine',
            r'mobil|motor|kendaraan|vehicle|car',
            r'bengkel|service|repair|perbaikan|diagnosis',
            r'sparepart|onderdil|komponen',
            r'oli|bensin|fuel',
            r'rem|brake',
            r'gigi|gearbox',
            r'klep|valve',
            r'busi|spark plug',
            r'radiator|pendingin',
            r'aki|battery',
            r'alternator',
            r'kampas|pad',
            r'ban|tire',
        ]

        # Check if response has at least ONE automotive keyword
        has_automotive_keyword = False
        for pattern in automotive_keywords:
            if re.search(pattern, response_lower):
                has_automotive_keyword = True
                break

        if not has_automotive_keyword:
            print(f"⚠️  Response lacks automotive keywords")
            return False

        return True

    def _filter_non_automotive_context(self, chunks: list) -> list:
        """
        Filter out non-automotive chunks from context
        Prevents model from using irrelevant documents

        Args:
            chunks: List of chunks from search results

        Returns:
            Filtered list with only automotive-related chunks
        """
        automotive_keywords = [
            r'mesin|engine|motor',
            r'mobil|kendaraan|vehicle|car|truck',
            r'bengkel|service|repair|perbaikan',
            r'oli|fuel|bensin',
            r'sparepart|onderdil|komponen',
            r'rem|brake|transmisi|gearbox',
            r'klep|valve|spark plug|busi',
            r'diagnostik|diagnosis|troubleshoot',
            r'teknisi|mekanik|bengkel',
        ]

        # Reject chunks with obvious non-automotive keywords
        non_automotive_reject_words = [
            'tanaman', 'buah', 'sayur', 'resep', 'memasak',
            'bumbu', 'kuliner', 'masakan', 'penyakit', 'obat', 'kesehatan',
            'olahraga', 'musik', 'film', 'hiburan', 'entertainment'
        ]

        filtered_chunks = []
        for chunk in chunks:
            chunk_text = chunk.get('text', '').lower()

            # Check if chunk has non-automotive keywords → skip
            skip = False
            for reject_word in non_automotive_reject_words:
                if reject_word in chunk_text:
                    skip = True
                    print(f"⚠️  Skipping chunk with keyword '{reject_word}'")
                    break

            if skip:
                continue

            # Check if chunk has at least ONE automotive keyword → keep
            has_auto_keyword = False
            for pattern in automotive_keywords:
                if re.search(pattern, chunk_text):
                    has_auto_keyword = True
                    break

            if has_auto_keyword:
                filtered_chunks.append(chunk)
            else:
                print(f"⚠️  Chunk lacks automotive keywords, skipping")

        return filtered_chunks

    def _check_mechanic_database(self, engine_code: str, query: str) -> Optional[str]:
        """
        IMPROVED: Check mechanic reference database untuk quick answers
        Berguna untuk spec questions seperti valve clearance
        """
        if not MECHANIC_DB_AVAILABLE:
            return None

        # Check jika query berkaitan dengan valve clearance
        if any(keyword in query.lower() for keyword in ['valve clear', 'celah klep', 'clearance']):
            return format_valve_clearance_response(engine_code)

        return None

    def generate_answer(self,
                       query: str,
                       context: str = "",
                       include_sources: bool = True) -> Dict:
        """
        IMPROVED: Generate jawaban menggunakan Groq API (FAST & FREE)
        Dengan ENGINE-SPECIFIC FALLBACK KNOWLEDGE untuk spec queries

        Args:
            query: Pertanyaan dari user
            context: Context dari dokumen
            include_sources: Include sumber rujukan

        Returns:
            {
                'success': bool,
                'answer': str,
                'model': str,
                'generated_at': str,
                'from_docs': bool,
                'error': str (jika ada)
            }
        """
        if not self.initialized or not self.client:
            return {
                'success': False,
                'error': 'Groq API tidak diinisialisasi. Pastikan GROQ_API_KEY tersedia.',
                'answer': None,
                'model': None,
                'from_docs': False
            }

        try:
            from_docs = bool(context and context.strip())

            # ✅ STEP 1: TRY ENGINE-SPECIFIC REFERENCE DATABASE
            # For queries like "celah klep 2NR" - answer immediately dari database
            engine_code = self._detect_engine_query(query)
            if engine_code:
                db_answer = self._check_mechanic_database(engine_code, query)
                if db_answer:
                    return {
                        'success': True,
                        'answer': db_answer,
                        'model': self.model,
                        'generated_at': datetime.utcnow().isoformat(),
                        'provider': 'Groq (Reference Database)',
                        'from_docs': False,  # From internal reference, not external docs
                        'source_type': 'mechanic_reference_database'
                    }

            # ✅ STEP 2: BUILD IMPROVED PROMPT WITH CONTEXT AWARENESS
            # Jika ada context (dari docs), gunakan itu
            # Jika tidak ada context, prompt untuk use general knowledge
            if context and context.strip():
                # With documentation context
                prompt = f"""📚 CONTEXT DARI DOKUMENTASI:
{context}

❓ PERTANYAAN MEKANIK:
{query}

👉 Jawab berdasarkan dokumentasi, dengan penjelasan yang NATURAL dan mudah dipahami."""
                source_note = "(dari dokumentasi)"
            else:
                # Without documentation - use general knowledge, but be clear about it
                prompt = f"""❓ PERTANYAAN MEKANIK:
{query}

👉 Jawab berdasarkan pengetahuan umum dan best practices otomotif Indonesia. Jika ada uncertainty, sebutkan dengan jelas."""
                source_note = "(dari pengetahuan umum)"

            # ✅ STEP 3: CALL GROQ API
            # temperature=0.8: Balance kreativitas & konsistensi (higher = more creative, lower = more rigid)
            #   - 0.3: Too rigid, sounds robotic ❌
            #   - 0.5: Formal, structured (good for technical)
            #   - 0.7: Natural, balanced ✅
            #   - 0.8: More conversational, engaging ✅✅
            #   - 1.0: Too random, less coherent
            # max_tokens=2048: Jawaban lebih lengkap untuk topik kompleks
            # top_p=0.95: Quality terbaik dengan diverse opsi (0.9 terlalu konservatif)
            # presence_penalty=0.1: Encourage variety, avoid repetition
            message = self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.8,  # ⬆️ INCREASED: More natural & conversational
                max_tokens=2048,
                top_p=0.95,       # ⬆️ Better quality responses
                presence_penalty=0.1  # NEW: Encourage variety
            )

            answer = message.choices[0].message.content.strip()

            # ✅ STEP 4: VALIDATE RESPONSE IS AUTOMOTIVE-RELATED
            # This prevents responses like "Adas adalah tanaman..." when user asks about mechanics
            is_valid = self._validate_automotive_response(query, answer)

            if not is_valid:
                # Response is off-topic - reject and ask user to clarify
                return {
            # Report success to API key manager
            if self.use_multi_key_manager:
                report_api_success('groq')

            return {
                'success': True,
                'answer': answer,
                'model': self.model,
                'generated_at': datetime.utcnow().isoformat(),
                'provider': 'Groq',
                'from_docs': from_docs,
                'usage': {
                    'input_tokens': message.usage.prompt_tokens,
                    'output_tokens': message.usage.completion_tokens
                }
            }

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Groq generation error: {error_msg}")
            
            # Report error to API key manager for quota tracking
            if self.use_multi_key_manager:
                if 'quota' in error_msg.lower() or 'rate limit' in error_msg.lower():
                    report_api_error('groq', error_type='quota_exceeded')
                else:
                    report_api_error('groq', error_type='api_error')
            
                'model': self.model,
                'generated_at': datetime.utcnow().isoformat(),
                'provider': 'Groq',
                'from_docs': from_docs,
                'usage': {
                    'input_tokens': message.usage.prompt_tokens,
                    'output_tokens': message.usage.completion_tokens
                }
            }

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Groq generation error: {error_msg}")
            return {
                'success': False,
                'error': f'Groq error: {error_msg}',
                'answer': None,
                'model': self.model,
                'from_docs': False
            }

    def check_api_availability(self) -> bool:
        """Check if Groq API is available"""
        if not self.initialized:
            return False

        try:
            # Simple test
            response = self.client.chat.completions.create(
                messages=[{"role": "user", "content": "Hi"}],
                model=self.model,
                max_tokens=10
            )
            return response is not None
        except Exception as e:
            print(f"⚠️  Groq health check failed: {e}")
            return False
