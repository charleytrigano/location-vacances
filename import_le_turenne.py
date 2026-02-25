"""
Script d'import des réservations Le Turenne dans Supabase
"""
import pandas as pd
from supabase import create_client, Client

# ⚠️ REMPLACEZ PAR VOS VRAIES VALEURS
SUPABASE_URL = "https://kntkfczfxehgdsruhabu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImtudGtmY3pmeGVoZ2RzcnVoYWJ1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE5MzM1NDU..."

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def nettoyer_boolean(val):
    """Convertir VRAI/FAUX en boolean"""
    if pd.isna(val):
        return False
    val_str = str(val).strip().upper()
    return val_str in ['VRAI', 'TRUE', '1', 'OUI']

def importer_le_turenne(csv_path):
    """Importer les réservations Le Turenne"""
    print("📥 Lecture du fichier CSV...")
    df = pd.read_csv(csv_path)
    
    print(f"   Total lignes brutes: {len(df)}")
    
    # Filtrer les lignes vides (garder seulement celles avec nom_client)
    df = df[df['nom_client'].notna()].copy()
    print(f"   Lignes avec données valides: {len(df)}")
    
    if len(df) == 0:
        print("❌ Aucune ligne valide trouvée !")
        return
    
    # Récupérer l'ID de la propriété "Le Turenne"
    prop = supabase.table('proprietes').select('id').eq('nom', 'Le Turenne').execute()
    if not prop.data:
        print("❌ Propriété 'Le Turenne' non trouvée dans Supabase !")
        print("   Créez-la d'abord avec SETUP_SUPABASE.sql")
        return
    
    propriete_id = prop.data[0]['id']
    print(f"✅ Propriété 'Le Turenne' trouvée (ID: {propriete_id})")
    
    nb_imported = 0
    nb_errors = 0
    
    for idx, row in df.iterrows():
        try:
            # Nettoyer les dates (déjà au bon format YYYY-MM-DD)
            date_arrivee = str(row['date_arrivee']) if pd.notna(row['date_arrivee']) else None
            date_depart = str(row['date_depart']) if pd.notna(row['date_depart']) else None
            
            if not date_arrivee or not date_depart:
                print(f"   ⚠️ Ligne {idx}: dates manquantes, ignorée")
                continue
            
            # Préparer la réservation
            reservation = {
                'propriete_id': propriete_id,
                'res_id': str(row['res_id']) if pd.notna(row['res_id']) else None,
                'ical_uid': str(row['ical_uid']) if pd.notna(row['ical_uid']) else None,
                'nom_client': str(row['nom_client']),
                'email': str(row['email']) if pd.notna(row['email']) else None,
                'telephone': str(row['telephone']) if pd.notna(row['telephone']) else None,
                'pays': str(row['pays']) if pd.notna(row['pays']) else None,
                'date_arrivee': date_arrivee,
                'date_depart': date_depart,
                'nuitees': int(row['nuitees']) if pd.notna(row['nuitees']) else None,
                'plateforme': str(row['plateforme']) if pd.notna(row['plateforme']) else None,
                'prix_brut': float(row['prix_brut']) if pd.notna(row['prix_brut']) else 0,
                'commissions': float(row['commissions']) if pd.notna(row['commissions']) else 0,
                'frais_cb': float(row['frais_cb']) if pd.notna(row['frais_cb']) else 0,
                'prix_net': float(row['prix_brut']) - float(row['commissions']) - float(row['frais_cb']) if pd.notna(row['prix_brut']) else 0,
                'menage': float(row['menage']) if pd.notna(row['menage']) else 0,
                'taxes_sejour': float(row['taxes_sejour']) if pd.notna(row['taxes_sejour']) else 0,
                'base': float(row['base']) if pd.notna(row['base']) else 0,
                'charges': float(row['charges']) if pd.notna(row['charges']) else 0,
                'pct_commission': float(row['pct_commission']) if pd.notna(row['pct_commission']) else None,
                'paye': nettoyer_boolean(row['paye']),
                'sms_envoye': nettoyer_boolean(row['sms_envoye']),
                'post_depart_envoye': nettoyer_boolean(row['post_depart_envoye'])
            }
            
            # Insérer ou mettre à jour (upsert sur res_id)
            result = supabase.table('reservations').upsert(reservation, on_conflict='res_id').execute()
            nb_imported += 1
            
            if (nb_imported) % 10 == 0:
                print(f"   ... {nb_imported} réservations importées")
                
        except Exception as e:
            nb_errors += 1
            print(f"   ❌ Erreur ligne {idx}: {str(e)[:100]}")
    
    print(f"\n✅ Import terminé !")
    print(f"   - {nb_imported} réservations importées")
    print(f"   - {nb_errors} erreurs")
    
    # Vérification
    result = supabase.table('reservations').select('*').eq('propriete_id', propriete_id).execute()
    print(f"\n📊 Total réservations 'Le Turenne' dans Supabase: {len(result.data)}")

if __name__ == "__main__":
    print("🚀 Import réservations Le Turenne")
    print("=" * 60)
    
    # Import
    importer_le_turenne('reservations_le_turenne.csv')
    
    print("\n" + "=" * 60)
    print("✅ Terminé !")
