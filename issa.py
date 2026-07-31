import base64
from datetime import datetime
import io
import os
import urllib.request
import sqlite3
from fpdf import FPDF
import pandas as pd
import streamlit as st

# ==========================================
# 0. GESTION DU CHIFFREMENT DES MOTS DE PASSE (SÉCURITÉ PRODUCTION)
# ==========================================
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    import hashlib
    HAS_BCRYPT = False

def hacher_mot_de_passe(password: str) -> str:
    """Hache un mot de passe avec bcrypt ou hashlib en fallback."""
    if not password:
        return ""
    if HAS_BCRYPT:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    else:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verifier_mot_de_passe(password: str, hashed: str) -> bool:
    """Vérifie un mot de passe par rapport à son hachage."""
    if not password or not hashed:
        return False
    if HAS_BCRYPT:
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except ValueError:
            return password == hashed
    else:
        return hashlib.sha256(password.encode('utf-8')).hexdigest() == hashed or password == hashed


# ==========================================
# 0. BIS. GESTION DE LA BASE DE DONNÉES SQLITE EXTERNE
# ==========================================
DB_DIR = "/tmp" if os.path.exists("/tmp") else "."
DB_NAME = os.path.join(DB_DIR, "ecole_nelson_mandela.db")

def obtenir_connexion():
    return sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)

def initialiser_base_de_donnees_externe():
    connexion = obtenir_connexion()
    cursor = connexion.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS eleves (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom_complet TEXT,
            date_naissance TEXT,
            classe TEXT,
            photo TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            classe TEXT,
            cycle TEXT,
            professeur_responsable TEXT
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
            bareme REAL,
            trimestre TEXT,
            appreciation TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS base_globale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            annee TEXT,
            trimestre TEXT,
            mois TEXT,
            type_acteur TEXT,
            nom_acteur TEXT,
            classe TEXT,
            type_entree TEXT,
            detail TEXT,
            appreciation TEXT
        )
    """)

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prof_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT,
            prenom TEXT,
            mot_de_passe TEXT,
            matiere_principale TEXT,
            classe_attribuee TEXT
        )
    ''')

    cursor.execute("SELECT COUNT(*) FROM eleves")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO eleves (nom_complet, date_naissance, classe, photo) VALUES (?, ?, ?, ?)", [
            ("Mamadou Diallo", "2012-05-14", "6ème A", None),
            ("Fatou Sow", "2015-08-20", "CP", None),
            ("Aminata Ba", "2013-02-10", "6ème A", None),
            ("Oumar Sy", "2011-11-03", "5ème A", None)
        ])

    cursor.execute("SELECT COUNT(*) FROM classes")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO classes (classe, cycle, professeur_responsable) VALUES (?, ?, ?)", [
            ("6ème A", "Collège", "Ibrahima Diallo"),
            ("5ème A", "Collège", "Cheikh Ndiaye"),
            ("CP", "Élémentaire", "Aissatou Sow"),
            ("Grande Section", "Préscolaire", "Marie Faye"),
            ("CE1", "Élémentaire", "Ousmane Diop")
        ])
        
    cursor.execute("SELECT COUNT(*) FROM prof_credentials")
    if cursor.fetchone()[0] == 0:
        try:
            cursor.executemany("""
                INSERT INTO prof_credentials (nom, prenom, mot_de_passe, matiere_principale, classe_attribuee) 
                VALUES (?, ?, ?, ?, ?)
            """, [
                ("Diallo", "Ibrahima", hacher_mot_de_passe("prof123"), "Mathématiques", "6ème A"),
                ("Sow", "Aissatou", hacher_mot_de_passe("prof456"), "Français", "CP"),
                ("Ndiaye", "Cheikh", hacher_mot_de_passe("prof789"), "Histoire-Géographie", "5ème A")
            ])
        except sqlite3.OperationalError as e:
            print(f"Erreur lors de l'insertion : {e}")

    cursor.execute("SELECT COUNT(*) FROM notes")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO notes (classe, eleve, matiere, type_evaluation, coefficient, note, bareme, trimestre, appreciation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("6ème A", "Mamadou Diallo", "Mathématiques", "Devoir 1", 3, 15.5, 20, "1er Semestre", "Très bon travail."),
            ("6ème A", "Mamadou Diallo", "Mathématiques", "Devoir 2", 3, 14.0, 20, "1er Semestre", "Bon ensemble."),
            ("6ème A", "Mamadou Diallo", "Mathématiques", "Composition", 3, 16.0, 20, "1er Semestre", "Excellent."),
            ("6ème A", "Mamadou Diallo", "Français", "Devoir 1", 3, 13.0, 20, "1er Semestre", "Assez bon."),
            ("6ème A", "Mamadou Diallo", "Français", "Devoir 2", 3, 14.5, 20, "1er Semestre", "Bon travail."),
            ("6ème A", "Mamadou Diallo", "Français", "Composition", 3, 15.0, 20, "1er Semestre", "Très bien."),
            ("CP", "Fatou Sow", "Graphisme / Écriture", "Composition", 1, 8.5, 10, "1er Trimestre", "Très bien.")
        ])

    cursor.execute("SELECT COUNT(*) FROM base_globale")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO base_globale (date, annee, trimestre, mois, type_acteur, nom_acteur, classe, type_entree, detail, appreciation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", [
            ("2026-01-15", "2025-2026", "1er Semestre", "Janvier", "Élève", "Mamadou Diallo", "6ème A", "Note", "Mathématiques (Devoir 1): 15.5/20", "Très bon travail"),
            ("2026-01-20", "2025-2026", "1er Semestre", "Janvier", "Élève", "Aminata Ba", "6ème A", "Absence", "Absent - Motif: Maladie", "Justifié"),
            ("2026-02-05", "2025-2026", "2ème Semestre", "Février", "Professeur", "Ibrahima Diallo", "6ème A", "Rapport Cours", "Algèbre - Chapitre 3 terminé", "Excellente progression")
        ])

    connexion.commit()
    connexion.close()

initialiser_base_de_donnees_externe()

# ==========================================
# 0. TER. GESTION DES POLICES UNICODE
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
# 1. CONFIGURATION DE LA PAGE & DESIGN
# ==========================================
st.set_page_config(
    page_title="Portail Pédagogique - Cours Privé Nelson Mandela | Sénégal",
    page_icon="🇸🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ADMIN_WHITELIST = ["admin", "superadmin", "directeur@ecole.com", "cpnm@gmail.com"]

st.markdown(
    """
    <style>
    .main { background-color: #F8FAFC; }
    .header-ecole { color: #1E3A8A; font-size: clamp(1.8rem, 4vw, 2.8rem); font-weight: 900; text-align: center; margin-bottom: 5px; text-transform: uppercase; letter-spacing: 1px; padding: 0 10px; }
    .sub-header { color: #047857; font-size: clamp(0.9rem, 2vw, 1.2rem); font-weight: 700; text-align: center; margin-bottom: 25px; padding: 0 10px; }
    .animated-card { border: 2px solid #E2E8F0; padding: clamp(15px, 3vw, 25px); border-radius: 16px; background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%); box-shadow: 0 10px 25px rgba(0,0,0,0.05); text-align: center; cursor: pointer; margin-bottom: 15px; height: 100%; }
    .kpi-card-animated { border-left: 5px solid #2563EB; background: #FFFFFF; padding: 15px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; }
    .stButton>button { background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); color: white; border-radius: 8px; font-weight: bold; border: none; padding: 0.75rem 1rem; width: 100%; min-height: 44px; font-size: 1rem; }
    </style>
""",
    unsafe_allow_html=True,
)

# ==========================================
# 2. CHARGEMENT SÉCURISÉ DES DONNÉES
# ==========================================
def charger_donnees_externes():
    initialiser_base_de_donnees_externe()
    conn = obtenir_connexion()
    try:
        st.session_state.eleves_db = pd.read_sql("SELECT nom_complet as 'Nom Complet', date_naissance as 'Date de Naissance', classe as 'Classe', photo as 'Photo' FROM eleves", conn)
    except Exception:
        st.session_state.eleves_db = pd.DataFrame(columns=["Nom Complet", "Date de Naissance", "Classe", "Photo"])

    try:
        st.session_state.classes_db = pd.read_sql("SELECT classe as 'Classe', cycle as 'Cycle', professeur_responsable as 'Professeur Responsable' FROM classes", conn)
    except Exception:
        st.session_state.classes_db = pd.DataFrame(columns=["Classe", "Cycle", "Professeur Responsable"])

    try:
        st.session_state.notes_db = pd.read_sql("SELECT classe as 'Classe', eleve as 'Élève', matiere as 'Matière', type_evaluation as 'Type Évaluation', coefficient as 'Coefficient', note as 'Note', bareme as 'Barème', trimestre as 'Trimestre', appreciation as 'Appréciation' FROM notes", conn)
    except Exception:
        st.session_state.notes_db = pd.DataFrame(columns=["Classe", "Élève", "Matière", "Type Évaluation", "Coefficient", "Note", "Barème", "Trimestre", "Appréciation"])

    try:
        st.session_state.base_globale_db = pd.read_sql("SELECT date as 'Date', annee as 'Année', trimestre as 'Trimestre', mois as 'Mois', type_acteur as 'Type Acteur', nom_acteur as 'Nom Acteur', classe as 'Classe', type_entree as 'Type Entrée', detail as 'Détail / Contenu', appreciation as 'Appréciation' FROM base_globale", conn)
    except Exception:
        st.session_state.base_globale_db = pd.DataFrame(columns=["Date", "Année", "Trimestre", "Mois", "Type Acteur", "Nom Acteur", "Classe", "Type Entrée", "Détail / Contenu", "Appréciation"])

    try:
        st.session_state.prof_credentials = pd.read_sql("SELECT nom as 'Nom', prenom as 'Prénom', mot_de_passe as 'Mot de passe', matiere_principale as 'Matière Principale', classe_attribuee as 'Classe Attribuée' FROM prof_credentials", conn)
    except Exception:
        st.session_state.prof_credentials = pd.DataFrame(columns=["Nom", "Prénom", "Mot de passe", "Matière Principale", "Classe Attribuée"])
    finally:
        conn.close()

if "espace_actif" not in st.session_state:
   st.session_state.espace_actif = "🏠 Accueil"

if "authenticated_admin" not in st.session_state:
   st.session_state.authenticated_admin = False

if "admin_credentials" not in st.session_state:
   st.session_state.admin_credentials = pd.DataFrame([
        {"Nom": "Admin", "Prénom": "Principal", "Email": "cpnm@gmail.com", "Mot de passe": hacher_mot_de_passe("cpnm2026")}
    ])

if "gestionnaires_proprietaires_db" not in st.session_state:
   st.session_state.gestionnaires_proprietaires_db = pd.DataFrame([
        {"Nom": "Mandela", "Prénom": "Propriétaire", "Email": "proprio@cpnm.sn", "Mot de passe": hacher_mot_de_passe("proprio2026"), "Rôle": "Propriétaire"},
        {"Nom": "Diop", "Prénom": "Gestionnaire", "Email": "gestion@cpnm.sn", "Mot de passe": hacher_mot_de_passe("gestion2026"), "Rôle": "Gestionnaire"}
    ])

if "parents_white_list" not in st.session_state:
   st.session_state.parents_white_list = pd.DataFrame([
        {"Téléphone": "+221771234567", "Prénom Élève": "Mamadou", "Nom Élève": "Diallo", "Année Naissance": 2012, "Classe": "6ème A"},
        {"Téléphone": "+221769876543", "Prénom Élève": "Fatou", "Nom Élève": "Sow", "Année Naissance": 2015, "Classe": "CP"},
    ])

charger_donnees_externes()

JOURS_LIST = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
HEURES_LIST = ["08h-09h", "09h-10h", "10h-11h", "11h-12h", "15h-16h", "16h-17h"]

if "edt_grid_db" not in st.session_state:
   st.session_state.edt_grid_db = {}

def get_or_create_edt(classe):
    if classe not in st.session_state.edt_grid_db:
        st.session_state.edt_grid_db[classe] = pd.DataFrame("", index=JOURS_LIST, columns=HEURES_LIST)
    return st.session_state.edt_grid_db[classe]

if "cahier_textes" not in st.session_state:
   st.session_state.cahier_textes = pd.DataFrame(
        columns=["Professeur", "Date", "Classe", "Matière", "Contenu", "Travail à faire"],
        data=[["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Introduction aux nombres relatifs.", "Exercices 1 et 2 page 45."]]
    )

if "rapports_journaliers_prof" not in st.session_state:
   st.session_state.rapports_journaliers_prof = pd.DataFrame(
        columns=["Professeur", "Date", "Classe", "Matière", "Bilan du Cours", "Difficultés / Remarques"],
        data=[["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Bonne participation globale des élèves.", "Quelques difficultés sur les soustractions de négatifs."]]
    )

if "absences_db" not in st.session_state:
   st.session_state.absences_db = pd.DataFrame(
        columns=["Date", "Classe", "Élève", "Statut", "Motif"],
        data=[["2026-06-01", "6ème A", "Aminata Ba", "Absent", "Maladie"]]
    )

if "matieres_def" not in st.session_state:
   st.session_state.matieres_def = pd.DataFrame([
        {"Matière": "Mathématiques", "Coefficient": 3, "Cycle": "Collège"},
        {"Matière": "Français", "Coefficient": 3, "Cycle": "Collège"},
        {"Matière": "Histoire-Géographie", "Coefficient": 2, "Cycle": "Collège"},
        {"Matière": "SVT", "Coefficient": 2, "Cycle": "Collège"},
        {"Matière": "Anglais", "Coefficient": 2, "Cycle": "Collège"},
        {"Matière": "Lecture / Langage", "Coefficient": 2, "Cycle": "Élémentaire"},
        {"Matière": "Calcul / Mathématiques", "Coefficient": 2, "Cycle": "Élémentaire"},
        {"Matière": "Éveil / Science", "Coefficient": 1, "Cycle": "Élémentaire"},
        {"Matière": "Activités Sensorielles", "Coefficient": 1, "Cycle": "Préscolaire"},
        {"Matière": "Graphisme / Dessin", "Coefficient": 1, "Cycle": "Préscolaire"}
    ])

if "conduite_db" not in st.session_state:
   st.session_state.conduite_db = pd.DataFrame(
        columns=["Classe", "Élève", "Date", "Type", "Description"],
        data=[["6ème A", "Mamadou Diallo", "2026-06-02", "Encouragement", "Participation active en classe."]]
    )

# ==========================================
# 3. FONCTIONS UTILITAIRES & GÉNÉRATION PDF
# ==========================================
class PDFReport(FPDF):
   def header(self):
        self.set_font("Arial", "B", 14)
        self.cell(0, 8, "COURS PRIVÉ NELSON MANDELA - SÉNÉGAL", 0, 1, "C")
        self.set_font("Arial", "I", 9)
        self.cell(0, 5, "Excellence - Discipline - Ancrage Culturel", 0, 1, "C")
        self.line(10, 25, 200, 25)
        self.ln(8)

   def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()} - Document Officiel CPNM Généré le {datetime.now().strftime('%d/%m/%Y')}", 0, 0, "C")

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

def exporter_emploi_du_temps_pdf(classe_nom, grid_df):
    pdf = PDFReport()
    pdf.add_page(orientation='L')
    use_dejavu = os.path.exists("DejaVuSans.ttf")
    font_main = "DejaVu" if use_dejavu else "Arial"
    if use_dejavu:
        pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
    pdf.set_font(font_main, "B", 14)
    pdf.cell(0, 8, f"EMPLOI DU TEMPS OFFICIEL - CLASSE DE {classe_nom.upper()}", 0, 1, "C")
    pdf.ln(5)
    pdf.set_font(font_main, "B", 10)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    col_w = 270 / (len(grid_df.columns) + 1)
    pdf.cell(col_w, 8, "Jours / Heures", 1, 0, "C", True)
    for col in grid_df.columns:
        pdf.cell(col_w, 8, str(col), 1, 0, "C", True)
    pdf.ln()
    pdf.set_font(font_main, "", 9)
    pdf.set_text_color(0, 0, 0)
    fill = False
    pdf.set_fill_color(240, 244, 248)
    for jour, row in grid_df.iterrows():
        pdf.cell(col_w, 8, str(jour), 1, 0, "C", True)
        for col in grid_df.columns:
            val = str(row[col]) if pd.notnull(row[col]) else ""
            if not use_dejavu:
                val = val.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(col_w, 8, val[:20], 1, 0, "C", fill)
        pdf.ln()
        fill = not fill
    return bytes(pdf.output())

def export_table_excel(df, columns_to_show=None):
    df_sub = df[columns_to_show] if columns_to_show else df
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_sub.to_excel(writer, index=False, sheet_name='Donnees')
    return output.getvalue()

def generer_bulletin_pdf(eleve_nom, classe_nom, trimestre_sel):
    pdf = PDFReport()
    pdf.add_page()
    row_cls = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe_nom]
    cycle = row_cls["Cycle"].values[0] if not row_cls.empty else "Collège"
    bareme = 10 if cycle in ["Préscolaire", "Élémentaire"] else 20
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, f"BULLETIN DE NOTES ET BILAN GLOBAL - {trimestre_sel.upper()}", 0, 1, "C")
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(100, 6, f"Élève : {eleve_nom}", 0, 0, "L")
    pdf.cell(90, 6, f"Classe : {classe_nom} ({cycle})", 0, 1, "R")
    pdf.ln(5)
    df_n = st.session_state.notes_db[(st.session_state.notes_db["Élève"] == eleve_nom) & (st.session_state.notes_db["Trimestre"] == trimestre_sel)]
    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    w_mat, w_comp, w_coef, w_moy, w_app = 55, 30, 20, 25, 60
    pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
    pdf.cell(w_comp, 7, "Composition", 1, 0, "C", True)
    pdf.cell(w_coef, 7, "Coef", 1, 0, "C", True)
    pdf.cell(w_moy, 7, f"Note /{bareme}", 1, 0, "C", True)
    pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)
    total_points, total_coefs = 0.0, 0
    if not df_n.empty:
        for mat in df_n["Matière"].unique():
            df_mat = df_n[df_n["Matière"] == mat]
            coef = int(df_mat["Coefficient"].iloc[0])
            appr_str = df_mat["Appréciation"].iloc[-1] if not df_mat.empty else "Bon ensemble"
            note_comp = df_mat[df_mat["Type Évaluation"].str.contains("Composition|Devoir", case=False, na=False)]["Note"].values
            moy_mat = note_comp[0] if len(note_comp) > 0 else 0.0
            total_points += moy_mat * coef
            total_coefs += coef
            pdf.cell(w_mat, 6, str(mat)[:25], 1, 0, "L")
            pdf.cell(w_comp, 6, f"{moy_mat:.2f}", 1, 0, "C")
            pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
            pdf.cell(w_moy, 6, f"{moy_mat:.2f}", 1, 0, "C")
            pdf.cell(w_app, 6, str(appr_str)[:30], 1, 1, "L")
    moyenne = (total_points / total_coefs) if total_coefs > 0 else 0.0
    pdf.ln(3)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(190, 8, f"MOYENNE GÉNÉRALE : {moyenne:.2f} / {bareme}", 1, 1, "C", True)
    return bytes(pdf.output())

def generer_rapport_general_pdf():
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "RAPPORT GÉNÉRAL & CONSOLIDATION ANNUELLE", 0, 1, "C")
    pdf.ln(6)
    pdf.set_font("Arial", "B", 11)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 7, "1. STATISTIQUES GÉNÉRALES DE L'ÉTABLISSEMENT", 1, 1, "L", True)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 6, f"Total Élèves Inscrits : {len(st.session_state.eleves_db)}", 1, 0, "L")
    pdf.cell(95, 6, f"Total Classes Actives : {len(st.session_state.classes_db)}", 1, 1, "L")
    pdf.cell(95, 6, f"Corps Enseignant : {len(st.session_state.prof_credentials)} professeurs", 1, 0, "L")
    pdf.cell(95, 6, f"Total Entrées Base Globale : {len(st.session_state.base_globale_db)}", 1, 1, "L")
    return bytes(pdf.output())

def assistant_ia_repondre(question):
    q = question.lower()
    if "élève" in q or "effectif" in q:
        return f"📊 L'établissement compte **{len(st.session_state.eleves_db)} élèves** et **{len(st.session_state.classes_db)} classes**."
    elif "professeur" in q or "prof" in q:
        return f"👨‍🏫 Nous avons **{len(st.session_state.prof_credentials)} professeurs** enregistrés."
    else:
        return "🤖 **IA Administration Nelson Mandela :** Posez vos questions sur les effectifs, notes ou rapports."

# ==========================================
# 4. EN-TÊTE ET NAVIGATION GLOBALE
# ==========================================
st.markdown('<div class="header-ecole">🦁 Cours Privé Nelson Mandela</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Excellence, Discipline et Ancrage Culturel au Cœur du Sénégal</div>', unsafe_allow_html=True)

if st.session_state.espace_actif != "🏠 Accueil":
    col_ret1, _ = st.columns([1, 5])
    with col_ret1:
        if st.button("⬅️ Retour Accueil"):
            st.session_state.espace_actif = "🏠 Accueil"
            st.rerun()
    st.markdown("---")

# ==========================================
# 5. ACCUEIL
# ==========================================
if st.session_state.espace_actif == "🏠 Accueil":
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="animated-card"><h1>👨‍🏫</h1><h3>Espace Professeurs</h3></div>', unsafe_allow_html=True)
        if st.button("Accéder Professeur", key="btn_p"):
            st.session_state.espace_actif = "👨‍🏫 Espace Professeurs / Maîtres"
            st.rerun()
    with c2:
        st.markdown('<div class="animated-card"><h1>👨‍👩‍👧</h1><h3>Espace Parents</h3></div>', unsafe_allow_html=True)
        if st.button("Accéder Parent", key="btn_pa"):
            st.session_state.espace_actif = "👨‍👩‍👧 Espace Parents / Élèves"
            st.rerun()
    with c3:
        st.markdown('<div class="animated-card"><h1>🔒</h1><h3>Administration</h3></div>', unsafe_allow_html=True)
        if st.button("Accéder Admin", key="btn_ad"):
            st.session_state.espace_actif = "🔒 Espace Administration (Sécurisé)"
            st.rerun()
    with c4:
        st.markdown('<div class="animated-card"><h1>🏫</h1><h3>Rapports Globaux</h3></div>', unsafe_allow_html=True)
        if st.button("Accéder Rapports", key="btn_rp"):
            st.session_state.espace_actif = "🔒 Espace Administration (Sécurisé)"
            st.rerun()

# ==========================================
# 6. MODULES MÉTIERS
# ==========================================

# ESPACE PROFESSEURS
if st.session_state.espace_actif == "👨‍🏫 Espace Professeurs / Maîtres":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Espace Enseignants & Maîtres</div>', unsafe_allow_html=True)

    if "prof_logged" not in st.session_state: st.session_state.prof_logged = False
    if "prof_nom_connecte" not in st.session_state: st.session_state.prof_nom_connecte = ""
    if "prof_classe_autorisee" not in st.session_state: st.session_state.prof_classe_autorisee = ""

    if not st.session_state.prof_logged:
        with st.form("form_login_prof"):
            p_nom = st.text_input("Nom")
            p_prenom = st.text_input("Prénom")
            p_pass = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Se connecter"):
                match_prof = False
                classe_trouvee = ""
                for _, row in st.session_state.prof_credentials.iterrows():
                    if (str(row["Nom"]).strip().lower() == p_nom.strip().lower() and 
                        str(row["Prénom"]).strip().lower() == p_prenom.strip().lower() and 
                        verifier_mot_de_passe(p_pass, str(row["Mot de passe"]))):
                        match_prof = True
                        classe_trouvee = str(row.get("Classe Attribuée", "6ème A"))
                        break
                if match_prof:
                    st.session_state.prof_logged = True
                    st.session_state.prof_nom_connecte = f"{p_prenom} {p_nom}"
                    st.session_state.prof_classe_autorisee = classe_trouvee
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects.")
    else:
        st.success(f"Connecté : **{st.session_state.prof_nom_connecte}** | Classe : **{st.session_state.prof_classe_autorisee}**")
        if st.button("Se déconnecter"):
            st.session_state.prof_logged = False
            st.rerun()

# ESPACE PARENTS
elif st.session_state.espace_actif == "👨‍👩‍👧 Espace Parents / Élèves":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Portail Parent & Élève</div>', unsafe_allow_html=True)
    if "parent_logged_eleve" not in st.session_state: st.session_state["parent_logged_eleve"] = ""

    if not st.session_state["parent_logged_eleve"]:
        with st.form("form_login_parent"):
            tel_p = st.text_input("Téléphone (ex: +221771234567)")
            prenom_e = st.text_input("Prénom de l'élève")
            nom_e = st.text_input("Nom de l'élève")
            an_e = st.number_input("Année de naissance", 2005, 2024, 2012)
            if st.form_submit_button("Se connecter"):
                clean_tel = tel_p.replace(" ", "").replace("+", "")
                match = False
                for _, row in st.session_state.parents_white_list.iterrows():
                    if clean_tel in str(row["Téléphone"]) and str(row["Prénom Élève"]).lower() == prenom_e.lower() and str(row["Nom Élève"]).lower() == nom_e.lower() and int(row["Année Naissance"]) == int(an_e):
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
        
        tri_p = st.selectbox("Période", ["1er Semestre", "2ème Semestre", "1er Trimestre"])
        pdf_bulletin = generer_bulletin_pdf(eleve, classe, tri_p)
        st.download_button(
            label="📄 Télécharger le Bulletin Officiel (PDF)",
            data=pdf_bulletin,
            file_name=f"bulletin_{eleve.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

# ESPACE ADMINISTRATION SÉCURISÉ
elif st.session_state.espace_actif == "🔒 Espace Administration (Sécurisé)":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration Générale (Accès Restreint)</div>', unsafe_allow_html=True)

    if not st.session_state.authenticated_admin:
        with st.form("form_adm_secu"):
            em = st.text_input("Email / Identifiant Administrateur")
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion Admin"):
                match_a = False
                role_connecte = "Administrateur"
                if em in ADMIN_WHITELIST:
                    match_a = True
                    role_connecte = "Administrateur Global"
                else:
                    for _, row in st.session_state.admin_credentials.iterrows():
                        if row["Email"] == em and verifier_mot_de_passe(pw, str(row["Mot de passe"])):
                            match_a = True
                            break
                    if not match_a:
                        for _, row in st.session_state.gestionnaires_proprietaires_db.iterrows():
                            if str(row["Email"]).strip().lower() == em.strip().lower() and verifier_mot_de_passe(pw, str(row["Mot de passe"])):
                                match_a = True
                                role_connecte = row["Rôle"]
                                break
                if match_a:
                    st.session_state.authenticated_admin = True
                    st.session_state.admin_role_connecte = role_connecte
                    st.session_state.admin_email_connecte = em
                    st.success("Accès accordé !")
                    st.rerun()
                else:
                    st.error("Identifiants erronés.")
    else:
        st.success(f"Mode Admin Activé — Connecté en tant que {st.session_state.get('admin_role_connecte', 'Admin')}")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)", 
            "👨‍🎓 Élèves (Export PDF, Modif, Suppr)", 
            "🏫 Classes (Ajouter, Modifier, Supprimer)", 
            "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel",
            "🤖 Assistant IA Administration"
        ])

        # ==========================================
        # MODULE PROFESSEURS CORRIGÉ ET SYNCHRONISÉ
        # ==========================================
        if adm_tab == "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Professeurs & Synchronisation BDD")
            
            # Formulaire d'ajout sécurisé
            with st.expander("➕ Enregistrer un nouveau professeur"):
                with st.form("form_add_prof"):
                    p_n = st.text_input("Nom")
                    p_p = st.text_input("Prénom")
                    p_mat = st.text_input("Matière principale")
                    classes_existantes = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"]
                    p_cls_attrib = st.selectbox("Classe Attribuée", classes_existantes)
                    p_pwd = st.text_input("Mot de passe", type="password")
                    
                    if st.form_submit_button("Enregistrer le professeur"):
                        if p_n and p_p and p_pwd:
                            new_p = pd.DataFrame([{
                                "Nom": p_n, 
                                "Prénom": p_p, 
                                "Mot de passe": hacher_mot_de_passe(p_pwd), 
                                "Matière Principale": p_mat, 
                                "Classe Attribuée": p_cls_attrib
                            }])
                            st.session_state.prof_credentials = pd.concat([st.session_state.prof_credentials, new_p], ignore_index=True)
                            
                            # SYNCHRONISATION SQLITE IMMÉDIATE ET ROBUSTE
                            conn = obtenir_connexion()
                            st.session_state.prof_credentials.to_sql('prof_credentials', conn, if_exists='replace', index=False)
                            conn.close()

                            st.success("Professeur enregistré et synchronisé avec succès dans la base de données !")
                            st.rerun()
                        else:
                            st.error("Veuillez remplir le nom, prénom et mot de passe.")

            st.markdown("---")
            st.markdown("#### 🗑️ Supprimer un Professeur")
            if not st.session_state.prof_credentials.empty:
                liste_profs_combo = [f"{row['Prénom']} {row['Nom']} ({row['Matière Principale']})" for _, row in st.session_state.prof_credentials.iterrows()]
                prof_choisi_del = st.selectbox("Sélectionner le professeur à supprimer", liste_profs_combo)
                if st.button("❌ Supprimer ce professeur"):
                    st.session_state.prof_credentials = st.session_state.prof_credentials[
                        ~st.session_state.prof_credentials.apply(lambda r: f"{r['Prénom']} {r['Nom']} ({r['Matière Principale']})" == prof_choisi_del, axis=1)
                    ].reset_index(drop=True)
                    
                    conn = obtenir_connexion()
                    st.session_state.prof_credentials.to_sql('prof_credentials', conn, if_exists='replace', index=False)
                    conn.close()

                    st.success("Professeur supprimé et base synchronisée !")
                    st.rerun()
            else:
                st.info("Aucun professeur enregistré.")

            st.markdown("---")
            st.markdown("#### Modification directe de la table Professeurs")
            edited_profs = st.data_editor(st.session_state.prof_credentials, num_rows="dynamic", use_container_width=True, key="editor_profs")
            if st.button("💾 Enregistrer les Modifications Professeurs"):
                st.session_state.prof_credentials = edited_profs
                conn = obtenir_connexion()
                st.session_state.prof_credentials.to_sql('prof_credentials', conn, if_exists='replace', index=False)
                conn.close()
                st.success("Base professeurs mise à jour et synchronisée avec succès !")

        elif adm_tab == "👨‍🎓 Élèves (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Élèves")
            edited_eleves = st.data_editor(st.session_state.eleves_db, num_rows="dynamic", use_container_width=True, key="editor_eleves")
            if st.button("💾 Enregistrer les Modifications Élèves"):
                st.session_state.eleves_db = edited_eleves
                conn = obtenir_connexion()
                st.session_state.eleves_db.to_sql('eleves', conn, if_exists='replace', index=False)
                conn.close()
                st.success("Base des élèves mise à jour et synchronisée !")

        elif adm_tab == "🏫 Classes (Ajouter, Modifier, Supprimer)":
            st.subheader("Gestion des Classes")
            edited_classes = st.data_editor(st.session_state.classes_db, num_rows="dynamic", use_container_width=True, key="editor_classes")
            if st.button("💾 Enregistrer les Modifications Classes"):
                st.session_state.classes_db = edited_classes
                conn = obtenir_connexion()
                st.session_state.classes_db.to_sql('classes', conn, if_exists='replace', index=False)
                conn.close()
                st.success("Base des classes mise à jour et synchronisée !")

        elif adm_tab == "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel":
            st.subheader("🗄️ Base Globale de Suivi")
            st.dataframe(st.session_state.base_globale_db, use_container_width=True)
            pdf_rap_gen = generer_rapport_general_pdf()
            st.download_button(
                label="📊 Télécharger le RAPPORT GÉNÉRAL OFFICIEL (PDF)",
                data=pdf_rap_gen,
                file_name="rapport_general_nelson_mandela.pdf",
                mime="application/pdf",
                type="primary"
            )

        elif adm_tab == "🤖 Assistant IA Administration":
            st.subheader("🤖 Assistant virtuel IA")
            q_ia = st.text_input("Posez votre question à l'IA :")
            if st.button("Consulter l'IA"):
                if q_ia:
                    st.markdown(f"> {assistant_ia_repondre(q_ia)}")
                else:
                    st.warning("Veuillez saisir une question.")
