import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_migrate import Migrate
import pandas as pd 
from ai_analyzer import AIAnalyzer
import json
from urllib.parse import quote
from sqlalchemy import text
import logging
import re
import sys
import io

# Importar validadores
from utils.validators import (
    allowed_file,
    validate_email,
    validate_phone,
    sanitize_filename,
    validate_file_size,
    validate_pdf_content,
    validate_username,
    validate_password
)

# ==================== CONFIGURAÇÃO ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sua-chave-secreta-super-segura-123')

# Database - PostgreSQL em produção, SQLite local
database_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Criar pasta de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Inicializar IA
ai_analyzer = AIAnalyzer()
logger.info(f" Provider configurado: {ai_analyzer.get_current_provider()}")

app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax'
)

# ==================== FILTROS JINJA ====================
@app.template_filter('whatsapp_link')
def whatsapp_link(phone):
    """Gera link para abrir WhatsApp"""
    if not phone:
        return '#'
    
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    
    if len(clean_phone) <= 11 and not clean_phone.startswith('55'):
        clean_phone = '55' + clean_phone
    
    return f'https://wa.me/{clean_phone}'

@app.template_filter('urlencode')
def urlencode_filter(s):
    """Encode para URL"""
    return quote(str(s))

# ==================== MODELS ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    candidates = db.relationship('Candidate', backref='job', lazy=True, cascade='all, delete-orphan')

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    resume_path = db.Column(db.String(500))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    ai_score = db.Column(db.Float)
    ai_analysis = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resume_text = db.Column(db.Text)

class Interview(db.Model):
    """Model para entrevistas agendadas"""
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    interviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Informações da entrevista
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    interview_type = db.Column(db.String(50), default='presencial')
    
    # Data e hora
    scheduled_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    
    # Status
    status = db.Column(db.String(20), default='scheduled')
    
    # Links e localização
    meeting_link = db.Column(db.String(500))
    location = db.Column(db.String(300))
    
    # Notas
    notes = db.Column(db.Text)
    feedback = db.Column(db.Text)
    rating = db.Column(db.Integer)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    candidate = db.relationship('Candidate', backref='interviews')
    job = db.relationship('Job', backref='interviews')
    interviewer = db.relationship('User', backref='conducted_interviews')

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# ==================== FUNÇÕES AUXILIARES ====================
def safe_delete_file(filepath):
    """Remove arquivo com segurança"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"[OK] Arquivo deletado: {filepath}")
            return True
    except Exception as e:
        logger.error(f"[ERROR] Erro ao deletar arquivo {filepath}: {e}")
    return False

def extract_text_from_pdf(file_path):
    """Extrai texto de PDF com fallback"""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + '\n'
        return text.strip()
    except Exception as e:
        logger.warning(f"pdfplumber falhou, tentando PyPDF2: {e}")
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ''
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + '\n'
                return text.strip()
        except Exception as e2:
            logger.error(f"Erro ao extrair texto do PDF: {e2}")
            return ''

def extract_candidate_info(resume_text, filename):
    """Extrai nome, email e telefone do currículo"""
    import re
    
    name = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
    
    first_lines = resume_text.split('\n')[:10]
    for line in first_lines:
        line = line.strip()
        if 5 < len(line) < 50 and not any(char.isdigit() for char in line) and ' ' in line:
            if len(line.split()) <= 4:
                name = line.title()
                break
    
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, resume_text)
    
    if emails:
        email = emails[0].lower()
    else:
        email_base = name.lower().replace(' ', '.').replace('..', '.')
        email = f'{email_base}@temporario.pendente'
    
    phone_patterns = [
        r'\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}',
        r'\+55\s*\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}',
        r'\d{2}\s*9\d{8}',
    ]
    
    phone = ''
    for pattern in phone_patterns:
        phones = re.findall(pattern, resume_text)
        if phones:
            phone = re.sub(r'[^\d]', '', phones[0])
            if len(phone) == 11 and phone[2] == '9':
                phone = '55' + phone
            elif len(phone) == 10:
                phone = '55' + phone
            break
    
    return {
        'name': name,
        'email': email,
        'phone': phone
    }

# ==================== ROTAS DE AUTENTICAÇÃO ====================

# ==================== ROTAS DO CHATBOT ====================

@app.route('/chatbot')
@login_required
def chatbot_page():
    """Página do Chatbot Tess"""
    # Buscar dados para contexto inicial
    total_candidates = Candidate.query.filter(
        Candidate.ai_score != None,
        Candidate.ai_score > 0
    ).count()
    
    total_jobs = Job.query.filter_by(status='active').count()
    
    return render_template('chatbot.html', 
                         total_candidates=total_candidates,
                         total_jobs=total_jobs)


@app.route('/api/chatbot/context', methods=['GET'])
@login_required
def chatbot_context():
    """Retorna contexto (candidatos e vagas) para o chatbot"""
    try:
        # Buscar candidatos com score
        candidates = Candidate.query.filter(
            Candidate.ai_score != None,
            Candidate.ai_score > 0
        ).all()
        
        jobs = Job.query.filter_by(status='active').all()
        
        candidates_data = []
        for c in candidates:
            try:
                job = db.session.get(Job, c.job_id) if c.job_id else None
                
                # Parse da análise IA
                analysis = {}
                if c.ai_analysis:
                    try:
                        analysis = json.loads(c.ai_analysis)
                    except:
                        analysis = {}
                
                candidates_data.append({
                    'id': c.id,
                    'name': c.name or 'Sem nome',
                    'email': c.email or '',
                    'phone': c.phone or '',
                    'job_title': job.title if job else 'Sem vaga',
                    'job_id': c.job_id,
                    'score': float(c.ai_score or 0),
                    'status': c.status,
                    
                    # Dados da análise IA
                    'strengths': analysis.get('strengths', []),
                    'weaknesses': analysis.get('weaknesses', []),
                    'recommendation': analysis.get('recommendation', ''),
                    'summary': analysis.get('summary', ''),
                    'technical_skills': analysis.get('technical_skills', []),
                    'experience_level': analysis.get('experience_level', 'Não especificado'),
                    
                    'created_at': c.created_at.strftime('%d/%m/%Y') if c.created_at else ''
                })
            except Exception as e:
                logger.error(f"[ERROR] Erro ao processar candidato {c.id}: {e}")
                continue
        
        jobs_data = []
        for j in jobs:
            try:
                candidates_count = Candidate.query.filter_by(job_id=j.id).count()
                jobs_data.append({
                    'id': j.id,
                    'title': j.title,
                    'description': j.description or '',
                    'requirements': j.requirements or '',
                    'status': j.status,
                    'candidates_count': candidates_count,
                    'created_at': j.created_at.strftime('%d/%m/%Y') if j.created_at else ''
                })
            except Exception as e:
                logger.error(f"[ERROR] Erro ao processar vaga {j.id}: {e}")
                continue
        
        logger.info(f"[OK] Contexto carregado: {len(candidates_data)} candidatos, {len(jobs_data)} vagas")
        
        return jsonify({
            'success': True,
            'candidates': candidates_data,
            'jobs': jobs_data
        })
        
    except Exception as e:
        logger.error(f"[ERROR] Erro ao buscar contexto: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'error': str(e),
            'candidates': [],
            'jobs': []
        }), 200


@app.route('/api/chatbot/query', methods=['POST'])
@login_required
def chatbot_query():
    """Endpoint para processar perguntas do chatbot"""
    try:
        data = request.get_json()
        user_query = data.get('query', '').strip()
        
        if not user_query:
            return jsonify({'error': 'Query vazia'}), 400
        
        logger.info(f"[CHAT] Pergunta recebida: {user_query}")
        
        # Buscar contexto (candidatos e vagas)
        candidates = Candidate.query.filter(
            Candidate.ai_score != None,
            Candidate.ai_score > 0
        ).all()
        
        jobs = Job.query.filter_by(status='active').all()
        
        # Montar contexto dos candidatos
        candidates_context = []
        for c in candidates:
            try:
                job = db.session.get(Job, c.job_id) if c.job_id else None
                
                # Parse da análise IA
                analysis = {}
                if c.ai_analysis:
                    try:
                        analysis = json.loads(c.ai_analysis)
                    except:
                        analysis = {}
                
                # [OK] TODOS OS CAMPOS QUE O CHATBOT_SERVICE.PY ESPERA
                technical_skills = analysis.get('technical_skills', [])
                skills_str = ', '.join(technical_skills) if isinstance(technical_skills, list) else str(technical_skills)
                
                candidates_context.append({
                    # Campos básicos
                    'id': c.id,
                    'name': c.name,
                    'email': c.email,
                    'phone': c.phone or '',
                    'vaga_aplicada': job.title if job else 'Sem vaga',
                    'job_id': c.job_id,
                    
                    # Scores (EXATOS como o chatbot_service.py espera)
                    'score_geral': round(float(c.ai_score or 0), 1),
                    'score_hard_skills': round(float(c.ai_score or 0) * 0.6, 1),
                    'score_soft_skills': round(float(c.ai_score or 0) * 0.4, 1),
                    
                    # Status e senioridade
                    'status': c.status,
                    'senioridade': analysis.get('experience_level', 'Não especificado'),
                    
                    # Análise detalhada
                    'pontos_fortes': analysis.get('strengths', []),
                    'pontos_atencao': analysis.get('weaknesses', []),
                    'recomendacao': analysis.get('recommendation', ''),
                    
                    # Skills (campo que o chatbot_service.py usa)
                    'skills_extraidas': skills_str,
                })
            except Exception as e:
                logger.error(f"[ERROR] Erro ao processar candidato {c.id}: {e}")
                continue
        
        # Montar contexto das vagas
        jobs_context = []
        for j in jobs:
            try:
                candidates_count = Candidate.query.filter_by(job_id=j.id).count()
                
                # [OK] TODOS OS CAMPOS QUE O CHATBOT_SERVICE.PY ESPERA
                jobs_context.append({
                    'id': j.id,
                    'titulo': j.title,
                    'nivel': 'Pleno',  # ← Ajuste se tiver no banco
                    'descricao': j.description or '',
                    'requisitos': j.requirements or '',
                    'skills_requeridas': j.requirements or '',  # ← Campo que o chatbot espera
                    'status': j.status,
                    'total_candidatos': candidates_count,
                })
            except Exception as e:
                logger.error(f"[ERROR] Erro ao processar vaga {j.id}: {e}")
                continue
        
        # Verificar se há dados
        if not candidates_context and not jobs_context:
            response_text = """[WARN] **Sistema sem dados**

Não encontrei candidatos nem vagas no sistema.

**O que fazer:**
1. Cadastre vagas em "Gerenciar Vagas"
2. Faça upload de currículos
3. Aguarde a análise da IA
4. Volte aqui para fazer perguntas"""
            
            return jsonify({
                'success': True,
                'response': response_text
            })
        
        if not candidates_context:
            response_text = """[WARN] **Nenhum candidato analisado**

Encontrei vagas, mas nenhum candidato com análise completa.

**Próximos passos:**
- Faça upload de currículos
- Aguarde a análise automática
- Depois poderei responder suas perguntas"""
            
            return jsonify({
                'success': True,
                'response': response_text
            })
        
        # Importar e usar o serviço de chatbot
        try:
            from chatbot_service import TessChatbotService
            
            service = TessChatbotService()
            
            # Construir prompt
            response = service.process_query(candidates=candidates_context, jobs=jobs_context, user_query=user_query)
            
            # Chamar Tess
            # response_text = service.call_tess(prompt)
            
            logger.info(f"[OK] Resposta gerada com sucesso")
            
            return jsonify({
                'success': response.success,
                'response': response.content,
                'function_type': response.function_type.name if hasattr(response, 'function_type') else None,
                'metadata': response.metadata if hasattr(response, 'metadata') else {},
                'error': response.error if hasattr(response, 'error') else None
            })
            
        except ImportError:
            logger.error("[ERROR] chatbot_service.py não encontrado!")
            return jsonify({
                'success': False,
                'error': 'Serviço de chatbot não disponível',
                'response': '[ERROR] Erro: Módulo chatbot_service não encontrado. Verifique se o arquivo existe.'
            }), 200
        
    except Exception as e:
        logger.error(f"[ERROR] Erro no chatbot: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Erro ao processar pergunta',
            'response': f'[ERROR] Desculpe, ocorreu um erro ao processar sua pergunta. Tente novamente.'
        }), 200

@app.route('/')
def index():
    """Rota principal"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    user_count = User.query.count()
    
    if user_count == 0:
        flash('Bem-vindo! Crie sua conta para começar.', 'info')
        return redirect(url_for('register'))
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login com validações"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if User.query.count() == 0:
        flash('Nenhum usuário cadastrado. Crie sua conta primeiro.', 'warning')
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('[ERROR] Preencha todos os campos!', 'danger')
            return render_template('login.html')
        
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'[OK] Bem-vindo, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('[ERROR] Usuário ou senha incorretos!', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de usuários"""
    user_count = User.query.count()
    is_first_user = (user_count == 0)
    
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not username or not email or not password or not confirm_password:
            flash('[ERROR] Todos os campos são obrigatórios!', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        valid, error = validate_username(username)
        if not valid:
            flash(f'[ERROR] {error}', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        if not validate_email(email):
            flash('[ERROR] Email inválido! Use o formato: exemplo@email.com', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        valid, error = validate_password(password)
        if not valid:
            flash(f'[ERROR] {error}', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        if password != confirm_password:
            flash('[ERROR] As senhas não coincidem!', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        if User.query.filter_by(username=username).first():
            flash('[ERROR] Nome de usuário já existe!', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        if User.query.filter_by(email=email).first():
            flash('[ERROR] Email já cadastrado!', 'danger')
            return render_template('register.html', is_first_user=is_first_user)
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_first_user
        )
        
        try:
            db.session.add(user)
            db.session.commit()
            
            if is_first_user:
                flash('[OK] Conta de administrador criada com sucesso! Faça login.', 'success')
            else:
                flash('[OK] Conta criada com sucesso! Faça login.', 'success')
            
            logger.info(f"[OK] Usuário criado: {username} (Admin: {is_first_user})")
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar usuário: {e}")
            flash('[ERROR] Erro ao criar conta. Tente novamente.', 'danger')
    
    return render_template('register.html', is_first_user=is_first_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('login'))

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Alterar senha do usuário"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not all([current_password, new_password, confirm_password]):
            flash('[ERROR] Preencha todos os campos!', 'danger')
            return render_template('change_password.html')
        
        if not check_password_hash(current_user.password_hash, current_password):
            flash('[ERROR] Senha atual incorreta!', 'danger')
            return render_template('change_password.html')
        
        if new_password != confirm_password:
            flash('[ERROR] As novas senhas não coincidem!', 'danger')
            return render_template('change_password.html')
        
        valid, error = validate_password(new_password)
        if not valid:
            flash(f'[ERROR] {error}', 'danger')
            return render_template('change_password.html')
        
        try:
            current_user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            
            flash('[OK] Senha alterada com sucesso!', 'success')
            logger.info(f"[OK] Usuário {current_user.username} alterou a senha")
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao alterar senha: {e}")
            flash('[ERROR] Erro ao alterar senha. Tente novamente.', 'danger')
    
    return render_template('change_password.html')

@app.route('/request-access', methods=['GET', 'POST'])
def request_access():
    """Solicitar acesso ao sistema"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        reason = request.form.get('reason', '').strip()
        
        if not all([name, email, reason]):
            flash('[ERROR] Preencha todos os campos!', 'danger')
            return render_template('request_access.html')
        
        if not validate_email(email):
            flash('[ERROR] Email inválido!', 'danger')
            return render_template('request_access.html')
        
        if User.query.filter_by(email=email).first():
            flash('[ERROR] Este email já está cadastrado. Faça login ou recupere sua senha.', 'danger')
            return redirect(url_for('login'))
        
        try:
            logger.info(f" Solicitação de acesso: {name} ({email}) - Motivo: {reason}")
            flash('[OK] Solicitação enviada! Entraremos em contato em breve.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            logger.error(f"[ERROR] Erro ao processar solicitação: {e}")
            flash('[ERROR] Erro ao enviar solicitação. Tente novamente.', 'danger')
    
    return render_template('request_access.html')

# ==================== DASHBOARD ====================
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard com métricas"""
    total_jobs = Job.query.count()
    total_candidates = Candidate.query.count()
    pending_candidates = Candidate.query.filter_by(status='pending').count()
    
    candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
    avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score) if candidates_with_score else 0.0
    
    # Total de entrevistas
    total_interviews = Interview.query.count()
    
    jobs = Job.query.all()
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
    recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
    
    top_skills = [
        ('Python', 15),
        ('JavaScript', 12),
        ('React', 10),
        ('SQL', 8),
        ('Docker', 6),
    ]
    
    seniority_counts = {
        'Júnior': 8,
        'Pleno': 12,
        'Sênior': 6,
        'Especialista': 3,
    }
    
    return render_template('dashboard.html',
                         total_jobs=total_jobs,
                         total_candidates=total_candidates,
                         pending_candidates=pending_candidates,
                         avg_score=avg_score,
                         total_interviews=total_interviews,
                         jobs=jobs,
                         top_skills=top_skills,
                         seniority_counts=seniority_counts,
                         recent_jobs=recent_jobs,
                         recent_candidates=recent_candidates,
                         now=datetime.utcnow())

# ==================== ROTAS DE VAGAS ====================
@app.route('/jobs')
@login_required
def jobs():
    """Listar vagas"""
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('jobs.html', jobs=all_jobs)

@app.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    """Criar nova vaga"""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        requirements = request.form.get('requirements', '').strip()
        
        if not title:
            flash('[ERROR] Título da vaga é obrigatório!', 'danger')
            return render_template('new_job.html')
        
        if len(title) < 3:
            flash('[ERROR] Título deve ter no mínimo 3 caracteres!', 'danger')
            return render_template('new_job.html')
        
        job = Job(
            title=title,
            description=description,
            requirements=requirements,
            created_by=current_user.id
        )
        
        try:
            db.session.add(job)
            db.session.commit()
            flash(f'[OK] Vaga "{title}" criada com sucesso!', 'success')
            return redirect(url_for('jobs'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar vaga: {e}")
            flash('[ERROR] Erro ao criar vaga. Tente novamente.', 'danger')
    
    return render_template('new_job.html')

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    """Detalhes da vaga"""
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).order_by(Candidate.ai_score.desc()).all()
    return render_template('job_detail.html', job=job, candidates=candidates)

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    """Excluir vaga e candidatos"""
    job = Job.query.get_or_404(job_id)
    
    try:
        candidates = Candidate.query.filter_by(job_id=job_id).all()
        for candidate in candidates:
            if candidate.resume_path:
                safe_delete_file(candidate.resume_path)
        
        Candidate.query.filter_by(job_id=job_id).delete()
        db.session.delete(job)
        db.session.commit()
        
        flash(f'[OK] Vaga "{job.title}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir vaga: {e}")
        flash('[ERROR] Erro ao excluir vaga. Tente novamente.', 'danger')
    
    return redirect(url_for('jobs'))

@app.route('/jobs/<int:job_id>/reanalyze-all', methods=['POST'])
@login_required
def reanalyze_all_candidates_for_job(job_id):
    """Reanalisa todos os candidatos de uma vaga"""
    job = Job.query.get_or_404(job_id)
    candidates = job.candidates

    if not candidates:
        flash('Não há candidatos para reanalisar nesta vaga.', 'info')
        return redirect(url_for('job_detail', job_id=job_id))

    success_count = 0
    error_count = 0

    job_requirements = {
        'title': job.title,
        'level': 'Não especificado',
        'description': job.description or '',
        'requirements': job.requirements or ''
    }

    for candidate in candidates:
        if not candidate.resume_text:
            error_count += 1
            logger.warning(f"Candidato {candidate.name} (ID: {candidate.id}) ignorado: sem texto de currículo.")
            continue

        try:
            candidate_data = {
                'name': candidate.name,
                'resume_text': candidate.resume_text
            }
            
            logger.info(f"[BOT] Reanalisando {candidate.name} para a vaga '{job.title}'...")
            new_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)

            if 'overall_score' in new_analysis:
                candidate.ai_score = new_analysis['overall_score']
                candidate.ai_analysis = json.dumps(new_analysis)
                success_count += 1
            else:
                error_count += 1
                logger.warning(f"Falha na reanálise de {candidate.name}: resposta da IA incompleta.")

        except Exception as e:
            error_count += 1
            logger.error(f"[ERROR] Erro ao reanalisar candidato {candidate.id}: {e}")

    try:
        db.session.commit()
        flash(f'[OK] Reanálise concluída! {success_count} candidatos atualizados.', 'success')
        if error_count > 0:
            flash(f'[WARN] {error_count} candidatos não puderam ser reanalisados.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao salvar reanálises no banco: {e}")
        flash('[ERROR] Ocorreu um erro ao salvar as atualizações no banco de dados.', 'danger')

    return redirect(url_for('job_detail', job_id=job_id))

# ==================== ROTAS DE CANDIDATOS ====================
@app.route('/candidates/new/<int:job_id>', methods=['GET', 'POST'])
@login_required
def new_candidate(job_id):
    """Adicionar novo candidato"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'GET':
        return render_template('new_candidate.html', job=job)
    
    try:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if not name:
            flash('[ERROR] Nome é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not email:
            flash('[ERROR] Email é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not phone:
            flash('[ERROR] Telefone é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not validate_email(email):
            flash('[ERROR] Email inválido! Use o formato: exemplo@email.com', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not validate_phone(phone):
            flash('[ERROR] Telefone inválido! Use formato: DDD + Número (ex: 11999999999)', 'danger')
            return render_template('new_candidate.html', job=job)
        
        file = request.files.get('resume')
        
        if not file or not file.filename:
            flash('[ERROR] É necessário enviar um currículo em PDF!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not allowed_file(file.filename):
            flash('[ERROR] Apenas arquivos PDF são permitidos!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        valid_size, size_error = validate_file_size(file, max_size_mb=16)
        if not valid_size:
            flash(f'[ERROR] {size_error}', 'danger')
            return render_template('new_candidate.html', job=job)
        
        filename = sanitize_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f" Arquivo salvo: {filepath}")
        
        valid_pdf, pdf_error = validate_pdf_content(filepath)
        if not valid_pdf:
            safe_delete_file(filepath)
            flash(f'[ERROR] PDF inválido: {pdf_error}', 'danger')
            return render_template('new_candidate.html', job=job)
        
        resume_text = extract_text_from_pdf(filepath)
        
        if not resume_text or len(resume_text.strip()) < 50:
            safe_delete_file(filepath)
            flash('[ERROR] Não foi possível extrair texto do PDF. Verifique o arquivo.', 'danger')
            return render_template('new_candidate.html', job=job)
        
        logger.info(f"[FILE] Texto extraído: {len(resume_text)} caracteres")
        
        try:
            candidate_data = {
                'name': name,
                'resume_text': resume_text
            }
            
            job_requirements = {
                'title': job.title,
                'level': 'Não especificado',
                'description': job.description or '',
                'requirements': job.requirements or ''
            }
            
            logger.info(f"[BOT] Iniciando análise IA...")
            ai_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)
            ai_score = ai_analysis.get('overall_score', 50)
            logger.info(f"[OK] Análise concluída. Score: {ai_score}")
            
        # CONTINUAÇÃO DO ARQUIVO app.py
# Cole isso após a linha "except Exception" da parte 1

        except Exception as e:
            logger.error(f"[WARN] Erro na análise IA: {e}")
            ai_analysis = {
                'overall_score': 50,
                'recommendation': 'Análise manual necessária',
                'strengths': ['Análise automática indisponível'],
                'weaknesses': ['Requer revisão manual'],
                'summary': f'Erro: {str(e)}'
            }
            ai_score = 50
        
        candidate = Candidate(
            name=name,
            email=email,
            phone=phone,
            resume_path=filepath,
            resume_text=resume_text,
            job_id=job_id,
            ai_score=ai_score,
            ai_analysis=json.dumps(ai_analysis),
            status='pending'
        )
        
        db.session.add(candidate)
        db.session.commit()
        
        logger.info(f"[OK] Candidato {name} cadastrado (ID: {candidate.id})")
        flash(f'[OK] Candidato {name} adicionado! Score IA: {ai_score}', 'success')
        return redirect(url_for('candidate_detail', candidate_id=candidate.id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao adicionar candidato: {e}")
        
        if 'filepath' in locals() and filepath:
            safe_delete_file(filepath)
        
        flash('[ERROR] Erro ao adicionar candidato. Tente novamente.', 'danger')
        return render_template('new_candidate.html', job=job)

@app.route('/candidates/<int:candidate_id>')
@login_required
def candidate_detail(candidate_id):
    """Detalhes do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    analysis = {}
    if candidate.ai_analysis:
        try:
            analysis = json.loads(candidate.ai_analysis)
        except:
            pass
    
    return render_template('candidate_detail.html', candidate=candidate, analysis=analysis)

@app.route('/candidates/<int:candidate_id>/status', methods=['POST'])
@login_required
def update_candidate_status(candidate_id):
    """Atualizar status do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    new_status = request.form.get('status')
    
    if new_status in ['pending', 'interview', 'approved', 'rejected']:
        candidate.status = new_status
        db.session.commit()
        flash('[OK] Status atualizado!', 'success')
    else:
        flash('[ERROR] Status inválido!', 'danger')
    
    return redirect(url_for('candidate_detail', candidate_id=candidate_id))

@app.route('/candidate/<int:candidate_id>/reanalyze', methods=['POST'])
@login_required
def reanalyze_candidate(candidate_id):
    """Reanalisar candidato com IA"""
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get_or_404(candidate.job_id)
    
    resume_text = candidate.resume_text 
    
    if not resume_text:
        flash('[ERROR] Texto do currículo não encontrado!', 'danger')
        return redirect(url_for('candidate_detail', candidate_id=candidate.id))

    try:
        candidate_data = {
            'name': candidate.name,
            'resume_text': resume_text
        }
        job_requirements = {
            'title': job.title,
            'level': 'Não especificado',
            'description': job.description,
            'requirements': job.requirements
        }

        new_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)

        if 'overall_score' in new_analysis:
            candidate.ai_score = new_analysis['overall_score']
            candidate.ai_analysis = json.dumps(new_analysis)
            db.session.commit()
            flash('[OK] Análise atualizada com sucesso!', 'success')
        else:
            flash('[ERROR] Erro na reanálise. Verifique os logs.', 'danger')
    
    except Exception as e:
        logger.error(f"Erro ao reanalisar: {e}")
        flash('[ERROR] Erro ao reanalisar candidato.', 'danger')

    return redirect(url_for('candidate_detail', candidate_id=candidate.id))

@app.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@login_required
def delete_candidate(candidate_id):
    """Excluir candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    job_id = candidate.job_id
    
    try:
        if candidate.resume_path:
            safe_delete_file(candidate.resume_path)
        
        db.session.delete(candidate)
        db.session.commit()
        
        flash(f'[OK] Candidato "{candidate.name}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir candidato: {e}")
        flash('[ERROR] Erro ao excluir candidato.', 'danger')
    
    return redirect(url_for('job_detail', job_id=job_id))

# ==================== ROTAS DE ENTREVISTAS ====================
@app.route('/interviews')
@login_required
def interviews_list():
    """Lista todas as entrevistas"""
    status_filter = request.args.get('status', 'all')
    date_filter = request.args.get('date', 'all')
    
    query = Interview.query
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if date_filter == 'today':
        today = datetime.utcnow().date()
        query = query.filter(db.func.date(Interview.scheduled_date) == today)
    elif date_filter == 'week':
        week_start = datetime.utcnow().date()
        week_end = week_start + timedelta(days=7)
        query = query.filter(Interview.scheduled_date.between(week_start, week_end))
    
    interviews = query.order_by(Interview.scheduled_date.desc()).all()
    
    total_interviews = Interview.query.count()
    scheduled = Interview.query.filter_by(status='scheduled').count()
    completed = Interview.query.filter_by(status='completed').count()
    cancelled = Interview.query.filter_by(status='cancelled').count()
    
    return render_template('interviews_list.html',
                         interviews=interviews,
                         total_interviews=total_interviews,
                         scheduled=scheduled,
                         completed=completed,
                         cancelled=cancelled,
                         status_filter=status_filter,
                         date_filter=date_filter)

@app.route('/interviews/calendar')
@login_required
def calendar():
    """Calendário de entrevistas"""
    interviews = Interview.query.filter_by(status='scheduled').all()
    
    calendar_events = []
    for interview in interviews:
        event = {
            'id': interview.id,
            'title': f"{interview.candidate.name} - {interview.title}",
            'start': interview.scheduled_date.isoformat(),
            'end': (interview.scheduled_date + timedelta(minutes=interview.duration_minutes)).isoformat(),
            'description': interview.description or '',
            'type': interview.interview_type,
            'candidate_name': interview.candidate.name,
            'job_title': interview.job.title
        }
        calendar_events.append(event)
    
    return render_template('calendar.html', 
                         events=calendar_events,
                         events_json=json.dumps(calendar_events))

@app.route('/interviews/new', methods=['GET', 'POST'])
@login_required
def new_interview():
    """Criar nova entrevista"""
    if request.method == 'POST':
        candidate_id = request.form.get('candidate_id')
        job_id = request.form.get('job_id')
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        interview_type = request.form.get('interview_type', 'presencial')
        
        date_str = request.form.get('date')
        time_str = request.form.get('time')
        duration = request.form.get('duration', 60, type=int)
        
        if not all([candidate_id, job_id, title, date_str, time_str]):
            flash('[ERROR] Preencha todos os campos obrigatórios!', 'danger')
            return redirect(url_for('new_interview'))
        
        try:
            scheduled_datetime = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            
            if scheduled_datetime < datetime.utcnow():
                flash('[ERROR] A data da entrevista não pode estar no passado!', 'danger')
                return redirect(url_for('new_interview'))
            
            meeting_link = request.form.get('meeting_link', '').strip()
            location = request.form.get('location', '').strip()
            notes = request.form.get('notes', '').strip()
            
            interview = Interview(
                candidate_id=candidate_id,
                job_id=job_id,
                interviewer_id=current_user.id,
                title=title,
                description=description,
                interview_type=interview_type,
                scheduled_date=scheduled_datetime,
                duration_minutes=duration,
                meeting_link=meeting_link if meeting_link else None,
                location=location if location else None,
                notes=notes if notes else None,
                status='scheduled'
            )
            
            db.session.add(interview)
            
            candidate = db.session.get(Candidate, candidate_id)
            if candidate and candidate.status == 'pending':
                candidate.status = 'interview'
            
            db.session.commit()
            
            flash(f'[OK] Entrevista agendada com sucesso!', 'success')
            logger.info(f"[OK] Entrevista criada: {title} (ID: {interview.id})")
            return redirect(url_for('interview_detail', interview_id=interview.id))
            
        except ValueError as e:
            flash('[ERROR] Data ou hora inválida!', 'danger')
            return redirect(url_for('new_interview'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao criar entrevista: {e}")
            flash('[ERROR] Erro ao agendar entrevista. Tente novamente.', 'danger')
    
    candidates = Candidate.query.filter(
        Candidate.status.in_(['pending', 'interview'])
    ).all()
    jobs = Job.query.filter_by(status='active').all()
    
    candidate_id = request.args.get('candidate_id')
    selected_candidate = None
    if candidate_id:
        selected_candidate = db.session.get(Candidate, candidate_id)
    
    return render_template('new_interview.html',
                         candidates=candidates,
                         jobs=jobs,
                         selected_candidate=selected_candidate)

@app.route('/interviews/<int:interview_id>')
@login_required
def interview_detail(interview_id):
    """Detalhes da entrevista"""
    interview = Interview.query.get_or_404(interview_id)
    return render_template('interview_detail.html', interview=interview)

@app.route('/interviews/<int:interview_id>/update-status', methods=['POST'])
@login_required
def update_interview_status(interview_id):
    """Atualizar status da entrevista"""
    interview = Interview.query.get_or_404(interview_id)
    new_status = request.form.get('status')
    
    if new_status in ['scheduled', 'completed', 'cancelled', 'rescheduled']:
        interview.status = new_status
        
        if new_status == 'completed':
            feedback = request.form.get('feedback', '').strip()
            rating = request.form.get('rating', type=int)
            
            if feedback:
                interview.feedback = feedback
            if rating and 1 <= rating <= 5:
                interview.rating = rating
        
        db.session.commit()
        flash('[OK] Status da entrevista atualizado!', 'success')
    else:
        flash('[ERROR] Status inválido!', 'danger')
    
    return redirect(url_for('interview_detail', interview_id=interview_id))

@app.route('/interviews/<int:interview_id>/delete', methods=['POST'])
@login_required
def delete_interview(interview_id):
    """Excluir entrevista"""
    interview = Interview.query.get_or_404(interview_id)
    
    try:
        db.session.delete(interview)
        db.session.commit()
        flash('[OK] Entrevista excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"[ERROR] Erro ao excluir entrevista: {e}")
        flash('[ERROR] Erro ao excluir entrevista.', 'danger')
    
    return redirect(url_for('interviews_list'))

@app.route('/candidate/<int:candidate_id>/schedule-interview', methods=['GET', 'POST'])
@login_required
def schedule_interview_from_candidate(candidate_id):
    """Agendar entrevista a partir do perfil do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    if request.method == 'POST':
        return redirect(url_for('new_interview', candidate_id=candidate_id))
    
    return render_template('schedule_interview_from_candidate.html', candidate=candidate)

# ==================== BULK UPLOAD E IMPORT ====================
@app.route('/jobs/<int:job_id>/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_candidates(job_id):
    """Upload em massa de candidatos via PDF"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        if 'pdf_files' not in request.files:
            logger.error(f"[ERROR] Campo 'pdf_files' não encontrado. Campos disponíveis: {list(request.files.keys())}")
            flash('[ERROR] Nenhum arquivo enviado!', 'danger')
            return redirect(url_for('bulk_upload_candidates', job_id=job_id))
        
        files = request.files.getlist('pdf_files')
        
        if not files or len(files) == 0 or files[0].filename == '':
            flash('[ERROR] Nenhum arquivo selecionado!', 'danger')
            return redirect(url_for('bulk_upload_candidates', job_id=job_id))
        
        logger.info(f" Recebidos {len(files)} arquivo(s) para upload")
        
        success_count = 0
        error_count = 0
        errors = []
        
        for file in files:
            filename = file.filename
            
            if not filename:
                continue
            
            logger.info(f"[FILE] Processando: {filename}")
            
            if not allowed_file(filename):
                error_count += 1
                errors.append(f'{filename}: Apenas PDFs são permitidos')
                logger.warning(f"[WARN] Arquivo rejeitado (não é PDF): {filename}")
                continue
            
            try:
                safe_name = sanitize_filename(filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                
                counter = 1
                base_name, extension = os.path.splitext(safe_name)
                while os.path.exists(filepath):
                    safe_name = f"{base_name}_{counter}{extension}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                    counter += 1
                
                file.save(filepath)
                logger.info(f" Arquivo salvo: {filepath}")
                
                valid_size, size_error = validate_file_size(file, max_size_mb=16)
                if not valid_size:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: {size_error}')
                    continue
                
                valid_pdf, pdf_error = validate_pdf_content(filepath)
                if not valid_pdf:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: {pdf_error}')
                    logger.warning(f"[WARN] PDF inválido: {filename}")
                    continue
                
                resume_text = extract_text_from_pdf(filepath)
                
                if not resume_text or len(resume_text.strip()) < 50:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: Não foi possível extrair texto do PDF')
                    logger.warning(f"[WARN] Texto insuficiente: {filename}")
                    continue
                
                logger.info(f" Texto extraído: {len(resume_text)} caracteres")
                
                candidate_info = extract_candidate_info(resume_text, filename)
                candidate_name = candidate_info['name']
                candidate_email = candidate_info['email']
                candidate_phone = candidate_info['phone']
                
                logger.info(f" Candidato: {candidate_name} | 📧 {candidate_email} | 📱 {candidate_phone}")
                
                candidate_data = {
                    'name': candidate_name,
                    'resume_text': resume_text
                }
                
                job_requirements = {
                    'title': job.title,
                    'level': 'Não especificado',
                    'description': job.description or '',
                    'requirements': job.requirements or ''
                }
                
                try:
                    logger.info(f"[BOT] Iniciando análise IA para {candidate_name}...")
                    ai_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)
                    ai_score = ai_analysis.get('overall_score', 50)
                    logger.info(f"[OK] Análise concluída. Score: {ai_score}")
                    
                except Exception as e:
                    logger.warning(f"[WARN] Erro na análise IA de {filename}: {e}")
                    ai_analysis = {
                        'overall_score': 50,
                        'recommendation': 'Análise manual necessária',
                        'strengths': ['Upload em massa - análise pendente'],
                        'weaknesses': ['Requer revisão manual'],
                        'summary': f'Candidato importado via upload em massa. Análise automática falhou.',
                        'technical_skills': [],
                        'experience_level': 'Não especificado'
                    }
                    ai_score = 50
                
                if Candidate.query.filter_by(email=candidate_email, job_id=job_id).first():
                    counter = 1
                    email_base = candidate_email.split('@')[0]
                    email_domain = candidate_email.split('@')[1]
                    while Candidate.query.filter_by(email=candidate_email, job_id=job_id).first():
                        candidate_email = f'{email_base}.{counter}@{email_domain}'
                        counter += 1
                
                candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email,
                    phone=candidate_phone,
                    resume_path=filepath,
                    resume_text=resume_text,
                    job_id=job_id,
                    ai_score=ai_score,
                    ai_analysis=json.dumps(ai_analysis),
                    status='pending'
                )
                
                db.session.add(candidate)
                success_count += 1
                logger.info(f"[OK] Candidato {candidate_name} adicionado ao banco")
                
            except Exception as e:
                logger.error(f"[ERROR] Erro ao processar {filename}: {e}")
                error_count += 1
                errors.append(f'{filename}: {str(e)}')
                if 'filepath' in locals() and filepath and os.path.exists(filepath):
                    safe_delete_file(filepath)
        
        try:
            db.session.commit()
            logger.info(f" Dados salvos no banco: {success_count} candidatos")
            
            if success_count > 0:
                flash(f'[OK] {success_count} candidato(s) adicionado(s) com sucesso!', 'success')
            
            if error_count > 0:
                flash(f'[WARN] {error_count} arquivo(s) com erro:', 'warning')
                for error in errors[:10]:
                    flash(f'• {error}', 'warning')
            
            if success_count == 0:
                flash('[ERROR] Nenhum candidato foi importado. Verifique os arquivos.', 'danger')
            
            return redirect(url_for('job_detail', job_id=job_id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao salvar no banco: {e}")
            flash('[ERROR] Erro ao salvar candidatos no banco de dados.', 'danger')
    
    return render_template('bulk_upload_pdf.html', job=job)

@app.route('/jobs/<int:job_id>/import', methods=['GET', 'POST'])
@login_required
def import_candidates(job_id):
    """Importar candidatos de CSV ou Excel"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        file = None
        
        for field_name in ['file', 'resumes', 'candidates_file', 'import_file']:
            if field_name in request.files:
                file = request.files[field_name]
                break
        
        if not file:
            flash('[ERROR] Nenhum arquivo enviado!', 'danger')
            logger.warning(f"Campos disponíveis: {list(request.files.keys())}")
            return redirect(url_for('import_candidates', job_id=job_id))
        
        if file.filename == '':
            flash('[ERROR] Nenhum arquivo selecionado!', 'danger')
            return redirect(url_for('import_candidates', job_id=job_id))
        
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in ['.csv', '.xlsx', '.xls']:
            flash('[ERROR] Formato inválido! Use CSV ou Excel (.csv, .xlsx, .xls)', 'danger')
            return redirect(url_for('import_candidates', job_id=job_id))
        
        try:
            logger.info(f" Processando arquivo: {file.filename} ({ext})")
            
            if ext == '.csv':
                df = pd.read_csv(file, encoding='utf-8-sig')
            else:
                df = pd.read_excel(file, engine='openpyxl')
            
            logger.info(f"[DATA] Arquivo lido: {len(df)} linhas, Colunas: {list(df.columns)}")
            
            df.columns = df.columns.str.strip().str.lower()
            
            required_columns = ['nome', 'email']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                flash(f'[ERROR] Colunas obrigatórias faltando: {", ".join(missing_columns)}', 'danger')
                flash(f'ℹ️ Colunas encontradas: {", ".join(df.columns)}', 'info')
                return redirect(url_for('import_candidates', job_id=job_id))
            
            success_count = 0
            error_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    name = str(row.get('nome', '')).strip()
                    email = str(row.get('email', '')).strip()
                    phone = str(row.get('telefone', row.get('phone', ''))).strip()
                    
                    if name == 'nan' or name == '' or email == 'nan' or email == '':
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Nome ou email vazio')
                        continue
                    
                    if not validate_email(email):
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Email inválido ({email})')
                        continue
                    
                    if phone == 'nan':
                        phone = ''
                    
                    existing = Candidate.query.filter_by(email=email, job_id=job_id).first()
                    if existing:
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Email {email} já cadastrado nesta vaga')
                        continue
                    
                    candidate = Candidate(
                        name=name,
                        email=email,
                        phone=phone,
                        resume_path=None,
                        resume_text='Importado via CSV/Excel - Aguardando upload de currículo',
                        job_id=job_id,
                        ai_score=50,
                        ai_analysis=json.dumps({
                            'overall_score': 50,
                            'recommendation': 'Análise pendente',
                            'summary': 'Candidato importado - aguardando upload de currículo',
                            'strengths': ['Cadastro via importação'],
                            'weaknesses': ['Currículo não anexado'],
                            'technical_skills': [],
                            'experience_level': 'Não especificado'
                        }),
                        status='pending'
                    )
                    
                    db.session.add(candidate)
                    success_count += 1
                    logger.info(f"[OK] Linha {index + 2}: {name} adicionado")
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f'Linha {index + 2}: {str(e)}'
                    errors.append(error_msg)
                    logger.error(f"[ERROR] {error_msg}")
            
            db.session.commit()
            
            if success_count > 0:
                flash(f'[OK] {success_count} candidato(s) importado(s) com sucesso!', 'success')
            
            if error_count > 0:
                flash(f'[WARN] {error_count} linha(s) com erro foram ignoradas.', 'warning')
                for error in errors[:10]:
                    flash(f'• {error}', 'warning')
            
            if success_count == 0 and error_count > 0:
                flash('[ERROR] Nenhum candidato foi importado. Verifique o arquivo.', 'danger')
            
            return redirect(url_for('job_detail', job_id=job_id))
            
        except pd.errors.EmptyDataError:
            flash('[ERROR] Arquivo vazio ou mal formatado!', 'danger')
            logger.error("Erro: Arquivo vazio")
        except Exception as e:
            db.session.rollback()
            logger.error(f"[ERROR] Erro ao importar: {e}")
            flash(f'[ERROR] Erro ao importar arquivo: {str(e)}', 'danger')
    
    return render_template('import_candidates.html', job=job)

# ==================== MÉTRICAS E RELATÓRIOS ====================
@app.route('/metrics')
@login_required
def metrics():
    """Página de métricas"""
    total_candidates = Candidate.query.count()
    
    candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
    avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score) if candidates_with_score else 0
    
    total_interviews = Interview.query.count()
    
    top_skills = [
        ('Python', 15),
        ('JavaScript', 12),
        ('React', 10),
        ('SQL', 8),
        ('Docker', 6),
    ]
    
    seniority_counts = {
        'Júnior': 8,
        'Pleno': 12,
        'Sênior': 6,
        'Especialista': 3,
    }
    
    jobs = Job.query.all()
    
    return render_template('metrics.html',
                         total_candidates=total_candidates,
                         total_interviews=total_interviews,
                         avg_score=avg_score,
                         top_skills=top_skills,
                         seniority_counts=seniority_counts,
                         jobs=jobs)

@app.route('/reports')
@login_required
def reports():
    """Relatórios"""
    return render_template('reports.html') if os.path.exists('templates/reports.html') else (
        flash('🚧 Relatórios em desenvolvimento', 'info'),
        redirect(url_for('dashboard'))
    )[1]

# ==================== ADMINISTRAÇÃO ====================
@app.route('/admin')
@login_required
def admin_panel():
    """Painel Administrativo"""
    if not current_user.is_admin:
        flash('[ERROR] Acesso negado! Apenas administradores.', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    total_jobs = Job.query.count()
    total_candidates = Candidate.query.count()
    
    return render_template('admin.html', 
                         users=users,
                         total_jobs=total_jobs,
                         total_candidates=total_candidates) if os.path.exists('templates/admin.html') else (
        flash('🚧 Painel admin em desenvolvimento', 'info'),
        redirect(url_for('dashboard'))
    )[1]

@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
def toggle_admin(user_id):
    """Alternar status de administrador"""
    if not current_user.is_admin:
        # CONTINUAÇÃO FINAL DO ARQUIVO app.py
# Cole isso após "if not current_user.is_admin:" da parte 2

        flash('[ERROR] Acesso negado!', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('[ERROR] Você não pode alterar seu próprio status de admin!', 'danger')
        return redirect(url_for('admin_panel'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "administrador" if user.is_admin else "usuário comum"
    flash(f'[OK] {user.username} agora é {status}!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Deletar usuário"""
    if not current_user.is_admin:
        flash('[ERROR] Acesso negado!', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('[ERROR] Você não pode deletar sua própria conta!', 'danger')
        return redirect(url_for('admin_panel'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'[OK] Usuário {username} deletado com sucesso!', 'success')
    return redirect(url_for('admin_panel'))

# ==================== ROTAS AUXILIARES ====================
@app.route('/settings')
@login_required
def settings():
    """Configurações"""
    return render_template('settings.html') if os.path.exists('templates/settings.html') else (
        flash('🚧 Configurações em desenvolvimento', 'info'),
        redirect(url_for('dashboard'))
    )[1]

@app.route('/profile')
@login_required
def profile():
    """Perfil do Usuário"""
    user_info = {
        'username': current_user.username,
        'email': current_user.email,
        'is_admin': current_user.is_admin,
        'created_at': current_user.created_at
    }
    return render_template('profile.html', user=user_info) if os.path.exists('templates/profile.html') else (
        flash('🚧 Perfil em desenvolvimento', 'info'),
        redirect(url_for('dashboard'))
    )[1]

@app.route('/notifications')
@login_required
def notifications():
    """Notificações"""
    flash('🚧 Notificações em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/help')
@login_required
def help_page():
    """Ajuda"""
    flash('🚧 Página de ajuda em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/search')
@login_required
def search():
    """Busca Global"""
    query = request.args.get('q', '')
    flash(f'🚧 Busca em desenvolvimento. Você pesquisou: "{query}"', 'info')
    return redirect(url_for('dashboard'))

@app.route('/candidate-space')
@login_required
def candidate_space():
    """Espaço do Candidato"""
    flash('🚧 Funcionalidade em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

# ==================== API ENDPOINTS ====================
@app.route('/api/candidates/<int:candidate_id>')
@login_required
def api_candidate(candidate_id):
    """API: Obter dados do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    analysis = {}
    if candidate.ai_analysis:
        try:
            analysis = json.loads(candidate.ai_analysis)
        except:
            pass
    
    return jsonify({
        'id': candidate.id,
        'name': candidate.name,
        'email': candidate.email,
        'phone': candidate.phone,
        'score': candidate.ai_score,
        'status': candidate.status,
        'analysis': analysis,
        'job_id': candidate.job_id,
        'created_at': candidate.created_at.isoformat()
    })

@app.route('/api/jobs')
@login_required
def api_jobs():
    """API: Listar vagas"""
    jobs = Job.query.all()
    return jsonify([{
        'id': job.id,
        'title': job.title,
        'description': job.description,
        'status': job.status,
        'candidates_count': len(job.candidates),
        'created_at': job.created_at.isoformat()
    } for job in jobs])

@app.route('/api/stats')
@login_required
def api_stats():
    """API: Estatísticas gerais"""
    return jsonify({
        'total_jobs': Job.query.count(),
        'total_candidates': Candidate.query.count(),
        'pending_candidates': Candidate.query.filter_by(status='pending').count(),
        'approved_candidates': Candidate.query.filter_by(status='approved').count(),
        'total_users': User.query.count(),
        'total_interviews': Interview.query.count()
    })

# ==================== ERROR HANDLERS ====================
@app.errorhandler(404)
def not_found_error(error):
    """Página não encontrada"""
    if 'favicon.ico' in request.path:
        return '', 404
    
    if os.path.exists('templates/404.html'):
        return render_template('404.html'), 404
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>404 - Página não encontrada</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                text-align: center;
                background: white;
                padding: 60px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{ color: #2C3E50; margin: 0 0 20px 0; font-size: 72px; }}
            p {{ color: #6C757D; margin: 0 0 30px 0; font-size: 18px; }}
            a {{
                display: inline-block;
                padding: 15px 30px;
                background: #0275D8;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
            }}
            a:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>404</h1>
            <p>Página não encontrada</p>
            <a href="{url_for('dashboard')}">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    ''', 404

@app.errorhandler(500)
def internal_error(error):
    """Erro interno do servidor"""
    db.session.rollback()
    logger.error(f"Erro 500: {error}")
    
    if 'favicon.ico' in request.path:
        return '', 500
    
    if os.path.exists('templates/500.html'):
        return render_template('500.html'), 500
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>500 - Erro interno</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                text-align: center;
                background: white;
                padding: 60px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{ color: #2C3E50; margin: 0 0 20px 0; font-size: 72px; }}
            p {{ color: #6C757D; margin: 0 0 30px 0; font-size: 18px; }}
            a {{
                display: inline-block;
                padding: 15px 30px;
                background: #0275D8;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
            }}
            a:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>500</h1>
            <p>Erro interno do servidor</p>
            <a href="{url_for('dashboard')}">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    ''', 500

@app.errorhandler(403)
def forbidden_error(error):
    """Acesso negado"""
    if 'favicon.ico' in request.path:
        return '', 403
    
    if os.path.exists('templates/403.html'):
        return render_template('403.html'), 403
    
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>403 - Acesso negado</title>
        <style>
            body {{
                font-family: 'Segoe UI', sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            }}
            .container {{
                text-align: center;
                background: white;
                padding: 60px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{ color: #2C3E50; margin: 0 0 20px 0; font-size: 72px; }}
            p {{ color: #6C757D; margin: 0 0 30px 0; font-size: 18px; }}
            a {{
                display: inline-block;
                padding: 15px 30px;
                background: #0275D8;
                color: white;
                text-decoration: none;
                border-radius: 8px;
                font-weight: 600;
            }}
            a:hover {{ background: #0056b3; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>403</h1>
            <p>Acesso negado</p>
            <a href="{url_for('dashboard')}">← Voltar ao Dashboard</a>
        </div>
    </body>
    </html>
    ''', 403

# ==================== INICIALIZAÇÃO ====================
with app.app_context():
    try:
        db.create_all()
        logger.info("[OK] Tabelas criadas com sucesso!")
        
        try:
            with db.engine.connect() as conn:
                try:
                    conn.execute(text("ALTER TABLE candidate ADD COLUMN resume_text TEXT"))
                    conn.commit()
                    logger.info("[OK] Coluna resume_text adicionada!")
                except Exception:
                    logger.info("[OK] Coluna resume_text já existe!")
        except Exception as e:
            logger.warning(f"[WARN] Aviso ao verificar coluna resume_text: {e}")
        
        logger.info(f"[DATA] Total de usuários: {User.query.count()}")
        logger.info(f"[DATA] Total de vagas: {Job.query.count()}")
        logger.info(f"[DATA] Total de candidatos: {Candidate.query.count()}")
        logger.info(f"[DATA] Total de entrevistas: {Interview.query.count()}")
        logger.info("[OK] Banco de dados inicializado!")
    except Exception as e:
        logger.error(f"[WARN] Erro ao inicializar banco: {e}")

# ==================== EXECUTAR ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)