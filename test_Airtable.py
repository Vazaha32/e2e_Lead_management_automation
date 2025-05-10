import os
import requests
from datetime import datetime, UTC
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('AIRTABLE_PAT')}",
    "Content-Type": "application/json"
}

# Format Airtable validé (sans clé 'date')
now = datetime.now(UTC).isoformat(timespec="milliseconds")

data = {
    "fields": {
        "Name": "TEST FINALEMENT OK",
        "Email": "ok@test.com",
        "Messages": "Plus de problème !",
        "Created": now  # Envoyer directement la string
    }
}

response = requests.post(
    f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/Leads",
    headers=headers,
    json=data
)

print("Status Code:", response.status_code)
print("Réponse:", response.json())