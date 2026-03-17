from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Peserta(db.Model):
    __tablename__ = 'peserta'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    whatsapp = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), nullable=True)
    alamat = db.Column(db.String(255), nullable=True)
    nama_bengkel = db.Column(db.String(100), nullable=True)
    alamat_bengkel = db.Column(db.String(255), nullable=True)
    status_pekerjaan = db.Column(db.String(50), nullable=True)
    alasan = db.Column(db.Text, nullable=True)
    batch = db.Column(db.String(50), default="Batch Baru")
    akses_workshop = db.Column(db.Boolean, default=False)
    akses_dokumen_bengkel = db.Column(db.Boolean, default=False)
    status_pembayaran = db.Column(db.String(20), default="Belum")
    whatsapp_link = db.Column(db.String(255), nullable=True)
    tanggal_daftar = db.Column(db.DateTime, default=datetime.utcnow)
    tanggal_izin_dokumen = db.Column(db.DateTime, nullable=True)
    tanggal_verifikasi_pembayaran = db.Column(db.DateTime, nullable=True)
    password_hash = db.Column(db.String(128), nullable=True)
    payment_proof = db.Column(db.String(255), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

class Batch(db.Model):
    __tablename__ = 'batch'
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(100), unique=True, nullable=False)
    whatsapp_link = db.Column(db.String(255), nullable=False)
    akses_workshop_default = db.Column(db.Boolean, default=False)
    aktif = db.Column(db.Boolean, default=True)
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.utcnow)

class Admin(db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class DocumentAccess(db.Model):
    __tablename__ = 'document_access'
    id = db.Column(db.Integer, primary_key=True)
    tipe_akses = db.Column(db.String(20), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    batch = db.relationship('Batch', backref='document_access')
    peserta_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=True)
    peserta = db.relationship('Peserta', backref='document_access')
    akses_diberikan = db.Column(db.Boolean, default=True)
    tanggal_mulai = db.Column(db.DateTime, default=datetime.utcnow)
    tanggal_kadaluarsa = db.Column(db.DateTime, nullable=True)
    catatan = db.Column(db.Text, nullable=True)
    dibuat_oleh = db.Column(db.String(50), nullable=True)
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.utcnow)
    tanggal_diubah = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_aktif(self):
        if not self.akses_diberikan:
            return False
        if self.tanggal_kadaluarsa:
            return datetime.utcnow() <= self.tanggal_kadaluarsa
        return True

class Announcement(db.Model):
    __tablename__ = 'announcement'
    id = db.Column(db.Integer, primary_key=True)
    judul = db.Column(db.String(255), nullable=False)
    isi = db.Column(db.Text, nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batch.id'), nullable=True)
    batch = db.relationship('Batch', backref='announcements')
    dibuat_oleh = db.Column(db.String(50), nullable=True)
    tanggal_dibuat = db.Column(db.DateTime, default=datetime.utcnow)
    tanggal_diubah = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    aktif = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<Announcement {self.id}: {self.judul}>"

class DocumentSyncLog(db.Model):
    __tablename__ = 'document_sync_log'
    id = db.Column(db.Integer, primary_key=True)
    tanggal_sync = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False)
    folder_baru = db.Column(db.Integer, default=0)
    folder_update = db.Column(db.Integer, default=0)
    file_baru = db.Column(db.Integer, default=0)
    file_update = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, nullable=True)
    durasi_detik = db.Column(db.Float, nullable=True)

class GoogleDriveFolder(db.Model):
    __tablename__ = 'google_drive_folder'
    id = db.Column(db.Integer, primary_key=True)
    drive_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('google_drive_folder.id'), nullable=True)
    path = db.Column(db.String(1024), nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)

    # Use lazy='dynamic' to get a query object instead of a list.
    # This is more efficient for large collections and avoids recursion issues.
    subfolders = db.relationship('GoogleDriveFolder',
                                 backref=db.backref('parent', remote_side=[id]),
                                 lazy='dynamic')
    files = db.relationship('GoogleDriveFile', backref='folder', lazy='dynamic')

class GoogleDriveFile(db.Model):
    __tablename__ = 'google_drive_file'
    id = db.Column(db.Integer, primary_key=True)
    drive_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    folder_id = db.Column(db.Integer, db.ForeignKey('google_drive_folder.id'), nullable=False)
    last_synced = db.Column(db.DateTime, default=datetime.utcnow)
    web_view_link = db.Column(db.String(1024))
    download_link = db.Column(db.String(1024))

class ChromaDocument(db.Model):
    __tablename__ = 'chroma_document'
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('google_drive_file.id'), nullable=False)
    file = db.relationship('GoogleDriveFile', backref='chroma_indexes')
    drive_id = db.Column(db.String(255), nullable=False)  # For quick lookup
    file_name = db.Column(db.String(255), nullable=False)
    chunk_count = db.Column(db.Integer, default=0)
    indexed_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = db.Column(db.String(20), default='indexed')  # 'indexed', 'pending', 'failed'
    error_message = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<ChromaDocument {self.file_name} ({self.chunk_count} chunks)>"

class ChatSession(db.Model):
    __tablename__ = 'chat_session'
    id = db.Column(db.Integer, primary_key=True)
    peserta_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    peserta = db.relationship('Peserta', backref='chat_sessions')
    title = db.Column(db.String(255), nullable=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    messages = db.relationship('ChatMessage', backref='session', cascade='all, delete-orphan')

class ChatMessage(db.Model):
    __tablename__ = 'chat_message'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' atau 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    tokens_used = db.Column(db.Integer, nullable=True)
    sources = db.relationship('ChatMessageSource', backref='message', cascade='all, delete-orphan')

class ChatMessageSource(db.Model):
    __tablename__ = 'chat_message_source'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('google_drive_file.id'), nullable=True)
    file_name = db.Column(db.String(255), nullable=False)
    relevance_score = db.Column(db.Float, default=0.0)

class ChatFeedback(db.Model):
    __tablename__ = 'chat_feedback'
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('chat_message.id'), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_session.id'), nullable=False)
    peserta_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    rating = db.Column(db.Integer)  # 1-5 stars
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================================
# NOTIFICATION MODELS
# ============================================================================

class TelegramNotificationLog(db.Model):
    """
    Log untuk melacak semua notifikasi Telegram yang dikirim ke admin
    Berguna untuk audit dan debugging
    """
    __tablename__ = 'telegram_notification_log'

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, nullable=False)  # Telegram user ID
    notification_type = db.Column(db.String(50), nullable=False)  # new_registration, payment_verified, etc
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    related_object_id = db.Column(db.Integer, nullable=True)  # ID peserta, batch, atau announcement
    related_object_type = db.Column(db.String(50), nullable=True)  # peserta, batch, announcement
    status = db.Column(db.String(20), default='sent')  # sent, failed, pending
    telegram_message_id = db.Column(db.String(255), nullable=True)  # Response message ID dari Telegram
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<TelegramNotification {self.notification_type} to {self.admin_id}>"


# ============================================================================
# LEARNING PLATFORM MODELS
# ============================================================================

# Many-to-many association table for learning sessions and files
learning_session_files = db.Table(
    'learning_session_files',
    db.Column('session_id', db.Integer, db.ForeignKey('learning_sessions.id'), primary_key=True),
    db.Column('file_id', db.Integer, db.ForeignKey('google_drive_file.id'), primary_key=True)
)

class LearningSession(db.Model):
    """
    Learning session dimana mekanik memilih files dari Google Drive
    dan belajar dengan diskusi/chat.
    """
    __tablename__ = 'learning_sessions'

    id = db.Column(db.Integer, primary_key=True)
    peserta_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    session_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    selected_files = db.relationship(
        'GoogleDriveFile',
        secondary=learning_session_files,
        backref='in_learning_sessions'
    )
    discussion_threads = db.relationship('DiscussionThread', backref='session', cascade='all, delete-orphan')
    quiz_attempts = db.relationship('UserQuizAttempt', backref='session', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<LearningSession {self.id}: {self.session_name}>'

class DiscussionThread(db.Model):
    """
    Discussion thread untuk mekanik berdiskusi tentang topik/dokumen
    dalam konteks learning session.
    """
    __tablename__ = 'discussion_threads'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('learning_sessions.id'), nullable=False)
    file_id = db.Column(db.Integer, db.ForeignKey('google_drive_file.id'))  # Optional
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    topic_category = db.Column(db.String(100))  # e.g., 'ignition', 'brake', etc
    created_by = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_closed = db.Column(db.Boolean, default=False)

    # Relationships
    posts = db.relationship('DiscussionPost', backref='thread', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DiscussionThread {self.id}: {self.title}>'

class DiscussionPost(db.Model):
    """
    Individual post dalam discussion thread.
    Bisa dari user atau AI-generated responses.
    """
    __tablename__ = 'discussion_posts'

    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.Integer, db.ForeignKey('discussion_threads.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_ai_generated = db.Column(db.Boolean, default=False)
    ai_confidence = db.Column(db.Float, default=0.0)  # 0.0-1.0 confidence score
    source_knowledge = db.Column(db.JSON)  # Store which files were used for AI response
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    reactions = db.relationship('PostReaction', backref='post', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DiscussionPost {self.id} in Thread {self.thread_id}>'

class PostReaction(db.Model):
    """
    Reactions to posts (helpful, agree, unclear, incorrect, etc)
    Helps identify valuable posts dalam diskusi.
    """
    __tablename__ = 'post_reactions'

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('discussion_posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    reaction_type = db.Column(
        db.String(50),
        nullable=False,
        default='helpful'
    )  # 'helpful', 'agree', 'unclear', 'incorrect'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Prevent duplicate reactions
    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', 'reaction_type', name='unique_reaction'),
    )

    def __repr__(self):
        return f'<PostReaction {self.reaction_type} on Post {self.post_id}>'

class StudyMaterial(db.Model):
    """
    Auto-generated study materials dari Google Drive documents.
    Bisa berupa guides, quiz, atau flashcards.
    """
    __tablename__ = 'study_materials'

    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('google_drive_file.id'), nullable=False)
    material_type = db.Column(
        db.String(50),
        nullable=False
    )  # 'guide', 'quiz', 'flashcard', 'summary'
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    content = db.Column(db.JSON)  # Store structured content
    difficulty_level = db.Column(db.String(50))  # 'beginner', 'intermediate', 'advanced'
    generated_by = db.Column(db.String(50))  # 'groq', 'manual'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    quiz_questions = db.relationship('QuizQuestion', backref='study_material', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<StudyMaterial {self.id}: {self.title}>'

class QuizQuestion(db.Model):
    """
    Quiz questions untuk study materials.
    Auto-generated dari documents menggunakan Groq LLM.
    """
    __tablename__ = 'quiz_questions'

    id = db.Column(db.Integer, primary_key=True)
    study_material_id = db.Column(db.Integer, db.ForeignKey('study_materials.id'), nullable=False)
    question = db.Column(db.Text, nullable=False)
    question_type = db.Column(
        db.String(50),
        default='multiple_choice'
    )  # 'multiple_choice', 'short_answer', 'true_false'
    options = db.Column(db.JSON)  # List of options for MC
    correct_answer = db.Column(db.String(255))
    explanation = db.Column(db.Text)  # Why this answer is correct
    difficulty = db.Column(db.String(50))  # 'easy', 'medium', 'hard'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    attempts = db.relationship('QuizAttempt', backref='question', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<QuizQuestion {self.id}>'

class UserQuizAttempt(db.Model):
    """
    Track user attempts untuk quizzes.
    Untuk measuring learning progress.
    """
    __tablename__ = 'user_quiz_attempts'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('learning_sessions.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    study_material_id = db.Column(db.Integer, db.ForeignKey('study_materials.id'), nullable=False)
    score = db.Column(db.Float)  # 0.0-100.0
    total_questions = db.Column(db.Integer)
    correct_answers = db.Column(db.Integer)
    time_taken_seconds = db.Column(db.Integer)
    completed_date = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    question_responses = db.relationship('QuizAttempt', backref='quiz_attempt', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<UserQuizAttempt {self.id}: User {self.user_id} Score {self.score}>'

class QuizAttempt(db.Model):
    """
    Individual question attempt dalam quiz.
    Untuk tracking per-question accuracy.
    """
    __tablename__ = 'quiz_attempts'

    id = db.Column(db.Integer, primary_key=True)
    quiz_attempt_id = db.Column(db.Integer, db.ForeignKey('user_quiz_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_questions.id'), nullable=False)
    user_answer = db.Column(db.String(255))
    is_correct = db.Column(db.Boolean)
    time_spent_seconds = db.Column(db.Integer)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<QuizAttempt Q{self.question_id}: {"Correct" if self.is_correct else "Incorrect"}>'

class UserCompetency(db.Model):
    """
    Track mekanik competency levels per topik/domain.
    Updated based on quiz scores dan discussion participation.
    """
    __tablename__ = 'user_competencies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    competency_area = db.Column(db.String(255), nullable=False)  # e.g., 'Engine Diagnostics'
    proficiency_level = db.Column(db.Float, default=0.0)  # 0.0-100.0
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    num_quizzes_passed = db.Column(db.Integer, default=0)
    discussion_posts = db.Column(db.Integer, default=0)
    verified_by_expert = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f'<UserCompetency {self.user_id}: {self.competency_area} {self.proficiency_level:.0f}%>'

class LearningActivityLog(db.Model):
    """
    Log semua learning activities untuk analytics.
    """
    __tablename__ = 'learning_activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('peserta.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('learning_sessions.id'))
    activity_type = db.Column(
        db.String(50),
        nullable=False
    )  # 'quiz', 'discussion', 'study', 'chat'
    topic = db.Column(db.String(255))
    description = db.Column(db.Text)
    score_or_engagement = db.Column(db.Float)  # For quiz: score, for discussion: engagement score
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LearningActivityLog {self.activity_type} by User {self.user_id}>'
