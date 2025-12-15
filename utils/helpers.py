"""
Funções auxiliares gerais para TalentScope AI
CRIAR: utils/helpers.py
"""
from datetime import datetime
from flask import flash
import logging

logger = logging.getLogger(__name__)


# ==================== FORMATAÇÃO ====================

def format_date(date, format='%d/%m/%Y'):
    """Formata data para exibição"""
    if not date:
        return ''
    
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date)
        except:
            return date
    
    try:
        return date.strftime(format)
    except:
        return str(date)


def format_datetime(dt, format='%d/%m/%Y %H:%M'):
    """Formata data e hora"""
    return format_date(dt, format)


def format_phone_display(phone):
    """
    Formata telefone para exibição
    11999999999 → (11) 99999-9999
    """
    if not phone:
        return ''
    
    clean = ''.join(filter(str.isdigit, str(phone)))
    
    # Remove DDI se tiver
    if clean.startswith('55') and len(clean) > 11:
        clean = clean[2:]
    
    if len(clean) == 11:
        return f"({clean[:2]}) {clean[2:7]}-{clean[7:]}"
    elif len(clean) == 10:
        return f"({clean[:2]}) {clean[2:6]}-{clean[6:]}"
    
    return phone


def format_score(score, decimals=1):
    """Formata score para exibição"""
    if score is None:
        return 'N/A'
    
    try:
        return f"{float(score):.{decimals}f}"
    except:
        return str(score)


def format_file_size(size_bytes):
    """Formata tamanho de arquivo"""
    if not size_bytes:
        return '0 B'
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    
    return f"{size_bytes:.1f} TB"


# ==================== STATUS E BADGES ====================

def get_status_badge_class(status):
    """Retorna classe CSS para badge de status"""
    status_map = {
        'pending': 'warning',
        'interview': 'info',
        'approved': 'success',
        'rejected': 'danger',
        'active': 'success',
        'inactive': 'secondary'
    }
    return status_map.get(status, 'secondary')


def get_status_icon(status):
    """Retorna ícone para status"""
    icon_map = {
        'pending': 'fa-clock',
        'interview': 'fa-calendar-check',
        'approved': 'fa-check-circle',
        'rejected': 'fa-times-circle',
        'active': 'fa-check',
        'inactive': 'fa-ban'
    }
    return icon_map.get(status, 'fa-circle')


def get_score_class(score):
    """Retorna classe CSS baseada no score"""
    if score is None:
        return 'secondary'
    
    try:
        score = float(score)
        if score >= 80:
            return 'success'
        elif score >= 60:
            return 'warning'
        else:
            return 'danger'
    except:
        return 'secondary'


# ==================== MENSAGENS ====================

def flash_success(message):
    """Flash message de sucesso"""
    flash(f'✅ {message}', 'success')


def flash_error(message):
    """Flash message de erro"""
    flash(f'❌ {message}', 'danger')


def flash_warning(message):
    """Flash message de aviso"""
    flash(f'⚠️ {message}', 'warning')


def flash_info(message):
    """Flash message de informação"""
    flash(f'ℹ️ {message}', 'info')


# ==================== PAGINAÇÃO ====================

def paginate_query(query, page, per_page=20):
    """
    Pagina uma query SQLAlchemy
    
    Returns:
        tuple: (items, pagination_info)
    """
    try:
        page = int(page) if page else 1
        per_page = int(per_page) if per_page else 20
    except:
        page = 1
        per_page = 20
    
    if page < 1:
        page = 1
    
    total = query.count()
    items = query.limit(per_page).offset((page - 1) * per_page).all()
    
    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'pages': (total + per_page - 1) // per_page,
        'has_prev': page > 1,
        'has_next': page * per_page < total,
        'prev_page': page - 1 if page > 1 else None,
        'next_page': page + 1 if page * per_page < total else None
    }
    
    return items, pagination


# ==================== VALIDAÇÕES RÁPIDAS ====================

def is_safe_redirect_url(url):
    """Verifica se URL é segura para redirect"""
    if not url:
        return False
    
    # Evita open redirect
    if url.startswith('http://') or url.startswith('https://'):
        return False
    
    if url.startswith('//'):
        return False
    
    return True


def sanitize_search_query(query):
    """Remove caracteres perigosos de queries de busca"""
    if not query:
        return ''
    
    # Remove caracteres especiais SQL
    dangerous_chars = ['%', '_', ';', '--', '/*', '*/']
    
    clean_query = str(query)
    for char in dangerous_chars:
        clean_query = clean_query.replace(char, '')
    
    return clean_query.strip()


# ==================== LOGGING ====================

def log_action(action, user_id=None, details=None):
    """Log de ações importantes"""
    message = f"ACTION: {action}"
    
    if user_id:
        message += f" | USER: {user_id}"
    
    if details:
        message += f" | DETAILS: {details}"
    
    logger.info(message)


# ==================== ESTATÍSTICAS ====================

def calculate_percentage(part, total):
    """Calcula porcentagem com segurança"""
    if not total or total == 0:
        return 0.0
    
    try:
        return round((float(part) / float(total)) * 100, 1)
    except:
        return 0.0


def get_average(values):
    """Calcula média com segurança"""
    if not values:
        return 0.0
    
    valid_values = [v for v in values if v is not None]
    
    if not valid_values:
        return 0.0
    
    try:
        return sum(valid_values) / len(valid_values)
    except:
        return 0.0