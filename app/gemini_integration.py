"""
Gemini API Integration Module
Untuk generate jawaban dari pertanyaan dengan context dari dokumen
"""

import os
import json
from typing import Optional, Dict, List
from datetime import datetime

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from app.api_key_manager import get_api_key, report_api_error, report_api_success, APIProvider


class GeminiChatManager:
    """Manager untuk Gemini API integration dengan multi-key support"""

    def __init__(self, api_key: str = None):
        # Priority: 1. Passed argument, 2. Multi-API manager, 3. Environment variable, 4. credentials.json
        if api_key:
            self.api_key = api_key
            self.use_multi_key_manager = False
        else:
            # Try get from multi-key manager (with fallback support)
            try:
                self.api_key = get_api_key('gemini', prefer_primary=True)
                self.use_multi_key_manager = True
            except:
                # Fallback: use old method
                self.api_key = os.getenv('GEMINI_API_KEY') or self._get_api_key_from_credentials()
                self.use_multi_key_manager = False

        # Model priority list - akan try satu per satu (urutan penting!)
        # gemini-pro adalah yang most stable dan free-tier friendly
        self.available_models = [
            "gemini-pro",            # Most stable & widely available (priority)
            "gemini-1.5-pro",        # Newer, but may require paid account
            "gemini-1.5-flash",      # Newer flash model
        ]

        self.model_name = None  # Will be set on first use
        self.initialized = False

        if self.api_key and genai:
            try:
                genai.configure(api_key=self.api_key)
                self.initialized = True
                print(f"✅ Gemini API configured. Will try models: {', '.join(self.available_models)}")
            except Exception as e:
                print(f"❌ Error initializing Gemini: {e}")

    def _get_working_model(self) -> Optional[str]:
        """Check mana model yang tersedia dan return yang first working"""
        if self.model_name:
            return self.model_name

        for model_name in self.available_models:
            try:
                # Try create model instance
                model = genai.GenerativeModel(model_name)
                # Test with simple request
                response = model.generate_content("test")
                if response:
                    self.model_name = model_name
                    print(f"✅ Using Gemini model: {model_name}")
                    return model_name
            except Exception as e:
                print(f"⚠️  Model {model_name} tidak tersedia: {str(e)[:100]}")
                continue

        # If nothing works, just return first model (akan error nanti tapi biar explicit)
        print(f"❌ No working models found. Trying with: {self.available_models[0]}")
        return self.available_models[0]

    @staticmethod
    def _get_api_key_from_credentials() -> Optional[str]:
        """Get Gemini API key dari credentials.json file (fallback only)"""
        try:
            # Use environment variable for path, with fallback to credentials.json
            credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

            if os.path.exists(credentials_path):
                with open(credentials_path, 'r') as f:
                    creds = json.load(f)
                    api_key = creds.get('gemini_api_key')
                    if api_key:
                        print(f"✅ Gemini API key loaded from credentials file (fallback)")
                        return api_key
        except Exception as e:
            # Silently fail - prefer environment variables
            pass
    def _build_system_prompt(self) -> str:
        """Build system prompt untuk Gemini"""
        return """Kamu adalah asisten teknis yang membantu mekanik Indonesia.

INSTRUKSI:
1. Jawab dalam Bahasa Indonesia yang jelas dan praktis
2. Gunakan istilah teknis yang mudah dipahami
3. Sertakan langkah-langkah praktis jika relevan
4. Selalu rujuk ke dokumen sumber yang diberikan
5. Jika tidak yakin, katakan "Saya tidak menemukan informasi yang cukup"

TONE: Profesional, ramah, dan praktis untuk mekanik.
FORMAT: Gunakan bullet points atau numbered lists untuk keterbacaan."""

    def generate_answer(self,
                       query: str,
                       context: str = "",
                       include_sources: bool = True) -> Dict:
        """
        Generate jawaban menggunakan Gemini API dengan multi-key fallback support

        Args:
            query: Pertanyaan dari user
            context: Context dari dokumen (optional)
            include_sources: Include sumber rujukan

        Returns:
            {
                'success': bool,
                'answer': str,
                'model': str,
                'generated_at': str,
                'usage': {
                    'prompt_tokens': int,
                    'response_tokens': int
                },
                'error': str (jika ada)
            }
        """
        if not self.initialized:
            return {
                'success': False,
                'error': 'Gemini API tidak diinisialisasi. Pastikan GEMINI_API_KEY tersedia.',
                'answer': None
            }

        try:
            # Get working model first
            working_model_name = self._get_working_model()
            if not working_model_name:
                return {
                    'success': False,
                    'error': 'Tidak ada model Gemini yang tersedia',
                    'answer': None
                }

            model = genai.GenerativeModel(working_model_name)

            # Build prompt
            if context:
                prompt = f"""Berdasarkan dokumen berikut, jawab pertanyaan:

{self._build_system_prompt()}

## DOKUMEN SUMBER:
{context}

## PERTANYAAN:
{query}

Jawab dengan merujuk dokumen di atas."""
            else:
                prompt = f"""{self._build_system_prompt()}

## PERTANYAAN:
{query}

Jawab dalam Bahasa Indonesia."""

            # Send request to Gemini
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                )
            )

            answer = response.text if response else "Tidak ada response dari model"

            # Report success to API key manager
            if self.use_multi_key_manager:
                report_api_success('gemini')

            return {
                'success': True,
                'answer': answer,
                'model': working_model_name,
                'generated_at': datetime.utcnow().isoformat(),
                'usage': {
                    'prompt_tokens': len(prompt.split()),
                    'response_tokens': len(answer.split()) if answer else 0
                }
            }

        except Exception as e:
            error_str = str(e)
            print(f"❌ Gemini API Error: {error_str}")

            # Report error to API key manager for quota tracking
            if self.use_multi_key_manager:
                if 'quota' in error_str.lower() or 'rate limit' in error_str.lower():
                    report_api_error('gemini', error_type='quota_exceeded')
                else:
                    report_api_error('gemini', error_type='api_error')

            working_model_name = self._get_working_model()
            return {
                'success': False,
                'error': error_str,
                'answer': None,
                'model': working_model_name
            }

    def generate_answer_with_rag(self,
                                query: str,
                                document_context: str,
                                document_sources: List[Dict] = None) -> Dict:
        """
        Generate jawaban dengan RAG (Retrieval Augmented Generation)

        Args:
            query: Pertanyaan
            document_context: Context dari dokumen yang sudah dicari
            document_sources: List of source documents untuk citation

        Returns:
            Combined result dengan answer + sources
        """
        # Generate answer
        result = self.generate_answer(query, document_context, include_sources=True)

        # Add sources info
        if document_sources and result['success']:
            result['sources'] = document_sources
            result['with_rag'] = True
        else:
            result['with_rag'] = False

        return result

    def extract_key_points(self, text: str) -> Dict:
        """Extract main points dari text menggunakan Gemini"""
        if not self.initialized:
            return {'success': False, 'error': 'Gemini API tidak diinisialisasi'}

        try:
            working_model_name = self._get_working_model()
            if not working_model_name:
                return {'success': False, 'error': 'Tidak ada model Gemini yang tersedia'}

            model = genai.GenerativeModel(working_model_name)

            prompt = f"""Ekstrak poin-poin utama dari teks berikut dalam Bahasa Indonesia.
Format: Berikan list dengan maksimal 5 poin.

TEKS:
{text}

POIN-POIN UTAMA:"""

            response = model.generate_content(prompt)

            return {
                'success': True,
                'key_points': response.text if response else "",
                'generated_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def check_api_availability(self) -> bool:
        """Check if Gemini API is available"""
        return self.initialized and genai is not None


class ChatHistory:
    """Simple chat history manager"""

    def __init__(self, max_history: int = 20):
        self.history = []
        self.max_history = max_history

    def add_message(self, role: str, content: str, sources: List = None):
        """Add message to history"""
        message = {
            'role': role,  # 'user' atau 'assistant'
            'content': content,
            'timestamp': datetime.utcnow().isoformat(),
            'sources': sources or []
        }
        self.history.append(message)

        # Keep only last N messages
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def get_history(self, limit: int = None) -> List[Dict]:
        """Get chat history"""
        if limit:
            return self.history[-limit:]
        return self.history

    def clear(self):
        """Clear history"""
        self.history = []

    def format_for_context(self) -> str:
        """Format history untuk di-pass ke model"""
        formatted = "## Chat History:\n"
        for msg in self.history[-5:]:  # Gunakan hanya 5 pesan terakhir
            formatted += f"\n**{msg['role'].upper()}**: {msg['content'][:200]}...\n"
        return formatted
