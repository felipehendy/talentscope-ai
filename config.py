"""
Configurações centralizadas do TalentScope AI
CRIAR ESTE ARQUIVO NA RAIZ: config.py
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configurações base"""
    # Segurança
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-MUDE-EM-PRODUCAO')
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')
    
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Upload
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    ALLOWED_EXTENSIONS = {'pdf'}
    
    # APIs
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    
    # Session
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hora
    
    # Paginação
    ITEMS_PER_PAGE = 20


class DevelopmentConfig(Config):
    """Configurações de desenvolvimento"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Configurações de produção"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Apenas HTTPS
    
    # Sobrescrever SECRET_KEY para forçar uso de variável de ambiente
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    def __init__(self):
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY deve ser definida em produção!")


class TestingConfig(Config):
    """Configurações de teste"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


# Mapa de configurações
config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(env=None):
    """
    Retorna configuração baseada no ambiente
    
    Usage:
        from config import get_config
        app.config.from_object(get_config())
    """
    if env is None:
        env = os.getenv('FLASK_ENV', 'development')
    
    return config_map.get(env, config_map['default'])
