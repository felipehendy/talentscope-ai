"""
Integração WhatsApp via Link Direto (wa.me)
Funciona em qualquer dispositivo - sem precisar de API!
"""

def format_phone(phone):
    """
    Formata número para WhatsApp
    Entrada: (11) 99999-9999 ou 11999999999
    Saída: 5511999999999
    """
    if not phone:
        return None
    
    # Remove tudo que não é número
    clean = ''.join(filter(str.isdigit, str(phone)))
    
    # Se não tem DDI (55), adiciona
    if not clean.startswith('55'):
        clean = '55' + clean
    
    return clean


def get_whatsapp_link(phone, message=None):
    """
    Gera link do WhatsApp Web/App
    
    Args:
        phone: Número do telefone
        message: Mensagem pré-pronta (opcional)
    
    Returns:
        URL do WhatsApp
    """
    formatted_phone = format_phone(phone)
    
    if not formatted_phone:
        return None
    
    base_url = f"https://wa.me/{formatted_phone}"
    
    if message:
        # URL encode da mensagem
        from urllib.parse import quote
        base_url += f"?text={quote(message)}"
    
    return base_url


def get_interview_invitation_message(candidate_name, job_title, date, time, link=None):
    """Mensagem de convite para entrevista"""
    message = f"""🎯 *Convite para Entrevista*

Olá *{candidate_name}*! 👋

É com satisfação que informamos que você foi selecionado(a) para a próxima etapa do processo seletivo para a vaga de *{job_title}*.

📅 *Data:* {date}
🕐 *Horário:* {time}"""
    
    if link:
        message += f"\n🔗 *Link:* {link}"
    
    message += """

Por favor, confirme sua presença.

Estamos ansiosos para conhecê-lo(a)! 😊"""
    
    return message


def get_approval_message(candidate_name, job_title):
    """Mensagem de aprovação"""
    return f"""🎉 *PARABÉNS!* 🎉

Olá *{candidate_name}*!

É com enorme satisfação que informamos que você foi *APROVADO(A)* para a vaga de *{job_title}*! 🎊

Ficamos muito impressionados com seu perfil!

Em breve entraremos em contato para os próximos passos.

Seja muito bem-vindo(a)! 🤝"""


def get_rejection_message(candidate_name, job_title):
    """Mensagem de reprovação"""
    return f"""Olá *{candidate_name}*,

Agradecemos seu interesse na vaga de *{job_title}* e por ter dedicado seu tempo ao processo seletivo.

Após análise, optamos por seguir com outros candidatos neste momento.

Esta decisão não diminui suas qualificações. Encorajamos você a acompanhar nossas futuras oportunidades!

Desejamos muito sucesso! 🌟"""


def get_thank_you_message(candidate_name):
    """Mensagem de agradecimento"""
    return f"""Olá *{candidate_name}*! 👋

Agradecemos sua participação no processo seletivo.

Em breve entraremos em contato com os próximos passos.

Fique à vontade para tirar dúvidas! 😊"""


def get_reminder_message(candidate_name, hours):
    """Lembrete de entrevista"""
    return f"""⏰ *Lembrete de Entrevista*

Olá *{candidate_name}*!

Sua entrevista está marcada para daqui a *{hours} hora(s)*.

Nos vemos em breve! 🤝"""