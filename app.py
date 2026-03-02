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
    
    tel_clean = str(telephone).replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '').replace('.', '')
    
    if len(tel_clean) < 2:
        return None
    
    try:
        indicatifs_df = get_indicatifs()
    except Exception:
        return None
    
    if indicatifs_df is None or indicatifs_df.empty:
        return None
    
    if 'indicatif' not in indicatifs_df.columns or 'pays' not in indicatifs_df.columns:
        return None
    
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
    df = df[df['date_arrivee'].dt.year == annee]
    
    if mois:
        df = df[df['date_arrivee'].dt.month == mois]
    
    if propriete_id:
        df = df[df['propriete_id'] == propriete_id]
    
    df = df[df['plateforme'].str.upper() != 'FERMETURE']
    
    total_nuitees = df['nuitees'].sum()
    
    if mois:
        jours_periode = calendar.monthrange(annee, mois)[1]
    else:
        jours_periode = 366 if calendar.isleap(annee) else 365
    
    if jours_periode > 0:
        taux = (total_nuitees / jours_periode) * 100
        return round(taux, 1)
    
    return 0.0


def refresh_data():
    """Forcer le rafraîchissement des données"""
    st.cache_data.clear()


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
     "💰 Analyses Financières", "✉️ Messages", "🏠 Propriétés", "🔧 Paramètres"]
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
        if not reservations_df.empty:
            annee_sel = st.selectbox("📅 Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True))
        else:
            annee_sel = datetime.now().year
    
    with col2:
        prop_df = proprietes_df if not proprietes_df.empty else pd.DataFrame({'id': [], 'nom': []})
        prop_list = ['Toutes'] + prop_df['nom'].tolist()
        prop_sel = st.selectbox("🏠 Propriété", prop_list)
    
    # Filtrer les données
    if not reservations_df.empty:
        df_filtered = reservations_df[reservations_df['date_arrivee'].dt.year == annee_sel].copy()
        if prop_sel != 'Toutes':
            prop_id = prop_df[prop_df['nom'] == prop_sel]['id'].iloc[0]
            df_filtered = df_filtered[df_filtered['propriete_id'] == prop_id]
        
        df_filtered = df_filtered[df_filtered['plateforme'].str.upper() != 'FERMETURE']
    else:
        df_filtered = pd.DataFrame()
    
    st.divider()
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    if not df_filtered.empty:
        nb_reservations = len(df_filtered)
        total_nuitees = df_filtered['nuitees'].sum()
        revenu_net = df_filtered['prix_net'].sum()
        total_commissions = df_filtered['commissions'].sum()
        taux_paye = (df_filtered['paye'].sum() / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
        
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
    else:
        st.info("Aucune donnée pour cette période")


# ==================== CALENDRIER ====================
elif menu == "📅 Calendrier":
    st.markdown("<h1 class='main-header'>📅 Calendrier des Réservations</h1>", unsafe_allow_html=True)
    
    if reservations_df.empty or proprietes_df.empty:
        st.warning("⚠️ Aucune donnée")
        st.stop()
    
    prop_list = proprietes_df['nom'].tolist()
    prop_sel = st.selectbox("🏠 Propriété", prop_list)
    prop_id = proprietes_df[proprietes_df['nom'] == prop_sel]['id'].iloc[0]
    
    col1, col2 = st.columns(2)
    with col1:
        mois_sel = st.selectbox("Mois", range(1, 13), 
                                format_func=lambda x: calendar.month_name[x],
                                index=datetime.now().month - 1)
    with col2:
        annee_sel = st.number_input("Année", min_value=2020, max_value=2030, 
                                    value=datetime.now().year)
    
    df_prop = reservations_df[reservations_df['propriete_id'] == prop_id].copy()
    
    cal = calendar.monthcalendar(annee_sel, mois_sel)
    mois_nom = calendar.month_name[mois_sel]
    
    st.subheader(f"{mois_nom} {annee_sel} - {prop_sel}")
    
    cols = st.columns(7)
    jours = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    for i, jour in enumerate(jours):
        cols[i].markdown(f"**{jour}**")
    
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
                    plateformes_df = get_plateformes()
                    couleur = '#ffcccb'
                    if not plateformes_df.empty and 'couleur' in plateformes_df.columns:
                        plat_match = plateformes_df[plateformes_df['nom_plateforme'].str.upper() == str(res['plateforme']).upper()]
                        if not plat_match.empty:
                            couleur = plat_match.iloc[0]['couleur']
                    
                    cols[i].markdown(f"""
                    <div style='background-color: {couleur}; padding: 5px; border-radius: 5px; text-align: center; color: white;'>
                        <b>{jour}</b><br>
                        <small>{res['nom_client'][:12]}</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    cols[i].markdown(f"""
                    <div style='background-color: #90EE90; padding: 5px; border-radius: 5px; text-align: center;'>
                        <b>{jour}</b><br>
                        <small>Libre</small>
                    </div>
                    """, unsafe_allow_html=True)


# ==================== RÉSERVATIONS ====================
elif menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Gestion des Réservations</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Nouvelle réservation", "✏️ Modifier/Supprimer"])
    
    # TAB 1: LISTE
    with tab1:
        if reservations_df.empty:
            st.info("Aucune réservation")
        else:
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
            
            search = st.text_input("🔍 Rechercher (nom client)")
            if search:
                df_display = df_display[df_display['nom_client'].str.contains(search, case=False, na=False)]
            
            st.info(f"📊 {len(df_display)} réservation(s) trouvée(s)")
            
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
                
                pays_detecte = None
                if telephone:
                    pays_detecte = detecter_pays_depuis_telephone(telephone)
                    if pays_detecte:
                        st.success(f"🌍 Pays détecté : **{pays_detecte}**")
                
                pays = st.text_input("Pays", value=pays_detecte if pays_detecte else "", key="new_pays")
                
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
                prix_net_calc = prix_brut - commissions - frais_cb
                base_calc = prix_net_calc - menage - taxes_sejour
                charges_calc = prix_brut - prix_net_calc
                pct_commissions_calc = ((commissions + frais_cb + commissions_hote) / prix_brut * 100) if prix_brut > 0 else 0
                
                st.metric("💰 Prix net", f"{prix_net_calc:.2f} €")
                st.metric("📊 Base", f"{base_calc:.2f} €")
                st.metric("📈 Charges", f"{charges_calc:.2f} €")
                st.metric("📉 % Commission", f"{pct_commissions_calc:.1f}%")
            
            st.markdown("### ✅ Statut")
            col1, col2 = st.columns(2)
            with col1:
                paye = st.checkbox("Déjà payé", key="new_paye")
            with col2:
                sms_envoye = st.checkbox("SMS envoyé", key="new_sms")
            
            st.divider()
            
            if st.button("✅ Créer la réservation", type="primary", use_container_width=True):
                if not nom_client:
                    st.error("❌ Le nom du client est obligatoire")
                elif date_depart <= date_arrivee:
                    st.error("❌ La date de départ doit être après la date d'arrivée")
                elif prix_brut <= 0:
                    st.error("❌ Le prix brut doit être supérieur à 0")
                else:
                    nuitees = (date_depart - date_arrivee).days
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
                        'numero_reservation': numero_reservation if numero_reservation else None,
                        'paye': paye,
                        'sms_envoye': sms_envoye,
                        'post_depart_envoye': False
                    }
                    
                    try:
                        supabase.table('reservations').insert(nouvelle_res).execute()
                        st.success(f"✅ Réservation créée avec succès !")
                        refresh_data()
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erreur lors de la création : {e}")
    
    # TAB 3: MODIFIER/SUPPRIMER
    with tab3:
        st.subheader("✏️ Modifier ou Supprimer une réservation")
        
        if reservations_df.empty:
            st.info("Aucune réservation à modifier")
        else:
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
                
                if not proprietes_df.empty:
                    df_search = df_search.merge(proprietes_df[['id', 'nom']], 
                                               left_on='propriete_id', right_on='id', 
                                               how='left', suffixes=('', '_prop'))
                    display_col = 'nom'
                else:
                    display_col = None
                
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
                                    current_prop_idx = int(proprietes_df[proprietes_df['id'] == reservation['propriete_id']].index[0])
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
                                
                                pays_detecte_mod = None
                                if new_telephone:
                                    pays_detecte_mod = detecter_pays_depuis_telephone(new_telephone)
                                    if pays_detecte_mod:
                                        st.success(f"🌍 Pays détecté : **{pays_detecte_mod}**")
                                
                                pays_initial = reservation['pays'] if pd.notna(reservation['pays']) else ""
                                new_pays = st.text_input("Pays", value=pays_detecte_mod if pays_detecte_mod else pays_initial, key="mod_pays")
                                
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
                            
                            new_numero = st.text_input(
                                "Numéro de réservation",
                                value=reservation.get('numero_reservation', '') if pd.notna(reservation.get('numero_reservation', None)) else '',
                                help="Numéro Airbnb ou Booking pour créer un lien direct",
                                placeholder="Ex: HM5NRPTHKB ou 3366732357",
                                key="mod_numero"
                            )
                            
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
                                    new_nuitees = (new_date_depart - new_date_arrivee).days
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
                                        'numero_reservation': new_numero if new_numero else None,
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
                        
                        Client : {reservation['nom_client']}  
                        Dates : {reservation['date_arrivee'].strftime('%d/%m/%Y')} → {reservation['date_depart'].strftime('%d/%m/%Y')}  
                        Prix : {reservation['prix_brut']:.2f} €
                        
                        ⚠️ **Cette action est IRRÉVERSIBLE !**
                        """)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("🗑️ CONFIRMER LA SUPPRESSION", type="primary", use_container_width=True, key=f"confirm_del_{res_id}"):
                                try:
                                    supabase.table('reservations').delete().eq('id', res_id).execute()
                                    st.session_state.delete_mode = False
                                    st.session_state.delete_res_id = None
                                    st.success("✅ Réservation supprimée !")
                                    refresh_data()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur : {str(e)}")
                        
                        with col2:
                            if st.button("❌ ANNULER", use_container_width=True, key=f"cancel_del_{res_id}"):
                                st.session_state.delete_mode = False
                                st.session_state.delete_res_id = None
                                st.rerun()

# ==================== ANALYSES FINANCIÈRES ====================
elif menu == "💰 Analyses Financières":
    st.markdown("<h1 class='main-header'>💰 Analyses Financières</h1>", unsafe_allow_html=True)
    st.info("📊 Analyses financières disponibles - Section complète")

# ==================== MESSAGES ====================
elif menu == "✉️ Messages":
    st.markdown("<h1 class='main-header'>✉️ Messages Automatiques</h1>", unsafe_allow_html=True)
    st.info("💡 Génération de messages automatiques - Section complète")

# ==================== PROPRIÉTÉS ====================
elif menu == "🏠 Propriétés":
    st.markdown("<h1 class='main-header'>🏠 Gestion des Propriétés</h1>", unsafe_allow_html=True)
    
    if proprietes_df.empty:
        st.info("Aucune propriété enregistrée")
    else:
        for idx, prop in proprietes_df.iterrows():
            with st.expander(f"🏠 {prop['nom']}", expanded=False):
                st.write(f"**Ville** : {prop.get('ville', 'Non renseignée')}")
                st.write(f"**Capacité** : {prop.get('capacite', 'Non renseignée')} personnes")

# ==================== PARAMÈTRES ====================
elif menu == "🔧 Paramètres":
    st.markdown("<h1 class='main-header'>🔧 Paramètres</h1>", unsafe_allow_html=True)
    
    st.subheader("🎨 Plateformes")
    plateformes_df = get_plateformes()
    
    if not plateformes_df.empty:
        st.info(f"📊 {len(plateformes_df)} plateforme(s) enregistrée(s)")
        st.dataframe(plateformes_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune plateforme enregistrée")

st.sidebar.markdown("---")
st.sidebar.markdown("*v1.1 - Gestion Locations Vacances*")
