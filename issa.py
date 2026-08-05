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
        "notes_db": st.session_state.notes_db.to_dict(orient="split"),
        "matieres_def": st.session_state.matieres_def.to_dict(orient="split"),
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
# 0. BIS. GESTION DES POLICES UNICODE
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
# 1. CONFIGURATION DE LA PAGE & DESIGN XXL
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
    .header-ecole { color: #1E3A8A; font-size: clamp(1.8rem, 4vw, 2.8rem); font-weight: 900; text-align: center; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 1px; padding: 0 10px; }
    .sub-header { color: #047857; font-size: clamp(0.9rem, 2vw, 1.2rem); font-weight: 700; text-align: center; margin-bottom: 25px; padding: 0 10px; font-style: italic; }
    .animated-card { border: 2px solid #E2E8F0; padding: clamp(15px, 3vw, 25px); border-radius: 16px; background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%); box-shadow: 0 10px 25px rgba(0,0,0,0.05); transition: transform 0.2s ease, box-shadow 0.2s ease; text-align: center; cursor: pointer; margin-bottom: 15px; height: 100%; }
    .animated-card:hover { transform: translateY(-3px); box-shadow: 0 15px 30px rgba(30, 58, 138, 0.12); border-color: #2563EB; }
    .kpi-card-animated { border-left: 5px solid #2563EB; background: #FFFFFF; padding: 15px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; }
    .stButton>button { background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); color: white; border-radius: 8px; font-weight: bold; border: none; padding: 0.75rem 1rem; transition: transform 0.1s ease; width: 100%; min-height: 44px; font-size: 1rem; }
    .stButton>button:active { transform: scale(0.98); }
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
            {"Nom": "Ndiaye", "Prénom": "Cheikh", "Mot de passe": "prof789", "Matière Principale": "Histoire-Géographie", "Classe Attribuée": "CE2"}
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
                ["CE2", "Élémentaire", "Moussa Ba"],
                ["Grande Section", "Préscolaire", "Marie Faye"]
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
                ["Aminata Ba", "Aminata", "Ba", "2013-02-10", "CE2", None],
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
                {"Date": "2026-01-15", "Année": "2025-2026", "Trimestre": "1er Semestre", "Mois": "Janvier", "Type Acteur": "Élève", "Nom Acteur": "Mamadou Diallo", "Classe": "6ème A", "Type Entrée": "Note", "Détail / Contenu": "Mathématiques (Devoir 1): 15.5/20", "Appréciation": "Très bon travail"}
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
        st.session_state.cahier_textes = pd.DataFrame(columns=["Professeur", "Date", "Classe", "Matière", "Contenu", "Travail à faire"])

if "rapports_journaliers_prof" not in st.session_state:
    if "rapports_journaliers_prof" in saved_data:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(**saved_data["rapports_journaliers_prof"])
    else:
        st.session_state.rapports_journaliers_prof = pd.DataFrame(columns=["Professeur", "Date", "Classe", "Matière", "Bilan du Cours", "Difficultés / Remarques"])

if "absences_db" not in st.session_state:
    if "absences_db" in saved_data:
        st.session_state.absences_db = pd.DataFrame(**saved_data["absences_db"])
    else:
        st.session_state.absences_db = pd.DataFrame(columns=["Date", "Classe", "Élève", "Statut", "Motif"])

if "notes_db" not in st.session_state:
    if "notes_db" in saved_data:
        st.session_state.notes_db = pd.DataFrame(**saved_data["notes_db"])
    else:
        st.session_state.notes_db = pd.DataFrame(
            columns=["Classe", "Élève", "Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Trimestre", "Appréciation"],
            data=[
                ["6ème A", "Mamadou Diallo", "Mathématiques", "Devoir 1", 3, 15.5, 20, "1er Semestre", "Très bon travail."],
                ["CP", "Fatou Sow", "Lecture", "Composition", 2, 8.5, 10, "1er Trimestre", "Très bien."]
            ]
        )

if "matieres_def" not in st.session_state:
    if "matieres_def" in saved_data:
        st.session_state.matieres_def = pd.DataFrame(**saved_data["matieres_def"])
    else:
        st.session_state.matieres_def = pd.DataFrame([
            {"Matière": "Mathématiques", "Coefficient": 3, "Cycle": "Collège"},
            {"Matière": "Français", "Coefficient": 3, "Cycle": "Collège"},
            {"Matière": "Lecture", "Coefficient": 2, "Cycle": "Élémentaire"},
            {"Matière": "Mathématiques", "Coefficient": 3, "Cycle": "Élémentaire"},
            {"Matière": "Activités Sensorielles", "Coefficient": 1, "Cycle": "Préscolaire"}
        ])

if "conduite_db" not in st.session_state:
    if "conduite_db" in saved_data:
        st.session_state.conduite_db = pd.DataFrame(**saved_data["conduite_db"])
    else:
        st.session_state.conduite_db = pd.DataFrame(columns=["Classe", "Élève", "Date", "Type", "Description"])

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
    elif cycle == "Élémentaire":
        w_mat, w_comp, w_coef, w_moy, w_app = 55, 30, 20, 30, 55
        pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
        pdf.cell(w_comp, 7, "Évaluation", 1, 0, "C", True)
        pdf.cell(w_coef, 7, "Coef", 1, 0, "C", True)
        pdf.cell(w_moy, 7, "Moy. /20", 1, 0, "C", True)
        pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)
    else:  # Préscolaire
        w_mat, w_comp, w_app = 70, 50, 70
        pdf.cell(w_mat, 7, "Domaine d'apprentissage", 1, 0, "C", True)
        pdf.cell(w_comp, 7, "Évaluation", 1, 0, "C", True)
        pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)

    total_points = 0.0
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

                moy_mat = (((d1_val + d2_val) / 2.0) + comp_val) / 2.0
                total_points += moy_mat * coef
                total_coefs += coef

                pdf.cell(w_mat, 6, str(mat)[:20], 1, 0, "L")
                pdf.cell(w_d1, 6, d1_str, 1, 0, "C")
                pdf.cell(w_d2, 6, d2_str, 1, 0, "C")
                pdf.cell(w_comp, 6, comp_str, 1, 0, "C")
                pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
                pdf.cell(w_moy, 6, f"{moy_mat:.2f}", 1, 0, "C")
                pdf.cell(w_app, 6, str(appr_str)[:25], 1, 1, "L")
            elif cycle == "Élémentaire":
                coef = int(df_mat["Coefficient"].iloc[0]) if "Coefficient" in df_mat.columns and pd.notnull(df_mat["Coefficient"].iloc[0]) else 1
                note_val = float(df_mat["Note"].iloc[0]) if not df_mat.empty and pd.notnull(df_mat["Note"].iloc[0]) else 0.0
                bareme_val = float(df_mat["Barème"].iloc[0]) if "Barème" in df_mat.columns and pd.notnull(df_mat["Barème"].iloc[0]) and float(df_mat["Barème"].iloc[0]) > 0 else 20.0
                
                # Conversion automatique sur 20
                note_sur_20 = (note_val / bareme_val) * 20.0
                total_points += note_sur_20 * coef
                total_coefs += coef

                pdf.cell(w_mat, 6, str(mat)[:25], 1, 0, "L")
                pdf.cell(w_comp, 6, f"{note_val:.2f}/{bareme_val}", 1, 0, "C")
                pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
                pdf.cell(w_moy, 6, f"{note_sur_20:.2f}", 1, 0, "C")
                pdf.cell(w_app, 6, str(appr_str)[:30], 1, 1, "L")
            else:  # Préscolaire
                eval_comp = df_mat["Appréciation"].iloc[0] if not df_mat.empty else "Acquis"
                pdf.cell(w_mat, 6, str(mat)[:30], 1, 0, "L")
                pdf.cell(w_comp, 6, str(eval_comp), 1, 0, "C")
                pdf.cell(w_app, 6, str(appr_str)[:35], 1, 1, "L")

    if cycle != "Préscolaire":
        moyenne = (total_points / total_coefs) if total_coefs > 0 else 0.0
        libelle_moy = f"MOYENNE GÉNÉRALE PONDÉRÉE : {moyenne:.2f} / 20"
        
        pdf.ln(3)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(95, 7, f"Total des Points : {total_points:.2f}", 1, 0, "L")
        pdf.cell(95, 7, f"Total des Coefficients : {total_coefs}", 1, 1, "L")
        
        pdf.set_fill_color(230, 242, 255)
        pdf.cell(190, 8, libelle_moy, 1, 1, "C", True)
    else:
        libelle_moy = "ÉVALUATION QUALITATIVE PAR COMPÉTENCES (SANS MOYENNE)"
        pdf.ln(3)
        pdf.set_font("Arial", "B", 10)
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

    if cycle == "Collège" or cycle == "Élémentaire":
        if moyenne >= 16: mention = "Très Bien (Félicitations du Conseil)"
        elif moyenne >= 14: mention = "Bien (Tableau d'Honneur)"
        elif moyenne >= 12: mention = "Assez Bien"
        elif moyenne >= 10: mention = "Passable"
        else: mention = "Insuffisant - Avertissement Travail"
    else:
        mention = "Évaluation formative validée"

    pdf.ln(3)
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 6, f"Appréciation Globale & Mention : {mention}", 0, 1, "L")

    pdf.ln(8)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(60, 6, "Le Professeur Principal", 0, 0, "C")
    pdf.cell(70, 6, "Les Parents", 0, 0, "C")
    pdf.cell(60, 6, "Le Directeur des Études", 0, 1, "C")

    return bytes(pdf.output())

def generer_bulletin_classe_pdf(classe_nom, trimestre_sel):
    pdf = PDFReport()
    eleves_classe = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_nom]
    
    if eleves_classe.empty:
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, f"Aucun élève trouvé dans la classe {classe_nom}", 0, 1, "C")
        return bytes(pdf.output())

    for idx, r_el in eleves_classe.iterrows():
        eleve_nom = r_el["Nom Complet"]
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
        elif cycle == "Élémentaire":
            w_mat, w_comp, w_coef, w_moy, w_app = 55, 30, 20, 30, 55
            pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
            pdf.cell(w_comp, 7, "Évaluation", 1, 0, "C", True)
            pdf.cell(w_coef, 7, "Coef", 1, 0, "C", True)
            pdf.cell(w_moy, 7, "Moy. /20", 1, 0, "C", True)
            pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)
        else:
            w_mat, w_comp, w_app = 70, 50, 70
            pdf.cell(w_mat, 7, "Domaine d'apprentissage", 1, 0, "C", True)
            pdf.cell(w_comp, 7, "Évaluation", 1, 0, "C", True)
            pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)

        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(0, 0, 0)

        total_points = 0.0
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

                    moy_mat = (((d1_val + d2_val) / 2.0) + comp_val) / 2.0
                    total_points += moy_mat * coef
                    total_coefs += coef

                    pdf.cell(w_mat, 6, str(mat)[:20], 1, 0, "L")
                    pdf.cell(w_d1, 6, d1_str, 1, 0, "C")
                    pdf.cell(w_d2, 6, d2_str, 1, 0, "C")
                    pdf.cell(w_comp, 6, comp_str, 1, 0, "C")
                    pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
                    pdf.cell(w_moy, 6, f"{moy_mat:.2f}", 1, 0, "C")
                    pdf.cell(w_app, 6, str(appr_str)[:25], 1, 1, "L")
                elif cycle == "Élémentaire":
                    coef = int(df_mat["Coefficient"].iloc[0]) if "Coefficient" in df_mat.columns and pd.notnull(df_mat["Coefficient"].iloc[0]) else 1
                    note_val = float(df_mat["Note"].iloc[0]) if not df_mat.empty and pd.notnull(df_mat["Note"].iloc[0]) else 0.0
                    bareme_val = float(df_mat["Barème"].iloc[0]) if "Barème" in df_mat.columns and pd.notnull(df_mat["Barème"].iloc[0]) and float(df_mat["Barème"].iloc[0]) > 0 else 20.0
                    
                    note_sur_20 = (note_val / bareme_val) * 20.0
                    total_points += note_sur_20 * coef
                    total_coefs += coef

                    pdf.cell(w_mat, 6, str(mat)[:25], 1, 0, "L")
                    pdf.cell(w_comp, 6, f"{note_val:.2f}/{bareme_val}", 1, 0, "C")
                    pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
                    pdf.cell(w_moy, 6, f"{note_sur_20:.2f}", 1, 0, "C")
                    pdf.cell(w_app, 6, str(appr_str)[:30], 1, 1, "L")
                else:
                    eval_comp = df_mat["Appréciation"].iloc[0] if not df_mat.empty else "Acquis"
                    pdf.cell(w_mat, 6, str(mat)[:30], 1, 0, "L")
                    pdf.cell(w_comp, 6, str(eval_comp), 1, 0, "C")
                    pdf.cell(w_app, 6, str(appr_str)[:35], 1, 1, "L")

        if cycle != "Préscolaire":
            moyenne = (total_points / total_coefs) if total_coefs > 0 else 0.0
            libelle_moy = f"MOYENNE GÉNÉRALE PONDÉRÉE : {moyenne:.2f} / 20"
            
            pdf.ln(3)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(95, 7, f"Total des Points : {total_points:.2f}", 1, 0, "L")
            pdf.cell(95, 7, f"Total des Coefficients : {total_coefs}", 1, 1, "L")
            
            pdf.set_fill_color(230, 242, 255)
            pdf.cell(190, 8, libelle_moy, 1, 1, "C", True)
        else:
            libelle_moy = "ÉVALUATION QUALITATIVE PAR COMPÉTENCES (SANS MOYENNE)"
            pdf.ln(3)
            pdf.set_font("Arial", "B", 10)
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

        if cycle == "Collège" or cycle == "Élémentaire":
            if moyenne >= 16: mention = "Très Bien (Félicitations du Conseil)"
            elif moyenne >= 14: mention = "Bien (Tableau d'Honneur)"
            elif moyenne >= 12: mention = "Assez Bien"
            elif moyenne >= 10: mention = "Passable"
            else: mention = "Insuffisant - Avertissement Travail"
        else:
            mention = "Évaluation formative validée"

        pdf.ln(3)
        pdf.set_font("Arial", "I", 10)
        pdf.cell(0, 6, f"Appréciation Globale & Mention : {mention}", 0, 1, "L")

        pdf.ln(8)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(60, 6, "Le Professeur Principal", 0, 0, "C")
        pdf.cell(70, 6, "Les Parents", 0, 0, "C")
        pdf.cell(60, 6, "Le Directeur des Études", 0, 1, "C")

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
        return "📝 Le système applique les règles spécifiques des cycles au Sénégal : Préscolaire, Élémentaire et Collège (coefficients paramétrables, barème et conversion automatique sur 20)."
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
                Sélectionnez votre espace. Le système intègre une Base Globale centralisant tout l'historique annuel avec tables relationnelles SQLite sécurisées.
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
                <p style="font-size: 0.85rem; color: #64748B;">Saisie des notes selon le système éducatif du Sénégal, fiches d'appel & base globale.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Consultation des bulletins en ligne selon les ordres d'enseignement.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Téléchargement PDF bulletins classe/élève, Base Globale & EDT.</p>
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
                    st.error("Identifiants incorrects. Veuillez vérifier votre nom, prénom et mot de passe.")
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
            "📝 Saisie de Notes",
            "📋 Fiche d'Appel", 
            "⚠️ Conduite", 
            "📖 Travail fait et à faire", 
            "📑 Cahier de texte"
        ], horizontal=True)

        if menu_prof == "📝 Saisie de Notes":
            st.markdown("### 📝 Saisie de Notes — Système Éducatif du Sénégal")
            st.info(f"📌 Classe assignée : **{classe_autorisee}**")

            row_cls_p = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe_autorisee]
            cycle_prof = row_cls_p["Cycle"].values[0] if not row_cls_p.empty else "Collège"

            st.markdown(f"**Ordre d'enseignement détecté :** {cycle_prof}")

            eleves_cls_list = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_autorisee]["Nom Complet"].tolist()

            if not eleves_cls_list:
                st.warning("Aucun élève trouvé dans cette classe pour effectuer la saisie des notes.")
            else:
                with st.form("form_saisie_notes_prof"):
                    eleve_selectionne = st.selectbox("Sélectionner l'élève", eleves_cls_list)
                    
                    if cycle_prof == "Préscolaire":
                        st.markdown("#### 🎨 Évaluation par Compétences (Préscolaire)")
                        st.caption("Aucune note chiffrée. Évaluation exclusivement basée sur les compétences officielles.")
                        
                        domaines_prescolaire = [
                            "Activités d'éveil et sensorielles",
                            "Langage oral / Communication",
                            "Graphisme / Pré-écriture",
                            "Activités mathématiques de base / Logique",
                            "Éducation artistique (Dessin, Chant, Modelage)"
                        ]
                        matiere_saisie = st.selectbox("Domaine d'apprentissage officiel", domaines_prescolaire)
                        trim_saisie = st.selectbox("Période", ["Premier Trimestre", "Deuxième Trimestre", "Troisième Trimestre"])
                        type_eval = "Évaluation formative par compétences"
                        coefficient_val = 1
                        bareme_val = 0
                        
                        echelle_competence = st.selectbox("Évaluation de la compétence", ["Acquis", "En cours d'acquisition", "Non acquis"])
                        note_val = 0.0
                        appreciation_val = echelle_competence

                    elif cycle_prof == "Élémentaire":
                        st.markdown("#### 📚 Saisie Élémentaire (CI, CP, CE1, CE2, CM1, CM2)")
                        matieres_elementaire_defaut = [
                            "Lecture", "Langue et Communication / Français", "Mathématiques", 
                            "Étude du Milieu", "Histoire-Géographie", "Éducation Civique et Morale", 
                            "Sciences d'Observation", "Éducation Artistique – Dessin et Chant", 
                            "Éducation Physique et Sportive – EPS", "Informatique", "Langues nationales"
                        ]
                        matiere_saisie = st.selectbox("Matière (Élémentaire)", matieres_elementaire_defaut)
                        trim_saisie = st.selectbox("Période", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
                        type_eval = st.selectbox("Type d'évaluation", ["Devoir", "Composition", "Interrogation"])
                        
                        coefficient_val = st.number_input("Coefficient (Paramétrable)", 1, 10, 2)
                        bareme_val = st.selectbox("Barème de notation", [10, 15, 20, 30, 40, 50, 100], index=2)
                        note_saisie_brute = st.number_input(f"Note obtenue (sur le barème de {bareme_val})", 0.0, float(bareme_val), 14.0, 0.5)
                        
                        if note_saisie_brute < 0 or note_saisie_brute > bareme_val:
                            st.error(f"Erreur : La note doit être comprise entre 0 et {bareme_val}.")
                        
                        # Conversion automatique sur 20 avant tout calcul
                        note_val = (note_saisie_brute / bareme_val) * 20.0 if bareme_val > 0 else note_saisie_brute
                        appreciation_val = st.text_input("Appréciation", value="Bon travail")

                    else:  # Collège
                        st.markdown("#### 📐 Saisie Collège (6e, 5e, 4e, 3e)")
                        matieres_college_defaut = [
                            "Français", "Mathématiques", "Anglais", "Histoire-Géographie", 
                            "Éducation Civique", "Sciences de la Vie et de la Terre – SVT", 
                            "Physique-Chimie", "Technologie", "Informatique", 
                            "Éducation Physique et Sportive – EPS", "Éducation Artistique", "Arabe / Langues"
                        ]
                        matiere_saisie = st.selectbox("Matière enseignée (Collège)", matieres_college_defaut)
                        trim_saisie = st.selectbox("Période (Collège)", ["1er Semestre", "2ème Semestre"])
                        type_eval = st.selectbox("Type d'évaluation", ["Devoir 1", "Devoir 2", "Composition"])
                        
                        coefficient_val = st.number_input("Coefficient", 1, 10, 3)
                        bareme_val = 20
                        
                        note_saisie_brute = st.number_input("Note obtenue (sur 20)", 0.0, 20.0, 14.0, 0.5)
                        if note_saisie_brute < 0 or note_saisie_brute > bareme_val:
                            st.error(f"Erreur : La note doit être comprise entre 0 et {bareme_val}.")
                        
                        note_val = note_saisie_brute
                        appreciation_val = st.text_input("Appréciation / Commentaire", value="Bon travail général")
                    
                    btn_valider_note = st.form_submit_button("Enregistrer la note")

                    if btn_valider_note:
                        if cycle_prof != "Préscolaire" and (note_saisie_brute < 0 or note_saisie_brute > bareme_val):
                            st.error("Saisie impossible : note hors barème.")
                        else:
                            nouvelle_ligne_note = pd.DataFrame([{
                                "Classe": classe_autorisee,
                                "Élève": eleve_selectionne,
                                "Matière": matiere_saisie,
                                "Type Évaluation": type_eval,
                                "Coefficient": coefficient_val,
                                "Note": note_val,
                                "Barème": bareme_val if cycle_prof != "Préscolaire" else 0,
                                "Trimestre": trim_saisie,
                                "Appréciation": appreciation_val
                            }])
                            
                            st.session_state.notes_db = pd.concat([st.session_state.notes_db, nouvelle_ligne_note], ignore_index=True)

                            mois_actuel = datetime.today().strftime("%B")
                            bg_note_entry = pd.DataFrame([{
                                "Date": str(datetime.today().date()),
                                "Année": "2025-2026",
                                "Trimestre": trim_saisie,
                                "Mois": mois_actuel,
                                "Type Acteur": "Élève",
                                "Nom Acteur": eleve_selectionne,
                                "Classe": classe_autorisee,
                                "Type Entrée": "Note",
                                "Détail / Contenu": f"{matiere_saisie} ({type_eval}): {note_val if cycle_prof != 'Préscolaire' else appreciation_val}",
                                "Appréciation": appreciation_val
                            }])
                            st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, bg_note_entry], ignore_index=True)
                            
                            sauvegarder_donnees_externes()
                            st.success(f"Note enregistrée avec succès pour {eleve_selectionne} et synchronisée dans la Base Globale !")

        elif menu_prof == "📋 Fiche d'Appel":
            st.markdown("### Feuille d'Appel Journalière")
            st.info(f"📌 Classe assignée (accès restreint) : **{classe_autorisee}**")
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

        elif menu_prof == "⚠️ Conduite":
            st.markdown("### Suivi de Conduite")
            st.info(f"📌 Classe assignée (accès restreint) : **{classe_autorisee}**")
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
            st.info(f"📌 Classe assignée (accès restreint) : **{classe_autorisee}**")
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
            st.info(f"📌 Classe assignée (accès restreint) : **{classe_autorisee}**")
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
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Portail Parent & Élève (Système Sénégalais)</div>', unsafe_allow_html=True)

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

        st.success(f"Connecté pour l'élève : **{eleve}** (Classe : {classe} - Cycle : {cycle_eleve})")
        if st.button("Se déconnecter"):
            st.session_state["parent_logged_eleve"] = ""
            st.rerun()

        st.markdown("---")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Bulletin & Notes", "📅 Emploi du Temps", "📉 Absences", "⚠️ Conduite", "📖 Travail fait et à faire", "🪪 Carte Scolaire"])
        
        with t1:
            st.subheader("Bulletin de Notes Officiel (Consultation en ligne - Espace Parents)")
            if cycle_eleve == "Collège":
                tri_p = st.selectbox("Sélectionner la Période", ["1er Semestre", "2ème Semestre"])
            elif cycle_eleve == "Élémentaire":
                tri_p = st.selectbox("Sélectionner la Période", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
            else:
                tri_p = st.selectbox("Sélectionner la Période", ["Premier Trimestre", "Deuxième Trimestre", "Troisième Trimestre"])
            
            notes_el = st.session_state.notes_db[
                (st.session_state.notes_db["Élève"] == eleve) & 
                (st.session_state.notes_db["Trimestre"] == tri_p)
            ]

            if not notes_el.empty:
                if cycle_eleve != "Préscolaire":
                    st.dataframe(notes_el[["Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Appréciation"]], use_container_width=True)
                    total_pts = 0.0
                    total_coef = 0
                    for _, r in notes_el.iterrows():
                        n_val = float(r["Note"]) if pd.notnull(r["Note"]) else 0.0
                        c_val = int(r["Coefficient"]) if pd.notnull(r["Coefficient"]) else 1
                        total_pts += n_val * c_val
                        total_coef += c_val
                    if total_coef > 0:
                        moy = total_pts / total_coef
                        st.markdown(f"### 🎯 Moyenne générale pondérée : **{moy:.2f} / 20**")
                else:
                    st.dataframe(notes_el[["Matière", "Type Évaluation", "Appréciation"]], use_container_width=True)
                    st.markdown("### 🎨 Évaluation qualitative par compétences (Pas de moyenne au préscolaire)")
            else:
                st.info(f"Aucune note enregistrée pour le {tri_p}.")

        with t2:
            st.subheader("Emploi du Temps de la Classe & Documents Interactifs")
            grid_edt = get_or_create_edt(classe)
            st.dataframe(grid_edt, use_container_width=True)

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
                    st.success(f"Accès accordé en tant que **{role_connecte}** !")
                    st.rerun()
                else:
                    st.error("Identifiants erronés. Veuillez vérifier votre email et mot de passe.")
    else:
        role_actuel = st.session_state.get("admin_role_connecte", "Administrateur")
        st.success(f"Mode {role_actuel} Activé — Gestion Centralisée Complète.")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "📥 Téléchargement Bulletins PDF (Classe & Élève)",
            "☁️ Sauvegarde & Restauration Cloud (Anti-Effacement)",
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

        if adm_tab == "📥 Téléchargement Bulletins PDF (Classe & Élève)":
            st.subheader("📥 Téléchargement des Bulletins en PDF")
            classes_liste_adm = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
            if classes_liste_adm:
                classe_choisie_adm = st.selectbox("Sélectionner la classe", classes_liste_adm, key="sel_cls_bulletin_adm")
                row_c_adm = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe_choisie_adm]
                cyc_adm = row_c_adm["Cycle"].values[0] if not row_c_adm.empty else "Collège"

                if cyc_adm == "Collège":
                    trim_choisi_adm = st.selectbox("Période", ["1er Semestre", "2ème Semestre"], key="trim_adm_col")
                elif cyc_adm == "Élémentaire":
                    trim_choisi_adm = st.selectbox("Période", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"], key="trim_adm_elem")
                else:
                    trim_choisi_adm = st.selectbox("Période", ["Premier Trimestre", "Deuxième Trimestre", "Troisième Trimestre"], key="trim_adm_pres")

                col_dl_c1, col_dl_c2 = st.columns(2)
                with col_dl_c1:
                    if st.button("Générer PDF toute la classe"):
                        pdf_classe_bytes = generer_bulletin_classe_pdf(classe_choisie_adm, trim_choisi_adm)
                        st.download_button(label=f"📥 Télécharger Bulletin Global ({classe_choisie_adm}) .pdf", data=pdf_classe_bytes, file_name=f"bulletins_classe_{classe_choisie_adm.lower()}.pdf", mime="application/pdf")
                with col_dl_c2:
                    eleves_de_la_classe = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_choisie_adm]["Nom Complet"].tolist()
                    if eleves_de_la_classe:
                        eleve_choisi_adm = st.selectbox("Sélectionner l'élève", eleves_de_la_classe, key="sel_eleve_bulletin_adm")
                        if st.button("Générer PDF pour cet élève"):
                            pdf_eleve_bytes = generer_bulletin_pdf(eleve_choisi_adm, classe_choisie_adm, trim_choisi_adm)
                            st.download_button(label=f"📥 Télécharger Bulletin ({eleve_choisi_adm}) .pdf", data=pdf_eleve_bytes, file_name=f"bulletin_{eleve_choisi_adm.lower()}.pdf", mime="application/pdf")

        elif adm_tab == "☁️ Sauvegarde & Restauration Cloud (Anti-Effacement)":
            st.subheader("☁️ Sauvegarde & Restauration de la Base de Données")
            if os.path.exists(DB_FILE):
                with open(DB_FILE, "rb") as f:
                    db_bytes = f.read()
                st.download_button(label="📥 Télécharger la base SQLite (.db)", data=db_bytes, file_name="cpnm_database.db", mime="application/octet-stream")
            
            uploaded_db = st.file_uploader("Restaurer une base de données SQLite (.db)", type=["db"])
            if uploaded_db is not None:
                with open(DB_FILE, "wb") as f:
                    f.write(uploaded_db.getbuffer())
                st.success("Base de données restaurée avec succès ! Veuillez recharger la page.")

        elif adm_tab == "🛡️ Gestionnaires & Propriétaires (Liste Blanche)":
            st.subheader("Gestion des Accès Administratifs Avancés")
            st.dataframe(st.session_state.gestionnaires_proprietaires_db, use_container_width=True)
            with st.form("form_add_gp"):
                gp_nom = st.text_input("Nom")
                gp_prenom = st.text_input("Prénom")
                gp_email = st.text_input("Email")
                gp_pass = st.text_input("Mot de passe", type="password")
                gp_role = st.selectbox("Rôle", ["Gestionnaire", "Propriétaire", "Administrateur Adjoint"])
                if st.form_submit_button("Ajouter le compte"):
                    if gp_email and gp_pass:
                        new_row = pd.DataFrame([{"Nom": gp_nom, "Prénom": gp_prenom, "Email": gp_email, "Mot de passe": gp_pass, "Rôle": gp_role}])
                        st.session_state.gestionnaires_proprietaires_db = pd.concat([st.session_state.gestionnaires_proprietaires_db, new_row], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Compte ajouté avec succès.")

        elif adm_tab == "📊 Liste & Classement des Élèves (Par Classe & Niveau)":
            st.subheader("Liste et Classement des Élèves par Classe")
            cls_sel_cl = st.selectbox("Sélectionner la classe pour classement", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else [])
            if cls_sel_cl:
                el_cls = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_sel_cl]
                st.dataframe(el_cls, use_container_width=True)

        elif adm_tab == "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel":
            st.subheader("Base Globale Centralisée (Historique Complet)")
            st.dataframe(st.session_state.base_globale_db, use_container_width=True)
            if st.button("📥 Exporter la Base Globale en Excel"):
                excel_bytes = export_table_excel(st.session_state.base_globale_db)
                st.download_button("Télécharger Excel", data=excel_bytes, file_name="base_globale_cpnm.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        elif adm_tab == "🤖 Assistant IA Administration":
            st.subheader("Assistant IA Pédagogique et Administratif")
            question_ia = st.text_input("Posez votre question à l'IA :")
            if question_ia:
                reponse = assistant_ia_repondre(question_ia)
                st.markdown(reponse)

        elif adm_tab == "📅 Emploi du Temps Interactif & Documents":
            st.subheader("Gestion des Emplois du Temps")
            cls_edt = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else [])
            if cls_edt:
                grid = get_or_create_edt(cls_edt)
                edited_grid = st.data_editor(grid, use_container_width=True)
                if st.button("Enregistrer l'emploi du temps"):
                    st.session_state.edt_grid_db[cls_edt] = edited_grid
                    sauvegarder_donnees_externes()
                    st.success("Emploi du temps mis à jour avec succès.")

        elif adm_tab == "👨‍🎓 Élèves (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Élèves")
            st.dataframe(st.session_state.eleves_db, use_container_width=True)
            with st.form("form_add_eleve"):
                p_el = st.text_input("Prénom")
                n_el = st.text_input("Nom")
                dt_el = st.date_input("Date de naissance")
                c_el = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else [])
                if st.form_submit_button("Ajouter l'élève"):
                    if p_el and n_el and c_el:
                        nc = f"{p_el} {n_el}"
                        new_el = pd.DataFrame([{"Nom Complet": nc, "Prénom": p_el, "Nom": n_el, "Date de Naissance": str(dt_el), "Classe": c_el, "Photo": None}])
                        st.session_state.eleves_db = pd.concat([st.session_state.eleves_db, new_el], ignore_index=True)
                        st.session_state.eleves_db = st.session_state.eleves_db.sort_values(by="Nom").reset_index(drop=True)
                        sauvegarder_donnees_externes()
                        st.success("Élève ajouté avec succès.")

        elif adm_tab == "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Professeurs")
            st.dataframe(st.session_state.prof_credentials, use_container_width=True)
            with st.form("form_add_prof"):
                p_pr = st.text_input("Prénom Prof")
                n_pr = st.text_input("Nom Prof")
                mat_pr = st.text_input("Matière Principale")
                cls_pr = st.selectbox("Classe Attribuée", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else [])
                pw_pr = st.text_input("Mot de passe", type="password")
                if st.form_submit_button("Ajouter le professeur"):
                    if p_pr and n_pr and pw_pr:
                        new_p = pd.DataFrame([{"Nom": n_pr, "Prénom": p_pr, "Mot de passe": pw_pr, "Matière Principale": mat_pr, "Classe Attribuée": cls_pr}])
                        st.session_state.prof_credentials = pd.concat([st.session_state.prof_credentials, new_p], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Professeur ajouté avec succès.")

        elif adm_tab == "🏫 Gestion des classes et cycles":
            st.subheader("Gestion des Classes et Cycles (Préscolaire, Élémentaire, Collège)")
            st.dataframe(st.session_state.classes_db, use_container_width=True)
            with st.form("form_add_classe"):
                nom_cls = st.text_input("Nom de la Classe (ex: 6ème A, CP, Grande Section)")
                cycle_cls = st.selectbox("Cycle d'enseignement", ["Préscolaire", "Élémentaire", "Collège"])
                prof_resp = st.text_input("Professeur Responsable / Maître(sse)")
                if st.form_submit_button("Créer la classe"):
                    if nom_cls:
                        new_c = pd.DataFrame([{"Classe": nom_cls, "Cycle": cycle_cls, "Professeur Responsable": prof_resp}])
                        st.session_state.classes_db = pd.concat([st.session_state.classes_db, new_c], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Classe créée avec succès.")

        elif adm_tab == "📋 Listes blanches des parents":
            st.subheader("Listes Blanches des Parents (Accès Portail)")
            st.dataframe(st.session_state.parents_white_list, use_container_width=True)
            with st.form("form_add_pw"):
                tel_pw = st.text_input("Téléphone Parent (+221...)")
                p_el_pw = st.text_input("Prénom Élève")
                n_el_pw = st.text_input("Nom Élève")
                an_pw = st.number_input("Année Naissance Élève", 2005, 2024, 2012)
                cls_pw = st.selectbox("Classe Élève", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else [])
                if st.form_submit_button("Autoriser le parent"):
                    if tel_pw and p_el_pw:
                        new_pw = pd.DataFrame([{"Téléphone": tel_pw, "Prénom Élève": p_el_pw, "Nom Élève": n_el_pw, "Année Naissance": int(an_pw), "Classe": cls_pw}])
                        st.session_state.parents_white_list = pd.concat([st.session_state.parents_white_list, new_pw], ignore_index=True)
                        sauvegarder_donnees_externes()
                        st.success("Accès parent autorisé.")

        elif adm_tab == "📑 Rapport journalier":
            st.subheader("Rapports Journaliers Transmis par les Professeurs")
            st.dataframe(st.session_state.rapports_journaliers_prof, use_container_width=True)

elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Rapports Globaux & Statistiques de l\'Établissement</div>', unsafe_allow_html=True)
    st.info("Consultez et téléchargez le rapport général consolidé de l'École Président Nelson Mandela.")
    
    if st.button("📥 Télécharger le Rapport Général Consolidé (PDF)"):
        pdf_rep_bytes = generer_rapport_general_pdf()
        st.download_button("Télécharger Rapport PDF", data=pdf_rep_bytes, file_name="rapport_general_cpnm.pdf", mime="application/pdf")
