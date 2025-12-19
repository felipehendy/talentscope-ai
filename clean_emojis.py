import re

def remove_emojis():
    with open('chatbot_service.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Dicionário de substituições
    replacements = {
        '🚀': 'Inicializando',
        '🤖': 'CONFIGURACAO', 
        '🔑': 'API Key',
        '🌐': 'Endpoint',
        '⏱️': 'Timeout',
        '🎯': 'Model',
        '🌡️': 'Temperature',
        '✅': 'OK',
        '💬': 'NOVA QUERY',
        '📝': 'Query',
        '👥': 'Candidatos',
        '💼': 'Vagas',
        '📡': 'Enviando',
        '👋': 'Processando',
        '📄': 'Processando',
        '🔍': 'Testando',
        '❌': 'ERROR',
        '⚠️': 'WARN',
        '🔥': 'Pontos Fortes',
        '💡': 'Recomendacao',
        '❓': 'PERGUNTA',
    }
    
    # Remover todos os emojis
    for emoji, replacement in replacements.items():
        content = content.replace(emoji, replacement)
    
    # Remover outros emojis não listados
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # símbolos & pictogramas
        "\U0001F680-\U0001F6FF"  # transporte & símbolos
        "\U0001F700-\U0001F77F"  # alquimia
        "\U0001F780-\U0001F7FF"  # formas geométricas
        "\U0001F800-\U0001F8FF"  # setas suplementares
        "\U0001F900-\U0001F9FF"  # símbolos suplementares
        "\U0001FA00-\U0001FA6F"  # símbolos de xadrez
        "\U0001FA70-\U0001FAFF"  # símbolos suplementares
        "\U00002702-\U000027B0"  # símbolos diversos
        "\U000024C2-\U0001F251" 
        "]+", flags=re.UNICODE
    )
    
    content = emoji_pattern.sub('', content)
    
    with open('chatbot_service.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Todos os emojis foram removidos!")

if __name__ == '__main__':
    remove_emojis()
    