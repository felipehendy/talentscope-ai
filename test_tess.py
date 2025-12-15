#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
test_tess.py - Script para testar conexão com Tess AI
VERSÃO CORRIGIDA - Agent 67 requer campos customizados
"""

import os
import json
import requests
from dotenv import load_dotenv

def test_tess_connection():
    """Testa conexão com Agent 67 usando campos obrigatórios"""
    
    print("🧪 TESTE DE CONEXÃO TESS AI - AGENT 67 CUSTOMIZADO")
    print("=" * 60)
    
    # Carregar variáveis de ambiente
    load_dotenv()
    
    api_key = os.getenv('PARETO_API_KEY') or os.getenv('TESS_API_KEY')
    agent_id = os.getenv('TESS_AGENT_ID') or os.getenv('AGENT_ID', '67')
    
    if not api_key:
        print("❌ ERRO: PARETO_API_KEY não encontrada no .env")
        return False
    
    print(f"✅ API Key encontrada: {api_key[:10]}...{api_key[-5:]}")
    print(f"✅ Agent ID: {agent_id}")
    
    # Montar endpoint
    endpoint = f"https://tess.pareto.io/api/agents/{agent_id}/execute"
    print(f"✅ Endpoint: {endpoint}")
    
    # ============================================================
    # 🔥 PAYLOAD CORRETO PARA AGENT 67 CUSTOMIZADO
    # ============================================================
    # O Agent 67 foi configurado para EXIGIR estes campos:
    # - texto: o input/prompt
    # - temperature: controle de criatividade (0.0 a 1.0)
    # - model: modelo de IA a usar
    # - maxlength: tamanho máximo da resposta
    # - language: idioma da resposta
    # ============================================================
    
    payload = {
        "texto": "Olá, este é um teste de conexão. Por favor, responda com 'Teste bem-sucedido!' e confirme que está funcionando corretamente.",
        "temperature": "0.5",              # STRING! Opções: "0", "0.25", "0.5", "0.75", "1"
        "model": "gpt-4o-mini",            # Modelos disponíveis no Agent 67
        "maxlength": 500,                  # Número inteiro
        "language": "Portuguese (Brazil)"  # Nome COMPLETO do idioma
    }
    
    # Headers
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("\n📦 PAYLOAD ENVIADO (Agent 67 Customizado):")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    print("\n🔐 HEADERS:")
    print(json.dumps({
        "Authorization": f"Bearer {api_key[:10]}...{api_key[-5:]}",
        "Content-Type": headers["Content-Type"]
    }, indent=2))
    
    print("\n🚀 Enviando requisição...")
    
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=60  # Aumentado para 60s (IA pode demorar)
        )
        
        print(f"\n📡 STATUS CODE: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCESSO! Agent 67 respondeu!")
            
            try:
                data = response.json()
                print("\n📥 RESPOSTA COMPLETA:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # Tentar extrair o output
                if 'output' in data:
                    print("\n💬 OUTPUT DO AGENT:")
                    print(data['output'])
                elif 'data' in data and 'output' in data['data']:
                    print("\n💬 OUTPUT DO AGENT:")
                    print(data['data']['output'])
                
                return True
            except:
                print("\n📥 RESPOSTA (texto):")
                print(response.text[:1000])
                return True
        
        else:
            print(f"❌ ERRO HTTP {response.status_code}")
            
            try:
                error = response.json()
                print("\n📥 ERRO DETALHADO:")
                print(json.dumps(error, indent=2, ensure_ascii=False))
            except:
                print("\n📥 RESPOSTA:")
                print(response.text[:500])
            
            return False
    
    except requests.exceptions.Timeout:
        print("❌ ERRO: Timeout (requisição demorou mais de 60s)")
        print("   O Agent pode estar processando. Tente aumentar o timeout.")
        return False
    
    except requests.exceptions.ConnectionError as e:
        print(f"❌ ERRO DE CONEXÃO: {e}")
        return False
    
    except Exception as e:
        print(f"❌ ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_agent_details():
    """Tenta obter detalhes do Agent 67"""
    
    print("\n\n🔍 OBTENDO DETALHES DO AGENT 67")
    print("=" * 60)
    
    load_dotenv()
    api_key = os.getenv('PARETO_API_KEY') or os.getenv('TESS_API_KEY')
    agent_id = os.getenv('TESS_AGENT_ID') or os.getenv('AGENT_ID', '67')
    
    url = f"https://tess.pareto.io/api/agents/{agent_id}"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📡 Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("\n📋 CONFIGURAÇÃO DO AGENT:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            return data
        else:
            print(f"❌ Não foi possível obter detalhes (HTTP {response.status_code})")
            return None
    
    except Exception as e:
        print(f"❌ Erro ao obter detalhes: {e}")
        return None


if __name__ == "__main__":
    print("\n")
    
    # Teste 1: Testar execução do agent
    success = test_tess_connection()
    
    # Teste 2: Obter detalhes do agent
    test_agent_details()
    
    print("\n" + "=" * 60)
    
    if success:
        print("✅ TESTE CONCLUÍDO COM SUCESSO!")
        print("   O Agent 67 está funcionando corretamente.")
        print("\n📝 CONFIGURAÇÃO IDENTIFICADA:")
        print("   - Campo: 'texto' (não 'input')")
        print("   - Campos obrigatórios: texto, temperature, model, maxlength, language")
    else:
        print("❌ TESTE FALHOU!")
        print("   Possíveis causas:")
        print("   1. API Key inválida ou expirada")
        print("   2. Sem permissão para usar Agent 67")
        print("   3. Agent 67 não existe ou foi deletado")
        print("   4. Problema de conectividade")
    
    print("=" * 60)