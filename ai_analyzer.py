# ai_analyzer.py - VERSÃO OTIMIZADA E MELHORADA
import os
import json
import requests
import certifi
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import re
from dataclasses import dataclass
from enum import Enum
import logging

# ==================== CONFIGURAÇÃO DE LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== ENUMS E DATACLASSES ====================
class AnalysisProvider(Enum):
    """Provedores de análise disponíveis"""
    TESS_PARETO = "pareto_tess_json"
    ENHANCED_LOCAL = "enhanced_local"
    EMERGENCY_FALLBACK = "error"


class Recommendation(Enum):
    """Níveis de recomendação"""
    HIGHLY_RECOMMENDED = "Altamente Recomendado"
    RECOMMENDED = "Recomendado"
    MANUAL_REVIEW = "Análise Manual Recomendada"
    NOT_RECOMMENDED = "Não Recomendado"
    SYSTEM_ERROR = "Erro de Sistema"


class SeniorityLevel(Enum):
    """Níveis de senioridade"""
    SENIOR = "Sênior"
    PLENO = "Pleno"
    JUNIOR = "Junior"
    TRAINEE = "Trainee/Estagiário"
    UNDETERMINED = "Indeterminado"


@dataclass
class ContactInfo:
    """Informações de contato do candidato"""
    email: str = "Não informado"
    phone: str = "Não informado"
    linkedin: str = "Não informado"


@dataclass
class Experience:
    """Experiência profissional"""
    years: float = 0.0
    positions: List[str] = None
    gaps: List[str] = None
    
    def __post_init__(self):
        if self.positions is None:
            self.positions = []
        if self.gaps is None:
            self.gaps = []


@dataclass
class Skill:
    """Habilidade técnica"""
    name: str
    level: str = "Intermediário"
    
    def to_dict(self) -> Dict[str, str]:
        return {"nome": self.name, "nivel": self.level}


# ==================== CONFIGURAÇÃO ====================
class Config:
    """Gerenciador de configurações"""
    
    def __init__(self):
        self._load_env()
        self.pareto_api_key = self._get_api_key()
        self.agent_id = self._get_agent_id()
        self.tess_endpoint = self._build_endpoint()
        self.timeout = int(os.getenv('TESS_TIMEOUT', '100'))
        self.max_resume_length = int(os.getenv('MAX_RESUME_LENGTH', '8000'))
        
    def _load_env(self):
        """Carrega variáveis de ambiente"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            logger.info(" Variáveis de ambiente carregadas")
        except ImportError:
            logger.warning("⚠️ python-dotenv não instalado")
    
    def _get_api_key(self) -> Optional[str]:
        """Obtém API key com fallbacks"""
        return (
            os.getenv('PARETO_API_KEY') or 
            os.getenv('TESS_API_KEY') or 
            None
        )
    
    def _get_agent_id(self) -> str:
        """Obtém Agent ID"""
        return os.getenv('TESS_AGENT_ID') or os.getenv('AGENT_ID', '67')
    
    def _build_endpoint(self) -> Optional[str]:
        """Constrói endpoint da API corretamente"""
        if self.agent_id:
            # Garante que a URL comece com https:// e use o domínio da Pareto
            return f"https://tess.pareto.io/api/agents/{self.agent_id}/execute"
        return None
    
    def is_tess_configured(self) -> bool:
        """Verifica se Tess está configurada"""
        return bool(self.pareto_api_key and self.tess_endpoint)
    
    def log_config(self):
        """Exibe configuração atual"""
        if self.is_tess_configured():
            logger.info(" Tess API configurada")
            logger.info(f" API Key: {self.pareto_api_key[:10]}...{self.pareto_api_key[-5:]}")
            logger.info(f" Agent ID: {self.agent_id}")
            logger.info(f" Endpoint: {self.tess_endpoint}")
        else:
            logger.warning("⚠️ Tess não configurada - usando Enhanced Analyzer")


# ==================== PARSERS ====================
class ResponseParser:
    """Parser de respostas da Tess"""
    
    @staticmethod
    def extract_output(response_data: Dict) -> str:
        """Extrai output da resposta (responses[0].output)"""
        try:
            responses = response_data.get('responses', [])
            if responses and isinstance(responses[0], dict):
                output = responses[0].get('output')
                if output:
                    logger.info(" Output extraído de responses[0].output")
                    return str(output)
                logger.warning("⚠️ responses[0].output está vazio")
        except Exception as e:
            logger.error(f"⚠️ Erro ao ler responses[0].output: {e}")
        
        # Fallbacks
        fallback_keys = ['output', 'data.output', 'result', 'message', 'response']
        for key in fallback_keys:
            value = ResponseParser._get_nested_value(response_data, key)
            if value:
                logger.info(f" Output extraído de '{key}'")
                return str(value)
        
        logger.warning("⚠️ Nenhum output encontrado - retornando JSON bruto")
        return json.dumps(response_data, ensure_ascii=False)
    
    @staticmethod
    def _get_nested_value(data: Dict, key_path: str) -> Any:
        """Obtém valor aninhado usando notação de ponto"""
        keys = key_path.split('.')
        value = data
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    @staticmethod
    def parse_json_response(output: str) -> Dict[str, Any]:
        """Parseia resposta JSON"""
        logger.info(" Parseando resposta JSON...")
        
        # Tentar extrair JSON da resposta
        json_match = re.search(r'\{[\s\S]*\}', output)
        
        if json_match:
            try:
                analysis = json.loads(json_match.group(0))
                logger.info(f" JSON parseado - Chaves: {list(analysis.keys())}")
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"⚠️ Erro ao parsear JSON: {e}")
        
        logger.warning("🔄 Usando fallback parser")
        return ResponseParser._fallback_parse(output)
    
    @staticmethod
    def _fallback_parse(text: str) -> Dict[str, Any]:
        """Parser de fallback para texto livre"""
        return {
            "score": TextExtractor.extract_score(text),
            "hard_skills": [
                {"nome": s, "nivel": "Intermediário"} 
                for s in TextExtractor.extract_skills(text)
            ],
            "soft_skills": ["Comunicação", "Trabalho em equipe"],
            "experiencia": {
                "anos": TextExtractor.extract_years(text),
                "cargos": ["Verificar manualmente"],
                "lacunas": []
            },
            "pontos_fortes": ["Experiência relevante", "Perfil potencialmente aderente"],
            "pontos_atencao": ["Validar escopo de atuação", "Verificar profundidade técnica"],
            "observacoes_riscos": []
        }


class TextExtractor:
    """Extrator de informações de texto livre"""
    
    @staticmethod
    def extract_score(text: str) -> float:
        """Extrai pontuação do texto"""
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
    
    @staticmethod
    def extract_skills(text: str) -> List[str]:
        """Extrai skills do texto"""
        skills = []
        
        # Padrão 1: "skills identificadas"
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
        
        # Padrão 2: "ANÁLISE DE HARD SKILLS:"
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
    
    @staticmethod
    def extract_years(text: str) -> float:
        """Extrai anos de experiência"""
        patterns = [
            r'(\d+)\s*(?:\+)?\s*anos?\s+de\s+experiência',
            r'experiência[:\s]+(\d+)\s*(?:\+)?\s*anos?',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1))
        return 2.0
    
    @staticmethod
    def count_projects(text: str) -> int:
        """Conta menções a projetos"""
        keywords = ['projeto', 'project', 'desenvolveu', 'implementou']
        count = sum(
            len(re.findall(r'\b' + k + r'\b', text.lower())) 
            for k in keywords
        )
        return min(count, 20)


# ==================== ANALISADORES ====================
class TessAnalyzer:
    """Analisador usando API Tess"""
    
    def __init__(self, config: Config):
        self.config = config
        self.session = self._create_session()
    
    def _create_session(self) -> requests.Session:
        """Cria sessão HTTP com certificados"""
        session = requests.Session()
        session.verify = certifi.where()
        return session
    
    def analyze(self, candidate_data: Dict[str, Any], 
                job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Executa análise via Tess"""
        logger.info(" Iniciando análise com Tess...")
        
        # Preparar prompt
        prompt = self._build_prompt(candidate_data, job_requirements)
        
        # Preparar payload
        payload = {
            "texto": prompt,
            "temperature": "0.5",
            "model": "gpt-4o-mini",
            "maxlength": 4500,
            "language": "Portuguese (Brazil)",
            "wait_execution": True
        }
        
        headers = {
            "Authorization": f"Bearer {self.config.pareto_api_key}",
            "Content-Type": "application/json"
        }
        
        # Fazer requisição
        response = self.session.post(
            self.config.tess_endpoint,
            json=payload,
            headers=headers,
            timeout=self.config.timeout
        )
        
        logger.info(f" Status HTTP: {response.status_code}")
        
        if response.status_code != 200:
            raise Exception(self._format_error(response))
        
        # Processar resposta
        tess_data = response.json()
        output = ResponseParser.extract_output(tess_data)
        
        if not output:
            raise Exception("Output vazio da Tess")
        
        logger.info(f" Output extraído ({len(output)} chars)")
        
        # Parsear e estruturar
        return self._structure_response(
            output, candidate_data, job_requirements, tess_data
        )
    
    def _build_prompt(self, candidate_data: Dict, job_requirements: Dict) -> str:
        """Constrói prompt otimizado"""
        resume_text = candidate_data.get('resume_text', '')[:self.config.max_resume_length]
        
        return f"""
=== ANÁLISE DE CURRÍCULO ===

📋 VAGA:
Título: {job_requirements.get('title', 'N/A')}
Descrição: {job_requirements.get('description', 'N/A')}
Requisitos: {job_requirements.get('requirements', 'N/A')}

👤 CANDIDATO: {candidate_data.get('name', 'Candidato')}

📄 CURRÍCULO:
{resume_text}

---

🎯 ANÁLISE REQUERIDA:

1) HARD SKILLS (até 10, com nível: Básico/Intermediário/Avançado)
2) SOFT SKILLS (até 5 competências interpessoais)
3) EXPERIÊNCIA (anos, cargos, lacunas)
4) SCORE GERAL (0-10, considerando fit técnico e match com vaga)
5) PONTOS FORTES (3-5 itens)
6) PONTOS DE ATENÇÃO (3-5 riscos ou gaps)
7) OBSERVAÇÕES E RISCOS CRÍTICOS

FORMATO DE SAÍDA - JSON VÁLIDO:
{{
  "score": 0-10,
  "hard_skills": [{{"nome": "...", "nivel": "..."}}],
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

IMPORTANTE: Retorne APENAS o JSON, sem texto adicional.
""".strip()
    
    def _format_error(self, response: requests.Response) -> str:
        """Formata mensagem de erro"""
        error_msg = f"HTTP {response.status_code}"
        try:
            error_detail = response.json()
            error_msg += f" - {error_detail}"
        except Exception:
            error_msg += f" - {response.text[:200]}"
        return error_msg
    
    def _structure_response(self, output: str, candidate_data: Dict,
                           job_requirements: Dict, raw_data: Dict) -> Dict[str, Any]:
        """Estrutura resposta final"""
        analysis = ResponseParser.parse_json_response(output)
        
        # Extrair dados
        score = self._extract_score(analysis)
        hard_skills = analysis.get('hard_skills', [])
        soft_skills = analysis.get('soft_skills', [])
        experiencia = analysis.get('experiencia', {})
        pontos_fortes = analysis.get('pontos_fortes', [])
        pontos_atencao = analysis.get('pontos_atencao', [])
        observacoes = analysis.get('observacoes_riscos', [])
        
        # Processar skills
        skill_names = self._process_skills(hard_skills)
        
        # Extrair experiência
        years, positions = self._process_experience(experiencia)
        
        # Determinar senioridade
        seniority = self._determine_seniority(years, score)
        
        # Formatar textos
        strengths_text = self._format_list(pontos_fortes, "✅") or "✅ Perfil adequado"
        weaknesses_text = self._format_list(pontos_atencao, "⚠️") or "⚠️ Nenhum ponto crítico"
        risks_text = self._format_list(observacoes, "🔴") or "✅ Sem riscos críticos"
        
        # Recomendação
        recommendation = self._get_recommendation(score)
        
        logger.info(f" Análise concluída - Score: {score:.1f}/10 | {seniority.value}")
        
        return {
            "contact_info": {
                "email": candidate_data.get('email', 'Não informado'),
                "phone": candidate_data.get('phone', 'Não informado'),
                "linkedin": candidate_data.get('linkedin_url', 'Não informado')
            },
            "extracted_skills": skill_names[:20],
            "matched_skills": skill_names[:15],
            "missing_skills": [],
            "seniority_detected": seniority.value,
            "experience_years": years,
            "experience_summary": f"{seniority.value} • {years} anos • {', '.join(positions[:3]) if positions else 'Cargos não detalhados'}",
            "leadership_responsibilities": ["Avaliar em entrevista"],
            "complexity_indicators": [f"Score: {score:.1f}/10"],
            "mentorship_indicators": soft_skills[:3] if soft_skills else ["Validar em entrevista"],
            "strengths": strengths_text,
            "weaknesses": weaknesses_text,
            "professional_summary": self._generate_summary(score, seniority, years, len(skill_names)),
            "hard_skills_score": max(1.0, min(10.0, score)),
            "soft_skills_score": max(1.0, min(10.0, score - 0.5)),
            "experience_score": max(1.0, min(10.0, years * 1.2)),
            "overall_score": score,
            "recommendation": recommendation.value,
            "recommendation_reason": pontos_fortes[0] if pontos_fortes else "Perfil aderente",
            "potential_risks": risks_text,
            "analysis_source": "🤖 Tess AI (Pareto) - Agent 67",
            "analysis_timestamp": datetime.now().isoformat(),
            "provider": AnalysisProvider.TESS_PARETO.value,
            "confidence_level": "Alta - Análise estruturada",
            "tess_raw_output": output[:1000],
            "tess_full_response": raw_data,
            "tess_json_analysis": analysis,
            "total_skills_found": len(skill_names),
            "skill_match_percentage": min(100, int(score * 10)),
            "projects_mentioned": TextExtractor.count_projects(candidate_data.get('resume_text', '')),
            "education_level": "Avaliar manualmente",
            "soft_skills_identified": soft_skills,
            "hard_skills_detailed": hard_skills,
            "job_positions": positions,
            "analysis_note": f"✅ Análise Tess | Score: {score:.1f}/10 | {len(skill_names)} skills"
        }
    
    @staticmethod
    def _extract_score(analysis: Dict) -> float:
        """Extrai score com fallbacks"""
        score = analysis.get('score') or analysis.get('pontuacao') or analysis.get('nota', 6.5)
        try:
            return float(score)
        except (TypeError, ValueError):
            return 6.5
    
    @staticmethod
    def _process_skills(hard_skills: List) -> List[str]:
        """Processa lista de skills"""
        skill_names = []
        
        if isinstance(hard_skills, list):
            for skill in hard_skills:
                if isinstance(skill, dict):
                    nome = skill.get('nome') or skill.get('name') or skill.get('skill', '')
                    if nome:
                        skill_names.append(nome)
                elif isinstance(skill, str):
                    skill_names.append(skill)
        
        return skill_names
    
    @staticmethod
    def _process_experience(experiencia: Dict) -> Tuple[float, List[str]]:
        """Processa experiência profissional"""
        years = 0.0
        positions = []
        
        if isinstance(experiencia, dict):
            years = experiencia.get('anos') or experiencia.get('years', 0) or 0
            positions = experiencia.get('cargos') or experiencia.get('positions', []) or []
        
        return float(years), positions
    
    @staticmethod
    def _determine_seniority(years: float, score: float) -> SeniorityLevel:
        """Determina nível de senioridade"""
        if years >= 7 or score >= 8.5:
            return SeniorityLevel.SENIOR
        elif years >= 4 or score >= 7.0:
            return SeniorityLevel.PLENO
        elif years >= 2:
            return SeniorityLevel.JUNIOR
        else:
            return SeniorityLevel.TRAINEE
    
    @staticmethod
    def _format_list(items: List[str], prefix: str) -> str:
        """Formata lista com prefixo"""
        if not items:
            return ""
        return '\n'.join([f"{prefix} {item}" for item in items])
    
    @staticmethod
    def _get_recommendation(score: float) -> Recommendation:
        """Determina recomendação baseada no score"""
        if score >= 8.0:
            return Recommendation.HIGHLY_RECOMMENDED
        elif score >= 6.5:
            return Recommendation.RECOMMENDED
        elif score >= 5.0:
            return Recommendation.MANUAL_REVIEW
        else:
            return Recommendation.NOT_RECOMMENDED
    
    @staticmethod
    def _generate_summary(score: float, seniority: SeniorityLevel, 
                         years: float, skills_count: int) -> str:
        """Gera resumo profissional"""
        return (
            f"Profissional {seniority.value} com {years} anos de experiência. "
            f"Score de {score:.1f}/10, com {skills_count} competências técnicas. "
            f"Análise via Tess Agent 67."
        )


class EnhancedLocalAnalyzer:
    """Analisador local (fallback)"""
    
    def analyze(self, candidate_data: Dict[str, Any],
                job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Executa análise local"""
        logger.info(" Usando Enhanced Local Analyzer...")
        
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
            
            logger.info(f" Enhanced Analysis - Score: {result.get('overall_score', 0):.1f}/10")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro no Enhanced Analyzer: {e}")
            raise


# ==================== CLASSE PRINCIPAL ====================
class AIAnalyzer:
    """Analisador AI com múltiplos provedores"""
    
    def __init__(self):
        logger.info(" Inicializando TalentScope AI Analyzer...")
        
        self.config = Config()
        self.config.log_config()
        
        self.tess_analyzer = TessAnalyzer(self.config) if self.config.is_tess_configured() else None
        self.enhanced_analyzer = EnhancedLocalAnalyzer()
    
    def analyze_candidate(self, candidate_data: Dict[str, Any], 
                          job_requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Análise com estratégia de fallback"""
        
        logger.info("=" * 60)
        logger.info(" INICIANDO ANÁLISE")
        logger.info("=" * 60)
        logger.info(f" Candidato: {candidate_data.get('name', 'N/A')}")
        logger.info(f" Vaga: {job_requirements.get('title', 'N/A')}")
        
        # Estratégia 1: Tess
        if self.tess_analyzer:
            try:
                result = self.tess_analyzer.analyze(candidate_data, job_requirements)
                logger.info(" Análise Tess concluída")
                return result
            except Exception as e:
                logger.warning(f" Tess falhou: {str(e)}")
                logger.info(" Ativando fallback...")
        
        # Estratégia 2: Enhanced Local
        try:
            return self.enhanced_analyzer.analyze(candidate_data, job_requirements)
        except Exception as e:
            logger.error(f"❌ Enhanced falhou: {e}")
            return self._emergency_fallback(candidate_data, job_requirements, str(e))
    
    def _emergency_fallback(self, candidate_data: Dict, 
                           job_requirements: Dict, error: str) -> Dict:
        """Fallback de emergência"""
        logger.error("⚠️ Executando fallback de emergência")
        
        return {
            "contact_info": {
                "email": candidate_data.get('email', 'N/A'),
                "phone": candidate_data.get('phone', 'N/A'),
                "linkedin": candidate_data.get('linkedin_url', 'N/A')
            },
            "extracted_skills": [],
            "matched_skills": [],
            "missing_skills": [],
            "seniority_detected": SeniorityLevel.UNDETERMINED.value,
            "experience_years": 0,
            "experience_summary": "Erro na análise",
            "strengths": f"❌ Erro: {error}",
            "weaknesses": "Análise não concluída",
            "professional_summary": "Sistema indisponível",
            "hard_skills_score": 0,
            "soft_skills_score": 0,
            "experience_score": 0,
            "overall_score": 0,
            "recommendation": Recommendation.SYSTEM_ERROR.value,
            "recommendation_reason": error,
            "potential_risks": "Análise manual obrigatória",
            "analysis_source": "❌ Erro de Sistema",
            "analysis_timestamp": datetime.now().isoformat(),
            "provider": AnalysisProvider.EMERGENCY_FALLBACK.value,
            "confidence_level": "Nenhuma",
            "error": error
        }
    
    def test_connection(self) -> bool:
        """Testa conexão com Tess"""
        if not self.config.is_tess_configured():
            logger.warning("⚠️ API não configurada")
            return True
        
        logger.info(" Testando endpoint Tess...")
        
        try:
            payload = {
                "texto": "Teste de conexão",
                "temperature": "0.5",
                "model": "gpt-4o-mini",
                "maxlength": 100,
                "language": "Portuguese (Brazil)",
                "wait_execution": True
            }
            
            headers = {
                "Authorization": f"Bearer {self.config.pareto_api_key}",
                "Content-Type": "application/json"
            }
            
            response = self.tess_analyzer.session.post(
                self.config.tess_endpoint,
                json=payload,
                headers=headers,
                timeout=30
            )
            
            logger.info(f" Status: {response.status_code}")
            logger.info(f" Resposta: {response.text[:300]}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Erro: {e}")
            return True
    
    def get_current_provider(self) -> str:
        """Retorna provedor atual"""
        if self.config.is_tess_configured():
            return "pareto_tess_with_enhanced_fallback"
        return "enhanced_local"


# ==================== FUNÇÕES DE CONVENIÊNCIA ====================
def create_analyzer() -> AIAnalyzer:
    """Factory function para criar analisador"""
    return AIAnalyzer()


def analyze_candidate_quick(cv_text: str, job_description: str, 
                            candidate_name: str = "Candidato",
                            email: str = "", phone: str = "") -> Dict[str, Any]:
    """Análise rápida (função de conveniência)"""
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


# ==================== PONTO DE ENTRADA ====================
if __name__ == "__main__":
    # Teste básico
    analyzer = create_analyzer()
    analyzer.test_connection()
    logger.info(f" Provider atual: {analyzer.get_current_provider()}")
