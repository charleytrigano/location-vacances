import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from supabase import create_client, Client
import calendar

# Configuration
st.set_page_config(page_title="Gestion Locations", page_icon="🏖️", layout="wide")

if 'delete_mode' not in st.session_state:
    st.session_state.delete_mode = False

st.markdown("""
<style>
.main-header {font-size: 2.5rem; color: #a78bfa; border-bottom: 3px solid #7c3aed;}
.stMetric {background: rgba(99, 102, 241, 0.15) !important; padding: 1.2rem !important; border-radius: 10px !important;}
</style>
""", unsafe_allow_html=True)

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

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
        st.error(f"Erreur: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_proprietes():
    try:
        response = supabase.table('proprietes').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_plateformes():
    try:
        response = supabase.table('plateformes').select('*').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

def calculer_taux_occupation(df, annee, mois=None):
    if df.empty:
        return 0.0
    df = df[(df['date_arrivee'].dt.year == annee) & (df['plateforme'].str.upper() != 'FERMETURE')]
    if mois:
        df = df[df['date_arrivee'].dt.month == mois]
    nuitees = df['nuitees'].sum()
    jours = calendar.monthrange(annee, mois)[1] if mois else (366 if calendar.isleap(annee) else 365)
    return round((nuitees / jours) * 100, 1) if jours > 0 else 0.0

def refresh_data():
    st.cache_data.clear()

reservations_df = get_reservations()
proprietes_df = get_proprietes()

# SIDEBAR
st.sidebar.markdown("# 🏖️ Locations")
st.sidebar.markdown("---")

menu = st.sidebar.radio("Navigation", 
    ["📊 Tableau de Bord", "📋 Réservations", "💰 Analyses Financières", "🔧 Paramètres"])

if st.sidebar.button("🔄 Rafraîchir"):
    refresh_data()
    st.rerun()

# TABLEAU DE BORD
if menu == "📊 Tableau de Bord":
    st.markdown("<h1 class='main-header'>📊 Tableau de Bord</h1>", unsafe_allow_html=True)
    
    if not reservations_df.empty:
        annee = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True))
        df = reservations_df[(reservations_df['date_arrivee'].dt.year == annee) & 
                             (reservations_df['plateforme'].str.upper() != 'FERMETURE')]
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📅 Réservations", len(df))
        col2.metric("🌙 Nuitées", int(df['nuitees'].sum()))
        col3.metric("💰 Revenu Net", f"{df['prix_net'].sum():,.0f} €")
        col4.metric("💸 Commissions", f"{df['commissions'].sum():,.0f} €")

# RÉSERVATIONS
elif menu == "📋 Réservations":
    st.markdown("<h1 class='main-header'>📋 Réservations</h1>", unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["📋 Liste", "✏️ Modifier"])
    
    with tab1:
        if not reservations_df.empty:
            st.dataframe(reservations_df.head(20), use_container_width=True)
    
    with tab2:
        if not reservations_df.empty:
            search = st.text_input("🔍 Rechercher")
            df_search = reservations_df[reservations_df['nom_client'].str.contains(search, case=False, na=False)] if search else reservations_df
            
            if not df_search.empty:
                options = [(f"{r['nom_client']} - {r['date_arrivee'].strftime('%d/%m/%Y')}", r['id']) 
                          for _, r in df_search.iterrows()]
                selected = st.selectbox("Sélection", options, format_func=lambda x: x[0])
                
                if selected:
                    res = reservations_df[reservations_df['id'] == selected[1]].iloc[0]
                    
                    with st.form("modifier"):
                        new_nom = st.text_input("Nom", value=res['nom_client'])
                        new_numero = st.text_input("N° réservation", 
                                                   value=res.get('numero_reservation', ''),
                                                   placeholder="DEBUG999")
                        
                        if st.form_submit_button("✅ Enregistrer"):
                            if new_numero and new_numero.strip().upper() == "DEBUG999":
                                st.error("🚨 DEBUG999 DÉTECTÉ ! Modification bloquée.")
                                st.stop()
                            
                            try:
                                supabase.table('reservations').update({
                                    'nom_client': new_nom,
                                    'numero_reservation': new_numero or None
                                }).eq('id', selected[1]).execute()
                                st.success("✅ Modifié !")
                                refresh_data()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erreur: {e}")

# ANALYSES FINANCIÈRES
elif menu == "💰 Analyses Financières":
    st.markdown("<h1 class='main-header'>💰 Analyses Financières</h1>", unsafe_allow_html=True)
    
    if reservations_df.empty:
        st.warning("Aucune donnée")
        st.stop()
    
    tab1, tab2 = st.tabs(["📊 Vue d'ensemble", "📅 Détail Mensuel par Plateforme"])
    
    with tab1:
        annee = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True))
        df = reservations_df[(reservations_df['date_arrivee'].dt.year == annee) & 
                             (reservations_df['plateforme'].str.upper() != 'FERMETURE')]
        
        col1, col2, col3 = st.columns(3)
        col1.metric("💰 CA Brut", f"{df['prix_brut'].sum():,.0f} €")
        col2.metric("💵 CA Net", f"{df['prix_net'].sum():,.0f} €")
        col3.metric("🌙 Nuitées", int(df['nuitees'].sum()))
    
    with tab2:
        st.subheader("📅 Détail Mensuel par Plateforme")
        
        annee = st.selectbox("Année", sorted(reservations_df['date_arrivee'].dt.year.unique(), reverse=True), key="det")
        df = reservations_df[(reservations_df['date_arrivee'].dt.year == annee) & 
                             (reservations_df['plateforme'].str.upper() != 'FERMETURE')].copy()
        
        if df.empty:
            st.warning("Aucune donnée")
        else:
            df['mois'] = df['date_arrivee'].dt.month
            
            # Agrégation par mois ET plateforme
            detail = df.groupby(['mois', 'plateforme']).agg({
                'prix_brut': 'sum',
                'prix_net': 'sum',
                'nuitees': 'sum',
                'id': 'count'
            }).reset_index()
            
            detail.columns = ['Mois', 'Plateforme', 'Prix Brut', 'Prix Net', 'Nuitées', 'Nb']
            
            # Taux occupation
            taux = [calculer_taux_occupation(reservations_df, annee, m) for m in detail['Mois']]
            detail['Taux Occ %'] = taux
            
            # Noms mois
            mois_noms = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                        'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
            mois_map = {i+1: nom for i, nom in enumerate(mois_noms)}
            detail['Mois'] = detail['Mois'].map(mois_map)
            
            # Afficher par mois
            for mois in mois_noms:
                df_mois = detail[detail['Mois'] == mois]
                
                if not df_mois.empty:
                    with st.expander(f"📅 {mois} {annee}"):
                        # Totaux
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("CA Brut", f"{df_mois['Prix Brut'].sum():,.0f} €")
                        col2.metric("CA Net", f"{df_mois['Prix Net'].sum():,.0f} €")
                        col3.metric("Nuitées", int(df_mois['Nuitées'].sum()))
                        col4.metric("Taux Occ", f"{df_mois['Taux Occ %'].iloc[0]}%")
                        
                        st.divider()
                        
                        # Tableau par plateforme
                        display = df_mois[['Plateforme', 'Prix Brut', 'Prix Net', 'Nuitées', 'Nb']].copy()
                        display['Prix Brut'] = display['Prix Brut'].round(0).astype(int)
                        display['Prix Net'] = display['Prix Net'].round(0).astype(int)
                        display['Nuitées'] = display['Nuitées'].astype(int)
                        
                        # TOTAL
                        total = pd.DataFrame([{
                            'Plateforme': '🔹 TOTAL',
                            'Prix Brut': int(df_mois['Prix Brut'].sum()),
                            'Prix Net': int(df_mois['Prix Net'].sum()),
                            'Nuitées': int(df_mois['Nuitées'].sum()),
                            'Nb': display['Nb'].sum()
                        }])
                        
                        display = pd.concat([display, total], ignore_index=True)
                        st.dataframe(display, use_container_width=True, hide_index=True)
            
            # Export
            st.divider()
            csv = detail.to_csv(index=False)
            st.download_button("📥 Télécharger CSV", data=csv, 
                             file_name=f"detail_{annee}.csv", mime="text/csv")

# PARAMÈTRES
elif menu == "🔧 Paramètres":
    st.markdown("<h1 class='main-header'>🔧 Paramètres</h1>", unsafe_allow_html=True)
    
    plateformes_df = get_plateformes()
    if not plateformes_df.empty:
        st.dataframe(plateformes_df, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("*v2.0*")
