"""
Multi-API Key Management System
Supports multiple API keys for fallback & load balancing
Prevents quota exhaustion dengan automatic key rotation
"""

import os
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import random

logger = logging.getLogger(__name__)


class APIProvider(Enum):
    """Supported API providers"""
    GEMINI = "gemini"
    GROQ = "groq"
    CHROMA = "chroma"


class APIKeyStatus(Enum):
    """Status of an API key"""
    ACTIVE = "active"
    QUOTA_EXCEEDED = "quota_exceeded"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    UNKNOWN = "unknown"


class APIKey:
    """Represents a single API key with tracking"""

    def __init__(self, key: str, key_id: int, provider: APIProvider):
        self.key = key
        self.key_id = key_id  # 1 or 2
        self.provider = provider
        self.status = APIKeyStatus.ACTIVE
        self.created_at = datetime.utcnow()
        self.last_used = None
        self.error_count = 0
        self.quota_refill_time = None  # When quota will reset

    def is_available(self) -> bool:
        """Check if key can be used"""
        if self.status == APIKeyStatus.QUOTA_EXCEEDED:
            # Check if quota window has passed
            if self.quota_refill_time and datetime.utcnow() > self.quota_refill_time:
                self.status = APIKeyStatus.ACTIVE
                self.error_count = 0
                return True
            return False

        return self.status == APIKeyStatus.ACTIVE

    def mark_used(self):
        """Mark key as used"""
        self.last_used = datetime.utcnow()

    def mark_error(self, error_type: str = "error"):
        """Mark key as having encountered an error"""
        self.error_count += 1

        if error_type == "quota_exceeded":
            self.status = APIKeyStatus.QUOTA_EXCEEDED
            # Assume 1-hour quota window
            self.quota_refill_time = datetime.utcnow() + timedelta(hours=1)
            logger.warning(f"{self.provider.value} key #{self.key_id}: Quota exceeded. Will retry at {self.quota_refill_time}")

        elif error_type == "rate_limited":
            self.status = APIKeyStatus.RATE_LIMITED
            # Retry after 30 seconds
            self.quota_refill_time = datetime.utcnow() + timedelta(seconds=30)
            logger.warning(f"{self.provider.value} key #{self.key_id}: Rate limited. Will retry at {self.quota_refill_time}")

        elif self.error_count >= 3:
            self.status = APIKeyStatus.ERROR
            logger.error(f"{self.provider.value} key #{self.key_id}: Too many errors ({self.error_count})")

    def reset_error_count(self):
        """Reset error count on successful use"""
        self.error_count = 0
        self.status = APIKeyStatus.ACTIVE

    def __repr__(self):
        masked = self.key[:10] + "..." + self.key[-5:]
        return f"APIKey(id={self.key_id}, provider={self.provider.value}, status={self.status.value}, key={masked})"


class MultiAPIKeyManager:
    """
    Manages multiple API keys with fallback & rotation

    Features:
    - Multiple keys per provider
    - Automatic fallback on quota/error
    - Load balancing across keys
    - Error tracking and recovery
    - Status monitoring
    """

    def __init__(self):
        self.keys: Dict[APIProvider, List[APIKey]] = {
            APIProvider.GEMINI: [],
            APIProvider.GROQ: [],
            APIProvider.CHROMA: [],
        }

        self._initialize_keys()

    def _initialize_keys(self):
        """Load API keys from environment variables"""
        # Load Gemini keys
        for i in range(1, 3):
            key = os.getenv(f'GEMINI_API_KEY_{i}')
            if key:
                self.keys[APIProvider.GEMINI].append(
                    APIKey(key, i, APIProvider.GEMINI)
                )
                logger.info(f"Loaded Gemini API key #{i}")

        # Load Groq keys
        for i in range(1, 3):
            key = os.getenv(f'GROQ_API_KEY_{i}')
            if key:
                self.keys[APIProvider.GROQ].append(
                    APIKey(key, i, APIProvider.GROQ)
                )
                logger.info(f"Loaded Groq API key #{i}")

        # Load Chroma keys
        for i in range(1, 3):
            key = os.getenv(f'CHROMA_API_KEY_{i}')
            if key:
                self.keys[APIProvider.CHROMA].append(
                    APIKey(key, i, APIProvider.CHROMA)
                )
                logger.info(f"Loaded Chroma API key #{i}")

        # Fallback to single key format
        if not self.keys[APIProvider.GEMINI]:
            key = os.getenv('GEMINI_API_KEY')
            if key:
                self.keys[APIProvider.GEMINI].append(
                    APIKey(key, 1, APIProvider.GEMINI)
                )
                logger.info("Loaded single Gemini API key (backward compatibility)")

        if not self.keys[APIProvider.GROQ]:
            key = os.getenv('GROQ_API_KEY')
            if key:
                self.keys[APIProvider.GROQ].append(
                    APIKey(key, 1, APIProvider.GROQ)
                )
                logger.info("Loaded single Groq API key (backward compatibility)")

        if not self.keys[APIProvider.CHROMA]:
            key = os.getenv('CHROMA_API_KEY')
            if key:
                self.keys[APIProvider.CHROMA].append(
                    APIKey(key, 1, APIProvider.CHROMA)
                )
                logger.info("Loaded single Chroma API key (backward compatibility)")

    def get_key(self, provider: APIProvider, prefer_primary: bool = True) -> Optional[str]:
        """
        Get an available API key for provider

        Args:
            provider: Which API provider
            prefer_primary: If True, try primary key first

        Returns:
            Available API key or None if none available
        """
        available_keys = [k for k in self.keys[provider] if k.is_available()]

        if not available_keys:
            logger.error(f"No available {provider.value} API keys!")
            return None

        if prefer_primary and len(available_keys) > 1:
            # Try primary key first
            primary = next((k for k in available_keys if k.key_id == 1), None)
            if primary:
                selected_key = primary
            else:
                selected_key = available_keys[0]
        else:
            # Random rotation for load balancing
            selected_key = random.choice(available_keys)

        selected_key.mark_used()
        logger.debug(f"Selected {provider.value} key #{selected_key.key_id}")

        return selected_key.key

    def get_primary_key(self, provider: APIProvider) -> Optional[str]:
        """Get primary API key (only)"""
        primary_keys = [k for k in self.keys[provider] if k.key_id == 1]

        if not primary_keys or not primary_keys[0].is_available():
            return None

        primary_keys[0].mark_used()
        return primary_keys[0].key

    def get_backup_key(self, provider: APIProvider) -> Optional[str]:
        """Get backup API key (only)"""
        backup_keys = [k for k in self.keys[provider] if k.key_id == 2]

        if not backup_keys or not backup_keys[0].is_available():
            return None

        backup_keys[0].mark_used()
        return backup_keys[0].key

    def report_error(self, provider: APIProvider, key_id: int, error_type: str = "error"):
        """
        Report an error for a specific key

        Args:
            provider: Which provider
            key_id: Which key (1 or 2)
            error_type: Type of error - "quota_exceeded", "rate_limited", "error"
        """
        key_list = self.keys[provider]
        target_key = next((k for k in key_list if k.key_id == key_id), None)

        if target_key:
            target_key.mark_error(error_type)
            logger.warning(f"Reported {error_type} for {provider.value} key #{key_id}")

    def report_success(self, provider: APIProvider, key_id: int):
        """Report successful usage of a key"""
        key_list = self.keys[provider]
        target_key = next((k for k in key_list if k.key_id == key_id), None)

        if target_key:
            target_key.reset_error_count()
            logger.debug(f"{provider.value} key #{key_id} operated successfully")

    def get_status(self, provider: str = None, key_id: int = None) -> Dict:
        """
        Get status of API keys

        Args:
            provider: Provider name ('gemini', 'groq', 'chroma') or None for all
            key_id: Specific key ID (1 or 2) or None for all

        Returns:
            Status dictionary
        """
        if provider:
            try:
                prov = APIProvider(provider.lower())
                provider_keys = self.keys[prov]

                if key_id:
                    # Get specific key
                    target_key = next((k for k in provider_keys if k.key_id == key_id), None)
                    if target_key:
                        return {
                            'key_id': target_key.key_id,
                            'status': target_key.status.value,
                            'available': target_key.is_available(),
                            'error_count': target_key.error_count,
                            'last_used': target_key.last_used.isoformat() if target_key.last_used else None,
                            'quota_exceeded': target_key.status == APIKeyStatus.QUOTA_EXCEEDED,
                            'rate_limited': target_key.status == APIKeyStatus.RATE_LIMITED,
                            'last_error': None
                        }
                    return {}
                else:
                    # Return all keys for this provider
                    return {
                        prov.value: [
                            {
                                'key_id': k.key_id,
                                'status': k.status.value,
                                'available': k.is_available(),
                                'error_count': k.error_count,
                                'last_used': k.last_used.isoformat() if k.last_used else None,
                                'quota_exceeded': k.status == APIKeyStatus.QUOTA_EXCEEDED,
                                'rate_limited': k.status == APIKeyStatus.RATE_LIMITED,
                            }
                            for k in provider_keys
                        ]
                    }
            except ValueError:
                return {}

        # Return all providers
        status = {}
        for prov in APIProvider:
            status[prov.value] = [
                {
                    'key_id': k.key_id,
                    'status': k.status.value,
                    'available': k.is_available(),
                    'error_count': k.error_count,
                    'last_used': k.last_used.isoformat() if k.last_used else None,
                }
                for k in self.keys[prov]
            ]

        return status

    def _reset_error_state(self, provider: str, key_id: int = None):
        """
        Reset error state for a provider's key

        Args:
            provider: Provider name ('gemini', 'groq', 'chroma')
            key_id: Specific key ID (1 or 2) or None for all
        """
        try:
            prov = APIProvider(provider.lower())
            provider_keys = self.keys[prov]

            if key_id:
                # Reset specific key
                target_key = next((k for k in provider_keys if k.key_id == key_id), None)
                if target_key:
                    target_key.reset_error_count()
                    logger.info(f"Reset error state for {provider} key #{key_id}")
            else:
                # Reset all keys for this provider
                for k in provider_keys:
                    k.reset_error_count()
                logger.info(f"Reset error state for all {provider} keys")
        except ValueError:
            logger.error(f"Invalid provider: {provider}")

    def health_check(self, provider: str = None) -> Dict:
        """
        Check health of API keys

        Args:
            provider: Provider name ('gemini', 'groq', 'chroma') or None for all

        Returns:
            Health status dictionary
        """
        health = {
            'timestamp': datetime.utcnow().isoformat(),
        }

        if provider:
            try:
                prov = APIProvider(provider.lower())
                provider_keys = self.keys[prov]
                available = sum(1 for k in provider_keys if k.is_available())

                health['provider'] = prov.value
                health['ok'] = available > 0
                health['message'] = f"{available}/{len(provider_keys)} keys available"
                health['available_keys'] = available
                health['total_keys'] = len(provider_keys)
                health['keys'] = [
                    {
                        'id': k.key_id,
                        'status': k.status.value,
                        'available': k.is_available(),
                        'errors': k.error_count
                    }
                    for k in provider_keys
                ]
                return health
            except ValueError:
                health['ok'] = False
                health['message'] = f"Invalid provider: {provider}"
                return health

        # Check all providers
        health['providers'] = {}
        for prov in APIProvider:
            provider_keys = self.keys[prov]
            available = sum(1 for k in provider_keys if k.is_available())

            health['providers'][prov.value] = {
                'total_keys': len(provider_keys),
                'available_keys': available,
                'all_keys_down': available == 0,
                'keys': [
                    {
                        'id': k.key_id,
                        'status': k.status.value,
                        'available': k.is_available(),
                        'errors': k.error_count
                    }
                    for k in provider_keys
                ]
            }

        return health


def get_manager() -> MultiAPIKeyManager:
    """Get or create the global API key manager"""
    global _manager
    if _manager is None:
        _manager = MultiAPIKeyManager()
    return _manager


def get_api_key_manager() -> MultiAPIKeyManager:
    """Alias for get_manager() - backwards compatibility"""
    return get_manager()


def get_api_key(provider: str, prefer_primary: bool = True) -> Optional[str]:
    """
    Convenience function to get an API key

    Args:
        provider: 'gemini', 'groq', or 'chroma'
        prefer_primary: If True, try primary key first

    Returns:
        API key or None
    """
    manager = get_manager()
    try:
        prov = APIProvider(provider.lower())
        return manager.get_key(prov, prefer_primary=prefer_primary)
    except ValueError:
        logger.error(f"Invalid provider: {provider}")
        return None


def report_api_error(provider: str, key_id: int = 1, error_type: str = "error"):
    """
    Report an error for an API key

    Args:
        provider: 'gemini', 'groq', or 'chroma'
        key_id: Which key (1 or 2), defaults to 1
        error_type: Type of error
    """
    manager = get_manager()
    try:
        prov = APIProvider(provider.lower())
        manager.report_error(prov, key_id, error_type)
    except ValueError:
        logger.error(f"Invalid provider: {provider}")


def report_api_success(provider: str, key_id: int = 1):
    """
    Report successful API key usage

    Args:
        provider: 'gemini', 'groq', or 'chroma'
        key_id: Which key (1 or 2), defaults to 1
    """
    manager = get_manager()
    try:
        prov = APIProvider(provider.lower())
        manager.report_success(prov, key_id)
    except ValueError:
        logger.error(f"Invalid provider: {provider}")
