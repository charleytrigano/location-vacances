import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from supabase import create_client, Client
import calendar

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
        border-bottom: 3px solid #1f77b4;
    }
    .stMetric {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
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

# ==================== SIDEBAR ====================
st.sidebar.markdown("# 🏖️ Locations Vacances")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    ["📊 Tableau de Bord", "📅 Calendrier", "📋 Réservations", 
     "💰 Analyses Financières", "🏠 Propriétés", "🔧 Paramètres"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rafraîchir les données"):
    refresh_data()
    st.rerun()

# ==================== TABLEAU DE BORD ====================
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    
    reservations_df = get_reservations()
    proprietes_df = get_proprietes()
    
    if reservations_df.empty:
        st.warning("⚠️ Aucune réservation. Importez vos données d'abord.")
        st.info("👉 Allez dans Paramètres pour voir les instructions d'import")
        st.stop()
    
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
    
    # KPIs
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
    
    reservations_df = get_reservations()
    proprietes_df = get_proprietes()
    
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
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("Aucune réservation ce mois-ci")

# ==================== RÉSERVATIONS ====================
elif menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Gestion des Réservations</h1>", unsafe_allow_html=True)
    
    reservations_df = get_reservations()
    proprietes_df = get_proprietes()
    
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
                        st.error(f"❌ Erreur lors de la création : {e}")
            
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

# ==================== ANALYSES FINANCIÈRES ====================
elif menu == "💰 Analyses Financières":
    st.markdown("<h1 class='main-header'>💰 Analyses Financières</h1>", unsafe_allow_html=True)
    
    reservations_df = get_reservations()
    proprietes_df = get_proprietes()
    
    if reservations_df.empty:
        st.warning("Aucune donnée")
        st.stop()
    
    # Filtres
    col1, col2 = st.columns(2)
    with col1:
        annee_sel = st.selectbox("📅 Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True))
    with col2:
        props = ['Toutes'] + proprietes_df['nom'].tolist() if not proprietes_df.empty else ['Toutes']
        prop_sel = st.selectbox("🏠 Propriété", props)
    
    df_filtered = reservations_df[reservations_df['date_arrivee'].dt.year == annee_sel].copy()
    if prop_sel != 'Toutes' and not proprietes_df.empty:
        prop_id = proprietes_df[proprietes_df['nom'] == prop_sel]['id'].iloc[0]
        df_filtered = df_filtered[df_filtered['propriete_id'] == prop_id]
    
    # KPIs financiers
    st.divider()
    col1, col2, col3, col4 = st.columns(4)
    
    revenus_bruts = df_filtered['prix_brut'].sum()
    revenus_nets = df_filtered['prix_net'].sum()
    total_commissions = df_filtered['commissions'].sum()
    total_menage = df_filtered['menage'].sum()
    
    with col1:
        st.metric("💵 Revenus bruts", f"{revenus_bruts:,.0f} €")
    with col2:
        st.metric("💰 Revenus nets", f"{revenus_nets:,.0f} €")
    with col3:
        st.metric("💸 Commissions", f"{total_commissions:,.0f} €", 
                 delta=f"-{total_commissions/revenus_bruts*100:.1f}%" if revenus_bruts > 0 else "0%")
    with col4:
        st.metric("🧹 Ménage", f"{total_menage:,.0f} €")
    
    # Graphiques
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Revenus mensuels")
        df_filtered['mois'] = df_filtered['date_arrivee'].dt.month
        revenus_mois = df_filtered.groupby('mois').agg({
            'prix_brut': 'sum',
            'prix_net': 'sum',
            'commissions': 'sum'
        }).reset_index()
        revenus_mois['mois_nom'] = revenus_mois['mois'].apply(lambda x: calendar.month_name[x])
        
        fig = go.Figure()
        fig.add_trace(go.Bar(name='Brut', x=revenus_mois['mois_nom'], y=revenus_mois['prix_brut'], marker_color='lightblue'))
        fig.add_trace(go.Bar(name='Net', x=revenus_mois['mois_nom'], y=revenus_mois['prix_net'], marker_color='darkblue'))
        fig.update_layout(barmode='group', yaxis_title='Montant (€)')
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.subheader("Commissions par plateforme")
        comm_plat = df_filtered.groupby('plateforme')['commissions'].sum().reset_index()
        comm_plat = comm_plat.sort_values('commissions', ascending=False)
        fig = px.bar(comm_plat, x='plateforme', y='commissions',
                    color='commissions', color_continuous_scale='Reds')
        st.plotly_chart(fig, use_container_width=True)

# ==================== MESSAGES ====================
elif menu == "✉️ Messages":
    st.markdown("<h1 class='main-header'>✉️ Messages Automatiques</h1>", unsafe_allow_html=True)
    
    st.info("💡 **Messages personnalisés** : Générez des messages J-1 (avant arrivée) et J+1 (après départ) dans la langue du client")
    
    reservations_df = get_reservations()
    proprietes_df = get_proprietes()
    
    if reservations_df.empty:
        st.warning("Aucune réservation disponible")
    else:
        # Fusionner avec propriétés pour avoir les noms
        if not proprietes_df.empty:
            reservations_df = reservations_df.merge(proprietes_df[['id', 'nom']], 
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
                
                if type_message == "📅 J-1 Avant arrivée":
                    # Message J-1
                    if langue_code == 'fr':
                        message = f"""🏠 {prop_nom}
📱 Plateforme : {reservation['plateforme']}
📅 Arrivée : {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Départ : {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Nuitées : {int(reservation['nuitees'])}

Bonjour {reservation['nom_client']},

Bienvenue chez nous ! 🌟

Nous sommes ravis de vous accueillir bientôt à Nice. Afin d'organiser au mieux votre réception, nous vous demandons de bien vouloir nous indiquer votre heure d'arrivée.

🅿️ Un parking est à votre disposition sur place.

⏰ Check-in : à partir de 14:00
⏰ Check-out : avant 11:00

🔑 Nous serons sur place lors de votre arrivée pour vous remettre les clés.

🎒 Vous trouverez des consignes à bagages dans chaque quartier, à Nice.

Nous vous souhaitons un excellent voyage et nous nous réjouissons de vous rencontrer très bientôt ! ✈️"""
                    
                    elif langue_code == 'en':
                        message = f"""🏠 {prop_nom}
📱 Platform: {reservation['plateforme']}
📅 Arrival: {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Departure: {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Nights: {int(reservation['nuitees'])}

Hello {reservation['nom_client']},

Welcome! 🌟

We are delighted to welcome you soon to Nice. To best organize your reception, please let us know your arrival time.

🅿️ Parking is available on site.

⏰ Check-in: from 2:00 PM
⏰ Check-out: before 11:00 AM

🔑 We will be on site when you arrive to hand you the keys.

🎒 You will find luggage storage in every neighborhood in Nice.

We wish you an excellent trip and look forward to meeting you very soon! ✈️"""
                    
                    else:  # español
                        message = f"""🏠 {prop_nom}
📱 Plataforma: {reservation['plateforme']}
📅 Llegada: {reservation['date_arrivee'].strftime('%d/%m/%Y')}  |  Salida: {reservation['date_depart'].strftime('%d/%m/%Y')}  |  Noches: {int(reservation['nuitees'])}

Hola {reservation['nom_client']},

¡Bienvenido! 🌟

Estamos encantados de recibirle pronto en Niza. Para organizar mejor su recepción, le rogamos que nos indique su hora de llegada.

🅿️ Hay aparcamiento disponible en el lugar.

⏰ Check-in: a partir de las 14:00
⏰ Check-out: antes de las 11:00

🔑 Estaremos presentes a su llegada para entregarle las llaves.

🎒 Encontrará consignas de equipaje en cada barrio de Niza.

¡Le deseamos un excelente viaje y esperamos conocerle muy pronto! ✈️"""
                
                else:  # J+1 Après départ
                    if langue_code == 'fr':
                        message = f"""🏠 {prop_nom}

Bonjour {reservation['nom_client']},

Un grand merci d'avoir choisi notre appartement pour votre séjour. 🙏

Nous espérons que vous avez passé un moment agréable et que vous avez pu profiter de tout ce que Nice a à offrir. ☀️

Si vous souhaitez revenir explorer encore un peu la ville, notre porte vous sera toujours grande ouverte. 🚪

Au plaisir de vous accueillir à nouveau ! 🌟"""
                    
                    elif langue_code == 'en':
                        message = f"""🏠 {prop_nom}

Hello {reservation['nom_client']},

A big thank you for choosing our apartment for your stay. 🙏

We hope you had a pleasant time and were able to enjoy everything Nice has to offer. ☀️

If you would like to come back and explore the city a bit more, our door will always be wide open. 🚪

Looking forward to welcoming you again! 🌟"""
                    
                    else:  # español
                        message = f"""🏠 {prop_nom}

Hola {reservation['nom_client']},

Muchas gracias por elegir nuestro apartamento para su estancia. 🙏

Esperamos que haya pasado un momento agradable y que haya podido disfrutar de todo lo que Niza tiene para ofrecer. ☀️

Si desea volver para explorar un poco más la ciudad, nuestra puerta siempre estará abierta. 🚪

¡Esperamos darle la bienvenida de nuevo! 🌟"""
                
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

# ==================== PROPRIÉTÉS ====================
elif menu == "🏠 Propriétés":
    st.markdown("<h1 class='main-header'>🏠 Gestion des Propriétés</h1>", unsafe_allow_html=True)
    
    proprietes_df = get_proprietes()
    
    if not proprietes_df.empty:
        for _, prop in proprietes_df.iterrows():
            with st.expander(f"🏠 {prop['nom']}", expanded=True):
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.write(f"**Ville**: {prop.get('ville', 'N/A')}")
                with col2:
                    st.write(f"**Capacité**: {prop.get('capacite', 'N/A')} personnes")
                with col3:
                    st.write(f"**ID**: {prop['id']}")
    else:
        st.info("Aucune propriété enregistrée")

# ==================== PARAMÈTRES ====================
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
        
        reservations_df = get_reservations()
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
