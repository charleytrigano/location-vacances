"""
Script d'envoi automatique de messages via BREVO
- Emails J-1 et J+1
- Intégration Supabase
- Prêt à utiliser avec GitHub Actions
"""

import os
from datetime import datetime, timedelta
from supabase import create_client
import requests
import json

# =====================================================================
# CONFIGURATION - À REMPLIR AVEC VOS CLÉS
# =====================================================================

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'YOUR_SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', 'YOUR_SUPABASE_KEY')
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', 'YOUR_BREVO_API_KEY')

# Votre email d'expéditeur (doit être validé dans Brevo)
SENDER_EMAIL = "charley@trigano.org"
SENDER_NAME = "Gestion Locations"

# Email pour recevoir les alertes
ALERT_EMAIL = "charley@trigano.org"  # ← VOTRE EMAIL ICI
ALERT_NAME = "Vous"

# =====================================================================
# INITIALISATION
# =====================================================================

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_brevo_headers():
    """Headers pour l'API Brevo"""
    return {
        'accept': 'application/json',
        'api-key': BREVO_API_KEY,
        'content-type': 'application/json'
    }

# =====================================================================
# GÉNÉRATION DES MESSAGES
# =====================================================================

def generer_message_j_moins_1(reservation, propriete, langue='fr'):
    ville = propriete.get('ville', 'Nice')
    """Génère le message J-1 avec signature gestionnaire"""
    
    gestionnaire = propriete.get('gestionnaire_nom', 'L\'équipe')
    gestionnaire_email = propriete.get('gestionnaire_email', '')
    gestionnaire_tel = propriete.get('gestionnaire_telephone', '')
    
    # Créer la signature
    signature = f"\n\nCordialement,\n{gestionnaire}"
    if gestionnaire_email:
        signature += f"\n📧 {gestionnaire_email}"
    if gestionnaire_tel:
        signature += f"\n📞 {gestionnaire_tel}"
    
    messages = {
        'fr': {
            'subject': f"Bienvenue - Arrivée demain à {propriete['nom']}",
            'html': f"""
            <h2>🏠 {propriete['nom']}</h2>
            <p><strong>📱 Plateforme :</strong> {reservation['plateforme']}<br>
            <strong>📅 Arrivée :</strong> {reservation['date_arrivee']}<br>
            <strong>📅 Départ :</strong> {reservation['date_depart']}<br>
            <strong>🌙 Nuitées :</strong> {reservation['nuitees']}</p>
            
            <p>Bonjour {reservation['nom_client']},</p>
            
            <p>Bienvenue chez nous ! 🌟</p>
            
            <p>Nous sommes ravis de vous accueillir bientôt à {ville}. Afin d'organiser au mieux votre réception, 
            nous vous demandons de bien vouloir nous indiquer votre heure d'arrivée.</p>
            
            <p>🅿️ Un parking est à votre disposition sur place.</p>
            
            <p><strong>⏰ Check-in :</strong> à partir de 14:00<br>
            <strong>⏰ Check-out :</strong> avant 11:00</p>
            
            <p>🔑 Nous serons sur place lors de votre arrivée pour vous remettre les clés.</p>
            
            <p>🎒 Vous trouverez des consignes à bagages dans chaque quartier, à {ville}.</p>
            
            <p>Nous vous souhaitons un excellent voyage et nous nous réjouissons de vous rencontrer très bientôt ! ✈️</p>
            
            <p>{signature.replace(chr(10), '<br>')}</p>
            """
        },
        'en': {
            'subject': f"Welcome - Arrival tomorrow at {propriete['nom']}",
            'html': f"""
            <h2>🏠 {propriete['nom']}</h2>
            <p><strong>📱 Platform:</strong> {reservation['plateforme']}<br>
            <strong>📅 Arrival:</strong> {reservation['date_arrivee']}<br>
            <strong>📅 Departure:</strong> {reservation['date_depart']}<br>
            <strong>🌙 Nights:</strong> {reservation['nuitees']}</p>
            
            <p>Hello {reservation['nom_client']},</p>
            
            <p>Welcome! 🌟</p>
            
            <p>We are delighted to welcome you soon to {ville}. To best organize your reception, 
            please let us know your arrival time.</p>
            
            <p>🅿️ Parking is available on site.</p>
            
            <p><strong>⏰ Check-in:</strong> from 2:00 PM<br>
            <strong>⏰ Check-out:</strong> before 11:00 AM</p>
            
            <p>🔑 We will be on site when you arrive to hand you the keys.</p>
            
            <p>🎒 You will find luggage storage in every neighborhood in {ville}.</p>
            
            <p>We wish you an excellent trip and look forward to meeting you very soon! ✈️</p>
            
            <p>{signature.replace(chr(10), '<br>')}</p>
            """
        }
    }
    
    return messages.get(langue, messages['fr'])

def generer_message_j_plus_1(reservation, propriete, langue='fr'):
    ville = propriete.get('ville', 'Nice')
    """Génère le message J+1 avec signature gestionnaire"""
    
    gestionnaire = propriete.get('gestionnaire_nom', 'L\'équipe')
    gestionnaire_email = propriete.get('gestionnaire_email', '')
    gestionnaire_tel = propriete.get('gestionnaire_telephone', '')
    
    signature = f"\n\nCordialement,\n{gestionnaire}"
    if gestionnaire_email:
        signature += f"\n📧 {gestionnaire_email}"
    if gestionnaire_tel:
        signature += f"\n📞 {gestionnaire_tel}"
    
    messages = {
        'fr': {
            'subject': f"Merci pour votre séjour - {propriete['nom']}",
            'html': f"""
            <h2>🏠 {propriete['nom']}</h2>
            
            <p>Bonjour {reservation['nom_client']},</p>
            
            <p>Un grand merci d'avoir choisi notre appartement pour votre séjour. 🙏</p>
            
            <p>Nous espérons que vous avez passé un moment agréable et que vous avez pu profiter 
            de tout ce que Nice a à offrir. ☀️</p>
            
            <p>Si vous souhaitez revenir explorer encore un peu la ville, notre porte vous sera 
            toujours grande ouverte. 🚪</p>
            
            <p>Au plaisir de vous accueillir à nouveau ! 🌟</p>
            
            <p>{signature.replace(chr(10), '<br>')}</p>
            """
        },
        'en': {
            'subject': f"Thank you for your stay - {propriete['nom']}",
            'html': f"""
            <h2>🏠 {propriete['nom']}</h2>
            
            <p>Hello {reservation['nom_client']},</p>
            
            <p>A big thank you for choosing our apartment for your stay. 🙏</p>
            
            <p>We hope you had a pleasant time and were able to enjoy everything {ville} has to offer. ☀️</p>
            
            <p>If you would like to come back and explore the city a bit more, our door will always 
            be wide open. 🚪</p>
            
            <p>Looking forward to welcoming you again! 🌟</p>
            
            <p>{signature.replace(chr(10), '<br>')}</p>
            """
        }
    }
    
    return messages.get(langue, messages['fr'])

# =====================================================================
# ENVOI EMAIL VIA BREVO
# =====================================================================

def envoyer_email_brevo(destinataire, nom_destinataire, sujet, contenu_html):
    """Envoie un email via l'API Brevo"""
    
    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = {
        "sender": {
            "name": SENDER_NAME,
            "email": SENDER_EMAIL
        },
        "to": [
            {
                "email": destinataire,
                "name": nom_destinataire
            }
        ],
        "subject": sujet,
        "htmlContent": contenu_html
    }
    
    try:
        response = requests.post(url, headers=get_brevo_headers(), data=json.dumps(payload))
        
        if response.status_code == 201:
            return True, "Email envoyé avec succès"
        else:
            return False, f"Erreur {response.status_code}: {response.text}"
    
    except Exception as e:
        return False, f"Exception: {str(e)}"

# =====================================================================
# DÉTECTION LANGUE
# =====================================================================

def detecter_langue(pays):
    """Détecte la langue depuis le pays"""
    if not pays:
        return 'fr'
    
    pays_lower = pays.lower()
    
    if any(k in pays_lower for k in ['royaume-uni', 'uk', 'united', 'états-unis', 'usa', 'canada', 'australia', 'ireland']):
        return 'en'
    elif any(k in pays_lower for k in ['espagne', 'spain', 'mexique', 'argentine', 'colombie']):
        return 'es'
    else:
        return 'fr'



# =====================================================================
# ENVOI EMAIL D'ALERTE
# =====================================================================

def envoyer_email_alerte(reservations_j1, reservations_j_plus_1):
    """Envoie un email d'alerte récapitulatif au gestionnaire"""
    
    if not reservations_j1 and not reservations_j_plus_1:
        # Pas de réservations, pas d'alerte
        return
    
    # Construire le contenu HTML
    html_content = "<h2>🔔 Alerte Réservations - SMS/WhatsApp à envoyer</h2>"
    
    # Section J-1
    if reservations_j1:
        html_content += f"<h3>📅 {len(reservations_j1)} arrivée(s) DEMAIN (J-1)</h3>"
        html_content += "<table border='1' cellpadding='10' style='border-collapse: collapse; width: 100%;'>"
        html_content += "<tr style='background-color: #f0f0f0;'><th>Client</th><th>Propriété</th><th>Téléphone</th><th>Message à envoyer</th></tr>"
        
        for res in reservations_j1:
            propriete = res.get('proprietes', {})
            ville = propriete.get('ville', 'Nice')
            gestionnaire = propriete.get('gestionnaire_nom', 'L\'équipe')
            
            # Message en français par défaut
            message_text = f"""Bonjour {res['nom_client']},

Bienvenue chez nous ! 🌟

Nous sommes ravis de vous accueillir demain à {ville}. 

Merci de nous indiquer votre heure d'arrivée.

⏰ Check-in : 14h00
⏰ Check-out : 11h00

Cordialement,
{gestionnaire}"""
            
            html_content += f"""
            <tr>
                <td><strong>{res['nom_client']}</strong></td>
                <td>{propriete.get('nom', 'N/A')} ({ville})</td>
                <td><strong>{res.get('telephone', 'N/A')}</strong></td>
                <td><pre style='white-space: pre-wrap; font-family: Arial;'>{message_text}</pre></td>
            </tr>
            """
        
        html_content += "</table><br><br>"
    
    # Section J+1
    if reservations_j_plus_1:
        html_content += f"<h3>👋 {len(reservations_j_plus_1)} départ(s) HIER (J+1)</h3>"
        html_content += "<table border='1' cellpadding='10' style='border-collapse: collapse; width: 100%;'>"
        html_content += "<tr style='background-color: #f0f0f0;'><th>Client</th><th>Propriété</th><th>Téléphone</th><th>Message à envoyer</th></tr>"
        
        for res in reservations_j_plus_1:
            propriete = res.get('proprietes', {})
            ville = propriete.get('ville', 'Nice')
            gestionnaire = propriete.get('gestionnaire_nom', 'L\'équipe')
            
            message_text = f"""Bonjour {res['nom_client']},

Merci d'avoir séjourné chez nous ! 🙏

Nous espérons que vous avez passé un agréable moment à {ville}. ☀️

Au plaisir de vous accueillir à nouveau !

Cordialement,
{gestionnaire}"""
            
            html_content += f"""
            <tr>
                <td><strong>{res['nom_client']}</strong></td>
                <td>{propriete.get('nom', 'N/A')} ({ville})</td>
                <td><strong>{res.get('telephone', 'N/A')}</strong></td>
                <td><pre style='white-space: pre-wrap; font-family: Arial;'>{message_text}</pre></td>
            </tr>
            """
        
        html_content += "</table>"
    
    # Instructions
    html_content += """
    <br><br>
    <div style='background-color: #fff3cd; padding: 15px; border-radius: 5px;'>
        <h4>📱 Comment envoyer :</h4>
        <ol>
            <li><strong>WhatsApp</strong> : Copiez le message et collez dans WhatsApp</li>
            <li><strong>SMS</strong> : Copiez le message et collez dans Messages</li>
            <li><strong>Téléphone</strong> : Cliquez sur le numéro pour appeler</li>
        </ol>
    </div>
    """
    
    # Sujet de l'email
    nb_total = len(reservations_j1) + len(reservations_j_plus_1)
    subject = f"🔔 {nb_total} message(s) SMS/WhatsApp à envoyer"
    
    # Envoyer l'alerte
    url = "https://api.brevo.com/v3/smtp/email"
    
    payload = {
        "sender": {
            "name": SENDER_NAME,
            "email": SENDER_EMAIL
        },
        "to": [
            {
                "email": ALERT_EMAIL,
                "name": ALERT_NAME
            }
        ],
        "subject": subject,
        "htmlContent": html_content
    }
    
    try:
        response = requests.post(url, headers=get_brevo_headers(), data=json.dumps(payload))
        
        if response.status_code == 201:
            print(f"✅ Alerte envoyée à {ALERT_EMAIL}")
            return True
        else:
            print(f"❌ Erreur envoi alerte : {response.status_code}")
            return False
    
    except Exception as e:
        print(f"❌ Exception envoi alerte : {str(e)}")
        return False

# =====================================================================
# ENVOI MESSAGES J-1
# =====================================================================

def envoyer_messages_j_moins_1():
    """Envoie les messages J-1 (veille d'arrivée)"""
    
    print("\n" + "="*60)
    print("📧 ENVOI MESSAGES J-1 (AVANT ARRIVÉE)")
    print("="*60)
    
    # Date de demain
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        # Récupérer les réservations avec propriétés
        response = supabase.table('reservations') \
            .select('*, proprietes(nom, ville, gestionnaire_nom, gestionnaire_email, gestionnaire_telephone)') \
            .eq('date_arrivee', tomorrow) \
            .execute()
        
        reservations = response.data
        
        # RETOURNER les réservations pour l'alerte
        return reservations if reservations else []
        
        if not reservations:
            print(f"ℹ️  Aucune arrivée demain ({tomorrow})")
            return
        
        print(f"📅 {len(reservations)} arrivée(s) demain : {tomorrow}")
        print()
        
        nb_envoyes = 0
        nb_erreurs = 0
        
        for res in reservations:
            client = res['nom_client']
            email = res.get('email')
            
            if not email:
                print(f"⚠️  {client} : Pas d'email")
                nb_erreurs += 1
                continue
            
            # Récupérer la propriété
            propriete = res.get('proprietes', {})
            if not propriete:
                print(f"⚠️  {client} : Propriété introuvable")
                nb_erreurs += 1
                continue
            
            # Détecter la langue
            langue = detecter_langue(res.get('pays'))
            
            # Générer le message
            message = generer_message_j_moins_1(res, propriete, langue)
            
            # Envoyer
            print(f"📧 Envoi à {client} ({email}) en {langue.upper()}...")
            success, msg = envoyer_email_brevo(email, client, message['subject'], message['html'])
            
            if success:
                print(f"   ✅ {msg}")
                nb_envoyes += 1
                
                # Marquer comme envoyé
                try:
                    supabase.table('reservations') \
                        .update({'sms_envoye': True}) \
                        .eq('id', res['id']) \
                        .execute()
                except:
                    pass
            else:
                print(f"   ❌ {msg}")
                nb_erreurs += 1
        
        print()
        print(f"📊 Résumé : {nb_envoyes} envoyés, {nb_erreurs} erreurs")
        
    except Exception as e:
        print(f"❌ Erreur globale : {e}")

# =====================================================================
# ENVOI MESSAGES J+1
# =====================================================================

def envoyer_messages_j_plus_1():
    """Envoie les messages J+1 (lendemain de départ)"""
    
    print("\n" + "="*60)
    print("📧 ENVOI MESSAGES J+1 (APRÈS DÉPART)")
    print("="*60)
    
    # Date d'hier
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        # Récupérer les réservations
        response = supabase.table('reservations') \
            .select('*, proprietes(nom, ville, gestionnaire_nom, gestionnaire_email, gestionnaire_telephone)') \
            .eq('date_depart', yesterday) \
            .execute()
        
        reservations = response.data
        
        # RETOURNER les réservations pour l'alerte
        return reservations if reservations else []
        
        # Filtrer ceux qui n'ont pas encore reçu le message
        reservations_a_traiter = []
        for res in reservations:
            # Vérifier si le message J+1 a déjà été envoyé (vous pouvez ajouter une colonne pour ça)
            reservations_a_traiter.append(res)
        
        if not reservations_a_traiter:
            print(f"ℹ️  Aucun départ hier ({yesterday}) ou tous déjà traités")
            return
        
        print(f"📅 {len(reservations_a_traiter)} départ(s) hier : {yesterday}")
        print()
        
        nb_envoyes = 0
        nb_erreurs = 0
        
        for res in reservations_a_traiter:
            client = res['nom_client']
            email = res.get('email')
            
            if not email:
                print(f"⚠️  {client} : Pas d'email")
                nb_erreurs += 1
                continue
            
            propriete = res.get('proprietes', {})
            if not propriete:
                print(f"⚠️  {client} : Propriété introuvable")
                nb_erreurs += 1
                continue
            
            langue = detecter_langue(res.get('pays'))
            message = generer_message_j_plus_1(res, propriete, langue)
            
            print(f"📧 Envoi à {client} ({email}) en {langue.upper()}...")
            success, msg = envoyer_email_brevo(email, client, message['subject'], message['html'])
            
            if success:
                print(f"   ✅ {msg}")
                nb_envoyes += 1
            else:
                print(f"   ❌ {msg}")
                nb_erreurs += 1
        
        print()
        print(f"📊 Résumé : {nb_envoyes} envoyés, {nb_erreurs} erreurs")
        
    except Exception as e:
        print(f"❌ Erreur globale : {e}")

# =====================================================================
# MAIN
# =====================================================================

if __name__ == '__main__':
    print("🚀 SCRIPT D'ENVOI AUTOMATIQUE - BREVO")
    print(f"📆 Date : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # J-1 : Messages avant arrivée
    reservations_j1 = envoyer_messages_j_moins_1()
    
    # J+1 : Messages après départ
    reservations_j_plus_1 = envoyer_messages_j_plus_1()
    
    # Envoyer l'alerte récapitulative pour SMS/WhatsApp
    print("\n" + "="*60)
    print("🔔 ENVOI ALERTE SMS/WHATSAPP")
    print("="*60)
    
    if reservations_j1 or reservations_j_plus_1:
        envoyer_email_alerte(reservations_j1, reservations_j_plus_1)
    else:
        print("ℹ️  Aucune alerte à envoyer (pas de réservations)")
    
    print("\n✅ Script terminé !")
