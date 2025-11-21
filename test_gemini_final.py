import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

print("🔧 Testando configuração do Gemini...")

# Verificar chave
gemini_key = os.getenv('GOOGLE_API_KEY')
if not gemini_key:
    print("❌ GOOGLE_API_KEY não encontrada no .env")
    exit()

print(f"✅ GOOGLE_API_KEY encontrada: {gemini_key[:10]}...")

try:
    # Configurar
    genai.configure(api_key=gemini_key)
    print("✅ Gemini configurado com sucesso!")
    
    # Testar modelo
    model = genai.GenerativeModel('gemini-1.5-flash')
    print("✅ Modelo carregado!")
    
    # Teste simples
    response = model.generate_content("Responda apenas 'OK' se estiver funcionando")
    print(f"✅ Resposta do Gemini: {response.text}")
    
except Exception as e:
    print(f"❌ Erro: {e}")