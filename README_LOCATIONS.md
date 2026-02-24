# 🏖️ Gestion Locations Vacances

Application complète de gestion de locations saisonnières construite avec Streamlit et Supabase.

## 📋 Fonctionnalités

### 📊 Tableau de Bord
- KPIs en temps réel (réservations, nuitées, revenus, commissions)
- Graphiques de performance par plateforme
- Évolution mensuelle des revenus et nuitées
- Prochaines arrivées

### 📅 Calendrier
- Vue mensuelle des disponibilités
- Visualisation des réservations par propriété
- Détection des périodes libres/occupées

### 📋 Réservations
- Liste complète avec filtres avancés
- Recherche par nom de client
- Création de nouvelles réservations
- Export CSV

### 💰 Analyses Financières
- Revenus bruts vs nets
- Suivi des commissions par plateforme
- Analyse mensuelle détaillée
- Comparaison multi-propriétés

### 🏠 Propriétés
- Gestion des biens locatifs
- Informations détaillées par propriété

## 🚀 Installation

### 1. Configuration Supabase

1. Créez un compte sur [Supabase](https://supabase.com)
2. Créez un nouveau projet
3. Dans le SQL Editor, exécutez le fichier `SETUP_SUPABASE.sql`
4. Notez votre `SUPABASE_URL` et `SUPABASE_KEY` (Settings → API)

### 2. Import des données

Si vous avez déjà des réservations en CSV :

```bash
# Modifiez import_data.py avec vos credentials Supabase
python import_data.py
```

### 3. Déploiement Streamlit Cloud

1. Créez un repo GitHub `location-vacances`
2. Ajoutez les fichiers :
   - `app_locations.py` → renommez en `app.py`
   - `requirements_locations.txt` → renommez en `requirements.txt`
   - `SETUP_SUPABASE.sql`
   - `README.md`

3. Sur [Streamlit Cloud](https://streamlit.io/cloud):
   - New app
   - Connectez votre repo GitHub
   - Dans **Settings → Secrets**, ajoutez :

```toml
SUPABASE_URL = "https://votre-projet.supabase.co"
SUPABASE_KEY = "votre_clé_publique_ici"
```

4. Deploy !

## 📁 Structure des données

### Table `proprietes`
- Nom de la propriété
- Ville, capacité
- Description

### Table `reservations`
- Client (nom, email, téléphone, pays)
- Dates (arrivée, départ, nuitées)
- Financier (prix brut, net, commissions, ménage, taxes)
- Statuts (payé, SMS envoyé, post-départ envoyé)
- Plateforme

### Table `plateformes`
- Nom de la plateforme
- Taux de commission

## 🎨 Captures d'écran

### Tableau de Bord
- KPIs temps réel
- Graphiques revenus
- Prochaines arrivées

### Calendrier
- Vue mensuelle
- Disponibilités
- Réservations du mois

## 🔧 Développement local

```bash
# Cloner le repo
git clone https://github.com/votre-username/location-vacances.git
cd location-vacances

# Installer les dépendances
pip install -r requirements.txt

# Créer .streamlit/secrets.toml
mkdir -p .streamlit
cat > .streamlit/secrets.toml << EOF
SUPABASE_URL = "votre_url"
SUPABASE_KEY = "votre_key"
EOF

# Lancer l'app
streamlit run app.py
```

## 📊 Données exemples

Le projet inclut 4 fichiers CSV d'exemple :
- `reservations_le_turenne.csv` (999 réservations)
- `reservations_villatobias.csv` (98 réservations)
- `plateformes_villa-tobias.csv`
- `plateformes.csv`

## 🤝 Support

Pour toute question ou problème, ouvrez une issue sur GitHub.

## 📝 License

MIT License - Libre d'utilisation et modification

## 👨‍💻 Auteur

Développé avec ❤️ pour simplifier la gestion de locations vacances

---

**Version**: 1.0  
**Dernière mise à jour**: Février 2026
