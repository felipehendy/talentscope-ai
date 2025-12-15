# enhanced_analyzer.py
"""
Enhanced CV Analyzer - Analisador de Currículos Avançado
Sistema de análise inteligente sem necessidade de API externa
"""

import re
from typing import Dict, List, Tuple
from datetime import datetime

class EnhancedCVAnalyzer:
    """Analisador de currículos avançado com análise detalhada e estruturada"""
    
    def __init__(self):
        # Tecnologias categorizadas
        self.tech_stack = {
            'Linguagens de Programação': [
                'python', 'java', 'javascript', 'typescript', 'c#', 'c++', 'php', 
                'ruby', 'go', 'rust', 'swift', 'kotlin', 'scala', 'r', 'matlab',
                'perl', 'dart', 'elixir', 'haskell', 'lua', 'bash', 'shell'
            ],
            'Frameworks Web': [
                'react', 'angular', 'vue', 'svelte', 'django', 'flask', 'fastapi',
                'spring', 'laravel', 'rails', 'express', 'nest', 'next', 'nuxt',
                'gatsby', 'remix', 'solid', 'qwik', 'astro'
            ],
            'Bancos de Dados': [
                'mysql', 'postgresql', 'mongodb', 'oracle', 'sql server', 'redis',
                'cassandra', 'dynamodb', 'elasticsearch', 'mariadb', 'sqlite',
                'neo4j', 'couchdb', 'influxdb', 'clickhouse', 'sql'
            ],
            'Cloud & DevOps': [
                'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes',
                'jenkins', 'gitlab', 'github actions', 'terraform', 'ansible',
                'circleci', 'travis', 'heroku', 'vercel', 'netlify', 'digitalocean'
            ],
            'Ferramentas & Metodologias': [
                'git', 'jira', 'scrum', 'agile', 'kanban', 'rest', 'graphql',
                'microservices', 'api', 'tdd', 'ci/cd', 'devops', 'solid',
                'clean code', 'design patterns'
            ],
            'Data Science & IA': [
                'machine learning', 'deep learning', 'tensorflow', 'pytorch',
                'scikit-learn', 'pandas', 'numpy', 'jupyter', 'data analysis',
                'power bi', 'tableau', 'keras', 'spark', 'hadoop', 'airflow'
            ],
            'Business Intelligence': [
                'power bi', 'tableau', 'qlik', 'looker', 'metabase', 'excel avançado',
                'dax', 'powerquery', 'sap', 'salesforce', 'microsoft excel'
            ],
            'Mobile': [
                'react native', 'flutter', 'ionic', 'xamarin', 'android',
                'ios', 'swift', 'kotlin', 'objective-c'
            ]
        }
        
        # Palavras-chave de ação (verbos de realização)
        self.action_verbs = [
            'desenvolveu', 'implementou', 'criou', 'liderou', 'gerenciou',
            'coordenou', 'projetou', 'arquitetou', 'otimizou', 'melhorou',
            'automatizou', 'integrou', 'migrou', 'refatorou', 'escalou',
            'deployed', 'built', 'created', 'led', 'managed', 'designed',
            'maintained', 'tested', 'debugged', 'configured', 'desenvolvido',
            'realizado', 'executado', 'implantado'
        ]
        
        # Indicadores de senioridade
        self.seniority_indicators = {
            'Junior': {
                'keywords': ['júnior', 'junior', 'jr', 'estagiário', 'trainee', 'assistente', 'intern', 'iniciante'],
                'years_range': (0, 2),
                'score_multiplier': 0.85
            },
            'Pleno': {
                'keywords': ['pleno', 'analista', 'desenvolvedor', 'developer', 'engineer', 'programador'],
                'years_range': (2, 5),
                'score_multiplier': 1.0
            },
            'Sênior': {
                'keywords': ['sênior', 'senior', 'sr', 'especialista', 'specialist', 'lead', 'principal', 'sênior'],
                'years_range': (5, 100),
                'score_multiplier': 1.15
            },
            'Expert': {
                'keywords': ['arquiteto', 'architect', 'tech lead', 'staff', 'principal', 'head', 'diretor', 'gerente'],
                'years_range': (8, 100),
                'score_multiplier': 1.25
            }
        }
        
        # Formação acadêmica
        self.education_levels = {
            'ensino médio': 1,
            'técnico': 2,
            'tecnólogo': 3,
            'graduação': 4,
            'bacharelado': 4,
            'licenciatura': 4,
            'pós-graduação': 5,
            'especialização': 5,
            'mba': 5,
            'mestrado': 6,
            'doutorado': 7,
            'phd': 7
        }

    def analyze(self, cv_text: str, job_description: str, candidate_name: str = "Candidato") -> Dict:
        """
        Análise completa e detalhada do CV vs Vaga
        
        Returns:
            Dict com análise estruturada compatível com o sistema
        """
        
        print("🔍 Iniciando Enhanced Analysis...")
        
        cv_lower = cv_text.lower()
        job_lower = job_description.lower()
        
        # 1. Extrair todas as tecnologias
        cv_tech = self._extract_all_technologies(cv_lower)
        job_tech = self._extract_all_technologies(job_lower)
        
        # 2. Calcular match de tecnologias
        tech_match = self._calculate_tech_match(cv_tech, job_tech)
        
        # 3. Analisar experiência profissional
        experience_data = self._analyze_experience(cv_text)
        
        # 4. Analisar senioridade
        seniority = self._detect_seniority(cv_lower, experience_data['years'])
        
        # 5. Analisar projetos e complexidade
        projects_data = self._analyze_projects(cv_text)
        
        # 6. Analisar liderança
        leadership = self._analyze_leadership(cv_lower)
        
        # 7. Analisar formação
        education = self._analyze_education(cv_lower)
        
        # 8. Calcular scores (CALIBRADOS)
        scores = self._calculate_scores_calibrated(
            tech_match, experience_data, projects_data, 
            leadership, education, seniority, len(cv_text)
        )
        
        # 9. Gerar feedback estruturado
        feedback = self._generate_detailed_feedback(
            tech_match, experience_data, projects_data,
            leadership, seniority, scores, cv_tech
        )
        
        print(f"✅ Enhanced Analysis concluída - Score: {scores['overall']:.1f}/10")
        
        # Retornar no formato esperado pelo sistema
        return {
            # Informações básicas
            "contact_info": {
                "email": "Extrair do formulário",
                "phone": "Extrair do formulário",
                "linkedin": "Extrair do formulário"
            },
            
            # Skills e tecnologias
            "extracted_skills": cv_tech['all_skills'][:20],
            "matched_skills": tech_match['matched'],
            "missing_skills": tech_match['missing'][:5],
            
            # Experiência e senioridade
            "seniority_detected": seniority['level'],
            "experience_years": experience_data['years'],
            "experience_summary": f"{seniority['level']} • {experience_data['years']:.0f} anos • {len(cv_tech['all_skills'])} skills identificadas",
            
            # Indicadores de liderança e complexidade
            "leadership_responsibilities": leadership['responsibilities'],
            "complexity_indicators": projects_data['complexity_indicators'],
            "mentorship_indicators": leadership['mentorship'],
            
            # Análise qualitativa
            "strengths": feedback['strengths'],
            "weaknesses": feedback['weaknesses'],
            "professional_summary": feedback['summary'],
            
            # Scores
            "hard_skills_score": scores['technical'],
            "soft_skills_score": scores['soft_skills'],
            "experience_score": scores['experience'],
            "overall_score": scores['overall'],
            
            # Recomendação
            "recommendation": feedback['recommendation'],
            "recommendation_reason": feedback['recommendation_reason'],
            
            # Riscos e observações
            "potential_risks": feedback['risks'],
            
            # Metadados
            "analysis_source": "🤖 Enhanced Local Analyzer",
            "analysis_timestamp": datetime.now().isoformat(),
            "provider": "enhanced_local",
            "confidence_level": "Alta - Análise estruturada avançada",
            
            # Estatísticas adicionais
            "total_skills_found": len(cv_tech['all_skills']),
            "skill_match_percentage": tech_match['percentage'],
            "projects_mentioned": projects_data['count'],
            "education_level": education['level'],
            "analysis_note": "✅ Análise avançada com múltiplos critérios"
        }

    def _extract_all_technologies(self, text: str) -> Dict:
        """Extrai todas as tecnologias por categoria"""
        
        found = {}
        all_skills = []
        
        for category, techs in self.tech_stack.items():
            category_skills = []
            for tech in techs:
                # Busca mais precisa com word boundaries
                pattern = r'\b' + re.escape(tech) + r'\b'
                if re.search(pattern, text, re.IGNORECASE):
                    skill_name = tech.title()
                    category_skills.append(skill_name)
                    all_skills.append(skill_name)
            found[category] = category_skills
        
        return {
            'by_category': found,
            'all_skills': list(set(all_skills))
        }

    def _calculate_tech_match(self, cv_tech: Dict, job_tech: Dict) -> Dict:
        """Calcula match detalhado de tecnologias COM CRITÉRIO"""
        
        cv_skills = set(s.lower() for s in cv_tech['all_skills'])
        job_skills = set(s.lower() for s in job_tech['all_skills'])
        
        if not job_skills:
            # Se não há skills na vaga, avaliar baseado no CV
            if len(cv_skills) >= 10:
                percentage = 75.0
                score = 7.5
            elif len(cv_skills) >= 5:
                percentage = 60.0
                score = 6.0
            else:
                percentage = 40.0
                score = 4.5
            
            return {
                'matched': list(cv_skills)[:10],
                'missing': [],
                'percentage': percentage,
                'score': score
            }
        
        matched = cv_skills & job_skills
        missing = job_skills - cv_skills
        
        # Cálculo mais realista
        if len(matched) == 0:
            percentage = 0.0
            score = 2.0
        else:
            percentage = (len(matched) / len(job_skills) * 100)
            
            # Score baseado no match + bonus por skills extras
            base_score = (percentage / 10)  # 0-10
            extra_skills_bonus = min(1.5, len(cv_skills - job_skills) * 0.15)
            score = min(10.0, base_score + extra_skills_bonus)
        
        return {
            'matched': [s.title() for s in matched],
            'missing': [s.title() for s in missing],
            'percentage': round(percentage, 1),
            'score': round(score, 1)
        }

    def _analyze_experience(self, text: str) -> Dict:
        """Analisa anos de experiência de forma robusta"""
        
        # Padrões para detectar anos
        patterns = [
            r'(\d+)\s*(?:\+)?\s*anos?\s+de\s+experiência',
            r'experiência\s+de\s+(\d+)\s*(?:\+)?\s*anos?',
            r'(\d+)\s*(?:\+)?\s*years?\s+(?:of\s+)?experience',
        ]
        
        years = 0
        text_lower = text.lower()
        
        # Tentar extrair anos explícitos
        for pattern in patterns:
            matches = re.findall(pattern, text_lower)
            if matches:
                years = max(years, int(matches[0]))
        
        # Tentar calcular por períodos de trabalho (formato YYYY - YYYY)
        work_periods = re.findall(r'(\d{4})\s*[-–até]\s*(\d{4}|\bpresente\b|\batual\b|present|atual)', text_lower)
        if work_periods:
            total_years = 0
            current_year = datetime.now().year
            
            for start, end in work_periods:
                start_year = int(start)
                if 'present' in end or 'atual' in end or 'presente' in end:
                    end_year = current_year
                else:
                    try:
                        end_year = int(end)
                    except:
                        end_year = current_year
                
                period = max(0, end_year - start_year)
                if period <= 50:  # Validação: período razoável
                    total_years += period
            
            years = max(years, total_years)
        
        # Contar verbos de ação (indicador de projetos)
        action_count = sum(1 for verb in self.action_verbs if verb in text_lower)
        
        # Se não achou anos explícitos mas tem muitos verbos de ação
        if years == 0 and action_count >= 5:
            years = 2.0  # Estimar 2 anos
        elif years == 0:
            years = 1.0  # Mínimo 1 ano por default
        
        return {
            'years': float(years),
            'action_verbs_count': action_count,
            'has_explicit_years': years > 0
        }

    def _detect_seniority(self, text: str, years: float) -> Dict:
        """Detecta senioridade baseado em keywords e anos"""
        
        detected_level = 'Pleno'
        multiplier = 1.0
        found_keywords = []
        
        # Verificar keywords por ordem de senioridade (do maior pro menor)
        for level in ['Expert', 'Sênior', 'Pleno', 'Junior']:
            data = self.seniority_indicators[level]
            for keyword in data['keywords']:
                if keyword in text:
                    detected_level = level
                    multiplier = data['score_multiplier']
                    found_keywords.append(keyword)
                    break
            if found_keywords:
                break
        
        # Validar/ajustar com anos de experiência
        if years >= 8:
            if detected_level in ['Junior', 'Pleno']:
                detected_level = 'Sênior'
                multiplier = self.seniority_indicators['Sênior']['score_multiplier']
        elif years >= 5:
            if detected_level == 'Junior':
                detected_level = 'Pleno'
                multiplier = self.seniority_indicators['Pleno']['score_multiplier']
        elif years < 2:
            if detected_level in ['Sênior', 'Expert']:
                detected_level = 'Junior'
                multiplier = self.seniority_indicators['Junior']['score_multiplier']
        
        return {
            'level': detected_level,
            'multiplier': multiplier,
            'confidence': 'Alta' if found_keywords else 'Média'
        }

    def _analyze_projects(self, text: str) -> Dict:
        """Analisa projetos e implementações mencionados"""
        
        project_keywords = [
            'projeto', 'project', 'desenvolveu', 'implementou', 'criou',
            'built', 'created', 'developed', 'implemented', 'launched',
            'desenvolvido', 'implantado', 'executado'
        ]
        
        text_lower = text.lower()
        count = 0
        
        for keyword in project_keywords:
            # Contar ocorrências únicas com word boundary
            pattern = r'\b' + re.escape(keyword) + r'\b'
            count += len(re.findall(pattern, text_lower))
        
        # Limitar contagem para ser realista
        count = min(count, 15)
        
        complexity_indicators = []
        
        # Indicadores de complexidade
        if 'arquitetura' in text_lower or 'architecture' in text_lower:
            complexity_indicators.append("Experiência em arquitetura de software")
        
        if 'microserviços' in text_lower or 'microservices' in text_lower:
            complexity_indicators.append("Trabalho com microserviços")
        
        if any(word in text_lower for word in ['escalabilidade', 'performance', 'otimização', 'optimization']):
            complexity_indicators.append("Foco em performance e escalabilidade")
        
        if any(word in text_lower for word in ['migração', 'refatoração', 'modernização', 'migration']):
            complexity_indicators.append("Experiência em modernização de sistemas")
        
        if count >= 8:
            complexity_indicators.append(f"{count}+ projetos/implementações no histórico")
        elif count >= 3:
            complexity_indicators.append(f"{count} projetos/implementações identificados")
        else:
            complexity_indicators.append("Poucos projetos detalhados no CV")
        
        return {
            'count': count,
            'complexity_indicators': complexity_indicators
        }

    def _analyze_leadership(self, text: str) -> Dict:
        """Analisa indicadores de liderança e mentoria"""
        
        leadership_keywords = {
            'líder': 'Atuação como líder de equipe',
            'lead': 'Liderança técnica',
            'coordenação': 'Coordenação de projetos',
            'gestão': 'Gestão de equipe/projetos',
            'coordenador': 'Coordenação',
            'gerente': 'Gestão'
        }
        
        responsibilities = []
        for keyword, desc in leadership_keywords.items():
            if keyword in text:
                responsibilities.append(desc)
        
        mentorship = []
        if 'mentor' in text or 'mentoria' in text:
            mentorship.append("Experiência em mentoria")
        if 'treinamento' in text or 'training' in text:
            mentorship.append("Treinamento de equipe")
        if 'code review' in text or 'revisão' in text:
            mentorship.append("Participação em code reviews")
        
        if not responsibilities:
            responsibilities = ["Experiência técnica individual"]
        
        if not mentorship:
            mentorship = ["Não evidenciado"]
        
        return {
            'responsibilities': responsibilities,
            'mentorship': mentorship
        }

    def _analyze_education(self, text: str) -> Dict:
        """Analisa formação acadêmica"""
        
        highest_level = 0
        detected = 'Não informado'
        
        for education, level in self.education_levels.items():
            if education in text:
                if level > highest_level:
                    highest_level = level
                    detected = education.title()
        
        return {
            'level': detected,
            'score': highest_level
        }

    def _calculate_scores_calibrated(self, tech_match: Dict, experience: Dict, 
                                    projects: Dict, leadership: Dict, 
                                    education: Dict, seniority: Dict, cv_length: int) -> Dict:
        """Calcula todos os scores de forma CALIBRADA e REALISTA"""
        
        # 1. Score técnico (baseado em match real)
        technical = tech_match['score']
        
        # Penalizar se CV é muito curto (menos de 500 chars)
        if cv_length < 500:
            technical *= 0.8
        
        # 2. Score de experiência (mais realista)
        if experience['years'] >= 8:
            exp_score = 9.0
        elif experience['years'] >= 5:
            exp_score = 8.0
        elif experience['years'] >= 3:
            exp_score = 7.0
        elif experience['years'] >= 2:
            exp_score = 6.0
        else:
            exp_score = 5.0
        
        # Bonus por verbos de ação (até +1.0)
        action_bonus = min(1.0, experience['action_verbs_count'] * 0.1)
        exp_score = min(10.0, exp_score + action_bonus)
        
        # 3. Score de soft skills (mais criterioso)
        soft = 5.5  # Base mais realista
        
        if len(leadership['responsibilities']) >= 3:
            soft += 2.5
        elif len(leadership['responsibilities']) >= 2:
            soft += 1.5
        elif len(leadership['responsibilities']) > 1:
            soft += 0.8
        
        if len(leadership['mentorship']) >= 2:
            soft += 1.5
        elif 'Não evidenciado' not in leadership['mentorship']:
            soft += 0.5
        
        soft = min(10.0, soft)
        
        # 4. Score de projetos (calibrado)
        if projects['count'] >= 10:
            project_score = 8.5
        elif projects['count'] >= 5:
            project_score = 7.0
        elif projects['count'] >= 3:
            project_score = 6.0
        else:
            project_score = 4.5
        
        # 5. Score overall ponderado (mais realista)
        overall = (
            technical * 0.35 +      # 35% técnico
            exp_score * 0.30 +      # 30% experiência
            soft * 0.20 +           # 20% soft skills
            project_score * 0.15    # 15% projetos
        )
        
        # Aplicar multiplicador de senioridade (com menos impacto)
        seniority_factor = 0.9 + (seniority['multiplier'] - 1.0) * 0.5
        overall *= seniority_factor
        
        # Bonus por formação (+0.5 a +1.5)
        education_bonus = education['score'] * 0.2
        overall = min(10.0, overall + education_bonus)
        
        # Garantir que scores fazem sentido
        overall = max(2.0, min(10.0, overall))
        
        return {
            'technical': round(technical, 1),
            'experience': round(exp_score, 1),
            'soft_skills': round(soft, 1),
            'projects': round(project_score, 1),
            'overall': round(overall, 1)
        }

    def _generate_detailed_feedback(self, tech_match: Dict, experience: Dict,
                                   projects: Dict, leadership: Dict,
                                   seniority: Dict, scores: Dict, cv_tech: Dict) -> Dict:
        """Gera feedback detalhado, específico e realista"""
        
        # Pontos fortes (ser específico)
        strengths = []
        
        if tech_match['percentage'] >= 80:
            strengths.append(f"✅ Excelente match técnico ({tech_match['percentage']:.0f}% das skills requisitadas)")
        elif tech_match['percentage'] >= 60:
            strengths.append(f"✅ Bom alinhamento técnico ({len(tech_match['matched'])} tecnologias match)")
        elif tech_match['percentage'] >= 40:
            strengths.append(f"✅ Alinhamento técnico parcial ({len(tech_match['matched'])} skills)")
        
        if experience['years'] >= 5:
            strengths.append(f"✅ Experiência sólida de {int(experience['years'])} anos na área")
        elif experience['years'] >= 3:
            strengths.append(f"✅ Experiência relevante de {int(experience['years'])} anos")
        
        if projects['count'] >= 8:
            strengths.append(f"✅ Histórico robusto: {projects['count']}+ projetos/implementações")
        elif projects['count'] >= 4:
            strengths.append(f"✅ Experiência prática: {projects['count']} projetos identificados")
        
        if len(leadership['responsibilities']) >= 2 and 'individual' not in leadership['responsibilities'][0].lower():
            strengths.append(f"✅ Experiência em liderança: {', '.join(leadership['responsibilities'][:2])}")
        
        if seniority['level'] in ['Sênior', 'Expert']:
            strengths.append(f"✅ Perfil {seniority['level']} com maturidade profissional")
        
        if not strengths:
            strengths.append("Candidato com potencial a ser explorado em entrevista")
        
        # Pontos de atenção (ser específico e construtivo)
        weaknesses = []
        
        if tech_match['percentage'] < 40:
            weaknesses.append(f"⚠️ Gap técnico significativo: {len(tech_match['missing'])} skills da vaga ausentes no CV")
            if tech_match['missing']:
                top_missing = ', '.join(tech_match['missing'][:4])
                weaknesses.append(f"⚠️ Skills ausentes críticas: {top_missing}")
        elif tech_match['percentage'] < 60:
            weaknesses.append(f"⚠️ Gap técnico moderado: {len(tech_match['missing'])} skills não evidentes")
            if len(tech_match['missing']) <= 3:
                weaknesses.append(f"⚠️ Skills ausentes: {', '.join(tech_match['missing'])}")
        
        if len(cv_tech['all_skills']) < 5:
            weaknesses.append(f"⚠️ Portfólio tecnológico limitado ({len(cv_tech['all_skills'])} skills)")
        
        if experience['years'] < 2:
            weaknesses.append(f"⚠️ Experiência profissional inicial ({int(experience['years'])} ano{'s' if experience['years'] != 1 else ''})")
        
        if not experience['has_explicit_years']:
            weaknesses.append("⚠️ Anos de experiência não explicitados no CV")
        
        if projects['count'] < 3:
            weaknesses.append("⚠️ Poucos projetos/implementações detalhados")
        
        if 'individual' in leadership['responsibilities'][0].lower():
            weaknesses.append("⚠️ Pouca evidência de liderança ou gestão de equipe")
        
        if not weaknesses:
            weaknesses.append("Perfil adequado - Validar fit cultural em entrevista")
        
        # Recomendação (criteriosa)
        score = scores['overall']
        
        if score >= 8.5:
            recommendation = "Altamente Recomendado"
            reason = f"Candidato excepcional com score {score}/10. Forte alinhamento técnico ({tech_match['percentage']:.0f}%) e {int(experience['years'])} anos de experiência."
        elif score >= 7.0:
            recommendation = "Recomendado"
            reason = f"Candidato qualificado (score {score}/10) com bom fit para a vaga. {len(tech_match['matched'])} skills alinhadas e experiência de {int(experience['years'])} anos."
        elif score >= 5.5:
            recommendation = "Análise Manual Recomendada"
            reason = f"Score {score}/10 - Potencial identificado mas requer validação em entrevista. Gap técnico de {len(tech_match['missing'])} skills."
        else:
            recommendation = "Não Recomendado"
            reason = f"Score {score}/10 - Baixa aderência aos requisitos. Gap técnico significativo e experiência limitada."
        
        # Resumo profissional (detalhado e específico)
        summary_parts = []
        summary_parts.append(f"Profissional {seniority['level']} com {int(experience['years'])} ano{'s' if experience['years'] != 1 else ''} de experiência")
        
        if len(cv_tech['all_skills']) > 0:
            top_skills = ', '.join(cv_tech['all_skills'][:5])
            summary_parts.append(f"Domínio de {len(cv_tech['all_skills'])} tecnologias, incluindo {top_skills}")
        
        if projects['count'] >= 3:
            summary_parts.append(f"{projects['count']}+ projetos/implementações no histórico")
        
        if tech_match['matched']:
            summary_parts.append(f"Match com {len(tech_match['matched'])} skills da vaga: {', '.join(tech_match['matched'][:4])}")
        
        summary = ". ".join(summary_parts) + "."
        
        # Riscos (específicos)
        risks = []
        
        if tech_match['percentage'] < 30:
            risks.append("🔴 Alto risco: Gap técnico crítico - Requer capacitação extensiva")
        elif tech_match['percentage'] < 50:
            risks.append("🟡 Risco moderado: Gap técnico significativo")
        
        if experience['years'] < 1:
            risks.append("🔴 Alto risco: Experiência muito limitada para a vaga")
        elif experience['years'] < 2 and seniority['level'] != 'Junior':
            risks.append("🟡 Senioridade pode não estar alinhada com experiência")
        
        if projects['count'] < 2:
            risks.append("🟡 Poucos projetos comprovados - Validar em entrevista")
        
        if len(cv_tech['all_skills']) < 4:
            risks.append("🟡 Portfólio tecnológico limitado")
        
        if not risks:
            risks.append("✅ Nenhum risco crítico identificado")
            risks.append("✅ Perfil alinhado com a vaga")
        
        return {
            'strengths': '\n'.join(strengths),
            'weaknesses': '\n'.join(weaknesses),
            'recommendation': recommendation,
            'recommendation_reason': reason,
            'summary': summary,
            'risks': '\n'.join(risks)
        }


# Função helper para integração fácil
def analyze_cv_enhanced(cv_text: str, job_description: str, candidate_name: str = "Candidato") -> Dict:
    """
    Função wrapper para uso direto
    """
    analyzer = EnhancedCVAnalyzer()
    return analyzer.analyze(cv_text, job_description, candidate_name)