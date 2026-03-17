"""
Helper module untuk mengirim dan log notifikasi Telegram dengan database tracking
"""

import logging
from typing import Optional, Dict
from datetime import datetime
from .telegram_notifications import TelegramNotificationService
from .models import db, TelegramNotificationLog, Peserta, Batch, Announcement

logger = logging.getLogger(__name__)


class NotificationManager:
    """Manager untuk mengirim notifikasi dan melacak status di database"""

    @staticmethod
    def log_notification(
        admin_id: int,
        notification_type: str,
        title: str,
        message: str,
        related_object_id: Optional[int] = None,
        related_object_type: Optional[str] = None,
        status: str = 'sent',
        telegram_message_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> TelegramNotificationLog:
        """
        Log notifikasi ke database

        Args:
            admin_id: Telegram admin ID
            notification_type: Tipe notifikasi (new_registration, payment_verified, etc)
            title: Judul notifikasi
            message: Pesan notifikasi
            related_object_id: ID object yang terkait
            related_object_type: Tipe object yang terkait
            status: Status notifikasi
            telegram_message_id: Message ID dari Telegram
            error_message: Pesan error jika ada

        Returns:
            TelegramNotificationLog: Record notifikasi yang sudah disimpan
        """
        try:
            notification_log = TelegramNotificationLog(
                admin_id=admin_id,
                notification_type=notification_type,
                title=title,
                message=message,
                related_object_id=related_object_id,
                related_object_type=related_object_type,
                status=status,
                telegram_message_id=telegram_message_id,
                error_message=error_message
            )

            db.session.add(notification_log)
            db.session.commit()

            logger.info(f"✅ Notifikasi dicatat di database: {notification_type} ({admin_id})")
            return notification_log

        except Exception as e:
            logger.error(f"❌ Error saat log notifikasi: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def notify_new_registration(peserta_data: Dict) -> Dict:
        """
        Kirim dan log notifikasi untuk pendaftaran peserta baru

        Args:
            peserta_data: Dictionary dengan data peserta

        Returns:
            Dict: Status pengiriman notifikasi
        """
        message = f"""
🆕 <b>PESERTA BARU MENDAFTAR</b>

📝 <b>Data Peserta:</b>
• Nama: <code>{peserta_data.get('nama', 'N/A')}</code>
• WhatsApp: <code>{peserta_data.get('whatsapp', 'N/A')}</code>
• Email: <code>{peserta_data.get('email', 'N/A')}</code>
• Batch: <code>{peserta_data.get('batch', 'N/A')}</code>
• Status Pekerjaan: <code>{peserta_data.get('status_pekerjaan', 'N/A')}</code>

🏢 <b>Bengkel:</b>
• Nama: <code>{peserta_data.get('nama_bengkel', 'N/A')}</code>
• Alamat: <code>{peserta_data.get('alamat_bengkel', 'N/A')}</code>

⏰ <b>Waktu Pendaftaran:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

✋ <b>Tindakan Diperlukan:</b>
• Verifikasi data peserta
• Proses verifikasi pembayaran
• Set permission dokumen
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='new_registration',
                    title='Pendaftaran Peserta Baru',
                    message=message,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='new_registration',
                    title='Pendaftaran Peserta Baru',
                    message=message,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def notify_payment_verification(peserta_data: Dict, status: str) -> Dict:
        """
        Kirim dan log notifikasi untuk verifikasi pembayaran

        Args:
            peserta_data: Data peserta
            status: Status pembayaran

        Returns:
            Dict: Status pengiriman notifikasi
        """
        icon = "✅" if status == "Lunas" else "❌" if status == "Ditolak" else "⏳"

        message = f"""
{icon} <b>VERIFIKASI PEMBAYARAN</b>

📋 <b>Data Peserta:</b>
• Nama: <code>{peserta_data.get('nama', 'N/A')}</code>
• WhatsApp: <code>{peserta_data.get('whatsapp', 'N/A')}</code>
• Batch: <code>{peserta_data.get('batch', 'N/A')}</code>

💰 <b>Status Pembayaran:</b>
<b>{status}</b>

⏰ <b>Waktu Update:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='payment_verification',
                    title=f'Verifikasi Pembayaran - {status}',
                    message=message,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='payment_verification',
                    title=f'Verifikasi Pembayaran - {status}',
                    message=message,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def notify_payment_verification_with_photo(peserta_data: Dict, status: str, photo_path: Optional[str] = None) -> Dict:
        """
        Kirim dan log notifikasi untuk verifikasi pembayaran dengan foto bukti

        Args:
            peserta_data: Data peserta
            status: Status pembayaran
            photo_path: Path ke file foto bukti pembayaran

        Returns:
            Dict: Status pengiriman notifikasi
        """
        icon = "✅" if status == "Lunas" else "❌" if status == "Ditolak" else "⏳"

        caption = f"""
{icon} <b>VERIFIKASI PEMBAYARAN</b>

📋 <b>Data Peserta:</b>
• Nama: <code>{peserta_data.get('nama', 'N/A')}</code>
• WhatsApp: <code>{peserta_data.get('whatsapp', 'N/A')}</code>
• Batch: <code>{peserta_data.get('batch', 'N/A')}</code>

💰 <b>Status Pembayaran:</b>
<b>{status}</b>

⏰ <b>Waktu Update:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

        results = {}

        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                # Send photo if available
                if photo_path:
                    success = TelegramNotificationService.send_photo(
                        admin_id,
                        photo_path,
                        caption=caption,
                        parse_mode="HTML"
                    )
                else:
                    # Send text message only if no photo
                    success = TelegramNotificationService.send_message(admin_id, caption)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='payment_verification_with_photo',
                    title=f'Bukti Pembayaran - {peserta_data.get("nama", "Unknown")} ({status})',
                    message=caption,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='payment_verification_with_photo',
                    title=f'Bukti Pembayaran - {peserta_data.get("nama", "Unknown")} (FAILED)',
                    message=caption,
                    related_object_id=peserta_data.get('id'),
                    related_object_type='peserta',
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def notify_announcement_created(announcement_data: Dict) -> Dict:
        """
        Kirim dan log notifikasi untuk pengumuman baru

        Args:
            announcement_data: Data pengumuman

        Returns:
            Dict: Status pengiriman notifikasi
        """
        message = f"""
📢 <b>PENGUMUMAN BARU DIBUAT</b>

📝 <b>Judul:</b>
<b>{announcement_data.get('judul', 'N/A')}</b>

📄 <b>Isi:</b>
<code>{announcement_data.get('isi', 'N/A')[:300]}...</code>

📋 <b>Target Batch:</b>
<code>{announcement_data.get('batch', 'Semua Peserta')}</code>

👤 <b>Dibuat Oleh:</b>
<code>{announcement_data.get('dibuat_oleh', 'Unknown')}</code>

🕐 <b>Waktu Dibuat:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

✅ <b>Status:</b>
{announcement_data.get('aktif', True) and 'AKTIF' or 'NONAKTIF'}
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='announcement_created',
                    title=f'Pengumuman Baru: {announcement_data.get("judul", "Untitled")}',
                    message=message,
                    related_object_id=announcement_data.get('id'),
                    related_object_type='announcement',
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='announcement_created',
                    title=f'Pengumuman Baru: {announcement_data.get("judul", "Untitled")}',
                    message=message,
                    related_object_id=announcement_data.get('id'),
                    related_object_type='announcement',
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def notify_batch_created(batch_data: Dict) -> Dict:
        """
        Kirim dan log notifikasi untuk batch baru

        Args:
            batch_data: Data batch

        Returns:
            Dict: Status pengiriman notifikasi
        """
        message = f"""
🆕 <b>BATCH BARU DIBUAT</b>

📝 <b>Nama Batch:</b>
<code>{batch_data.get('nama', 'N/A')}</code>

🔗 <b>WhatsApp Link:</b>
<code>{batch_data.get('whatsapp_link', 'N/A')}</code>

📊 <b>Akses Workshop Default:</b>
{batch_data.get('akses_workshop_default', False) and '✅ YA' or '❌ TIDAK'}

📊 <b>Status:</b>
{batch_data.get('aktif', True) and '✅ AKTIF' or '❌ NONAKTIF'}

🕐 <b>Waktu Dibuat:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='batch_created',
                    title=f'Batch Baru: {batch_data.get("nama", "Unknown")}',
                    message=message,
                    related_object_id=batch_data.get('id'),
                    related_object_type='batch',
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='batch_created',
                    title=f'Batch Baru: {batch_data.get("nama", "Unknown")}',
                    message=message,
                    related_object_id=batch_data.get('id'),
                    related_object_type='batch',
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def notify_system_alert(alert_title: str, alert_message: str, severity: str = "INFO") -> Dict:
        """
        Kirim dan log alert sistem

        Args:
            alert_title: Judul alert
            alert_message: Pesan alert
            severity: Tingkat severity

        Returns:
            Dict: Status pengiriman notifikasi
        """
        severity_icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }

        icon = severity_icons.get(severity, "ℹ️")

        message = f"""
{icon} <b>{severity} - {alert_title}</b>

📝 <b>Pesan:</b>
<code>{alert_message}</code>

🕐 <b>Waktu:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='system_alert',
                    title=f'{severity}: {alert_title}',
                    message=message,
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='system_alert',
                    title=f'{severity}: {alert_title}',
                    message=message,
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def test_notification() -> Dict:
        """
        Kirim notifikasi test untuk verifikasi sistem

        Returns:
            Dict: Status pengiriman test notifikasi
        """
        message = f"""
🧪 <b>TEST NOTIFIKASI SISTEM</b>

✅ Sistem notifikasi Telegram berhasil dikonfigurasi!

📊 <b>Informasi:</b>
• Bot Status: <code>AKTIF</code>
• Admin IDs: <code>{len(TelegramNotificationService.ADMIN_IDS)} Admin(s)</code>
• Timestamp: <code>{datetime.now().isoformat()}</code>

🎉 Bot siap mengirim notifikasi untuk:
✓ Pendaftaran peserta baru
✓ Verifikasi pembayaran
✓ Perubahan akses dokumen
✓ Pengumuman baru
✓ Batch baru
✓ Alert sistem
"""

        results = {}
        for admin_id in TelegramNotificationService.ADMIN_IDS:
            try:
                success = TelegramNotificationService.send_message(admin_id, message)

                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='test_notification',
                    title='Test Notifikasi Sistem',
                    message=message,
                    status='sent' if success else 'failed'
                )

                results[admin_id] = success

            except Exception as e:
                logger.error(f"❌ Error mengirim test notifikasi ke {admin_id}: {str(e)}")
                NotificationManager.log_notification(
                    admin_id=admin_id,
                    notification_type='test_notification',
                    title='Test Notifikasi Sistem',
                    message=message,
                    status='failed',
                    error_message=str(e)
                )
                results[admin_id] = False

        return results

    @staticmethod
    def get_notification_logs(notification_type: Optional[str] = None, limit: int = 50) -> list:
        """
        Ambil log notifikasi dari database

        Args:
            notification_type: Filter berdasarkan tipe notifikasi (opsional)
            limit: Jumlah record yang diambil

        Returns:
            list: List record notifikasi
        """
        try:
            query = TelegramNotificationLog.query.order_by(TelegramNotificationLog.created_at.desc())

            if notification_type:
                query = query.filter_by(notification_type=notification_type)

            return query.limit(limit).all()

        except Exception as e:
            logger.error(f"❌ Error mengambil notification logs: {str(e)}")
            return []

    @staticmethod
    def get_notification_stats() -> Dict:
        """
        Ambil statistik notifikasi

        Returns:
            Dict: Statistik notifikasi
        """
        try:
            total = TelegramNotificationLog.query.count()
            sent = TelegramNotificationLog.query.filter_by(status='sent').count()
            failed = TelegramNotificationLog.query.filter_by(status='failed').count()

            # Group by notification type
            by_type = db.session.query(
                TelegramNotificationLog.notification_type,
                db.func.count(TelegramNotificationLog.id)
            ).group_by(TelegramNotificationLog.notification_type).all()

            return {
                'total': total,
                'sent': sent,
                'failed': failed,
                'by_type': {item[0]: item[1] for item in by_type}
            }

        except Exception as e:
            logger.error(f"❌ Error menghitung notification stats: {str(e)}")
            return {
                'total': 0,
                'sent': 0,
                'failed': 0,
                'by_type': {}
            }


# Shortcuts untuk kemudahan penggunaan
def notify_new_registration(peserta_data):
    return NotificationManager.notify_new_registration(peserta_data)

def notify_payment_verification(peserta_data, status):
    return NotificationManager.notify_payment_verification(peserta_data, status)

def notify_payment_verification_with_photo(peserta_data, status, photo_path=None):
    return NotificationManager.notify_payment_verification_with_photo(peserta_data, status, photo_path)

def notify_document_access_change(peserta_data, access_type, access_status, duration=None):
    return NotificationManager.notify_document_access_change(peserta_data, access_type, access_status, duration)

def notify_announcement_created(announcement_data):
    return NotificationManager.notify_announcement_created(announcement_data)

def notify_batch_created(batch_data):
    return NotificationManager.notify_batch_created(batch_data)

def notify_system_alert(alert_title, alert_message, severity="INFO"):
    return NotificationManager.notify_system_alert(alert_title, alert_message, severity)

def test_notification():
    return NotificationManager.test_notification()
