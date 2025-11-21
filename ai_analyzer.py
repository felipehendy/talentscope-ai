import os
import json
import google.generativeai as genai
from typing import Dict, Any, Optional
import re

# Importação condicional da OpenAI
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    print("⚠️  OpenAI não disponível. Usando apenas Google Gemini.")
    OPENAI_AVAILABLE = False

class AIAnalyzer:
    def __init__(self):
        # ✅ CARREGAR .env PRIMEIRO
        from dotenv import load_dotenv
        load_dotenv()
        
        # Configuração do Gemini (PRIORIDADE AGORA)
        gemini_key = os.getenv('GOOGLE_API_KEY')
        
        if gemini_key:
            try:
                genai.configure(api_key=gemini_key)
                self.gemini_client = genai
                self.gemini_available = True
                
                # Modelos de texto - versões CORRETAS
                text_models_priority = [
                    'gemini-2.0-flash',           # Modelo rápido e eficiente
                    'gemini-2.0-flash-001',       # Versão específica
                    'gemini-pro-latest',          # Modelo estável
                ]
                
                # Tentar usar um modelo de texto
                self.gemini_model = None
                for model_name in text_models_priority:
                    try:
                        model = genai.GenerativeModel(model_name)
                        # Teste simples
                        test_response = model.generate_content("Test")
                        self.gemini_model = model_name
                        print(f"✅ Modelo Gemini selecionado: {self.gemini_model}")
                        break
                    except Exception as e:
                        print(f"❌ Modelo {model_name} não disponível: {e}")
                        continue
                
                # Se nenhum modelo funcionou
                if not self.gemini_model:
                    self.gemini_available = False
                    print("❌ Nenhum modelo Gemini funcionou")
                
            except Exception as e:
                print(f"⚠️  Erro ao configurar Gemini: {e}")
                self.gemini_available = False
        else:
            self.gemini_available = False
            print("❌ GOOGLE_API_KEY não encontrada")
        
        # Configuração do OpenAI (APENAS SE DISPONÍVEL)
        self.openai_available = False
        if OPENAI_AVAILABLE and os.getenv('OPENAI_API_KEY'):
            try:
                openai_key = os.getenv('OPENAI_API_KEY')
                self.openai_client = OpenAI(api_key=openai_key)
                self.openai_available = True
                print("✅ OpenAI configurado")
            except Exception as e:
                print(f"⚠️  OpenAI não configurado: {e}")
                self.openai_available = False
        
        # Provider padrão - PRIORIDADE GEMINI
        if self.gemini_available:
            self.current_provider = 'gemini'
            print(f"🚀 Google Gemini configurado como provider principal")
        elif self.openai_available:
            self.current_provider = 'openai'
            print("🤖 OpenAI como provider")
        else:
            self.current_provider = None
            print("❌ Nenhuma API de IA disponível!")

    def analyze_candidate(self, candidate_data, job_requirements):
        """
        Analisa um candidato usando Gemini PRIMEIRO
        """
        prompt = self._build_analysis_prompt(candidate_data, job_requirements)
        
        # Tentar Gemini PRIMEIRO
        if self.gemini_available:
            try:
                analysis = self._analyze_with_gemini(prompt)
                self.current_provider = 'gemini'
                print(f"🤖 Análise realizada com Google Gemini ({self.gemini_model})")
                return analysis
            except Exception as e:
                print(f"❌ Gemini falhou: {e}")
        
        # Fallback para OpenAI
        if self.openai_available:
            try:
                analysis = self._analyze_with_openai(prompt)
                self.current_provider = 'openai'
                print("🤖 Análise realizada com OpenAI")
                return analysis
            except Exception as e:
                print(f"❌ OpenAI também falhou: {e}")
        
        # Se ambas falharem
        print("❌ Todas as APIs falharam. Retornando análise padrão.")
        return self._get_fallback_analysis()

    def _build_analysis_prompt(self, candidate_data, job_requirements):
        """Constrói o prompt para análise com critérios rigorosos de senioridade"""
        
        json_template = '''{
    "contact_info": {
        "email": "email@exemplo.com ou null",
        "phone": "+55 11 99999-9999 ou null",
        "linkedin": "https://linkedin.com/in/usuario ou null"
    },
    "extracted_skills": ["skill1","skill2","skill3"],
    "seniority_detected": "Júnior" | "Pleno" | "Sênior" | "Especialista" | "Coordenador" | "Gerente" | "Diretor",
    "experience_years": 4.5,
    "experience_summary": "Resumo de experiências relevantes em 2-3 linhas",
    "leadership_responsibilities": ["exemplo: liderou time de 5 pessoas","exemplo: gerenciou budget X"],
    "complexity_indicators": ["arquitetura distribuída","integração multi-sistemas"],
    "mentorship_indicators": ["mentoria interna","treinamentos conduzidos"],
    "strengths": "Principais pontos fortes em 2-3 linhas",
    "weaknesses": "Possíveis pontos fracos em 2-3 linhas",
    "hard_skills_score": 8.5,
    "soft_skills_score": 7.0,
    "overall_score": 7.8,
    "professional_summary": "Resumo profissional em até 3 linhas",
    "recommendation": "Altamente Recomendado" | "Recomendado" | "Parcialmente Recomendado" | "Não Recomendado",
    "potential_risks": "Possíveis riscos na contratação em 1-2 linhas"
}'''
        
        prompt = f"""
ANÁLISE DE CANDIDATO - ESPECIALISTA EM RECRUTAMENTO

Objetivo: extrair informações do candidato e classificar senioridade com regras rígidas.

**VAGA:**
- Cargo: {job_requirements.get('title', 'Não especificado')}
- Nível: {job_requirements.get('level', 'Não especificado')}
- Descrição: {job_requirements.get('description', 'Não especificado')}
- Skills Requeridas: {job_requirements.get('requirements', 'Não especificado')}

**CANDIDATO:**
Nome: {candidate_data.get('name', 'Não informado')}
Currículo/Perfil: {candidate_data.get('resume_text', 'Não informado')}

Retorne APENAS o JSON válido conforme template abaixo:

{json_template}
"""
        return prompt

    def _analyze_with_gemini(self, prompt):
        """Análise usando Google Gemini"""
        if not self.gemini_available:
            raise Exception("Gemini não disponível")
        
        try:
            model = genai.GenerativeModel(self.gemini_model)
            
            generation_config = {
                "temperature": 0.1,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2000,
            }
            
            gemini_prompt = f"""
{prompt}

IMPORTANTE: Retorne APENAS o JSON válido, sem nenhum texto adicional.
"""
            
            response = model.generate_content(
                gemini_prompt,
                generation_config=generation_config
            )
            
            if not response.parts:
                raise Exception("Resposta vazia do Gemini")
            
            return self._parse_ai_response(response.text)
            
        except Exception as e:
            print(f"❌ Erro com Gemini: {e}")
            raise e

    def _analyze_with_openai(self, prompt):
        """Análise usando OpenAI"""
        if not self.openai_available:
            raise Exception("OpenAI não disponível")
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Você é um especialista em análise de candidatos. Retorne apenas JSON válido."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            content = response.choices[0].message.content.strip()
            return self._parse_ai_response(content)
        except Exception as e:
            print(f"❌ Erro com OpenAI: {e}")
            raise e

    def _parse_ai_response(self, content):
        """Parseia a resposta da AI - MÉTODO QUE ESTAVA FALTANDO"""
        # Remove markdown se presente
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"❌ Erro ao fazer parse do JSON: {e}")
            # Tentar extrair JSON do texto
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
            raise e

    def _get_fallback_analysis(self):
        """Retorna análise padrão em caso de erro - MÉTODO QUE ESTAVA FALTANDO"""
        return {
            "contact_info": {
                "email": None,
                "phone": None,
                "linkedin": None
            },
            "extracted_skills": ["Análise manual necessária"],
            "seniority_detected": "Não detectado",
            "experience_years": 0,
            "experience_summary": "Erro ao processar. Análise manual recomendada.",
            "leadership_responsibilities": [],
            "complexity_indicators": [],
            "mentorship_indicators": [],
            "strengths": "Pendente de análise manual",
            "weaknesses": "Pendente de análise manual",
            "hard_skills_score": 5.0,
            "soft_skills_score": 5.0,
            "overall_score": 5.0,
            "professional_summary": "Erro na análise automática. Revisão manual necessária.",
            "recommendation": "Análise Manual Necessária",
            "potential_risks": "Análise automática falhou"
        }

    def get_current_provider(self):
        """Retorna qual provider está sendo usado atualmente"""
        return self.current_provider

    def is_any_ai_available(self):
        """Verifica se alguma API está disponível"""
        return self.gemini_available or self.openai_available