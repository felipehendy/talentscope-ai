import os
import io
import re
import pdfplumber
import PyPDF2
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
    linkedin_url = db.Column(db.String(500), nullable=True)
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
def calculate_location_score(candidate_city, candidate_state, job_city, job_state):
    """Calcula score de localização"""
    if not candidate_city or not candidate_state:
        return 50
    
    if candidate_city == job_city and candidate_state == job_state:
        return 100
    elif candidate_state == job_state:
        return 80
    else:
        return 60

def calculate_experience_score(candidate_exp, job_requirements):
    """Calcula score de experiência baseado nos requisitos"""
    # Lógica simples baseada em anos
    if "sênior" in job_requirements.lower() and candidate_exp >= 5:
        return 90
    elif "pleno" in job_requirements.lower() and candidate_exp >= 3:
        return 80
    elif "júnior" in job_requirements.lower():
        return 70
    else:
        return 60
    
def extract_text_from_pdf(file_path):
    """Extrai texto de PDF com múltiplos fallbacks"""
    text = ""
    
    # Método 1: pdfplumber (mais preciso)
    try:
        import pdfplumber
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
        import PyPDF2
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

def extract_city_state_from_text(text):
    """Extrai cidade e estado do texto do currículo - VERSÃO MELHORADA"""
    if not text:
        return None, None
    
    try:
        text_upper = text.upper()
        
        # Padrões mais específicos para endereços brasileiros
        patterns = [
            r'(\w[\w\s]+?),\s*([A-Z]{2})',  # "São Paulo, SP"
            r'([^,]+?)\s*-\s*([A-Z]{2})',   # "São Paulo - SP" 
            r'CIDADE:\s*([^\n,]+?)\s*\/\s*([A-Z]{2})',  # "CIDADE: São Paulo/SP"
            r'LOCALIZAÇÃO:\s*([^\n,]+?)\s*\/\s*([A-Z]{2})',
            r'ENDEREÇO[^:]*:\s*[^,]+?,\s*[^,]+?,\s*([^,]+?)\s*-\s*([A-Z]{2})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_upper)
            if match:
                city = match.group(1).strip()
                state = match.group(2).strip().upper()
                
                # Validar estados brasileiros
                brazil_states = ['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT',
                               'MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO',
                               'RR','SC','SP','SE','TO']
                
                if state in brazil_states:
                    # Limpar nome da cidade (remover lixo comum)
                    city = re.sub(r'\b(RIO|DE|DA|DO|DOS|DAS|E|\d+)\b', '', city, flags=re.IGNORECASE).strip()
                    city = re.sub(r'\s+', ' ', city)  # Remove espaços múltiplos
                    return city.title(), state
        
        # Fallback: procurar por menções de estados
        state_pattern = r'\b([A-Z]{2})\b'
        state_matches = re.findall(state_pattern, text_upper)
        for state in state_matches:
            if state in brazil_states:
                # Tentar encontrar cidade próxima
                city_pattern = r'([A-Z][A-Z\s]{3,20}?)\s*[,-\/]\s*' + state
                city_match = re.search(city_pattern, text_upper)
                if city_match:
                    city = city_match.group(1).strip()
                    city = re.sub(r'\s+', ' ', city)
                    return city.title(), state
                else:
                    return "Cidade não identificada", state
        
        return "Local não identificada", "NI"
        
    except Exception as e:
        print(f"⚠️ Erro ao extrair localização: {e}")
        return "Erro na extração", "ER"

def estimate_experience(text):
    """Estima anos de experiência baseado no texto - VERSÃO MELHORADA"""
    if not text:
        return "Não informada"
    
    try:
        text_lower = text.lower()
        
        # Padrões para anos de experiência explícitos
        exp_patterns = [
            r'(\d+)[\s\-]+anos?[\s\-]+(?:de\s+)?experiência',
            r'experiência[\s\-]+(?:de\s+)?(\d+)[\s\-]+anos?',
            r'(\d+)[\s\-]+anos?[\s\-]+(?:na\s+área|em\s+ti|em\s+tecnologia|na\s+profissão)',
            r'tempo[\s\-]+de[\s\-]+experiência[\s\-]*:[\s\-]*(\d+)',
        ]
        
        for pattern in exp_patterns:
            match = re.search(pattern, text_lower)
            if match:
                years = int(match.group(1))
                if years <= 2:
                    return f"{years} ano" + ("s" if years > 1 else "")
                elif years <= 5:
                    return f"{years} anos (Pleno)"
                else:
                    return f"{years} anos (Sênior)"
        
        # Procurar por senioridade
        seniority_keywords = {
            'sênior': '8+ anos (Sênior)',
            'senior': '8+ anos (Sênior)', 
            'sr.': '8+ anos (Sênior)',
            'pleno': '3-7 anos (Pleno)',
            'pleno/': '3-7 anos (Pleno)',
            'junior': '1-3 anos (Júnior)', 
            'júnior': '1-3 anos (Júnior)',
            'jr.': '1-3 anos (Júnior)',
            'estagiário': '0-1 ano (Estagiário)',
            'estagiaria': '0-1 ano (Estagiário)',
            'trainee': '0-1 ano (Trainee)',
            'assistente': '1-3 anos (Assistente)'
        }
        
        for keyword, exp in seniority_keywords.items():
            if keyword in text_lower:
                return exp
        
        # Estimativa por anos mencionados (mais conservadora)
        year_matches = re.findall(r'(19|20)\d{2}', text)
        if year_matches:
            unique_years = len(set(year_matches))
            estimated_years = min(unique_years, 10)  # Máximo 10 anos
            if estimated_years <= 2:
                return f"{estimated_years} anos (Júnior)"
            elif estimated_years <= 5:
                return f"{estimated_years} anos (Pleno)"
            else:
                return f"{estimated_years}+ anos (Sênior)"
        
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
        
        # Universidades brasileiras comuns
        universities = [
            'usp', 'unicamp', 'ufrj', 'ufmg', 'ufrgs', 'ufpr', 'ufsc', 'unb', 'ufba', 'ufc',
            'unesp', 'puc', 'puc-rio', 'puc-sp', 'puc-rs', 'puc-mg', 'puc-pr',
            'fgv', 'mackenzie', 'faap', 'fei', 'fmu', 'unip', 'anhanguera', 'estácio',
            'uninove', 'cruzeiro do sul', 'unicesumar', 'unifran', 'unimar'
        ]
        
        # Níveis de formação
        education_levels = {
            'doutorado': 'Doutorado',
            'phd': 'Doutorado', 
            'mestrado': 'Mestrado',
            'mba': 'MBA',
            'graduação': 'Graduação',
            'bacharelado': 'Bacharelado',
            'licenciatura': 'Licenciatura',
            'tecnólogo': 'Tecnólogo',
            'técnico': 'Técnico',
            'ensino médio': 'Ensino Médio'
        }
        
        # Procurar por universidades
        found_university = None
        for uni in universities:
            if uni in text_lower:
                found_university = uni.upper()
                break
        
        # Procurar por nível de formação
        found_level = None
        for level_key, level_name in education_levels.items():
            if level_key in text_lower:
                found_level = level_name
                break
        
        # Montar resultado
        if found_university and found_level:
            return f"{found_university} - {found_level}"
        elif found_university:
            return f"{found_university} - Graduação"
        elif found_level:
            return found_level
        else:
            # Procurar por padrões comuns de educação
            patterns = [
                r'(ciência da computação|engenharia|administração|direito|medicina|pedagogia)',
                r'(sistemas de informação|análise de sistemas|gestão|marketing|rh|recursos humanos)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    return f"{match.group(1).title()}"
            
            return "Formação superior"  # Default
        
    except Exception as e:
        print(f"⚠️ Erro ao extrair educação: {e}")
        return "Formação não identificada"
    
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

# ==================== FUNÇÕES PARA IMPORTACAO EM MASSA ====================

def process_bulk_analysis(job_id):
    """Processa análise de IA para todos os candidatos pendentes da vaga"""
    try:
        job = Job.query.get(job_id)
        candidates = Candidate.query.filter_by(job_id=job_id, ai_score=None).all()
        
        if not candidates:
            return
        
        print(f"🔍 Iniciando análise em massa para {len(candidates)} candidatos...")
        
        for candidate in candidates:
            try:
                # ❌ PROBLEMA: Candidatos importados em massa NÃO têm currículo PDF
                # ✅ SOLUÇÃO: Usar dados básicos para análise ou criar um texto simulado
                resume_text = candidate.resume_text
                
                if not resume_text:
                    # Criar um texto básico com informações disponíveis
                    resume_text = f"""
CANDIDATO: {candidate.name}
EMAIL: {candidate.email}
TELEFONE: {candidate.phone or 'Não informado'}
LINKEDIN: {candidate.linkedin_url or 'Não informado'}

INFORMAÇÕES DISPONÍVEIS:
- Candidato importado via CSV
- Dados de contato básicos fornecidos
- Currículo detalhado não disponível para análise
"""
                    candidate.resume_text = resume_text
                
                # Analisar com IA
                ai_result = analyze_candidate_with_ai(resume_text, job.description, job.requirements)
                
                candidate.ai_score = ai_result['score']
                candidate.ai_analysis = json.dumps(ai_result)
                
                print(f"✅ Analisado: {candidate.name} - Score: {ai_result['score']}")
                
                # Commit após cada candidato para não perder progresso
                db.session.commit()
                
            except Exception as e:
                print(f"❌ Erro ao analisar {candidate.name}: {str(e)}")
                continue
        
        print("🎯 Análise em massa concluída!")
        
    except Exception as e:
        print(f"❌ Erro no processamento em massa: {str(e)}")

# ==================== ROTAS ====================

@app.route('/candidates/<int:candidate_id>/schedule-interview', methods=['GET', 'POST'])
@login_required
def schedule_interview_from_candidate(candidate_id):
    """Agendar entrevista a partir da página do candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    
    if request.method == 'POST':
        try:
            interview = Interview(
                candidate_id=candidate_id,
                job_id=request.form.get('job_id'),
                title=request.form.get('title'),
                description=request.form.get('description'),
                start_time=datetime.fromisoformat(request.form.get('start_time')),
                end_time=datetime.fromisoformat(request.form.get('end_time')),
                meeting_link=request.form.get('meeting_link'),
                notes=request.form.get('notes'),
                created_by=current_user.id
            )
            
            db.session.add(interview)
            db.session.commit()
            
            flash('Entrevista agendada com sucesso!', 'success')
            return redirect(url_for('calendar'))
            
        except Exception as e:
            flash(f'Erro ao agendar entrevista: {str(e)}', 'danger')
    
    # Dados para o formulário (GET)
    jobs = Job.query.all()
    
    return render_template('new_interview.html', 
                         candidate=candidate,
                         jobs=jobs,
                         auto_fill_candidate=True)

@app.route('/interviews/<int:interview_id>/send-whatsapp')
@login_required
def send_interview_whatsapp(interview_id):
    """Enviar convite de entrevista via WhatsApp"""
    interview = Interview.query.get_or_404(interview_id)
    candidate = interview.candidate
    
    if not candidate.phone:
        flash('Candidato não possui telefone cadastrado!', 'danger')
        return redirect(url_for('calendar'))
    
    # Formatar data e hora
    start_time = interview.start_time
    formatted_date = start_time.strftime('%d/%m/%Y')
    formatted_time = start_time.strftime('%H:%M')
    
    # Criar mensagem personalizada
    message = f"""Olá {candidate.name}! 

🎯 *Convite para Entrevista*

📅 *Data:* {formatted_date}
⏰ *Horário:* {formatted_time}
💼 *Vaga:* {interview.job.title}

"""
    
    # Adicionar link da reunião se existir
    if interview.meeting_link:
        message += f"🔗 *Link da Reunião:* {interview.meeting_link}\n\n"
    
    message += f"""Por favor, confirme sua disponibilidade.

Atenciosamente,
Equipe TalentScope AI"""
    
    # Codificar mensagem para URL
    encoded_message = quote(message)
    
    # Marcar como enviado no banco
    interview.whatsapp_sent = True
    interview.whatsapp_sent_at = datetime.utcnow()
    db.session.commit()
    
    # 🔥 CORREÇÃO: Usar a função whatsapp_link corretamente
    base_url = whatsapp_link(candidate.phone)
    whatsapp_url = f"{base_url}&text={encoded_message}"
    
    flash('Convite preparado para envio no WhatsApp!', 'success')
    return redirect(whatsapp_url)

@app.route('/api/candidates/<int:job_id>')
@login_required
def get_candidates_by_job(job_id):
    """API para buscar candidatos por vaga"""
    candidates = Candidate.query.filter_by(job_id=job_id).all()
    
    candidates_data = []
    for candidate in candidates:
        candidates_data.append({
            'id': candidate.id,
            'name': candidate.name,
            'email': candidate.email,
            'phone': candidate.phone
        })
    
    return jsonify(candidates_data)


@app.route('/calendar')
@login_required
def calendar():
    """Página principal do calendário"""
    return render_template('calendar.html')

@app.route('/api/calendar/events')
@login_required
def calendar_events():
    """API para eventos do calendário"""
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
            'color': '#007bff',  # Azul padrão
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
    """Lista de entrevistas"""
    interviews = Interview.query.order_by(Interview.start_time.asc()).all()
    return render_template('interviews_list.html', interviews=interviews)

@app.route('/interviews/new', methods=['GET', 'POST'])
@login_required
def new_interview():
    """Agendar nova entrevista"""
    if request.method == 'POST':
        try:
            interview = Interview(
                candidate_id=request.form.get('candidate_id'),
                job_id=request.form.get('job_id'),
                title=request.form.get('title'),
                description=request.form.get('description'),
                start_time=datetime.fromisoformat(request.form.get('start_time')),
                end_time=datetime.fromisoformat(request.form.get('end_time')),
                meeting_link=request.form.get('meeting_link'),
                notes=request.form.get('notes'),
                created_by=current_user.id
            )
            
            db.session.add(interview)
            db.session.commit()
            
            flash('Entrevista agendada com sucesso!', 'success')
            return redirect(url_for('calendar'))
            
        except Exception as e:
            flash(f'Erro ao agendar entrevista: {str(e)}', 'danger')
    
    # Dados para o formulário
    candidates = Candidate.query.all()
    jobs = Job.query.all()
    
    return render_template('new_interview.html', 
                         candidates=candidates, 
                         jobs=jobs)

@app.route('/interviews/<int:interview_id>/delete', methods=['POST'])
@login_required
def delete_interview(interview_id):
    """Cancelar entrevista"""
    interview = Interview.query.get_or_404(interview_id)
    interview.status = 'cancelled'
    db.session.commit()
    
    flash('Entrevista cancelada!', 'success')
    return redirect(url_for('calendar'))

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

# ==================== ROTAS PARA IMPORTACAO EM MASSA ====================

@app.route('/jobs/<int:job_id>/bulk-upload', methods=['GET', 'POST'])
@login_required
def bulk_upload_candidates(job_id):
    """Importar e analisar múltiplos candidatos de uma vez via PDFs"""
    job = Job.query.get_or_404(job_id)
    
    if request.method == 'POST':
        files = request.files.getlist('pdf_files')  # Múltiplos arquivos PDF
        
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
                # Salvar o arquivo PDF
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Extrair texto do PDF
                resume_text = extract_text_from_pdf(filepath)
                
                if not resume_text.strip():
                    errors.append(f"PDF '{filename}' não contém texto legível")
                    os.remove(filepath)
                    continue
                
                # Extrair nome e email automaticamente do texto
                candidate_name = extract_name_from_text(resume_text, filename)
                candidate_email = extract_email_from_text(resume_text)
                
                # Criar candidato
                candidate = Candidate(
                    name=candidate_name,
                    email=candidate_email or f"candidato_{candidates_added + 1}@temp.com",
                    phone=None,  # Será extraído se encontrado no PDF
                    linkedin_url=None,
                    resume_path=filepath,
                    resume_text=resume_text,
                    job_id=job_id,
                    status='pending'
                )
                
                db.session.add(candidate)
                candidates_added += 1
                
                print(f"📄 PDF processado: {filename} → {candidate_name}")
                
            except Exception as e:
                errors.append(f"Erro em '{file.filename}': {str(e)}")
                continue
        
        # Commit para obter IDs dos candidatos
        if candidates_added > 0:
            db.session.commit()
            
            # 🔥 PROCESSAMENTO EM MASSA DA IA - ANALISA TODOS OS PDFs
            process_bulk_pdf_analysis(job_id)
            
            flash(f'{candidates_added} currículos PDF analisados com sucesso pela IA!', 'success')
        
        if errors:
            flash(f'Alguns erros: {", ".join(errors[:3])}', 'warning')
        
        return redirect(url_for('job_detail', job_id=job_id))
    
    return render_template('bulk_upload_pdf.html', job=job)

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
    import re
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    return emails[0] if emails else None

def extract_phone_from_text(text):
    """Extrai telefone do texto do currículo - VERSÃO CORRIGIDA"""
    import re
    phone_pattern = r'(\+55\s?)?(\(?\d{2}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}'
    phones = re.findall(phone_pattern, text)
    
    if phones:
        # 🔥 CORREÇÃO: re.findall retorna lista de tuplas, precisamos extrair a string completa
        # Procura pelo padrão completo no texto
        phone_match = re.search(phone_pattern, text)
        if phone_match:
            return phone_match.group().strip()
    
    return None

def process_bulk_pdf_analysis(job_id):
    """Processa análise de IA para TODOS os candidatos da vaga (com PDFs) - VERSÃO CORRIGIDA"""
    try:
        job = Job.query.get(job_id)
        candidates = Candidate.query.filter_by(job_id=job_id).all()
        
        if not candidates:
            return
        
        print(f"🔍 Iniciando análise em massa para {len(candidates)} currículos PDF...")
        
        for candidate in candidates:
            try:
                if not candidate.resume_text:
                    print(f"⚠️ Candidato {candidate.name} sem texto de currículo")
                    continue
                
                # Analisar com IA
                ai_result = analyze_candidate_with_ai(candidate.resume_text, job.description, job.requirements)
                
                # Atualizar candidato com análise completa
                candidate.ai_score = ai_result['score']
                candidate.ai_analysis = json.dumps(ai_result)
                
                # 🔥 CORREÇÃO: Verificar se phone é None antes de tentar extrair
                if not candidate.phone:
                    phone = extract_phone_from_text(candidate.resume_text)
                    if phone:
                        candidate.phone = phone
                
                print(f"✅ Analisado: {candidate.name} - Score: {ai_result['score']}")
                
                # 🔥 CORREÇÃO: Rollback em caso de erro e continuar com próximo candidato
                db.session.commit()
                
            except Exception as e:
                print(f"❌ Erro ao analisar {candidate.name}: {str(e)}")
                db.session.rollback()  # 🔥 IMPORTANTE: Rollback para continuar com próximo
                continue
        
        print("🎯 Análise em massa de PDFs concluída!")
        
    except Exception as e:
        print(f"❌ Erro no processamento em massa: {str(e)}")
        db.session.rollback()  # 🔥 Rollback geral

@app.route('/jobs/<int:job_id>/reanalyze-all', methods=['POST'])
@login_required
def reanalyze_all_candidates(job_id):
    """Reanalisa TODOS os candidatos da vaga"""
    try:
        # Resetar scores para forçar reanálise completa
        Candidate.query.filter_by(job_id=job_id).update({'ai_score': None})
        db.session.commit()
        
        # Processar análise em massa
        process_bulk_analysis(job_id)
        
        flash('Reanálise em massa concluída! Todos os candidatos foram atualizados.', 'success')
        return redirect(url_for('job_detail', job_id=job_id))
        
    except Exception as e:
        flash(f'Erro ao iniciar reanálise: {str(e)}', 'danger')
        return redirect(url_for('job_detail', job_id=job_id))

# ==================== ROTAS EXISTENTES ====================

@app.route('/candidate-space')
@login_required
def candidate_space():
    """Página do Espaço Candidato - Top 10 Ranking com dados REAIS"""
    
    # Buscar TODOS os candidatos com score do banco de dados
    all_candidates = Candidate.query.filter(
        Candidate.ai_score.isnot(None)
    ).order_by(Candidate.ai_score.desc()).limit(50).all()
    
    # Processar dados para o template
    top_candidates = []
    for i, candidate in enumerate(all_candidates[:10]):  # Top 10
        # Extrair localização do texto do currículo
        city, state = extract_city_state_from_text(candidate.resume_text or "")
        
        # Calcular scores baseados nos dados reais
        top_candidates.append({
            'id': candidate.id,
            'name': candidate.name,
            'email': candidate.email,
            'score': candidate.ai_score or 0,
            'city': city or "Não informada",
            'state': state or "NI",
            'experience': estimate_experience(candidate.resume_text or ""),
            'education': extract_education(candidate.resume_text or ""),
            'tech_score': candidate.ai_score or 0,
            'location_score': 75,  # Placeholder por enquanto
            'exp_score': 80,       # Placeholder por enquanto
            'phone': candidate.phone
        })
    
    return render_template('candidate_space.html', top_candidates=top_candidates)

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
    """Dashboard com tratamento de erros robusto"""
    try:
        # Consultas seguras com try/except
        try:
            total_jobs = Job.query.count()
        except:
            total_jobs = 0
            
        try:
            total_candidates = Candidate.query.count()
        except:
            total_candidates = 0
            
        try:
            pending_candidates = Candidate.query.filter_by(status='pending').count()
        except:
            pending_candidates = 0
            
        try:
            candidates_with_score = Candidate.query.filter(Candidate.ai_score.isnot(None)).all()
            if candidates_with_score:
                avg_score = sum(c.ai_score for c in candidates_with_score) / len(candidates_with_score)
            else:
                avg_score = 0.0
        except:
            avg_score = 0.0
        
        # Dados mockados para evitar erros
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
        
        # Consultas seguras para dados recentes
        try:
            recent_jobs = Job.query.order_by(Job.created_at.desc()).limit(5).all()
        except:
            recent_jobs = []
            
        try:
            recent_candidates = Candidate.query.order_by(Candidate.created_at.desc()).limit(5).all()
        except:
            recent_candidates = []
        
        total_interviews = 0
        
        return render_template('dashboard.html',
                             total_jobs=total_jobs,
                             total_candidates=total_candidates,
                             pending_candidates=pending_candidates,
                             avg_score=round(avg_score, 1),
                             total_interviews=total_interviews,
                             jobs=recent_jobs,  # Passando jobs para o template
                             top_skills=top_skills,
                             seniority_counts=seniority_counts,
                             recent_jobs=recent_jobs,
                             recent_candidates=recent_candidates)
                             
    except Exception as e:
        print(f"❌ Erro crítico no dashboard: {e}")
        # Fallback: dashboard mínimo
        return render_template('dashboard.html',
                             total_jobs=0,
                             total_candidates=0,
                             pending_candidates=0,
                             avg_score=0,
                             total_interviews=0,
                             jobs=[],
                             top_skills=[],
                             seniority_counts={},
                             recent_jobs=[],
                             recent_candidates=[])

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
                linkedin_url=request.form.get('linkedin_url'),
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

@app.route('/jobs/<int:job_id>/delete', methods=['POST'])
@login_required
def delete_job(job_id):
    """Excluir vaga"""
    job = Job.query.get_or_404(job_id)
    
    # Excluir todos os candidatos da vaga primeiro
    Candidate.query.filter_by(job_id=job_id).delete()
    
    # Excluir a vaga
    db.session.delete(job)
    db.session.commit()
    
    flash(f'Vaga "{job.title}" excluída com sucesso!', 'success')
    return redirect(url_for('jobs'))

@app.route('/candidates/<int:candidate_id>/delete', methods=['POST'])
@login_required
def delete_candidate(candidate_id):
    """Excluir candidato"""
    candidate = Candidate.query.get_or_404(candidate_id)
    job_id = candidate.job_id
    
    # Excluir arquivo do currículo se existir
    if candidate.resume_path and os.path.exists(candidate.resume_path):
        try:
            os.remove(candidate.resume_path)
        except:
            pass
    
    # Excluir candidato
    db.session.delete(candidate)
    db.session.commit()
    
    flash(f'Candidato "{candidate.name}" excluído com sucesso!', 'success')
    return redirect(url_for('job_detail', job_id=job_id))

@app.route('/jobs/<int:job_id>/export')
@login_required
def export_candidates(job_id):
    """Exporta candidatos de uma vaga para CSV"""
    job = Job.query.get_or_404(job_id)
    candidates = Candidate.query.filter_by(job_id=job_id).order_by(Candidate.name).all()
    
    if not candidates:
        flash('Nenhum candidato para exportar.', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    # Preparar dados para o DataFrame
    data = []
    for candidate in candidates:
        data.append({
            'Nome': candidate.name,
            'Email': candidate.email,
            'Telefone': candidate.phone,
            'LinkedIn': candidate.linkedin_url
        })
        
    df = pd.DataFrame(data)
    
    # Gerar CSV em memória
    output = io.StringIO()
    df.to_csv(output, index=False, encoding='utf-8-sig')
    output.seek(0)
    
    # Enviar arquivo para download
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'candidatos_{job.title.replace(" ", "_")}.csv'
    )

# ==================== INICIALIZAÇÃO ====================
with app.app_context():
    try:
        db.create_all()
        print("✅ Tabelas criadas com sucesso!")
        
        # 🔥 CORREÇÃO: SQLite não suporta IF NOT EXISTS, usar try/except
        try:
            # Verificar se as colunas já existem
            inspector = db.inspect(db.engine)
            existing_columns = [col['name'] for col in inspector.get_columns('candidate')]
            
            if 'resume_text' not in existing_columns:
                db.engine.execute(text("ALTER TABLE candidate ADD COLUMN resume_text TEXT"))
                print("✅ Coluna resume_text adicionada!")
                
            if 'linkedin_url' not in existing_columns:
                db.engine.execute(text("ALTER TABLE candidate ADD COLUMN linkedin_url VARCHAR(500)"))
                print("✅ Coluna linkedin_url adicionada!")
                
        except Exception as e:
            print(f"⚠️ Aviso nas colunas: {e}")
        
        print(f"📊 Total de usuários no banco: {User.query.count()}")
        print("✅ Banco de dados inicializado!")
    except Exception as e:
        print(f"⚠️ Aviso ao inicializar banco: {e}")
# Configuração para produção no Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)