import os
import sys
import json
import logging
import requests
import smtplib
from datetime import datetime, timedelta, timezone
from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
from urllib.parse import urlparse

# Configuration des logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

app = Flask(__name__)
app.logger.setLevel(logging.DEBUG)

# Chargement des variables d'environnement
load_dotenv()

# Configuration Airtable
AIRTABLE_PAT = os.getenv('AIRTABLE_PAT')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

# Configuration Email
GMAIL_USER = os.getenv('GMAIL_USER')
GMAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')

# Configuration Calendly
CALENDLY_EVENT_URL = os.getenv('CALENDLY_EVENT_URL')
CALENDLY_API_KEY = os.getenv('CALENDLY_API_KEY')
CALENDLY_ORG_ID = os.getenv('CALENDLY_ORG_ID')

# Vérification des variables critiques
required_vars = {
    'AIRTABLE_PAT': AIRTABLE_PAT,
    'AIRTABLE_BASE_ID': AIRTABLE_BASE_ID,
    'GMAIL_USER': GMAIL_USER,
    'GMAIL_PASSWORD': GMAIL_PASSWORD,
    'CALENDLY_EVENT_URL': CALENDLY_EVENT_URL,
    'CALENDLY_API_KEY': CALENDLY_API_KEY
}

for var_name, var_value in required_vars.items():
    if not var_value:
        app.logger.error(f"❌ Variable manquante dans .env : {var_name}")
        exit(1)

# Configuration Scheduler
scheduler = BackgroundScheduler(timezone="UTC")
scheduler.start()

# Template Engine
env = Environment(loader=FileSystemLoader('templates'))


def create_airtable_record(data):
    try:
        headers = {
            "Authorization": f"Bearer {AIRTABLE_PAT}",
            "Content-Type": "application/json"
        }

        record_data = {
            "fields": {
                "Name": data['name'],
                "Email": data['email'],
                "Messages": data.get('message', ''),
                "Created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            }
        }

        response = requests.post(
            f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Leads",
            headers=headers,
            json=record_data
        )

        app.logger.debug(f"Réponse Airtable : {response.status_code} {response.text}")
        response.raise_for_status()
        return response.json()

    except Exception as err:
        app.logger.error(f"Erreur Airtable : {str(err)}", exc_info=True)
        return None


def get_organization_id():
    """Récupère dynamiquement l'Organization ID"""
    headers = {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Calendly-API-Version": "2024-05-01"
    }

    response = requests.get("https://api.calendly.com/users/me", headers=headers)
    return response.json()['resource']['current_organization'].split('/')[-1]


def get_calendly_event_uuid():
    """Récupère l'UUID de l'événement via l'API Calendly (version corrigée)"""
    headers = {
        "Authorization": f"Bearer {CALENDLY_API_KEY}",
        "Calendly-API-Version": "2024-05-01"
    }

    org_id = get_organization_id()

    response = requests.get(
        "https://api.calendly.com/event_types",
        headers=headers,
        params={
            "organization": f"https://api.calendly.com/organizations/{org_id}",
            "active": True
        }
    )

    return response.json()["collection"][0]["uri"].split("/")[-1]


def send_email(email: str, calendly_link: str):
    try:
        # Génération du contenu HTML
        template = env.get_template('email_rappel.html')
        html_content = template.render(calendly_link=calendly_link)

        # Configuration de l'email
        msg = MIMEText(html_content, 'html')
        msg['Subject'] = "📅 Rappel pour votre appel de suivi"
        msg['From'] = GMAIL_USER
        msg['To'] = email

        # Envoi via SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.send_message(msg)
            app.logger.info(f"✅ Email envoyé à {email}")

    except Exception as e:
        app.logger.error(f"❌ Erreur d'envoi email : {str(e)}", exc_info=True)


def send_calendly_reminder(email: str):
    try:
        app.logger.info(f"\n=== Création lien Calendly pour {email} ===")

        headers = {
            "Authorization": f"Bearer {CALENDLY_API_KEY}",
            "Content-Type": "application/json",
            "Calendly-API-Version": "2024-05-01"
        }

        # Récupération de l'UUID une seule fois
        event_uuid = get_calendly_event_uuid()
        payload = {
            "max_event_count": 1,
            "owner": f"https://api.calendly.com/event_types/{event_uuid}",
            "owner_type": "EventType"
        }

        response = requests.post(
            "https://api.calendly.com/scheduling_links",
            headers=headers,
            json=payload
        )

        if response.status_code == 201:
            calendly_link = response.json()["resource"]["booking_url"]
            send_email(email, calendly_link)
        else:
            app.logger.error(f"Erreur Calendly {response.status_code} : {response.text}")

    except Exception as e:
        app.logger.error(f"Erreur globale Calendly : {str(e)}", exc_info=True)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    try:
        app.logger.info("\n=== NOUVELLE REQUÊTE RECUE ===")

        # Vérification du Content-Type
        if not request.is_json:
            content_type = request.headers.get('Content-Type', '')
            app.logger.error(f"❌ Content-Type non supporté : {content_type}")
            return jsonify({"error": "Unsupported Media Type"}), 415

        # Parsing et validation des données
        try:
            data = request.get_json()
        except Exception as e:
            app.logger.error(f"❌ Erreur de parsing JSON : {str(e)}")
            return jsonify({"error": "Invalid JSON format"}), 400

        # Logging des données
        app.logger.debug("Headers : %s", dict(request.headers))
        app.logger.debug("Body brut : %s", request.get_data().decode('utf-8', errors='replace'))
        app.logger.debug("Données parsées : %s", json.dumps(data, indent=2))

        # Validation des champs obligatoires
        required_fields = ['name', 'email']
        missing_fields = [f for f in required_fields if f not in data]
        if missing_fields:
            return jsonify({"error": f"Champs manquants: {', '.join(missing_fields)}"}), 400

        # Sauvegarde Airtable
        airtable_response = create_airtable_record(data)
        if not airtable_response:
            return jsonify({"error": "Erreur d'enregistrement Airtable"}), 500

        # Envoi email immédiat
        try:
            template = env.get_template('email_bienvenue.html')
            html_content = template.render(
                name=data['name'],
                message=data.get('message', '')
            )

            msg = MIMEText(html_content, 'html')
            msg['Subject'] = "Merci pour votre demande !"
            msg['From'] = GMAIL_USER
            msg['To'] = data['email']

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(GMAIL_USER, GMAIL_PASSWORD)
                server.send_message(msg)
                app.logger.info(f"✅ Email de bienvenue envoyé à {data['email']}")

        except Exception as e:
            app.logger.error(f"❌ Erreur email de bienvenue : {str(e)}", exc_info=True)

        # Planification rappel
        run_date = datetime.now(timezone.utc) + timedelta(minutes=2)
        scheduler.add_job(
            send_calendly_reminder,
            'date',
            run_date=run_date,
            args=[data['email']],
            id=f"reminder_{data['email']}"
        )
        app.logger.info(f"📅 Rappel planifié à {run_date.isoformat()}")

        return jsonify({"status": "success"}), 200

    except Exception as e:
        app.logger.error(f"❌ Erreur globale : {str(e)}", exc_info=True)
        return jsonify({"error": "Erreur serveur"}), 500


if __name__ == '__main__':
    try:
        app.logger.info("Démarrage du serveur...")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        app.logger.info("Arrêt du serveur...")
        scheduler.shutdown()
