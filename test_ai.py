from dotenv import load_dotenv
import os
from openai import OpenAI

# Carrega as variáveis do arquivo .env
load_dotenv()

# Cria o cliente usando a variável de ambiente
client = OpenAI()

# Teste simples
resp = client.chat.completions.create(
    model="gemini-2.5-flash",
    messages=[
        {"role": "user", "content": "Diga apenas: TESTE OK"}
    ]
)

print(resp.choices[0].message.content)
