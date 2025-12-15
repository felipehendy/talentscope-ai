import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_migrate import Migrate
import pandas as pd 
from ai_analyzer import AIAnalyzer
import json
from urllib.parse import quote
from sqlalchemy import text
import logging
import re

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
logger.info(f"🔧 Provider configurado: {ai_analyzer.get_current_provider()}")

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

@login_manager.user_loader
def load_user(user_id):
    # Forma moderna de buscar por chave primária
    return db.session.get(User, int(user_id))


# ==================== FUNÇÕES AUXILIARES ====================
def safe_delete_file(filepath):
    """Remove arquivo com segurança"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"✅ Arquivo deletado: {filepath}")
            return True
    except Exception as e:
        logger.error(f"❌ Erro ao deletar arquivo {filepath}: {e}")
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
    """
    Extrai nome, email e telefone do currículo
    """
    import re
    
    # Extrair nome (primeiras linhas do PDF ou nome do arquivo)
    name = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()
    
    # Tentar encontrar um nome nas primeiras linhas
    first_lines = resume_text.split('\n')[:10]
    for line in first_lines:
        line = line.strip()
        # Se linha tem entre 5 e 50 caracteres, sem números, provavelmente é um nome
        if 5 < len(line) < 50 and not any(char.isdigit() for char in line) and ' ' in line:
            # Verificar se não é uma frase/parágrafo (máximo 4 palavras)
            if len(line.split()) <= 4:
                name = line.title()
                break
    
    # Extrair email (regex)
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, resume_text)
    
    if emails:
        email = emails[0].lower()
    else:
        # Gerar email temporário baseado no nome
        email_base = name.lower().replace(' ', '.').replace('..', '.')
        email = f'{email_base}@temporario.pendente'
    
    # Extrair telefone (vários formatos brasileiros)
    phone_patterns = [
        r'\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}',  # (11) 99999-9999 ou 11999999999
        r'\+55\s*\(?\d{2}\)?\s*9?\d{4}[-\s]?\d{4}',  # +55 (11) 99999-9999
        r'\d{2}\s*9\d{8}',  # 11999999999
    ]
    
    phone = ''
    for pattern in phone_patterns:
        phones = re.findall(pattern, resume_text)
        if phones:
            # Limpar formatação
            phone = re.sub(r'[^\d]', '', phones[0])
            # Garantir que tem código do país
            if len(phone) == 11 and phone[2] == '9':  # DDD + 9 dígitos
                phone = '55' + phone
            elif len(phone) == 10:  # DDD + 8 dígitos (telefone fixo)
                phone = '55' + phone
            break
    
    return {
        'name': name,
        'email': email,
        'phone': phone
    }


# ==================== ROTAS DE AUTENTICAÇÃO ====================
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
    """Login com validações - CORRIGIDO"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if User.query.count() == 0:
        flash('Nenhum usuário cadastrado. Crie sua conta primeiro.', 'warning')
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validações básicas
        if not username or not password:
            flash('❌ Preencha todos os campos!', 'danger')
            return render_template('login.html')
        
        # CORRIGIDO: Buscar por username OU email (seu template permite ambos)
        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash(f'✅ Bem-vindo, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('❌ Usuário ou senha incorretos!', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de usuários - público"""

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
         # ==================== VALIDAÇÕES ====================
        
        # 1️⃣ Campos vazios
        if not username or not email or not password or not confirm_password:
            flash('❌ Todos os campos são obrigatórios!', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # 2️⃣ Validar username
        valid, error = validate_username(username)
        if not valid:
            flash(f'❌ {error}', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # 3️⃣ Validar email
        if not validate_email(email):
            flash('❌ Email inválido! Use o formato: exemplo@email.com', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # 4️⃣ Validar senha
        valid, error = validate_password(password)
        if not valid:
            flash(f'❌ {error}', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # 5️⃣ NOVO: Verificar se as senhas coincidem
        if password != confirm_password:
            flash('❌ As senhas não coincidem!', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # 6️⃣ Verificar duplicatas
        if User.query.filter_by(username=username).first():
            flash('❌ Nome de usuário já existe!', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        if User.query.filter_by(email=email).first():
            flash('❌ Email já cadastrado!', 'danger')
            return render_template('register.html', is_first_user=(user_count == 0))
        
        # ==================== CRIAR USUÁRIO ====================
        is_first_user = (user_count == 0)
        
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
                flash('✅ Conta de administrador criada com sucesso! Faça login.', 'success')
            else:
                flash('✅ Conta criada com sucesso! Faça login.', 'success')
            
            logger.info(f"✅ Usuário criado: {username} (Admin: {is_first_user})")
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao criar usuário: {e}")
            flash('❌ Erro ao criar conta. Tente novamente.', 'danger')
    
    is_first_user = (user_count == 0)
    return render_template('register.html', is_first_user=is_first_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('login'))

# ==================== DASHBOARD ====================
@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard com métricas"""
    from datetime import datetime  # Adicionar no topo do arquivo se ainda não existir
    
    total_jobs = Job.query.count()
    total_candidates = Candidate.query.count()
    pending_candidates = Candidate.query.filter_by(status='pending').count()
    
    candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
    avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score) if candidates_with_score else 0.0
    
    jobs = Job.query.all()
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
    recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
    
    # Dados mockados
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
                         total_interviews=0,
                         jobs=jobs,
                         top_skills=top_skills,
                         seniority_counts=seniority_counts,
                         recent_jobs=recent_jobs,
                         recent_candidates=recent_candidates,
                         now=datetime.utcnow())  # ADICIONAR ESTA LINHA

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
        
        # Validações básicas
        if not title:
            flash('❌ Título da vaga é obrigatório!', 'danger')
            return render_template('new_job.html')
        
        if len(title) < 3:
            flash('❌ Título deve ter no mínimo 3 caracteres!', 'danger')
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
            flash(f'✅ Vaga "{title}" criada com sucesso!', 'success')
            return redirect(url_for('jobs'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Erro ao criar vaga: {e}")
            flash('❌ Erro ao criar vaga. Tente novamente.', 'danger')
    
    return render_template('new_job.html')

# em app.py

# ... (outras rotas de candidatos) ...

@app.route('/candidate/<int:candidate_id>/schedule-interview', methods=['GET', 'POST'])
@login_required
def schedule_interview_from_candidate(candidate_id):
    """Página para agendar entrevista para um candidato - Em desenvolvimento"""
    candidate = Candidate.query.get_or_404(candidate_id)
    # No futuro, aqui você integraria com um calendário ou sistema de agendamento.
    # Por enquanto, apenas exibimos uma mensagem e redirecionamos.
    flash(f'🚧 Agendamento de entrevista para {candidate.name} em desenvolvimento.', 'info')
    return redirect(url_for('candidate_detail', candidate_id=candidate_id))


@app.route('/jobs/<int:job_id>/reanalyze-all', methods=['POST'])
@login_required
def reanalyze_all_candidates_for_job(job_id):
    """Reanalisa todos os candidatos de uma vaga específica."""
    job = Job.query.get_or_404(job_id)
    candidates = job.candidates  # Pega todos os candidatos associados à vaga

    if not candidates:
        flash('Não há candidatos para reanalisar nesta vaga.', 'info')
        return redirect(url_for('job_detail', job_id=job_id))

    success_count = 0
    error_count = 0

    # Reutiliza a lógica de análise que você já tem
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
            
            logger.info(f"🤖 Reanalisando {candidate.name} para a vaga '{job.title}'...")
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
            logger.error(f"❌ Erro ao reanalisar candidato {candidate.id}: {e}")

    try:
        db.session.commit()
        flash(f'✅ Reanálise concluída! {success_count} candidatos atualizados.', 'success')
        if error_count > 0:
            flash(f'⚠️ {error_count} candidatos não puderam ser reanalisados.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao salvar reanálises no banco: {e}")
        flash('❌ Ocorreu um erro ao salvar as atualizações no banco de dados.', 'danger')

    return redirect(url_for('job_detail', job_id=job_id))

# ... (resto do seu código) ...


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
        # Deletar arquivos dos candidatos
        candidates = Candidate.query.filter_by(job_id=job_id).all()
        for candidate in candidates:
            if candidate.resume_path:
                safe_delete_file(candidate.resume_path)
        
        # Deletar candidatos (cascade já faz isso, mas garantimos)
        Candidate.query.filter_by(job_id=job_id).delete()
        
        # Deletar vaga
        db.session.delete(job)
        db.session.commit()
        
        flash(f'✅ Vaga "{job.title}" excluída com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir vaga: {e}")
        flash('❌ Erro ao excluir vaga. Tente novamente.', 'danger')
    
    return redirect(url_for('jobs'))

# ==================== ROTAS DE CANDIDATOS ====================
@app.route('/candidates/new/<int:job_id>', methods=['GET', 'POST'])
@login_required
def new_candidate(job_id):
    """Adicionar novo candidato - VERSÃO SEGURA"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'GET':
        return render_template('new_candidate.html', job=job)
    
    # ==================== POST - VALIDAÇÕES COMPLETAS ====================
    try:
        # 1️⃣ COLETAR DADOS
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # 2️⃣ VALIDAR CAMPOS OBRIGATÓRIOS
        if not name:
            flash('❌ Nome é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not email:
            flash('❌ Email é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not phone:
            flash('❌ Telefone é obrigatório!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        # 3️⃣ VALIDAR FORMATO
        if not validate_email(email):
            flash('❌ Email inválido! Use o formato: exemplo@email.com', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not validate_phone(phone):
            flash('❌ Telefone inválido! Use formato: DDD + Número (ex: 11999999999)', 'danger')
            return render_template('new_candidate.html', job=job)
        
        # 4️⃣ VALIDAR ARQUIVO
        file = request.files.get('resume')
        
        if not file or not file.filename:
            flash('❌ É necessário enviar um currículo em PDF!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        if not allowed_file(file.filename):
            flash('❌ Apenas arquivos PDF são permitidos!', 'danger')
            return render_template('new_candidate.html', job=job)
        
        # Validar tamanho
        valid_size, size_error = validate_file_size(file, max_size_mb=16)
        if not valid_size:
            flash(f'❌ {size_error}', 'danger')
            return render_template('new_candidate.html', job=job)
        
        # 5️⃣ SALVAR ARQUIVO
        filename = sanitize_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        logger.info(f"📁 Arquivo salvo: {filepath}")
        
        # Validar conteúdo
        valid_pdf, pdf_error = validate_pdf_content(filepath)
        if not valid_pdf:
            safe_delete_file(filepath)
            flash(f'❌ PDF inválido: {pdf_error}', 'danger')
            return render_template('new_candidate.html', job=job)
        
        # 6️⃣ EXTRAIR TEXTO
        resume_text = extract_text_from_pdf(filepath)
        
        if not resume_text or len(resume_text.strip()) < 50:
            safe_delete_file(filepath)
            flash('❌ Não foi possível extrair texto do PDF. Verifique o arquivo.', 'danger')
            return render_template('new_candidate.html', job=job)
        
        logger.info(f"📄 Texto extraído: {len(resume_text)} caracteres")
        
        # 7️⃣ ANALISAR COM IA
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
            
            logger.info(f"🤖 Iniciando análise IA...")
            ai_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)
            ai_score = ai_analysis.get('overall_score', 50)
            logger.info(f"✅ Análise concluída. Score: {ai_score}")
            
        except Exception as e:
            logger.error(f"⚠️ Erro na análise IA: {e}")
            ai_analysis = {
                'overall_score': 50,
                'recommendation': 'Análise manual necessária',
                'strengths': ['Análise automática indisponível'],
                'weaknesses': ['Requer revisão manual'],
                'summary': f'Erro: {str(e)}'
            }
            ai_score = 50
        
        # 8️⃣ SALVAR NO BANCO
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
        
        logger.info(f"✅ Candidato {name} cadastrado (ID: {candidate.id})")
        flash(f'✅ Candidato {name} adicionado! Score IA: {ai_score}', 'success')
        return redirect(url_for('candidate_detail', candidate_id=candidate.id))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"❌ Erro ao adicionar candidato: {e}")
        
        if 'filepath' in locals() and filepath:
            safe_delete_file(filepath)
        
        flash('❌ Erro ao adicionar candidato. Tente novamente.', 'danger')
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
        flash('✅ Status atualizado!', 'success')
    else:
        flash('❌ Status inválido!', 'danger')
    
    return redirect(url_for('candidate_detail', candidate_id=candidate_id))

@app.route('/candidate/<int:candidate_id>/reanalyze', methods=['POST'])
@login_required
def reanalyze_candidate(candidate_id):
    """Reanalisar candidato com IA"""
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get_or_404(candidate.job_id)
    
    resume_text = candidate.resume_text 
    
    if not resume_text:
        flash('❌ Texto do currículo não encontrado!', 'danger')
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
            flash('✅ Análise atualizada com sucesso!', 'success')
        else:
            flash('❌ Erro na reanálise. Verifique os logs.', 'danger')
    
    except Exception as e:
        logger.error(f"Erro ao reanalisar: {e}")
        flash('❌ Erro ao reanalisar candidato.', 'danger')

    return redirect(url_for('candidate_detail', candidate_id=candidate.id))

@app.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@login_required
def delete_candidate(candidate_id):
    """Excluir candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    job_id = candidate.job_id
    
    try:
        # Deletar arquivo
        if candidate.resume_path:
            safe_delete_file(candidate.resume_path)
        
        # Deletar candidato
        db.session.delete(candidate)
        db.session.commit()
        
        flash(f'✅ Candidato "{candidate.name}" excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao excluir candidato: {e}")
        flash('❌ Erro ao excluir candidato.', 'danger')
    
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/metrics')
@login_required
def metrics():
    """Página de métricas"""
    total_candidates = Candidate.query.count()
    
    candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
    avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score) if candidates_with_score else 0
    
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
                         total_interviews=0,
                         avg_score=avg_score,
                         top_skills=top_skills,
                         seniority_counts=seniority_counts,
                         jobs=jobs)

# ==================== SUBSTITUIR A SEÇÃO DE INICIALIZAÇÃO NO APP.PY ====================
# Encontre no final do app.py (linha ~565) e SUBSTITUA por:

# ==================== INICIALIZAÇÃO ====================
with app.app_context():
    try:
        db.create_all()
        logger.info("✅ Tabelas criadas com sucesso!")
        
        # Adicionar coluna resume_text se não existir
        # SQLite não suporta IF NOT EXISTS, então tentamos e ignoramos se já existir
        try:
            with db.engine.connect() as conn:
                try:
                    # Tentar adicionar coluna
                    conn.execute(text("ALTER TABLE candidate ADD COLUMN resume_text TEXT"))
                    conn.commit()
                    logger.info("✅ Coluna resume_text adicionada!")
                except Exception:
                    # Coluna já existe, tudo OK
                    logger.info("✅ Coluna resume_text já existe!")
        except Exception as e:
            logger.warning(f"⚠️ Aviso ao verificar coluna resume_text: {e}")
        
        logger.info(f"📊 Total de usuários: {User.query.count()}")
        logger.info("✅ Banco de dados inicializado!")
    except Exception as e:
        logger.error(f"⚠️ Erro ao inicializar banco: {e}")

        # ==================== ROTA TEMPORÁRIA ====================
@app.route('/candidate-space')
@login_required
def candidate_space():
    """Espaço do Candidato - Em desenvolvimento"""
    flash('🚧 Funcionalidade em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

# ==================== ADICIONE ESTAS ROTAS NO FINAL DO SEU APP.PY ====================
# Logo antes de "if __name__ == '__main__':"

# ==================== ROTAS TEMPORÁRIAS (Em Desenvolvimento) ====================

@app.route('/calendar')
@login_required
def calendar():
    """Calendário de Entrevistas - Em desenvolvimento"""
    flash('🚧 Calendário em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/interviews')
@login_required
def interviews():
    """Gerenciar Entrevistas - Em desenvolvimento"""
    flash('🚧 Gestão de entrevistas em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/reports')
@login_required
def reports():
    """Relatórios - Em desenvolvimento"""
    flash('🚧 Relatórios em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/settings')
@login_required
def settings():
    """Configurações - Em desenvolvimento"""
    flash('🚧 Configurações em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/profile')
@login_required
def profile():
    """Perfil do Usuário - Em desenvolvimento"""
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
    """Notificações - Em desenvolvimento"""
    flash('🚧 Notificações em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/help')
@login_required
def help_page():
    """Ajuda - Em desenvolvimento"""
    flash('🚧 Página de ajuda em desenvolvimento', 'info')
    return redirect(url_for('dashboard'))

@app.route('/search')
@login_required
def search():
    """Busca Global - Em desenvolvimento"""
    query = request.args.get('q', '')
    flash(f'🚧 Busca em desenvolvimento. Você pesquisou: "{query}"', 'info')
    return redirect(url_for('dashboard'))

# ==================== ROTAS DE ADMINISTRAÇÃO ====================

@app.route('/admin')
@login_required
def admin_panel():
    """Painel Administrativo"""
    if not current_user.is_admin:
        flash('❌ Acesso negado! Apenas administradores.', 'danger')
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
        flash('❌ Acesso negado!', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('❌ Você não pode alterar seu próprio status de admin!', 'danger')
        return redirect(url_for('admin_panel'))
    
    user.is_admin = not user.is_admin
    db.session.commit()
    
    status = "administrador" if user.is_admin else "usuário comum"
    flash(f'✅ {user.username} agora é {status}!', 'success')
    return redirect(url_for('admin_panel'))

@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    """Deletar usuário"""
    if not current_user.is_admin:
        flash('❌ Acesso negado!', 'danger')
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    
    if user.id == current_user.id:
        flash('❌ Você não pode deletar sua própria conta!', 'danger')
        return redirect(url_for('admin_panel'))
    
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'✅ Usuário {username} deletado com sucesso!', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/jobs/<int:job_id>/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_candidates(job_id):
    """Upload em massa de candidatos via PDF - VERSÃO D1000"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        # 🔧 CORREÇÃO: Seu template usa 'pdf_files', não 'resumes'
        if 'pdf_files' not in request.files:
            logger.error(f"❌ Campo 'pdf_files' não encontrado. Campos disponíveis: {list(request.files.keys())}")
            flash('❌ Nenhum arquivo enviado!', 'danger')
            return redirect(url_for('bulk_upload_candidates', job_id=job_id))
        
        files = request.files.getlist('pdf_files')
        
        # Verificar se há arquivos selecionados
        if not files or len(files) == 0 or files[0].filename == '':
            flash('❌ Nenhum arquivo selecionado!', 'danger')
            return redirect(url_for('bulk_upload_candidates', job_id=job_id))
        
        logger.info(f"📂 Recebidos {len(files)} arquivo(s) para upload")
        
        success_count = 0
        error_count = 0
        errors = []
        
        for file in files:
            filename = file.filename
            
            # Ignorar arquivos vazios
            if not filename:
                continue
            
            logger.info(f"📄 Processando: {filename}")
            
            # Verificar extensão
            if not allowed_file(filename):
                error_count += 1
                errors.append(f'{filename}: Apenas PDFs são permitidos')
                logger.warning(f"⚠️ Arquivo rejeitado (não é PDF): {filename}")
                continue
            
            try:
                # Sanitizar nome do arquivo
                safe_name = sanitize_filename(filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                
                # Evitar sobrescrever arquivos
                counter = 1
                base_name, extension = os.path.splitext(safe_name)
                while os.path.exists(filepath):
                    safe_name = f"{base_name}_{counter}{extension}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
                    counter += 1
                
                # Salvar arquivo
                file.save(filepath)
                logger.info(f"💾 Arquivo salvo: {filepath}")
                
                # Validar tamanho
                valid_size, size_error = validate_file_size(file, max_size_mb=16)
                if not valid_size:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: {size_error}')
                    continue
                
                # Validar PDF
                valid_pdf, pdf_error = validate_pdf_content(filepath)
                if not valid_pdf:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: {pdf_error}')
                    logger.warning(f"⚠️ PDF inválido: {filename}")
                    continue
                
                # Extrair texto
                resume_text = extract_text_from_pdf(filepath)
                
                if not resume_text or len(resume_text.strip()) < 50:
                    safe_delete_file(filepath)
                    error_count += 1
                    errors.append(f'{filename}: Não foi possível extrair texto do PDF')
                    logger.warning(f"⚠️ Texto insuficiente: {filename}")
                    continue
                
                logger.info(f"📝 Texto extraído: {len(resume_text)} caracteres")
                
                # 🔧 MELHORADO: Extrair informações do PDF
                candidate_info = extract_candidate_info(resume_text, filename)
                candidate_name = candidate_info['name']
                candidate_email = candidate_info['email']
                candidate_phone = candidate_info['phone']
                
                logger.info(f"👤 Candidato: {candidate_name} | 📧 {candidate_email} | 📱 {candidate_phone}")
                
                # Preparar dados para IA
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
                
                # Analisar com IA
                try:
                    logger.info(f"🤖 Iniciando análise IA para {candidate_name}...")
                    ai_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)
                    ai_score = ai_analysis.get('overall_score', 50)
                    logger.info(f"✅ Análise concluída. Score: {ai_score}")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Erro na análise IA de {filename}: {e}")
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
                
                # Verificar se email já existe
                if Candidate.query.filter_by(email=candidate_email, job_id=job_id).first():
                    counter = 1
                    email_base = candidate_email.split('@')[0]
                    email_domain = candidate_email.split('@')[1]
                    while Candidate.query.filter_by(email=candidate_email, job_id=job_id).first():
                        candidate_email = f'{email_base}.{counter}@{email_domain}'
                        counter += 1
                
                # Criar candidato
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
                logger.info(f"✅ Candidato {candidate_name} adicionado ao banco")
                
            except Exception as e:
                logger.error(f"❌ Erro ao processar {filename}: {e}")
                error_count += 1
                errors.append(f'{filename}: {str(e)}')
                if 'filepath' in locals() and filepath and os.path.exists(filepath):
                    safe_delete_file(filepath)
        
        # Salvar no banco
        try:
            db.session.commit()
            logger.info(f"💾 Dados salvos no banco: {success_count} candidatos")
            
            if success_count > 0:
                flash(f'✅ {success_count} candidato(s) adicionado(s) com sucesso!', 'success')
            
            if error_count > 0:
                flash(f'⚠️ {error_count} arquivo(s) com erro:', 'warning')
                for error in errors[:10]:  # Mostrar no máximo 10 erros
                    flash(f'• {error}', 'warning')
            
            if success_count == 0:
                flash('❌ Nenhum candidato foi importado. Verifique os arquivos.', 'danger')
            
            return redirect(url_for('job_detail', job_id=job_id))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao salvar no banco: {e}")
            flash('❌ Erro ao salvar candidatos no banco de dados.', 'danger')
    
    return render_template('bulk_upload_pdf.html', job=job)


# ==================== IMPORTAR CANDIDATOS (CSV/EXCEL) ====================

@app.route('/jobs/<int:job_id>/import', methods=['GET', 'POST'])
@login_required
def import_candidates(job_id):
    """Importar candidatos de CSV ou Excel - VERSÃO CORRIGIDA"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        # 🔧 CORREÇÃO 1: Verificar múltiplos nomes de campo possíveis
        file = None
        
        # Tentar diferentes nomes de campo
        for field_name in ['file', 'resumes', 'candidates_file', 'import_file']:
            if field_name in request.files:
                file = request.files[field_name]
                break
        
        # Se nenhum arquivo encontrado
        if not file:
            flash('❌ Nenhum arquivo enviado!', 'danger')
            logger.warning(f"Campos disponíveis: {list(request.files.keys())}")
            return redirect(url_for('import_candidates', job_id=job_id))
        
        # 🔧 CORREÇÃO 2: Verificar se arquivo está vazio
        if file.filename == '':
            flash('❌ Nenhum arquivo selecionado!', 'danger')
            return redirect(url_for('import_candidates', job_id=job_id))
        
        # Verificar extensão
        ext = os.path.splitext(file.filename)[1].lower()
        
        if ext not in ['.csv', '.xlsx', '.xls']:
            flash('❌ Formato inválido! Use CSV ou Excel (.csv, .xlsx, .xls)', 'danger')
            return redirect(url_for('import_candidates', job_id=job_id))
        
        try:
            logger.info(f"📂 Processando arquivo: {file.filename} ({ext})")
            
            # Ler arquivo
            if ext == '.csv':
                df = pd.read_csv(file, encoding='utf-8-sig')  # utf-8-sig para remover BOM
            else:
                df = pd.read_excel(file, engine='openpyxl')
            
            logger.info(f"📊 Arquivo lido: {len(df)} linhas, Colunas: {list(df.columns)}")
            
            # 🔧 CORREÇÃO 3: Normalizar nomes das colunas (ignorar maiúsculas/minúsculas)
            df.columns = df.columns.str.strip().str.lower()
            
            # Validar colunas obrigatórias
            required_columns = ['nome', 'email']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                flash(f'❌ Colunas obrigatórias faltando: {", ".join(missing_columns)}', 'danger')
                flash(f'ℹ️ Colunas encontradas: {", ".join(df.columns)}', 'info')
                return redirect(url_for('import_candidates', job_id=job_id))
            
            success_count = 0
            error_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # 🔧 CORREÇÃO 4: Tratamento robusto de valores NaN
                    name = str(row.get('nome', '')).strip()
                    email = str(row.get('email', '')).strip()
                    phone = str(row.get('telefone', row.get('phone', ''))).strip()
                    
                    # Ignorar linhas vazias
                    if name == 'nan' or name == '' or email == 'nan' or email == '':
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Nome ou email vazio')
                        continue
                    
                    # Validar email
                    if not validate_email(email):
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Email inválido ({email})')
                        continue
                    
                    # Limpar telefone
                    if phone == 'nan':
                        phone = ''
                    
                    # 🔧 CORREÇÃO 5: Verificar duplicatas
                    existing = Candidate.query.filter_by(email=email, job_id=job_id).first()
                    if existing:
                        error_count += 1
                        errors.append(f'Linha {index + 2}: Email {email} já cadastrado nesta vaga')
                        continue
                    
                    # Criar candidato
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
                    logger.info(f"✅ Linha {index + 2}: {name} adicionado")
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f'Linha {index + 2}: {str(e)}'
                    errors.append(error_msg)
                    logger.error(f"❌ {error_msg}")
            
            # Salvar no banco
            db.session.commit()
            
            # Feedback ao usuário
            if success_count > 0:
                flash(f'✅ {success_count} candidato(s) importado(s) com sucesso!', 'success')
            
            if error_count > 0:
                flash(f'⚠️ {error_count} linha(s) com erro foram ignoradas.', 'warning')
                # Mostrar até 10 erros
                for error in errors[:10]:
                    flash(f'• {error}', 'warning')
            
            if success_count == 0 and error_count > 0:
                flash('❌ Nenhum candidato foi importado. Verifique o arquivo.', 'danger')
            
            return redirect(url_for('job_detail', job_id=job_id))
            
        except pd.errors.EmptyDataError:
            flash('❌ Arquivo vazio ou mal formatado!', 'danger')
            logger.error("Erro: Arquivo vazio")
        except Exception as e:
            db.session.rollback()
            logger.error(f"❌ Erro ao importar: {e}")
            flash(f'❌ Erro ao importar arquivo: {str(e)}', 'danger')
    
    return render_template('import_candidates.html', job=job)


# ==================== SUBSTITUA OS ERROR HANDLERS NO SEU APP.PY ====================
# Localize as funções @app.errorhandler e substitua por estas:

@app.errorhandler(404)
def not_found_error(error):
    """Página não encontrada"""
    # Ignorar erros de favicon
    if 'favicon.ico' in request.path:
        return '', 404
    
    # Se template existe, usar
    if os.path.exists('templates/404.html'):
        return render_template('404.html'), 404
    
    # Fallback simples
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
    
    # Ignorar erros de favicon
    if 'favicon.ico' in request.path:
        return '', 500
    
    # Se template existe, usar
    if os.path.exists('templates/500.html'):
        return render_template('500.html'), 500
    
    # Fallback simples
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
    # Ignorar erros de favicon
    if 'favicon.ico' in request.path:
        return '', 403
    
    # Se template existe, usar
    if os.path.exists('templates/403.html'):
        return render_template('403.html'), 403
    
    # Fallback simples
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
# ==================== API ENDPOINTS (OPCIONAL) ====================

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
        'total_users': User.query.count()
    })



# ==================== EXECUTAR ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)