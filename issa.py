import base64
from datetime import datetime
import io
import os
import sqlite3
import urllib.request
from fpdf import FPDF
import pandas as pd
import streamlit as st

# ==========================================
# 0. GESTION DE LA PERSISTANCE EXTERNE ET CLOUD GÉRÉ (SUPABASE / NEON / PLANETSCALE / SQLITE DISTANT)
# ==========================================
DB_FILE = "cpnm_database.db"

def init_sqlite_db():
    """Initialise la base de données SQLite avec de vraies tables relationnelles structurées 
    pour éviter de stocker de gros blocs JSON et garantir une robustesse à 100%."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eleves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prenom TEXT,
            nom TEXT,
            date_naissance TEXT,
            classe TEXT,
            photo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS professeurs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prenom TEXT,
            nom TEXT,
            matiere_principale TEXT,
            classe_attribuee TEXT,
            mot_de_passe TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS absences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            classe TEXT,
            eleve TEXT,
            statut TEXT,
            motif TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classe TEXT,
            matiere TEXT,
            periode TEXT,
            eleve TEXT,
            devoir1 REAL,
            devoir2 REAL,
            composition REAL,
            moyenne REAL
        )
    """)
    
    conn.commit()
    conn.close()

init_sqlite_db()

def charger_donnees_externes():
    """Charge les données depuis la base de données SQLite externe."""
    data = {}
    if os.path.exists(DB_FILE):
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM app_data")
            rows = cursor.fetchall()
            conn.close()
            for key, val_json in rows:
                import json
                data[key] = json.loads(val_json)
        except Exception:
            return {}
    return data

def sauvegarder_donnees_externes():
    """Sauvegarde toutes les bases de données de session dans la base SQLite externe 
    et synchronise systématiquement avec les tables relationnelles dédiées."""
    import json
    
    if "eleves_db" in st.session_state and not st.session_state.eleves_db.empty:
        if "Prénom" not in st.session_state.eleves_db.columns or "Nom" not in st.session_state.eleves_db.columns:
            prenoms = []
            noms = []
            for _, r in st.session_state.eleves_db.iterrows():
                nc = str(r.get("Nom Complet", ""))
                parts = nc.split(" ", 1)
                prenoms.append(parts[0] if len(parts) > 0 else "")
                noms.append(parts[1] if len(parts) > 1 else "")
            st.session_state.eleves_db["Prénom"] = prenoms
            st.session_state.eleves_db["Nom"] = noms

    data_to_save = {
        "admin_credentials": st.session_state.admin_credentials.to_dict(orient="split"),
        "gestionnaires_proprietaires_db": st.session_state.gestionnaires_proprietaires_db.to_dict(orient="split"),
        "prof_credentials": st.session_state.prof_credentials.to_dict(orient="split"),
        "parents_white_list": st.session_state.parents_white_list.to_dict(orient="split"),
        "classes_db": st.session_state.classes_db.to_dict(orient="split"),
        "eleves_db": st.session_state.eleves_db.to_dict(orient="split"),
        "base_globale_db": st.session_state.base_globale_db.to_dict(orient="split"),
        "cahier_textes": st.session_state.cahier_textes.to_dict(orient="split"),
        "rapports_journaliers_prof": st.session_state.rapports_journaliers_prof.to_dict(orient="split"),
        "absences_db": st.session_state.absences_db.to_dict(orient="split"),
        "matieres_def": st.session_state.matieres_def.to_dict(orient="split"),
        "coefficients_db": st.session_state.coefficients_db.to_dict(orient="split"),
        "periodes_db": st.session_state.periodes_db.to_dict(orient="split"),
        "notes_db": st.session_state.notes_db.to_dict(orient="split"),
        "viescolaire_db": st.session_state.viescolaire_db.to_dict(orient="split"),
        "conduite_db": st.session_state.conduite_db.to_dict(orient="split"),
        "edt_grid_db": {k: v.to_dict(orient="split") for k, v in st.session_state.edt_grid_db.items()},
        "edt_documents": {k: v for k, v in st.session_state.edt_documents.items()}
    }
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(eleves)")
        columns_info = [col[1] for col in cursor.fetchall()]
        if "nom" not in columns_info:
            cursor.execute("ALTER TABLE eleves ADD COLUMN nom TEXT")
        if "prenom" not in columns_info:
            cursor.execute("ALTER TABLE eleves ADD COLUMN prenom TEXT")
        if "date_naissance" not in columns_info:
            cursor.execute("ALTER TABLE eleves ADD COLUMN date_naissance TEXT")
        if "classe" not in columns_info:
            cursor.execute("ALTER TABLE eleves ADD COLUMN classe TEXT")
        if "photo" not in columns_info:
            cursor.execute("ALTER TABLE eleves ADD COLUMN photo TEXT")

        for key, value in data_to_save.items():
            cursor.execute("""
                INSERT INTO app_data (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, json.dumps(value, ensure_ascii=False)))
            
        if "eleves_db" in st.session_state and not st.session_state.eleves_db.empty:
            cursor.execute("DELETE FROM eleves")
            for _, r in st.session_state.eleves_db.iterrows():
                cursor.execute("INSERT INTO eleves (prenom, nom, date_naissance, classe, photo) VALUES (?, ?, ?, ?, ?)",
                               (r.get("Prénom"), r.get("Nom"), r.get("Date de Naissance"), r.get("Classe"), r.get("Photo")))

        if "prof_credentials" in st.session_state and not st.session_state.prof_credentials.empty:
            cursor.execute("DELETE FROM professeurs")
            for _, r in st.session_state.prof_credentials.iterrows():
                cursor.execute("INSERT INTO professeurs (prenom, nom, matiere_principale, classe_attribuee, mot_de_passe) VALUES (?, ?, ?, ?, ?)",
                               (r.get("Prénom"), r.get("Nom"), r.get("Matière Principale"), r.get("Classe Attribuée"), r.get("Mot de passe")))

        if "absences_db" in st.session_state and not st.session_state.absences_db.empty:
            cursor.execute("DELETE FROM absences")
            for _, r in st.session_state.absences_db.iterrows():
                cursor.execute("INSERT INTO absences (date, classe, eleve, statut, motif) VALUES (?, ?, ?, ?, ?)",
                               (r.get("Date"), r.get("Classe"), r.get("Élève"), r.get("Statut"), r.get("Motif")))

        conn.commit()
        conn.close()
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde externe SQLite : {e}")

saved_data = charger_donnees_externes()

# ==========================================
# 0. BIS. GESTION DES POLICES UNICODE (OPTIMISÉE POUR MOBILE)
# ==========================================
FONT_PATH = "DejaVuSans.ttf"

@st.cache_resource
def telecharger_polices():
    fonts = {
        "DejaVuSans.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
        "DejaVuSans-Oblique.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Oblique.ttf"
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    for font_name, font_url in fonts.items():
        if not os.path.exists(font_name):
            try:
                req = urllib.request.Request(font_url, headers=headers)
                with urllib.request.urlopen(req) as response, open(font_name, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception:
                pass

telecharger_polices()

# ==========================================
# 1. CONFIGURATION DE LA PAGE & DESIGN XXL RESPONSIVE FAST-LOAD
# ==========================================
st.set_page_config(
    page_title="Portail Pédagogique-École Président Nelson Mandela | Sénégal",
    page_icon="🇸🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main { background-color: #F8FAFC; }
    .header-ecole { 
        color: #1E3A8A; 
        font-size: clamp(1.8rem, 4vw, 2.8rem); 
        font-weight: 900; 
        text-align: center; 
        margin-bottom: 2px;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 0 10px;
    }
    .sub-header { 
        color: #047857; 
        font-size: clamp(0.9rem, 2vw, 1.2rem); 
        font-weight: 700; 
        text-align: center; 
        margin-bottom: 25px; 
        padding: 0 10px;
        font-style: italic;
    }
    .animated-card {
        border: 2px solid #E2E8F0;
        padding: clamp(15px, 3vw, 25px);
        border-radius: 16px;
        background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        text-align: center;
        cursor: pointer;
        margin-bottom: 15px;
        height: 100%;
    }
    .animated-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 15px 30px rgba(30, 58, 138, 0.12);
        border-color: #2563EB;
    }
    .kpi-card-animated {
        border-left: 5px solid #2563EB;
        background: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: center;
    }
    .stButton>button { 
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); 
        color: white; 
        border-radius: 8px; 
        font-weight: bold; 
        border: none;
        padding: 0.75rem 1rem;
        transition: transform 0.1s ease;
        width: 100%;
        min-height: 44px;
        font-size: 1rem;
    }
    .stButton>button:active {
        transform: scale(0.98);
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. INITIALISATION EXHAUSTIVE DES DONNÉES
# ==========================================
if "espace_actif" not in st.session_state:
    st.session_state.espace_actif = "🏠 Accueil"

if "authenticated_admin" not in st.session_state:
    st.session_state.authenticated_admin = False

if "admin_credentials" not in st.session_state:
    if "admin_credentials" in saved_data:
        st.session_state.admin_credentials = pd.DataFrame(**saved_data["admin_credentials"])
    else:
        st.session_state.admin_credentials = pd.DataFrame([
            {"Nom": "Principal", "Prénom": "Admin", "Email": "cpnm@gmail.com", "Mot de passe": "cpnm2026"}
        ])

if "gestionnaires_proprietaires_db" not in st.session_state:
    if "gestionnaires_proprietaires_db" in saved_data:
        st.session_state.gestionnaires_proprietaires_db = pd.DataFrame(**saved_data["gestionnaires_proprietaires_db"])
    else:
        st.session_state.gestionnaires_proprietaires_db = pd.DataFrame([
            {"Nom": "Mandela", "Prénom": "Propriétaire", "Email": "proprio@cpnm.sn", "Mot de passe": "proprio2026", "Rôle": "Propriétaire"},
            {"Nom": "Diop", "Prénom": "Gestionnaire", "Email": "gestion@cpnm.sn", "Mot de passe": "gestion2026", "Rôle": "Gestionnaire"}
        ])

if "prof_credentials" not in st.session_state:
    if "prof_credentials" in saved_data:
        st.session_state.prof_credentials = pd.DataFrame(**saved_data["prof_credentials"])
    else:
        st.session_state.prof_credentials = pd.DataFrame([
            {"Nom": "Diallo", "Prénom": "Ibrahima", "Mot de passe": "prof123", "Matière Principale": "Mathématiques", "Classe Attribuée": "6ème A"},
            {"Nom": "Sow", "Prénom": "Aissatou", "Mot de passe": "prof456", "Matière Principale": "Français", "Classe Attribuée": "CP"},
            {"Nom": "Ndiaye", "Prénom": "Cheikh", "Mot de passe": "prof789", "Matière Principale": "Histoire-Géographie", "Classe Attribuée": "5ème A"}
        ])

if "parents_white_list" not in st.session_state:
    if "parents_white_list" in saved_data:
        st.session_state.parents_white_list = pd.DataFrame(**saved_data["parents_white_list"])
    else:
        st.session_state.parents_white_list = pd.DataFrame([
            {"Téléphone": "+221771234567", "Prénom Élève": "Mamadou", "Nom Élève": "Diallo", "Année Naissance": 2012, "Classe": "6ème A"},
            {"Téléphone": "+221769876543", "Prénom Élève": "Fatou", "Nom Élève": "Sow", "Année Naissance": 2015, "Classe": "CP"},
        ])

if "classes_db" not in st.session_state:
    if "classes_db" in saved_data:
        st.session_state.classes_db = pd.DataFrame(**saved_data["classes_db"])
    else:
        st.session_state.classes_db = pd.DataFrame(
            columns=["Classe", "Cycle", "Professeur Responsable"],
            data=[
                ["CI", "Élémentaire", "Aissatou Sow"],
                ["CP", "Élémentaire", "Aissatou Sow"],
                ["CE1", "Élémentaire", "Ousmane Diop"],
                ["CE2", "Élémentaire", "Ousmane Diop"],
                ["CM1", "Élémentaire", "Marie Faye"],
                ["CM2", "Élémentaire", "Marie Faye"],
                ["6ème A", "Collège", "Ibrahima Diallo"],
                ["5ème A", "Collège", "Cheikh Ndiaye"],
                ["4ème A", "Collège", "Cheikh Ndiaye"],
                ["3ème A", "Collège", "Ibrahima Diallo"]
            ]
        )

if "eleves_db" not in st.session_state:
    if "eleves_db" in saved_data:
        st.session_state.eleves_db = pd.DataFrame(**saved_data["eleves_db"])
    else:
        st.session_state.eleves_db = pd.DataFrame(
            columns=["Nom Complet", "Prénom", "Nom", "Date de Naissance", "Classe", "Photo"],
            data=[
                ["Mamadou Diallo", "Mamadou", "Diallo", "2012-05-14", "6ème A", None],
                ["Fatou Sow", "Fatou", "Sow", "2015-08-20", "CP", None],
                ["Aminata Ba", "Aminata", "Ba", "2013-02-10", "6ème A", None],
                ["Oumar Sy", "Oumar", "Sy", "2011-11-03", "5ème A", None]
            ]
        )

if "matieres_def" not in st.session_state:
    if "matieres_def" in saved_data:
        st.session_state.matieres_def = pd.DataFrame(**saved_data["matieres_def"])
    else:
        st.session_state.matieres_def = pd.DataFrame([
            {"Matière": "Mathématiques", "Cycle": "Collège"},
            {"Matière": "Français", "Cycle": "Collège"},
            {"Matière": "Histoire-Géographie", "Cycle": "Collège"},
            {"Matière": "SVT", "Cycle": "Collège"},
            {"Matière": "Anglais", "Cycle": "Collège"},
            {"Matière": "Physique-Chimie", "Cycle": "Collège"},
            {"Matière": "Lecture / Langage", "Cycle": "Élémentaire"},
            {"Matière": "Calcul / Mathématiques", "Cycle": "Élémentaire"},
            {"Matière": "Éveil / Science", "Cycle": "Élémentaire"},
            {"Matière": "Éducation Civique", "Cycle": "Élémentaire"}
        ])

if "coefficients_db" not in st.session_state:
    if "coefficients_db" in saved_data:
        st.session_state.coefficients_db = pd.DataFrame(**saved_data["coefficients_db"])
    else:
        st.session_state.coefficients_db = pd.DataFrame([
            {"Classe": "6ème A", "Matière": "Mathématiques", "Coefficient": 3},
            {"Classe": "6ème A", "Matière": "Français", "Coefficient": 3},
            {"Classe": "6ème A", "Matière": "Histoire-Géographie", "Coefficient": 2},
            {"Classe": "6ème A", "Matière": "SVT", "Coefficient": 2},
            {"Classe": "6ème A", "Matière": "Anglais", "Coefficient": 2},
            {"Classe": "CP", "Matière": "Lecture / Langage", "Coefficient": 2},
            {"Classe": "CP", "Matière": "Calcul / Mathématiques", "Coefficient": 2},
            {"Classe": "CP", "Matière": "Éveil / Science", "Coefficient": 1}
        ])

if "periodes_db" not in st.session_state:
    if "periodes_db" in saved_data:
        st.session_state.periodes_db = pd.DataFrame(**saved_data["periodes_db"])
    else:
        st.session_state.periodes_db = pd.DataFrame([
            {"Période": "1er Trimestre", "Statut": "Ouvert"},
            {"Période": "2ème Trimestre", "Statut": "Fermé"},
            {"Période": "3ème Trimestre", "Statut": "Fermé"}
        ])

if "notes_db" not in st.session_state:
    if "notes_db" in saved_data:
        st.session_state.notes_db = pd.DataFrame(**saved_data["notes_db"])
    else:
        st.session_state.notes_db = pd.DataFrame(
            columns=["Classe", "Matière", "Periode", "Eleve", "Devoir1", "Devoir2", "Composition"],
            data=[
                ["6ème A", "Mathématiques", "1er Trimestre", "Mamadou Diallo", 14.0, 15.0, 13.5],
                ["6ème A", "Français", "1er Trimestre", "Mamadou Diallo", 12.0, 11.5, 13.0],
                ["CP", "Calcul / Mathématiques", "1er Trimestre", "Fatou Sow", 16.0, 15.0, 17.0]
            ]
        )

if "viescolaire_db" not in st.session_state:
    if "viescolaire_db" in saved_data:
        st.session_state.viescolaire_db = pd.DataFrame(**saved_data["viescolaire_db"])
    else:
        st.session_state.viescolaire_db = pd.DataFrame(
            columns=["Classe", "Periode", "Eleve", "AbsencesJustifiees", "AbsencesNonJustifiees", "Retards", "HeuresPerdues", "Observations", "DecisionConseil"],
            data=[
                ["6ème A", "1er Trimestre", "Mamadou Diallo", 1, 0, 1, 2, "Elève sérieux et appliqué.", "Tableau d'honneur"],
                ["CP", "1er Trimestre", "Fatou Sow", 0, 0, 0, 0, "Très bon trimestre.", "Félicitations"]
            ]
        )

if "base_globale_db" not in st.session_state:
    if "base_globale_db" in saved_data:
        st.session_state.base_globale_db = pd.DataFrame(**saved_data["base_globale_db"])
    else:
        st.session_state.base_globale_db = pd.DataFrame(
            columns=["Date", "Année", "Trimestre", "Mois", "Type Acteur", "Nom Acteur", "Classe", "Type Entrée", "Détail / Contenu", "Appréciation"],
            data=[]
        )

JOURS_LIST = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
HEURES_LIST = ["08h-09h", "09h-10h", "10h-11h", "11h-12h", "15h-16h", "16h-17h", "17h-18h", "18h-19h"]

if "edt_grid_db" not in st.session_state:
    if "edt_grid_db" in saved_data:
        st.session_state.edt_grid_db = {k: pd.DataFrame(**v) for k, v in saved_data["edt_grid_db"].items()}
    else:
        st.session_state.edt_grid_db = {}

if "edt_documents" not in st.session_state:
    if "edt_documents" in saved_data:
        st.session_state.edt_documents = saved_data["edt_documents"]
    else:
        st.session_state.edt_documents = {}

def get_or_create_edt(classe):
    if classe not in st.session_state.edt_grid_db:
        st.session_state.edt_grid_db[classe] = pd.DataFrame(
            "", index=JOURS_LIST, columns=HEURES_LIST
        )
    return st.session_state.edt_grid_db[classe]

if "cahier_textes" not in st.session_state:
    if "cahier_textes" in saved_data:
        st.session_state.cahier_textes = pd.DataFrame(**saved_data["cahier_textes"])
    else:
        st.session_state.cahier_textes = pd.DataFrame(columns=["Professeur", "Date", "Classe", "Matière", "Contenu", "Travail à faire"], data=[])

if "rapports_journaliers_prof" not in st.session_state:
    if "rapports_journaliers_prof" in saved_data:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(**saved_data["rapports_journaliers_prof"])
    else:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(columns=["Professeur", "Date", "Classe", "Matière", "Bilan du Cours", "Difficultés / Remarques"], data=[])

if "absences_db" not in st.session_state:
    if "absences_db" in saved_data:
        st.session_state.absences_db = pd.DataFrame(**saved_data["absences_db"])
    else:
        st.session_state.absences_db = pd.DataFrame(columns=["Date", "Classe", "Élève", "Statut", "Motif"], data=[])

if "conduite_db" not in st.session_state:
    if "conduite_db" in saved_data:
        st.session_state.conduite_db = pd.DataFrame(**saved_data["conduite_db"])
    else:
        st.session_state.conduite_db = pd.DataFrame(columns=["Classe", "Élève", "Date", "Type", "Description"], data=[])

# ==========================================
# 3. FONCTIONS MÉTIER & UTILITAIRES DE NOTES / BULLETINS
# ==========================================
def convertir_sur_20(note, bareme):
    """Convertit automatiquement n'importe quelle note sur un barème donné en une note ramenée sur 20."""
    if bareme <= 0 or pd.isna(note):
        return 0.0
    return round((float(note) * 20.0) / float(bareme), 2)

def obtenir_appreciation(moyenne):
    """Attribue une mention textuelle automatique en fonction de la moyenne obtenue."""
    if moyenne >= 18:
        return "Excellent"
    elif moyenne >= 16:
        return "Très Bien"
    elif moyenne >= 14:
        return "Bien"
    elif moyenne >= 12:
        return "Assez Bien"
    elif moyenne >= 10:
        return "Passable"
    elif moyenne >= 8:
        return "Insuffisant"
    else:
        return "Faible"

def calculer_bulletin_eleve(classe, eleve, periode):
    """Calcule toutes les moyennes, totaux, coefficients et le rang de l'élève pour une période donnée."""
    matieres_coeffs = st.session_state.coefficients_db[st.session_state.coefficients_db["Classe"] == classe]
    if matieres_coeffs.empty:
        # Fallfait de secours si aucun coefficient configuré
        matieres_coeffs = pd.DataFrame({"Matière": ["Mathématiques", "Français"], "Coefficient": [2, 2]})

    notes_classe_periode = st.session_state.notes_db[
        (st.session_state.notes_db["Classe"] == classe) & 
        (st.session_state.notes_db["Periode"] == periode)
    ]

    lignes_bulletin = []
    total_points_global = 0.0
    total_coefficients_global = 0.0

    for _, row_mat in matieres_coeffs.iterrows():
        mat = row_mat["Matière"]
        coef = float(row_mat["Coefficient"])
        
        # Rechercher les notes de l'élève pour cette matière
        note_row = notes_classe_periode[notes_classe_periode["Eleve"] == eleve]
        note_mat = note_row[note_row["Matière"] == mat]

        d1, d2, comp = 0.0, 0.0, 0.0
        if not note_mat.empty:
            d1 = float(note_mat.iloc[0]["Devoir1"]) if not pd.isna(note_mat.iloc[0]["Devoir1"]) else 0.0
            d2 = float(note_mat.iloc[0]["Devoir2"]) if not pd.isna(note_mat.iloc[0]["Devoir2"]) else 0.0
            comp = float(note_mat.iloc[0]["Composition"]) if not pd.isna(note_mat.iloc[0]["Composition"]) else 0.0

        # Calcul moyenne matière : (Moyenne Devoirs + Composition) / 2 ramené sur 20
        moy_devoirs = (d1 + d2) / 2.0
        moy_matiere = (moy_devoirs + comp) / 2.0
        
        total_points_global += moy_matiere * coef
        total_coefficients_global += coef

        lignes_bulletin.append({
            "Matiere": mat,
            "Coefficient": coef,
            "Devoir1": d1,
            "Devoir2": d2,
            "Composition": comp,
            "MoyenneMatiere": round(moy_matiere, 2),
            "TotalPondere": round(moy_matiere * coef, 2),
            "Appreciation": obtenir_appreciation(moy_matiere)
        })

    moyenne_generale = round(total_points_global / total_coefficients_global, 2) if total_coefficients_global > 0 else 0.0

    # Calcul du rang de l'élève dans la classe
    tous_eleves = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe]["Nom Complet"].tolist()
    moyennes_classe = {}
    for el in tous_eleves:
        pts = 0.0
        coefs = 0.0
        notes_el_p = notes_classe_periode[notes_classe_periode["Eleve"] == el]
        for _, row_mat in matieres_coeffs.iterrows():
            mat = row_mat["Matière"]
            coef = float(row_mat["Coefficient"])
            n_m = notes_el_p[notes_el_p["Matière"] == mat]
            if not n_m.empty:
                d1 = float(n_m.iloc[0]["Devoir1"]) if not pd.isna(n_m.iloc[0]["Devoir1"]) else 0.0
                d2 = float(n_m.iloc[0]["Devoir2"]) if not pd.isna(n_m.iloc[0]["Devoir2"]) else 0.0
                comp = float(n_m.iloc[0]["Composition"]) if not pd.isna(n_m.iloc[0]["Composition"]) else 0.0
                m_mat = ((d1 + d2) / 2.0 + comp) / 2.0
                pts += m_mat * coef
                coefs += coef
        moyennes_classe[el] = round(pts / coefs, 2) if coefs > 0 else 0.0

    classement_trie = sorted(moyennes_classe.items(), key=lambda x: x[1], reverse=True)
    rang = "-"
    for idx, (el_nom, _) in enumerate(classement_trie, 1):
        if el_nom == eleve:
            rang = f"{idx} / {len(tous_eleves)}"
            break

    # Récupérer les infos de vie scolaire
    vs_row = st.session_state.viescolaire_db[
        (st.session_state.viescolaire_db["Classe"] == classe) & 
        (st.session_state.viescolaire_db["Periode"] == periode) & 
        (st.session_state.viescolaire_db["Eleve"] == eleve)
    ]
    abs_just, abs_non_just, retards, heures_p, obs, decision = 0, 0, 0, 0, "RAS", "Encouragements"
    if not vs_row.empty:
        abs_just = int(vs_row.iloc[0]["AbsencesJustifiees"])
        abs_non_just = int(vs_row.iloc[0]["AbsencesNonJustifiees"])
        retards = int(vs_row.iloc[0]["Retards"])
        heures_p = int(vs_row.iloc[0]["HeuresPerdues"])
        obs = str(vs_row.iloc[0]["Observations"])
        decision = str(vs_row.iloc[0]["DecisionConseil"])

    return {
        "eleve": eleve,
        "classe": classe,
        "periode": periode,
        "lignes": lignes_bulletin,
        "total_points": round(total_points_global, 2),
        "total_coefficients": total_coefficients_global,
        "moyenne_generale": moyenne_generale,
        "rang": rang,
        "effectif": len(tous_eleves),
        "abs_just": abs_just,
        "abs_non_just": abs_non_just,
        "retards": retards,
        "heures_perdues": heures_p,
        "observations": obs,
        "decision": decision
    }

def generer_pdf_bulletin(bul_data):
    """Génère un bulletin officiel aux normes sénégalaises au format PDF."""
    pdf = FPDF()
    pdf.add_page()
    
    # Utilisation de la police standard FPDF (Arial compatible Unicode de base)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "RÉPUBLIQUE DU SÉNÉGAL", 0, 1, "C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "Ministère de l'Éducation Nationale", 0, 1, "C")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "ÉCOLE PRÉSIDENT NELSON MANDELA", 0, 1, "C")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 4, "éduquer, instruire et promouvoir les vertus africaines.", 0, 1, "C")
    pdf.line(10, 26, 200, 26)
    pdf.ln(5)

    # Titre bulletin
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"BULLETIN DE NOTES - {bul_data['periode'].upper()}", 0, 1, "C")
    pdf.ln(3)

    # Informations de l'élève
    pdf.set_font("Arial", "B", 10)
    pdf.cell(100, 6, f"Nom et Prénom : {bul_data['eleve']}", 0, 0, "L")
    pdf.cell(90, 6, f"Classe : {bul_data['classe']}", 0, 1, "R")
    pdf.cell(100, 6, f"Effectif : {bul_data['effectif']} élèves", 0, 0, "L")
    pdf.cell(90, 6, f"Rang : {bul_data['rang']}", 0, 1, "R")
    pdf.ln(4)

    # Tableau des notes
    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    
    col_widths = [65, 18, 18, 18, 22, 22, 27]
    headers = ["Matière", "Coef", "Dev 1", "Dev 2", "Comp", "Moy/20", "Appréciation"]
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)
    fill = False
    pdf.set_fill_color(240, 244, 248)

    for lig in bul_data["lignes"]:
        pdf.cell(col_widths[0], 6, str(lig["Matiere"])[:25], 1, 0, "L", fill)
        pdf.cell(col_widths[1], 6, str(lig["Coefficient"]), 1, 0, "C", fill)
        pdf.cell(col_widths[2], 6, str(lig["Devoir1"]), 1, 0, "C", fill)
        pdf.cell(col_widths[3], 6, str(lig["Devoir2"]), 1, 0, "C", fill)
        pdf.cell(col_widths[4], 6, str(lig["Composition"]), 1, 0, "C", fill)
        pdf.cell(col_widths[5], 6, str(lig["MoyenneMatiere"]), 1, 0, "C", fill)
        pdf.cell(col_widths[6], 6, str(lig["Appreciation"])[:15], 1, 0, "C", fill)
        pdf.ln()
        fill = not fill

    pdf.ln(4)
    # Bilan académique
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, f"Moyenne Générale : {bul_data['moyenne_generale']} / 20", 1, 1, "L", True)
    pdf.ln(3)

    # Vie scolaire
    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "BILAN DE LA VIE SCOLAIRE ET DISCIPLINE", 0, 1, "L")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, f"Absences justifiées : {bul_data['abs_just']} | Absences non justifiées : {bul_data['abs_non_just']} | Retards : {bul_data['retards']} | Heures perdues : {bul_data['heures_perdues']}h", 1, 1, "L")
    pdf.cell(0, 5, f"Observations / Appréciation générale : {bul_data['observations']}", 1, 1, "L")
    pdf.cell(0, 5, f"Décision du Conseil de Classe : {bul_data['decision']}", 1, 1, "L")
    pdf.ln(10)

    # Signatures
    pdf.set_font("Arial", "B", 9)
    pdf.cell(95, 5, "Le Professor / Titulaire", 0, 0, "C")
    pdf.cell(95, 5, "Le Chef d'Établissement / Directeur", 0, 1, "C")

    return bytes(pdf.output())

# ==========================================
# 4. EN-TÊTE ET NAVIGATION GLOBALE
# ==========================================
st.markdown('<div class="header-ecole">🦁 École Président Nelson Mandela</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">éduquer, instruire et promouvoir les vertus africaines.</div>', unsafe_allow_html=True)

if st.session_state.espace_actif != "🏠 Accueil":
    col_ret1, col_ret2 = st.columns([1, 5])
    with col_ret1:
        if st.button("⬅️ Retour Accueil"):
            st.session_state.espace_actif = "🏠 Accueil"
            st.rerun()
    st.markdown("---")

# ==========================================
# 5. ACCUEIL ET REDIRECTION SÉLECTIVE
# ==========================================
if st.session_state.espace_actif == "🏠 Accueil":
    st.markdown(
        """
        <div style="text-align: center; padding: 10px 0 30px 0;">
            <h3 style="color: #1E3A8A; font-weight: 800;">Portail Numérique Intelligent & Suivi Pédagogique Centralisé</h3>
            <p style="font-size: 1.1rem; color: #475569; max-width: 800px; margin: 0 auto;">
                Sélectionnez votre espace. Le système intègre la gestion complète des notes, des bulletins officiels sénégalais et de la vie scolaire du CI à la 3e.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    
    with c1:
        st.markdown(
            """
            <div class="animated-card">
                <h1 style="font-size: 3rem; margin: 0;">👨‍🏫</h1>
                <h3 style="color: #1E3A8A; margin: 10px 0;">Espace Professeurs</h3>
                <p style="font-size: 0.85rem; color: #64748B;">Saisie des notes & cahier de texte.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Accéder Professeur", key="btn_p"):
            st.session_state.espace_actif = "👨‍🏫 Espace Professeurs / Maîtres"
            st.rerun()

    with c2:
        st.markdown(
            """
            <div class="animated-card">
                <h1 style="font-size: 3rem; margin: 0;">👨‍👩‍👧</h1>
                <h3 style="color: #1E3A8A; margin: 10px 0;">Espace Parents</h3>
                <p style="font-size: 0.85rem; color: #64748B;">Consultation des notes en ligne.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Accéder Parent", key="btn_pa"):
            st.session_state.espace_actif = "👨‍👩‍👧 Espace Parents / Élèves"
            st.rerun()

    with c3:
        st.markdown(
            """
            <div class="animated-card">
                <h1 style="font-size: 3rem; margin: 0;">🔒</h1>
                <h3 style="color: #1E3A8A; margin: 10px 0;">Administration</h3>
                <p style="font-size: 0.85rem; color: #64748B;">Bulletins, coefficients & périodes.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Accéder Admin", key="btn_ad"):
            st.session_state.espace_actif = "🔒 Espace Administration (Sécurisé)"
            st.rerun()

    with c4:
        st.markdown(
            """
            <div class="animated-card">
                <h1 style="font-size: 3rem; margin: 0;">🏫</h1>
                <h3 style="color: #1E3A8A; margin: 10px 0;">Rapports Globaux</h3>
                <p style="font-size: 0.85rem; color: #64748B;">Statistiques et PDF généraux.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Accéder Rapports", key="btn_rp"):
            st.session_state.espace_actif = "🏫 Administration XXL & Rapports"
            st.rerun()

# ==========================================
# 6. MODULES MÉTIERS DÉDIÉS ET FILTRÉS
# ==========================================

elif st.session_state.espace_actif == "👨‍🏫 Espace Professeurs / Maîtres":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Espace Enseignants & Saisie des Notes</div>', unsafe_allow_html=True)

    if "prof_logged" not in st.session_state:
        st.session_state.prof_logged = False
    if "prof_nom_connecte" not in st.session_state:
        st.session_state.prof_nom_connecte = ""
    if "prof_classe_autorisee" not in st.session_state:
        st.session_state.prof_classe_autorisee = ""

    if not st.session_state.prof_logged:
        st.info("Veuillez vous identifier avec vos accès professeurs.")
        with st.form("form_login_prof"):
            p_nom = st.text_input("Nom")
            p_prenom = st.text_input("Prénom")
            p_pass = st.text_input("Mot de passe", type="password")
            
            btn_p_login = st.form_submit_button("Se connecter")

            if btn_p_login:
                match_prof = False
                classe_trouvee = ""
                for _, row in st.session_state.prof_credentials.iterrows():
                    if (str(row["Nom"]).strip().lower() == p_nom.strip().lower() and 
                        str(row["Prénom"]).strip().lower() == p_prenom.strip().lower() and 
                        str(row["Mot de passe"]).strip() == p_pass.strip()):
                        match_prof = True
                        classe_trouvee = str(row.get("Classe Attribuée", ""))
                        break
                if match_prof:
                    st.session_state.prof_logged = True
                    st.session_state.prof_nom_connecte = f"{p_prenom.strip()} {p_nom.strip()}"
                    st.session_state.prof_classe_autorisee = classe_trouvee
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects.")
    else:
        prof_connecte = st.session_state.prof_nom_connecte
        classe_autorisee = st.session_state.prof_classe_autorisee
        st.success(f"Connecté en tant que : **{prof_connecte}** | Classe assignée : **{classe_autorisee}**")
        if st.button("Se déconnecter"):
            st.session_state.prof_logged = False
            st.session_state.prof_nom_connecte = ""
            st.session_state.prof_classe_autorisee = ""
            st.rerun()

        st.markdown("---")
        menu_prof = st.radio("Menu Professeur :", [
            "📝 Saisie des Notes & Évaluations",
            "📋 Fiche d'Appel", 
            "⚠️ Conduite & Vie Scolaire", 
            "📑 Cahier de texte"
        ], horizontal=True)

        if menu_prof == "📝 Saisie des Notes & Évaluations":
            st.markdown("### Module de Saisie des Notes (CI au CM2 & 6e à 3e)")
            
            # Vérifier si la période est ouverte
            periodes_ouvertes = st.session_state.periodes_db[st.session_state.periodes_db["Statut"] == "Ouvert"]["Période"].tolist()
            if not periodes_ouvertes:
                st.warning("⚠️ Aucune période de notation n'est actuellement ouverte par l'administration. La saisie est bloquée.")
            else:
                periode_sel = st.selectbox("Choisir la période active", periodes_ouvertes)
                classe_sel = classe_autorisee
                st.info(f"📌 Classe assignée : **{classe_sel}**")

                # Choisir la matière attitrée
                matieres_possibles = st.session_state.coefficients_db[st.session_state.coefficients_db["Classe"] == classe_sel]["Matière"].tolist()
                if not matieres_possibles:
                    matieres_possibles = ["Mathématiques", "Français"]
                
                matiere_sel = st.selectbox("Choisir la matière", matieres_possibles)
                bareme_sel = st.number_input("Barème de notation", min_value=5, max_value=100, value=20)

                eleves_classe = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_sel]["Nom Complet"].tolist()

                if eleves_classe:
                    st.markdown(f"#### Saisie des notes pour {matiere_sel} ({periode_sel})")
                    
                    # Récupérer notes existantes ou initialiser
                    notes_actuelles = st.session_state.notes_db[
                        (st.session_state.notes_db["Classe"] == classe_sel) & 
                        (st.session_state.notes_db["Matière"] == matiere_sel) & 
                        (st.session_state.notes_db["Periode"] == periode_sel)
                    ]

                    with st.form("form_saisie_notes"):
                        saisie_data = []
                        for el in eleves_classe:
                            ex_row = notes_actuelles[notes_actuelles["Eleve"] == el]
                            d1_val = float(ex_row.iloc[0]["Devoir1"]) if not ex_row.empty and not pd.isna(ex_row.iloc[0]["Devoir1"]) else 0.0
                            d2_val = float(ex_row.iloc[0]["Devoir2"]) if not ex_row.empty and not pd.isna(ex_row.iloc[0]["Devoir2"]) else 0.0
                            comp_val = float(ex_row.iloc[0]["Composition"]) if not ex_row.empty and not pd.isna(ex_row.iloc[0]["Composition"]) else 0.0

                            col_e1, col_e2, col_e3, col_e4 = st.columns([3, 2, 2, 2])
                            with col_e1:
                                st.write(el)
                            with col_e2:
                                nd1 = st.number_input(f"Devoir 1 (sur {bareme_sel})", 0.0, float(bareme_sel), d1_val, key=f"d1_{el}")
                            with col_e3:
                                nd2 = st.number_input(f"Devoir 2 (sur {bareme_sel})", 0.0, float(bareme_sel), d2_val, key=f"d2_{el}")
                            with col_e4:
                                ncomp = st.number_input(f"Composition (sur {bareme_sel})", 0.0, float(bareme_sel), comp_val, key=f"comp_{el}")

                            # Conversion automatique sur 20
                            d1_20 = convertir_sur_20(nd1, bareme_sel)
                            d2_20 = convertir_sur_20(nd2, bareme_sel)
                            comp_20 = convertir_sur_20(ncomp, bareme_sel)

                            saisie_data.append({
                                "Classe": classe_sel,
                                "Matière": matiere_sel,
                                "Periode": periode_sel,
                                "Eleve": el,
                                "Devoir1": d1_20,
                                "Devoir2": d2_20,
                                "Composition": comp_20
                            })

                        if st.form_submit_button("Enregistrer les notes"):
                            # Supprimer anciennes notes pour cette combinaison et insérer les nouvelles
                            st.session_state.notes_db = st.session_state.notes_db[
                                ~((st.session_state.notes_db["Classe"] == classe_sel) & 
                                  (st.session_state.notes_db["Matière"] == matiere_sel) & 
                                  (st.session_state.notes_db["Periode"] == periode_sel))
                            ]
                            new_notes_df = pd.DataFrame(saisie_data)
                            st.session_state.notes_db = pd.concat([st.session_state.notes_db, new_notes_df], ignore_index=True)
                            sauvegarder_donnees_externes()
                            st.success("Notes enregistrées et normalisées sur /20 avec succès !")
                else:
                    st.warning("Aucun élève dans cette classe.")

        elif menu_prof == "📋 Fiche d'Appel":
            st.markdown("### Feuille d'Appel Journalière")
            st.info(f"📌 Classe assignée : **{classe_autorisee}**")
            if not st.session_state.eleves_db.empty:
                date_jour = st.date_input("Date", value=datetime.today())
                eleves_cibles = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_autorisee]["Nom Complet"].tolist()

                if eleves_cibles:
                    with st.form("form_appel"):
                        res_appel = {}
                        for el in eleves_cibles:
                            c1, c2 = st.columns([3, 2])
                            with c1: st.write(el)
                            with c2: res_appel[el] = st.radio("Statut", ["Présent", "Absent", "Retard"], key=f"st_{el}", horizontal=True, label_visibility="collapsed")
                        if st.form_submit_button("Valider l'appel"):
                            nouveaux_abs = []
                            for el in eleves_cibles:
                                if res_appel[el] != "Présent":
                                    nouveaux_abs.append({"Date": str(date_jour), "Classe": classe_autorisee, "Élève": el, "Statut": res_appel[el], "Motif": "Non renseigné"})
                            if nouveaux_abs:
                                st.session_state.absences_db = pd.concat([st.session_state.absences_db, pd.DataFrame(nouveaux_abs)], ignore_index=True)
                                sauvegarder_donnees_externes()
                            st.success("Appel enregistré !")

        elif menu_prof == "⚠️ Conduite & Vie Scolaire":
            st.markdown("### Module Vie Scolaire & Conseil de Classe (Saisie Professeur)")
            cls_vs = classe_autorisee
            eleves_vs = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_vs]["Nom Complet"].tolist()
            periode_vs = st.selectbox("Période", st.session_state.periodes_db["Période"].tolist())
            el_vs = st.selectbox("Élève", eleves_vs if eleves_vs else ["--"])

            with st.form("form_viescolaire_prof"):
                c_vs1, c_vs2, c_vs3, c_vs4 = st.columns(4)
                with c_vs1: abs_j = st.number_input("Absences justifiées", 0, 50, 0)
                with c_vs2: abs_nj = st.number_input("Absences non justifiées", 0, 50, 0)
                with c_vs3: ret = st.number_input("Retards", 0, 50, 0)
                with c_vs4: hp = st.number_input("Heures perdues", 0, 100, 0)

                obs = st.text_area("Observations personnalisées")
                decision = st.selectbox("Décision du conseil de classe", [
                    "Félicitations", "Tableau d'honneur", "Encouragements", "Avertissement travail", "Avertissement conduite", "Blâme"
                ])

                if st.form_submit_button("Enregistrer le suivi de vie scolaire"):
                    if el_vs:
                        # Mettre à jour ou ajouter
                        st.session_state.viescolaire_db = st.session_state.viescolaire_db[
                            ~((st.session_state.viescolaire_db["Classe"] == cls_vs) & 
                              (st.session_state.viescolaire_db["Periode"] == periode_vs) & 
                              (st.session_state.viescolaire_db["Eleve"] == el_vs))
                        ]
                        new_vs = pd.DataFrame([{
                            "Classe": cls_vs, "Periode": periode_vs, "Eleve": el_vs,
                            "AbsencesJustifiees": abs_j, "AbsencesNonJustifiees": abs_nj,
                            "Retards": ret, "HeuresPerdues": hp, "Observations": obs, "DecisionConseil": decision
                        }])
                        st.session_state.viescolaire_db = pd.concat([st.session_state.viescolaire_db, new_vs], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Suivi de vie scolaire enregistré avec succès !")

        elif menu_prof == "📑 Cahier de texte":
            st.markdown("### Cahier de texte & Rapports")
            with st.form("form_cahier"):
                mat_ct = st.text_input("Matière")
                contenu = st.text_area("Contenu de la séance")
                travail = st.text_area("Travail à faire")
                if st.form_submit_button("Publier"):
                    if mat_ct and contenu:
                        new_ct = pd.DataFrame([{"Professeur": prof_connecte, "Date": str(datetime.today().date()), "Classe": classe_autorisee, "Matière": mat_ct, "Contenu": contenu, "Travail à faire": travail}])
                        st.session_state.cahier_textes = pd.concat([st.session_state.cahier_textes, new_ct], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Leçon publiée.")

elif st.session_state.espace_actif == "👨‍👩‍👧 Espace Parents / Élèves":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Portail Parent & Consultation des Notes</div>', unsafe_allow_html=True)

    if "parent_logged_eleve" not in st.session_state:
        st.session_state["parent_logged_eleve"] = ""

    if not st.session_state["parent_logged_eleve"]:
        st.info("Authentification par numéro de téléphone sénégalais du parent.")
        with st.form("form_login_parent"):
            tel_p = st.text_input("Téléphone (ex: +221771234567)")
            prenom_e = st.text_input("Prénom de l'élève")
            nom_e = st.text_input("Nom de l'élève")
            an_e = st.number_input("Année de naissance", 2005, 2024, 2012)
            if st.form_submit_button("Se connecter"):
                clean_tel = tel_p.replace(" ", "").replace("+", "")
                match = False
                for _, row in st.session_state.parents_white_list.iterrows():
                    db_tel = str(row["Téléphone"]).replace(" ", "").replace("+", "")
                    if (clean_tel in db_tel and 
                        str(row["Prénom Élève"]).strip().lower() == prenom_e.strip().lower() and 
                        str(row["Nom Élève"]).strip().lower() == nom_e.strip().lower() and 
                        int(row["Année Naissance"]) == int(an_e)):
                        match = True
                        st.session_state["parent_logged_eleve"] = f"{row['Prénom Élève']} {row['Nom Élève']}"
                        st.session_state["parent_logged_classe"] = row["Classe"]
                        break
                if match:
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Informations incorrectes.")
    else:
        eleve = st.session_state["parent_logged_eleve"]
        classe = st.session_state["parent_logged_classe"]
        
        st.success(f"Connecté pour l'élève : **{eleve}** (Classe : {classe})")
        if st.button("Se déconnecter"):
            st.session_state["parent_logged_eleve"] = ""
            st.rerun()

        st.markdown("---")
        st.subheader("📊 Consultation des Notes et Bulletins")
        periode_consult = st.selectbox("Choisir la période", st.session_state.periodes_db["Période"].tolist())

        # Calculer le bulletin de l'élève pour affichage direct des notes
        bul_el = calculer_bulletin_eleve(classe, eleve, periode_consult)
        
        col_res1, col_res2, col_res3 = st.columns(3)
        with col_res1: st.metric("Moyenne Générale", f"{bul_el['moyenne_generale']} / 20")
        with col_res2: st.metric("Rang", bul_el['rang'])
        with col_res3: st.metric("Décision", bul_el['decision'])

        st.markdown("#### Détail des Notes par Matière")
        df_notes_affiche = pd.DataFrame(bul_el["lignes"])
        if not df_notes_affiche.empty:
            st.dataframe(df_notes_affiche[["Matiere", "Coefficient", "Devoir1", "Devoir2", "Composition", "MoyenneMatiere", "Appreciation"]], use_container_width=True)
        else:
            st.info("Aucune note enregistrée pour cette période.")

        # Option téléchargement bulletin individuel en PDF pour les parents
        pdf_indiv = generer_pdf_bulletin(bul_el)
        st.download_button(
            label="📥 Télécharger mon Bulletin Officiel (PDF)",
            data=pdf_indiv,
            file_name=f"bulletin_{eleve.replace(' ', '_')}_{periode_consult.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

elif st.session_state.espace_actif == "🔒 Espace Administration (Sécurisé)":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration Générale & Gestion des Bulletins</div>', unsafe_allow_html=True)

    if not st.session_state.authenticated_admin:
        with st.form("form_adm_secu"):
            em = st.text_input("Email Administrateur")
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion Admin"):
                if em.strip() == "cpnm@gmail.com" and pw.strip() == "cpnm2026":
                    st.session_state.authenticated_admin = True
                    st.success("Accès accordé !")
                    st.rerun()
                else:
                    st.error("Identifiants erronés.")
    else:
        st.success("Mode Administrateur Activé.")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "📑 Bulletins & Téléchargement PDF (Classe & Élèves)",
            "📊 Statistiques de Classe & Classement Général",
            "⚙️ Configuration des Coefficients & Périodes",
            "👨‍🎓 Élèves", 
            "👨‍🏫 Professeurs", 
            "🏫 Classes et Cycles"
        ])

        if adm_tab == "📑 Bulletins & Téléchargement PDF (Classe & Élèves)":
            st.subheader("📑 Génération et Téléchargement des Bulletins en PDF")
            
            cls_adm = st.selectbox("Choisir la classe", st.session_state.classes_db["Classe"].tolist(), key="adm_cls_bul")
            per_adm = st.selectbox("Choisir la période", st.session_state.periodes_db["Période"].tolist(), key="adm_per_bul")

            eleves_ ds_cls = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_adm]["Nom Complet"].tolist()

            if eleves_ds_cls:
                st.markdown("#### 1. Télécharger le bulletin d'un élève spécifique")
                el_specifique = st.selectbox("Choisir l'élève", eleves_ds_cls)
                if st.button("📄 Générer le bulletin PDF de l'élève"):
                    bul_spec = calculer_bulletin_eleve(cls_adm, el_specifique, per_adm)
                    pdf_bytes_el = generer_pdf_bulletin(bul_spec)
                    st.download_button(
                        label=f"📥 Télécharger le bulletin de {el_specifique} (PDF)",
                        data=pdf_bytes_el,
                        file_name=f"bulletin_{el_specifique.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )

                st.markdown("---")
                st.markdown("#### 2. Télécharger les bulletins de toute la classe")
                if st.button("📦 Générer les bulletins de tous les élèves de la classe"):
                    # Création d'un fichier combiné ou ZIP / PDF global
                    pdf_all = FPDF()
                    for el in eleves_ds_cls:
                        bul_e = calculer_bulletin_eleve(cls_adm, el, per_adm)
                        # On réutilise la logique d'ajout de page
                        pdf_all.add_page()
                        pdf_all.set_font("Arial", "B", 12)
                        pdf_all.cell(0, 6, f"BULLETIN DE NOTES - {per_adm.upper()}", 0, 1, "C")
                        pdf_all.set_font("Arial", "B", 10)
                        pdf_all.cell(100, 6, f"Élève : {bul_e['eleve']}", 0, 0, "L")
                        pdf_all.cell(90, 6, f"Classe : {bul_e['classe']}", 0, 1, "R")
                        pdf_all.cell(100, 6, f"Moyenne Générale : {bul_e['moyenne_generale']} / 20", 0, 0, "L")
                        pdf_all.cell(90, 6, f"Rang : {bul_e['rang']}", 0, 1, "R")
                        pdf_all.ln(5)
                        
                        pdf_all.set_font("Arial", "B", 9)
                        pdf_all.cell(80, 6, "Matière", 1, 0, "C", True)
                        pdf_all.cell(20, 6, "Coef", 1, 0, "C", True)
                        pdf_all.cell(30, 6, "Moyenne", 1, 0, "C", True)
                        pdf_all.cell(60, 6, "Appréciation", 1, 1, "C", True)
                        
                        pdf_all.set_font("Arial", "", 9)
                        for lig in bul_e["lignes"]:
                            pdf_all.cell(80, 6, str(lig["Matiere"]), 1, 0, "L")
                            pdf_all.cell(20, 6, str(lig["Coefficient"]), 1, 0, "C")
                            pdf_all.cell(30, 6, str(lig["MoyenneMatiere"]), 1, 0, "C")
                            pdf_all.cell(60, 6, str(lig["Appreciation"]), 1, 1, "C")

                    pdf_bytes_all = bytes(pdf_all.output())
                    st.download_button(
                        label=f"📥 Télécharger tous les bulletins de la classe {cls_adm} (PDF)",
                        data=pdf_bytes_all,
                        file_name=f"bulletins_classe_{cls_adm.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
            else:
                st.warning("Aucun élève dans cette classe.")

        elif adm_tab == "📊 Statistiques de Classe & Classement Général":
            st.subheader("📊 Statistiques de Classe & Ordre de Mérite")
            cls_stat = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist(), key="stat_cls")
            per_stat = st.selectbox("Période", st.session_state.periodes_db["Période"].tolist(), key="stat_per")

            eleves_st = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_stat]["Nom Complet"].tolist()
            if eleves_st:
                recap_classe = []
                for el in eleves_st:
                    b_info = calculer_bulletin_eleve(cls_stat, el, per_stat)
                    recap_classe.append({
                        "Élève": el,
                        "Moyenne Générale": b_info["moyenne_generale"],
                        "Rang": b_info["rang"],
                        "Décision": b_info["decision"]
                    })
                df_recap = pd.DataFrame(recap_classe).sort_values(by="Moyenne Générale", ascending=False).reset_index(drop=True)
                
                # Indicateurs clés
                moy_classes = df_recap["Moyenne Générale"].tolist()
                meilleure = max(moy_classes) if moy_classes else 0.0
                plus_faible = min(moy_classes) if moy_classes else 0.0
                moy_gen_classe = round(sum(moy_classes) / len(moy_classes), 2) if moy_classes else 0.0

                c_k1, c_k2, c_k3 = st.columns(3)
                with c_k1: st.metric("Moyenne Générale de la Classe", f"{moy_gen_classe} / 20")
                with c_k2: st.metric("Meilleure Moyenne", f"{meilleure} / 20")
                with c_k3: st.metric("Plus Faible Moyenne", f"{plus_faible} / 20")

                st.markdown("#### Tableau Récapitulatif par Ordre de Mérite")
                st.dataframe(df_recap, use_container_width=True)

                pdf_stat = export_table_pdf(f"STATISTIQUES ET CLASSEMENT - {cls_stat}", df_recap)
                st.download_button("📄 Télécharger le classement (PDF)", data=pdf_stat, file_name=f"classement_{cls_stat}.pdf", mime="application/pdf")

        elif adm_tab == "⚙️ Configuration des Coefficients & Périodes":
            st.subheader("⚙️ Configuration des Coefficients & Périodes")
            
            st.markdown("#### Gestion des Périodes (Trimestres)")
            edited_periodes = st.data_editor(st.session_state.periodes_db, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Enregistrer les périodes"):
                st.session_state.periodes_db = edited_periodes
                sauvegarder_donnees_externes()
                st.success("Périodes mises à jour !")

            st.markdown("---")
            st.markdown("#### Configuration des Coefficients par Classe")
            edited_coefs = st.data_editor(st.session_state.coefficients_db, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Enregistrer les coefficients"):
                st.session_state.coefficients_db = edited_coefs
                sauvegarder_donnees_externes()
                st.success("coefficients mis à jour !")

        elif adm_tab == "👨‍🎓 Élèves":
            st.subheader("Gestion des Élèves")
            st.data_editor(st.session_state.eleves_db, num_rows="dynamic", use_container_width=True)

        elif adm_tab == "👨‍🏫 Professeurs":
            st.subheader("Gestion des Professeurs")
            st.data_editor(st.session_state.prof_credentials, num_rows="dynamic", use_container_width=True)

        elif adm_tab == "🏫 Classes et Cycles":
            st.subheader("Gestion des Classes et Cycles")
            st.data_editor(st.session_state.classes_db, num_rows="dynamic", use_container_width=True)

elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Rapports Globaux et Consolidation Annuelle</div>', unsafe_allow_html=True)
    if st.button("📄 Générer et Télécharger le Rapport Général Consolidé (PDF)"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 7, "RAPPORT GÉNÉRAL CONSOLIDÉ DE L'ÉTABLISSEMENT", 0, 1, "C")
        pdf.ln(4)
        pdf.set_font("Arial", "", 10)
        pdf.cell(0, 6, f"Total Élèves : {len(st.session_state.eleves_db)}", 0, 1, "L")
        pdf.cell(0, 6, f"Total Classes : {len(st.session_state.classes_db)}", 0, 1, "L")
        pdf.cell(0, 6, f"Total Professeurs : {len(st.session_state.prof_credentials)}", 0, 1, "L")
        pdf_gen = bytes(pdf.output())
        st.download_button("📥 Télécharger le Rapport Général PDF", data=pdf_gen, file_name="rapport_general.pdf", mime="application/pdf")
