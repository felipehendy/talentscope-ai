"""
TalentScope AI - Chatbot Service (Versão Inteligente)
Sistema de análise profunda com cálculos automáticos e respostas contextuais
"""

import os
import re
import requests
import certifi
from typing import List, Dict, Any


class TessResponse:
    """Classe de resposta compatível com app.py"""
    def __init__(self, success, content, metadata=None, error=None):
        self.success = success
        self.content = content
        self.metadata = metadata or {}
        self.error = error


class TessChatbotService:
    def __init__(self):
        """Inicializa o serviço com credenciais"""
        self.pareto_api_key = os.getenv('PARETO_API_KEY') or os.getenv('TESS_API_KEY')
        self.agent_id = os.getenv('TESS_AGENT_ID') or os.getenv('AGENT_ID', '67')
        
        if self.agent_id:
            self.tess_endpoint = f"https://tess.pareto.io/api/agents/{self.agent_id}/execute"
        else:
            self.tess_endpoint = None
        
        self.session = requests.Session()
        self.session.verify = certifi.where()
        
        print(f"🤖 Chatbot Inteligente inicializado - Agent ID: {self.agent_id}")
    
    def process_query(self, candidates, jobs, user_query, **kwargs):
        """
        Método principal compatível com app.py
        Processa query do usuário e retorna objeto TessResponse
        """
        try:
            # Construir prompt inteligente
            prompt = self.build_prompt(candidates, jobs, user_query)
            
            # Chamar Tess
            response_text = self.call_tess(prompt)
            
            # Retornar objeto compatível com app.py
            return TessResponse(
                success=True,
                content=response_text,
                metadata={
                    "candidates_count": len(candidates),
                    "jobs_count": len(jobs),
                    "prompt_length": len(prompt)
                }
            )
            
        except Exception as e:
            print(f"❌ Erro no process_query: {e}")
            import traceback
            traceback.print_exc()
            return TessResponse(
                success=False,
                content=f"❌ Erro ao processar: {str(e)}",
                error=str(e)
            )
    
    def build_prompt(self, candidates_context, jobs_context, user_query):
        """Constrói prompt ULTRA-INTELIGENTE com análises profundas"""
        
        # Calcular métricas avançadas automaticamente
        metrics = self._calculate_advanced_metrics(candidates_context, jobs_context)
        
        # Formatar candidatos com análise detalhada
        candidates_text = self._format_candidates_detailed(candidates_context, jobs_context)
        
        # Formatar vagas com análise de demanda
        jobs_text = self._format_jobs_detailed(jobs_context, candidates_context)
        
        # Detectar tipo de pergunta
        question_type = self._detect_question_type(user_query)
        
        # Construir instruções específicas por tipo
        specific_instructions = self._get_specific_instructions(question_type, metrics)
        
        prompt = f"""# SISTEMA DE ANÁLISE INTELIGENTE DE TALENTOS

## DADOS CONSOLIDADOS DO SISTEMA

### MÉTRICAS GERAIS CALCULADAS:
{metrics['summary']}

### CANDIDATOS ANALISADOS ({len(candidates_context)}):
{candidates_text}

### VAGAS DISPONÍVEIS ({len(jobs_context)}):
{jobs_text}

{specific_instructions}

## REGRAS CRÍTICAS DE ANÁLISE:

1. **PROFUNDIDADE OBRIGATÓRIA**: Não responda superficialmente. Analise:
   - Scores (quantitativos)
   - Skills (match técnico)
   - Senioridade (alinhamento de nível)
   - Gaps e oportunidades

2. **CÁLCULOS OBRIGATÓRIOS** quando aplicável:
   - Percentual de match (skills do candidato vs skills da vaga)
   - Ranking comparativo entre candidatos
   - Análise de gaps (skills ausentes)
   - Score ponderado (hard skills 60% + soft skills 40%)

3. **FORMATO DA RESPOSTA**:
   - Use tabelas para comparações
   - Apresente números e percentuais
   - Justifique TODA recomendação com dados
   - Conclua com ação sugerida

4. **PROIBIDO**:
   - Respostas genéricas ("candidatos disponíveis")
   - Propaganda comercial
   - Informações inventadas
   - Listas simples sem análise

## PERGUNTA DO USUÁRIO:
{user_query}

## SUA ANÁLISE PROFUNDA E FUNDAMENTADA:"""
        
        return prompt
    
    def _calculate_advanced_metrics(self, candidates, jobs):
        """Calcula métricas avançadas do sistema"""
        if not candidates:
            return {"summary": "Sem candidatos para análise"}
        
        # Scores médios
        avg_overall = sum(c.get('score_geral', 0) for c in candidates) / len(candidates)
        avg_hard = sum(c.get('score_hard_skills', 0) for c in candidates) / len(candidates)
        avg_soft = sum(c.get('score_soft_skills', 0) for c in candidates) / len(candidates)
        
        # Candidatos por faixa
        high_performers = sum(1 for c in candidates if c.get('score_geral', 0) >= 8)
        mid_performers = sum(1 for c in candidates if 6 <= c.get('score_geral', 0) < 8)
        low_performers = sum(1 for c in candidates if c.get('score_geral', 0) < 6)
        
        # Senioridade
        seniority_dist = {}
        for c in candidates:
            sen = c.get('senioridade', 'Não detectado')
            seniority_dist[sen] = seniority_dist.get(sen, 0) + 1
        
        summary = f"""
- Score Médio Geral: {avg_overall:.1f}/10
- Score Médio Hard Skills: {avg_hard:.1f}/10
- Score Médio Soft Skills: {avg_soft:.1f}/10
- Candidatos de Alto Desempenho (≥8): {high_performers} ({high_performers/len(candidates)*100:.0f}%)
- Candidatos de Médio Desempenho (6-8): {mid_performers} ({mid_performers/len(candidates)*100:.0f}%)
- Candidatos Abaixo da Média (<6): {low_performers} ({low_performers/len(candidates)*100:.0f}%)
- Distribuição de Senioridade: {', '.join(f'{k}: {v}' for k, v in seniority_dist.items())}"""
        
        return {
            "summary": summary,
            "avg_overall": avg_overall,
            "avg_hard": avg_hard,
            "avg_soft": avg_soft,
            "high_performers": high_performers,
            "seniority_dist": seniority_dist
        }
    
    def _format_candidates_detailed(self, candidates, jobs):
        """Formata candidatos com análise detalhada"""
        formatted = []
        
        for c in candidates:
            # Calcular score ponderado
            weighted_score = (c.get('score_hard_skills', 0) * 0.6 + 
                            c.get('score_soft_skills', 0) * 0.4)
            
            # Extrair skills como lista
            skills_str = c.get('skills_extraidas', '')
            if skills_str:
                skills_list = [s.strip() for s in skills_str.split(',')[:5]]
                skills_formatted = ', '.join(skills_list)
            else:
                skills_formatted = 'Não informado'
            
            # Análise de gap (comparar com vaga)
            vaga_aplicada = c.get('vaga_aplicada', '')
            job_match = next((j for j in jobs if j.get('titulo') == vaga_aplicada), None)
            
            gap_analysis = "N/A"
            if job_match:
                required_skills = job_match.get('skills_requeridas', '').lower()
                candidate_skills_lower = skills_str.lower()
                
                # Calcular match simplificado
                if required_skills:
                    req_skills_list = [s.strip() for s in required_skills.split(',')]
                    matches = sum(1 for rs in req_skills_list if rs in candidate_skills_lower)
                    match_pct = (matches / len(req_skills_list) * 100) if req_skills_list else 0
                    gap_analysis = f"{match_pct:.0f}% de match com vaga"
            
            formatted_text = f"""**{c.get('name', 'N/A')}** (ID: {c.get('id')})
- Vaga Aplicada: {vaga_aplicada}
- Senioridade: {c.get('senioridade', 'N/A')}
- Score Geral: {c.get('score_geral', 0)}/10 | Score Ponderado: {weighted_score:.1f}/10
- Hard Skills: {c.get('score_hard_skills', 0)}/10 | Soft Skills: {c.get('score_soft_skills', 0)}/10
- Principais Competências: {skills_formatted}
- Match com Vaga: {gap_analysis}
- Recomendação: {c.get('recomendacao', 'N/A')}
- Pontos Fortes: {c.get('pontos_fortes', 'N/A')[:100]}...
- Pontos de Atenção: {c.get('pontos_atencao', 'N/A')[:100]}..."""
            
            formatted.append(formatted_text)
        
        return "\n\n".join(formatted)
    
    def _format_jobs_detailed(self, jobs, candidates):
        """Formata vagas com análise de demanda"""
        formatted = []
        
        for j in jobs:
            job_title = j.get('titulo', 'N/A')
            
            # Contar candidatos para esta vaga
            candidates_for_job = [c for c in candidates 
                                 if str(c.get('vaga_aplicada', '')) == str(job_title)]
            
            # Calcular score médio dos candidatos
            if candidates_for_job:
                avg_score = sum(c.get('score_geral', 0) for c in candidates_for_job) / len(candidates_for_job)
                top_candidate = max(candidates_for_job, key=lambda x: x.get('score_geral', 0))
                top_candidate_name = top_candidate.get('name', 'N/A')
                top_candidate_score = top_candidate.get('score_geral', 0)
            else:
                avg_score = 0
                top_candidate_name = "Nenhum"
                top_candidate_score = 0
            
            formatted_text = f"""**{job_title}** (ID: {j.get('id')})
- Nível: {j.get('nivel', 'N/A')}
- Candidatos Inscritos: {len(candidates_for_job)}
- Score Médio dos Candidatos: {avg_score:.1f}/10
- Melhor Candidato: {top_candidate_name} (Score: {top_candidate_score}/10)
- Skills Requeridas: {j.get('skills_requeridas', 'N/A')[:150]}...
- Descrição: {j.get('descricao', 'N/A')[:150]}..."""
            
            formatted.append(formatted_text)
        
        return "\n\n".join(formatted)
    
    def _detect_question_type(self, query):
        """Detecta o tipo de pergunta para instruções específicas"""
        query_lower = query.lower()
        
        # Saudação
        if any(word in query_lower for word in ['olá', 'oi', 'bom dia', 'boa tarde', 'hey']):
            if len(query_lower.split()) < 5:
                return 'greeting'
        
        # Comparação
        if any(word in query_lower for word in ['compare', 'comparar', 'vs', 'versus', 'diferença']):
            return 'comparison'
        
        # Ranking
        if any(word in query_lower for word in ['melhor', 'top', 'ranking', 'melhores', 'classificar']):
            return 'ranking'
        
        # Match com vaga
        if any(word in query_lower for word in ['adequado', 'recomende', 'sugira', 'para a vaga', 'qual vaga']):
            return 'job_match'
        
        # Análise individual
        if any(word in query_lower for word in ['sobre', 'perfil', 'detalhes', 'informações sobre']):
            return 'individual_analysis'
        
        # Estatísticas
        if any(word in query_lower for word in ['quantos', 'quantas', 'estatística', 'média', 'total']):
            return 'statistics'
        
        return 'general'
    
    def _get_specific_instructions(self, question_type, metrics):
        """Retorna instruções específicas por tipo de pergunta"""
        
        if question_type == 'greeting':
            return """
## INSTRUÇÃO PARA SAUDAÇÃO:
Responda de forma profissional e objetiva, apresentando:
1. Resumo executivo das métricas gerais (use os dados calculados)
2. Destaques: top 3 candidatos por score
3. Status das vagas (qual tem mais/menos candidatos)
4. Sugestões de 3 perguntas úteis que o usuário pode fazer

NÃO faça propaganda. Seja objetivo e analítico."""
        
        elif question_type == 'comparison':
            return """
## INSTRUÇÃO PARA COMPARAÇÃO:
OBRIGATÓRIO criar uma tabela comparativa com:
- Scores lado a lado (geral, hard, soft)
- Skills em comum e exclusivas
- Análise de gaps específicos
- Recomendação fundamentada com percentuais
- Vencedor da comparação com justificativa quantitativa"""
        
        elif question_type == 'ranking':
            return """
## INSTRUÇÃO PARA RANKING:
OBRIGATÓRIO criar ranking ordenado com:
1. Posição (1º, 2º, 3º...)
2. Nome, score geral e score ponderado
3. Justificativa da posição com dados concretos
4. Percentual de diferença entre posições
5. Análise do gap entre 1º e último"""
        
        elif question_type == 'job_match':
            return """
## INSTRUÇÃO PARA MATCH COM VAGA:
OBRIGATÓRIO calcular:
- % de match de skills (candidato vs vaga)
- Score ponderado considerando senioridade
- Lista de skills presentes e ausentes
- Ranking dos top 3 candidatos com percentuais
- Recomendação final com justificativa"""
        
        elif question_type == 'individual_analysis':
            return """
## INSTRUÇÃO PARA ANÁLISE INDIVIDUAL:
OBRIGATÓRIO incluir:
1. Resumo do perfil (senioridade, score, skills)
2. Análise comparativa com a média do sistema
3. Pontos fortes (top 3) e fracos (top 3)
4. Vaga mais adequada com % de match
5. Plano de desenvolvimento (gaps a melhorar)"""
        
        elif question_type == 'statistics':
            return """
## INSTRUÇÃO PARA ESTATÍSTICAS:
OBRIGATÓRIO apresentar:
- Números absolutos e percentuais
- Médias, distribuições
- Comparações entre grupos
- Insights acionáveis baseados nos números
- Recomendações baseadas nas estatísticas"""
        
        else:
            return """
## INSTRUÇÃO GERAL:
Analise profundamente os dados fornecidos e responda com:
- Dados quantitativos (scores, percentuais)
- Comparações quando relevante
- Recomendações fundamentadas em números
- Próximos passos sugeridos"""
    
    def call_tess(self, prompt):
        """Chama a API da Tess"""
        
        if not self.pareto_api_key or not self.tess_endpoint:
            return "❌ API não configurada"
        
        payload = {
            "texto": prompt[:15000],
            "temperature": "0.5",
            "model": "gpt-4o-mini",
            "maxlength": 4000,
            "language": "Portuguese (Brazil)",
            "wait_execution": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.pareto_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            print(f"🔄 Chamando Tess Agent {self.agent_id}...")
            
            response = self.session.post(
                self.tess_endpoint,
                json=payload,
                headers=headers,
                timeout=60
            )
            
            print(f"📡 Status HTTP: {response.status_code}")
            
            if response.status_code != 200:
                try:
                    error_detail = response.json()
                    print(f"⚠️ Erro da API: {error_detail}")
                except:
                    error_detail = response.text[:300]
                    print(f"⚠️ Erro da API: {error_detail}")
                
                return f"❌ Erro HTTP {response.status_code}: A API retornou um erro."
            
            tess_data = response.json()
            output = self._extract_tess_output(tess_data)
            
            if not output:
                return "⚠️ Resposta vazia da Tess"
            
            # Pós-processar para remover propaganda
            output = self._clean_propaganda(output)
            
            print(f"✅ Resposta recebida ({len(output)} caracteres)")
            return output
            
        except requests.exceptions.Timeout:
            return "⏱️ Timeout. Tente novamente."
        
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()
            return f"❌ Erro ao processar: {str(e)}"
    
    def _extract_tess_output(self, response_data):
        """Extrai output da resposta"""
        try:
            if isinstance(response_data, dict) and 'responses' in response_data:
                responses = response_data.get('responses') or []
                if isinstance(responses, list) and len(responses) > 0:
                    first = responses[0]
                    output = first.get('output')
                    if output:
                        return str(output)
        except Exception as e:
            print(f"⚠️ Erro ao ler output: {e}")
        
        if isinstance(response_data, dict):
            for key in ['output', 'result', 'message', 'response']:
                if key in response_data and response_data[key]:
                    return str(response_data[key])
        
        return str(response_data)
    
    def _clean_propaganda(self, text):
        """Remove propaganda comercial da resposta"""
        propaganda_patterns = [
            r'🚀.*?construir um time.*?\n',
            r'Vamos juntos.*?\n',
            r'Se você conhece alguém.*?\n',
            r'#\w+\s*',
            r'Na TalentScope.*?\n',
            r'Descubra.*?potencial.*?\n',
            r'Entre em contato.*?\n',
            r'revolucionando.*?\n'
        ]
        
        cleaned = text
        for pattern in propaganda_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        
        cleaned = re.sub(r'\n\s*\n\s*\n+', '\n\n', cleaned)
        
        return cleaned.strip()