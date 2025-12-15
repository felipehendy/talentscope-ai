import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("PARETO_API_KEY")

url = "https://tess.pareto.io/api/agents"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

response = requests.get(url, headers=headers)

print("STATUS:", response.status_code)
print(response.json())
