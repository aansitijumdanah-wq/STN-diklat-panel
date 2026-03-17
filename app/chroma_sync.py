"""
Chroma Vector Database Synchronization
Sinkronisasi antara Local dan Cloud Chroma instances
Fitur: Two-way sync, conflict resolution, change tracking, batching
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import threading
from pathlib import Path

try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


class SyncStatus(Enum):
    """Status untuk operasi sinkronisasi"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    CONFLICT = "conflict"
    PARTIAL = "partial"


class SyncConflict(Enum):
    """Jenis konflik yang bisa terjadi saat sync"""
    LOCAL_NEWER = "local_newer"          # Local lebih baru dari cloud
    CLOUD_NEWER = "cloud_newer"          # Cloud lebih baru dari local
    BOTH_MODIFIED = "both_modified"      # Keduanya dimodifikasi
    LOCAL_ONLY = "local_only"            # Hanya di local
    CLOUD_ONLY = "cloud_only"            # Hanya di cloud
    HASH_MISMATCH = "hash_mismatch"      # Isi berbeda meski timestamp sama


class ChromaSyncManager:
    """
    Manager untuk sinkronisasi Chroma Cloud dan Local
    Mendukung: push (local->cloud), pull (cloud->local), bidirectional sync
    """

    def __init__(self,
                 local_client: 'chromadb.Client',
                 cloud_api_key: str = None,
                 cloud_database: str = None,
                 cloud_tenant: str = "default",
                 collection_name: str = "documents",
                 batch_size: int = 100,
                 sync_dir: str = None):
        """
        Initialize Sync Manager

        Args:
            local_client: Local Chroma PersistentClient
            cloud_api_key: Chroma Cloud API key
            cloud_database: Chroma Cloud database name
            cloud_tenant: Chroma Cloud tenant ID
            collection_name: Collection untuk disinkronisasi
            batch_size: Jumlah dokumen per batch (API limits)
            sync_dir: Directory untuk menyimpan sync metadata
        """
        self.local_client = local_client
        self.cloud_api_key = cloud_api_key or os.getenv('CHROMA_API_KEY')
        self.cloud_database = cloud_database or os.getenv('CHROMA_DATABASE')
        self.cloud_tenant = cloud_tenant
        self.collection_name = collection_name
        self.batch_size = batch_size

        # Create sync metadata directory
        self.sync_dir = sync_dir or os.path.join(
            os.path.dirname(__file__), '..', 'chroma_data', '.sync'
        )
        os.makedirs(self.sync_dir, exist_ok=True)

        # Initialize logging
        self.setup_logging()

        # Initialize clients
        self.cloud_client = None
        self.local_collection = None
        self.cloud_collection = None

        self._initialize_cloud_client()

    def setup_logging(self):
        """Setup logging untuk sync operations"""
        log_dir = os.path.join(self.sync_dir, 'logs')
        os.makedirs(log_dir, exist_ok=True)

        log_file = os.path.join(log_dir, f'sync_{datetime.now().strftime("%Y%m%d")}.log')

        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

        self.logger = logging.getLogger('ChromaSync')
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

        # Also log to console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

    def _initialize_cloud_client(self):
        """Initialize Chroma Cloud client"""
        if not CHROMADB_AVAILABLE:
            self.logger.error("chromadb library not available")
            return False

        if not self.cloud_api_key or not self.cloud_database:
            self.logger.warning("Cloud credentials tidak lengkap, skip cloud sync")
            return False

        try:
            self.cloud_client = chromadb.CloudClient(
                api_key=self.cloud_api_key,
                tenant=self.cloud_tenant,
                database=self.cloud_database
            )

            # Test connection
            test_collection = self.cloud_client.get_collection(
                name=self.collection_name
            ) or self.cloud_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

            self.cloud_collection = test_collection
            self.logger.info(f"✅ Cloud client initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize cloud client: {e}")
            return False

    def _get_local_collection(self):
        """Get atau create local collection"""
        if self.local_collection:
            return self.local_collection

        try:
            self.local_collection = self.local_client.get_collection(
                name=self.collection_name
            )
        except:
            self.local_collection = self.local_client.create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )

        return self.local_collection

    def _compute_document_hash(self, document: str, metadata: Dict) -> str:
        """Compute hash untuk detect perubahan"""
        combined = json.dumps({
            'doc': document,
            'meta': metadata
        }, sort_keys=True, default=str)
        return hashlib.md5(combined.encode()).hexdigest()

    def _get_sync_metadata(self, doc_id: str) -> Dict:
        """Get sync metadata untuk document"""
        metadata_file = os.path.join(self.sync_dir, f'{doc_id}.json')

        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, 'r') as f:
                    return json.load(f)
            except:
                return {}

        return {}

    def _save_sync_metadata(self, doc_id: str, metadata: Dict):
        """Save sync metadata untuk document"""
        metadata_file = os.path.join(self.sync_dir, f'{doc_id}.json')

        try:
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2, default=str)
        except Exception as e:
            self.logger.warning(f"Failed to save sync metadata for {doc_id}: {e}")

    def detect_changes(self) -> Dict:
        """
        Detect perubahan antara local dan cloud

        Returns:
            Dict dengan lists dari:
            - local_only: Docs hanya di local
            - cloud_only: Docs hanya di cloud
            - modified: Docs yang diubah
            - conflicts: Docs dengan konflik
        """
        if not self.cloud_client:
            self.logger.error("Cloud client not available")
            return {
                'local_only': [],
                'cloud_only': [],
                'modified': [],
                'conflicts': []
            }

        try:
            self.logger.info("🔍 Detecting changes between local and cloud...")

            local_collection = self._get_local_collection()

            # Get all docs dari local
            local_docs = local_collection.get(
                include=['documents', 'metadatas']
            )
            local_ids = set(local_docs['ids']) if local_docs['ids'] else set()

            # Get all docs dari cloud
            cloud_docs = self.cloud_collection.get(
                include=['documents', 'metadatas']
            )
            cloud_ids = set(cloud_docs['ids']) if cloud_docs['ids'] else set()

            # Categorize
            changes = {
                'local_only': list(local_ids - cloud_ids),
                'cloud_only': list(cloud_ids - local_ids),
                'modified': [],
                'conflicts': []
            }

            # Check modified documents
            common_ids = local_ids & cloud_ids

            for doc_id in common_ids:
                local_idx = local_docs['ids'].index(doc_id)
                cloud_idx = cloud_docs['ids'].index(doc_id)

                local_doc = local_docs['documents'][local_idx]
                local_meta = local_docs['metadatas'][local_idx] if local_docs['metadatas'] else {}

                cloud_doc = cloud_docs['documents'][cloud_idx]
                cloud_meta = cloud_docs['metadatas'][cloud_idx] if cloud_docs['metadatas'] else {}

                local_hash = self._compute_document_hash(local_doc, local_meta)
                cloud_hash = self._compute_document_hash(cloud_doc, cloud_meta)

                if local_hash != cloud_hash:
                    # Check untuk conflict
                    local_time = local_meta.get('updated_at', '1970-01-01')
                    cloud_time = cloud_meta.get('updated_at', '1970-01-01')

                    if local_time != cloud_time:
                        changes['modified'].append({
                            'id': doc_id,
                            'conflict_type': SyncConflict.BOTH_MODIFIED.value if local_time != cloud_time else SyncConflict.HASH_MISMATCH.value,
                            'local_updated': local_time,
                            'cloud_updated': cloud_time
                        })
                    else:
                        changes['conflicts'].append({
                            'id': doc_id,
                            'type': SyncConflict.HASH_MISMATCH.value
                        })

            self.logger.info(f"✅ Change detection complete:")
            self.logger.info(f"   Local only: {len(changes['local_only'])}")
            self.logger.info(f"   Cloud only: {len(changes['cloud_only'])}")
            self.logger.info(f"   Modified: {len(changes['modified'])}")
            self.logger.info(f"   Conflicts: {len(changes['conflicts'])}")

            return changes

        except Exception as e:
            self.logger.error(f"❌ Error detecting changes: {e}")
            return {
                'local_only': [],
                'cloud_only': [],
                'modified': [],
                'conflicts': []
            }

    def push_to_cloud(self,
                     changes: Dict = None,
                     override_conflicts: bool = False) -> Dict:
        """
        Push local changes ke cloud (local -> cloud)

        Args:
            changes: Dict dari detect_changes() atau None untuk push semua
            override_conflicts: Jika True, override cloud version dengan local

        Returns:
            Sync result summary
        """
        if not self.cloud_client:
            self.logger.error("Cloud client not available")
            return {
                'status': SyncStatus.FAILED.value,
                'pushed': 0,
                'skipped': 0,
                'errors': []
            }

        try:
            self.logger.info("📤 Starting push to cloud (local -> cloud)...")

            # Get changes jika tidak diberikan
            if changes is None:
                changes = self.detect_changes()

            local_collection = self._get_local_collection()
            pushed_count = 0
            error_count = 0
            errors = []

            # Push local_only docs
            for doc_id in changes.get('local_only', []):
                try:
                    result = local_collection.get(
                        ids=[doc_id],
                        include=['documents', 'embeddings', 'metadatas']
                    )

                    if result['ids']:
                        doc = result['documents'][0]
                        embedding = result['embeddings'][0] if result['embeddings'] else None
                        metadata = result['metadatas'][0] if result['metadatas'] else {}

                        # Add timestamp
                        metadata['synced_at'] = datetime.utcnow().isoformat()

                        if embedding:
                            self.cloud_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                embeddings=[embedding],
                                metadatas=[metadata]
                            )
                        else:
                            self.cloud_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                metadatas=[metadata]
                            )

                        pushed_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append(f"Failed to push {doc_id}: {str(e)}")

            # Push modified docs jika override enabled
            for mod_item in changes.get('modified', []):
                doc_id = mod_item['id']

                if not override_conflicts:
                    self.logger.warning(f"⚠️  Skipping modified doc {doc_id} (conflict resolution disabled)")
                    continue

                try:
                    result = local_collection.get(
                        ids=[doc_id],
                        include=['documents', 'embeddings', 'metadatas']
                    )

                    if result['ids']:
                        doc = result['documents'][0]
                        embedding = result['embeddings'][0] if result['embeddings'] else None
                        metadata = result['metadatas'][0] if result['metadatas'] else {}
                        metadata['synced_at'] = datetime.utcnow().isoformat()

                        # Delete old version in cloud
                        self.cloud_collection.delete(ids=[doc_id])

                        # Add new version
                        if embedding:
                            self.cloud_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                embeddings=[embedding],
                                metadatas=[metadata]
                            )
                        else:
                            self.cloud_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                metadatas=[metadata]
                            )

                        pushed_count += 1
                        self.logger.info(f"✅ Pushed modified doc: {doc_id}")

                except Exception as e:
                    error_count += 1
                    errors.append(f"Failed to push modified {doc_id}: {str(e)}")

            result = {
                'status': SyncStatus.SUCCESS.value if error_count == 0 else SyncStatus.PARTIAL.value,
                'pushed': pushed_count,
                'skipped': len(changes.get('cloud_only', [])),
                'errors': errors,
                'timestamp': datetime.utcnow().isoformat()
            }

            self.logger.info(f"✅ Push complete: {pushed_count} docs pushed, {error_count} errors")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error pushing to cloud: {e}")
            return {
                'status': SyncStatus.FAILED.value,
                'pushed': 0,
                'errors': [str(e)]
            }

    def pull_from_cloud(self, changes: Dict = None) -> Dict:
        """
        Pull cloud changes ke local (cloud -> local)

        Args:
            changes: Dict dari detect_changes() atau None untuk pull semua

        Returns:
            Sync result summary
        """
        if not self.cloud_client:
            self.logger.error("Cloud client not available")
            return {
                'status': SyncStatus.FAILED.value,
                'pulled': 0,
                'errors': []
            }

        try:
            self.logger.info("📥 Starting pull from cloud (cloud -> local)...")

            # Get changes jika tidak diberikan
            if changes is None:
                changes = self.detect_changes()

            local_collection = self._get_local_collection()
            pulled_count = 0
            error_count = 0
            errors = []

            # Pull cloud_only docs
            for doc_id in changes.get('cloud_only', []):
                try:
                    result = self.cloud_collection.get(
                        ids=[doc_id],
                        include=['documents', 'embeddings', 'metadatas']
                    )

                    if result['ids']:
                        doc = result['documents'][0]
                        embedding = result['embeddings'][0] if result['embeddings'] else None
                        metadata = result['metadatas'][0] if result['metadatas'] else {}
                        metadata['pulled_at'] = datetime.utcnow().isoformat()

                        if embedding:
                            local_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                embeddings=[embedding],
                                metadatas=[metadata]
                            )
                        else:
                            local_collection.add(
                                ids=[doc_id],
                                documents=[doc],
                                metadatas=[metadata]
                            )

                        pulled_count += 1

                except Exception as e:
                    error_count += 1
                    errors.append(f"Failed to pull {doc_id}: {str(e)}")

            result = {
                'status': SyncStatus.SUCCESS.value if error_count == 0 else SyncStatus.PARTIAL.value,
                'pulled': pulled_count,
                'skipped': len(changes.get('local_only', [])),
                'errors': errors,
                'timestamp': datetime.utcnow().isoformat()
            }

            self.logger.info(f"✅ Pull complete: {pulled_count} docs pulled, {error_count} errors")
            return result

        except Exception as e:
            self.logger.error(f"❌ Error pulling from cloud: {e}")
            return {
                'status': SyncStatus.FAILED.value,
                'pulled': 0,
                'errors': [str(e)]
            }

    def bidirectional_sync(self,
                          conflict_resolution: str = "cloud_wins") -> Dict:
        """
        Two-way sync antara local dan cloud

        Args:
            conflict_resolution: Strategy untuk resolve conflicts
                - "cloud_wins": Prioritas cloud version
                - "local_wins": Prioritas local version
                - "manual": Tidak auto-resolve, return untuk manual review

        Returns:
            Detailed sync result
        """
        try:
            self.logger.info(f"🔄 Starting bidirectional sync (strategy: {conflict_resolution})...")

            # Detect changes
            changes = self.detect_changes()

            # Handle conflicts based on strategy
            if changes['conflicts']:
                if conflict_resolution == "cloud_wins":
                    self.logger.info(f"⚠️  Resolving {len(changes['conflicts'])} conflicts - CLOUD WINS")
                    # Cloud versions are kept
                    pass
                elif conflict_resolution == "local_wins":
                    self.logger.info(f"⚠️  Resolving {len(changes['conflicts'])} conflicts - LOCAL WINS")
                    # Will be handled in push_to_cloud
                    pass
                else:
                    self.logger.warning(f"⚠️  {len(changes['conflicts'])} conflicts need manual resolution")

            # Push local changes
            push_result = self.push_to_cloud(
                changes=changes,
                override_conflicts=(conflict_resolution == "local_wins")
            )

            # Get updated changes
            updated_changes = self.detect_changes()

            # Pull cloud changes
            pull_result = self.pull_from_cloud(changes=updated_changes)

            summary = {
                'status': push_result['status'],
                'conflict_resolution': conflict_resolution,
                'push': push_result,
                'pull': pull_result,
                'conflicts_detected': len(changes['conflicts']),
                'timestamp': datetime.utcnow().isoformat()
            }

            self.logger.info(f"✅ Bidirectional sync complete!")
            self.logger.info(f"   Pushed: {push_result.get('pushed', 0)}")
            self.logger.info(f"   Pulled: {pull_result.get('pulled', 0)}")
            self.logger.info(f"   Conflicts: {len(changes['conflicts'])}")

            return summary

        except Exception as e:
            self.logger.error(f"❌ Error in bidirectional sync: {e}")
            return {
                'status': SyncStatus.FAILED.value,
                'error': str(e)
            }

    def get_sync_status(self) -> Dict:
        """Get current sync status"""
        try:
            local_collection = self._get_local_collection()

            local_count = local_collection.count() if local_collection else 0
            cloud_count = self.cloud_collection.count() if self.cloud_collection else 0

            changes = self.detect_changes()

            return {
                'local_documents': local_count,
                'cloud_documents': cloud_count,
                'sync_ready': self.cloud_client is not None,
                'local_only': len(changes['local_only']),
                'cloud_only': len(changes['cloud_only']),
                'modified': len(changes['modified']),
                'conflicts': len(changes['conflicts']),
                'last_check': datetime.utcnow().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error getting sync status: {e}")
            return {'error': str(e)}

    def enable_auto_sync(self, interval_seconds: int = 3600, direction: str = "bidirectional"):
        """
        Enable automatic sync dalam background thread

        Args:
            interval_seconds: Interval untuk sync checks (default: 1 hour)
            direction: "bidirectional", "push-only", atau "pull-only"
        """
        def auto_sync_worker():
            self.logger.info(f"🤖 Auto-sync worker started (interval: {interval_seconds}s, direction: {direction})")

            while True:
                try:
                    if direction == "bidirectional":
                        self.bidirectional_sync(conflict_resolution="cloud_wins")
                    elif direction == "push-only":
                        changes = self.detect_changes()
                        self.push_to_cloud(changes)
                    elif direction == "pull-only":
                        changes = self.detect_changes()
                        self.pull_from_cloud(changes)

                    self.logger.info(f"✅ Auto-sync completed at {datetime.now().isoformat()}")

                except Exception as e:
                    self.logger.error(f"❌ Auto-sync error: {e}")

                # Wait untuk next sync
                import time
                time.sleep(interval_seconds)

        # Start background thread
        sync_thread = threading.Thread(target=auto_sync_worker, daemon=True)
        sync_thread.start()

        self.logger.info(f"✅ Auto-sync enabled (direction: {direction}, interval: {interval_seconds}s)")
        return sync_thread


# Convenience functions untuk quick access
def quick_sync(local_client,
               direction: str = "bidirectional",
               cloud_api_key: str = None) -> Dict:
    """
    Quick sync wrapper function

    Args:
        local_client: Local Chroma client
        direction: "push", "pull", atau "bidirectional"
        cloud_api_key: Chroma Cloud API key (gunakan env jika None)

    Returns:
        Sync result
    """
    manager = ChromaSyncManager(
        local_client=local_client,
        cloud_api_key=cloud_api_key
    )

    if direction == "push":
        return manager.push_to_cloud()
    elif direction == "pull":
        return manager.pull_from_cloud()
    else:  # bidirectional
        return manager.bidirectional_sync()


def check_sync_status(local_client,
                      cloud_api_key: str = None) -> Dict:
    """Check current sync status"""
    manager = ChromaSyncManager(
        local_client=local_client,
        cloud_api_key=cloud_api_key
    )
    return manager.get_sync_status()
