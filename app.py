import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client, Client
import calendar
import requests
from icalendar import Calendar as iCalendar

# Initialiser session_state pour la suppression
if 'delete_mode' not in st.session_state:
    st.session_state.delete_mode = False
if 'delete_res_id' not in st.session_state:
    st.session_state.delete_res_id = None

# ==================== CONFIGURATION ====================
st.set_page_config(
    page_title="Gestion Locations Vacances",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé - MODE SOMBRE ADAPTÉ
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #a78bfa;
        padding-bottom: 1rem;
        border-bottom: 3px solid #7c3aed;
    }
    /* KPIs adaptés au mode sombre */
    .stMetric {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%) !important;
        padding: 1.2rem !important;
        border-radius: 10px !important;
        border: 2px solid rgba(124, 58, 237, 0.4) !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
    }
    .stMetric label {
        color: #a5b4fc !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #e0e7ff !important;
        font-size: 2.2rem !important;
        font-weight: 700 !important;
    }
    .stMetric [data-testid="stMetricDelta"] {
        color: #c7d2fe !important;
    }
</style>
""", unsafe_allow_html=True)

# ==================== CONNEXION SUPABASE ====================
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# ==================== FONCTIONS DATA ====================
@st.cache_data(ttl=300)
def get_proprietes():
    try:
        response = supabase.table('proprietes').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erreur chargement propriétés: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)
def get_reservations():
    try:
        response = supabase.table('reservations').select('*').order('date_arrivee', desc=True).execute()
        df = pd.DataFrame(response.data)
        if not df.empty:
            df['date_arrivee'] = pd.to_datetime(df['date_arrivee'])
            df['date_depart'] = pd.to_datetime(df['date_depart'])
        return df
    except Exception as e:
        st.error(f"Erreur chargement réservations: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_plateformes():
    try:
        response = supabase.table('plateformes').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Erreur chargement plateformes: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_indicatifs():
    """Charger les indicatifs pays"""
    try:
        response = supabase.table('indicatifs_pays').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

def detecter_pays_depuis_telephone(telephone):
    """Détecte le pays depuis le numéro de téléphone - VERSION ROBUSTE"""
    if not telephone or pd.isna(telephone) or str(telephone).strip() == '':
        return None
    
    # Nettoyer le numéro
    tel_clean = str(telephone).replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
    
    if len(tel_clean) < 2:
        return None
    
    # Charger les indicatifs avec gestion d'erreur
    try:
        indicatifs_df = get_indicatifs()
    except Exception:
        return None
    
    # VÉRIFICATIONS DE SÉCURITÉ
    if indicatifs_df is None or indicatifs_df.empty:
        return None
    
    if 'indicatif' not in indicatifs_df.columns or 'pays' not in indicatifs_df.columns:
        return None
    
    # Essayer les indicatifs du plus long au plus court
    for longueur in [4, 3, 2, 1]:
        if len(tel_clean) >= longueur:
            prefix = tel_clean[:longueur]
            try:
                match = indicatifs_df[indicatifs_df['indicatif'] == prefix]
                if not match.empty:
                    return match.iloc[0]['pays']
            except Exception:
                continue
    
    return None

def calculer_taux_occupation(reservations_df, annee, mois=None, propriete_id=None):
    """Calcule le taux d'occupation en excluant 'fermeture'"""
    if reservations_df.empty:
        return 0.0
    
    df = reservations_df.copy()
    
    # Filtrer par année
    df = df[df['date_arrivee'].dt.year == annee]
    
    # Filtrer par mois si spécifié
    if mois:
        df = df[df['date_arrivee'].dt.month == mois]
    
    # Filtrer par propriété si spécifié
    if propriete_id:
        df = df[df['propriete_id'] == propriete_id]
    
    # EXCLURE FERMETURE
    df = df[df['plateforme'].str.upper() != 'FERMETURE']
    
    # Calculer les nuitées totales
    total_nuitees = df['nuitees'].sum()
    
    # Calculer le nombre de jours dans la période
    if mois:
        jours_periode = calendar.monthrange(annee, mois)[1]
    else:
        jours_periode = 366 if calendar.isleap(annee) else 365
    
    # Calculer le taux
    if jours_periode > 0:
        taux = (total_nuitees / jours_periode) * 100
        return round(taux, 1)
    
    return 0.0


def refresh_data():
    """Forcer le rafraîchissement des données"""
    st.cache_data.clear()


# ==================== CHARGEMENT DES DONNÉES ====================
# Charger les données UNE SEULE FOIS au tout début


# ==================== FONCTIONS iCAL ====================

def parse_ical(url):
    """Télécharge et parse un fichier iCal avec extraction améliorée des noms"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        cal = iCalendar.from_ical(response.content)
        reservations = []
        
        for component in cal.walk():
            if component.name == "VEVENT":
                summary = str(component.get('summary', 'Réservation'))
                dtstart = component.get('dtstart').dt
                dtend = component.get('dtend').dt
                uid = str(component.get('uid', ''))
                
                if hasattr(dtstart, 'date'):
                    date_arrivee = dtstart.date()
                else:
                    date_arrivee = dtstart
                
                if hasattr(dtend, 'date'):
                    date_depart = dtend.date()
                else:
                    date_depart = dtend
                
                nuitees = (date_depart - date_arrivee).days
                
                # PARSING AMÉLIORÉ DU SUMMARY
                nom_client = 'Client plateforme'
                
                # Format : "Villa Tobias — Marc Bruyere (Airbnb)"
                if '—' in summary or '–' in summary:
                    parts = summary.replace('–', '—').split('—')
                    if len(parts) >= 2:
                        client_part = parts[1].strip()
                        if '(' in client_part:
                            nom_client = client_part.split('(')[0].strip()
                        else:
                            nom_client = client_part
                
                # Format : "Marc Bruyere (Airbnb)"
                elif '(' in summary and ')' in summary:
                    nom_client = summary.split('(')[0].strip()
                
                # Format : Nom simple
                elif summary not in ['Reserved', 'Réservé', 'Not available', 'Indisponible', 
                                    'Blocked', 'Bloqué', 'Unavailable']:
                    nom_client = summary.strip()
                
                if not nom_client or len(nom_client) < 2:
                    nom_client = 'Client plateforme'
                
                nom_client = nom_client.replace('\n', ' ').strip()
                
                reservations.append({
                    'ical_uid': uid,
                    'nom_client': nom_client,
                    'date_arrivee': date_arrivee,
                    'date_depart': date_depart,
                    'nuitees': nuitees
                })
        
        return reservations, None
    
    except Exception as e:
        return [], str(e)


def sync_ical_to_supabase(propriete_id, plateforme, ical_url, supabase):
    """Synchronise un flux iCal vers Supabase"""
    reservations, error = parse_ical(ical_url)
    
    if error:
        return 0, 0, 0, f"Erreur: {error}"
    
    if not reservations:
        return 0, 0, 0, "Aucune réservation dans le flux iCal"
    
    existing = supabase.table('reservations').select('*').eq('propriete_id', propriete_id).execute()
    existing_df = pd.DataFrame(existing.data) if existing.data else pd.DataFrame()
    
    nb_importees = 0
    nb_mises_a_jour = 0
    nb_conflits = 0
    
    for res in reservations:
        if not existing_df.empty and 'ical_uid' in existing_df.columns:
            match = existing_df[existing_df['ical_uid'] == res['ical_uid']]
            
            if not match.empty:
                existing_res = match.iloc[0]
                if (str(existing_res['date_arrivee'])[:10] != str(res['date_arrivee']) or
                    str(existing_res['date_depart'])[:10] != str(res['date_depart'])):
                    
                    supabase.table('reservations').update({
                        'date_arrivee': str(res['date_arrivee']),
                        'date_depart': str(res['date_depart']),
                        'nuitees': res['nuitees']
                    }).eq('id', existing_res['id']).execute()
                    
                    nb_mises_a_jour += 1
                continue
        
        if not existing_df.empty:
            conflits = existing_df[
                (pd.to_datetime(existing_df['date_arrivee']).dt.date < res['date_depart']) &
                (pd.to_datetime(existing_df['date_depart']).dt.date > res['date_arrivee']) &
                (existing_df['ical_uid'] != res['ical_uid'])
            ]
            
            if not conflits.empty:
                nb_conflits += 1
        
        new_res = {
            'propriete_id': propriete_id,
            'ical_uid': res['ical_uid'],
            'nom_client': res['nom_client'],
            'date_arrivee': str(res['date_arrivee']),
            'date_depart': str(res['date_depart']),
            'nuitees': res['nuitees'],
            'plateforme': plateforme,
            'prix_brut': 0,
            'prix_net': 0,
            'commissions': 0,
            'frais_cb': 0,
            'commissions_hote': 0,
            'menage': 0,
            'taxes_sejour': 0,
            'base': 0,
            'charges': 0,
            'pct_commission': 0,
            'paye': False,
            'sms_envoye': False,
            'post_depart_envoye': False
        }
        
        try:
            supabase.table('reservations').insert(new_res).execute()
            nb_importees += 1
        except:
            pass
    
    try:
        supabase.table('ical_sync_logs').insert({
            'propriete_id': propriete_id,
            'plateforme': plateforme,
            'nb_reservations_importees': nb_importees,
            'nb_reservations_mises_a_jour': nb_mises_a_jour,
            'nb_conflits': nb_conflits,
            'statut': 'success' if nb_importees > 0 or nb_mises_a_jour > 0 else 'no_changes',
            'message': f'{nb_importees} importées, {nb_mises_a_jour} mises à jour, {nb_conflits} conflits'
        }).execute()
    except:
        pass
    
    supabase.table('proprietes').update({
        'ical_last_sync': datetime.now().isoformat()
    }).eq('id', propriete_id).execute()
    
    message = f"✅ {nb_importees} importées, {nb_mises_a_jour} mises à jour"
    if nb_conflits > 0:
        message += f", ⚠️ {nb_conflits} conflits"
    
    return nb_importees, nb_mises_a_jour, nb_conflits, message


def sync_all_properties(supabase, proprietes_df):
    """Synchronise toutes les propriétés"""
    results = []
    
    for idx, prop in proprietes_df.iterrows():
        if not prop.get('ical_auto_sync', False):
            continue
        
        if prop.get('ical_url_airbnb'):
            nb_imp, nb_maj, nb_conf, msg = sync_ical_to_supabase(
                prop['id'], 'Airbnb', prop['ical_url_airbnb'], supabase
            )
            results.append({
                'propriete': prop['nom'],
                'plateforme': 'Airbnb',
                'importees': nb_imp,
                'mises_a_jour': nb_maj,
                'conflits': nb_conf,
                'message': msg
            })
        
        if prop.get('ical_url_booking'):
            nb_imp, nb_maj, nb_conf, msg = sync_ical_to_supabase(
                prop['id'], 'Booking', prop['ical_url_booking'], supabase
            )
            results.append({
                'propriete': prop['nom'],
                'plateforme': 'Booking',
                'importees': nb_imp,
                'mises_a_jour': nb_maj,
                'conflits': nb_conf,
                'message': msg
            })
    
    return results



def get_reservation_url(numero_reservation, plateforme, propriete_id):
    """Génère l'URL directe vers la réservation"""
    if not numero_reservation:
        return None
    if plateforme and plateforme.upper() == "AIRBNB":
        return f"https://www.airbnb.fr/hosting/reservations/details/{numero_reservation}"
    elif plateforme and plateforme.upper() == "BOOKING":
        hotel_ids = {1: "1844114", 2: "1120418"}
        hotel_id = hotel_ids.get(propriete_id, "1844114")
        return f"https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?lang=fr&ses=6665fb4bb26afe2fdc73efe8436e4697&res_id={numero_reservation}&hotel_id={hotel_id}"
    return None

def afficher_lien_reservation(numero, plateforme, propriete_id):
    """Affiche un lien cliquable vers la réservation"""
    if numero:
        url = get_reservation_url(numero, plateforme, propriete_id)
        if url:
            icon = "🔵" if plateforme and plateforme.upper() == "AIRBNB" else "🟠"
            st.markdown(f"[{icon} Voir sur {plateforme}]({url})")
            st.caption(f"N° {numero}")
            return True
    return False



reservations_df = get_reservations()
proprietes_df = get_proprietes()

# ==================== SIDEBAR ====================

st.sidebar.markdown("# 🏖️ Locations Vacances")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    ["📊 Tableau de Bord", "📅 Calendrier", "📋 Réservations", 
     "💰 Analyses Financières", "✉️ Messages", "🏠 Propriétés", "🔄 Synchronisation iCal", "🔧 Paramètres"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rafraîchir les données"):
    refresh_data()
    st.rerun()

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)

    # ==================== ALERTES J-1 / J+1 ====================
    st.markdown("### 🔔 Alertes Contacts")
    
    # Vérifier que les données sont disponibles
    if reservations_df.empty or proprietes_df.empty:
        st.info("ℹ️ Chargez des données pour voir les alertes")
        st.divider()
    else:
        # Récupérer les réservations J-1 et J+1
        today = datetime.now().date()
        tomorrow = today + timedelta(days=1)
        yesterday = today - timedelta(days=1)
        
        reservations_j1 = reservations_df[reservations_df['date_arrivee'].dt.date == tomorrow].copy()
        reservations_j_plus_1 = reservations_df[reservations_df['date_depart'].dt.date == yesterday].copy()
        
        # Fusionner avec propriétés
        reservations_j1 = reservations_j1.merge(
            proprietes_df[['id', 'nom', 'ville', 'gestionnaire_nom', 'gestionnaire_email', 'gestionnaire_telephone']], 
            left_on='propriete_id', right_on='id', 
            how='left', suffixes=('', '_prop'))
        
        reservations_j_plus_1 = reservations_j_plus_1.merge(
            proprietes_df[['id', 'nom', 'ville', 'gestionnaire_nom', 'gestionnaire_email', 'gestionnaire_telephone']], 
            left_on='propriete_id', right_on='id', 
            how='left', suffixes=('', '_prop'))
        
        # Afficher les alertes
        if not reservations_j1.empty or not reservations_j_plus_1.empty:
            
            # Alertes J-1
            if not reservations_j1.empty:
                st.warning(f"⚠️ **{len(reservations_j1)} arrivée(s) DEMAIN** - Messages SMS/WhatsApp à envoyer")
                
                for idx, client in reservations_j1.iterrows():
                    with st.expander(f"📅 {client['nom_client']} - {client.get('nom', 'Propriété')} - Arrivée demain", expanded=True):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.markdown(f"""
                            **👤 Client** : {client['nom_client']}  
                            **🏠 Propriété** : {client.get('nom', 'N/A')}  
                            **📍 Ville** : {client.get('ville', 'Nice')}  
                            **📱 Téléphone** : `{client.get('telephone', 'Non renseigné')}`  
                            **📅 Arrivée** : {client['date_arrivee'].strftime('%d/%m/%Y')}  
                            **📅 Départ** : {client['date_depart'].strftime('%d/%m/%Y')}
                            """)
                        
                        with col2:
                            ville = client.get('ville', 'Nice')
                            gestionnaire = client.get('gestionnaire_nom', 'L\'équipe')
                            gestionnaire_email = client.get('gestionnaire_email', '')
                            gestionnaire_tel = client.get('gestionnaire_telephone', '')
                            
                            signature = f"\n\nCordialement,\n{gestionnaire}"
                            if gestionnaire_email:
                                signature += f"\n📧 {gestionnaire_email}"
                            if gestionnaire_tel:
                                signature += f"\n📞 {gestionnaire_tel}"
                            
                            message_whatsapp = f"""Bonjour {client['nom_client']},

Bienvenue chez nous ! 🌟

Nous sommes ravis de vous accueillir demain à {ville}.

Merci de nous indiquer votre heure d'arrivée.

⏰ Check-in : à partir de 14h00
⏰ Check-out : avant 11h00

🔑 Nous serons sur place pour vous remettre les clés.{signature}"""
                            
                            st.text_area(
                                "📱 Message à copier pour WhatsApp/SMS",
                                message_whatsapp,
                                height=300,
                                key=f"msg_j1_{client['id']}"
                            )
                            
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                if client.get('telephone'):
                                    st.markdown(f"[📱 WhatsApp](https://wa.me/{client['telephone'].replace('+', '').replace(' ', '')})")
                            with col_b:
                                if client.get('telephone'):
                                    st.markdown(f"[💬 SMS](sms:{client['telephone']})")
                            with col_c:
                                st.info("💡 Copiez le message")
            
            # Alertes J+1
            if not reservations_j_plus_1.empty:
                st.info(f"👋 **{len(reservations_j_plus_1)} départ(s) HIER** - Messages de remerciement")
                
                for idx, client in reservations_j_plus_1.iterrows():
                    with st.expander(f"👋 {client['nom_client']} - {client.get('nom', 'Propriété')} - Parti hier", expanded=False):
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.markdown(f"""
                            **👤 Client** : {client['nom_client']}  
                            **🏠 Propriété** : {client.get('nom', 'N/A')}  
                            **📍 Ville** : {client.get('ville', 'Nice')}  
                            **📱 Téléphone** : `{client.get('telephone', 'Non renseigné')}`  
                            **📅 Départ** : {client['date_depart'].strftime('%d/%m/%Y')}
                            """)
                        
                        with col2:
                            ville = client.get('ville', 'Nice')
                            gestionnaire = client.get('gestionnaire_nom', 'L\'équipe')
                            gestionnaire_email = client.get('gestionnaire_email', '')
                            gestionnaire_tel = client.get('gestionnaire_telephone', '')
                            
                            signature = f"\n\nCordialement,\n{gestionnaire}"
                            if gestionnaire_email:
                                signature += f"\n📧 {gestionnaire_email}"
                            if gestionnaire_tel:
                                signature += f"\n📞 {gestionnaire_tel}"
                            
                            message_whatsapp = f"""Bonjour {client['nom_client']},

Un grand merci d'avoir choisi notre appartement ! 🙏

Nous espérons que vous avez passé un moment agréable à {ville}. ☀️

Au plaisir de vous accueillir à nouveau ! 🌟{signature}"""
                            
                            st.text_area(
                                "📱 Message à copier pour WhatsApp/SMS",
                                message_whatsapp,
                                height=250,
                                key=f"msg_j_plus_1_{client['id']}"
                            )
                            
                            col_a, col_b, col_c = st.columns(3)
                            with col_a:
                                if client.get('telephone'):
                                    st.markdown(f"[📱 WhatsApp](https://wa.me/{client['telephone'].replace('+', '').replace(' ', '')})")
                            with col_b:
                                if client.get('telephone'):
                                    st.markdown(f"[💬 SMS](sms:{client['telephone']})")
                            with col_c:
                                st.info("💡 Copiez le message")
            
            st.divider()
        
        else:
            st.success("✅ Aucune alerte - Pas de réservation J-1 ou J+1 aujourd'hui")
            st.divider()
    

    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        annee_sel = st.selectbox("📅 Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True))
    
    with col2:
        prop_df = proprietes_df if not proprietes_df.empty else pd.DataFrame({'id': [], 'nom': []})
        prop_list = ['Toutes'] + prop_df['nom'].tolist()
        prop_sel = st.selectbox("🏠 Propriété", prop_list)
    
    # Filtrer les données
    df_filtered = reservations_df[reservations_df['date_arrivee'].dt.year == annee_sel].copy()
    if prop_sel != 'Toutes':
        prop_id = prop_df[prop_df['nom'] == prop_sel]['id'].iloc[0]
        df_filtered = df_filtered[df_filtered['propriete_id'] == prop_id]
    
    # Exclure les périodes de fermeture
    df_filtered = df_filtered[df_filtered['plateforme'].str.upper() != 'FERMETURE']
    
    st.divider()
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    nb_reservations = len(df_filtered)
    total_nuitees = df_filtered['nuitees'].sum()
    revenu_net = df_filtered['prix_net'].sum()
    total_commissions = df_filtered['commissions'].sum()
    taux_paye = (df_filtered['paye'].sum() / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
    
    # CALCUL TAUX D'OCCUPATION (EXCLUT FERMETURE)
    prop_id_calc = prop_id if prop_sel != 'Toutes' else None
    taux_occ = calculer_taux_occupation(reservations_df, annee_sel, propriete_id=prop_id_calc)
    
    with col1:
        st.metric("📅 Réservations", f"{nb_reservations}")
    with col2:
        st.metric("🌙 Nuitées", f"{int(total_nuitees)}")
    with col3:
        st.metric("💰 Revenu Net", f"{revenu_net:,.0f} €")
    with col4:
        st.metric("💸 Commissions", f"{total_commissions:,.0f} €")
    with col5:
        st.metric("✅ Taux payé", f"{taux_paye:.0f}%")
    with col6:
        st.metric("📊 Taux occupation", f"{taux_occ}%")
    
    st.divider()
    
    # Graphiques
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Revenus par plateforme")
        revenus_plateforme = df_filtered.groupby('plateforme')['prix_net'].sum().reset_index()
        revenus_plateforme = revenus_plateforme.sort_values('prix_net', ascending=False)
        fig = px.bar(revenus_plateforme, x='plateforme', y='prix_net',
                    color='prix_net', color_continuous_scale='Blues',
                    labels={'prix_net': 'Revenu (€)', 'plateforme': 'Plateforme'})
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("🥧 Répartition réservations")
        repartition = df_filtered.groupby('plateforme').size().reset_index(name='count')
        fig = px.pie(repartition, values='count', names='plateforme',
                    title='Par plateforme')
        st.plotly_chart(fig, use_container_width=True)
    
    # Évolution mensuelle
    st.subheader(f"📈 Évolution mensuelle {annee_sel}")
    df_filtered['mois'] = df_filtered['date_arrivee'].dt.month
    evolution = df_filtered.groupby('mois').agg({
        'prix_net': 'sum',
        'nuitees': 'sum',
        'id': 'count'
    }).reset_index()
    evolution['mois_nom'] = evolution['mois'].apply(lambda x: calendar.month_name[x])
    
    fig = go.Figure()
    fig.add_trace(go.Bar(name='Revenus', x=evolution['mois_nom'], y=evolution['prix_net'], marker_color='lightblue'))
    fig.add_trace(go.Scatter(name='Nuitées', x=evolution['mois_nom'], y=evolution['nuitees'], yaxis='y2', 
                            mode='lines+markers', marker_color='orange', line=dict(width=3)))
    fig.update_layout(
        yaxis=dict(title='Revenus (€)'),
        yaxis2=dict(title='Nuitées', overlaying='y', side='right'),
        hovermode='x unified'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Prochaines arrivées
    st.subheader("📅 Prochaines arrivées")
    today = pd.Timestamp.now()
    prochaines = df_filtered[df_filtered['date_arrivee'] >= today].nsmallest(10, 'date_arrivee')
    if not prochaines.empty and not proprietes_df.empty:
        prochaines = prochaines.merge(proprietes_df[['id', 'nom']], left_on='propriete_id', right_on='id', how='left')
        display_cols = ['date_arrivee', 'date_depart', 'nom', 'nom_client', 'plateforme', 'nuitees', 'prix_net', 'paye']
        prochaines_display = prochaines[display_cols].copy()
        prochaines_display['date_arrivee'] = prochaines_display['date_arrivee'].dt.strftime('%d/%m/%Y')
        prochaines_display['date_depart'] = prochaines_display['date_depart'].dt.strftime('%d/%m/%Y')
        prochaines_display.columns = ['Arrivée', 'Départ', 'Propriété', 'Client', 'Plateforme', 'Nuitées', 'Prix net (€)', 'Payé']
        st.dataframe(prochaines_display, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune arrivée prévue")


# ==================== CALENDRIER ====================
elif menu == "📅 Calendrier":
    st.markdown("<h1 class='main-header'>📅 Calendrier des Réservations</h1>", unsafe_allow_html=True)
    
    # reservations_df = get_reservations()
    # proprietes_df = get_proprietes()
    
    if reservations_df.empty or proprietes_df.empty:
        st.warning("⚠️ Aucune donnée")
        st.stop()
    
    # Sélection propriété
    prop_list = proprietes_df['nom'].tolist()
    prop_sel = st.selectbox("🏠 Propriété", prop_list)
    prop_id = proprietes_df[proprietes_df['nom'] == prop_sel]['id'].iloc[0]
    
    # Sélection mois
    col1, col2 = st.columns(2)
    with col1:
        mois_sel = st.selectbox("Mois", range(1, 13), 
                                format_func=lambda x: calendar.month_name[x],
                                index=datetime.now().month - 1)
    with col2:
        annee_sel = st.number_input("Année", min_value=2020, max_value=2030, 
                                    value=datetime.now().year)
    
    # Filtrer réservations
    df_prop = reservations_df[reservations_df['propriete_id'] == prop_id].copy()
    
    # Créer le calendrier
    cal = calendar.monthcalendar(annee_sel, mois_sel)
    mois_nom = calendar.month_name[mois_sel]
    
    st.subheader(f"{mois_nom} {annee_sel} - {prop_sel}")
    
    # En-têtes jours
    cols = st.columns(7)
    jours = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    for i, jour in enumerate(jours):
        cols[i].markdown(f"**{jour}**")
    
    # Semaines
    for semaine in cal:
        cols = st.columns(7)
        for i, jour in enumerate(semaine):
            if jour == 0:
                cols[i].write("")
            else:
                date_check = datetime(annee_sel, mois_sel, jour).date()
                occupations = df_prop[
                    (df_prop['date_arrivee'].dt.date <= date_check) & 
                    (df_prop['date_depart'].dt.date > date_check)
                ]
                
                if not occupations.empty:
                    res = occupations.iloc[0]
                    
                    # Récupérer la couleur de la plateforme
                    plateformes_df = get_plateformes()
                    couleur = '#ffcccb'  # Couleur par défaut (rouge clair)
                    if not plateformes_df.empty and 'couleur' in plateformes_df.columns:
                        plat_match = plateformes_df[plateformes_df['nom_plateforme'].str.upper() == str(res['plateforme']).upper()]
                        if not plat_match.empty:
                            couleur = plat_match.iloc[0]['couleur']
                    
                    # Générer l'URL si numéro existe
                    url = get_reservation_url(
                        res.get('numero_reservation'),
                        res['plateforme'],
                        res['propriete_id']
                    ) if res.get('numero_reservation') else None
                    
                    # HTML avec ou sans lien
                    if url:
                        cols[i].markdown(f"""
                        <a href='{url}' target='_blank' style='text-decoration: none;'>
                            <div style='background-color: {couleur}; padding: 5px; border-radius: 5px; text-align: center; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.5); cursor: pointer; transition: transform 0.2s;' 
                                 onmouseover='this.style.transform="scale(1.05)"' 
                                 onmouseout='this.style.transform="scale(1)"'>
                                <b style='font-size: 1.1em;'>{jour}</b><br>
                                <small style='font-size: 0.75em;'>{res['nom_client'][:12]}</small><br>
                                <small style='font-size: 0.65em; opacity: 0.9;'>{res['plateforme']}</small><br>
                                <small style='font-size: 0.6em;'>🔗 Clic</small>
                            </div>
                        </a>
                        """, unsafe_allow_html=True)
                    else:
                        cols[i].markdown(f"""
                        <div style='background-color: {couleur}; padding: 5px; border-radius: 5px; text-align: center; color: white; text-shadow: 1px 1px 2px rgba(0,0,0,0.5);'>
                            <b style='font-size: 1.1em;'>{jour}</b><br>
                            <small style='font-size: 0.75em;'>{res['nom_client'][:12]}</small><br>
                            <small style='font-size: 0.65em; opacity: 0.9;'>{res['plateforme']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    cols[i].markdown(f"""
                    <div style='background-color: #90EE90; padding: 5px; border-radius: 5px; text-align: center;'>
                        <b>{jour}</b><br>
                        <small>Libre</small>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Légende
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("🟢 **Libre** : Disponible à la location")
    with col2:
        st.markdown("🔴 **Occupé** : Déjà réservé")
    
    # Liste des réservations du mois
    st.divider()
    st.subheader("Réservations du mois")
    debut_mois = datetime(annee_sel, mois_sel, 1)
    fin_mois = datetime(annee_sel, mois_sel, calendar.monthrange(annee_sel, mois_sel)[1])
    
    res_mois = df_prop[
        (df_prop['date_arrivee'] <= fin_mois) & 
        (df_prop['date_depart'] >= pd.Timestamp(debut_mois))
    ].copy()
    
    if not res_mois.empty:
        res_mois = res_mois.sort_values('date_arrivee')
        display_df = res_mois[['date_arrivee', 'date_depart', 'nom_client', 'plateforme', 'nuitees', 'prix_net', 'paye']].copy()
        display_df['date_arrivee'] = display_df['date_arrivee'].dt.strftime('%d/%m/%Y')
        display_df['date_depart'] = display_df['date_depart'].dt.strftime('%d/%m/%Y')
        display_df.columns = ['Arrivée', 'Départ', 'Client', 'Plateforme', 'Nuitées', 'Prix (€)', 'Payé']
        # Affichage détaillé avec liens
        for idx, res in res_mois.iterrows():
            with st.expander(f"📅 {res['date_arrivee'].strftime('%d/%m')} - {res['date_depart'].strftime('%d/%m')} | {res['nom_client']} ({res['plateforme']})", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Nuitées", res['nuitees'])
                with col2:
                    st.metric("Prix net", f"{res['prix_net']:.0f} €")
                with col3:
                    statut = "✅ Payé" if res['paye'] else "⏳ En attente"
                    st.write(f"**Statut:** {statut}")
                
                # Lien vers la plateforme
                if res.get('numero_reservation'):
                    st.divider()
                    st.markdown("**🔗 Accès plateforme**")
                    afficher_lien_reservation(res['numero_reservation'], res['plateforme'], res['propriete_id'])
    else:
        st.info("Aucune réservation ce mois-ci")

# ==================== RÉSERVATIONS ====================
elif menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Gestion des Réservations</h1>", unsafe_allow_html=True)
    
    # reservations_df = get_reservations()
    # proprietes_df = get_proprietes()
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Nouvelle réservation", "✏️ Modifier/Supprimer"])
    
    # TAB 1: LISTE
    with tab1:
        if reservations_df.empty:
            st.info("Aucune réservation")
        else:
            # Filtres
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                annees = ['Toutes'] + sorted(reservations_df['date_arrivee'].dt.year.unique().tolist(), reverse=True)
                annee_filter = st.selectbox("Année", annees)
            with col2:
                props = ['Toutes'] + proprietes_df['nom'].tolist() if not proprietes_df.empty else ['Toutes']
                prop_filter = st.selectbox("Propriété", props)
            with col3:
                plateformes = ['Toutes'] + sorted(reservations_df['plateforme'].dropna().unique().tolist())
                plat_filter = st.selectbox("Plateforme", plateformes)
            with col4:
                statut_filter = st.selectbox("Statut paiement", ['Tous', 'Payé', 'Non payé'])
            
            # Appliquer filtres
            df_display = reservations_df.copy()
            
            if annee_filter != 'Toutes':
                df_display = df_display[df_display['date_arrivee'].dt.year == int(annee_filter)]
            
            if prop_filter != 'Toutes' and not proprietes_df.empty:
                prop_id = proprietes_df[proprietes_df['nom'] == prop_filter]['id'].iloc[0]
                df_display = df_display[df_display['propriete_id'] == prop_id]
            
            if plat_filter != 'Toutes':
                df_display = df_display[df_display['plateforme'] == plat_filter]
            
            if statut_filter == 'Payé':
                df_display = df_display[df_display['paye'] == True]
            elif statut_filter == 'Non payé':
                df_display = df_display[df_display['paye'] == False]
            
            # Recherche
            search = st.text_input("🔍 Rechercher (nom client)")
            if search:
                df_display = df_display[df_display['nom_client'].str.contains(search, case=False, na=False)]
            
            st.info(f"📊 {len(df_display)} réservation(s) trouvée(s)")
            
            # Affichage
            if not df_display.empty:
                if not proprietes_df.empty:
                    df_display = df_display.merge(proprietes_df[['id', 'nom']], left_on='propriete_id', right_on='id', how='left', suffixes=('', '_prop'))
                    display_cols = ['date_arrivee', 'date_depart', 'nom', 'nom_client', 'email', 'plateforme', 
                                   'nuitees', 'prix_brut', 'prix_net', 'paye']
                else:
                    display_cols = ['date_arrivee', 'date_depart', 'nom_client', 'email', 'plateforme', 
                                   'nuitees', 'prix_brut', 'prix_net', 'paye']
                
                df_show = df_display[display_cols].copy()
                df_show['date_arrivee'] = df_show['date_arrivee'].dt.strftime('%d/%m/%Y')
                df_show['date_depart'] = df_show['date_depart'].dt.strftime('%d/%m/%Y')
                
                if not proprietes_df.empty:
                    df_show.columns = ['Arrivée', 'Départ', 'Propriété', 'Client', 'Email', 'Plateforme', 
                                      'Nuitées', 'Prix brut', 'Prix net', 'Payé']
                else:
                    df_show.columns = ['Arrivée', 'Départ', 'Client', 'Email', 'Plateforme', 
                                      'Nuitées', 'Prix brut', 'Prix net', 'Payé']
                
                st.dataframe(df_show, use_container_width=True, hide_index=True)
                
                # Export
                csv = df_show.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Exporter CSV", data=csv, 
                                 file_name=f"reservations_{datetime.now().strftime('%Y%m%d')}.csv",
                                 mime="text/csv")
    
    # TAB 2: NOUVELLE RÉSERVATION
    with tab2:
        st.subheader("Nouvelle réservation")
        
        if proprietes_df.empty:
            st.warning("Aucune propriété enregistrée")
        else:
            st.markdown("### 👤 Informations client")
            col1, col2 = st.columns(2)
            
            with col1:
                propriete_id = st.selectbox("Propriété *", proprietes_df['id'].tolist(),
                                           format_func=lambda x: proprietes_df[proprietes_df['id']==x]['nom'].iloc[0],
                                           key="new_prop")
                nom_client = st.text_input("Nom client *", key="new_nom")
                email = st.text_input("Email", key="new_email")
                
            with col2:
                telephone = st.text_input("Téléphone", key="new_tel")
                
                # DÉTECTION AUTOMATIQUE DU PAYS
                pays_detecte = None
                if telephone:
                    pays_detecte = detecter_pays_depuis_telephone(telephone)
                    if pays_detecte:
                        st.success(f"🌍 Pays détecté : **{pays_detecte}**")
                
                pays = st.text_input("Pays", value=pays_detecte if pays_detecte else "", key="new_pays")
                
                # PLATEFORMES DYNAMIQUES
                plateformes_df_form = get_plateformes()
                if not plateformes_df_form.empty:
                    liste_plateformes = sorted(plateformes_df_form['nom_plateforme'].unique().tolist())
                else:
                    liste_plateformes = ['Direct', 'Airbnb', 'Booking']
                plateforme = st.selectbox("Plateforme", liste_plateformes, key="new_plat")
                
                numero_reservation = st.text_input("Numéro de réservation (optionnel)", help="Ex: HM5NRPTHKB ou 3366732357", key="new_num")
                
            
            st.markdown("### 📅 Dates")
            col1, col2 = st.columns(2)
            with col1:
                date_arrivee = st.date_input("Date d'arrivée *", key="new_arr")
            with col2:
                date_depart = st.date_input("Date de départ *", key="new_dep")
            
            st.markdown("### 💰 Détails financiers")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                prix_brut = st.number_input("Prix brut (€) *", min_value=0.0, step=10.0, value=0.0, key="new_brut")
                commissions = st.number_input("Commissions (€)", min_value=0.0, step=1.0, value=0.0, key="new_com")
                frais_cb = st.number_input("Frais CB (€)", min_value=0.0, step=1.0, value=0.0, key="new_cb")
            
            with col2:
                commissions_hote = st.number_input("Commissions hôte (€)", min_value=0.0, step=1.0, value=0.0, key="new_comh")
                menage = st.number_input("Ménage (€)", min_value=0.0, step=5.0, value=50.0, key="new_menage")
                taxes_sejour = st.number_input("Taxes de séjour (€)", min_value=0.0, step=1.0, value=0.0, key="new_tax")
            
            with col3:
                # Calculs automatiques EN TEMPS RÉEL
                prix_net_calc = prix_brut - commissions - frais_cb
                base_calc = prix_net_calc - menage - taxes_sejour
                charges_calc = prix_brut - prix_net_calc
                pct_commissions_calc = ((commissions + frais_cb + commissions_hote) / prix_brut * 100) if prix_brut > 0 else 0
                
                st.metric("💰 Prix net", f"{prix_net_calc:.2f} €", 
                         help="Prix brut - Commissions - Frais CB")
                st.metric("📊 Base", f"{base_calc:.2f} €",
                         help="Prix net - Ménage - Taxes séjour")
                st.metric("📈 Charges", f"{charges_calc:.2f} €",
                         help="Total des commissions et frais")
                st.metric("📉 % Commission", f"{pct_commissions_calc:.1f}%",
                         help="(Commissions + Frais CB + Com hôte) / Prix brut × 100")
            
            st.markdown("### ✅ Statut")
            col1, col2 = st.columns(2)
            with col1:
                paye = st.checkbox("Déjà payé", key="new_paye")
            with col2:
                sms_envoye = st.checkbox("SMS envoyé", key="new_sms")
            
            st.divider()
            
            # Bouton de création HORS du form pour permettre les calculs dynamiques
            if st.button("✅ Créer la réservation", type="primary", use_container_width=True):
                if not nom_client:
                    st.error("❌ Le nom du client est obligatoire")
                elif date_depart <= date_arrivee:
                    st.error("❌ La date de départ doit être après la date d'arrivée")
                elif prix_brut <= 0:
                    st.error("❌ Le prix brut doit être supérieur à 0")
                else:
                    nuitees = (date_depart - date_arrivee).days
                    
                    # Calculs finaux (déjà calculés au-dessus)
                    prix_net = prix_net_calc
                    base = base_calc
                    charges = charges_calc
                    pct_commission = pct_commissions_calc
                    
                    nouvelle_res = {
                        'propriete_id': propriete_id,
                        'nom_client': nom_client,
                        'email': email if email else None,
                        'telephone': telephone if telephone else None,
                        'pays': pays if pays else None,
                        'date_arrivee': date_arrivee.strftime('%Y-%m-%d'),
                        'date_depart': date_depart.strftime('%Y-%m-%d'),
                        'nuitees': nuitees,
                        'plateforme': plateforme,
                        'prix_brut': round(prix_brut, 2),
                        'commissions': round(commissions, 2),
                        'frais_cb': round(frais_cb, 2),
                        'commissions_hote': round(commissions_hote, 2),
                        'prix_net': round(prix_net, 2),
                        'menage': round(menage, 2),
                        'taxes_sejour': round(taxes_sejour, 2),
                        'base': round(base, 2),
                        'charges': round(charges, 2),
                        'pct_commission': round(pct_commission, 2),
                        'paye': paye,
                        'sms_envoye': sms_envoye,
                        'post_depart_envoye': False
                    }
                    
                    try:
                        supabase.table('reservations').insert(nouvelle_res).execute()
                        st.success(f"""
                        ✅ **Réservation créée avec succès !**
                        
                        **📊 Résumé financier** :
                        - Prix brut : {prix_brut:.2f} €
                        - Commissions totales : {commissions + frais_cb + commissions_hote:.2f} €
                        - Prix net : {prix_net:.2f} €
                        - Ménage + Taxes : {menage + taxes_sejour:.2f} €
                        - **Base (votre profit) : {base:.2f} €**
                        
                        🌙 Durée : {nuitees} nuitée(s)
                        """)
                        refresh_data()
                        st.rerun()
                    except Exception as e:
                        error_msg = str(e)
                        if 'duplicate key' in error_msg and 'reservations_pkey' in error_msg:
                            st.error("""
                            ❌ **Erreur : ID dupliquée**
                            
                            La séquence d'auto-incrémentation n'est pas à jour.
                            
                            **Solution rapide (30 secondes)** :
                            1. Ouvrez **Supabase** → **SQL Editor**
                            2. Copiez-collez cette ligne :
                            ```sql
                            SELECT setval('reservations_id_seq', (SELECT MAX(id) FROM reservations) + 1);
                            ```
                            3. Cliquez **RUN**
                            4. Réessayez de créer la réservation
                            
                            **Pourquoi ?** Vous avez probablement importé un CSV avec des IDs existants.
                            La séquence Supabase n'a pas été mise à jour automatiquement.
                            """)
                        else:
                            st.error(f"❌ Erreur lors de la création : {error_msg}")
            
            # Aide
            with st.expander("💡 Aide - Comprendre les calculs"):
                st.markdown("""
                ### Formules automatiques :
                
                **Prix net** = Prix brut - Commissions - Frais CB  
                → C'est ce que vous recevez réellement
                
                **Base** = Prix net - Ménage - Taxes de séjour  
                → C'est votre profit final
                
                **Charges** = Prix brut - Prix net  
                → Total des commissions et frais
                
                **% Commission** = (Commissions + Frais CB + Com hôte) / Prix brut × 100  
                → Pourcentage total des frais
                
                ### Exemple concret :
                - Client paye **1,000 €** (prix brut)
                - Airbnb prend **180 €** (commissions)
                - Frais CB **10 €**
                - → Vous recevez **810 €** (prix net)
                - Ménage **50 €**, Taxes **32 €**
                - → **Il vous reste 728 €** (base = votre profit)
                """)
    
    # TAB 3: MODIFIER/SUPPRIMER
    with tab3:
        st.subheader("✏️ Modifier ou Supprimer une réservation")
        
        if reservations_df.empty:
            st.info("Aucune réservation à modifier")
        else:
            # Recherche de la réservation
            st.markdown("### 🔍 Rechercher la réservation")
            
            col1, col2 = st.columns(2)
            with col1:
                search_nom = st.text_input("Nom du client", key="search_modify")
            with col2:
                if not proprietes_df.empty:
                    prop_options = ['Toutes'] + proprietes_df['nom'].tolist()
                    prop_search = st.selectbox("Propriété", prop_options, key="prop_modify")
                else:
                    prop_search = 'Toutes'
            
            # Filtrer les réservations
            df_search = reservations_df.copy()
            if search_nom:
                df_search = df_search[df_search['nom_client'].str.contains(search_nom, case=False, na=False)]
            if prop_search != 'Toutes' and not proprietes_df.empty:
                prop_id = proprietes_df[proprietes_df['nom'] == prop_search]['id'].iloc[0]
                df_search = df_search[df_search['propriete_id'] == prop_id]
            
            if df_search.empty:
                st.info("Aucune réservation trouvée avec ces critères")
            else:
                st.success(f"✅ {len(df_search)} réservation(s) trouvée(s)")
                
                # Sélection de la réservation à modifier
                if not proprietes_df.empty:
                    df_search = df_search.merge(proprietes_df[['id', 'nom']], 
                                               left_on='propriete_id', right_on='id', 
                                               how='left', suffixes=('', '_prop'))
                    display_col = 'nom'
                else:
                    display_col = None
                
                # Créer une liste pour la sélection
                options = []
                for idx, row in df_search.iterrows():
                    prop_name = row[display_col] if display_col and display_col in row else f"ID {row['propriete_id']}"
                    label = f"{row['nom_client']} - {prop_name} - {row['date_arrivee'].strftime('%d/%m/%Y')} → {row['date_depart'].strftime('%d/%m/%Y')}"
                    options.append((label, row['id']))
                
                selected = st.selectbox(
                    "Sélectionnez la réservation à modifier/supprimer",
                    options,
                    format_func=lambda x: x[0],
                    key="select_res"
                )
                
                if selected:
                    res_id = selected[1]
                    reservation = reservations_df[reservations_df['id'] == res_id].iloc[0]
                    
                    st.divider()
                    
                    # Actions
                    action_col1, action_col2 = st.columns(2)
                    with action_col1:
                        modifier_mode = st.button("✏️ Modifier cette réservation", type="primary", use_container_width=True)
                    with action_col2:
                        supprimer_mode = st.button("🗑️ Supprimer cette réservation", type="secondary", use_container_width=True)
                    
                    # MODIFICATION
                    if modifier_mode:
                        st.markdown("### ✏️ Modifier la réservation")
                        
                        with st.form("form_modifier"):
                            st.markdown("#### 👤 Informations client")
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if not proprietes_df.empty:
                                    current_prop_idx = proprietes_df[proprietes_df['id'] == reservation['propriete_id']].index[0]
                                    new_propriete_id = st.selectbox("Propriété *", proprietes_df['id'].tolist(),
                                                                   index=current_prop_idx,
                                                                   format_func=lambda x: proprietes_df[proprietes_df['id']==x]['nom'].iloc[0],
                                                                   key="mod_prop")
                                else:
                                    new_propriete_id = reservation['propriete_id']
                                
                                new_nom_client = st.text_input("Nom client *", value=reservation['nom_client'], key="mod_nom")
                                new_email = st.text_input("Email", value=reservation['email'] if pd.notna(reservation['email']) else "", key="mod_email")
                            
                            with col2:
                                new_telephone = st.text_input("Téléphone", value=reservation['telephone'] if pd.notna(reservation['telephone']) else "", key="mod_tel")
                                
                                # DÉTECTION AUTOMATIQUE DU PAYS
                                pays_detecte_mod = None
                                if new_telephone:
                                    pays_detecte_mod = detecter_pays_depuis_telephone(new_telephone)
                                    if pays_detecte_mod:
                                        st.success(f"🌍 Pays détecté : **{pays_detecte_mod}**")
                                
                                pays_initial = reservation['pays'] if pd.notna(reservation['pays']) else ""
                                new_pays = st.text_input("Pays", value=pays_detecte_mod if pays_detecte_mod else pays_initial, key="mod_pays")
                                
                                # PLATEFORMES DYNAMIQUES
                                plateformes_df_mod = get_plateformes()
                                if not plateformes_df_mod.empty:
                                    liste_plateformes_mod = sorted(plateformes_df_mod['nom_plateforme'].unique().tolist())
                                    current_plat_idx = 0
                                    if reservation['plateforme'] in liste_plateformes_mod:
                                        current_plat_idx = liste_plateformes_mod.index(reservation['plateforme'])
                                else:
                                    liste_plateformes_mod = ['Direct', 'Airbnb', 'Booking']
                                    current_plat_idx = 0
                                
                                new_plateforme = st.selectbox("Plateforme", liste_plateformes_mod,
                                                             index=current_plat_idx,
                                                             key="mod_plat")
                            
                            st.markdown("#### 📅 Dates")
                            col1, col2 = st.columns(2)
                            with col1:
                                new_date_arrivee = st.date_input("Date d'arrivée *", value=reservation['date_arrivee'].date(), key="mod_arr")
                            with col2:
                                new_date_depart = st.date_input("Date de départ *", value=reservation['date_depart'].date(), key="mod_dep")
                            
                            st.markdown("#### 💰 Détails financiers")
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                new_prix_brut = st.number_input("Prix brut (€) *", min_value=0.0, step=10.0, value=float(reservation['prix_brut']), key="mod_brut")
                                new_commissions = st.number_input("Commissions (€)", min_value=0.0, step=1.0, value=float(reservation['commissions']) if pd.notna(reservation['commissions']) else 0.0, key="mod_com")
                                new_frais_cb = st.number_input("Frais CB (€)", min_value=0.0, step=1.0, value=float(reservation['frais_cb']) if pd.notna(reservation['frais_cb']) else 0.0, key="mod_cb")
                            
                            with col2:
                                new_commissions_hote = st.number_input("Commissions hôte (€)", min_value=0.0, step=1.0, value=float(reservation['commissions_hote']) if pd.notna(reservation.get('commissions_hote', 0)) else 0.0, key="mod_comh")
                                new_menage = st.number_input("Ménage (€)", min_value=0.0, step=5.0, value=float(reservation['menage']) if pd.notna(reservation['menage']) else 50.0, key="mod_men")
                                new_taxes_sejour = st.number_input("Taxes de séjour (€)", min_value=0.0, step=1.0, value=float(reservation['taxes_sejour']) if pd.notna(reservation['taxes_sejour']) else 0.0, key="mod_tax")
                            
                            with col3:
                                # Calculs automatiques
                                new_prix_net_calc = new_prix_brut - new_commissions - new_frais_cb
                                new_base_calc = new_prix_net_calc - new_menage - new_taxes_sejour
                                new_charges_calc = new_prix_brut - new_prix_net_calc
                                new_pct_calc = ((new_commissions + new_frais_cb + new_commissions_hote) / new_prix_brut * 100) if new_prix_brut > 0 else 0
                                
                                st.metric("Prix net (auto)", f"{new_prix_net_calc:.2f} €")
                                st.metric("Base (auto)", f"{new_base_calc:.2f} €")
                                st.metric("Charges (auto)", f"{new_charges_calc:.2f} €")
                                st.metric("% Commission", f"{new_pct_calc:.2f}%")
                            
                            st.markdown("#### ✅ Statut")
                            col1, col2 = st.columns(2)
                            with col1:
                                new_paye = st.checkbox("Déjà payé", value=bool(reservation['paye']), key="mod_paye")
                            with col2:
                                new_sms_envoye = st.checkbox("SMS envoyé", value=bool(reservation.get('sms_envoye', False)), key="mod_sms")
                            
                            submitted_mod = st.form_submit_button("✅ Enregistrer les modifications", type="primary")
                            
                            if submitted_mod:
                                if not new_nom_client:
                                    st.error("Le nom du client est obligatoire")
                                elif new_date_depart <= new_date_arrivee:
                                    st.error("La date de départ doit être après la date d'arrivée")
                                else:
                                    new_nuitees = (new_date_depart - new_date_arrivee).days
                                    
                                    # Calculs finaux
                                    new_prix_net = new_prix_brut - new_commissions - new_frais_cb
                                    new_base = new_prix_net - new_menage - new_taxes_sejour
                                    new_charges = new_prix_brut - new_prix_net
                                    new_pct_commission = ((new_commissions + new_frais_cb + new_commissions_hote) / new_prix_brut * 100) if new_prix_brut > 0 else 0
                                    
                                    updated_res = {
                                        'propriete_id': new_propriete_id,
                                        'nom_client': new_nom_client,
                                        'email': new_email if new_email else None,
                                        'telephone': new_telephone if new_telephone else None,
                                        'pays': new_pays if new_pays else None,
                                        'date_arrivee': new_date_arrivee.strftime('%Y-%m-%d'),
                                        'date_depart': new_date_depart.strftime('%Y-%m-%d'),
                                        'nuitees': new_nuitees,
                                        'plateforme': new_plateforme,
                                        'prix_brut': round(new_prix_brut, 2),
                                        'commissions': round(new_commissions, 2),
                                        'frais_cb': round(new_frais_cb, 2),
                                        'commissions_hote': round(new_commissions_hote, 2),
                                        'prix_net': round(new_prix_net, 2),
                                        'menage': round(new_menage, 2),
                                        'taxes_sejour': round(new_taxes_sejour, 2),
                                        'base': round(new_base, 2),
                                        'charges': round(new_charges, 2),
                                        'pct_commission': round(new_pct_commission, 2),
                        'numero_reservation': res.get('numero_reservation', ''),
                                        'paye': new_paye,
                                        'sms_envoye': new_sms_envoye
                                    }
                                    
                                    try:
                                        supabase.table('reservations').update(updated_res).eq('id', res_id).execute()
                                        st.success("✅ Réservation modifiée avec succès !")
                                        refresh_data()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur lors de la modification : {e}")
                    
                    # SUPPRESSION
                    if supprimer_mode:
                        st.session_state.delete_mode = True
                        st.session_state.delete_res_id = res_id
                    
                    if st.session_state.delete_mode and st.session_state.delete_res_id == res_id:
                        st.markdown("### 🗑️ Supprimer la réservation")
                        st.error(f"""
                        ⚠️ **ATTENTION - SUPPRESSION DÉFINITIVE**
                        
                        Vous êtes sur le point de supprimer :
                        
                        **Client** : {reservation['nom_client']}  
                        **Dates** : {reservation['date_arrivee'].strftime('%d/%m/%Y')} → {reservation['date_depart'].strftime('%d/%m/%Y')}  
                        **Prix** : {reservation['prix_brut']:.2f} €
                        
                        ⚠️ **Cette action est IRRÉVERSIBLE !**
                        """)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("🗑️ CONFIRMER LA SUPPRESSION", type="primary", use_container_width=True, key=f"confirm_del_{res_id}"):
                                try:
                                    result = supabase.table('reservations').delete().eq('id', res_id).execute()
                                    st.session_state.delete_mode = False
                                    st.session_state.delete_res_id = None
                                    st.success("✅ Réservation supprimée !")
                                    refresh_data()
                                    import time
                                    time.sleep(0.5)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {str(e)}")
                        
                        with col2:
                            if st.button("❌ ANNULER", use_container_width=True, key=f"cancel_del_{res_id}"):
                                st.session_state.delete_mode = False
                                st.session_state.delete_res_id = None
                                st.rerun()

# ================================================================
# SECTION ANALYSES FINANCIÈRES AVEC COMPARAISONS
# ================================================================
# À remplacer dans l'app

# ==================== ANALYSES FINANCIÈRES ====================
elif menu == "💰 Analyses Financières":
    st.markdown("<h1 class='main-header'>💰 Analyses Financières</h1>", unsafe_allow_html=True)
    
    # reservations_df = get_reservations()
    # proprietes_df = get_proprietes()
    
    if reservations_df.empty:
        st.warning("Aucune réservation à analyser")
        st.stop()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Vue d'ensemble", "📈 Comparaisons Années", "📉 Comparaisons Mois", "📐 Analyses Détaillées", "🎯 Optimisation Pricing"])
    
    # TAB 1: VUE D'ENSEMBLE
    with tab1:
        st.subheader("📊 Vue d'ensemble financière")
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        with col1:
            annee_sel = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="vue_annee")
        with col2:
            if not proprietes_df.empty:
                prop_list = ['Toutes'] + proprietes_df['nom'].tolist()
                prop_sel = st.selectbox("Propriété", prop_list, key="vue_prop")
            else:
                prop_sel = 'Toutes'
        with col3:
            plateformes = ['Toutes'] + sorted(reservations_df['plateforme'].unique().tolist())
            plat_sel = st.selectbox("Plateforme", plateformes, key="vue_plat")
        
        # Filtrer les données
        df_filtered = reservations_df[reservations_df['date_arrivee'].dt.year == annee_sel].copy()
        
        if prop_sel != 'Toutes':
            prop_id = proprietes_df[proprietes_df['nom'] == prop_sel]['id'].iloc[0]
            df_filtered = df_filtered[df_filtered['propriete_id'] == prop_id]
        
        if plat_sel != 'Toutes':
            df_filtered = df_filtered[df_filtered['plateforme'] == plat_sel]
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Prix Brut Total", f"{df_filtered['prix_brut'].sum():,.0f} €")
        with col2:
            st.metric("💵 Prix Net Total", f"{df_filtered['prix_net'].sum():,.0f} €")
        with col3:
            st.metric("💸 Commissions", f"{df_filtered['commissions'].sum():,.0f} €")
        with col4:
            st.metric("🌙 Nuitées", f"{int(df_filtered['nuitees'].sum())}")
        
        st.divider()
        
        # Graphiques
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Revenus par plateforme")
            revenus_plat = df_filtered.groupby('plateforme').agg({
                'prix_brut': 'sum',
                'prix_net': 'sum'
            }).reset_index()
            
            fig = px.bar(revenus_plat, x='plateforme', y=['prix_brut', 'prix_net'],
                        barmode='group',
                        labels={'value': 'Montant (€)', 'plateforme': 'Plateforme', 'variable': 'Type'},
                        color_discrete_map={'prix_brut': '#6366f1', 'prix_net': '#10b981'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("#### 🥧 Répartition des commissions")
            fig = px.pie(df_filtered, values='commissions', names='plateforme', 
                        title='Commissions par plateforme')
            st.plotly_chart(fig, use_container_width=True)
        
        # Évolution mensuelle
        st.markdown("#### 📈 Évolution mensuelle des revenus")
        df_filtered['mois'] = df_filtered['date_arrivee'].dt.to_period('M').astype(str)
        revenus_mois = df_filtered.groupby('mois').agg({
            'prix_brut': 'sum',
            'prix_net': 'sum',
            'nuitees': 'sum'
        }).reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=revenus_mois['mois'], y=revenus_mois['prix_brut'],
                                name='Prix Brut', mode='lines+markers', line=dict(color='#6366f1', width=3)))
        fig.add_trace(go.Scatter(x=revenus_mois['mois'], y=revenus_mois['prix_net'],
                                name='Prix Net', mode='lines+markers', line=dict(color='#10b981', width=3)))
        fig.update_layout(xaxis_title='Mois', yaxis_title='Revenus (€)', hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)
    
    # TAB 2: COMPARAISONS ANNÉES
    with tab2:
        st.subheader("📈 Comparaison entre années")
        
        # Sélection des années à comparer
        annees_disponibles = sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True)
        
        if len(annees_disponibles) < 2:
            st.warning("Vous devez avoir des réservations sur au moins 2 années différentes pour effectuer des comparaisons")
        else:
            col1, col2 = st.columns(2)
            with col1:
                annee1 = st.selectbox("Année 1", annees_disponibles, key="comp_annee1")
            with col2:
                annees_restantes = [a for a in annees_disponibles if a != annee1]
                if annees_restantes:
                    annee2 = st.selectbox("Année 2", annees_restantes, key="comp_annee2")
                else:
                    st.warning("Pas d'autre année disponible")
                    annee2 = annee1
            
            # Filtres additionnels
            col1, col2 = st.columns(2)
            with col1:
                if not proprietes_df.empty:
                    prop_list = ['Toutes'] + proprietes_df['nom'].tolist()
                    prop_comp = st.selectbox("Propriété", prop_list, key="comp_prop")
                else:
                    prop_comp = 'Toutes'
            
            with col2:
                plateformes = ['Toutes'] + sorted(reservations_df['plateforme'].unique().tolist())
                plat_comp = st.selectbox("Plateforme", plateformes, key="comp_plat")
            
            # Préparer les données
            df_annee1 = reservations_df[reservations_df['date_arrivee'].dt.year == annee1].copy()
            df_annee2 = reservations_df[reservations_df['date_arrivee'].dt.year == annee2].copy()
            
            # Filtrer par propriété
            if prop_comp != 'Toutes':
                prop_id = proprietes_df[proprietes_df['nom'] == prop_comp]['id'].iloc[0]
                df_annee1 = df_annee1[df_annee1['propriete_id'] == prop_id]
                df_annee2 = df_annee2[df_annee2['propriete_id'] == prop_id]
            
            # Filtrer par plateforme
            if plat_comp != 'Toutes':
                df_annee1 = df_annee1[df_annee1['plateforme'] == plat_comp]
                df_annee2 = df_annee2[df_annee2['plateforme'] == plat_comp]
            
            # Exclure fermeture du calcul d'occupation
            df_annee1_occ = df_annee1[df_annee1['plateforme'].str.upper() != 'FERMETURE']
            df_annee2_occ = df_annee2[df_annee2['plateforme'].str.upper() != 'FERMETURE']
            
            # KPIs comparatifs
            st.markdown("### 📊 Indicateurs clés")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            nuitees1 = int(df_annee1_occ['nuitees'].sum())
            nuitees2 = int(df_annee2_occ['nuitees'].sum())
            delta_nuitees = ((nuitees2 - nuitees1) / nuitees1 * 100) if nuitees1 > 0 else 0
            
            prix_brut1 = df_annee1['prix_brut'].sum()
            prix_brut2 = df_annee2['prix_brut'].sum()
            delta_brut = ((prix_brut2 - prix_brut1) / prix_brut1 * 100) if prix_brut1 > 0 else 0
            
            prix_net1 = df_annee1['prix_net'].sum()
            prix_net2 = df_annee2['prix_net'].sum()
            delta_net = ((prix_net2 - prix_net1) / prix_net1 * 100) if prix_net1 > 0 else 0
            
            nb_res1 = len(df_annee1)
            nb_res2 = len(df_annee2)
            delta_res = ((nb_res2 - nb_res1) / nb_res1 * 100) if nb_res1 > 0 else 0
            
            taux_occ1 = calculer_taux_occupation(reservations_df, annee1, propriete_id=prop_id if prop_comp != 'Toutes' else None)
            taux_occ2 = calculer_taux_occupation(reservations_df, annee2, propriete_id=prop_id if prop_comp != 'Toutes' else None)
            delta_occ = taux_occ2 - taux_occ1
            
            with col1:
                st.metric(f"🌙 Nuitées {annee1}", f"{nuitees1}", f"{nuitees2 - nuitees1:+d} ({delta_nuitees:+.1f}%)")
            with col2:
                st.metric(f"💰 Prix Brut {annee1}", f"{prix_brut1:,.0f} €", f"{delta_brut:+.1f}%")
            with col3:
                st.metric(f"💵 Prix Net {annee1}", f"{prix_net1:,.0f} €", f"{delta_net:+.1f}%")
            with col4:
                st.metric(f"📅 Réservations {annee1}", f"{nb_res1}", f"{nb_res2 - nb_res1:+d} ({delta_res:+.1f}%)")
            with col5:
                st.metric(f"📊 Taux occup. {annee1}", f"{taux_occ1}%", f"{delta_occ:+.1f}%")
            
            st.divider()
            
            # Graphiques comparatifs
            st.markdown("### 📊 Comparaison visuelle")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Comparaison prix brut vs net
                comparison_data = pd.DataFrame({
                    'Année': [str(annee1), str(annee2)],
                    'Prix Brut': [prix_brut1, prix_brut2],
                    'Prix Net': [prix_net1, prix_net2]
                })
                
                fig = px.bar(comparison_data, x='Année', y=['Prix Brut', 'Prix Net'],
                            barmode='group',
                            title='Comparaison Prix Brut vs Prix Net',
                            labels={'value': 'Montant (€)', 'variable': 'Type'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Comparaison nuitées
                comparison_nuitees = pd.DataFrame({
                    'Année': [str(annee1), str(annee2)],
                    'Nuitées': [nuitees1, nuitees2],
                    'Taux occupation (%)': [taux_occ1, taux_occ2]
                })
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Nuitées', x=comparison_nuitees['Année'], y=comparison_nuitees['Nuitées'],
                                    marker_color='#6366f1'))
                fig.add_trace(go.Scatter(name='Taux occupation (%)', x=comparison_nuitees['Année'], 
                                        y=comparison_nuitees['Taux occupation (%)'],
                                        mode='lines+markers', yaxis='y2', line=dict(color='#f59e0b', width=3)))
                fig.update_layout(
                    title='Nuitées et Taux d\'occupation',
                    yaxis=dict(title='Nuitées'),
                    yaxis2=dict(title='Taux occupation (%)', overlaying='y', side='right')
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Comparaison par plateforme
            st.markdown("### 🏢 Comparaison par plateforme")
            
            plat_annee1 = df_annee1.groupby('plateforme').agg({
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'nuitees': 'sum'
            }).reset_index()
            plat_annee1['annee'] = str(annee1)
            
            plat_annee2 = df_annee2.groupby('plateforme').agg({
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'nuitees': 'sum'
            }).reset_index()
            plat_annee2['annee'] = str(annee2)
            
            plat_comparison = pd.concat([plat_annee1, plat_annee2])
            
            fig = px.bar(plat_comparison, x='plateforme', y='prix_net', color='annee',
                        barmode='group',
                        title='Revenus nets par plateforme',
                        labels={'prix_net': 'Revenus nets (€)', 'plateforme': 'Plateforme', 'annee': 'Année'})
            st.plotly_chart(fig, use_container_width=True)
    
    # TAB 3: COMPARAISONS MOIS
    with tab3:
        st.subheader("📉 Comparaison entre mois")
        
        # Sélection de l'année et des mois
        col1, col2, col3 = st.columns(3)
        
        with col1:
            annee_mois = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="mois_annee")
        
        df_annee = reservations_df[reservations_df['date_arrivee'].dt.year == annee_mois].copy()
        mois_disponibles = sorted(df_annee['date_arrivee'].dt.month.unique())
        
        if len(mois_disponibles) < 2:
            st.warning("Vous devez avoir des réservations sur au moins 2 mois pour effectuer des comparaisons")
        else:
            mois_noms = {1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
                        7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'}
            
            with col2:
                mois1 = st.selectbox("Mois 1", mois_disponibles, 
                                    format_func=lambda x: mois_noms[x], key="comp_mois1")
            
            with col3:
                mois_restants = [m for m in mois_disponibles if m != mois1]
                if mois_restants:
                    mois2 = st.selectbox("Mois 2", mois_restants,
                                        format_func=lambda x: mois_noms[x], key="comp_mois2")
                else:
                    st.warning("Pas d'autre mois disponible")
                    mois2 = mois1
            
            # Filtres additionnels
            col1, col2 = st.columns(2)
            with col1:
                if not proprietes_df.empty:
                    prop_list = ['Toutes'] + proprietes_df['nom'].tolist()
                    prop_mois = st.selectbox("Propriété", prop_list, key="mois_prop")
                else:
                    prop_mois = 'Toutes'
            
            with col2:
                plateformes = ['Toutes'] + sorted(reservations_df['plateforme'].unique().tolist())
                plat_mois = st.selectbox("Plateforme", plateformes, key="mois_plat")
            
            # Préparer les données
            df_mois1 = df_annee[df_annee['date_arrivee'].dt.month == mois1].copy()
            df_mois2 = df_annee[df_annee['date_arrivee'].dt.month == mois2].copy()
            
            # Filtrer
            if prop_mois != 'Toutes':
                prop_id = proprietes_df[proprietes_df['nom'] == prop_mois]['id'].iloc[0]
                df_mois1 = df_mois1[df_mois1['propriete_id'] == prop_id]
                df_mois2 = df_mois2[df_mois2['propriete_id'] == prop_id]
            
            if plat_mois != 'Toutes':
                df_mois1 = df_mois1[df_mois1['plateforme'] == plat_mois]
                df_mois2 = df_mois2[df_mois2['plateforme'] == plat_mois]
            
            # Exclure fermeture
            df_mois1_occ = df_mois1[df_mois1['plateforme'].str.upper() != 'FERMETURE']
            df_mois2_occ = df_mois2[df_mois2['plateforme'].str.upper() != 'FERMETURE']
            
            # KPIs comparatifs
            st.markdown("### 📊 Indicateurs clés")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            nuitees_m1 = int(df_mois1_occ['nuitees'].sum())
            nuitees_m2 = int(df_mois2_occ['nuitees'].sum())
            delta_nuitees_m = ((nuitees_m2 - nuitees_m1) / nuitees_m1 * 100) if nuitees_m1 > 0 else 0
            
            prix_brut_m1 = df_mois1['prix_brut'].sum()
            prix_brut_m2 = df_mois2['prix_brut'].sum()
            delta_brut_m = ((prix_brut_m2 - prix_brut_m1) / prix_brut_m1 * 100) if prix_brut_m1 > 0 else 0
            
            prix_net_m1 = df_mois1['prix_net'].sum()
            prix_net_m2 = df_mois2['prix_net'].sum()
            delta_net_m = ((prix_net_m2 - prix_net_m1) / prix_net_m1 * 100) if prix_net_m1 > 0 else 0
            
            nb_res_m1 = len(df_mois1)
            nb_res_m2 = len(df_mois2)
            delta_res_m = ((nb_res_m2 - nb_res_m1) / nb_res_m1 * 100) if nb_res_m1 > 0 else 0
            
            taux_occ_m1 = calculer_taux_occupation(reservations_df, annee_mois, mois=mois1, propriete_id=prop_id if prop_mois != 'Toutes' else None)
            taux_occ_m2 = calculer_taux_occupation(reservations_df, annee_mois, mois=mois2, propriete_id=prop_id if prop_mois != 'Toutes' else None)
            delta_occ_m = taux_occ_m2 - taux_occ_m1
            
            with col1:
                st.metric(f"🌙 {mois_noms[mois1]}", f"{nuitees_m1}", f"{nuitees_m2 - nuitees_m1:+d} ({delta_nuitees_m:+.1f}%)")
            with col2:
                st.metric(f"💰 {mois_noms[mois1]}", f"{prix_brut_m1:,.0f} €", f"{delta_brut_m:+.1f}%")
            with col3:
                st.metric(f"💵 {mois_noms[mois1]}", f"{prix_net_m1:,.0f} €", f"{delta_net_m:+.1f}%")
            with col4:
                st.metric(f"📅 {mois_noms[mois1]}", f"{nb_res_m1}", f"{nb_res_m2 - nb_res_m1:+d} ({delta_res_m:+.1f}%)")
            with col5:
                st.metric(f"📊 {mois_noms[mois1]}", f"{taux_occ_m1}%", f"{delta_occ_m:+.1f}%")
            
            st.divider()
            
            # Graphiques comparatifs
            col1, col2 = st.columns(2)
            
            with col1:
                comparison_mois = pd.DataFrame({
                    'Mois': [mois_noms[mois1], mois_noms[mois2]],
                    'Prix Brut': [prix_brut_m1, prix_brut_m2],
                    'Prix Net': [prix_net_m1, prix_net_m2]
                })
                
                fig = px.bar(comparison_mois, x='Mois', y=['Prix Brut', 'Prix Net'],
                            barmode='group',
                            title='Comparaison Prix Brut vs Prix Net')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                comparison_nuitees_m = pd.DataFrame({
                    'Mois': [mois_noms[mois1], mois_noms[mois2]],
                    'Nuitées': [nuitees_m1, nuitees_m2],
                    'Taux occupation': [taux_occ_m1, taux_occ_m2]
                })
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name='Nuitées', x=comparison_nuitees_m['Mois'], 
                                    y=comparison_nuitees_m['Nuitées']))
                fig.add_trace(go.Scatter(name='Taux occupation (%)', x=comparison_nuitees_m['Mois'],
                                        y=comparison_nuitees_m['Taux occupation'],
                                        mode='lines+markers', yaxis='y2'))
                fig.update_layout(
                    title='Nuitées et Taux d\'occupation',
                    yaxis=dict(title='Nuitées'),
                    yaxis2=dict(title='Taux (%)', overlaying='y', side='right')
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # Comparaison par plateforme
            st.markdown("### 🏢 Comparaison par plateforme")
            
            plat_mois1 = df_mois1.groupby('plateforme').agg({
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'nuitees': 'sum'
            }).reset_index()
            plat_mois1['mois'] = mois_noms[mois1]
            
            plat_mois2 = df_mois2.groupby('plateforme').agg({
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'nuitees': 'sum'
            }).reset_index()
            plat_mois2['mois'] = mois_noms[mois2]
            
            plat_comp_mois = pd.concat([plat_mois1, plat_mois2])
            
            fig = px.bar(plat_comp_mois, x='plateforme', y='prix_net', color='mois',
                        barmode='group',
                        title='Revenus nets par plateforme',
                        labels={'prix_net': 'Revenus nets (€)', 'plateforme': 'Plateforme', 'mois': 'Mois'})
            st.plotly_chart(fig, use_container_width=True)



    
    # TAB 4: ANALYSES DÉTAILLÉES
    with tab4:
        st.subheader("📐 Analyses Détaillées")
        
        # Filtres
        col1, col2, col3 = st.columns(3)
        with col1:
            periode_type = st.selectbox("Type de période", ["Mois", "Trimestre", "Année"], key="detail_periode")
        with col2:
            if periode_type == "Année":
                annees_dispo = sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True)
                periode_sel = st.selectbox("Année", annees_dispo, key="detail_annee")
            elif periode_type == "Trimestre":
                annee_tri = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="detail_annee_tri")
                periode_sel = (annee_tri, st.selectbox("Trimestre", ["Q1", "Q2", "Q3", "Q4"], key="detail_tri"))
            else:  # Mois
                annee_mois = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="detail_annee_mois")
                mois_noms = {1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
                           7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'}
                mois_dispo = sorted(reservations_df[reservations_df['date_arrivee'].dt.year == annee_mois]['date_arrivee'].dt.month.unique())
                if mois_dispo:
                    periode_sel = (annee_mois, st.selectbox("Mois", mois_dispo, format_func=lambda x: mois_noms[x], key="detail_mois"))
                else:
                    st.warning("Pas de données pour cette année")
                    st.stop()
        
        with col3:
            if not proprietes_df.empty:
                prop_list = ['Toutes'] + proprietes_df['nom'].tolist()
                prop_detail = st.selectbox("Propriété", prop_list, key="detail_prop")
            else:
                prop_detail = 'Toutes'
        
        # Filtrer les données selon la période
        df_periode = reservations_df.copy()
        
        if periode_type == "Année":
            df_periode = df_periode[df_periode['date_arrivee'].dt.year == periode_sel]
            titre_periode = f"Année {periode_sel}"
        elif periode_type == "Trimestre":
            annee_tri, trimestre = periode_sel
            trimestre_map = {"Q1": [1, 2, 3], "Q2": [4, 5, 6], "Q3": [7, 8, 9], "Q4": [10, 11, 12]}
            mois_tri = trimestre_map[trimestre]
            df_periode = df_periode[
                (df_periode['date_arrivee'].dt.year == annee_tri) &
                (df_periode['date_arrivee'].dt.month.isin(mois_tri))
            ]
            titre_periode = f"{trimestre} {annee_tri}"
        else:  # Mois
            annee_mois, mois = periode_sel
            df_periode = df_periode[
                (df_periode['date_arrivee'].dt.year == annee_mois) &
                (df_periode['date_arrivee'].dt.month == mois)
            ]
            mois_noms = {1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
                       7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'}
            titre_periode = f"{mois_noms[mois]} {annee_mois}"
        
        # Filtrer par propriété
        if prop_detail != 'Toutes':
            prop_id = proprietes_df[proprietes_df['nom'] == prop_detail]['id'].iloc[0]
            df_periode = df_periode[df_periode['propriete_id'] == prop_id]
        
        # Exclure fermeture
        df_periode = df_periode[df_periode['plateforme'].str.upper() != 'FERMETURE']
        
        if df_periode.empty:
            st.warning(f"Aucune réservation pour {titre_periode}")
        else:
            st.markdown(f"### 📊 Analyses pour : **{titre_periode}**")
            
            # ========== DURÉE MOYENNE DE SÉJOUR ==========
            st.markdown("#### 🕐 Durée Moyenne de Séjour")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Durée moyenne globale
                duree_moyenne_globale = df_periode['nuitees'].mean()
                duree_mediane = df_periode['nuitees'].median()
                duree_min = df_periode['nuitees'].min()
                duree_max = df_periode['nuitees'].max()
                
                st.metric("Durée moyenne (toutes plateformes)", f"{duree_moyenne_globale:.1f} nuits")
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Médiane", f"{duree_mediane:.0f} nuits")
                with col_b:
                    st.metric("Min", f"{int(duree_min)} nuits")
                with col_c:
                    st.metric("Max", f"{int(duree_max)} nuits")
            
            with col2:
                # Distribution des durées
                duree_counts = df_periode['nuitees'].value_counts().sort_index()
                fig = px.bar(x=duree_counts.index, y=duree_counts.values,
                           labels={'x': 'Nombre de nuits', 'y': 'Nombre de réservations'},
                           title='Distribution des durées de séjour')
                st.plotly_chart(fig, use_container_width=True)
            
            # Durée moyenne par plateforme
            st.markdown("##### 📊 Durée moyenne par plateforme")
            duree_par_plateforme = df_periode.groupby('plateforme').agg({
                'nuitees': ['mean', 'median', 'count']
            }).round(1)
            duree_par_plateforme.columns = ['Moyenne (nuits)', 'Médiane (nuits)', 'Nb réservations']
            duree_par_plateforme = duree_par_plateforme.sort_values('Moyenne (nuits)', ascending=False)
            
            col1, col2 = st.columns([1, 1])
            with col1:
                st.dataframe(duree_par_plateforme, use_container_width=True)
            
            with col2:
                fig = px.bar(duree_par_plateforme, y=duree_par_plateforme.index, x='Moyenne (nuits)',
                           orientation='h',
                           title='Durée moyenne par plateforme',
                           labels={'Moyenne (nuits)': 'Nuits', 'index': 'Plateforme'})
                st.plotly_chart(fig, use_container_width=True)
            
            st.divider()
            
            # ========== PRIX PAR NUITÉE ==========
            st.markdown("#### 💰 Prix par Nuitée")
            
            # Calculer prix par nuitée
            df_periode['prix_brut_par_nuit'] = df_periode['prix_brut'] / df_periode['nuitees']
            df_periode['prix_net_par_nuit'] = df_periode['prix_net'] / df_periode['nuitees']
            
            # Avec frais de ménage
            df_periode['prix_brut_avec_menage_par_nuit'] = df_periode['prix_brut_par_nuit']
            df_periode['prix_net_avec_menage_par_nuit'] = df_periode['prix_net_par_nuit']
            
            # Sans frais de ménage (si la colonne existe)
            if 'frais_menage' in df_periode.columns:
                df_periode['prix_brut_sans_menage'] = df_periode['prix_brut'] - df_periode['frais_menage'].fillna(0)
                df_periode['prix_net_sans_menage'] = df_periode['prix_net'] - df_periode['frais_menage'].fillna(0)
                df_periode['prix_brut_sans_menage_par_nuit'] = df_periode['prix_brut_sans_menage'] / df_periode['nuitees']
                df_periode['prix_net_sans_menage_par_nuit'] = df_periode['prix_net_sans_menage'] / df_periode['nuitees']
                has_menage = True
            else:
                has_menage = False
            
            # Moyennes globales
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Prix brut moyen/nuit", f"{df_periode['prix_brut_par_nuit'].mean():.2f} €")
            with col2:
                st.metric("Prix net moyen/nuit", f"{df_periode['prix_net_par_nuit'].mean():.2f} €")
            with col3:
                if has_menage:
                    st.metric("Prix brut/nuit (sans ménage)", f"{df_periode['prix_brut_sans_menage_par_nuit'].mean():.2f} €")
                else:
                    st.info("Frais ménage non renseignés")
            with col4:
                if has_menage:
                    st.metric("Prix net/nuit (sans ménage)", f"{df_periode['prix_net_sans_menage_par_nuit'].mean():.2f} €")
            
            # Prix par plateforme
            st.markdown("##### 📊 Prix par nuitée par plateforme")
            
            if has_menage:
                prix_par_plateforme = df_periode.groupby('plateforme').agg({
                    'prix_brut_par_nuit': 'mean',
                    'prix_net_par_nuit': 'mean',
                    'prix_brut_sans_menage_par_nuit': 'mean',
                    'prix_net_sans_menage_par_nuit': 'mean',
                    'nuitees': 'count'
                }).round(2)
                prix_par_plateforme.columns = [
                    'Prix brut/nuit (avec ménage)',
                    'Prix net/nuit (avec ménage)',
                    'Prix brut/nuit (sans ménage)',
                    'Prix net/nuit (sans ménage)',
                    'Nb réservations'
                ]
            else:
                prix_par_plateforme = df_periode.groupby('plateforme').agg({
                    'prix_brut_par_nuit': 'mean',
                    'prix_net_par_nuit': 'mean',
                    'nuitees': 'count'
                }).round(2)
                prix_par_plateforme.columns = [
                    'Prix brut/nuit',
                    'Prix net/nuit',
                    'Nb réservations'
                ]
            
            st.dataframe(prix_par_plateforme, use_container_width=True)
            
            # Graphiques comparatifs
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(prix_par_plateforme, 
                           y=prix_par_plateforme.index,
                           x=['Prix brut/nuit (avec ménage)', 'Prix net/nuit (avec ménage)'] if has_menage else ['Prix brut/nuit', 'Prix net/nuit'],
                           orientation='h',
                           title='Prix par nuitée (avec ménage)' if has_menage else 'Prix par nuitée',
                           labels={'value': 'Prix (€)', 'variable': 'Type', 'index': 'Plateforme'},
                           barmode='group')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                if has_menage:
                    fig = px.bar(prix_par_plateforme,
                               y=prix_par_plateforme.index,
                               x=['Prix brut/nuit (sans ménage)', 'Prix net/nuit (sans ménage)'],
                               orientation='h',
                               title='Prix par nuitée (sans ménage)',
                               labels={'value': 'Prix (€)', 'variable': 'Type', 'index': 'Plateforme'},
                               barmode='group')
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("💡 Ajoutez une colonne 'frais_menage' dans votre table Supabase pour voir le prix sans ménage")
            
            st.divider()
            
            # ========== TABLEAU RÉCAPITULATIF ==========
            st.markdown("#### 📋 Tableau Récapitulatif Complet")
            
            recap = df_periode.groupby('plateforme').agg({
                'nuitees': ['mean', 'median', 'sum', 'count'],
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'prix_brut_par_nuit': 'mean',
                'prix_net_par_nuit': 'mean'
            }).round(2)
            
            recap.columns = [
                'Durée moy (nuits)',
                'Durée méd (nuits)', 
                'Total nuitées',
                'Nb réservations',
                'CA brut total (€)',
                'CA net total (€)',
                'Prix brut/nuit (€)',
                'Prix net/nuit (€)'
            ]
            
            # Ajouter ligne total
            recap.loc['TOTAL'] = [
                df_periode['nuitees'].mean(),
                df_periode['nuitees'].median(),
                df_periode['nuitees'].sum(),
                len(df_periode),
                df_periode['prix_brut'].sum(),
                df_periode['prix_net'].sum(),
                df_periode['prix_brut_par_nuit'].mean(),
                df_periode['prix_net_par_nuit'].mean()
            ]
            
            st.dataframe(recap, use_container_width=True)
            
            # Export CSV
            csv = recap.to_csv(index=True)
            st.download_button(
                label="📥 Télécharger le tableau (CSV)",
                data=csv,
                file_name=f"analyses_detaillees_{titre_periode.replace(' ', '_')}.csv",
                mime="text/csv"
            )



    # TAB 5: OPTIMISATION PRICING
    with tab5:
        st.subheader("🎯 Optimisation Pricing - Atteindre votre objectif CA")
        
        st.info("💡 Cet outil calcule le prix optimal par nuitée pour atteindre votre objectif de CA net annuel, en tenant compte des commissions, de la durée moyenne des séjours et du taux d'occupation.")
        
        # Paramètres globaux
        col1, col2, col3 = st.columns(3)
        with col1:
            objectif_ca_net = st.number_input("🎯 Objectif CA Net Annuel (€)", min_value=0, value=22000, step=1000)
        with col2:
            if not proprietes_df.empty:
                prop_list_opt = ['Toutes'] + proprietes_df['nom'].tolist()
                prop_opt = st.selectbox("🏠 Propriété", prop_list_opt, key="opt_prop")
            else:
                prop_opt = 'Toutes'
        with col3:
            annee_opt = st.selectbox("📅 Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="opt_annee")
        
        # Filtrer les données historiques
        df_hist = reservations_df[reservations_df['date_arrivee'].dt.year == annee_opt].copy()
        if prop_opt != 'Toutes':
            prop_id_opt = proprietes_df[proprietes_df['nom'] == prop_opt]['id'].iloc[0]
            df_hist = df_hist[df_hist['propriete_id'] == prop_id_opt]
        
        # Exclure fermeture
        df_hist = df_hist[df_hist['plateforme'].str.upper() != 'FERMETURE']
        
        if df_hist.empty:
            st.warning("⚠️ Pas de données historiques pour cette sélection")
        else:
            # Analyse par plateforme
            st.markdown("### 📊 Analyse des Plateformes")
            
            plateformes_stats = df_hist.groupby('plateforme').agg({
                'nuitees': ['count', 'mean', 'sum'],
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'commissions': 'sum'
            }).round(2)
            
            plateformes_stats.columns = ['Nb réservations', 'Durée moy (nuits)', 'Total nuitées', 'CA brut', 'CA net', 'Commissions']
            plateformes_stats['Taux commission (%)'] = (plateformes_stats['Commissions'] / plateformes_stats['CA brut'] * 100).round(2)
            
            st.dataframe(plateformes_stats, use_container_width=True)
            
            # Calcul du taux de commission moyen pondéré
            commission_moy = (df_hist['commissions'].sum() / df_hist['prix_brut'].sum() * 100) if df_hist['prix_brut'].sum() > 0 else 15
            duree_moy_globale = df_hist['nuitees'].mean()
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📊 Taux commission moyen pondéré", f"{commission_moy:.1f}%")
            with col2:
                st.metric("📅 Durée moyenne séjour", f"{duree_moy_globale:.1f} nuits")
            
            st.divider()
            
            # Paramètres de simulation
            st.markdown("### ⚙️ Paramètres de Simulation")
            
            st.info("💡 Définissez le taux d'occupation cible pour chaque mois. Le prix sera calculé en fonction de cet objectif.")
            
            # Taux d'occupation par mois
            mois_noms = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
                        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
            
            # Calculer les taux d'occupation historiques par mois
            taux_occ_hist = {}
            for mois in range(1, 13):
                taux = calculer_taux_occupation(reservations_df, annee_opt, mois, prop_id_opt if prop_opt != 'Toutes' else None)
                taux_occ_hist[mois] = taux
            
            # Permettre de modifier les taux d'occupation cibles
            st.markdown("#### 📅 Taux d'Occupation Cible par Mois")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Basse saison (Oct-Mar)**")
                taux_basse = st.slider("Taux d'occupation cible", 0, 100, 50, 5, key="taux_basse")
            with col2:
                st.markdown("**Haute saison (Avr-Sep)**")
                taux_haute = st.slider("Taux d'occupation cible", 0, 100, 80, 5, key="taux_haute")
            
            # Appliquer les taux par mois
            taux_occ_cible = {}
            for mois in range(1, 13):
                if mois in [4, 5, 6, 7, 8, 9]:  # Avril à Septembre
                    taux_occ_cible[mois] = taux_haute
                else:
                    taux_occ_cible[mois] = taux_basse
            
            # Permettre ajustements manuels
            if st.checkbox("🎛️ Ajuster manuellement par mois"):
                cols = st.columns(6)
                for i, mois in enumerate(range(1, 13)):
                    with cols[i % 6]:
                        taux_occ_cible[mois] = st.number_input(
                            f"{mois_noms[mois-1][:3]}", 
                            min_value=0, 
                            max_value=100, 
                            value=taux_occ_cible[mois],
                            step=5,
                            key=f"taux_{mois}"
                        )
            
            st.divider()
            
            # CALCUL DU PRICING OPTIMAL
            st.markdown("### 💰 Pricing Optimal par Mois")
            
            # Calculer le nombre de nuitées disponibles par mois
            jours_par_mois = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
            if annee_opt % 4 == 0:  # Année bissextile
                jours_par_mois[1] = 29
            
            # Calculer pour chaque mois
            resultats = []
            total_ca_net_projete = 0
            total_nuitees_projetees = 0
            
            for mois in range(1, 13):
                # Nuitées disponibles
                nuitees_dispo = jours_par_mois[mois-1]
                
                # Nuitées vendues (selon taux occupation)
                nuitees_vendues = nuitees_dispo * taux_occ_cible[mois] / 100
                
                # Durée moyenne pour ce mois (historique)
                df_mois = df_hist[df_hist['date_arrivee'].dt.month == mois]
                duree_moy_mois = df_mois['nuitees'].mean() if not df_mois.empty else duree_moy_globale
                
                # Nombre de réservations nécessaires
                nb_reservations = nuitees_vendues / duree_moy_mois if duree_moy_mois > 0 else 0
                
                # Taux de commission pour ce mois
                commission_mois = (df_mois['commissions'].sum() / df_mois['prix_brut'].sum() * 100) if not df_mois.empty and df_mois['prix_brut'].sum() > 0 else commission_moy
                
                resultats.append({
                    'mois': mois,
                    'mois_nom': mois_noms[mois-1],
                    'jours_dispo': nuitees_dispo,
                    'taux_occ': taux_occ_cible[mois],
                    'nuitees_vendues': nuitees_vendues,
                    'duree_moy': duree_moy_mois,
                    'nb_reservations': nb_reservations,
                    'commission_pct': commission_mois
                })
                
                total_nuitees_projetees += nuitees_vendues
            
            # Répartir l'objectif de CA sur les mois proportionnellement aux nuitées
            for r in resultats:
                # Part de ce mois dans le total
                part_mois = r['nuitees_vendues'] / total_nuitees_projetees if total_nuitees_projetees > 0 else 1/12
                
                # CA net à générer ce mois
                ca_net_mois = objectif_ca_net * part_mois
                
                # CA brut nécessaire (en tenant compte de la commission)
                ca_brut_mois = ca_net_mois / (1 - r['commission_pct']/100)
                
                # Prix brut par nuitée
                prix_brut_nuitee = ca_brut_mois / r['nuitees_vendues'] if r['nuitees_vendues'] > 0 else 0
                
                # Prix net par nuitée
                prix_net_nuitee = prix_brut_nuitee * (1 - r['commission_pct']/100)
                
                # Prix par réservation
                prix_brut_reservation = prix_brut_nuitee * r['duree_moy']
                
                r['ca_net_mois'] = ca_net_mois
                r['ca_brut_mois'] = ca_brut_mois
                r['prix_brut_nuitee'] = prix_brut_nuitee
                r['prix_net_nuitee'] = prix_net_nuitee
                r['prix_brut_reservation'] = prix_brut_reservation
                
                total_ca_net_projete += ca_net_mois
            
            # Créer le DataFrame des résultats
            df_resultats = pd.DataFrame(resultats)
            
            # Afficher le résumé
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🎯 Objectif CA Net", f"{objectif_ca_net:,.0f} €")
            with col2:
                st.metric("📊 CA Net Projeté", f"{total_ca_net_projete:,.0f} €", f"{total_ca_net_projete - objectif_ca_net:+.0f} €")
            with col3:
                st.metric("🌙 Nuitées Totales", f"{int(total_nuitees_projetees)}")
            
            # Tableau détaillé
            st.markdown("#### 📋 Détail par Mois")
            
            df_display = df_resultats[['mois_nom', 'taux_occ', 'nuitees_vendues', 'duree_moy', 'nb_reservations', 
                                      'commission_pct', 'prix_brut_nuitee', 'prix_net_nuitee', 'prix_brut_reservation', 
                                      'ca_net_mois']].copy()
            
            df_display.columns = ['Mois', 'Taux Occ (%)', 'Nuitées', 'Durée moy', 'Nb réserv', 
                                'Commission (%)', 'Prix brut/nuit (€)', 'Prix net/nuit (€)', 
                                'Prix brut/réserv (€)', 'CA net (€)']
            
            # Formater
            df_display['Nuitées'] = df_display['Nuitées'].round(0).astype(int)
            df_display['Durée moy'] = df_display['Durée moy'].round(1)
            df_display['Nb réserv'] = df_display['Nb réserv'].round(1)
            df_display['Commission (%)'] = df_display['Commission (%)'].round(1)
            df_display['Prix brut/nuit (€)'] = df_display['Prix brut/nuit (€)'].round(0).astype(int)
            df_display['Prix net/nuit (€)'] = df_display['Prix net/nuit (€)'].round(0).astype(int)
            df_display['Prix brut/réserv (€)'] = df_display['Prix brut/réserv (€)'].round(0).astype(int)
            df_display['CA net (€)'] = df_display['CA net (€)'].round(0).astype(int)
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
            # Graphiques
            st.markdown("#### 📈 Visualisations")
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.bar(df_resultats, x='mois_nom', y='prix_brut_nuitee',
                           title="Prix Brut par Nuitée par Mois",
                           labels={'mois_nom': 'Mois', 'prix_brut_nuitee': 'Prix (€)'},
                           color='prix_brut_nuitee',
                           color_continuous_scale='Blues')
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.line(df_resultats, x='mois_nom', y=['taux_occ', 'commission_pct'],
                            title="Taux d'Occupation vs Commission",
                            labels={'mois_nom': 'Mois', 'value': '%', 'variable': 'Type'},
                            markers=True)
                st.plotly_chart(fig, use_container_width=True)
            
            # Recommandations
            st.markdown("#### 💡 Recommandations")
            
            # Identifier les mois avec prix élevés
            prix_moyen = df_resultats['prix_brut_nuitee'].mean()
            mois_chers = df_resultats[df_resultats['prix_brut_nuitee'] > prix_moyen * 1.2]
            mois_bas = df_resultats[df_resultats['prix_brut_nuitee'] < prix_moyen * 0.8]
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.success("✅ **Mois avec prix attractifs**")
                if not mois_bas.empty:
                    for _, row in mois_bas.iterrows():
                        st.write(f"- **{row['mois_nom']}** : {row['prix_brut_nuitee']:.0f}€/nuit ({row['taux_occ']:.0f}% occupation)")
                else:
                    st.write("Aucun mois identifié")
            
            with col2:
                st.warning("⚠️ **Mois nécessitant prix élevés**")
                if not mois_chers.empty:
                    for _, row in mois_chers.iterrows():
                        st.write(f"- **{row['mois_nom']}** : {row['prix_brut_nuitee']:.0f}€/nuit ({row['taux_occ']:.0f}% occupation)")
                        if row['taux_occ'] < 60:
                            st.caption(f"  💡 Augmenter le taux d'occupation pour réduire le prix")
                else:
                    st.write("Aucun mois identifié")
            
            # Stratégies
            st.info("""
            **💡 Stratégies pour optimiser votre pricing :**
            
            1. **Haute saison** : Maintenez des prix élevés avec un taux d'occupation élevé
            2. **Basse saison** : Baissez les prix pour augmenter le taux d'occupation
            3. **Commissions** : Privilégiez les réservations directes (0% commission) quand possible
            4. **Durée de séjour** : Encouragez les séjours longs (réductions pour 7+ nuits)
            5. **Ajustements** : Modifiez les taux d'occupation cibles ci-dessus pour voir l'impact sur les prix
            """)
            
            # Export
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="📥 Télécharger la grille tarifaire (CSV)",
                data=csv,
                file_name=f"grille_tarifaire_{annee_opt}_{prop_opt.replace(' ', '_')}.csv",
                mime="text/csv"
            )

# ==================== MESSAGES ====================
elif menu == "✉️ Messages":
    st.markdown("<h1 class='main-header'>✉️ Messages Automatiques</h1>", unsafe_allow_html=True)
    
    st.info("💡 **Messages personnalisés** : Générez des messages J-1 (avant arrivée) et J+1 (après départ) dans la langue du client")
    
    # reservations_df = get_reservations()
    # proprietes_df = get_proprietes()
    
    if reservations_df.empty:
        st.warning("Aucune réservation disponible")
    else:
        # Fusionner avec propriétés pour avoir les noms ET le gestionnaire
        if not proprietes_df.empty:
            reservations_df = reservations_df.merge(
                proprietes_df[['id', 'nom', 'gestionnaire_nom', 'gestionnaire_email', 'gestionnaire_telephone']], 
                left_on='propriete_id', right_on='id', 
                how='left', suffixes=('', '_prop'))
        
        # Sélection de la réservation
        st.markdown("### 🔍 Sélectionner une réservation")
        col1, col2 = st.columns(2)
        
        with col1:
            # Créer la liste des réservations
            options = []
            for idx, row in reservations_df.iterrows():
                prop_name = row.get('nom', 'Propriété inconnue')
                label = f"{row['nom_client']} - {prop_name} - {row['date_arrivee'].strftime('%d/%m/%Y')}"
                options.append((label, idx))
            
            selected = st.selectbox(
                "Choisir une réservation",
                options,
                format_func=lambda x: x[0]
            )
        
        with col2:
            type_message = st.radio("Type de message", ["📅 J-1 Avant arrivée", "👋 J+1 Après départ"])
        
        if selected:
            res_idx = selected[1]
            reservation = reservations_df.iloc[res_idx]
            
            # Détection langue depuis pays
            langue_detectee = 'fr'  # Par défaut français
            if pd.notna(reservation.get('pays')):
                pays = str(reservation['pays']).lower()
                if any(k in pays for k in ['royaume-uni', 'uk', 'united', 'états-unis', 'usa', 'canada']):
                    langue_detectee = 'en'
                elif any(k in pays for k in ['espagne', 'spain', 'mexique', 'argentine']):
                    langue_detectee = 'es'
            
            langue_map = {'fr': 'Français', 'en': 'English', 'es': 'Español'}
            langue_options = ['Français', 'English', 'Español']
            langue_default_idx = 0
            if langue_detectee in langue_map:
                langue_default_idx = langue_options.index(langue_map[langue_detectee])
            
            langue = st.selectbox("🌍 Langue", langue_options, index=langue_default_idx)
            langue_code = {'Français': 'fr', 'English': 'en', 'Español': 'es'}[langue]
            
            if langue_detectee != langue_code:
                st.info(f"💡 Langue détectée depuis le pays : {langue_map.get(langue_detectee, 'Français')}")
            
            # Générer le message
            if st.button("📝 Générer le message", type="primary", use_container_width=True):
                prop_nom = reservation.get('nom', 'Notre appartement')
                prop_ville = proprietes_df[proprietes_df['id'] == reservation['propriete_id']]['ville'].iloc[0] if not proprietes_df.empty else 'Nice'
                
                # Récupérer les infos du gestionnaire
                gestionnaire_nom = reservation.get('gestionnaire_nom', 'L\'équipe')
                gestionnaire_email = reservation.get('gestionnaire_email', '')
                gestionnaire_tel = reservation.get('gestionnaire_telephone', '')
                
                # Créer la signature
                signature = f"\n\nCordialement,\n{gestionnaire_nom}"
                if gestionnaire_email:
                    signature += f"\n📧 {gestionnaire_email}"
                if gestionnaire_tel:
                    signature += f"\n📞 {gestionnaire_tel}"
                
                if type_message == "📅 J-1 Avant arrivée":
                    # Message J-1
                    if langue_code == 'fr':
                        message = f"""🏠 {prop_nom}
📱 Plateforme : {reservation['plateforme']}
📅 Arrivée : {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Départ : {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Nuitées : {int(reservation['nuitees'])}

Bonjour {reservation['nom_client']},

Bienvenue chez nous ! 🌟

Nous sommes ravis de vous accueillir bientôt à {prop_ville}. Afin d'organiser au mieux votre réception, nous vous demandons de bien vouloir nous indiquer votre heure d'arrivée.

🅿️ Un parking est à votre disposition sur place.

⏰ Check-in : à partir de 14:00
⏰ Check-out : avant 11:00

🔑 Nous serons sur place lors de votre arrivée pour vous remettre les clés.

🎒 Vous trouverez des consignes à bagages dans chaque quartier, à {prop_ville}.

Nous vous souhaitons un excellent voyage et nous nous réjouissons de vous rencontrer très bientôt ! ✈️{signature}"""
                    
                    elif langue_code == 'en':
                        message = f"""🏠 {prop_nom}
📱 Platform: {reservation['plateforme']}
📅 Arrival: {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Departure: {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Nights: {int(reservation['nuitees'])}

Hello {reservation['nom_client']},

Welcome! 🌟

We are delighted to welcome you soon to {prop_ville}. To best organize your reception, please let us know your arrival time.

🅿️ Parking is available on site.

⏰ Check-in: from 2:00 PM
⏰ Check-out: before 11:00 AM

🔑 We will be on site when you arrive to hand you the keys.

🎒 You will find luggage storage in every neighborhood in {prop_ville}.

We wish you an excellent trip and look forward to meeting you very soon! ✈️{signature}"""
                    
                    else:  # español
                        message = f"""🏠 {prop_nom}
📱 Plataforma: {reservation['plateforme']}
📅 Llegada: {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Salida: {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Noches: {int(reservation['nuitees'])}

Hola {reservation['nom_client']},

¡Bienvenido! 🌟

Estamos encantados de recibirle pronto en {prop_ville}. Para organizar mejor su recepción, le rogamos que nos indique su hora de llegada.

🅿️ Hay aparcamiento disponible en el lugar.

⏰ Check-in: a partir de las 14:00
⏰ Check-out: antes de las 11:00

🔑 Estaremos presentes a su llegada para entregarle las llaves.

🎒 Encontrará consignas de equipaje en cada barrio de {prop_ville}.

¡Le deseamos un excelente viaje y esperamos conocerle muy pronto! ✈️{signature}"""
                
                else:  # J+1 Après départ
                    if langue_code == 'fr':
                        message = f"""🏠 {prop_nom}

Bonjour {reservation['nom_client']},

Un grand merci d'avoir choisi notre appartement pour votre séjour. 🙏

Nous espérons que vous avez passé un moment agréable et que vous avez pu profiter de tout ce que {prop_ville} a à offrir. ☀️

Si vous souhaitez revenir explorer encore un peu la ville, notre porte vous sera toujours grande ouverte. 🚪

Au plaisir de vous accueillir à nouveau ! 🌟{signature}"""
                    
                    elif langue_code == 'en':
                        message = f"""🏠 {prop_nom}

Hello {reservation['nom_client']},

A big thank you for choosing our apartment for your stay. 🙏

We hope you had a pleasant time and were able to enjoy everything {prop_ville} has to offer. ☀️

If you would like to come back and explore the city a bit more, our door will always be wide open. 🚪

Looking forward to welcoming you again! 🌟{signature}"""
                    
                    else:  # español
                        message = f"""🏠 {prop_nom}

Hola {reservation['nom_client']},

Muchas gracias por elegir nuestro apartamento para su estancia. 🙏

Esperamos que haya pasado un momento agradable y que haya podido disfrutar de todo lo que {prop_ville} tiene para ofrecer. ☀️

Si desea volver para explorar un poco más la ciudad, nuestra puerta siempre estará abierta. 🚪

¡Esperamos darle la bienvenida de nuevo! 🌟{signature}"""
                
                # Afficher le message
                st.success("✅ Message généré !")
                st.text_area("📝 Message généré", message, height=450, key="message_generated")
                
                # Boutons de copie
                st.markdown("### 📋 Copier le message")
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("📧 Pour Email", use_container_width=True):
                        st.info("💡 Copiez le message ci-dessus et collez-le dans votre email")
                with col2:
                    if st.button("💬 Pour SMS", use_container_width=True):
                        st.info("💡 Copiez le message ci-dessus et collez-le dans votre SMS")
                with col3:
                    if st.button("📱 Pour WhatsApp", use_container_width=True):
                        st.info("💡 Copiez le message ci-dessus et collez-le dans WhatsApp")
                
                # Info automatisation
                st.divider()
                st.markdown("### 🤖 Automatiser l'envoi")
                st.info("""
                **Pour automatiser ces messages** :
                
                1. **Zapier** ou **Make.com** (Recommandé)
                   - Connectez Supabase
                   - Trigger : date_arrivee = demain OU date_depart = hier
                   - Action : Envoyer Email/SMS/WhatsApp
                
                2. **Script Python quotidien**
                   - Vérifier les dates J-1 et J+1 chaque jour
                   - Générer et envoyer automatiquement
                
                3. **Supabase Edge Functions**
                   - Fonction serverless déclenchée automatiquement
                """)

# ================================================================
# SECTION GESTION PROPRIÉTÉS COMPLÈTE
# ================================================================
# À ajouter dans l'app après la section Messages

# ==================== PROPRIÉTÉS ====================
elif menu == "🏠 Propriétés":
    st.markdown("<h1 class='main-header'>🏠 Gestion des Propriétés</h1>", unsafe_allow_html=True)
    
    # proprietes_df = get_proprietes()
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste des propriétés", "➕ Ajouter propriété", "📊 Statistiques"])
    
    # TAB 1: LISTE DES PROPRIÉTÉS
    with tab1:
        st.subheader("📋 Vos propriétés")
        
        if proprietes_df.empty:
            st.info("Aucune propriété enregistrée. Créez-en une dans l'onglet ➕ Ajouter")
        else:
            for idx, prop in proprietes_df.iterrows():
                with st.expander(f"🏠 {prop['nom']}", expanded=False):
                    col1, col2 = st.columns([2, 1])
                    
                    with col1:
                        st.markdown(f"""
                        **📍 Ville** : {prop.get('ville', 'Non renseignée')}  
                        **👥 Capacité** : {prop.get('capacite', 'Non renseignée')} personnes  
                        **📝 Description** : {prop.get('description', 'Aucune description')}
                        
                        ---
                        
                        **👤 Gestionnaire** : {prop.get('gestionnaire_nom', 'Non renseigné')}  
                        **📧 Email** : {prop.get('gestionnaire_email', 'Non renseigné')}  
                        **📞 Téléphone** : {prop.get('gestionnaire_telephone', 'Non renseigné')}
                        """)
                    
                    with col2:
                        # Statistiques rapides
    # reservations_df = get_reservations()
                        if not reservations_df.empty:
                            res_prop = reservations_df[reservations_df['propriete_id'] == prop['id']]
                            st.metric("Réservations", len(res_prop))
                            st.metric("Nuitées", int(res_prop['nuitees'].sum()) if not res_prop.empty else 0)
                    
                    # Actions
                    st.divider()
                    action_col1, action_col2 = st.columns(2)
                    
                    with action_col1:
                        if st.button("✏️ Modifier", key=f"edit_{prop['id']}", use_container_width=True):
                            st.session_state[f'editing_{prop["id"]}'] = True
                    
                    with action_col2:
                        if st.button("🗑️ Supprimer", key=f"del_{prop['id']}", use_container_width=True):
                            st.session_state[f'deleting_{prop["id"]}'] = True
                    
                    # FORMULAIRE DE MODIFICATION
                    if st.session_state.get(f'editing_{prop["id"]}', False):
                        st.markdown("### ✏️ Modifier la propriété")
                        
                        with st.form(f"form_edit_prop_{prop['id']}"):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                new_nom = st.text_input("Nom *", value=prop['nom'], key=f"nom_{prop['id']}")
                                new_ville = st.text_input("Ville", value=prop.get('ville', ''), key=f"ville_{prop['id']}")
                                new_capacite = st.number_input("Capacité (personnes)", min_value=1, value=int(prop.get('capacite', 4)), key=f"cap_{prop['id']}")
                                new_description = st.text_area("Description", value=prop.get('description', ''), height=100, key=f"desc_{prop['id']}")
                            
                            with col2:
                                st.markdown("#### 👤 Gestionnaire")
                                new_gest_nom = st.text_input("Nom du gestionnaire *", value=prop.get('gestionnaire_nom', ''), key=f"gest_nom_{prop['id']}")
                                new_gest_email = st.text_input("Email du gestionnaire", value=prop.get('gestionnaire_email', ''), key=f"gest_email_{prop['id']}")
                                new_gest_tel = st.text_input("Téléphone du gestionnaire", value=prop.get('gestionnaire_telephone', ''), key=f"gest_tel_{prop['id']}")
                            
                            submitted = st.form_submit_button("💾 Enregistrer les modifications", type="primary", use_container_width=True)
                            
                            if submitted:
                                if not new_nom:
                                    st.error("Le nom est obligatoire")
                                elif not new_gest_nom:
                                    st.error("Le nom du gestionnaire est obligatoire")
                                else:
                                    try:
                                        update_data = {
                                            'nom': new_nom,
                                            'ville': new_ville if new_ville else None,
                                            'capacite': new_capacite,
                                            'description': new_description if new_description else None,
                                            'gestionnaire_nom': new_gest_nom,
                                            'gestionnaire_email': new_gest_email if new_gest_email else None,
                                            'gestionnaire_telephone': new_gest_tel if new_gest_tel else None
                                        }
                                        
                                        supabase.table('proprietes').update(update_data).eq('id', prop['id']).execute()
                                        st.success(f"✅ Propriété '{new_nom}' modifiée avec succès !")
                                        st.session_state[f'editing_{prop["id"]}'] = False
                                        refresh_data()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur : {e}")
                    
                    # CONFIRMATION SUPPRESSION
                    if st.session_state.get(f'deleting_{prop["id"]}', False):
                        st.error(f"""
                        ⚠️ **ATTENTION - SUPPRESSION DÉFINITIVE**
                        
                        Vous êtes sur le point de supprimer la propriété **{prop['nom']}**.
                        
                        ⚠️ Toutes les réservations associées seront également supprimées !
                        
                        Cette action est **IRRÉVERSIBLE** !
                        """)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("🗑️ CONFIRMER LA SUPPRESSION", type="primary", key=f"confirm_del_{prop['id']}", use_container_width=True):
                                try:
                                    supabase.table('proprietes').delete().eq('id', prop['id']).execute()
                                    st.success(f"✅ Propriété '{prop['nom']}' supprimée")
                                    st.session_state[f'deleting_{prop["id"]}'] = False
                                    refresh_data()
                                    import time
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {e}")
                        
                        with col2:
                            if st.button("❌ ANNULER", key=f"cancel_del_{prop['id']}", use_container_width=True):
                                st.session_state[f'deleting_{prop["id"]}'] = False
                                st.rerun()
    
    # TAB 2: AJOUTER UNE PROPRIÉTÉ
    with tab2:
        st.subheader("➕ Ajouter une nouvelle propriété")
        
        with st.form("form_nouvelle_propriete"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 🏠 Informations propriété")
                nom = st.text_input("Nom de la propriété *", placeholder="Ex: Villa Sunshine")
                ville = st.text_input("Ville", placeholder="Ex: Nice")
                capacite = st.number_input("Capacité (personnes)", min_value=1, value=4, step=1)
                description = st.text_area("Description", placeholder="Décrivez votre propriété...", height=150)
            
            with col2:
                st.markdown("#### 👤 Gestionnaire")
                st.info("💡 Le gestionnaire sera affiché comme signature dans les messages envoyés aux clients")
                
                gestionnaire_nom = st.text_input("Nom du gestionnaire *", placeholder="Ex: Jean Dupont")
                gestionnaire_email = st.text_input("Email du gestionnaire", placeholder="Ex: jean@exemple.com")
                gestionnaire_telephone = st.text_input("Téléphone du gestionnaire", placeholder="Ex: +33612345678")
            
            submitted = st.form_submit_button("✅ Créer la propriété", type="primary", use_container_width=True)
            
            if submitted:
                if not nom:
                    st.error("❌ Le nom de la propriété est obligatoire")
                elif not gestionnaire_nom:
                    st.error("❌ Le nom du gestionnaire est obligatoire")
                else:
                    try:
                        nouvelle_prop = {
                            'nom': nom,
                            'ville': ville if ville else None,
                            'capacite': capacite,
                            'description': description if description else None,
                            'gestionnaire_nom': gestionnaire_nom,
                            'gestionnaire_email': gestionnaire_email if gestionnaire_email else None,
                            'gestionnaire_telephone': gestionnaire_telephone if gestionnaire_telephone else None
                        }
                        
                        supabase.table('proprietes').insert(nouvelle_prop).execute()
                        st.success(f"✅ Propriété '{nom}' créée avec succès !")
                        st.balloons()
                        refresh_data()
                        import time
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        error_msg = str(e)
                        if 'duplicate key' in error_msg and 'reservations_pkey' in error_msg:
                            st.error("""
                            ❌ **Erreur : ID dupliquée**
                            
                            La séquence d'auto-incrémentation n'est pas à jour.
                            
                            **Solution rapide (30 secondes)** :
                            1. Ouvrez **Supabase** → **SQL Editor**
                            2. Copiez-collez cette ligne :
                            ```sql
                            SELECT setval('reservations_id_seq', (SELECT MAX(id) FROM reservations) + 1);
                            ```
                            3. Cliquez **RUN**
                            4. Réessayez de créer la réservation
                            
                            **Pourquoi ?** Vous avez probablement importé un CSV avec des IDs existants.
                            La séquence Supabase n'a pas été mise à jour automatiquement.
                            """)
                        else:
                            st.error(f"❌ Erreur lors de la création : {error_msg}")
    
    # TAB 3: STATISTIQUES
    with tab3:
        st.subheader("📊 Statistiques par propriété")
        
        if proprietes_df.empty:
            st.info("Aucune propriété pour afficher les statistiques")
        else:
            
            if reservations_df.empty:
                st.info("Aucune réservation pour calculer les statistiques")
            else:
                # FILTRES
                col1, col2 = st.columns(2)
                with col1:
                    annees_dispo = sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True)
                    annee_stats = st.selectbox("📅 Année", ['Toutes'] + list(annees_dispo), key="stats_prop_annee")
                
                with col2:
                    plateformes_dispo = sorted(reservations_df['plateforme'].unique())
                    plateforme_stats = st.selectbox("🏢 Plateforme", ['Toutes'] + list(plateformes_dispo), key="stats_prop_plateforme")
                
                # Filtrer les données
                stats_df = reservations_df.copy()
                
                if annee_stats != 'Toutes':
                    stats_df = stats_df[stats_df['date_arrivee'].dt.year == annee_stats]
                
                if plateforme_stats != 'Toutes':
                    stats_df = stats_df[stats_df['plateforme'] == plateforme_stats]
                
                # Exclure fermeture
                stats_df = stats_df[stats_df['plateforme'].str.upper() != 'FERMETURE']
                
                if stats_df.empty:
                    st.warning("⚠️ Aucune réservation pour les filtres sélectionnés")
                else:
                    # Fusionner avec propriétés
                    stats_df = stats_df.merge(proprietes_df[['id', 'nom']], left_on='propriete_id', right_on='id', suffixes=('', '_prop'))
                    
                    # Calculer les statistiques
                    stats = stats_df.groupby('nom').agg({
                        'id': 'count',
                        'nuitees': 'sum',
                        'prix_net': 'sum',
                        'prix_brut': 'sum',
                        'commissions': 'sum'
                    }).rename(columns={
                        'id': 'Nb réservations',
                        'nuitees': 'Total nuitées',
                        'prix_brut': 'CA brut (€)',
                        'prix_net': 'Revenus nets (€)',
                        'commissions': 'Commissions (€)'
                    })
                    
                    # Ajouter taux de commission
                    stats['Taux commission (%)'] = (stats['Commissions (€)'] / stats['CA brut (€)'] * 100).round(1)
                    
                    st.divider()
                    
                    # Afficher tableau
                    st.dataframe(stats, use_container_width=True)
                    
                    # Graphiques
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        fig = px.bar(stats, y='Nb réservations', title="Nombre de réservations par propriété")
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with col2:
                        fig = px.pie(stats, values='Revenus nets (€)', names=stats.index, title="Répartition des revenus")
                        st.plotly_chart(fig, use_container_width=True)

# ==================== PARAMÈTRES ====================

# ==================== SYNCHRONISATION iCAL ====================
elif menu == "🔄 Synchronisation iCal":
    st.markdown("<h1 class='main-header'>🔄 Synchronisation iCal</h1>", unsafe_allow_html=True)
    
    st.info("""
    💡 **Synchronisation automatique avec Airbnb et Booking**
    
    Importez automatiquement vos réservations depuis les plateformes via les flux iCal.
    Évitez les doubles réservations et gardez tout synchronisé !
    """)
    
    tab1, tab2, tab3 = st.tabs(["⚙️ Configuration", "▶️ Synchroniser", "📜 Historique"])
    
    with tab1:
        st.subheader("⚙️ Configuration des flux iCal")
        
        if proprietes_df.empty:
            st.warning("⚠️ Aucune propriété. Créez d'abord une propriété.")
        else:
            for idx, prop in proprietes_df.iterrows():
                with st.expander(f"🏠 {prop['nom']}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🔵 Airbnb")
                        ical_airbnb = st.text_input(
                            "URL iCal Airbnb",
                            value=prop.get('ical_url_airbnb', ''),
                            key=f"airbnb_{prop['id']}",
                            help="Format: https://www.airbnb.fr/calendar/ical/..."
                        )
                        
                        if st.button(f"💾 Sauvegarder Airbnb", key=f"save_airbnb_{prop['id']}"):
                            try:
                                supabase.table('proprietes').update({
                                    'ical_url_airbnb': ical_airbnb if ical_airbnb else None
                                }).eq('id', prop['id']).execute()
                                st.success("✅ URL Airbnb sauvegardée")
                                refresh_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
                    
                    with col2:
                        st.markdown("#### 🟠 Booking")
                        ical_booking = st.text_input(
                            "URL iCal Booking",
                            value=prop.get('ical_url_booking', ''),
                            key=f"booking_{prop['id']}",
                            help="Format: https://ical.booking.com/v1/export?t=..."
                        )
                        
                        if st.button(f"💾 Sauvegarder Booking", key=f"save_booking_{prop['id']}"):
                            try:
                                supabase.table('proprietes').update({
                                    'ical_url_booking': ical_booking if ical_booking else None
                                }).eq('id', prop['id']).execute()
                                st.success("✅ URL Booking sauvegardée")
                                refresh_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
                    
                    st.divider()
                    auto_sync = st.checkbox(
                        "🔄 Activer la synchronisation automatique",
                        value=prop.get('ical_auto_sync', False),
                        key=f"auto_{prop['id']}"
                    )
                    
                    if auto_sync != prop.get('ical_auto_sync', False):
                        supabase.table('proprietes').update({
                            'ical_auto_sync': auto_sync
                        }).eq('id', prop['id']).execute()
                        st.success(f"✅ Synchronisation automatique {'activée' if auto_sync else 'désactivée'}")
                        refresh_data()
                        st.rerun()
                    
                    if prop.get('ical_last_sync'):
                        last_sync = pd.to_datetime(prop['ical_last_sync'])
                        st.caption(f"🕒 Dernière synchro : {last_sync.strftime('%d/%m/%Y %H:%M')}")
    
    with tab2:
        st.subheader("▶️ Synchronisation manuelle")
        
        if st.button("🔄 Synchroniser toutes les propriétés", type="primary", use_container_width=True):
            with st.spinner("Synchronisation en cours..."):
                results = sync_all_properties(supabase, proprietes_df)
                
                st.divider()
                st.markdown("### 📊 Résultats de la synchronisation")
                
                for result in results:
                    with st.expander(f"🏠 {result['propriete']} - {result['plateforme']}", expanded=True):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Importées", result['importees'])
                        with col2:
                            st.metric("Mises à jour", result['mises_a_jour'])
                        with col3:
                            st.metric("Conflits", result['conflits'])
                        
                        st.info(result['message'])
                
                refresh_data()
                st.success("✅ Synchronisation terminée !")
        
        st.divider()
        st.markdown("#### Synchroniser une propriété spécifique")
        
        for idx, prop in proprietes_df.iterrows():
            with st.expander(f"🏠 {prop['nom']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    if prop.get('ical_url_airbnb'):
                        if st.button(f"🔵 Sync Airbnb", key=f"sync_airbnb_{prop['id']}"):
                            with st.spinner("Synchronisation Airbnb..."):
                                nb_imp, nb_maj, nb_conf, msg = sync_ical_to_supabase(
                                    prop['id'], 'Airbnb', prop['ical_url_airbnb'], supabase
                                )
                                st.success(msg)
                                refresh_data()
                    else:
                        st.warning("URL Airbnb non configurée")
                
                with col2:
                    if prop.get('ical_url_booking'):
                        if st.button(f"🟠 Sync Booking", key=f"sync_booking_{prop['id']}"):
                            with st.spinner("Synchronisation Booking..."):
                                nb_imp, nb_maj, nb_conf, msg = sync_ical_to_supabase(
                                    prop['id'], 'Booking', prop['ical_url_booking'], supabase
                                )
                                st.success(msg)
                                refresh_data()
                    else:
                        st.warning("URL Booking non configurée")
    
    with tab3:
        st.subheader("📜 Historique des synchronisations")
        
        try:
            logs = supabase.table('ical_sync_logs').select('*').order('sync_date', desc=True).limit(50).execute()
            
            if logs.data:
                logs_df = pd.DataFrame(logs.data)
                logs_df = logs_df.merge(
                    proprietes_df[['id', 'nom']], 
                    left_on='propriete_id', 
                    right_on='id',
                    how='left',
                    suffixes=('', '_prop')
                )
                
                for idx, log in logs_df.iterrows():
                    sync_date = pd.to_datetime(log['sync_date'])
                    icon = "✅" if log['statut'] == 'success' else "⚠️"
                    
                    with st.expander(
                        f"{icon} {log['nom']} - {log['plateforme']} - {sync_date.strftime('%d/%m/%Y %H:%M')}",
                        expanded=False
                    ):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Importées", log['nb_reservations_importees'])
                        with col2:
                            st.metric("Mises à jour", log['nb_reservations_mises_a_jour'])
                        with col3:
                            st.metric("Conflits", log['nb_conflits'])
                        
                        if log.get('message'):
                            st.caption(log['message'])
            else:
                st.info("📭 Aucune synchronisation effectuée")
        
        except Exception as e:
            st.error(f"❌ Erreur: {e}")


elif menu == "🔧 Paramètres":
    st.markdown("<h1 class='main-header'>🔧 Paramètres</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["🎨 Plateformes", "➕ Ajouter plateforme", "💾 Export"])
    
    # TAB 1 : LISTE DES PLATEFORMES
    with tab1:
        st.subheader("🎨 Gérer les plateformes")
        plateformes_df = get_plateformes()
        
        if not plateformes_df.empty:
            st.info(f"📊 {len(plateformes_df)} plateforme(s) enregistrée(s)")
            
            for idx, plat in plateformes_df.iterrows():
                with st.expander(f"📱 {plat['nom_plateforme']}", expanded=False):
                    with st.form(f"form_plat_{plat['id']}"):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            new_nom = st.text_input("Nom", value=plat['nom_plateforme'], key=f"nom_{plat['id']}")
                        
                        with col2:
                            # Gérer le cas où commission_pct n'existe pas
                            current_commission = 0.0
                            if 'commission_pct' in plat and pd.notna(plat['commission_pct']):
                                current_commission = float(plat['commission_pct'])
                            
                            new_commission = st.number_input(
                                "Commission (%)", 
                                min_value=0.0, 
                                max_value=100.0, 
                                value=current_commission,
                                step=0.5,
                                key=f"com_{plat['id']}"
                            )
                        
                        with col3:
                            # Gérer le cas où couleur n'existe pas
                            current_couleur = '#6c757d'
                            if 'couleur' in plat and pd.notna(plat['couleur']):
                                current_couleur = str(plat['couleur'])
                            
                            new_couleur = st.color_picker(
                                "Couleur calendrier", 
                                value=current_couleur,
                                key=f"col_{plat['id']}"
                            )
                            # Prévisualisation
                            st.markdown(f"""
                            <div style='background-color: {new_couleur}; padding: 10px; border-radius: 5px; text-align: center; color: white; margin-top: 10px;'>
                                <b>Aperçu</b>
                            </div>
                            """, unsafe_allow_html=True)
                        
                        col_save, col_del = st.columns(2)
                        
                        with col_save:
                            if st.form_submit_button("💾 Enregistrer", use_container_width=True):
                                try:
                                    update_data = {
                                        'nom_plateforme': new_nom,
                                        'commission_pct': new_commission,
                                        'couleur': new_couleur
                                    }
                                    supabase.table('plateformes').update(update_data).eq('id', plat['id']).execute()
                                    st.success("✅ Plateforme mise à jour !")
                                    refresh_data()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {e}")
                        
                        with col_del:
                            if st.form_submit_button("🗑️ Supprimer", use_container_width=True):
                                try:
                                    supabase.table('plateformes').delete().eq('id', plat['id']).execute()
                                    st.success("✅ Plateforme supprimée !")
                                    refresh_data()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {e}")
        else:
            st.info("Aucune plateforme enregistrée")
    
    # TAB 2 : AJOUTER UNE PLATEFORME
    with tab2:
        st.subheader("➕ Ajouter une nouvelle plateforme")
        
        st.info("💡 **Astuce** : Choisissez une couleur distinctive pour chaque plateforme. Elle sera utilisée dans le calendrier.")
        
        with st.form("form_nouvelle_plateforme"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                nom_plateforme = st.text_input("Nom de la plateforme *", placeholder="Ex: VRBO, Gîtes de France...")
                st.caption("Ce nom apparaîtra dans les réservations")
            
            with col2:
                commission_pct = st.number_input("Commission (%)", min_value=0.0, max_value=100.0, value=15.0, step=0.5)
                st.caption("Taux de commission de la plateforme")
            
            with col3:
                couleur = st.color_picker("Couleur pour le calendrier", value="#FF6B6B")
                st.markdown(f"""
                <div style='background-color: {couleur}; padding: 15px; border-radius: 5px; text-align: center; color: white; margin-top: 5px;'>
                    <b>Aperçu calendrier</b>
                </div>
                """, unsafe_allow_html=True)
            
            submitted = st.form_submit_button("✅ Ajouter la plateforme", type="primary", use_container_width=True)
            
            if submitted:
                if not nom_plateforme:
                    st.error("❌ Le nom est obligatoire")
                else:
                    try:
                        nouvelle_plat = {
                            'nom_plateforme': nom_plateforme.strip(),
                            'commission_pct': commission_pct,
                            'couleur': couleur
                        }
                        supabase.table('plateformes').insert(nouvelle_plat).execute()
                        st.success(f"✅ Plateforme '{nom_plateforme}' ajoutée avec succès !")
                        st.balloons()
                        refresh_data()
                        import time
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur : {e}")
                        if "duplicate key" in str(e).lower():
                            st.error("Cette plateforme existe déjà !")
    
    # TAB 3 : EXPORT
    with tab3:
        st.subheader("💾 Export des données")
        
    # reservations_df = get_reservations()
        if not reservations_df.empty:
            st.info(f"📊 {len(reservations_df)} réservation(s) à exporter")
            csv = reservations_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "📥 Télécharger toutes les réservations (CSV)",
                data=csv,
                file_name=f"reservations_export_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("Aucune réservation à exporter")

st.sidebar.markdown("---")
st.sidebar.markdown("*v1.1 - Gestion Locations Vacances*")
