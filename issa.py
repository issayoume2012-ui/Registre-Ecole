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
# 0. GESTION DE LA PERSISTANCE EXTERNE (SQLITE STRUCTURÉE ET ROBUSTE)
# ==========================================
DB_FILE = "cpnm_database.db"

def init_sqlite_db():
    """Initialise la base de données SQLite avec de vraies tables relationnelles structurées 
    pour éviter de stocker de gros blocs JSON et garantir une robustesse à 100%."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Table clé-valeur de secours pour les configurations simples
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS app_data (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Tables relationnelles structurées recommandées pour le cloud éphémère
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
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classe TEXT,
            eleve TEXT,
            matiere TEXT,
            type_evaluation TEXT,
            coefficient INTEGER,
            note REAL,
            bareme INTEGER,
            trimestre TEXT,
            appreciation TEXT
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
    
    # Correction robuste de la table eleves pour s'assurer que les colonnes prenom et nom existent toujours
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
        "notes_db": st.session_state.notes_db.to_dict(orient="split"),
        "matieres_def": st.session_state.matieres_def.to_dict(orient="split"),
        "conduite_db": st.session_state.conduite_db.to_dict(orient="split"),
        "edt_grid_db": {k: v.to_dict(orient="split") for k, v in st.session_state.edt_grid_db.items()},
        "edt_documents": {k: v for k, v in st.session_state.edt_documents.items()}
    }
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Vérification et mise à jour dynamique du schéma de la table eleves pour éviter toute erreur "has no column named nom"
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

        # Sauvegarde clé-valeur globale
        for key, value in data_to_save.items():
            cursor.execute("""
                INSERT INTO app_data (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """, (key, json.dumps(value, ensure_ascii=False)))
            
        # Synchronisation automatique dans les tables relationnelles dédiées
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
                               
        if "notes_db" in st.session_state and not st.session_state.notes_db.empty:
            cursor.execute("DELETE FROM notes")
            for _, r in st.session_state.notes_db.iterrows():
                cursor.execute("INSERT INTO notes (classe, eleve, matiere, type_evaluation, coefficient, note, bareme, trimestre, appreciation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (r.get("Classe"), r.get("Élève"), r.get("Matière"), r.get("Type Évaluation"), r.get("Coefficient"), r.get("Note"), r.get("Barème"), r.get("Trimestre"), r.get("Appréciation")))

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
    """Télécharge les polices Unicode depuis GitHub avec mise en cache Streamlit."""
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

    @media screen and (max-width: 768px) {
        .header-ecole { font-size: 1.6rem; }
        .sub-header { font-size: 0.95rem; }
        .animated-card { padding: 15px; margin-bottom: 12px; }
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
                ["6ème A", "Collège", "Ibrahima Diallo"],
                ["5ème A", "Collège", "Cheikh Ndiaye"],
                ["CP", "Élémentaire", "Aissatou Sow"],
                ["Grande Section", "Préscolaire", "Marie Faye"],
                ["CE1", "Élémentaire", "Ousmane Diop"]
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
    st.session_state.eleves_db = st.session_state.eleves_db.sort_values(by="Nom").reset_index(drop=True)

if "base_globale_db" not in st.session_state:
    if "base_globale_db" in saved_data:
        st.session_state.base_globale_db = pd.DataFrame(**saved_data["base_globale_db"])
    else:
        st.session_state.base_globale_db = pd.DataFrame(
            columns=["Date", "Année", "Trimestre", "Mois", "Type Acteur", "Nom Acteur", "Classe", "Type Entrée", "Détail / Contenu", "Appréciation"],
            data=[
                {"Date": "2026-01-15", "Année": "2025-2026", "Trimestre": "1er Semestre", "Mois": "Janvier", "Type Acteur": "Élève", "Nom Acteur": "Mamadou Diallo", "Classe": "6ème A", "Type Entrée": "Note", "Détail / Contenu": "Mathématiques (Devoir 1): 15.5/20", "Appréciation": "Très bon travail"},
                {"Date": "2026-01-20", "Année": "2025-2026", "Trimestre": "1er Semestre", "Mois": "Janvier", "Type Acteur": "Élève", "Nom Acteur": "Aminata Ba", "Classe": "6ème A", "Type Entrée": "Absence", "Détail / Contenu": "Absent - Motif: Maladie", "Appréciation": "Justifié"},
                {"Date": "2026-02-05", "Année": "2025-2026", "Trimestre": "2ème Semestre", "Mois": "Février", "Type Acteur": "Professeur", "Nom Acteur": "Ibrahima Diallo", "Classe": "6ème A", "Type Entrée": "Rapport Cours", "Détail / Contenu": "Algèbre - Chapitre 3 terminé", "Appréciation": "Excellente progression"}
            ]
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
        st.session_state.cahier_textes = pd.DataFrame(
            columns=["Professeur", "Date", "Classe", "Matière", "Contenu", "Travail à faire"],
            data=[
                ["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Introduction aux nombres relatifs.", "Exercices 1 et 2 page 45."]
            ]
        )

if "rapports_journaliers_prof" not in st.session_state:
    if "rapports_journaliers_prof" in saved_data:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(**saved_data["rapports_journaliers_prof"])
    else:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(
            columns=["Professeur", "Date", "Classe", "Matière", "Bilan du Cours", "Difficultés / Remarques"],
            data=[
                ["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Bonne participation globale des élèves.", "Quelques difficultés sur les soustractions de négatifs."]
            ]
        )

if "absences_db" not in st.session_state:
    if "absences_db" in saved_data:
        st.session_state.absences_db = pd.DataFrame(**saved_data["absences_db"])
    else:
        st.session_state.absences_db = pd.DataFrame(
            columns=["Date", "Classe", "Élève", "Statut", "Motif"],
            data=[
                ["2026-06-01", "6ème A", "Aminata Ba", "Absent", "Maladie"]
            ]
        )

if "notes_db" not in st.session_state:
    if "notes_db" in saved_data:
        st.session_state.notes_db = pd.DataFrame(**saved_data["notes_db"])
    else:
        st.session_state.notes_db = pd.DataFrame(
            columns=["Classe", "Élève", "Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Trimestre", "Appréciation"],
            data=[
                ["6ème A", "Mamadou Diallo", "Mathématiques", "Devoir 1", 3, 15.5, 20, "1er Semestre", "Très bon travail."],
                ["6ème A", "Mamadou Diallo", "Mathématiques", "Devoir 2", 3, 14.0, 20, "1er Semestre", "Bon ensemble."],
                ["6ème A", "Mamadou Diallo", "Mathématiques", "Composition", 3, 16.0, 20, "1er Semestre", "Excellent."],
                ["6ème A", "Mamadou Diallo", "Français", "Devoir 1", 3, 13.0, 20, "1er Semestre", "Assez bon."],
                ["6ème A", "Mamadou Diallo", "Français", "Devoir 2", 3, 14.5, 20, "1er Semestre", "Bon travail."],
                ["6ème A", "Mamadou Diallo", "Français", "Composition", 3, 15.0, 20, "1er Semestre", "Très bien."],
                ["CP", "Fatou Sow", "Graphisme / Écriture", "Composition 1er trimestre", 1, 8.5, 10, "1er Trimestre", "Très bien."]
            ]
        )

if "matieres_def" not in st.session_state:
    if "matieres_def" in saved_data:
        st.session_state.matieres_def = pd.DataFrame(**saved_data["matieres_def"])
    else:
        st.session_state.matieres_def = pd.DataFrame([
            {"Matière": "Mathématiques", "Coefficient": 3, "Cycle": "Collège"},
            {"Matière": "Français", "Coefficient": 3, "Cycle": "Collège"},
            {"Matière": "Histoire-Géographie", "Coefficient": 2, "Cycle": "Collège"},
            {"Matière": "SVT", "Coefficient": 2, "Cycle": "Collège"},
            {"Matière": "Anglais", "Coefficient": 2, "Cycle": "Collège"},
            {"Matière": "Lecture / Langage", "Coefficient": 1, "Cycle": "Élémentaire"},
            {"Matière": "Calcul / Mathématiques", "Coefficient": 1, "Cycle": "Élémentaire"},
            {"Matière": "Éveil / Science", "Coefficient": 1, "Cycle": "Élémentaire"},
            {"Matière": "Activités Sensorielles", "Coefficient": 1, "Cycle": "Préscolaire"},
            {"Matière": "Graphisme / Dessin", "Coefficient": 1, "Cycle": "Préscolaire"}
        ])

if "conduite_db" not in st.session_state:
    if "conduite_db" in saved_data:
        st.session_state.conduite_db = pd.DataFrame(**saved_data["conduite_db"])
    else:
        st.session_state.conduite_db = pd.DataFrame(
            columns=["Classe", "Élève", "Date", "Type", "Description"],
            data=[
                ["6ème A", "Mamadou Diallo", "2026-06-02", "Encouragement", "Participation active en classe."]
            ]
        )

# ==========================================
# 3. FONCTIONS UTILITAIRES & GÉNÉRATION PDF/EXCEL
# ==========================================
class PDFReport(FPDF):
    def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "ÉCOLE PRÉSIDENT NELSON MANDELA - SÉNÉGAL", 0, 1, "C")
        self.set_font("Arial", "I", 9)
        self.cell(0, 5, "éduquer, instruire et promouvoir les vertus africaines.", 0, 1, "C")
        self.line(10, 25, 200, 25)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} - Document Officiel ÉPNM Généré le {datetime.now().strftime('%d/%m/%Y')}", 0, 0, "C")

def export_table_pdf(title, df, columns_to_show=None):
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 13)
    pdf.cell(0, 8, title, 0, 1, "L")
    pdf.ln(4)

    df_sub = df[columns_to_show] if columns_to_show else df

    pdf.set_font("Arial", "B", 10)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)

    col_widths = [190 / len(df_sub.columns)] * len(df_sub.columns)
    
    for i, col in enumerate(df_sub.columns):
        pdf.cell(col_widths[i], 8, str(col)[:20], 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)
    fill = False
    pdf.set_fill_color(240, 244, 248)

    for _, row in df_sub.iterrows():
        for i, col in enumerate(df_sub.columns):
            val = str(row[col]) if pd.notnull(row[col]) else ""
            pdf.cell(col_widths[i], 7, val[:25], 1, 0, "C", fill)
        pdf.ln()
        fill = not fill

    return bytes(pdf.output())

def export_table_excel(df, columns_to_show=None):
    df_sub = df[columns_to_show] if columns_to_show else df
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_sub.to_excel(writer, index=False, sheet_name='Élèves')
    return output.getvalue()

def generer_bulletin_pdf(eleve_nom, classe_nom, trimestre_sel):
    pdf = PDFReport()
    pdf.add_page()
    
    row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe_nom]
    cycle = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, f"BULLETIN DE NOTES ET BILAN GLOBAL - {trimestre_sel.upper()}", 0, 1, "C")
    pdf.ln(2)
    
    pdf.set_font("Arial", "", 10)
    pdf.cell(100, 6, f"Élève : {eleve_nom}", 0, 0, "L")
    pdf.cell(90, 6, f"Classe : {classe_nom} ({cycle})", 0, 1, "R")
    pdf.cell(100, 6, f"Établissement : École Président Nelson Mandela", 0, 0, "L")
    pdf.cell(90, 6, f"Devise : éduquer, instruire et promouvoir les vertus africaines.", 0, 1, "R")
    pdf.ln(5)

    df_n = st.session_state.notes_db[
        (st.session_state.notes_db["Élève"] == eleve_nom) & 
        (st.session_state.notes_db["Trimestre"] == trimestre_sel)
    ]

    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    
    if cycle == "Collège":
        w_mat, w_d1, w_d2, w_comp, w_coef, w_moy, w_app = 35, 18, 18, 30, 14, 20, 55
        pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
        pdf.cell(w_d1, 7, "Devoir 1", 1, 0, "C", True)
        pdf.cell(w_d2, 7, "Devoir 2", 1, 0, "C", True)
        pdf.cell(w_comp, 7, "Composition", 1, 0, "C", True)
        pdf.cell(w_coef, 7, "Coef", 1, 0, "C", True)
        pdf.cell(w_moy, 7, "Moy. /20", 1, 0, "C", True)
        pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)
    else:
        w_mat, w_comp, w_moy, w_app = 65, 30, 30, 65
        pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
        pdf.cell(w_comp, 7, "Évaluation", 1, 0, "C", True)
        pdf.cell(w_moy, 7, "Note /Barème", 1, 0, "C", True)
        pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)

    total_points_sur_20 = 0.0
    total_points_sur_10 = 0.0
    total_coefs = 0

    if not df_n.empty:
        matieres_list = df_n["Matière"].unique()
        for mat in matieres_list:
            df_mat = df_n[df_n["Matière"] == mat]
            appr_str = df_mat["Appréciation"].iloc[-1] if not df_mat.empty else "Bon ensemble"
            
            if cycle == "Collège":
                coef = int(df_mat["Coefficient"].iloc[0]) if "Coefficient" in df_mat.columns and pd.notnull(df_mat["Coefficient"].iloc[0]) else 1
                note_d1 = df_mat[df_mat["Type Évaluation"] == "Devoir 1"]["Note"].values
                note_d2 = df_mat[df_mat["Type Évaluation"] == "Devoir 2"]["Note"].values
                note_comp = df_mat[df_mat["Type Évaluation"].isin(["Composition", "Composition 1er semestre", "Composition 2ème semestre"])]["Note"].values

                d1_val = float(note_d1[0]) if len(note_d1) > 0 and pd.notnull(note_d1[0]) else 0.0
                d2_val = float(note_d2[0]) if len(note_d2) > 0 and pd.notnull(note_d2[0]) else 0.0
                comp_val = float(note_comp[0]) if len(note_comp) > 0 and pd.notnull(note_comp[0]) else 0.0

                d1_str = f"{d1_val:.2f}" if len(note_d1) > 0 else "-"
                d2_str = f"{d2_val:.2f}" if len(note_d2) > 0 else "-"
                comp_str = f"{comp_val:.2f}" if len(note_comp) > 0 else "-"

                # Calcul spécifique exigé pour collège : (((D1 + D2) / 2) + Composition) / 2
                moy_mat = (((d1_val + d2_val) / 2.0) + comp_val) / 2.0
                
                tot = moy_mat * coef
                total_points_sur_20 += tot
                total_coefs += coef

                pdf.cell(w_mat, 6, str(mat)[:20], 1, 0, "L")
                pdf.cell(w_d1, 6, d1_str, 1, 0, "C")
                pdf.cell(w_d2, 6, d2_str, 1, 0, "C")
                pdf.cell(w_comp, 6, comp_str, 1, 0, "C")
                pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
                pdf.cell(w_moy, 6, f"{moy_mat:.2f}", 1, 0, "C")
                pdf.cell(w_app, 6, str(appr_str)[:25], 1, 1, "L")
            else:
                note_comp = df_mat["Note"].values
                bareme_val = int(df_mat["Barème"].iloc[0]) if "Barème" in df_mat.columns and pd.notnull(df_mat["Barème"].iloc[0]) else 10
                comp_str = f"{note_comp[0]:.2f}" if len(note_comp) > 0 else "-"
                note_val = note_comp[0] if len(note_comp) > 0 else 0.0
                
                note_sur_10 = (note_val / bareme_val) * 10.0 if bareme_val > 0 else note_val
                total_points_sur_10 += note_sur_10
                total_coefs += 1 

                pdf.cell(w_mat, 6, str(mat)[:25], 1, 0, "L")
                pdf.cell(w_comp, 6, comp_str, 1, 0, "C")
                pdf.cell(w_moy, 6, f"{note_val:.2f}/{bareme_val}", 1, 0, "C")
                pdf.cell(w_app, 6, str(appr_str)[:30], 1, 1, "L")

    if cycle == "Collège":
        moyenne = (total_points_sur_20 / total_coefs) if total_coefs > 0 else 0.0
        libelle_moy = f"MOYENNE GÉNÉRALE : {moyenne:.2f} / 20"
    else:
        moyenne = (total_points_sur_10 / total_coefs) if total_coefs > 0 else 0.0
        libelle_moy = f"MOYENNE GÉNÉRALE CONSOLIDÉE : {moyenne:.2f} / 10"

    pdf.ln(3)
    pdf.set_font("Arial", "B", 10)
    if cycle == "Collège":
        pdf.cell(95, 7, f"Total des Points : {total_points_sur_20:.2f}", 1, 0, "L")
        pdf.cell(95, 7, f"Total des Coefficients : {total_coefs}", 1, 1, "L")
    else:
        pdf.cell(95, 7, f"Somme des notes ramenées sur 10 : {total_points_sur_10:.2f}", 1, 0, "L")
        pdf.cell(95, 7, f"Nombre de matières : {total_coefs}", 1, 1, "L")
    
    pdf.set_fill_color(230, 242, 255)
    pdf.cell(190, 8, libelle_moy, 1, 1, "C", True)

    df_bg_abs = st.session_state.base_globale_db[
        (st.session_state.base_globale_db["Nom Acteur"] == eleve_nom) & 
        (st.session_state.base_globale_db["Trimestre"] == trimestre_sel) & 
        (st.session_state.base_globale_db["Type Entrée"] == "Absence")
    ]
    df_bg_cond = st.session_state.conduite_db[st.session_state.conduite_db["Élève"] == eleve_nom]

    nb_abs = len(df_bg_abs)
    
    pdf.ln(4)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, "BILAN ASSIDUITÉ & COMPORTEMENT (BASE GLOBALE)", 0, 1, "L")
    pdf.set_font("Arial", "", 9)
    pdf.cell(95, 6, f"Nombre d'absences relevées : {nb_abs}", 1, 0, "L")
    rem_cond = df_bg_cond["Type"].iloc[-1] if not df_bg_cond.empty else "R.A.S"
    pdf.cell(95, 6, f"Remarque Conduite : {rem_cond}", 1, 1, "L")

    if cycle == "Collège":
        if moyenne >= 16: mention = "Très Bien (Félicitations du Conseil)"
        elif moyenne >= 14: mention = "Bien (Tableau d'Honneur)"
        elif moyenne >= 12: mention = "Assez Bien"
        elif moyenne >= 10: mention = "Passable"
        else: mention = "Insuffisant - Avertissement Travail"
    else:
        if moyenne >= 8: mention = "Très Bon travail"
        elif moyenne >= 6: mention = "Travail Satisfaisant"
        elif moyenne >= 5: mention = "Moyen"
        else: mention = "Efforts requis"

    pdf.ln(3)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, f"Appréciation Globale & Mention : {mention}", 0, 1, "L")

    pdf.ln(8)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(60, 6, "Le Professeur Principal", 0, 0, "C")
    pdf.cell(70, 6, "Les Parents", 0, 0, "C")
    pdf.cell(60, 6, "Le Directeur des Études", 0, 1, "C")

    return bytes(pdf.output())

def generer_rapport_general_pdf():
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, "RAPPORT GÉNÉRAL CONSOLIDÉ DE L'ÉTABLISSEMENT", 0, 1, "C")
    pdf.ln(4)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, f"Total Élèves : {len(st.session_state.eleves_db)}", 0, 1, "L")
    pdf.cell(0, 6, f"Total Classes : {len(st.session_state.classes_db)}", 0, 1, "L")
    pdf.cell(0, 6, f"Total Professeurs : {len(st.session_state.prof_credentials)}", 0, 1, "L")
    pdf.cell(0, 6, f"Entrées Base Globale : {len(st.session_state.base_globale_db)}", 0, 1, "L")
    return bytes(pdf.output())

def assistant_ia_repondre(question):
    q = question.lower()
    if "élève" in q or "effectif" in q or "nombre" in q:
        nb_e = len(st.session_state.eleves_db)
        nb_c = len(st.session_state.classes_db)
        return f"📊 Actuellement, l'établissement compte **{nb_e} élèves** répartis dans **{nb_c} classes**."
    elif "professeur" in q or "prof" in q:
        nb_p = len(st.session_state.prof_credentials)
        return f"👨‍🏫 Nous avons **{nb_p} professeurs** enregistrés dans le système."
    elif "rapport" in q or "base" in q:
        nb_r = len(st.session_state.rapports_journaliers_prof)
        nb_bg = len(st.session_state.base_globale_db)
        return f"📑 **{nb_r} rapport(s)** journalier(s) enregistrés et **{nb_bg} entrées** centralisées dans la Base Globale de suivi."
    elif "bulletin" in q or "note" in q or "barème" in q:
        return "📝 Le système applique un barème adapté : pour le préscolaire et l'élémentaire, la saisie comporte uniquement les compositions du 1er, 2ème et 3ème trimestre sans coefficient, avec barème personnalisable par le professeur ; pour le collège, les semestres comportent Devoir 1, Devoir 2 et Composition avec coefficients."
    else:
        return "🤖 **IA Administration École Président Nelson Mandela :** Je suis là pour vous assister ! Posez-moi des questions sur la base globale, les effectifs, emplois du temps ou les rapports."

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
                Sélectionnez votre espace. Le système intègre une Base Globale centralisant tout l'historique annuel avec tables relationnelles SQLite sécurisées contre l'effacement du Cloud.
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
                <p style="font-size: 0.85rem; color: #64748B;">Notes, fiches d'appel, travail fait et à faire & alimentation de la base globale.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Consultation des bulletins en ligne (téléchargement réservé à l'admin).</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Gestion Base Globale, EDT & PDF.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Tableaux de bord généraux et Téléchargement Rapport PDF.</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        if st.button("Accéder Rapports", key="btn_rp"):
            st.session_state.espace_actif = "🏫 Administration XXL & Rapports"
            st.rerun()

    st.markdown("---")
    st.markdown("### 📊 Indicateurs en Temps Réel")
    s1, s2, s3, s4 = st.columns(4)
    with s1:
        st.markdown(f'<div class="kpi-card-animated"><h4 style="margin:0;color:#64748B;">Élèves Inscrits</h4><h2 style="margin:0;color:#1E3A8A;">{len(st.session_state.eleves_db)}</h2></div>', unsafe_allow_html=True)
    with s2:
        st.markdown(f'<div class="kpi-card-animated"><h4 style="margin:0;color:#64748B;">Classes Actives</h4><h2 style="margin:0;color:#1E3A8A;">{len(st.session_state.classes_db)}</h2></div>', unsafe_allow_html=True)
    with s3:
        st.markdown(f'<div class="kpi-card-animated"><h4 style="margin:0;color:#64748B;">Professeurs</h4><h2 style="margin:0;color:#1E3A8A;">{len(st.session_state.prof_credentials)}</h2></div>', unsafe_allow_html=True)
    with s4:
        st.markdown(f'<div class="kpi-card-animated"><h4 style="margin:0;color:#64748B;">Entrées Base Globale</h4><h2 style="margin:0;color:#1E3A8A;">{len(st.session_state.base_globale_db)}</h2></div>', unsafe_allow_html=True)

# ==========================================
# 6. MODULES MÉTIERS DÉDIÉS ET FILTRÉS
# ==========================================

elif st.session_state.espace_actif == "👨‍🏫 Espace Professeurs / Maîtres":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Espace Enseignants & Maîtres</div>', unsafe_allow_html=True)

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
            
            classes_dispo_admin = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"]
            p_classe_session = st.selectbox("Classe de session (définie par l'administration)", classes_dispo_admin)
            
            btn_p_login = st.form_submit_button("Se connecter")

            if btn_p_login:
                match_prof = False
                for _, row in st.session_state.prof_credentials.iterrows():
                    if (str(row["Nom"]).strip().lower() == p_nom.strip().lower() and 
                        str(row["Prénom"]).strip().lower() == p_prenom.strip().lower() and 
                        str(row["Mot de passe"]).strip() == p_pass.strip()):
                        match_prof = True
                        break
                if match_prof:
                    st.session_state.prof_logged = True
                    st.session_state.prof_nom_connecte = f"{p_prenom.strip()} {p_nom.strip()}"
                    st.session_state.prof_classe_autorisee = p_classe_session
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects. Veuillez vérifier votre nom, prénom et mot de passe.")
    else:
        prof_connecte = st.session_state.prof_nom_connecte
        classe_autorisee = st.session_state.prof_classe_autorisee
        st.success(f"Connecté en tant que : **{prof_connecte}** | Classe assignée de session : **{classe_autorisee}**")
        if st.button("Se déconnecter"):
            st.session_state.prof_logged = False
            st.session_state.prof_nom_connecte = ""
            st.session_state.prof_classe_autorisee = ""
            st.rerun()

        st.markdown("---")
        menu_prof = st.radio("Menu Professeur :", [
            "📋 Fiche d'Appel", 
            "📝 Saisie des Notes par Fiche Matière", 
            "⚠️ Conduite", 
            "📖 Travail fait et à faire", 
            "📑 Cahier de texte"
        ], horizontal=True)

        if menu_prof == "📋 Fiche d'Appel":
            st.markdown("### Feuille d'Appel Journalière")
            st.info(f"📌 Classe assignée de session : **{classe_autorisee}**")
            if not st.session_state.eleves_db.empty:
                date_jour = st.date_input("Date", value=datetime.today())
                cls_appel = classe_autorisee
                st.write(f"**Classe concernée :** {cls_appel}")
                eleves_cibles = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_appel]["Nom Complet"].tolist()

                if eleves_cibles:
                    with st.form("form_appel"):
                        res_appel = {}
                        for el in eleves_cibles:
                            c1, c2 = st.columns([3, 2])
                            with c1: st.write(el)
                            with c2: res_appel[el] = st.radio("Statut", ["Présent", "Absent", "Retard"], key=f"st_{el}", horizontal=True, label_visibility="collapsed")
                        if st.form_submit_button("Valider l'appel"):
                            nouveaux_abs = []
                            nouvelles_entrées_bg = []
                            
                            mois_actuel = date_jour.strftime("%B")
                            row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == cls_appel]
                            cycle_cls = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"
                            tri_actuel = "1er Semestre" if cycle_cls == "Collège" else "1er Trimestre"

                            for el in eleves_cibles:
                                if res_appel[el] != "Présent":
                                    nouveaux_abs.append({"Date": str(date_jour), "Classe": cls_appel, "Élève": el, "Statut": res_appel[el], "Motif": "Non renseigné"})
                                    nouvelles_entrées_bg.append({
                                        "Date": str(date_jour), "Année": "2025-2026", "Trimestre": tri_actuel, "Mois": mois_actuel,
                                        "Type Acteur": "Élève", "Nom Acteur": el, "Classe": cls_appel,
                                        "Type Entrée": "Absence" if res_appel[el] == "Absent" else "Présence/Retard", 
                                        "Détail / Contenu": f"Statut : {res_appel[el]}", "Appréciation": "Non justifiée"
                                    })
                            
                            if nouveaux_abs:
                                st.session_state.absences_db = pd.concat([st.session_state.absences_db, pd.DataFrame(nouveaux_abs)], ignore_index=True)
                                st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, pd.DataFrame(nouvelles_entrées_bg)], ignore_index=True)
                                sauvegarder_donnees_externes()
                            st.success("Appel enregistré et synchronisé dans la Base Globale !")
                else:
                    st.info("Aucun élève dans cette classe.")

        elif menu_prof == "📝 Saisie des Notes par Fiche Matière":
            st.markdown("### Fiche de Matière — Saisie des Notes et Appréciations")
            st.info(f"📌 Classe assignée de session : **{classe_autorisee}**")
            
            cols_requis = ["Classe", "Élève", "Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Trimestre", "Appréciation"]
            for col in cols_requis:
                if col not in st.session_state.notes_db.columns:
                    st.session_state.notes_db[col] = None

            cls_n = classe_autorisee
            
            row_c = st.session_state.classes_db[st.session_state.classes_db["Classe"] == cls_n]
            cycle_sel = row_c["Cycle"].values[0] if not row_c.empty else "Collège"
            
            c_tri, c_type_eval = st.columns(2)
            with c_tri:
                if cycle_sel == "Collège":
                    trimestre_sel = st.selectbox("Semestre", ["1er Semestre", "2ème Semestre"])
                else:
                    trimestre_sel = st.selectbox("Trimestre", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])

            with c_type_eval:
                if cycle_sel == "Collège":
                    type_eval_sel = st.selectbox("Type d'Évaluation", ["Devoir 1", "Devoir 2", "Composition"])
                else:
                    # CORRECTION EXIGÉE : Pour élémentaire et préscolaire, uniquement les compositions de trimestres sans coef
                    type_eval_sel = st.selectbox("Type d'Évaluation", ["Composition 1er trimestre", "Composition 2ème trimestre", "Composition 3ème trimestre"])

            if cycle_sel in ["Préscolaire", "Élémentaire"]:
                bareme_sel = st.number_input("Définir le barème de notation (ex: 10, 20, 5...)", min_value=1, max_value=100, value=10)
                coef_val = 1 
                st.info(f"📌 Cycle Élémentaire / Préscolaire : Uniquement les compositions de trimestres, sans coefficient et avec barème personnalisable sur **{bareme_sel}**.")
            else:
                bareme_sel = 20
                coef_val = st.number_input("Coefficient prédéfini par le professeur", min_value=1, max_value=10, value=3)
                st.info("📌 Cycle Collège : Devoir 1, Devoir 2 et Composition pour chaque semestre avec coefficients prédéfinis. Formule : (((D1 + D2) / 2) + Composition) / 2 * Coef.")

            mode_mat = st.radio("Saisie Matière :", ["Saisir directement la matière", "Choisir parmi les matières prédéfinies"], horizontal=True)
            
            if mode_mat == "Saisir directement la matière":
                matiere_sel = st.text_input("Saisir le nom de la Matière", value="", placeholder="ex: Mathématiques, Arabe, Éveil...")
            else:
                mats_filt = st.session_state.matieres_def[st.session_state.matieres_def["Cycle"] == cycle_sel]["Matière"].tolist()
                if not mats_filt:
                    mats_filt = ["Mathématiques", "Français", "Histoire-Géo"]
                matiere_sel = st.selectbox("Matière Prédéfinie", mats_filt)

            eleves_cls = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_n]["Nom Complet"].tolist()

            if eleves_cls and matiere_sel.strip() != "":
                @st.fragment
                def editeur_notes_fragment():
                    data_fiche = []
                    for el in eleves_cls:
                        existing = st.session_state.notes_db[
                            (st.session_state.notes_db["Classe"] == cls_n) & 
                            (st.session_state.notes_db["Élève"] == el) & 
                            (st.session_state.notes_db["Matière"] == matiere_sel) & 
                            (st.session_state.notes_db["Type Évaluation"] == type_eval_sel) & 
                            (st.session_state.notes_db["Trimestre"] == trimestre_sel)
                        ]
                        note_init = float(existing["Note"].values[0]) if (not existing.empty and pd.notnull(existing["Note"].values[0])) else float(bareme_sel / 2)
                        appr_init = str(existing["Appréciation"].values[0]) if (not existing.empty and pd.notnull(existing["Appréciation"].values[0])) else "Bon travail"

                        data_fiche.append({
                            "Élève": el,
                            f"Note /{bareme_sel}": note_init,
                            "Appréciation": appr_init
                        })

                    df_fiche = pd.DataFrame(data_fiche)

                    edited_fiche = st.data_editor(
                        df_fiche,
                        num_rows="fixed",
                        use_container_width=True,
                        column_config={
                            f"Note /{bareme_sel}": st.column_config.NumberColumn(
                                f"Note /{bareme_sel}",
                                min_value=0.0,
                                max_value=float(bareme_sel),
                                step=0.25
                            ),
                            "Élève": st.column_config.TextColumn("Nom & Prénom Élève", disabled=True)
                        },
                        key=f"editor_{cls_n}_{matiere_sel}_{type_eval_sel}_{trimestre_sel}_{bareme_sel}"
                    )

                    if st.button("💾 Enregistrer la Fiche de Matière"):
                        st.session_state.notes_db = st.session_state.notes_db[
                            ~((st.session_state.notes_db["Classe"] == cls_n) & 
                              (st.session_state.notes_db["Matière"] == matiere_sel) & 
                              (st.session_state.notes_db["Type Évaluation"] == type_eval_sel) & 
                              (st.session_state.notes_db["Trimestre"] == trimestre_sel))
                        ]
                        
                        new_rows = []
                        new_bg_rows = []
                        d_today = str(datetime.today().date())
                        m_today = datetime.today().strftime("%B")

                        for _, r in edited_fiche.iterrows():
                            new_rows.append({
                                "Classe": cls_n,
                                "Élève": r["Élève"],
                                "Matière": matiere_sel,
                                "Type Évaluation": type_eval_sel,
                                "Coefficient": coef_val,
                                "Note": r[f"Note /{bareme_sel}"],
                                "Barème": bareme_sel,
                                "Trimestre": trimestre_sel,
                                "Appréciation": r["Appréciation"]
                            })
                            new_bg_rows.append({
                                "Date": d_today, "Année": "2025-2026", "Trimestre": trimestre_sel, "Mois": m_today,
                                "Type Acteur": "Élève", "Nom Acteur": r["Élève"], "Classe": cls_n,
                                "Type Entrée": "Note", "Détail / Contenu": f"{matiere_sel} ({type_eval_sel}): {r[f'Note /{bareme_sel}']}/{bareme_sel}",
                                "Appréciation": r["Appréciation"]
                            })
                        
                        st.session_state.notes_db = pd.concat([st.session_state.notes_db, pd.DataFrame(new_rows)], ignore_index=True)
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, pd.DataFrame(new_bg_rows)], ignore_index=True)
                        
                        sauvegarder_donnees_externes()
                        st.success(f"Fiche de {matiere_sel} ({type_eval_sel}) enregistrée, synchronisée et sauvegardée automatiquement !")

                editeur_notes_fragment()

            elif not matiere_sel.strip():
                st.warning("Veuillez indiquer ou saisir le nom de la matière.")
            else:
                st.warning("Aucun élève trouvé dans cette classe.")

        elif menu_prof == "⚠️ Conduite":
            st.markdown("### Suivi de Conduite")
            st.info(f"📌 Classe assignée de session : **{classe_autorisee}**")
            with st.form("form_cond_prof"):
                cls_c = classe_autorisee
                st.write(f"**Classe concernée :** {cls_c}")
                eleves_c = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_c]["Nom Complet"].tolist()
                el_c = st.selectbox("Élève", eleves_c if eleves_c else ["--"])
                type_s = st.selectbox("Type", ["Avertissement", "Blâme", "Retenue", "Félicitations", "Encouragement"])
                desc = st.text_area("Description des faits")
                if st.form_submit_button("Enregistrer"):
                    if el_c and desc:
                        d_str = str(datetime.today().date())
                        new_cd = pd.DataFrame([{"Classe": cls_c, "Élève": el_c, "Date": d_str, "Type": type_s, "Description": desc}])
                        st.session_state.conduite_db = pd.concat([st.session_state.conduite_db, new_cd], ignore_index=True)
                        
                        row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == cls_c]
                        cyc_c = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"
                        tri_p = "1er Semestre" if cyc_c == "Collège" else "1er Trimestre"

                        bg_entry = pd.DataFrame([{
                            "Date": d_str, "Année": "2025-2026", "Trimestre": tri_p, "Mois": datetime.today().strftime("%B"),
                            "Type Acteur": "Élève", "Nom Acteur": el_c, "Classe": cls_c,
                            "Type Entrée": "Conduite", "Détail / Contenu": f"{type_s}: {desc}", "Appréciation": type_s
                        }])
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, bg_entry], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Remarque enregistrée et synchronisée.")

        elif menu_prof == "📖 Travail fait et à faire":
            st.markdown("### Travail fait et à faire")
            st.info(f"📌 Classe assignée de session : **{classe_autorisee}**")
            with st.form("form_cahier"):
                cls_ct = classe_autorisee
                st.write(f"**Classe concernée :** {cls_ct}")
                mat_ct = st.text_input("Matière")
                contenu = st.text_area("Contenu de la séance")
                travail = st.text_area("Travail à faire")
                if st.form_submit_button("Publier"):
                    if mat_ct and contenu:
                        new_ct = pd.DataFrame([{"Professeur": prof_connecte, "Date": str(datetime.today().date()), "Classe": cls_ct, "Matière": mat_ct, "Contenu": contenu, "Travail à faire": travail}])
                        st.session_state.cahier_textes = pd.concat([st.session_state.cahier_textes, new_ct], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Leçon publiée.")

        elif menu_prof == "📑 Cahier de texte":
            st.markdown("### Cahier de texte")
            st.info(f"📌 Classe assignée de session : **{classe_autorisee}**")
            st.caption("Ce rapport sera directement transmis à la direction et enregistré dans la base globale.")
            with st.form("form_rap_prof"):
                cls_r = classe_autorisee
                st.write(f"**Classe concernée :** {cls_r}")
                mat_r = st.text_input("Matière")
                bilan = st.text_area("Bilan du cours")
                diff = st.text_area("Difficultés ou remarques")
                if st.form_submit_button("Soumettre à l'administration"):
                    if mat_r and bilan:
                        d_str = str(datetime.today().date())
                        new_r = pd.DataFrame([{"Professeur": prof_connecte, "Date": d_str, "Classe": cls_r, "Matière": mat_r, "Bilan du Cours": bilan, "Difficultés / Remarques": diff}])
                        st.session_state.rapports_journaliers_prof = pd.concat([st.session_state.rapports_journaliers_prof, new_r], ignore_index=True)
                        
                        row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == cls_r]
                        cyc_r = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"
                        tri_p = "1er Semestre" if cyc_r == "Collège" else "1er Trimestre"

                        bg_prof = pd.DataFrame([{
                            "Date": d_str, "Année": "2025-2026", "Trimestre": tri_p, "Mois": datetime.today().strftime("%B"),
                            "Type Acteur": "Professeur", "Nom Acteur": prof_connecte, "Classe": cls_r,
                            "Type Entrée": "Rapport", "Détail / Contenu": f"{mat_r} - {bilan}", "Appréciation": diff if diff else "RAS"
                        }])
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, bg_prof], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Rapport transmis et centralisé dans la Base Globale !")

elif st.session_state.espace_actif == "👨‍👩‍👧 Espace Parents / Élèves":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Portail Parent & Élève</div>', unsafe_allow_html=True)

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
                    st.error("Informations incorrectes. Veuillez vérifier vos données d'accès.")
    else:
        eleve = st.session_state["parent_logged_eleve"]
        classe = st.session_state["parent_logged_classe"]
        
        row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe]
        cycle_eleve = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"

        st.success(f"Connecté pour l'élève : **{eleve}** (Classe : {classe} - {cycle_eleve})")
        if st.button("Se déconnecter"):
            st.session_state["parent_logged_eleve"] = ""
            st.rerun()

        st.markdown("---")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Bulletin & Notes", "📅 Emploi du Temps", "📉 Absences", "⚠️ Conduite", "📖 Travail fait et à faire", "🪪 Carte Scolaire"])
        
        with t1:
            st.subheader("Bulletin de Notes Officiel (Consultation en ligne)")
            st.info("💡 Conformément au règlement intérieur, le téléchargement direct du bulletin PDF est restreint à l'espace administration.")
            
            if cycle_eleve == "Collège":
                tri_p = st.selectbox("Sélectionner la Période", ["1er Semestre", "2ème Semestre"])
            else:
                tri_p = st.selectbox(
                    "Sélectionner la Période",
                    ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"],
                )
            
            notes_el = st.session_state.notes_db[
                (st.session_state.notes_db["Élève"] == eleve) & 
                (st.session_state.notes_db["Trimestre"] == tri_p)
            ]

            if not notes_el.empty:
                if cycle_eleve == "Collège":
                    st.dataframe(notes_el[["Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Appréciation"]], use_container_width=True)
                    total_pts = (notes_el["Note"] * notes_el["Coefficient"]).sum()
                    total_coef = notes_el["Coefficient"].sum()
                    if total_coef > 0:
                        moy = total_pts / total_coef
                        st.markdown(f"### 🎯 Moyenne générale pondérée : **{moy:.2f} / 20**")
                else:
                    st.dataframe(notes_el[["Matière", "Type Évaluation", "Note", "Barème", "Appréciation"]], use_container_width=True)
                    somme_sur_10 = 0.0
                    nb_mat = 0
                    for _, r in notes_el.iterrows():
                        n_val = float(r["Note"]) if pd.notnull(r["Note"]) else 0.0
                        b_val = float(r["Barème"]) if pd.notnull(r["Barème"]) and float(r["Barème"]) > 0 else 10.0
                        somme_sur_10 += (n_val / b_val) * 10.0
                        nb_mat += 1
                    if nb_mat > 0:
                        moy = somme_sur_10 / nb_mat
                        st.markdown(f"### 🎯 Moyenne générale : **{moy:.2f} / 10**")
            else:
                st.info(f"Aucune note enregistrée pour le {tri_p}.")

        with t2:
            st.subheader("Emploi du Temps de la Classe & Documents Interactifs")
            grid_edt = get_or_create_edt(classe)
            st.dataframe(grid_edt, use_container_width=True)
            
            if classe in st.session_state.edt_documents and st.session_state.edt_documents[classe]:
                st.markdown("#### 📁 Documents associés à l'emploi du temps :")
                for doc_name in st.session_state.edt_documents[classe]:
                    st.write(f"- {doc_name}")

        with t3:
            st.subheader("Absences (Historique Base Globale)")
            abs_el = st.session_state.absences_db[st.session_state.absences_db["Élève"].str.contains(eleve, case=False, na=False)]
            if not abs_el.empty: st.dataframe(abs_el, use_container_width=True)
            else: st.success("Aucune absence recensée.")

        with t4:
            st.subheader("Conduite")
            cond_el = st.session_state.conduite_db[st.session_state.conduite_db["Élève"].str.contains(eleve, case=False, na=False)]
            if not cond_el.empty: st.dataframe(cond_el, use_container_width=True)
            else: st.info("Aucune observation disciplinaire.")

        with t5:
            st.subheader("Travail fait et à faire de la Classe")
            ct_cls = st.session_state.cahier_textes[st.session_state.cahier_textes["Classe"] == classe]
            if not ct_cls.empty: st.dataframe(ct_cls, use_container_width=True)
            else: st.info("Aucune leçon publiée.")

        with t6:
            st.subheader("Carte Scolaire Numérique")
            st.markdown(
                f"""
                <div style="border: 2px solid #1E3A8A; padding: 20px; border-radius: 12px; background-color: #FFF; max-width: 400px;">
                    <h4 style="color: #1E3A8A; text-align: center; margin:0;">ÉCOLE PRÉSIDENT NELSON MANDELA</h4>
                    <p style="text-align: center; font-size: 0.7rem; color: #666;">éduquer, instruire et promouvoir les vertus africaines.</p>
                    <hr>
                    <p><b>Nom & Prénom :</b> {eleve}</p>
                    <p><b>Classe :</b> {classe} ({cycle_eleve})</p>
                    <p><b>Statut :</b> Élève régulier(ère)</p>
                </div>
                """,
                unsafe_allow_html=True
            )

elif st.session_state.espace_actif == "🔒 Espace Administration (Sécurisé)":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration Générale (Accès Restreint)</div>', unsafe_allow_html=True)

    if not st.session_state.authenticated_admin:
        with st.form("form_adm_secu"):
            em = st.text_input("Email Administrateur / Gestionnaire / Propriétaire")
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion Admin"):
                match_a = False
                role_connecte = "Administrateur"
                
                clean_em = em.strip().lower()
                clean_pw = pw.strip()

                for _, row in st.session_state.admin_credentials.iterrows():
                    if str(row["Email"]).strip().lower() == clean_em and str(row["Mot de passe"]).strip() == clean_pw:
                        match_a = True
                        break
                
                if not match_a:
                    for _, row in st.session_state.gestionnaires_proprietaires_db.iterrows():
                        if str(row["Email"]).strip().lower() == clean_em and str(row["Mot de passe"]).strip() == clean_pw:
                            match_a = True
                            role_connecte = row["Rôle"]
                            break

                if match_a:
                    st.session_state.authenticated_admin = True
                    st.session_state.admin_role_connecte = role_connecte
                    st.session_state.admin_email_connecte = clean_em
                    st.success(f"Accès accordé en tant que **{role_connecte}** !")
                    st.rerun()
                else:
                    st.error("Identifiants erronés. Veuillez vérifier votre email et mot de passe.")
    else:
        role_actuel = st.session_state.get("admin_role_connecte", "Administrateur")
        email_actuel = st.session_state.get("admin_email_connecte", "")
        st.success(f"Mode {role_actuel} Activé — Gestion Centralisée Complète.")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.session_state.pop("admin_role_connecte", None)
            st.session_state.pop("admin_email_connecte", None)
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "☁️ Sauvegarde & Restauration Cloud (Anti-Effacement)",
            "📑 Bulletins PDF (Par Élève & Par Classe)",
            "🛡️ Gestionnaires & Propriétaires (Liste Blanche)",
            "📊 Liste & Classement des Élèves (Par Classe & Niveau)",
            "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel",
            "🤖 Assistant IA Administration",
            "📅 Emploi du Temps Interactif & Documents",
            "👨‍🎓 Élèves (Export PDF, Modif, Suppr)", 
            "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)", 
            "🏫 Gestion des classes et cycles", 
            "📋 Listes blanches des parents", 
            "📑 Rapport journalier"
        ])

        if adm_tab == "☁️ Sauvegarde & Restauration Cloud (Anti-Effacement)":
            st.subheader("☁️ Sauvegarde & Restauration de la Base de Données (Persistance Cloud Éphémère)")
            st.info("Puisque le cloud efface les fichiers locaux lors d'un redémarrage complet du serveur, utilisez cet outil pour **sauvegarder** régulièrement votre base SQLite sur votre ordinateur ou pour la **restaurer** après une réinitialisation.")

            col_s1, col_s2 = st.columns(2)

            with col_s1:
                st.markdown("#### 💾 1. Télécharger une Sauvegarde")
                st.caption("Télécharge le fichier de base de données actuel contenant toutes les données (élèves, notes, utilisateurs, etc.).")
                if os.path.exists(DB_FILE):
                    with open(DB_FILE, "rb") as f:
                        db_bytes = f.read()
                    st.download_button(
                        label="📥 Télécharger la base SQLite (.db)",
                        data=db_bytes,
                        file_name=f"cpnm_database_backup_{datetime.today().strftime('%Y%m%d')}.db",
                        mime="application/octet-stream"
                    )
                else:
                    st.warning("Aucun fichier de base de données trouvé.")

            with col_s2:
                st.markdown("#### 🔄 2. Restaurer une Sauvegarde")
                st.caption("Envoyez un fichier de sauvegarde `.db` précédent pour restaurer l'intégralité des données après un reset du cloud.")
                uploaded_db_file = st.file_uploader("Sélectionner le fichier .db de sauvegarde", type=["db"])
                if uploaded_db_file is not None:
                    if st.button("⚠️ Confirmer et restaurer cette base de données"):
                        with open(DB_FILE, "wb") as f_out:
                            f_out.write(uploaded_db_file.getbuffer())
                        st.success("Base de données restaurée avec succès ! Rechargez la page pour appliquer les changements.")
                        st.balloons()

        elif adm_tab == "📑 Bulletins PDF (Par Élève & Par Classe)":
            st.subheader("📑 Génération et Téléchargement des Bulletins en PDF")
            st.info("Espace sécurisé pour télécharger les bulletins officiels par élève ou pour l'ensemble d'une classe.")

            sous_mode_bul = st.radio("Mode de génération :", ["Par Élève", "Par Classe entière (Zip / Fichiers consolidés)"], horizontal=True)

            if sous_mode_bul == "Par Élève":
                classes_list = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
                if classes_list:
                    c_bul_cls = st.selectbox("Sélectionner la classe", classes_list, key="bul_cls_s")
                    eleves_bul = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == c_bul_cls]["Nom Complet"].tolist()
                    
                    if eleves_bul:
                        c_bul_el = st.selectbox("Sélectionner l'élève", eleves_bul, key="bul_el_s")
                        row_c = st.session_state.classes_db[st.session_state.classes_db["Classe"] == c_bul_cls]
                        cyc_bul = row_c["Cycle"].values[0] if not row_c.empty else "Collège"
                        
                        if cyc_bul == "Collège":
                            tri_bul = st.selectbox("Période", ["1er Semestre", "2ème Semestre"], key="bul_tri_c")
                        else:
                            tri_bul = st.selectbox("Période", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"], key="bul_tri_e")

                        if st.button("Générer le Bulletin PDF de l'élève"):
                            pdf_data_b = generer_bulletin_pdf(c_bul_el, c_bul_cls, tri_bul)
                            st.success("Bulletin généré avec succès !")
                            st.download_button(
                                label=f"📄 Télécharger le Bulletin de {c_bul_el} ({tri_bul})",
                                data=pdf_data_b,
                                file_name=f"bulletin_{c_bul_el.replace(' ', '_')}_{tri_bul}.pdf",
                                mime="application/pdf"
                            )
                    else:
                        st.warning("Aucun élève dans cette classe.")
                else:
                    st.warning("Aucune classe enregistrée.")

            else:
                classes_list = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
                if classes_list:
                    c_bul_cls_tot = st.selectbox("Sélectionner la classe entière", classes_list, key="bul_cls_tot")
                    row_c = st.session_state.classes_db[st.session_state.classes_db["Classe"] == c_bul_cls_tot]
                    cyc_bul = row_c["Cycle"].values[0] if not row_c.empty else "Collège"
                    
                    if cyc_bul == "Collège":
                        tri_bul_tot = st.selectbox("Période", ["1er Semestre", "2ème Semestre"], key="bul_tri_tot_c")
                    else:
                        tri_bul_tot = st.selectbox("Période", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"], key="bul_tri_tot_e")

                    eleves_classe_tot = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == c_bul_cls_tot]["Nom Complet"].tolist()

                    if eleves_classe_tot:
                        st.info(f"Classe de **{c_bul_cls_tot}** : {len(eleves_classe_tot)} élèves détectés.")
                        if st.button("Préparer et Télécharger les Bulletins de la Classe"):
                            import zipfile
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                                for el_name in eleves_classe_tot:
                                    pdf_bytes = generer_bulletin_pdf(el_name, c_bul_cls_tot, tri_bul_tot)
                                    filename = f"bulletin_{el_name.replace(' ', '_')}_{tri_bul_tot}.pdf"
                                    zip_file.writestr(filename, pdf_bytes)
                            
                            zip_data = zip_buffer.getvalue()
                            st.success("Archive ZIP des bulletins de la classe générée avec succès !")
                            st.download_button(
                                label=f"📦 Télécharger tous les bulletins de {c_bul_cls_tot} (.zip)",
                                data=zip_data,
                                file_name=f"bulletins_classe_{c_bul_cls_tot.replace(' ', '_')}.zip",
                                mime="application/zip"
                            )
                    else:
                        st.warning("Aucun élève dans cette classe.")
                else:
                    st.warning("Aucune classe disponible.")

        elif adm_tab == "🛡️ Gestionnaires & Propriétaires (Liste Blanche)":
            st.subheader("🛡️ Liste Blanche des Gestionnaires & Propriétaires")
            st.info("💡 **Règle d'accès :** Seul l'administrateur principal (`cpnm@gmail.com`) a les privilèges exclusifs d'ajouter ou de révoquer des membres dans cette liste.")

            df_gp = st.session_state.gestionnaires_proprietaires_db
            is_super_admin = (email_actuel.strip().lower() == "cpnm@gmail.com")

            st.markdown("#### Membres Actuels")
            for idx, row in df_gp.iterrows():
                col_i1, col_i2, col_i3, col_i4 = st.columns([2, 2, 2, 2])
                with col_i1: st.write(f"**{row['Prénom']} {row['Nom']}**")
                with col_i2: st.write(row['Email'])
                with col_i3: st.write(f"Rôle : {row['Rôle']}")
                with col_i4:
                    if is_super_admin:
                        if st.button(f"🗑️ Révoquer", key=f"rev_{idx}"):
                            st.session_state.gestionnaires_proprietaires_db = df_gp.drop(idx).reset_index(drop=True)
                            sauvegarder_donnees_externes()
                            st.success(f"Membre {row['Prénom']} {row['Nom']} révoqué avec succès !")
                            st.rerun()
                    else:
                        st.caption("🔒 (Réservé à cpnm@gmail.com)")

            st.markdown("---")
            if is_super_admin:
                with st.expander("➕ Ajouter un Gestionnaire ou Propriétaire"):
                    with st.form("form_add_gp"):
                        gp_nom = st.text_input("Nom")
                        gp_prenom = st.text_input("Prénom")
                        gp_email = st.text_input("Email professionnel")
                        gp_pass = st.text_input("Mot de passe temporaire", type="password")
                        gp_role = st.selectbox("Rôle", ["Gestionnaire", "Propriétaire"])
                        
                        if st.form_submit_button("Ajouter à la liste blanche"):
                            if gp_nom and gp_email and gp_pass:
                                if gp_email in df_gp["Email"].values:
                                    st.warning("Cet email est déjà enregistré.")
                                else:
                                    new_member = pd.DataFrame([{
                                        "Nom": gp_nom, "Prénom": gp_prenom, "Email": gp_email, 
                                        "Mot de passe": gp_pass, "Rôle": gp_role
                                    }])
                                    st.session_state.gestionnaires_proprietaires_db = pd.concat([df_gp, new_member], ignore_index=True)
                                    sauvegarder_donnees_externes()
                                    st.success("Nouveau membre ajouté avec succès à la liste blanche !")
                                    st.rerun()
                            else:
                                st.warning("Veuillez remplir tous les champs obligatoires.")
            else:
                st.warning("⚠️ Vous devez être connecté avec l'adresse `cpnm@gmail.com` pour pouvoir ajouter de nouveaux gestionnaires ou propriétaires.")

        elif adm_tab == "📊 Liste & Classement des Élèves (Par Classe & Niveau)":
            st.subheader("📊 Classement et Liste des Élèves par Classe et par Niveau (Cycle)")

            if "Prénom" not in st.session_state.eleves_db.columns or "Nom" not in st.session_state.eleves_db.columns:
                prenoms, noms = [], []
                for _, r in st.session_state.eleves_db.iterrows():
                    nc = str(r.get("Nom Complet", ""))
                    parts = nc.split(" ", 1)
                    prenoms.append(parts[0] if len(parts) > 0 else "")
                    noms.append(parts[1] if len(parts) > 1 else "")
                st.session_state.eleves_db["Prénom"] = prenoms
                st.session_state.eleves_db["Nom"] = noms

            st.session_state.eleves_db = st.session_state.eleves_db.sort_values(by="Nom").reset_index(drop=True)
            df_merged = pd.merge(st.session_state.eleves_db, st.session_state.classes_db[["Classe", "Cycle"]], on="Classe", how="left")

            t_niv, t_cls = st.tabs(["🏛️ Par Niveau (Cycle)", "🏫 Par Classe"])

            with t_niv:
                st.markdown("### 🏛️ Répartition des Élèves par Niveau (Cycle)")
                cycles_existants = ["Préscolaire", "Élémentaire", "Collège"]
                for cyc in cycles_existants:
                    df_c = df_merged[df_merged["Cycle"] == cyc]
                    with st.expander(f"📌 Cycle {cyc.upper()} ({len(df_c)} Élèves)", expanded=True):
                        if not df_c.empty:
                            df_export_niv = df_c[["Nom", "Prénom", "Classe", "Date de Naissance"]].sort_values(by=["Nom", "Prénom"])
                            st.dataframe(df_export_niv, use_container_width=True)
                            
                            c_exp_pdf, c_exp_excel = st.columns(2)
                            with c_exp_pdf:
                                pdf_niv = export_table_pdf(f"LISTE DES ÉLÈVES - CYCLE {cyc.upper()}", df_export_niv)
                                st.download_button(
                                    label=f"📄 Télécharger PDF ({cyc})",
                                    data=pdf_niv,
                                    file_name=f"eleves_cycle_{cyc.lower()}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_pdf_cycle_{cyc}"
                                )
                            with c_exp_excel:
                                excel_niv = export_table_excel(df_export_niv)
                                st.download_button(
                                    label=f"📊 Télécharger Excel ({cyc})",
                                    data=excel_niv,
                                    file_name=f"eleves_cycle_{cyc.lower()}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"btn_excel_cycle_{cyc}"
                                )
                        else:
                            st.info("Aucun élève dans ce cycle.")

            with t_cls:
                st.markdown("### 🏫 Répartition des Élèves par Classe")
                classes_existantes = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
                for cl in classes_existantes:
                    df_cl = df_merged[df_merged["Classe"] == cl]
                    with st.expander(f"🏫 Classe : {cl} ({len(df_cl)} Élèves)", expanded=True):
                        if not df_cl.empty:
                            df_export_cls = df_cl[["Nom", "Prénom", "Date de Naissance"]].sort_values(by=["Nom", "Prénom"])
                            st.dataframe(df_export_cls, use_container_width=True)
                            
                            c_exp_pdf_cls, c_exp_excel_cls = st.columns(2)
                            clean_cl_name = cl.replace(" ", "_").lower()
                            with c_exp_pdf_cls:
                                pdf_cls = export_table_pdf(f"LISTE DES ÉLÈVES - CLASSE {cl}", df_export_cls)
                                st.download_button(
                                    label=f"📄 Télécharger PDF ({cl})",
                                    data=pdf_cls,
                                    file_name=f"eleves_classe_{clean_cl_name}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_pdf_classe_{cl}"
                                )
                            with c_exp_excel_cls:
                                excel_cls = export_table_excel(df_export_cls)
                                st.download_button(
                                    label=f"📊 Télécharger Excel ({cl})",
                                    data=excel_cls,
                                    file_name=f"eleves_classe_{clean_cl_name}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    key=f"btn_excel_classe_{cl}"
                                )
                        else:
                            st.info("Aucun élève dans cette classe.")

        elif adm_tab == "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel":
            st.subheader("🗄️ Base Globale Centrale — Traçabilité Annuelle, Trimestrielle & Mensuelle")
            st.info("Cette table centralise l'ensemble des notes, absences, rapports et remarques de l'établissement.")

            if not st.session_state.base_globale_db.empty:
                df_bg = st.session_state.base_globale_db
                
                c_f1, c_f2, c_f3 = st.columns(3)
                with c_f1:
                    trim_filter = st.selectbox("Filtrer par Trimestre / Semestre", ["Tous"] + list(df_bg["Trimestre"].dropna().unique()))
                with c_f2:
                    mois_filter = st.selectbox("Filtrer par Mois", ["Tous"] + list(df_bg["Mois"].dropna().unique()))
                with c_f3:
                    type_filter = st.selectbox("Filtrer par Type d'Entrée", ["Tous"] + list(df_bg["Type Entrée"].dropna().unique()))

                df_filtered = df_bg.copy()
                if trim_filter != "Tous":
                    df_filtered = df_filtered[df_filtered["Trimestre"] == trim_filter]
                if mois_filter != "Tous":
                    df_filtered = df_filtered[df_filtered["Mois"] == mois_filter]
                if type_filter != "Tous":
                    df_filtered = df_filtered[df_filtered["Type Entrée"] == type_filter]

                st.dataframe(df_filtered, use_container_width=True)

                c_dl1, c_dl2 = st.columns(2)
                with c_dl1:
                    pdf_bg_bytes = export_table_pdf("RAPPORT DE LA BASE GLOBALE", df_filtered)
                    st.download_button("📄 Télécharger Base Globale (PDF)", data=pdf_bg_bytes, file_name="base_globale_cpnm.pdf", mime="application/pdf")
                with c_dl2:
                    excel_bg_bytes = export_table_excel(df_filtered)
                    st.download_button("📊 Télécharger Base Globale (Excel)", data=excel_bg_bytes, file_name="base_globale_cpnm.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.info("La base globale est vide pour le moment.")

        elif adm_tab == "🤖 Assistant IA Administration":
            st.subheader("🤖 Assistant IA Pédagogique et Administratif")
            st.info("Posez vos questions sur les effectifs, les enseignants, le suivi ou l'état de l'établissement.")

            if "ia_chat_history" not in st.session_state:
                st.session_state.ia_chat_history = [
                    {"role": "assistant", "content": "Bonjour ! Je suis l'assistant virtuel de l'École Président Nelson Mandela. Comment puis-je vous aider aujourd'hui ?"}
                ]

            for msg in st.session_state.ia_chat_history:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            user_q = st.chat_input("Posez votre question à l'IA...")
            if user_q:
                st.session_state.ia_chat_history.append({"role": "user", "content": user_q})
                with st.chat_message("user"):
                    st.markdown(user_q)

                resp = assistant_ia_repondre(user_q)
                st.session_state.ia_chat_history.append({"role": "assistant", "content": resp})
                with st.chat_message("assistant"):
                    st.markdown(resp)

        elif adm_tab == "📅 Emploi du Temps Interactif & Documents":
            st.subheader("📅 Gestion des Emplois du Temps par Classe")
            classes_edt = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
            if classes_edt:
                cls_edt_sel = st.selectbox("Choisir la classe pour l'emploi du temps", classes_edt, key="sel_edt_adm")
                current_grid = get_or_create_edt(cls_edt_sel)

                st.markdown(f"**Édition de l'Emploi du Temps pour la classe : {cls_edt_sel}**")
                edited_grid = st.data_editor(current_grid, use_container_width=True, key=f"grid_edt_{cls_edt_sel}")

                if st.button("💾 Enregistrer l'Emploi du Temps"):
                    st.session_state.edt_grid_db[cls_edt_sel] = edited_grid
                    sauvegarder_donnees_externes()
                    st.success("Emploi du temps mis à jour et sauvegardé avec succès !")
            else:
                st.warning("Veuillez d'abord créer des classes.")

        elif adm_tab == "👨‍🎓 Élèves (Export PDF, Modif, Suppr)":
            st.subheader("👨‍🎓 Gestion des Élèves (Ajout, Modification, Suppression via Tableau Dynamique)")
            st.info("💡 **Astuce :** Vous pouvez ajouter directement un élève en cliquant sur la ligne vide `+` tout en bas du tableau ci-dessous, ou modifier/supprimer des élèves existants directement en ligne. Pensez à cliquer sur **'Enregistrer les modifications'** pour valider.")

            if "Prénom" not in st.session_state.eleves_db.columns or "Nom" not in st.session_state.eleves_db.columns:
                prenoms, noms = [], []
                for _, r in st.session_state.eleves_db.iterrows():
                    nc = str(r.get("Nom Complet", ""))
                    parts = nc.split(" ", 1)
                    prenoms.append(parts[0] if len(parts) > 0 else "")
                    noms.append(parts[1] if len(parts) > 1 else "")
                st.session_state.eleves_db["Prénom"] = prenoms
                st.session_state.eleves_db["Nom"] = noms

            cols_eleves_edit = ["Prénom", "Nom", "Date de Naissance", "Classe"]
            for col in cols_eleves_edit:
                if col not in st.session_state.eleves_db.columns:
                    st.session_state.eleves_db[col] = ""

            classes_dispo = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"]

            df_to_edit = st.session_state.eleves_db[cols_eleves_edit].copy()

            edited_eleves_df = st.data_editor(
                df_to_edit,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Classe": st.column_config.SelectboxColumn(
                        "Classe",
                        help="Classe de l'élève",
                        options=classes_dispo,
                        required=True
                    ),
                    "Date de Naissance": st.column_config.TextColumn(
                        "Date de Naissance (AAAA-MM-JJ)",
                        help="Format AAAA-MM-JJ"
                    )
                },
                key="editor_eleves_admin"
            )

            if st.button("💾 Enregistrer les modifications de la liste des élèves"):
                clean_df = edited_eleves_df.copy()
                clean_df["Prénom"] = clean_df["Prénom"].fillna("").astype(str).str.strip()
                clean_df["Nom"] = clean_df["Nom"].fillna("").astype(str).str.strip()
                clean_df["Date de Naissance"] = clean_df["Date de Naissance"].fillna("2012-01-01").astype(str).str.strip()
                clean_df["Classe"] = clean_df["Classe"].fillna(classes_dispo[0]).astype(str).str.strip()
                clean_df["Nom Complet"] = clean_df["Prénom"] + " " + clean_df["Nom"]
                
                photos = []
                for _, r in clean_df.iterrows():
                    match_orig = st.session_state.eleves_db[
                        (st.session_state.eleves_db["Prénom"] == r["Prénom"]) & 
                        (st.session_state.eleves_db["Nom"] == r["Nom"])
                    ]
                    if not match_orig.empty and "Photo" in match_orig.columns:
                        photos.append(match_orig["Photo"].values[0])
                    else:
                        photos.append(None)
                clean_df["Photo"] = photos

                st.session_state.eleves_db = clean_df.sort_values(by="Nom").reset_index(drop=True)
                sauvegarder_donnees_externes()
                st.success("La base des élèves a été mise à jour, synchronisée et sauvegardée avec succès !")
                st.rerun()

            st.markdown("---")
            st.markdown("#### 📄 Export de la liste complète")
            c_exp_p, c_exp_e = st.columns(2)
            with c_exp_p:
                pdf_bytes_el = export_table_pdf("LISTE GÉNÉRALE DES ÉLÈVES", st.session_state.eleves_db[["Nom", "Prénom", "Classe", "Date de Naissance"]])
                st.download_button("📄 Télécharger PDF", data=pdf_bytes_el, file_name="liste_eleves.pdf", mime="application/pdf")
            with c_exp_e:
                excel_bytes_el = export_table_excel(st.session_state.eleves_db[["Nom", "Prénom", "Classe", "Date de Naissance"]])
                st.download_button("📊 Télécharger Excel", data=excel_bytes_el, file_name="liste_eleves.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        elif adm_tab == "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)":
            st.subheader("👨‍🏫 Gestion des Professeurs")
            edited_prof = st.data_editor(st.session_state.prof_credentials, num_rows="dynamic", use_container_width=True, key="editor_prof_admin")
            if st.button("💾 Enregistrer les modifications professeurs"):
                st.session_state.prof_credentials = edited_prof
                sauvegarder_donnees_externes()
                st.success("Mise à jour enregistrée !")
                st.rerun()

        elif adm_tab == "🏫 Gestion des classes et cycles":
            st.subheader("🏫 Gestion des Classes et Cycles")
            edited_classes = st.data_editor(st.session_state.classes_db, num_rows="dynamic", use_container_width=True, key="editor_classes_admin")
            if st.button("💾 Enregistrer les modifications des classes"):
                st.session_state.classes_db = edited_classes
                sauvegarder_donnees_externes()
                st.success("Classes et cycles mis à jour avec succès !")
                st.rerun()

        elif adm_tab == "📋 Listes blanches des parents":
            st.subheader("📋 Listes blanches des parents")
            edited_parents = st.data_editor(st.session_state.parents_white_list, num_rows="dynamic", use_container_width=True, key="editor_parents_admin")
            if st.button("💾 Enregistrer la liste blanche des parents"):
                st.session_state.parents_white_list = edited_parents
                sauvegarder_donnees_externes()
                st.success("Liste blanche des parents mise à jour avec succès !")
                st.rerun()

        elif adm_tab == "📑 Rapport journalier":
            st.subheader("📑 Rapport journalier")
            if not st.session_state.rapports_journaliers_prof.empty:
                st.dataframe(st.session_state.rapports_journaliers_prof, use_container_width=True)
                if st.button("📄 Télécharger les rapports journaliers (PDF)"):
                    pdf_rj = export_table_pdf("RAPPORTS JOURNALIERS DES PROFESSEURS", st.session_state.rapports_journaliers_prof)
                    st.download_button("Télécharger PDF", data=pdf_rj, file_name="rapports_journaliers.pdf", mime="application/pdf")
            else:
                st.info("Aucun rapport journalier enregistré.")

elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Rapports Globaux et Consolidation Annuelle</div>', unsafe_allow_html=True)
    st.markdown("Téléchargez le rapport général consolidé de l'établissement au format PDF :")
    if st.button("📄 Générer et Télécharger le Rapport Général Consolidé (PDF)"):
        pdf_gen = generer_rapport_general_pdf()
        st.success("Rapport général généré avec succès !")
        st.download_button(
            label="📥 Télécharger le Rapport Général PDF",
            data=pdf_gen,
            file_name=f"rapport_general_cpnm_{datetime.today().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
