"""
Validadores e funções auxiliares para TalentScope AI
COLE ESTE CÓDIGO EM: utils/validators.py
"""
import os
import re
from werkzeug.utils import secure_filename
import logging

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf'}

# ==================== VALIDAÇÃO DE ARQUIVOS ====================

def allowed_file(filename):
    """Verifica se a extensão do arquivo é permitida"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(filename):
    """Sanitiza nome de arquivo e adiciona timestamp"""
    from datetime import datetime
    
    filename = secure_filename(filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(filename)
    name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
    
    return f"{name}_{timestamp}{ext}"


def validate_file_size(file, max_size_mb=16):
    """Valida tamanho do arquivo"""
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    
    max_bytes = max_size_mb * 1024 * 1024
    
    if size > max_bytes:
        size_mb = size / (1024 * 1024)
        return False, f"Arquivo muito grande ({size_mb:.1f}MB). Máximo: {max_size_mb}MB"
    
    if size == 0:
        return False, "Arquivo está vazio"
    
    return True, ""


def validate_pdf_content(filepath):
    """Valida se o PDF é legível"""
    try:
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            
            if len(reader.pages) == 0:
                return False, "PDF vazio (sem páginas)"
            
            try:
                first_page = reader.pages[0]
                text = first_page.extract_text()
            except Exception as e:
                return False, f"Erro ao ler PDF: {str(e)}"
        
        return True, ""
        
    except Exception as e:
        logger.error(f"Erro ao validar PDF: {e}")
        return False, "Arquivo PDF inválido ou corrompido"


# ==================== VALIDAÇÃO DE DADOS ====================

def validate_email(email):
    """Valida formato de email"""
    if not email:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone(phone):
    """Valida telefone brasileiro (10 ou 11 dígitos)"""
    if not phone:
        return False
    
    clean = ''.join(filter(str.isdigit, str(phone)))
    return len(clean) in [10, 11]


def format_phone_for_whatsapp(phone):
    """Formata telefone para WhatsApp"""
    if not phone:
        return None
    
    clean = ''.join(filter(str.isdigit, str(phone)))
    
    if len(clean) <= 11 and not clean.startswith('55'):
        clean = '55' + clean
    
    return clean if len(clean) >= 12 else None


def validate_username(username):
    """Valida nome de usuário"""
    if not username:
        return False, "Usuário não pode estar vazio"
    
    if len(username) < 3:
        return False, "Usuário deve ter no mínimo 3 caracteres"
    
    if len(username) > 50:
        return False, "Usuário deve ter no máximo 50 caracteres"
    
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Usuário deve conter apenas letras, números e underscore"
    
    return True, ""


def validate_password(password):
    """Valida senha"""
    if not password:
        return False, "Senha não pode estar vazia"
    
    if len(password) < 6:
        return False, "Senha deve ter no mínimo 6 caracteres"
    
    if len(password) > 100:
        return False, "Senha deve ter no máximo 100 caracteres"
    
    return True, ""


def truncate_text(text, max_length=100, suffix='...'):
    """Trunca texto"""
    if not text:
        return ''
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix