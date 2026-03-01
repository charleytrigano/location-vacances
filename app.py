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

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #a78bfa;
        padding-bottom: 1rem;
        border-bottom: 3px solid #7c3aed;
    }
    .stMetric {
        background: linear-gradient(135deg, rgba(99, 102, 241, 0.15) 0%, rgba(139, 92, 246, 0.15) 100%) !important;
        padding: 1.2rem !important;
        border-radius: 10px !important;
        border: 2px solid rgba(124, 58, 237, 0.4) !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
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

def refresh_data():
    st.cache_data.clear()

reservations_df = get_reservations()
proprietes_df = get_proprietes()

# ==================== SIDEBAR ====================
st.sidebar.markdown("# 🏖️ Locations Vacances")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "Navigation",
    ["📊 Tableau de Bord", "📋 Réservations"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🔄 Rafraîchir les données"):
    refresh_data()
    st.rerun()

# ==================== RÉSERVATIONS ====================
if menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Gestion des Réservations</h1>", unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["📋 Liste", "➕ Nouvelle réservation", "✏️ Modifier/Supprimer"])
    
    # TAB 1: LISTE
    with tab1:
        if reservations_df.empty:
            st.info("Aucune réservation")
        else:
            st.dataframe(reservations_df, use_container_width=True, hide_index=True)
    
    # TAB 2: NOUVELLE RÉSERVATION
    with tab2:
        st.subheader("Nouvelle réservation")
        
        if proprietes_df.empty:
            st.warning("Aucune propriété enregistrée")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                propriete_id = st.selectbox("Propriété *", proprietes_df['id'].tolist(),
                                           format_func=lambda x: proprietes_df[proprietes_df['id']==x]['nom'].iloc[0],
                                           key="new_prop")
                nom_client = st.text_input("Nom client *", key="new_nom")
                
            with col2:
                plateformes_df_form = get_plateformes()
                if not plateformes_df_form.empty:
                    liste_plateformes = sorted(plateformes_df_form['nom_plateforme'].unique().tolist())
                else:
                    liste_plateformes = ['Direct', 'Airbnb', 'Booking']
                plateforme = st.selectbox("Plateforme", liste_plateformes, key="new_plat")
                
                numero_reservation = st.text_input("Numéro de réservation (optionnel)", key="new_num")
            
            col1, col2 = st.columns(2)
            with col1:
                date_arrivee = st.date_input("Date d'arrivée *", key="new_arr")
            with col2:
                date_depart = st.date_input("Date de départ *", key="new_dep")
            
            prix_brut = st.number_input("Prix brut (€) *", min_value=0.0, step=10.0, value=0.0, key="new_brut")
            
            if st.button("✅ Créer la réservation", type="primary", use_container_width=True):
                if not nom_client:
                    st.error("❌ Le nom du client est obligatoire")
                elif date_depart <= date_arrivee:
                    st.error("❌ La date de départ doit être après la date d'arrivée")
                else:
                    nuitees = (date_depart - date_arrivee).days
                    
                    nouvelle_res = {
                        'propriete_id': propriete_id,
                        'nom_client': nom_client,
                        'date_arrivee': date_arrivee.strftime('%Y-%m-%d'),
                        'date_depart': date_depart.strftime('%Y-%m-%d'),
                        'nuitees': nuitees,
                        'plateforme': plateforme,
                        'prix_brut': round(prix_brut, 2),
                        'prix_net': round(prix_brut, 2),
                        'numero_reservation': numero_reservation if numero_reservation else None,
                        'paye': False
                    }
                    
                    try:
                        supabase.table('reservations').insert(nouvelle_res).execute()
                        st.success("✅ Réservation créée avec succès !")
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
            col1, col2 = st.columns(2)
            with col1:
                search_nom = st.text_input("Nom du client", key="search_modify")
            
            df_search = reservations_df.copy()
            if search_nom:
                df_search = df_search[df_search['nom_client'].str.contains(search_nom, case=False, na=False)]
            
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
                    
                    if modifier_mode:
                        st.markdown("### ✏️ Modifier la réservation")
                        
                        with st.form("form_modifier"):
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
                            
                            with col2:
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
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                new_date_arrivee = st.date_input("Date d'arrivée *", value=reservation['date_arrivee'].date(), key="mod_arr")
                            with col2:
                                new_date_depart = st.date_input("Date de départ *", value=reservation['date_depart'].date(), key="mod_dep")
                            
                            new_prix_brut = st.number_input("Prix brut (€) *", min_value=0.0, step=10.0, value=float(reservation['prix_brut']), key="mod_brut")
                            
                            new_paye = st.checkbox("Déjà payé", value=bool(reservation['paye']), key="mod_paye")
                            
                            submitted_mod = st.form_submit_button("Enregistrer les modifications", type="primary")
                            
                            if submitted_mod:
                                if new_numero and new_numero.strip().upper() == "DEBUG999":
                                    st.error("ERREUR : DEBUG999 DETECTE !")
                                    st.error("Ce numero de reservation est utilise pour les tests. Modification bloquee.")
                                    st.error("Version V4.18 fonctionne correctement !")
                                    st.stop()
                                
                                if not new_nom_client:
                                    st.error("Le nom du client est obligatoire")
                                elif new_date_depart <= new_date_arrivee:
                                    st.error("La date de départ doit être après la date d'arrivée")
                                else:
                                    new_nuitees = (new_date_depart - new_date_arrivee).days
                                    
                                    updated_res = {
                                        'propriete_id': new_propriete_id,
                                        'nom_client': new_nom_client,
                                        'date_arrivee': new_date_arrivee.strftime('%Y-%m-%d'),
                                        'date_depart': new_date_depart.strftime('%Y-%m-%d'),
                                        'nuitees': new_nuitees,
                                        'plateforme': new_plateforme,
                                        'prix_brut': round(new_prix_brut, 2),
                                        'prix_net': round(new_prix_brut, 2),
                                        'numero_reservation': new_numero if new_numero else None,
                                        'paye': new_paye
                                    }
                                    
                                    try:
                                        supabase.table('reservations').update(updated_res).eq('id', res_id).execute()
                                        st.success("✅ Réservation modifiée avec succès !")
                                        refresh_data()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Erreur lors de la modification : {e}")
                    
                    if supprimer_mode:
                        st.session_state.delete_mode = True
                        st.session_state.delete_res_id = res_id
                    
                    if st.session_state.delete_mode and st.session_state.delete_res_id == res_id:
                        st.markdown("### 🗑️ Supprimer la réservation")
                        st.error(f"""
                        ATTENTION - SUPPRESSION DEFINITIVE
                        
                        Vous êtes sur le point de supprimer :
                        
                        Client : {reservation['nom_client']}  
                        Dates : {reservation['date_arrivee'].strftime('%d/%m/%Y')} → {reservation['date_depart'].strftime('%d/%m/%Y')}  
                        Prix : {reservation['prix_brut']:.2f} €
                        
                        Cette action est IRREVERSIBLE !
                        """)
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            if st.button("CONFIRMER LA SUPPRESSION", type="primary", use_container_width=True, key=f"confirm_del_{res_id}"):
                                try:
                                    supabase.table('reservations').delete().eq('id', res_id).execute()
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
                            if st.button("ANNULER", use_container_width=True, key=f"cancel_del_{res_id}"):
                                st.session_state.delete_mode = False
                                st.session_state.delete_res_id = None
                                st.rerun()

# ==================== TABLEAU DE BORD ====================
elif menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    
    if reservations_df.empty:
        st.info("Aucune réservation")
    else:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("📅 Réservations", len(reservations_df))
        with col2:
            st.metric("🌙 Nuitées", int(reservations_df['nuitees'].sum()))
        with col3:
            st.metric("💰 Revenu", f"{reservations_df['prix_brut'].sum():,.0f} €")
        with col4:
            taux_paye = (reservations_df['paye'].sum() / len(reservations_df) * 100) if len(reservations_df) > 0 else 0
            st.metric("✅ Taux payé", f"{taux_paye:.0f}%")

st.sidebar.markdown("---")
st.sidebar.markdown("*v4.19 - DEBUG999 Protection Active*")
