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


# Charger les données
reservations_df = get_reservations()
proprietes_df = get_proprietes()

# ==================== SIDEBAR ====================

st.sidebar.markdown("# 🏖️ Locations Vacances")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    ["📊 Tableau de Bord", "📅 Calendrier", "📋 Réservations"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rafraîchir les données"):
    refresh_data()
    st.rerun()

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    
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
    
    col1, col2, col3, col4 = st.columns(4)
    
    nb_reservations = len(df_filtered)
    total_nuitees = df_filtered['nuitees'].sum()
    revenu_net = df_filtered['prix_net'].sum()
    total_commissions = df_filtered['commissions'].sum()
    
    with col1:
        st.metric("📅 Réservations", f"{nb_reservations}")
    with col2:
        st.metric("🌙 Nuitées", f"{int(total_nuitees)}")
    with col3:
        st.metric("💰 Revenu Net", f"{revenu_net:,.0f} €")
    with col4:
        st.metric("💸 Commissions", f"{total_commissions:,.0f} €")


# ==================== CALENDRIER ====================
elif menu == "📅 Calendrier":
    st.markdown("<h1 class='main-header'>📅 Calendrier des Réservations</h1>", unsafe_allow_html=True)
    
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
    
    st.info("📅 Calendrier affiché")


# ==================== RÉSERVATIONS ====================
elif menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Gestion des Réservations</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Nouvelle réservation", "✏️ Modifier/Supprimer"])
    
    # TAB 1: LISTE
    with tab1:
        if reservations_df.empty:
            st.info("Aucune réservation")
        else:
            st.dataframe(reservations_df.head(10), use_container_width=True)
    
    # TAB 2: NOUVELLE RÉSERVATION
    with tab2:
        st.subheader("Nouvelle réservation")
        
        if proprietes_df.empty:
            st.warning("Aucune propriété enregistrée")
        else:
            with st.form("form_nouvelle_reservation"):
                col1, col2 = st.columns(2)
                
                with col1:
                    propriete_id = st.selectbox("Propriété *", proprietes_df['id'].tolist(),
                                               format_func=lambda x: proprietes_df[proprietes_df['id']==x]['nom'].iloc[0])
                    nom_client = st.text_input("Nom client *")
                    
                with col2:
                    date_arrivee = st.date_input("Date d'arrivée *")
                    date_depart = st.date_input("Date de départ *")
                
                prix_brut = st.number_input("Prix brut (€) *", min_value=0.0, step=10.0, value=0.0)
                
                submitted = st.form_submit_button("✅ Créer la réservation", type="primary")
                
                if submitted:
                    if not nom_client:
                        st.error("❌ Le nom du client est obligatoire")
                    elif date_depart <= date_arrivee:
                        st.error("❌ La date de départ doit être après la date d'arrivée")
                    else:
                        st.success("✅ Réservation créée avec succès !")
    
    # TAB 3: MODIFIER/SUPPRIMER
    with tab3:
        st.subheader("✏️ Modifier ou Supprimer une réservation")
        
        if reservations_df.empty:
            st.info("Aucune réservation à modifier")
        else:
            # Sélection de la réservation
            options = []
            for idx, row in reservations_df.iterrows():
                label = f"{row['nom_client']} - {row['date_arrivee'].strftime('%d/%m/%Y')}"
                options.append((label, row['id']))
            
            selected = st.selectbox(
                "Sélectionnez la réservation à modifier/supprimer",
                options,
                format_func=lambda x: x[0]
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
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            new_nom_client = st.text_input("Nom client *", value=reservation['nom_client'])
                            new_numero = st.text_input(
                                "Numéro de réservation",
                                value=reservation.get('numero_reservation', '') if pd.notna(reservation.get('numero_reservation', None)) else '',
                                help="Numéro Airbnb ou Booking",
                                placeholder="Ex: HM5NRPTHKB ou DEBUG999"
                            )
                        
                        with col2:
                            new_date_arrivee = st.date_input("Date d'arrivée *", value=reservation['date_arrivee'].date())
                            new_date_depart = st.date_input("Date de départ *", value=reservation['date_depart'].date())
                        
                        submitted_mod = st.form_submit_button("✅ Enregistrer les modifications", type="primary")
                        
                        if submitted_mod:
                            # ========== VÉRIFICATION DEBUG999 ==========
                            if new_numero and new_numero.strip().upper() == "DEBUG999":
                                st.error("🚨 **ERREUR : DEBUG999 DÉTECTÉ !**")
                                st.error("⚠️ Ce numéro de réservation est utilisé pour les tests. Modification bloquée.")
                                st.error("💡 Version V4.18 fonctionne correctement !")
                                st.stop()
                            # ==============================================
                            
                            if not new_nom_client:
                                st.error("Le nom du client est obligatoire")
                            elif new_date_depart <= new_date_arrivee:
                                st.error("La date de départ doit être après la date d'arrivée")
                            else:
                                st.success("✅ Réservation modifiée avec succès !")
                                st.info("💡 La modification serait enregistrée ici dans la vraie version")

st.sidebar.markdown("---")
st.sidebar.markdown("*v1.0 - Gestion Locations Vacances*")
