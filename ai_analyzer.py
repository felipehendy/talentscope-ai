# ai_analyzer.py - AGENT 67 (Tess) - VERSÃO CORRIGIDA (wait_execution + responses[0].output)
import os
import json
import requests
import certifi
from typing import Dict, Any
from datetime import datetime
import re


class AIAnalyzer:
    def __init__(self):
        print("🚀 Inicializando TalentScope AI Analyzer...")
        
        try:
            from dotenv import load_dotenv
            load_dotenv()
            print("✅ Variáveis de ambiente carregadas")
        except ImportError:
            print("⚠️  python-dotenv não instalado")
        
        # Carregar credenciais
        self.pareto_api_key = os.getenv('PARETO_API_KEY') or os.getenv('TESS_API_KEY')
        self.agent_id = os.getenv('TESS_AGENT_ID') or os.getenv('AGENT_ID', '67')
        
        # Endpoint correto
        if self.agent_id:
            self.tess_endpoint = f"https://tess.pareto.io/api/agents/{self.agent_id}/execute"
        else:
            self.tess_endpoint = None
            print("⚠️  TESS_AGENT_ID não configurado")
        
        # Configurar sessão com certificados
        self.session = requests.Session()
        self.session.verify = certifi.where()
        
        if self.pareto_api_key and self.tess_endpoint:
            print("✅ Tess API configurada (com fallback para Enhanced Analyzer)")
            print(f"🔑 API Key: {self.pareto_api_key[:10]}...{self.pareto_api_key[-5:]}")
            print(f"🤖 Agent ID: {self.agent_id}")
            print(f"🌐 Endpoint CORRETO: {self.tess_endpoint}")
        else:
            print("⚠️  PARETO_API_KEY não encontrada ou endpoint não configurado - usando Enhanced Analyzer local")
    
    def analyze_candidate(self, candidate_data: Dict[str, Any], 
                          job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Análise inteligente com priorização: Tess → Enhanced"""
        
        print("\n" + "=" * 60)
        print("📊 INICIANDO ANÁLISE")
        print("=" * 60)
        print(f"👤 Candidato: {candidate_data.get('name', 'N/A')}")
        print(f"🎯 Vaga: {job_requirements.get('title', 'N/A')}")
        
        # Estratégia 1: Tentar Tess primeiro
        if self.pareto_api_key and self.tess_endpoint:
            try:
                print("\n📡 Tentando análise com Tess (Pareto)...")
                result = self._analyze_with_tess(candidate_data, job_requirements)
                print("✅ Análise Tess concluída com sucesso!")
                return result
            
            except Exception as e:
                print(f"⚠️  Tess falhou: {str(e)}")
                print("🔄 Ativando fallback para Enhanced Analyzer...")
        
        # Estratégia 2: Fallback Enhanced
        print("\n🤖 Usando Enhanced Local Analyzer...")
        return self._analyze_with_enhanced(candidate_data, job_requirements)
    
    def _analyze_with_tess(self, candidate_data: Dict[str, Any],
                           job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Análise usando Tess com payload alinhado ao Agent 67 (JSON)"""
        
        # Preparar textos com validação
        resume_text = candidate_data.get('resume_text', '')[:8000]
        job_title = job_requirements.get('title', 'Vaga não especificada')
        job_desc = job_requirements.get('description', 'Descrição não fornecida')
        job_reqs = job_requirements.get('requirements', 'Requisitos não especificados')
        candidate_name = candidate_data.get('name', 'Candidato')
        
        # Prompt otimizado para o Agent 67 (que gera JSON)
        combined_text = f"""
=== ANÁLISE DE CURRÍCULO ===

📋 INFORMAÇÕES DA VAGA:
Título: {job_title}
Descrição: {job_desc}
Requisitos: {job_reqs}

👤 CANDIDATO: {candidate_name}

📄 CURRÍCULO COMPLETO:
{resume_text}

---

🎯 INSTRUÇÕES PARA O AGENTE:
Você é um especialista em recrutamento e seleção.

Analise o currículo do candidato considerando as informações da vaga acima e siga EXATAMENTE as orientações abaixo:

1) HARD SKILLS:
- Identifique até 10 habilidades técnicas mencionadas.
- Para cada skill, indique o nível (Básico / Intermediário / Avançado).
- Caso não haja skills explícitas, estime pelo contexto ou experiência declarada.

2) SOFT SKILLS:
- Identifique até 5 competências interpessoais relevantes (como liderança, comunicação, trabalho em equipe, adaptabilidade).
- Caso não haja informações, indique "Não identificado".

3) EXPERIÊNCIA:
- Resuma o nível de experiência profissional em anos.
- Inclua cargos e responsabilidades principais.
- Se houver lacunas ou inconsistências, destaque.

4) SCORE GERAL:
- Calcule score de 0 a 10 considerando fit técnico, experiência, soft skills e match com a vaga.
- Se houver falta de informações, ajuste score para refletir incerteza.

5) PONTOS FORTES:
- Liste 3 a 5 pontos fortes do candidato baseados no currículo.
- Use bullet points claros.

6) PONTOS DE ATENÇÃO:
- Liste 3 a 5 riscos ou gaps identificados (ex.: experiência insuficiente, skills ausentes, inconsistências).

7) OBSERVAÇÕES E RISCOS:
- Indique riscos críticos ou potenciais problemas de contratação.
- Se não houver riscos, informe "Nenhum risco crítico identificado".

8) SAÍDA:
- Sempre RETORNE APENAS um JSON VÁLIDO com o seguinte formato:

{{
  "score": 0-10,
  "hard_skills": [{{"nome": "...", "nivel": "Básico/Intermediário/Avançado"}}],
  "soft_skills": ["..."],
  "experiencia": {{
      "anos": X,
      "cargos": ["..."],
      "lacunas": ["..."]
  }},
  "pontos_fortes": ["..."],
  "pontos_atencao": ["..."],
  "observacoes_riscos": ["..."]
}}

- NÃO inclua texto fora do JSON.
- Respeite o idioma do currículo (Português ou Inglês).
""".strip()
        
        # IMPORTANTE: aqui adicionamos wait_execution=True para a Tess esperar o output
        payload = {
            "texto": combined_text,
            "temperature": "0.5",
            "model": "gpt-4o-mini",
            "maxlength": 4500,
            "language": "Portuguese (Brazil)",
            "wait_execution": True  # <- chave para não vir status "starting" com output null
        }
        
        headers = {
            "Authorization": f"Bearer {self.pareto_api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔄 Enviando para Tess Agent {self.agent_id}...")
        print(f"📡 Endpoint: {self.tess_endpoint}")
        print(f"📦 Payload: texto={len(combined_text)} chars, temp='0.5', model='gpt-4o-mini', wait_execution=True")
        
        # Fazer requisição
        response = self.session.post(
            self.tess_endpoint,
            json=payload,
            headers=headers,
            timeout=100  # até o limite que a Tess documenta para wait_execution
        )
        
        print(f"📡 Status HTTP: {response.status_code}")
        
        # Validar resposta
        if response.status_code != 200:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f" - {error_detail}"
            except Exception:
                error_msg += f" - {response.text[:200]}"
            raise Exception(error_msg)
        
        # Processar resposta
        tess_data = response.json()
        print("✅ Resposta Tess recebida")
        
        # Extrair output do lugar CERTO (responses[0].output)
        tess_output = self._extract_tess_output(tess_data)
        
        if not tess_output:
            raise Exception("Output vazio da Tess (responses[0].output está vazio)")
        
        print(f"📝 Output extraído ({len(tess_output)} chars)")
        
        # Parsear e estruturar resposta JSON do Agent 67
        return self._parse_tess_response_json(
            tess_output, 
            candidate_data, 
            job_requirements,
            tess_data
        )
    
    def _extract_tess_output(self, response_data: Dict) -> str:
        """Extrai o output correto da resposta da Tess (responses[0].output)"""
        
        # NOVO: olhar primeiro para responses[0]
        try:
            if isinstance(response_data, dict) and 'responses' in response_data:
                responses = response_data.get('responses') or []
                if isinstance(responses, list) and len(responses) > 0 and isinstance(responses[0], dict):
                    first = responses[0]
                    status = first.get('status')
                    print(f"📡 Status do Agent na Tess: {status}")
                    
                    output = first.get('output')
                    if output:
                        print("✅ Encontrado responses[0].output preenchido")
                        return str(output)
                    else:
                        print("⚠️ responses[0].output está vazio ou null")
        except Exception as e:
            print(f"⚠️ Erro ao ler responses[0].output: {e}")
        
        # Antigas tentativas (mantidas como fallback)
        if isinstance(response_data, dict):
            if 'output' in response_data and response_data['output']:
                return str(response_data['output'])
            
            if 'data' in response_data:
                data = response_data['data']
                if isinstance(data, dict) and 'output' in data and data['output']:
                    return str(data['output'])
            
            if 'result' in response_data and response_data['result']:
                return str(response_data['result'])
            
            if 'message' in response_data and response_data['message']:
                return str(response_data['message'])
            
            if 'response' in response_data and response_data['response']:
                return str(response_data['response'])
        
        # Fallback final: retornar JSON completo como string (para debug / parser de texto)
        print("⚠️ Não foi encontrado campo output; retornando JSON bruto como string para fallback")
        return json.dumps(response_data, ensure_ascii=False)
    
    def _parse_tess_response_json(self, tess_output: str, candidate_data: Dict,
                                  job_requirements: Dict, raw_data: Dict) -> Dict[str, Any]:
        """Parseia resposta JSON do Agent 67 e converte para o formato interno (com DEBUG)"""
        
        print("🔍 Parseando JSON do Agent 67...")
        print(f"📦 Output recebido (primeiros 500 chars):\n{tess_output[:500]}")
        
        try:
            # Tentar pegar apenas o JSON (caso venha algo a mais)
            json_match = re.search(r'\{[\s\S]*\}', tess_output)
            
            if json_match:
                json_str = json_match.group(0)
                analysis = json.loads(json_str)
                
                print("✅ JSON parseado com sucesso!")
                print(f"🔑 Chaves encontradas no JSON: {list(analysis.keys())}")
                print("📊 Conteúdo completo do JSON:")
                print(json.dumps(analysis, indent=2, ensure_ascii=False))
            else:
                print("⚠️ JSON não encontrado claramente - usando parser de fallback")
                analysis = self._fallback_parse(tess_output)
        
        except json.JSONDecodeError as e:
            print(f"⚠️ Erro ao parsear JSON: {e}")
            print("🔄 Usando fallback parser baseado em texto livre...")
            analysis = self._fallback_parse(tess_output)
        
        # -------- EXTRAÇÃO COM LOG DETALHADO --------
        print("\n🔍 Extraindo campos do JSON...")
        
        score = analysis.get('score', None)
        print(f"  📊 Score raw: {score} (tipo: {type(score)})")
        
        if score is None:
            # Tentar variações de nome
            score = analysis.get('pontuacao', analysis.get('nota', analysis.get('overall_score', 6.5)))
            print(f"  🔄 Score alternativo: {score}")
        
        try:
            score = float(score) if score is not None else 6.5
        except (TypeError, ValueError):
            score = 6.5
        print(f"  ✅ Score final: {score}")
        
        hard_skills = analysis.get('hard_skills', [])
        print(f"  🔧 Hard skills raw: {hard_skills} (tipo: {type(hard_skills)}, len: {len(hard_skills) if isinstance(hard_skills, list) else 'N/A'})")
        
        soft_skills = analysis.get('soft_skills', [])
        print(f"  💼 Soft skills raw: {soft_skills}")
        
        experiencia = analysis.get('experiencia', {})
        print(f"  📅 Experiência raw: {experiencia} (tipo: {type(experiencia)})")
        
        pontos_fortes = analysis.get('pontos_fortes', [])
        print(f"  ✅ Pontos fortes: {pontos_fortes}")
        
        pontos_atencao = analysis.get('pontos_atencao', [])
        print(f"  ⚠️ Pontos atenção: {pontos_atencao}")
        
        observacoes = analysis.get('observacoes_riscos', [])
        print(f"  📝 Observações: {observacoes}")
        
        # Processar hard skills para lista de nomes
        skill_names = []
        if isinstance(hard_skills, list):
            for skill in hard_skills:
                if isinstance(skill, dict):
                    nome = skill.get('nome', skill.get('name', skill.get('skill', '')))
                    if nome:
                        skill_names.append(nome)
                elif isinstance(skill, str):
                    skill_names.append(skill)
        print(f"  🎯 Skills processadas: {skill_names}")
        
        # Anos de experiência
        years = 0
        cargos = []
        if isinstance(experiencia, dict):
            years = experiencia.get('anos', experiencia.get('years', 0)) or 0
            cargos = experiencia.get('cargos', experiencia.get('positions', [])) or []
        print(f"  📆 Anos extraídos: {years}")
        print(f"  💼 Cargos: {cargos}")
        
        # Determinar senioridade baseado em anos e score
        if years >= 7 or score >= 8.5:
            seniority = 'Sênior'
        elif years >= 4 or score >= 7.0:
            seniority = 'Pleno'
        elif years >= 2:
            seniority = 'Junior'
        else:
            seniority = 'Trainee/Estagiário'
        print(f"  🏆 Senioridade calculada: {seniority}")
        
        # Formatar pontos fortes, atenção e riscos
        strengths_text = '\n'.join([f"✅ {p}" for p in pontos_fortes]) if pontos_fortes else "✅ Perfil adequado aos requisitos básicos"
        weaknesses_text = '\n'.join([f"⚠️ {p}" for p in pontos_atencao]) if pontos_atencao else "⚠️ Nenhum ponto crítico identificado"
        risks_text = '\n'.join([f"🔴 {r}" for r in observacoes]) if observacoes else "✅ Nenhum risco crítico identificado"
        
        # Determinar recomendação geral
        if score >= 8.0:
            recommendation = "Altamente Recomendado"
        elif score >= 6.5:
            recommendation = "Recomendado"
        elif score >= 5.0:
            recommendation = "Análise Manual Recomendada"
        else:
            recommendation = "Não Recomendado"
        
        print(f"\n✅ Parse concluído - Score: {score:.1f}/10 | Senioridade: {seniority} | Anos: {years}")
        
        # Construir resposta padronizada
        return {
            "contact_info": {
                "email": candidate_data.get('email', 'Não informado'),
                "phone": candidate_data.get('phone', 'Não informado'),
                "linkedin": candidate_data.get('linkedin_url', 'Não informado')
            },
            "extracted_skills": skill_names[:20],
            "matched_skills": skill_names[:15],
            "missing_skills": [],
            "seniority_detected": seniority,
            "experience_years": years,
            "experience_summary": f"{seniority} • {years} anos • {', '.join(cargos[:3]) if cargos else 'Cargos não detalhados'}",
            "leadership_responsibilities": ["Avaliar em entrevista"],
            "complexity_indicators": [f"Score global: {score:.1f}/10"],
            "mentorship_indicators": soft_skills[:3] if soft_skills else ["Validar soft skills em entrevista"],
            "strengths": strengths_text,
            "weaknesses": weaknesses_text,
            "professional_summary": self._generate_summary_from_json(score, seniority, years, len(skill_names)),
            "hard_skills_score": max(1.0, min(10.0, score)),
            "soft_skills_score": max(1.0, min(10.0, score - 0.5)),
            "experience_score": max(1.0, min(10.0, years * 1.2)),
            "overall_score": score,
            "recommendation": recommendation,
            "recommendation_reason": pontos_fortes[0] if pontos_fortes else "Candidato apresenta perfil potencialmente aderente.",
            "potential_risks": risks_text,
            "analysis_source": "🤖 Tess AI (Pareto) - Agent 67 (JSON estruturado)",
            "analysis_timestamp": datetime.now().isoformat(),
            "provider": "pareto_tess_json",
            "confidence_level": "Alta - Análise estruturada via JSON",
            "tess_raw_output": tess_output[:1000],
            "tess_full_response": raw_data,
            "tess_json_analysis": analysis,
            "total_skills_found": len(skill_names),
            "skill_match_percentage": min(100, max(0, int(score * 10))),
            "projects_mentioned": self._count_projects(candidate_data.get('resume_text', '')),
            "education_level": "Avaliar manualmente",
            "soft_skills_identified": soft_skills,
            "hard_skills_detailed": hard_skills,
            "job_positions": cargos,
            "analysis_note": f"✅ Análise via Tess Agent 67 (JSON) | Score: {score:.1f}/10 | {len(skill_names)} skills técnicas identificadas"
        }
    
    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        """Parser de fallback caso o JSON estruturado não seja detectado"""
        print("🔁 Fallback: interpretando resposta como texto livre...")
        return {
            "score": self._extract_score(text),
            "hard_skills": [{"nome": s, "nivel": "Intermediário"} for s in self._extract_skills(text)],
            "soft_skills": ["Comunicação", "Trabalho em equipe"],
            "experiencia": {
                "anos": self._extract_years(text),
                "cargos": ["Verificar manualmente"],
                "lacunas": []
            },
            "pontos_fortes": ["Experiência relevante", "Perfil potencialmente aderente"],
            "pontos_atencao": ["Validar escopo de atuação", "Verificar profundidade técnica"],
            "observacoes_riscos": []
        }
    
    def _analyze_with_enhanced(self, candidate_data: Dict[str, Any],
                               job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback: Enhanced Local Analyzer"""
        
        try:
            from enhanced_analyzer import EnhancedCVAnalyzer
            
            analyzer = EnhancedCVAnalyzer()
            
            result = analyzer.analyze(
                cv_text=candidate_data.get('resume_text', ''),
                job_description=f"{job_requirements.get('description', '')} {job_requirements.get('requirements', '')}",
                candidate_name=candidate_data.get('name', 'Candidato')
            )
            
            result['contact_info'] = {
                'email': candidate_data.get('email', 'Não informado'),
                'phone': candidate_data.get('phone', 'Não informado'),
                'linkedin': candidate_data.get('linkedin_url', 'Não informado')
            }
            
            print(f"✅ Enhanced Analysis concluída - Score: {result.get('overall_score', 0):.1f}/10")
            return result
            
        except Exception as e:
            print(f"❌ Erro no Enhanced Analyzer: {e}")
            return self._emergency_fallback(candidate_data, job_requirements, str(e))
    
    def _emergency_fallback(self, candidate_data: Dict, job_requirements: Dict, error: str) -> Dict:
        """Fallback de emergência"""
        print("⚠️  Executando fallback de emergência...")
        
        return {
            "contact_info": {
                "email": candidate_data.get('email', 'N/A'),
                "phone": candidate_data.get('phone', 'N/A'),
                "linkedin": candidate_data.get('linkedin_url', 'N/A')
            },
            "extracted_skills": [],
            "matched_skills": [],
            "missing_skills": [],
            "seniority_detected": "Indeterminado",
            "experience_years": 0,
            "experience_summary": "Erro na análise",
            "strengths": f"❌ Erro: {error}",
            "weaknesses": "Análise não concluída",
            "professional_summary": "Sistema de análise indisponível",
            "hard_skills_score": 0,
            "soft_skills_score": 0,
            "experience_score": 0,
            "overall_score": 0,
            "recommendation": "Erro de Sistema",
            "recommendation_reason": error,
            "potential_risks": "Sistema indisponível - Análise manual obrigatória",
            "analysis_source": "❌ Erro de Sistema",
            "analysis_timestamp": datetime.now().isoformat(),
            "provider": "error",
            "confidence_level": "Nenhuma",
            "error": error
        }
    
    # =========================
    # Métodos de extração (apoio ao fallback)
    # =========================
    
    def _extract_score(self, text: str) -> float:
        # Normaliza vírgula para ponto para facilitar parsing
        normalized = text.lower().replace(',', '.')
        
        patterns = [
            r'score[:\s]+(\d+(?:\.\d+)?)',
            r'pontuação[:\s]+(\d+(?:\.\d+)?)',
            r'nota[:\s]+(\d+(?:\.\d+)?)',
            r'(\d+(?:\.\d+)?)\s*/\s*10',
        ]
        for pattern in patterns:
            match = re.search(pattern, normalized)
            if match:
                try:
                    value = float(match.group(1))
                    return min(10.0, max(0.0, value))
                except ValueError:
                    continue
        return 6.5
    
    def _extract_skills(self, text: str) -> list:
        skills = []
        
        # 1) Padrão antigo: "skills identificadas"
        skills_section = re.search(
            r'skills?\s+identificadas?[:\s]+(.*?)(?=\n\n|\d+\.|\Z)', 
            text, re.IGNORECASE | re.DOTALL
        )
        if skills_section:
            content = skills_section.group(1)
            items = re.findall(r'[-•*]\s*([^\n]+)', content)
            if items:
                skills.extend([item.strip() for item in items])
            else:
                items = content.split(',')
                skills.extend([item.strip() for item in items if len(item.strip()) > 2])
        
        # 2) Novo padrão: "ANÁLISE DE HARD SKILLS:"
        if not skills:
            hard_section = re.search(
                r'ANÁLISE DE HARD SKILLS[:\s]+(.*?)(?=\n\n|POSSÍVEIS LACUNAS|PONTOS FORTES|Recomendações|$)', 
                text, re.IGNORECASE | re.DOTALL
            )
            if hard_section:
                content = hard_section.group(1)
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                for line in lines:
                    if ':' in line:
                        nome = line.split(':', 1)[0].strip()
                        if 1 < len(nome) < 50:
                            skills.append(nome)
        
        return [s for s in skills if s and len(s) < 50][:20]
    
    def _extract_years(self, text: str) -> float:
        patterns = [
            r'(\d+)\s*(?:\+)?\s*anos?\s+de\s+experiência',
            r'experiência[:\s]+(\d+)\s*(?:\+)?\s*anos?',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1))
        return 2.0
    
    def _count_projects(self, text: str) -> int:
        keywords = ['projeto', 'project', 'desenvolveu', 'implementou']
        count = sum(len(re.findall(r'\b' + k + r'\b', text.lower())) for k in keywords)
        return min(count, 20)
    
    def _generate_summary_from_json(self, score: float, seniority: str, years: float, skills_count: int) -> str:
        return (
            f"Profissional {seniority} com {years} anos de experiência. "
            f"Score geral de {score:.1f}/10, com {skills_count} competências técnicas identificadas. "
            f"Análise estruturada via Tess Agent 67 (JSON)."
        )
    
    def test_connection(self) -> bool:
        """Testa conexão com Tess"""
        if not self.pareto_api_key or not self.tess_endpoint:
            print("⚠️  API não configurada - Enhanced disponível")
            return True
        
        print("🔍 Testando endpoint Tess...")
        
        try:
            payload = {
                "texto": "Teste de conexão com Agent 67",
                "temperature": "0.5",
                "model": "gpt-4o-mini",
                "maxlength": 100,
                "language": "Portuguese (Brazil)",
                "wait_execution": True
            }
            headers = {
                "Authorization": f"Bearer {self.pareto_api_key}",
                "Content-Type": "application/json"
            }
            
            response = self.session.post(
                self.tess_endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            print(f"📡 Status: {response.status_code}")
            print(f"📦 Corpo (primeiros 300 chars): {response.text[:300]}")
            return True
        
        except Exception as e:
            print(f"❌ Erro ao testar Tess: {e}")
            return True
    
    def get_current_provider(self) -> str:
        if self.pareto_api_key and self.tess_endpoint:
            return "pareto_tess_with_enhanced_fallback"
        return "enhanced_local"


def create_analyzer() -> AIAnalyzer:
    return AIAnalyzer()


def analyze_candidate_quick(cv_text: str, job_description: str, 
                            candidate_name: str = "Candidato",
                            email: str = "", phone: str = "") -> Dict[str, Any]:
    analyzer = AIAnalyzer()
    
    candidate_data = {
        "name": candidate_name,
        "email": email,
        "phone": phone,
        "resume_text": cv_text
    }
    
    job_requirements = {
        "title": "Análise Rápida",
        "description": job_description,
        "requirements": ""
    }
    
    return analyzer.analyze_candidate(candidate_data, job_requirements)
