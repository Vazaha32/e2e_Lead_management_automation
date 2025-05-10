import os

import requests
from flask import Flask, request, jsonify
from airtable import Airtable
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration Airtable
AIRTABLE_PAT = os.getenv('AIRTABLE_PAT')
BASE_ID = os.getenv('AIRTABLE_BASE_ID')


def create_airtable_record(data):
    try:
        headers = {
            "Authorization": f"Bearer {os.getenv('AIRTABLE_PAT')}",
            "Content-Type": "application/json"
        }

        url = f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID')}/Leads"

        record_data = {
            "fields": {
                "Name": data['name'],  # Exactement comme dans Airtable
                "Email": data['email'],  # Respecter la casse
                "Messages": data.get('message', ''),  # "Messages" avec 's' final
                "Created": datetime.now().isoformat() + "Z"  # Format Airtable
            }
        }

        response = requests.post(url, headers=headers, json=record_data)
        response.raise_for_status()
        return response.json()

    except Exception as err:
        print(f"Erreur Airtable : {str(err)}")
        return None

# Configuration Email
email_user = os.getenv('GMAIL_USER')
email_password = os.getenv('GMAIL_PASSWORD')

# Initialisation Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# Template Engine
env = Environment(loader=FileSystemLoader('templates'))


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    data = request.json

    # Sauvegarde dans Airtable
    airtable_response = create_airtable_record(data)

    # Envoi email immédiat
    send_welcome_email(data)

    # Planification rappel Calendly dans 3 jours
    scheduler.add_job(
        send_calendly_reminder,
        'date',
        run_date=datetime.now() + timedelta(days=3),
        args=[data['email']]
    )

    return jsonify({'status': 'success'}), 200


def send_welcome_email(data):
    # Génération du template
    template = env.get_template('email_template.html')
    html_content = template.render(
        name=data['name'],
        message=data.get('message', '')
    )

    # Configuration email
    msg = MIMEText(html_content, 'html')
    msg['Subject'] = "Merci pour votre demande !"
    msg['From'] = email_user
    msg['To'] = data['email']

    # Envoi via SMTP
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(email_user, email_password)
        server.send_message(msg)


def send_calendly_reminder(email):
    try:
        # Configuration Calendly
        calendly_api_key = os.getenv('CALENDLY_API_KEY')
        event_type_url = "https://calendly.com/vazaha-beuh/test"  # À remplacer

        headers = {
            "Authorization": f"Bearer {calendly_api_key}",
            "Content-Type": "application/json"
        }

        # Créer un événement programmé
        start_time = (datetime.now() + timedelta(days=3)).isoformat()
        payload = {
            "event_type": event_type_url,
            "start_time": start_time,
            "invitees": [{"email": email}]
        }

        response = requests.post(
            "https://api.calendly.com/scheduled_events",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            calendly_link = response.json()['resource']['uri']

            # Envoyer l'email avec le lien
            msg = MIMEText(f"Bonjour ! Voici votre lien de rendez-vous : {calendly_link}")
            msg['Subject'] = "📅 Rappel pour notre appel"
            msg['From'] = email_user
            msg['To'] = email

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(email_user, email_password)
                server.send_message(msg)
        else:
            print("Erreur Calendly :", response.json())

    except Exception as e:
        print("Erreur :", str(e))


if __name__ == '__main__':
    app.run(port=5000, debug=True)