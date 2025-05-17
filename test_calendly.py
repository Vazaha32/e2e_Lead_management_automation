import os
import requests
from pprint import pprint
from dotenv import load_dotenv

# Chargement des variables d'environnement
load_dotenv()


# Configuration
CALENDLY_API_KEY = os.getenv('CALENDLY_API_KEY')
TEST_EMAIL = os.getenv('TEST_EMAIL')

# Vérification des variables critiques
if not CALENDLY_API_KEY:
    print("❌ CALENDLY_API_KEY manquant dans .env")
    exit(1)

HEADERS = {
    "Authorization": f"Bearer {CALENDLY_API_KEY}",
    "Content-Type": "application/json",
    "Calendly-API-Version": "2024-05-01"
}


# Étape 1: Récupérer l'Organization ID
def get_organization_id():
    try:
        response = requests.get("https://api.calendly.com/users/me", headers=HEADERS)
        response.raise_for_status()

        org_uri = response.json()['resource']['current_organization']
        org_id = org_uri.split('/')[-1]

        print(f"✅ Organization ID trouvé : {org_id}")
        return org_id

    except Exception as e:
        print(f"❌ Erreur lors de la récupération de l'Organization ID: {str(e)}")
        return None


# Étape 2: Lister les types d'événements
def list_event_types(org_id):
    try:
        # Utiliser l'URI complète pour l'organisation
        org_uri = f"https://api.calendly.com/organizations/{org_id}"

        params = {
            "organization": org_uri,
            "active": True  # Booléen au lieu de chaîne
        }

        response = requests.get(
            "https://api.calendly.com/event_types",
            headers=HEADERS,
            params=params
        )

        # Debugging : afficher l'URL appelée
        print(f"\n📡 URL appelée : {response.request.url}")

        response.raise_for_status()

        response_data = response.json()
        events = response_data.get('collection', [])

        if not events:
            print("\nℹ️ Aucun événement actif trouvé dans Calendly")
            return None

        print("\n📅 Événements disponibles :")
        for event in events:
            print(f"- {event['name']} (UUID: {event['uri'].split('/')[-1]})")

        return events[0]['uri'].split('/')[-1]

    except requests.exceptions.HTTPError as e:
        print(f"\n❌ Erreur HTTP {e.response.status_code}:")
        print("Réponse complète :", e.response.text)
        return None
    except Exception as e:
        print(f"❌ Erreur lors du listing des événements: {str(e)}")
        return None

# Étape 3: Générer un lien de rendez-vous
def create_scheduling_link(event_uuid, email):
    try:
        payload = {
            "max_event_count": 1,
            "owner": f"https://api.calendly.com/event_types/{event_uuid}",
            "owner_type": "EventType"
        }

        response = requests.post(
            "https://api.calendly.com/scheduling_links",
            headers=HEADERS,
            json=payload
        )
        response.raise_for_status()

        link = response.json()['resource']['booking_url']
        print(f"\n🎉 Lien Calendly généré : {link}")
        return link

    except Exception as e:
        print(f"❌ Erreur lors de la création du lien: {str(e)}")
        return None


# Exécution pas à pas
if __name__ == "__main__":
    print("=== Début du test Calendly ===")

    if not TEST_EMAIL:
        print("⚠️ TEST_EMAIL non défini dans .env, utilisation d'une valeur par défaut")
        TEST_EMAIL = "test@example.com"

    # 1. Authentification
    org_id = get_organization_id()
    if not org_id:
        exit(1)

    # 2. Choix de l'événement
    event_uuid = list_event_types(org_id)
    if not event_uuid:
        exit(1)

    # 3. Génération du lien
    test_email = "votre@email.test"  # ← Mettez un email de test
    link = create_scheduling_link(event_uuid, test_email)

    if link:
        print("\n🔥 Test réussi ! Vérifiez que :")
        print("- Vous voyez le lien dans la console")
        print("- Le lien fonctionne dans le navigateur")
        print("- Un email de confirmation est reçu (si configuré dans Calendly)")
    else:
        print("\n💥 Test échoué. Vérifiez :")
        print("- La validité du token API")
        print("- Les permissions de l'événement dans Calendly")
        print("- Que l'événement est actif")