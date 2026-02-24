Script d'import des réservations dans Supabase
À exécuter une fois après avoir créé les tables
"""
import pandas as pd
from supabase import create_client, Client
import os

# Configuration Supabase
SUPABASE_URL = "VOTRE_URL_SUPABASE"  # À remplacer
SUPABASE_KEY = "VOTRE_CLE_SUPABASE"  # À remplacer

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def nettoyer_valeur(val):
    """Convertir les valeurs pour Supabase"""
    if pd.isna(val):
        return None
    if isinstance(val, str):
        val = val.strip()
        if val.upper() in ['VRAI', 'TRUE', '1']:
            return True
        if val.upper() in ['FAUX', 'FALSE', '0']:
            return False
    return val

def importer_reservations(csv_path, propriete_nom):
    """Importer les réservations d'un CSV"""
    print(f"\n📥 Import {propriete_nom}...")
    
    # Récupérer l'ID de la propriété
    prop = supabase.table('proprietes').select('id').eq('nom', propriete_nom).execute()
    if not prop.data:
        print(f"❌ Propriété '{propriete_nom}' non trouvée !")
        return
    
    propriete_id = prop.data[0]['id']
    
    # Lire le CSV
    df = pd.read_csv(csv_path)
    print(f"   {len(df)} réservations à importer")
    
    nb_imported = 0
    nb_errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Nettoyer les dates
            date_arrivee = pd.to_datetime(row['date_arrivee'], format='%d/%m/%Y', errors='coerce')
            if pd.isna(date_arrivee):
                date_arrivee = pd.to_datetime(row['date_arrivee'], format='%m/%d/%Y', errors='coerce')
            
            date_depart = pd.to_datetime(row['date_depart'], format='%d/%m/%Y', errors='coerce')
            if pd.isna(date_depart):
                date_depart = pd.to_datetime(row['date_depart'], format='%m/%d/%Y', errors='coerce')
            
            if pd.isna(date_arrivee) or pd.isna(date_depart):
                print(f"   ⚠️ Ligne {idx}: dates invalides, ignorée")
                continue
            
            reservation = {
                'propriete_id': propriete_id,
                'res_id': nettoyer_valeur(row.get('res_id')),
                'ical_uid': nettoyer_valeur(row.get('ical_uid')),
                'nom_client': nettoyer_valeur(row['nom_client']),
                'email': nettoyer_valeur(row.get('email')),
                'telephone': nettoyer_valeur(row.get('telephone')),
                'pays': nettoyer_valeur(row.get('pays')),
                'date_arrivee': date_arrivee.strftime('%Y-%m-%d'),
                'date_depart': date_depart.strftime('%Y-%m-%d'),
                'nuitees': int(float(row['nuitees'])) if pd.notna(row.get('nuitees')) else None,
                'plateforme': nettoyer_valeur(row.get('plateforme')),
                'prix_brut': float(row['prix_brut']) if pd.notna(row.get('prix_brut')) else 0,
                'commissions': float(row['commissions']) if pd.notna(row.get('commissions')) else 0,
                'frais_cb': float(row['frais_cb']) if pd.notna(row.get('frais_cb')) else 0,
                'prix_net': float(row['prix_net']) if pd.notna(row.get('prix_net')) else 0,
                'menage': float(row['menage']) if pd.notna(row.get('menage')) else 0,
                'taxes_sejour': float(row['taxes_sejour']) if pd.notna(row.get('taxes_sejour')) else 0,
                'base': float(row['base']) if pd.notna(row.get('base')) else 0,
                'charges': float(row['charges']) if pd.notna(row.get('charges')) else 0,
                'pct_commission': float(row['%']) if pd.notna(row.get('%')) else None,
                'paye': nettoyer_valeur(row.get('paye', False)),
                'sms_envoye': nettoyer_valeur(row.get('sms_envoye', False)),
                'post_depart_envoye': nettoyer_valeur(row.get('post_depart_envoye', False))
            }
            
            # Insérer ou mettre à jour
            result = supabase.table('reservations').upsert(reservation, on_conflict='res_id').execute()
            nb_imported += 1
            
            if (idx + 1) % 50 == 0:
                print(f"   ... {idx + 1} lignes traitées")
                
        except Exception as e:
            nb_errors += 1
            print(f"   ❌ Erreur ligne {idx}: {str(e)[:100]}")
    
    print(f"   ✅ Import terminé: {nb_imported} réservations | {nb_errors} erreurs")

if __name__ == "__main__":
    print("🚀 Import des réservations dans Supabase")
    print("=" * 60)
    
    # Import Le Turenne
    importer_reservations('reservations_le_turenne.csv', 'Le Turenne')
    
    # Import Villa Tobias
    importer_reservations('reservations_villatobias.csv', 'Villa Tobias')
    
    print("\n" + "=" * 60)
    print("✅ Import terminé !")
    
    # Vérification
    result = supabase.table('reservations').select('propriete_id, COUNT').execute()
    print(f"\n📊 Total réservations: {len(result.data) if result.data else 0}")
