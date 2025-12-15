import os
import json
import requests

# Carrega API Key do ambiente
API_KEY = os.getenv("PARETO_API_KEY")
if not API_KEY:
    raise ValueError("🚨 PARETO_API_KEY não encontrada. Configure a variável de ambiente.")

AGENT_ID = 67  # Substitua pelo seu Agent ID
URL = f"https://tess.pareto.io/api/agents/{AGENT_ID}/execute"

# Dados da requisição
data = {
    "texto": "Estou construindo uma solução de IA para RH focada em análise de currículos.",
    "temperature": 0.5,
    "model": "gpt-4o-mini",
    "maxlength": 120,
    "language": "Portuguese (Brazil)"
}

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# Envia requisição
response = requests.post(URL, headers=headers, json=data)

if response.status_code == 200:
    print("✅ REQUISIÇÃO ENVIADA COM SUCESSO!")
    resp_json = response.json()
    
    # Salva o último request_id
    with open("last_request.json", "w", encoding="utf-8") as f:
        json.dump(resp_json, f, ensure_ascii=False, indent=2)
else:
    print(f"❌ ERRO NA REQUISIÇÃO | STATUS CODE: {response.status_code}")
    print(response.text)
