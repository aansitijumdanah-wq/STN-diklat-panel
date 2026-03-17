"""
Telegram Notification Service untuk Admin
Mengintegrasikan Telegram Bot API untuk mengirim notifikasi real-time ke admin
"""

import requests
import logging
from datetime import datetime
from typing import Optional, Dict, List
from .models import db

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    """Service untuk mengirim notifikasi melalui Telegram Bot"""

    # Konfigurasi Telegram
    TELEGRAM_BOT_TOKEN = "8247214035:AAH--6ex4LZXfkaGSQDG14Cu4ZLbX1RWDLU"
    TELEGRAM_API_URL = "https://api.telegram.org"

    # List admin Telegram IDs yang akan menerima notifikasi
    ADMIN_IDS = [5915236875]

    @classmethod
    def send_message(cls, chat_id: int, message: str, parse_mode: str = "HTML") -> bool:
        """
        Mengirim pesan langsung ke Telegram

        Args:
            chat_id: Telegram chat ID
            message: Pesan yang akan dikirim
            parse_mode: Format pesan (HTML atau Markdown)

        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            url = f"{cls.TELEGRAM_API_URL}/bot{cls.TELEGRAM_BOT_TOKEN}/sendMessage"

            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ Notifikasi berhasil dikirim ke chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Gagal mengirim notifikasi: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error mengirim message: {str(e)}")
            return False

    @classmethod
    def send_photo(cls, chat_id: int, photo_path: str, caption: str = "", parse_mode: str = "HTML") -> bool:
        """
        Mengirim foto ke Telegram dengan caption

        Args:
            chat_id: Telegram chat ID
            photo_path: Path lengkap file foto
            caption: Caption untuk foto
            parse_mode: Format caption (HTML atau Markdown)

        Returns:
            bool: True jika berhasil, False jika gagal
        """
        try:
            import os

            # Validate file exists
            if not os.path.exists(photo_path):
                logger.error(f"❌ File tidak ditemukan: {photo_path}")
                return False

            url = f"{cls.TELEGRAM_API_URL}/bot{cls.TELEGRAM_BOT_TOKEN}/sendPhoto"

            with open(photo_path, 'rb') as photo_file:
                files = {'photo': photo_file}
                data = {
                    'chat_id': chat_id,
                    'caption': caption,
                    'parse_mode': parse_mode
                }

                response = requests.post(url, files=files, data=data, timeout=30)

            if response.status_code == 200:
                logger.info(f"✅ Foto berhasil dikirim ke chat {chat_id}")
                return True
            else:
                logger.error(f"❌ Gagal mengirim foto: {response.text}")
                return False

        except Exception as e:
            logger.error(f"❌ Error mengirim photo: {str(e)}")
            return False

    @classmethod
    def send_photo_to_all_admins(cls, photo_path: str, caption: str = "", parse_mode: str = "HTML") -> Dict:
        """
        Mengirim foto ke semua admin

        Args:
            photo_path: Path lengkap file foto
            caption: Caption untuk foto
            parse_mode: Format caption

        Returns:
            Dict: Status pengiriman ke setiap admin
        """
        results = {}

        for admin_id in cls.ADMIN_IDS:
            success = cls.send_photo(admin_id, photo_path, caption, parse_mode)
            results[admin_id] = success

        return results

    @classmethod
    def send_to_all_admins(cls, message: str, parse_mode: str = "HTML") -> Dict:
        """
        Mengirim notifikasi ke semua admin

        Args:
            message: Pesan yang akan dikirim
            parse_mode: Format pesan

        Returns:
            Dict: Status pengiriman ke setiap admin
        """
        results = {}

        for admin_id in cls.ADMIN_IDS:
            success = cls.send_message(admin_id, message, parse_mode)
            results[admin_id] = success

        return results

    @classmethod
    def notify_new_registration(cls, peserta_data: Dict) -> bool:
        """
        Notifikasi untuk pendaftaran peserta baru

        Args:
            peserta_data: Data peserta yang baru mendaftar

        Returns:
            bool: Status pengiriman notifikasi
        """
        message = f"""
🆕 <b>PESERTA BARU MENDAFTAR</b>

📝 <b>Data Peserta:</b>
• Nama: <code>{peserta_data.get('nama', 'N/A')}</code>
• WhatsApp: <code>{peserta_data.get('whatsapp', 'N/A')}</code>
• Email: <code>{peserta_data.get('email', 'N/A')}</code>
• Batch: <code>{peserta_data.get('batch', 'N/A')}</code>
• Status: <code>{peserta_data.get('status_pekerjaan', 'N/A')}</code>

🏢 <b>Bengkel:</b>
• Nama: <code>{peserta_data.get('nama_bengkel', 'N/A')}</code>
• Alamat: <code>{peserta_data.get('alamat_bengkel', 'N/A')}</code>

⏰ <b>Waktu Pendaftaran:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}

✋ <b>Tindakan Diperlukan:</b>
• Verifikasi data peserta
• Proses pembayaran
• Set permission dokumen
"""
        return cls.send_to_all_admins(message)

    @classmethod
    def notify_payment_verification(cls, peserta_data: Dict, status: str) -> bool:
        """
        Notifikasi untuk perubahan akses dokumen

        Args:
            peserta_data: Data peserta
            access_type: Tipe akses (individual, group, batch)
            access_status: Status akses (True = diberikan, False = dicabut)
            duration: Durasi akses (opsional)

        Returns:
            bool: Status pengiriman notifikasi
        """
        action = "✅ DIBERIKAN" if access_status else "❌ DICABUT"

        message = f"""
📄 <b>PERUBAHAN AKSES DOKUMEN</b>

📋 <b>Data Peserta:</b>
• Nama: <code>{peserta_data.get('nama', 'N/A')}</code>
• WhatsApp: <code>{peserta_data.get('whatsapp', 'N/A')}</code>
• Batch: <code>{peserta_data.get('batch', 'N/A')}</code>

🔐 <b>Tipe Akses:</b>
<code>{access_type.upper()}</code>

📊 <b>Status:</b>
<b>{action}</b>

⏰ <b>Durasi Akses:</b>
{duration if duration else 'Unlimited'}

🕐 <b>Waktu Update:</b>
{datetime.now().strftime('%d-%m-%Y %H:%M:%S')}
"""
        return cls.send_to_all_admins(message)

    @classmethod
    def notify_announcement_created(cls, announcement_data: Dict) -> bool:
        """
        Notifikasi untuk pengumuman baru

        Args:
            announcement_data: Data pengumuman

        Returns:
            bool: Status pengiriman notifikasi
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
        return cls.send_to_all_admins(message)

    @classmethod
    def notify_batch_created(cls, batch_data: Dict) -> bool:
        """
        Notifikasi untuk batch baru

        Args:
            batch_data: Data batch

        Returns:
            bool: Status pengiriman notifikasi
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
        return cls.send_to_all_admins(message)

    @classmethod
    def notify_system_alert(cls, alert_title: str, alert_message: str, severity: str = "INFO") -> bool:
        """
        Notifikasi untuk alert sistem

        Args:
            alert_title: Judul alert
            alert_message: Pesan alert
            severity: Tingkat severity (INFO, WARNING, ERROR, CRITICAL)

        Returns:
            bool: Status pengiriman notifikasi
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
        return cls.send_to_all_admins(message)

    @classmethod
    def test_notification(cls, admin_id: int = None) -> bool:
        """
        Kirim notifikasi test untuk verifikasi

        Args:
            admin_id: ID admin untuk test (jika None, kirim ke semua admin)

        Returns:
            bool: Status pengiriman notifikasi
        """
        message = f"""
🧪 <b>TEST NOTIFIKASI</b>

✅ Sistem notifikasi Telegram berhasil dikonfigurasi!

📊 <b>Informasi:</b>
• Bot Token: <code>Tersedia</code>
• Admin ID: <code>{admin_id if admin_id else 'Semua Admin'}</code>
• Timestamp: <code>{datetime.now().isoformat()}</code>
• Status: <code>AKTIF</code>

🎉 Bot siap mengirim notifikasi untuk:
✓ Pendaftaran peserta baru
✓ Verifikasi pembayaran
✓ Perubahan akses dokumen
✓ Pengumuman baru
✓ Batch baru
✓ Alert sistem
"""
        if admin_id:
            return cls.send_message(admin_id, message)
        else:
            return cls.send_to_all_admins(message)


# Alias untuk kemudahan penggunaan
notify = TelegramNotificationService
