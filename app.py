import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
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

# Configuração
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'sua-chave-secreta-super-segura-123')

# Database - PostgreSQL em produção, SQLite local
database_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://')

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
    description = db.Column(db.Text)
    requirements = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    candidates = db.relationship('Candidate', backref='job', lazy=True)

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
    return User.query.get(int(user_id))

# ==================== FUNÇÕES AI ====================
def extract_text_from_pdf(file_path):
    """Extrai texto de PDF"""
    try:
        import pdfplumber
        with pdfplumber.open(file_path) as pdf:
            text = ''
            for page in pdf.pages:
                text += page.extract_text() or ''
        return text
    except:
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ''
                for page in reader.pages:
                    text += page.extract_text() or ''
            return text
        except:
            return ''

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
        
        # Usar o AIAnalyzer (automaticamente usa Gemini)
        analysis = ai_analyzer.analyze_candidate(candidate_data, job_reqs)
        
        # Converter resultado do novo formato para o formato antigo (compatibilidade)
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
            "strengths": ["Erro na análise"],
            "weaknesses": [f"Detalhes: {str(e)}"],
            "recommendation": "Revisar manualmente",
            "summary": f"Erro na análise: {str(e)}"
        }

# ==================== ROTAS ====================

@app.route('/candidate/<int:candidate_id>/reanalyze', methods=['POST'])
@login_required
def reanalyze_candidate(candidate_id):
    candidate = Candidate.query.get_or_404(candidate_id)
    job = Job.query.get_or_404(candidate.job_id)
    
    # Extrair texto do currículo
    resume_text = candidate.resume_text 
    
    if not resume_text:
        flash('Erro: Não foi possível encontrar o texto do currículo para reanálise.', 'danger')
        return redirect(url_for('candidate_detail', candidate_id=candidate.id))

    # Preparar os dados para o analisador
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

    # Chamar o analisador de IA
    new_analysis = ai_analyzer.analyze_candidate(candidate_data, job_requirements)

    # Atualizar o candidato no banco de dados
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

@app.route('/')
def index():
    """Rota principal - verifica primeiro acesso"""
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
    """Rota de login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if User.query.count() == 0:
        flash('Nenhum usuário cadastrado. Crie sua conta primeiro.', 'warning')
        return redirect(url_for('register'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos!', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Rota de registro"""
    user_count = User.query.count()
    
    if user_count > 0 and not current_user.is_authenticated:
        flash('Registro desabilitado. Faça login ou contate o administrador.', 'warning')
        return redirect(url_for('login'))
    
    if current_user.is_authenticated and not current_user.is_admin and user_count > 0:
        flash('Apenas administradores podem criar novos usuários.', 'warning')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'danger')
            return redirect(url_for('register'))
        
        is_first_user = (user_count == 0)
        
        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            is_admin=is_first_user
        )
        db.session.add(user)
        db.session.commit()
        
        if is_first_user:
            flash('Conta criada com sucesso! Você é o administrador do sistema.', 'success')
        else:
            flash('Conta criada com sucesso!', 'success')
        
        return redirect(url_for('login'))
    
    is_first_user = (user_count == 0)
    
    return render_template('register.html', is_first_user=is_first_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logout realizado com sucesso!', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    total_jobs = Job.query.count()
    total_candidates = Candidate.query.count()
    pending_candidates = Candidate.query.filter_by(status='pending').count()
    
    candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
    if candidates_with_score:
        avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score)
    else:
        avg_score = 0.0
    
    total_interviews = 0
    
    jobs = Job.query.all()
    
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
    
    recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
    recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
    
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
                         recent_candidates=recent_candidates)

@app.route('/jobs')
@login_required
def jobs():
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('jobs.html', jobs=all_jobs)

@app.route('/jobs/new', methods=['GET', 'POST'])
@login_required
def new_job():
    if request.method == 'POST':
        job = Job(
            title=request.form.get('title'),
            description=request.form.get('description'),
            requirements=request.form.get('requirements'),
            created_by=current_user.id
        )
        db.session.add(job)
        db.session.commit()
        
        flash('Vaga criada com sucesso!', 'success')
        return redirect(url_for('jobs'))
    
    return render_template('new_job.html')

@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).order_by(Candidate.ai_score.desc()).all()
    return render_template('job_detail.html', job=job, candidates=candidates)

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
            
            candidate = Candidate(
                name=request.form.get('name'),
                email=request.form.get('email'),
                phone=request.form.get('phone'),
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

@app.route('/metrics')
@login_required
def metrics():
    """Página de métricas"""
    total_candidates = Candidate.query.count()
    total_interviews = 0
    
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
                         total_interviews=total_interviews,
                         avg_score=avg_score,
                         top_skills=top_skills,
                         seniority_counts=seniority_counts,
                         jobs=jobs)

# ==================== INICIALIZAÇÃO ====================
with app.app_context():
    try:
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
        
        # 🔥 ADICIONAR COLUNA resume_text AUTOMATICAMENTE
        try:
            with db.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE candidate ADD COLUMN IF NOT EXISTS resume_text TEXT"
                ))
                conn.commit()
            print("✅ Coluna resume_text verificada/adicionada!")
        except Exception as e:
            print(f"⚠️ Coluna resume_text: {e}")
        
        print(f"📊 Total de usuários no banco: {User.query.count()}")
        print("✅ Banco de dados inicializado!")
    except Exception as e:
        print(f"⚠️ Aviso ao inicializar banco: {e}")

# Configuração para produção no Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)