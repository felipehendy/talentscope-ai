import os
from dotenv import load_dotenv

print("🔧 Testando carregamento do .env...")

# Carregar .env
load_dotenv()

# Verificar variáveis
gemini_key = os.getenv('GOOGLE_API_KEY')
openai_key = os.getenv('OPENAI_API_KEY')

print(f"GOOGLE_API_KEY: {'✅' if gemini_key else '❌ Não encontrada'}")
print(f"OPENAI_API_KEY: {'✅' if openai_key else '❌ Não encontrada'}")

if gemini_key:
    print(f"Chave Gemini: {gemini_key[:10]}...")