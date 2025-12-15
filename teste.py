# teste.py
import os
import json
import requests
from dotenv import load_dotenv
import certifi

# ==============================
# 🔑 Carregar variáveis de ambiente
# ==============================
load_dotenv()

API_KEY = os.getenv("PARETO_API_KEY")
AGENT_ID = os.getenv("TESS_AGENT_ID")

if not API_KEY or not AGENT_ID:
    raise ValueError("🚨 PARETO_API_KEY ou TESS_AGENT_ID não encontrada. Configure a variável de ambiente.")

# ==============================
# 📄 Currículo para análise
# ==============================
# Aqui você pode ler um arquivo PDF/TXT e extrair o texto
# Para o teste, colocamos um texto de exemplo
curriculo_texto = """
Candidato: Felipe Paulo da Silva
Experiência: Analista de Informações Operacionais Jr
Resumo: Experiência em análise de dados, relatórios gerenciais e suporte operacional.
"""

# ==============================
# 🌐 Endpoint da Tess
# ==============================
url = f"https://api.pareto.io/v1/tess/analysis/agents/{AGENT_ID}/execute"

# ==============================
# 📝 Payload
# ==============================
payload = {
    "texto": curriculo_texto,
    "temperature": 0.5,
    "model": "gpt-4o-mini",
    "maxlength": 500,
    "language": "Portuguese (Brazil)"
}

# ==============================
# 🛡️ Headers
# ==============================
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# ==============================
# 🔧 Requisição com sessão segura
# ==============================
with requests.Session() as s:
    s.verify = certifi.where()  # Garante certificado SSL atualizado
    try:
        response = s.post(url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()  # Gera exceção para erros HTTP
        data = response.json()
        print("✅ Requisição enviada com sucesso!")
        print("🔹 Resposta da Tess:\n")
        # Exibe o output, se existir
        if "output" in data:
            print(data["output"])
        else:
            print(json.dumps(data, indent=2, ensure_ascii=False))
    except requests.exceptions.SSLError as ssl_err:
        print("❌ Erro SSL:", ssl_err)
    except requests.exceptions.RequestException as req_err:
        print("❌ Erro na requisição:", req_err)
