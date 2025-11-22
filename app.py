import os
import io
import re
import pdfplumber
import PyPDF2
import time
from urllib.parse import quote
from sqlalchemy import inspect, text
from datetime import datetime
from flask import session
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_migrate import Migrate
import pandas as pd 
from ai_analyzer import AIAnalyzer
import json
from sqlalchemy import text, create_engine
from sqlalchemy.exc import SQLAlchemyError
from flask_wtf.csrf import CSRFProtect

# --- Configuração ---
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sua-chave-secreta-super-segura-123')

# ✅ ADICIONE CSRF PROTECTION
csrf = CSRFProtect()
csrf.init_app(app)

# ✅ CONFIGURAÇÃO CORRETA DO BANCO PARA RENDER
def get_database_url():
    """Configuração do PostgreSQL para Render com fallback para SQLite"""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        # ✅ CORREÇÃO SSL PARA RENDER
        if 'postgresql' in database_url and 'sslmode' not in database_url:
            database_url += "?sslmode=require"
        return database_url
    
    # Fallback para SQLite local
    return 'sqlite:///database.db'

app.config['SQLALCHEMY_DATABASE_URI'] = get_database_url()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True
}
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Criar pasta de uploads
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

db = SQLAlchemy(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ✅ CONFIGURAÇÃO CORRETA - Apenas AIAnalyzer
ai_analyzer = AIAnalyzer()
print(f"🔧 Provider configurado: {ai_analyzer.get_current_provider()}")

# ==================== INICIALIZAÇÃO DO BANCO ====================

def init_database():
    """Inicializa o banco de dados no Render"""
    with app.app_context():
        try:
            print("🔄 Inicializando banco de dados...")
            
            # Verifica se as tabelas existem
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            if not existing_tables:
                print("🗃️ Criando todas as tabelas do banco de dados...")
                db.create_all()
                print("✅ Tabelas criadas com sucesso!")
            else:
                print("✅ Tabelas já existem no banco de dados")
                
            # ✅ Executa migração para linkedin_url
            run_auto_migration()
                
        except Exception as e:
            print(f"❌ Erro ao verificar/criar tabelas: {e}")
            # Tenta criar as tabelas mesmo assim
            try:
                db.create_all()
                print("✅ Tabelas criadas com sucesso após erro!")
            except Exception as e2:
                print(f"❌ Erro crítico ao criar tabelas: {e2}")

def run_auto_migration():
    """
    Executa a migração para adicionar a coluna linkedin_url na inicialização.
    """
    try:
        # Para SQLite, verifica de forma diferente
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        
        # Verifica se a tabela candidate existe
        inspector = inspect(engine)
        if 'candidate' not in inspector.get_table_names():
            print("📋 Tabela candidate não existe ainda. Será criada com db.create_all()")
            return
        
        # Verifica se a coluna já existe (método compatível com SQLite)
        columns = [col['name'] for col in inspector.get_columns('candidate')]
        
        if 'linkedin_url' in columns:
            print(f"✅ Migração: Coluna 'linkedin_url' já existe. Nenhuma ação necessária.")
            return

        # Adiciona a coluna se não existir
        print("🔄 Adicionando coluna 'linkedin_url' à tabela candidate...")
        with engine.connect() as connection:
            connection.execute(text("""
                ALTER TABLE candidate 
                ADD COLUMN linkedin_url VARCHAR(500) DEFAULT NULL
            """))
            connection.commit()
            
        print("🎉 Migração: Coluna 'linkedin_url' adicionada com sucesso!")

    except Exception as e:
        print(f"⚠️ Aviso na migração: {e}")
        print("A coluna será criada quando as tabelas forem geradas.")

# ==================== FILTRO WHATSAPP ====================
@app.template_filter('whatsapp_link')
def whatsapp_link(phone):
    """Gera link para abrir WhatsApp"""
    if not phone:
        return '#'
    
    # Remove tudo exceto números
    clean_phone = ''.join(filter(str.isdigit, str(phone)))
    
    # Se não tem DDI (55), adiciona
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
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    requirements = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    candidates = db.relationship('Candidate', backref='job', lazy=True)

class Candidate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    linkedin_url = db.Column(db.String(500))  # ✅ ADICIONADO
    resume_path = db.Column(db.String(500))
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    ai_score = db.Column(db.Float)
    ai_analysis = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resume_text = db.Column(db.Text)

class Interview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='scheduled')
    meeting_link = db.Column(db.String(500))
    notes = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOVO: Campos para controle WhatsApp
    whatsapp_sent = db.Column(db.Boolean, default=False)
    whatsapp_sent_at = db.Column(db.DateTime)
    
    candidate = db.relationship('Candidate', backref='interviews')
    job = db.relationship('Job', backref='interviews')
    user = db.relationship('User', backref='interviews')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== FUNÇÕES DE EXTRAÇÃO ====================

def extract_linkedin_from_text(text):
    """Extrai URL do LinkedIn do texto do currículo"""
    if not text:
        return None
    
    try:
        # Padrões comuns de LinkedIn
        patterns = [
            r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?',
            r'(?:https?://)?(?:br\.)?linkedin\.com/in/[\w-]+/?',
            r'linkedin\.com/in/[\w-]+/?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                url = match.group()
                # Garantir que tem https://
                if not url.startswith('http'):
                    url = 'https://' + url
                # Remover barra final duplicada
                url = url.rstrip('/')
                return url
        
        return None
        
    except Exception as e:
        print(f"⚠️ Erro ao extrair LinkedIn: {e}")
        return None

def extract_text_from_pdf(file_path):
    """Extrai texto de PDF com múltiplos fallbacks"""
    text = ""
    
    # Método 1: pdfplumber (mais preciso)
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"⚠️ pdfplumber falhou: {e}")
    
    # Método 2: PyPDF2 (fallback)
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text + "\n"
        if text.strip():
            return text.strip()
    except Exception as e:
        print(f"⚠️ PyPDF2 falhou: {e}")
    
    # Método 3: Tentativa com encoding alternativo
    try:
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                try:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n"
                except:
                    continue
        return text.strip() if text.strip() else "Não foi possível extrair texto do PDF"
    except Exception as e:
        return f"Erro na extração: {str(e)}"

def extract_name_from_text(text, filename):
    """Tenta extrair o nome do candidato do texto do currículo"""
    try:
        # Remove extensão do arquivo para usar como fallback
        base_name = os.path.splitext(filename)[0]
        
        # Procura por padrões comuns em currículos
        lines = text.split('\n')
        for i, line in enumerate(lines[:10]):  # Primeiras 10 linhas
            line = line.strip()
            if len(line) > 3 and len(line) < 50:
                # Verifica se parece um nome (primeira letra maiúscula, sem números)
                if (any(c.isupper() for c in line) and 
                    not any(c.isdigit() for c in line) and
                    ' ' in line and
                    not any(word in line.lower() for word in ['curriculo', 'curriculum', 'linkedin', 'email', 'telefone', 'phone'])):
                    return line
        
        return base_name.replace('_', ' ').replace('-', ' ').title()
    except:
        return os.path.splitext(filename)[0].replace('_', ' ').title()

def extract_email_from_text(text):
    """Extrai email do texto do currículo"""
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    return emails[0] if emails else None

def extract_phone_from_text(text):
    """Extrai telefone do texto do currículo"""
    if not text:
        return None
    
    phone_pattern = r'(\+55\s?)?(\(?\d{2}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}'
    phone_match = re.search(phone_pattern, text)
    
    if phone_match:
        return phone_match.group().strip()
    
    return None

def extract_city_state_from_text(text):
    """Extrai cidade e estado do texto do currículo"""
    if not text:
        return None, None
    
    try:
        text_upper = text.upper()
        
        patterns = [
            r'(\w[\w\s]+?),\s*([A-Z]{2})',
            r'([^,]+?)\s*-\s*([A-Z]{2})',
            r'CIDADE:\s*([^\n,]+?)\s*\/\s*([A-Z]{2})',
            r'LOCALIZAÇÃO:\s*([^\n,]+?)\s*\/\s*([A-Z]{2})',
            r'ENDEREÇO[^:]*:\s*[^,]+?,\s*[^,]+?,\s*([^,]+?)\s*-\s*([A-Z]{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip().upper()
                
                brazil_states = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT',
                               'MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO',
                               'RR','SC','SP','SE','TO']
                
                if state in brazil_states:
                    city = re.sub(r'\b(RIO|DE|DA|DO|DOS|DAS|E|\d+)\b', '', city, flags=re.IGNORECASE).strip()
                    city = re.sub(r'\s+', ' ', city)
                    return city.title(), state
        
        return "Local não identificado", "NI"
        
    except Exception as e:
        print(f"⚠️ Erro ao extrair localização: {e}")
        return "Erro na extração", "ER"

def estimate_experience(text):
    """Estima a experiência do candidato"""
    if not text:
        return "Não informada"
    
    try:
        text_lower = text.lower()
        
        # 1. Procura por anos de experiência (ex: 5 anos de experiência)
        match = re.search(r'(\d+)\s+(?:anos|ano)\s+(?:de\s+)?experi[êe]ncia', text_lower)
        if match:
            years = int(match.group(1))
            if years < 3:
                return f"{years} anos (Júnior)"
            elif years < 8:
                return f"{years} anos (Pleno)"
            else:
                return f"{years} anos (Sênior)"
        
        seniority_keywords = {
            'sênior': '8+ anos (Sênior)',
            'senior': '8+ anos (Sênior)', 
            'pleno': '3-7 anos (Pleno)',
            'junior': '1-3 anos (Júnior)', 
            'júnior': '1-3 anos (Júnior)',
        }
        
        for keyword, exp in seniority_keywords.items():
            if keyword in text_lower:
                return exp
        
        return "Não informada"
        
    except Exception as e:
        print(f"⚠️ Erro ao estimar experiência: {e}")
        return "Não informada"

def extract_education(text):
    """Extrai informação educacional do texto do currículo"""
    if not text:
        return "Formação não informada"
    
    try:
        text_lower = text.lower()
        
        universities = [
            'usp', 'unicamp', 'ufrj', 'ufmg', 'ufrgs', 'ufpr', 'ufsc', 'unb',
            'puc', 'fgv', 'mackenzie', 'faap', 'fei'
        ]
        
        education_levels = {
            'doutorado': 'Doutorado',
            'mestrado': 'Mestrado',
            'mba': 'MBA',
            'graduação': 'Graduação',
            'bacharelado': 'Bacharelado',
        }
        
        found_university = None
        for uni in universities:
            if uni in text_lower:
                found_university = uni.upper()
                break
        
        found_level = None
        for level_key, level_name in education_levels.items():
            if level_key in text_lower:
                found_level = level_name
                break
        
        if found_university and found_level:
            return f"{found_university} - {found_level}"
        elif found_university:
            return f"{found_university} - Graduação"
        elif found_level:
            return found_level
        else:
            return "Formação superior"
        
    except Exception as e:
        print(f"⚠️ Erro ao extrair educação: {e}")
        return "Formação não identificada"

# ==================== FUNÇÕES AI ====================

def analyze_candidate_with_ai(resume_text, job_description, job_requirements):
    """Analisa candidato com IA usando AIAnalyzer"""
    try:
        candidate_data = {
            'name': 'Candidato',
            'resume_text': resume_text
        }
        
        job_reqs = {
            'title': 'Vaga',
            'description': job_description,
            'requirements': job_requirements,
            'level': 'Não especificado'
        }
        
        analysis = ai_analyzer.analyze_candidate(candidate_data, job_reqs)
        
        return {
            "score": analysis.get('overall_score', 50),
            "match_percentage": analysis.get('hard_skills_score', 50),
            "strengths": [analysis.get('strengths', 'Pontos fortes não identificados')],
            "weaknesses": [analysis.get('weaknesses', 'Pontos fracos não identificados')],
            "recommendation": analysis.get('recommendation', 'Revisar manualmente'),
            "summary": analysis.get('professional_summary', 'Resumo não disponível')
        }
        
    except Exception as e:
        return {
            "score": 50,
            "match_percentage": 50,
            "strengths": ['Erro na análise de IA'],
            "weaknesses": ['Erro na análise de IA'],
            "recommendation": 'Erro na análise de IA',
            "summary": f'Erro ao processar com IA: {str(e)}'
        }

def process_bulk_pdf_analysis(job_id):
    """Processa a análise de IA para candidatos pendentes de uma vaga"""
    job = Job.query.get(job_id)
    if not job:
        return
        
    candidates = Candidate.query.filter_by(job_id=job_id, status='pending').all()
    
    for candidate in candidates:
        try:
            ai_result = analyze_candidate_with_ai(candidate.resume_text, job.description, job.requirements)
            
            candidate.ai_score = ai_result['score']
            candidate.ai_analysis = json.dumps(ai_result)
            candidate.status = 'analyzed'
            
            db.session.commit()
            
        except Exception as e:
            print(f"❌ Erro ao analisar candidato {candidate.id}: {e}")
            db.session.rollback()

# ==================== ROTAS DE AUTENTICAÇÃO ====================

# ✅ ROTA TEMPORÁRIA - CRIAR USUÁRIO MANUALMENTE
@app.route('/fix-register')
def fix_register():
    """Solução temporária para criar usuário"""
    try:
        # Verifica se já existe admin
        admin = User.query.filter_by(email='admin@talentscope.com').first()
        
        if not admin:
            user = User(
                username='admin',
                email='admin@talentscope.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(user)
            db.session.commit()
            return '''
            <h1>✅ USUÁRIO CRIADO COM SUCESSO!</h1>
            <p><strong>Email:</strong> admin@talentscope.com</p>
            <p><strong>Senha:</strong> admin123</p>
            <p><a href="/login" style="display: inline-block; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px;">👉 CLIQUE AQUI PARA LOGIN</a></p>
            '''
        else:
            return f'''
            <h1>⚠️ Usuário já existe</h1>
            <p>O usuário admin já está cadastrado.</p>
            <p><a href="/login" style="color: blue;">Ir para Login</a></p>
            '''
            
    except Exception as e:
        return f'''
        <h1>❌ Erro ao criar usuário</h1>
        <p><strong>Erro:</strong> {str(e)}</p>
        <p><a href="/debug">Ver status do sistema</a></p>
        '''

# ✅ ROTA TEMPORÁRIA PARA CRIAR ADMIN RÁPIDO
@app.route('/create-admin-now')
def create_admin_now():
    """Rota temporária para criar admin rapidamente"""
    try:
        # Verifica se já existe usuário
        user_count = User.query.count()
        
        if user_count == 0:
            user = User(
                username='admin',
                email='admin@talentscope.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(user)
            db.session.commit()
            
            return '''
            <h1>✅ Usuário Admin Criado!</h1>
            <p><strong>Email:</strong> admin@talentscope.com</p>
            <p><strong>Senha:</strong> admin123</p>
            <p><a href="/login" style="color: blue;">👉 Clique aqui para fazer LOGIN</a></p>
            '''
        else:
            return f'''
            <h1>⚠️ Já existem usuários</h1>
            <p>Já existem {user_count} usuários no sistema.</p>
            <p><a href="/login" style="color: blue;">👉 Ir para Login</a></p>
            '''
            
    except Exception as e:
        return f'''
        <h1>❌ Erro ao criar usuário</h1>
        <p>Erro: {str(e)}</p>
        <p><a href="/debug" style="color: blue;">👉 Ver status do sistema</a></p>
        '''

# ✅ ROTA TEMPORÁRIA PARA CRIAR PRIMEIRO USUÁRIO
@app.route('/create-first-user')
def create_first_user():
    """Rota temporária para criar o primeiro usuário"""
    try:
        user_count = User.query.count()
        
        if user_count == 0:
            user = User(
                username='admin',
                email='admin@talentscope.com',
                password_hash=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(user)
            db.session.commit()
            return jsonify({
                'success': True,
                'message': 'Usuário admin criado!',
                'credentials': {
                    'email': 'admin@talentscope.com',
                    'password': 'admin123'
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Já existem usuários no sistema'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    # ✅ Verifica se existe algum usuário no banco
    try:
        user_count = db.session.query(User).count()
        
        if user_count == 0:
            # ✅ Primeiro acesso: redireciona para registro
            flash('Bem-vindo! Crie a primeira conta de administrador.', 'info')
            return redirect(url_for('register'))
        else:
            # ✅ Acessos subsequentes: redireciona para login
            return redirect(url_for('login'))
            
    except Exception as e:
        print(f"⚠️ Erro ao verificar usuários: {e}")
        # Em caso de erro, permite o registro
        return redirect(url_for('register'))
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    # ✅ VERIFICA SE TEM EMAIL PRÉ-PREENCHIDO DA SESSION
    prefill_email = session.pop('registered_email', None) if request.method == 'GET' else None
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha inválidos.', 'danger')
            
    return render_template('login.html', prefill_email=prefill_email)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Rota de registro - permite acesso controlado"""
    # Se já estiver logado, redireciona para dashboard
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    try:
        # Conta usuários existentes
        user_count = User.query.count()
    except Exception as e:
        print(f"⚠️ Erro ao verificar usuários: {e}")
        user_count = 0
    
    # ✅ CORREÇÃO: Se já existem usuários, mostra página de solicitação
    if user_count > 0:
        if request.method == 'POST':
            # Processa solicitação de acesso
            name = request.form.get('name')
            email = request.form.get('email')
            company = request.form.get('company')
            message = request.form.get('message')
            
            # Simula envio de solicitação
            print(f"📧 Solicitação de acesso recebida: {name} - {email} - {company}")
            flash('✅ Solicitação enviada! Entraremos em contato para liberar seu acesso.', 'success')
            return redirect(url_for('login'))
        
        # Mostra formulário de solicitação de acesso
        return render_template('request_access.html')
    
    # ✅ Se não há usuários, permite registro completo
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([username, email, password]):
            flash('Todos os campos são obrigatórios!', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe!', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'danger')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=True  # Primeiro usuário sempre é admin
        )
        
        db.session.add(user)
        db.session.commit()
        
        session['registered_email'] = email
        flash('🎉 Conta de administrador criada com sucesso! Faça login para continuar.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', is_first_user=True)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('login'))

# ==================== ROTAS PRINCIPAIS ====================

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        total_jobs = Job.query.count()
        total_candidates = Candidate.query.count()
        pending_candidates = Candidate.query.filter_by(status='pending').count()
        
        candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
        avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score) if candidates_with_score else 0.0
        
        recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
        recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
        
        return render_template('dashboard.html',
                             total_jobs=total_jobs,
                             total_candidates=total_candidates,
                             pending_candidates=pending_candidates,
                             avg_score=round(avg_score, 1),
                             total_interviews=0,
                             jobs=recent_jobs,
                             recent_jobs=recent_jobs,
                             recent_candidates=recent_candidates)
                             
    except Exception as e:
        print(f"❌ Erro no dashboard: {e}")
        return render_template('dashboard.html',
                             total_jobs=0,
                             total_candidates=0,
                             pending_candidates=0,
                             avg_score=0,
                             total_interviews=0,
                             jobs=[],
                             recent_jobs=[],
                             recent_candidates=[])

@app.route('/jobs')
@login_required
def jobs():
    try:
        all_jobs = Job.query.order_by(Job.created_at.desc()).all()
        
        for job in all_jobs:
            try:
                job.candidate_count = db.session.query(Candidate.id).filter_by(job_id=job.id).count()
            except Exception as e:
                print(f"⚠️ Erro ao contar candidatos para a vaga {job.id}: {str(e)}")
                job.candidate_count = 0
        
        return render_template('jobs.html', jobs=all_jobs)
        
    except Exception as e:
        print(f"❌ Erro ao listar vagas: {str(e)}")
        flash('Erro ao carregar vagas.', 'danger')
        return render_template('jobs.html', jobs=[])

@app.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    if request.method == 'POST':
        try:
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            requirements = request.form.get('requirements', '').strip()

            if not title:
                flash('O título da vaga é obrigatório!', 'danger')
                return render_template('new_job.html')

            job = Job(
                title=title,
                description=description if description else '',
                requirements=requirements if requirements else '',
                status='active',
                created_by=current_user.id
            )
            
            db.session.add(job)
            db.session.commit()
            
            flash(f'Vaga "{title}" criada com sucesso!', 'success')
            return redirect(url_for('jobs'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao criar vaga: {str(e)}', 'danger')
            return render_template('new_job.html')
    
    return render_template('new_job.html')

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).order_by(Candidate.ai_score.desc()).all()
    return render_template('job_detail.html', job=job, candidates=candidates)

@app.route('/jobs/<int:job_id>/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        files = request.files.getlist('pdf_files')
        
        if not files or all(not file.filename for file in files):
            flash('Por favor, selecione pelo menos um arquivo PDF.', 'danger')
            return redirect(url_for('bulk_upload_candidates', job_id=job_id))
        
        candidates_added = 0
        errors = []
        
        for file in files:
            if not file.filename:
                continue
                
            if not file.filename.lower().endswith('.pdf'):
                errors.append(f"'{file.filename}' não é um PDF válido")
                continue
            
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                resume_text = extract_text_from_pdf(filepath)
                
                if not resume_text.strip():
                    errors.append(f"PDF '{filename}' não contém texto legível")
                    os.remove(filepath)
                    continue
                
                # ✅ Extrair dados automaticamente
                candidate_name = extract_name_from_text(resume_text, filename)
                candidate_email = extract_email_from_text(resume_text)
                candidate_phone = extract_phone_from_text(resume_text)
                candidate_linkedin = extract_linkedin_from_text(resume_text)  # ✅ EXTRAÇÃO DO LINKEDIN
                
                candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email or f"candidato_{candidates_added + 1}@temp.com",
                    phone=candidate_phone,
                    linkedin_url=candidate_linkedin,  # ✅ SALVAR LINKEDIN
                    resume_path=filepath,
                    resume_text=resume_text,
                    job_id=job_id,
                    status='pending'
                )
                
                db.session.add(candidate)
                candidates_added += 1
                
                if candidate_linkedin:
                    print(f"🔗 LinkedIn encontrado para {candidate_name}: {candidate_linkedin}")
                
            except Exception as e:
                errors.append(f"Erro em '{file.filename}': {str(e)}")
                continue
        
        if candidates_added > 0:
            db.session.commit()
            process_bulk_pdf_analysis(job_id)
            flash(f'{candidates_added} currículos analisados com sucesso!', 'success')
        
        if errors:
            flash(f'Alguns erros: {", ".join(errors[:3])}', 'warning')
        
        return redirect(url_for('job_detail', job_id=job_id))
    
    return render_template('bulk_upload_pdf.html', job=job)

@app.route('/candidates/new/<int:job_id>', methods=['GET', 'POST'])
@login_required
def new_candidate(job_id):
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        file = request.files.get('resume')
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            resume_text = extract_text_from_pdf(filepath)
            ai_result = analyze_candidate_with_ai(resume_text, job.description, job.requirements)
            
            # ✅ Extrair LinkedIn do currículo
            linkedin_url = extract_linkedin_from_text(resume_text)
            
            candidate = Candidate(
                name=request.form.get('name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
                linkedin_url=linkedin_url or request.form.get('linkedin_url'),
                resume_path=filepath,
                resume_text=resume_text,
                job_id=job_id,
                ai_score=ai_result['score'],
                ai_analysis=json.dumps(ai_result)
            )
            
            db.session.add(candidate)
            db.session.commit()
            
            flash('Candidato adicionado com sucesso!', 'success')
            return redirect(url_for('job_detail', job_id=job_id))
    
    return render_template('new_candidate.html', job=job)

@app.route('/candidates/<int:candidate_id>')
@login_required
def candidate_detail(candidate_id):
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
    candidate = Candidate.query.get_or_404(candidate_id)
    candidate.status = request.form.get('status')
    db.session.commit()
    
    flash('Status atualizado!', 'success')
    return redirect(url_for('candidate_detail', candidate_id=candidate_id))

@app.route('/candidate/<int:candidate_id>/reanalyze', methods=['POST'])
@login_required
def reanalyze_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get_or_404(candidate.job_id)
    
    resume_text = candidate.resume_text 
    
    if not resume_text:
        flash('Erro: Não foi possível encontrar o texto do currículo para reanálise.', 'danger')
        return redirect(url_for('candidate_detail', candidate_id=candidate.id))

    candidate_data = {
        'name': candidate.name,
        'resume_text': resume_text
    }
    job_requirements = {
        'title': job.title,
        'level': 'Não especificado',
        'description': job.description,
        'skills_required': job.requirements
    }

    new_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)

    if 'overall_score' in new_analysis:
        candidate.ai_score = new_analysis['overall_score']
        candidate.ai_analysis = json.dumps(new_analysis)
        db.session.commit()
        flash('Análise de IA concluída e atualizada com sucesso!', 'success')
    else:
        candidate.ai_analysis = json.dumps(new_analysis)
        db.session.commit()
        flash('Erro ao reanalisar o candidato. Verifique os detalhes na seção de Análise IA.', 'danger')

    return redirect(url_for('candidate_detail', candidate_id=candidate.id))

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    job = Job.query.get_or_404(job_id)
    
    Candidate.query.filter_by(job_id=job_id).delete()
    
    db.session.delete(job)
    db.session.commit()
    
    flash(f'Vaga "{job.title}" excluída com sucesso!', 'success')
    return redirect(url_for('jobs'))

@app.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@login_required
def delete_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    job_id = candidate.job_id
    
    if candidate.resume_path and os.path.exists(candidate.resume_path):
        try:
            os.remove(candidate.resume_path)
        except:
            pass
    
    db.session.delete(candidate)
    db.session.commit()
    
    flash(f'Candidato "{candidate.name}" excluído com sucesso!', 'success')
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/jobs/<int:job_id>/export')
@login_required
def export_candidates(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).order_by(Candidate.name).all()
    
    if not candidates:
        flash('Nenhum candidato para exportar.', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    data = []
    for candidate in candidates:
        data.append({
            'Nome': candidate.name,
            'Email': candidate.email,
            'Telefone': candidate.phone,
            'LinkedIn': candidate.linkedin_url or ''
        })
        
    df = pd.DataFrame(data)
    
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'candidatos_{job.title.replace(" ", "_")}.csv'
    )

@app.route('/candidate-space')
@login_required
def candidate_space():
    try:
        all_candidates = Candidate.query.filter(
            Candidate.ai_score.isnot(None)
        ).order_by(Candidate.ai_score.desc()).limit(50).all()
        
        top_candidates = []
        for candidate in all_candidates[:10]:
            city, state = extract_city_state_from_text(candidate.resume_text or "")
            
            candidate_data = {
                'id': candidate.id,
                'name': candidate.name,
                'email': candidate.email,
                'score': candidate.ai_score or 0,
                'city': city or "Não informada",
                'state': state or "NI",
                'experience': estimate_experience(candidate.resume_text or ""),
                'education': extract_education(candidate.resume_text or ""),
                'tech_score': candidate.ai_score or 0,
                'phone': candidate.phone or "Não informado",
                'linkedin_url': candidate.linkedin_url
            }
            
            top_candidates.append(candidate_data)
        
        return render_template('candidate_space.html', top_candidates=top_candidates)
        
    except Exception as e:
        print(f"❌ Erro no Espaço Candidato: {e}")
        return render_template('candidate_space.html', top_candidates=[])

@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

@app.route('/api/calendar/events')
@login_required
def calendar_events():
    interviews = Interview.query.filter(
        Interview.status == 'scheduled'
    ).all()
    
    events = []
    for interview in interviews:
        events.append({
            'id': interview.id,
            'title': f"{interview.candidate.name} - {interview.job.title}",
            'start': interview.start_time.isoformat(),
            'end': interview.end_time.isoformat(),
            'color': '#007bff',
            'extendedProps': {
                'candidate_id': interview.candidate_id,
                'job_id': interview.job_id,
                'status': interview.status
            }
        })
    
    return jsonify(events)

@app.route('/interviews')
@login_required
def interviews_list():
    interviews = Interview.query.order_by(Interview.start_time.asc()).all()
    return render_template('interviews_list.html', interviews=interviews)

@app.route('/interviews/new', methods=['GET', 'POST'])
@login_required
def new_interview():
    try:
        if request.method == 'POST':
            try:
                candidate_id = request.form.get('candidate_id')
                job_id = request.form.get('job_id')
                title = request.form.get('title')
                start_time = request.form.get('start_time')
                end_time = request.form.get('end_time')
                meeting_link = request.form.get('meeting_link')

                if not all([candidate_id, job_id, title, start_time, end_time]):
                    flash('Todos os campos obrigatórios devem ser preenchidos!', 'danger')
                    return redirect(url_for('new_interview'))

                interview = Interview(
                    candidate_id=int(candidate_id),
                    job_id=int(job_id),
                    title=title,
                    description=request.form.get('description', ''),
                    start_time=datetime.fromisoformat(start_time),
                    end_time=datetime.fromisoformat(end_time),
                    meeting_link=meeting_link or '',
                    notes=request.form.get('notes', ''),
                    created_by=current_user.id
                )
                
                db.session.add(interview)
                db.session.commit()
                
                flash('Entrevista agendada com sucesso!', 'success')
                return redirect(url_for('calendar'))
                
            except Exception as e:
                flash(f'Erro ao agendar entrevista: {str(e)}', 'danger')
        
        candidates = Candidate.query.all()
        jobs = Job.query.all()
        
        return render_template('new_interview.html', 
                             candidates=candidates, 
                             jobs=jobs)
                             
    except Exception as e:
        print(f"❌ Erro na rota new_interview: {e}")
        flash(f'Erro interno ao carregar dados: {str(e)}', 'danger')
        candidates = Candidate.query.all()
        jobs = Job.query.all()
        return render_template('new_interview.html', 
                             candidates=candidates, 
                             jobs=jobs)

# ==================== ROTAS ADICIONAIS ====================

@app.route('/interviews/schedule/<int:candidate_id>', methods=['GET', 'POST'])
@login_required
def schedule_interview_from_candidate(candidate_id):
    """Agendar entrevista a partir da página do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    if request.method == 'POST':
        try:
            job_id = request.form.get('job_id')
            title = request.form.get('title')
            description = request.form.get('description', '')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            meeting_link = request.form.get('meeting_link', '')
            notes = request.form.get('notes', '')

            if not all([job_id, title, start_time, end_time]):
                flash('Todos os campos obrigatórios devem ser preenchidos!', 'danger')
                return redirect(url_for('schedule_interview_from_candidate', candidate_id=candidate_id))

            interview = Interview(
                candidate_id=candidate_id,
                job_id=int(job_id),
                title=title,
                description=description,
                start_time=datetime.fromisoformat(start_time),
                end_time=datetime.fromisoformat(end_time),
                meeting_link=meeting_link,
                notes=notes,
                created_by=current_user.id
            )
            
            db.session.add(interview)
            db.session.commit()
            
            flash('Entrevista agendada com sucesso!', 'success')
            return redirect(url_for('candidate_detail', candidate_id=candidate_id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao agendar entrevista: {str(e)}', 'danger')
    
    jobs = Job.query.all()
    suggested_title = f"Entrevista com {candidate.name}"
    if candidate.job:
        suggested_title += f" - {candidate.job.title}"
    
    return render_template('schedule_interview_from_candidate.html', 
                         candidate=candidate, 
                         jobs=jobs,
                         suggested_title=suggested_title)

@app.route('/jobs/<int:job_id>/reanalyze_all', methods=['POST'])
@login_required
def reanalyze_all_candidates_for_job(job_id):
    """Reanalisa todos os candidatos para uma vaga específica"""
    try:
        job = Job.query.get_or_404(job_id)
        candidates = Candidate.query.filter_by(job_id=job_id).all()
        
        if not candidates:
            flash('Nenhum candidato encontrado para reanálise.', 'warning')
            return redirect(url_for('job_detail', job_id=job_id))
        
        reanalyzed_count = 0
        
        for candidate in candidates:
            try:
                analysis_result = analyze_candidate_with_ai(
                    candidate.resume_text, 
                    job.description, 
                    job.requirements
                )
                
                if analysis_result and 'score' in analysis_result:
                    candidate.ai_score = analysis_result.get('score', 0)
                    candidate.ai_analysis = json.dumps(analysis_result)
                    reanalyzed_count += 1
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Erro ao reanalisar candidato {candidate.id}: {str(e)}")
                continue
        
        db.session.commit()
        
        if reanalyzed_count > 0:
            flash(f'Reanálise concluída! {reanalyzed_count} candidatos foram reanalisados.', 'success')
        else:
            flash('Nenhum candidato pôde ser reanalisado.', 'warning')
            
    except Exception as e:
        db.session.rollback()
        flash(f'Erro durante a reanálise: {str(e)}', 'error')
    
    return redirect(url_for('job_detail', job_id=job_id))

# ==================== INICIALIZAÇÃO ====================

def initialize_app():
    """Inicializa a aplicação e o banco de dados"""
    print("🚀 Inicializando aplicação...")
    with app.app_context():
        init_database()
        print("✅ Aplicação inicializada com sucesso!")

# ✅ INICIALIZA O BANCO DE DADOS AO INICIAR
initialize_app()

# ✅ ROTA DE DEBUG PARA VERIFICAR STATUS
@app.route('/debug')
def debug_info():
    """Rota para debugging no Render"""
    info = {
        'database_url': app.config['SQLALCHEMY_DATABASE_URI'][:50] + '...' if app.config['SQLALCHEMY_DATABASE_URI'] else None,
        'user_count': User.query.count(),
        'tables_created': len(inspect(db.engine).get_table_names()) if db.engine else 0
    }
    return jsonify(info)

if __name__ == "__main__":
    # Inicializa o banco de dados
    initialize_app()
    
    # Cria as tabelas se estiver usando SQLite localmente
    if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
        with app.app_context():
            db.create_all()
            
    app.run(debug=True)