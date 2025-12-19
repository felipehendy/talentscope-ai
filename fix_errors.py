"""
Script para corrigir automaticamente os erros de encoding e API deprecated
"""

import re
from pathlib import Path

def fix_query_get(file_path: Path):
    """Substitui Query.get() por db.session.get()"""
    content = file_path.read_text(encoding='utf-8')
    
    # Padrão 1: Model.query.get(id)
    pattern1 = r'(\w+)\.query\.get\(([^)]+)\)'
    replacement1 = r'db.session.get(\1, \2)'
    content = re.sub(pattern1, replacement1, content)
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✅ {file_path.name}: Query.get() corrigido")

def fix_emoji_logging(file_path: Path):
    """Remove emojis diretos do código"""
    content = file_path.read_text(encoding='utf-8')
    
    # Mapa de substituições
    emoji_map = {
        '✅': '[OK]',
        '❌': '[ERROR]',
        '⚠️': '[WARN]',
        '🤖': '[BOT]',
        '🔑': '[KEY]',
        '🚀': '[START]',
        '📊': '[DATA]',
        '💬': '[CHAT]',
        '🎯': '[TARGET]',
        '📄': '[FILE]',
        '💼': '[JOB]',
        '👥': '[USERS]',
        '🌐': '[WEB]',
        '⏱️': '[TIME]',
        '🌡️': '[TEMP]',
        '📡': '[API]',
        '📥': '[IN]',
        '📦': '[PKG]',
        '🔍': '[FIND]',
        '═': '='
    }
    
    for emoji_char, replacement in emoji_map.items():
        content = content.replace(emoji_char, replacement)
    
    file_path.write_text(content, encoding='utf-8')
    print(f"✅ {file_path.name}: Emojis substituídos")

def main():
    """Executa todas as correções"""
    print("🔧 Iniciando correções automáticas...\n")
    
    # Arquivos a corrigir
    files = ['app.py', 'chatbot_service.py']
    
    for file_name in files:
        file_path = Path(file_name)
        
        if not file_path.exists():
            print(f"⚠️ {file_name} não encontrado")
            continue
        
        print(f"📝 Processando {file_name}...")
        
        # Backup
        backup_path = file_path.with_suffix('.py.bak')
        backup_path.write_text(file_path.read_text(encoding='utf-8'), encoding='utf-8')
        print(f"💾 Backup criado: {backup_path.name}")
        
        # Aplicar correções
        fix_emoji_logging(file_path)
        fix_query_get(file_path)
        
        print(f"✅ {file_name} corrigido\n")
    
    print("🎉 Correções concluídas com sucesso!")
    print("📂 Backups salvos com extensão .bak")

if __name__ == '__main__':
    main()
