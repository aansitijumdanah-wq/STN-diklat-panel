from .models import db, DocumentAccess, Peserta
from datetime import datetime, timedelta
import os
import logging

logger = logging.getLogger(__name__)

def revoke_expired_access():
    """
    Mencabut akses dokumen yang telah kedaluwarsa.
    """
    try:
        expired_accesses = DocumentAccess.query.filter(
            DocumentAccess.tanggal_kadaluarsa <= datetime.utcnow(),
            DocumentAccess.akses_diberikan == True
        ).all()

        if not expired_accesses:
            print("Tidak ada akses dokumen yang kedaluwarsa.")
            return

        for access in expired_accesses:
            access.akses_diberikan = False
            print(f"Akses dokumen untuk {access.peserta_id or access.batch_id} telah dicabut.")

        db.session.commit()
        print(f"Total {len(expired_accesses)} akses dokumen yang kedaluwarsa telah dicabut.")

    except Exception as e:
        print(f"Error saat mencabut akses dokumen yang kedaluwarsa: {e}")
        db.session.rollback()

def cleanup_old_payment_proofs(upload_folder: str = None):
    """
    Menghapus bukti pembayaran yang sudah terverifikasi lebih dari 24 jam.

    Args:
        upload_folder: Path ke folder upload (ambil dari config jika tidak diberikan)
    """
    try:
        from flask import current_app

        # Get upload folder from app config if not provided
        if not upload_folder:
            if current_app:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', '/workspaces/STN-diklat-panel/instance/uploads')
            else:
                upload_folder = '/workspaces/STN-diklat-panel/instance/uploads'

        # Calculate timestamp for 24 hours ago
        cutoff_time = datetime.utcnow() - timedelta(hours=24)

        # Find peserta with payment proofs verified more than 24 hours ago
        old_payments = Peserta.query.filter(
            Peserta.payment_proof != None,
            Peserta.tanggal_verifikasi_pembayaran != None,
            Peserta.tanggal_verifikasi_pembayaran <= cutoff_time
        ).all()

        if not old_payments:
            logger.info("✅ Tidak ada bukti pembayaran yang perlu dihapus (< 24 jam)")
            return {'deleted': 0, 'failed': 0}

        deleted_count = 0
        failed_count = 0

        for peserta in old_payments:
            try:
                # Get full file path
                file_path = os.path.join(upload_folder, peserta.payment_proof)

                # Check if file exists and delete it
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"✅ Dihapus: {peserta.payment_proof} (Peserta: {peserta.nama})")
                    deleted_count += 1
                else:
                    logger.warning(f"⚠️  File tidak ditemukan: {file_path} (Peserta: {peserta.nama})")

                # Clear the payment_proof field from database
                peserta.payment_proof = None
                peserta.tanggal_verifikasi_pembayaran = None

            except Exception as e:
                logger.error(f"❌ Error menghapus {peserta.payment_proof}: {str(e)}")
                failed_count += 1
                continue

        # Save changes to database
        db.session.commit()

        logger.info(f"🗑️  Pembersihan bukti pembayaran selesai!")
        logger.info(f"   ✅ Dihapus: {deleted_count} file")
        logger.info(f"   ❌ Gagal: {failed_count} file")

        return {'deleted': deleted_count, 'failed': failed_count}

    except Exception as e:
        logger.error(f"❌ Error saat cleanup payment proofs: {str(e)}")
        db.session.rollback()
        return {'deleted': 0, 'failed': -1, 'error': str(e)}
