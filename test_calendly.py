import os
import requests
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('CALENDLY_API_KEY')}",
    "Content-Type": "application/json"
}

response = requests.get("https://api.calendly.com/users/me", headers=headers)
print(response.status_code)
print(response.json())