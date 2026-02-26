"""
Script d'import des indicatifs pays dans Supabase
À exécuter une fois après avoir créé la table indicatifs_pays
"""
import pandas as pd
from supabase import create_client, Client

# ⚠️ REMPLACEZ PAR VOS VRAIES VALEURS
SUPABASE_URL = "https://kntkfczfxehgdsruhabu.supabase.co"
SUPABASE_KEY = "VOTRE_CLE_SUPABASE"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def importer_indicatifs(csv_path):
    """Importer les indicatifs pays"""
    print("📥 Lecture du fichier CSV...")
    
    # Lire avec le bon séparateur
    df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig', skiprows=1)
    df.columns = ['Indicatif', 'Pays', 'Drapeau', 'CodeISO']
    
    # Nettoyer les indicatifs
    df['Indicatif'] = df['Indicatif'].astype(str).str.replace('-', '').str.replace(',', '.').str.strip()
    df['Pays'] = df['Pays'].str.strip()
    df['CodeISO'] = df['CodeISO'].str.strip()
    
    print(f"   {len(df)} pays trouvés")
    
    nb_imported = 0
    nb_errors = 0
    
    for idx, row in df.iterrows():
        try:
            indicatif_data = {
                'indicatif': row['Indicatif'],
                'pays': row['Pays'],
                'drapeau': row['Drapeau'] if pd.notna(row['Drapeau']) else None,
                'code_iso': row['CodeISO'] if pd.notna(row['CodeISO']) else None
            }
            
            supabase.table('indicatifs_pays').insert(indicatif_data).execute()
            nb_imported += 1
            
            if (nb_imported) % 50 == 0:
                print(f"   ... {nb_imported} indicatifs importés")
                
        except Exception as e:
            nb_errors += 1
            if nb_errors <= 5:  # Afficher seulement les 5 premières erreurs
                print(f"   ⚠️ Erreur ligne {idx}: {str(e)[:80]}")
    
    print(f"\n✅ Import terminé !")
    print(f"   - {nb_imported} indicatifs importés")
    print(f"   - {nb_errors} erreurs")
    
    # Vérification
    result = supabase.table('indicatifs_pays').select('*').limit(10).execute()
    print(f"\n📊 Aperçu des 10 premiers indicatifs :")
    for item in result.data:
        print(f"   +{item['indicatif']} → {item['pays']}")

if __name__ == "__main__":
    print("🚀 Import des indicatifs pays dans Supabase")
    print("=" * 60)
    
    # Import
    importer_indicatifs('indicatifs_pays.csv')
    
    print("\n" + "=" * 60)
    print("✅ Terminé !")
