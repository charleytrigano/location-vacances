# 🚀 GUIDE DE DÉPLOIEMENT - Gestion Locations Vacances

Guide complet étape par étape pour déployer votre application de gestion de locations.

---

## 📋 CHECKLIST AVANT DE COMMENCER

- [ ] Compte Supabase (gratuit)
- [ ] Compte GitHub (gratuit)
- [ ] Compte Streamlit Cloud (gratuit)
- [ ] Vos fichiers CSV de réservations (optionnel)

---

## ÉTAPE 1️⃣ : CONFIGURATION SUPABASE (15 minutes)

### A. Créer le projet

1. Allez sur https://supabase.com
2. Cliquez sur **"Start your project"**
3. **Sign up** avec GitHub ou email
4. Cliquez **"New Project"**
5. Remplissez :
   - **Name** : `location-vacances`
   - **Database Password** : Générez un mot de passe sécurisé (GARDEZ-LE !)
   - **Region** : Choisissez le plus proche (Europe West pour France)
6. Cliquez **"Create new project"**
7. ⏳ Attendez 2-3 minutes que le projet soit créé

### B. Créer les tables

1. Dans votre projet Supabase, menu de gauche → **SQL Editor**
2. Cliquez **"New query"**
3. Copiez-collez TOUT le contenu du fichier `SETUP_SUPABASE.sql`
4. Cliquez **"Run"** (en bas à droite)
5. ✅ Vous devriez voir : "Success. No rows returned"

### C. Vérifier les tables

1. Menu de gauche → **Table Editor**
2. Vous devez voir 3 tables :
   - ✅ `proprietes` (2 lignes : Le Turenne, Villa Tobias)
   - ✅ `plateformes` (5 lignes : Airbnb, Booking, etc.)
   - ✅ `reservations` (0 lignes pour l'instant)

### D. Récupérer vos credentials

1. Menu de gauche → **Settings** (⚙️ en bas)
2. Cliquez **API**
3. Notez (copiez dans un fichier texte) :
   - **Project URL** : `https://xxxxxxxxx.supabase.co`
   - **anon public key** : `eyJhbGciOiJIUzI1...` (très long)

---

## ÉTAPE 2️⃣ : IMPORT DES DONNÉES (10 minutes)

### Option A : Avec le script Python (recommandé)

Si vous avez Python installé :

1. Ouvrez `import_data.py`
2. Modifiez les lignes 9-10 :
```python
SUPABASE_URL = "https://VOTRE-PROJET.supabase.co"
SUPABASE_KEY = "eyJhbG..."  # Votre clé anon
```
3. Placez vos CSV dans le même dossier que le script
4. Ouvrez un terminal et exécutez :
```bash
pip install supabase pandas
python import_data.py
```
5. ✅ Vous devriez voir : "✅ Import terminé !"

### Option B : Import manuel via Supabase

Si vous n'avez pas Python :

1. Dans Supabase → **Table Editor** → `reservations`
2. Cliquez **"Insert"** → **"Import data from CSV"**
3. Uploadez vos fichiers CSV un par un
4. Mappez les colonnes correctement
5. Cliquez **"Import data"**

**Note** : Ajoutez manuellement `propriete_id` (1 pour Le Turenne, 2 pour Villa Tobias)

---

## ÉTAPE 3️⃣ : CRÉATION DU REPO GITHUB (5 minutes)

1. Allez sur https://github.com
2. Cliquez **"+"** (en haut à droite) → **"New repository"**
3. Remplissez :
   - **Repository name** : `location-vacances`
   - **Description** : `Application de gestion de locations vacances`
   - **Public** (cochez)
   - ✅ **Add a README file**
4. Cliquez **"Create repository"**

5. Uploadez les fichiers :
   - Cliquez **"Add file"** → **"Upload files"**
   - Glissez-déposez ces fichiers :
     - `app_locations.py` (renommez en `app.py`)
     - `requirements_locations.txt` (renommez en `requirements.txt`)
     - `README_LOCATIONS.md` (renommez en `README.md`)
   - Ajoutez un message : "Initial commit"
   - Cliquez **"Commit changes"**

---

## ÉTAPE 4️⃣ : DÉPLOIEMENT STREAMLIT CLOUD (10 minutes)

### A. Créer l'app

1. Allez sur https://streamlit.io/cloud
2. **Sign in** avec GitHub
3. Autorisez Streamlit à accéder à vos repos
4. Cliquez **"New app"**
5. Remplissez :
   - **Repository** : Sélectionnez `location-vacances`
   - **Branch** : `main`
   - **Main file path** : `app.py`
   - **App URL** : `location-vacances` (ou ce que vous voulez)
6. ⏳ Ne cliquez pas encore sur Deploy !

### B. Configurer les secrets

1. En dessous du formulaire, cliquez **"Advanced settings..."**
2. Dans l'onglet **Secrets**, collez :

```toml
SUPABASE_URL = "https://VOTRE-PROJET.supabase.co"
SUPABASE_KEY = "eyJhbG..."
```

⚠️ **IMPORTANT** : Remplacez par VOS vraies valeurs récupérées à l'étape 1.D

3. Cliquez **"Save"**

### C. Déployer !

1. Cliquez **"Deploy!"**
2. ⏳ Attendez 2-5 minutes (suivez les logs en temps réel)
3. ✅ L'app est en ligne quand vous voyez : "App is live!" 🎉

---

## ÉTAPE 5️⃣ : TESTER L'APPLICATION (5 minutes)

### Tests essentiels

1. **Tableau de Bord** :
   - Voyez-vous les KPIs ?
   - Les graphiques s'affichent-ils ?
   - Les données correspondent-elles à vos CSV ?

2. **Calendrier** :
   - Sélectionnez une propriété
   - Les réservations s'affichent-elles ?
   - Les jours occupés sont-ils en rouge ?

3. **Réservations** :
   - La liste complète apparaît-elle ?
   - Les filtres fonctionnent-ils ?
   - Testez la recherche par nom

4. **Nouvelle réservation** :
   - Créez une réservation test
   - Vérifiez qu'elle apparaît dans la liste

### En cas de problème

**Erreur : "Connection refused"**
→ Vérifiez vos secrets Supabase dans Streamlit Cloud

**Erreur : "Table does not exist"**
→ Retournez à l'étape 1.B, exécutez à nouveau le SQL

**Aucune donnée n'apparaît**
→ Vérifiez l'import des données (étape 2)

---

## ÉTAPE 6️⃣ : PERSONNALISATION (optionnel)

### Ajouter votre logo

1. Uploadez un logo sur votre repo GitHub
2. Dans `app.py`, remplacez l'URL du logo :
```python
st.sidebar.image("https://votre-url-logo.com/logo.png", width=100)
```

### Modifier les couleurs

Dans la section CSS de `app.py`, modifiez :
```css
.main-header {
    color: #1f77b4;  /* Changez cette couleur */
}
```

### Ajouter des propriétés

Dans Supabase → Table Editor → `proprietes` → **Insert row** :
- Nom : "Votre propriété"
- Ville : "Ville"
- Capacité : 4

---

## 🎯 RÉCAPITULATIF - TEMPS TOTAL : ~45 MINUTES

- ✅ Étape 1 : Configuration Supabase (15 min)
- ✅ Étape 2 : Import données (10 min)
- ✅ Étape 3 : Repo GitHub (5 min)
- ✅ Étape 4 : Déploiement Streamlit (10 min)
- ✅ Étape 5 : Tests (5 min)

---

## 📞 SUPPORT

### Problèmes fréquents

**"Module not found: supabase"**
→ Vérifiez que `requirements.txt` est bien à la racine du repo

**"SUPABASE_URL not found"**
→ Les secrets sont mal configurés dans Streamlit Cloud

**L'app est lente**
→ Normal sur le plan gratuit, utilisez le cache Streamlit

### Ressources

- Documentation Streamlit : https://docs.streamlit.io
- Documentation Supabase : https://supabase.com/docs
- GitHub du projet : https://github.com/votre-username/location-vacances

---

## 🎉 FÉLICITATIONS !

Votre application de gestion de locations est maintenant en ligne et accessible 24/7 !

URL de votre app : `https://location-vacances.streamlit.app`

Partagez cette URL avec vos collaborateurs ! 🚀
