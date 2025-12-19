"""
Teste rápido da API Tess
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('PARETO_API_KEY')
agent_id = os.getenv('TESS_AGENT_ID', '67')
endpoint = f"https://tess.pareto.io/api/agents/{agent_id}/execute"

print(f"🔑 API Key: {api_key[:20]}...")
print(f"🆔 Agent ID: {agent_id}")
print(f"🔗 Endpoint: {endpoint}")

# Teste simples
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "input": "Olá, teste",
    "parameters": {
        "temperature": 0.3,
        "max_tokens": 100
    }
}

try:
    response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
    print(f"\n📡 Status: {response.status_code}")
    print(f"📄 Resposta: {response.text[:500]}")
except Exception as e:
    print(f"\n❌ Erro: {e}")