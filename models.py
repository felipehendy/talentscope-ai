from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Modelo de Usuário"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # MÉTODOS DE SENHA CORRIGIDOS
    def set_password(self, password):
        """Criptografa e armazena a senha."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica se a senha fornecida corresponde ao hash armazenado."""
        # A correção é garantir que este método exista e esteja correto.
        # O código fornecido pelo usuário já estava correto, mas o erro
        # ocorreu porque o banco de dados antigo não tinha o hash.
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Job(db.Model):
    """Modelo para Vagas"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    level = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    skills_required = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    
    candidates = db.relationship('Candidate', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Job {self.title}>'


class Candidate(db.Model):
    """Modelo para Candidatos"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    linkedin_url = db.Column(db.String(500))
    resume_path = db.Column(db.String(500))

    # AQUI — campo que está faltando!
    resume_text = db.Column(db.Text)

    # Análise IA
    extracted_skills = db.Column(db.Text)
    seniority_detected = db.Column(db.String(50))
    experience_summary = db.Column(db.Text)
    strengths = db.Column(db.Text)
    weaknesses = db.Column(db.Text)
    hard_skills_score = db.Column(db.Float, default=0.0)
    soft_skills_score = db.Column(db.Float, default=0.0)
    overall_score = db.Column(db.Float, default=0.0)
    professional_summary = db.Column(db.Text)
    recommendation = db.Column(db.Text)
    potential_risks = db.Column(db.Text)

    status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    interviews = db.relationship('Interview', backref='candidate', lazy=True)

    def __repr__(self):
        return f'<Candidate {self.name}>'



class Interview(db.Model):
    """Modelo para Entrevistas"""
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    scheduled_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    meeting_link = db.Column(db.String(500))
    notes = db.Column(db.Text)
    status = db.Column(db.String(50), default='scheduled')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Interview {self.id}>'


class WhatsAppLog(db.Model):
    """Log de mensagens WhatsApp enviadas"""
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'))
    message_type = db.Column(db.String(50))
    message_text = db.Column(db.Text)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='sent')
    
    def __repr__(self):
        return f'<WhatsAppLog {self.id}>'
