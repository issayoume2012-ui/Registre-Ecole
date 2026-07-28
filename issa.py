import base64
from datetime import datetime
import io
import os
import urllib.request
from fpdf import FPDF
import pandas as pd
import streamlit as st

# ==========================================
# 0. GESTION DES POLICES UNICODE (OPTIMISÉE POUR MOBILE)
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

# Téléchargement au premier lancement (mis en cache)
telecharger_polices()

# ==========================================
# 1. CONFIGURATION DE LA PAGE & DESIGN XXL RESPONSIVE FAST-LOAD
# ==========================================
st.set_page_config(
    page_title="Portail Pédagogique - Cours Privé Nelson Mandela | Sénégal",
    page_icon="🇸🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* Global Styles & Mobile Reset Optimisé */
    .main { background-color: #F8FAFC; }
    
    .header-ecole { 
        color: #1E3A8A; 
        font-size: clamp(1.8rem, 4vw, 2.8rem); 
        font-weight: 900; 
        text-align: center; 
        margin-bottom: 5px;
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
    }

    /* Cartes adaptatives légères */
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

    /* Key Performance Indicators */
    .kpi-card-animated {
        border-left: 5px solid #2563EB;
        background: #FFFFFF;
        padding: 15px;
        border-radius: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        text-align: center;
    }

    /* Boutons tactiles optimisés mobile */
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
    st.session_state.admin_credentials = pd.DataFrame([
        {"Nom": "Admin", "Prénom": "Principal", "Email": "cpnm@gmail.com", "Mot de passe": "cpnm2026"}
    ])

if "prof_credentials" not in st.session_state:
    st.session_state.prof_credentials = pd.DataFrame([
        {"Nom": "Diallo", "Prénom": "Ibrahima", "Mot de passe": "prof123", "Matière Principale": "Mathématiques"},
        {"Nom": "Sow", "Prénom": "Aissatou", "Mot de passe": "prof456", "Matière Principale": "Français"},
        {"Nom": "Ndiaye", "Prénom": "Cheikh", "Mot de passe": "prof789", "Matière Principale": "Histoire-Géographie"}
    ])

if "parents_white_list" not in st.session_state:
    st.session_state.parents_white_list = pd.DataFrame([
        {"Téléphone": "+221771234567", "Prénom Élève": "Mamadou", "Nom Élève": "Diallo", "Année Naissance": 2012, "Classe": "6ème A"},
        {"Téléphone": "+221769876543", "Prénom Élève": "Fatou", "Nom Élève": "Sow", "Année Naissance": 2015, "Classe": "CP"},
    ])

if "classes_db" not in st.session_state:
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
    st.session_state.eleves_db = pd.DataFrame(
        columns=["Nom Complet", "Date de Naissance", "Classe", "Photo"],
        data=[
            ["Mamadou Diallo", "2012-05-14", "6ème A", None],
            ["Fatou Sow", "2015-08-20", "CP", None],
            ["Aminata Ba", "2013-02-10", "6ème A", None],
            ["Oumar Sy", "2011-11-03", "5ème A", None]
        ]
    )

if "base_globale_db" not in st.session_state:
    st.session_state.base_globale_db = pd.DataFrame(
        columns=["Date", "Année", "Trimestre", "Mois", "Type Acteur", "Nom Acteur", "Classe", "Type Entrée", "Détail / Contenu", "Appréciation"],
        data=[
            {"Date": "2026-01-15", "Année": "2025-2026", "Trimestre": "1er Trimestre", "Mois": "Janvier", "Type Acteur": "Élève", "Nom Acteur": "Mamadou Diallo", "Classe": "6ème A", "Type Entrée": "Note", "Détail / Contenu": "Mathématiques: 15.5/20", "Appréciation": "Très bon travail"},
            {"Date": "2026-01-20", "Année": "2025-2026", "Trimestre": "1er Trimestre", "Mois": "Janvier", "Type Acteur": "Élève", "Nom Acteur": "Aminata Ba", "Classe": "6ème A", "Type Entrée": "Absence", "Détail / Contenu": "Absent - Motif: Maladie", "Appréciation": "Justifié"},
            {"Date": "2026-02-05", "Année": "2025-2026", "Trimestre": "2ème Trimestre", "Mois": "Février", "Type Acteur": "Professeur", "Nom Acteur": "Ibrahima Diallo", "Classe": "6ème A", "Type Entrée": "Rapport Cours", "Détail / Contenu": "Algèbre - Chapitre 3 terminé", "Appréciation": "Excellente progression"}
        ]
    )

JOURS_LIST = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]
HEURES_LIST = ["08h-09h", "09h-10h", "10h-11h", "11h-12h", "15h-16h", "16h-17h"]

if "edt_grid_db" not in st.session_state:
    st.session_state.edt_grid_db = {}

def get_or_create_edt(classe):
    if classe not in st.session_state.edt_grid_db:
        st.session_state.edt_grid_db[classe] = pd.DataFrame(
            "", index=JOURS_LIST, columns=HEURES_LIST
        )
    return st.session_state.edt_grid_db[classe]

if "cahier_textes" not in st.session_state:
    st.session_state.cahier_textes = pd.DataFrame(
        columns=["Professeur", "Date", "Classe", "Matière", "Contenu", "Travail à faire"],
        data=[
            ["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Introduction aux nombres relatifs.", "Exercices 1 et 2 page 45."]
        ]
    )

if "rapports_journaliers_prof" not in st.session_state:
    st.session_state.rapports_journaliers_prof = pd.DataFrame(
        columns=["Professeur", "Date", "Classe", "Matière", "Bilan du Cours", "Difficultés / Remarques"],
        data=[
            ["Ibrahima Diallo", "2026-06-01", "6ème A", "Mathématiques", "Bonne participation globale des élèves.", "Quelques difficultés sur les soustractions de négatifs."]
        ]
    )

if "absences_db" not in st.session_state:
    st.session_state.absences_db = pd.DataFrame(
        columns=["Date", "Classe", "Élève", "Statut", "Motif"],
        data=[
            ["2026-06-01", "6ème A", "Aminata Ba", "Absent", "Maladie"]
        ]
    )

if "notes_db" not in st.session_state:
    st.session_state.notes_db = pd.DataFrame(
        columns=["Classe", "Élève", "Matière", "Coefficient", "Note", "Barème", "Trimestre", "Appréciation"],
        data=[
            ["6ème A", "Mamadou Diallo", "Mathématiques", 3, 15.5, 20, "1er Trimestre", "Très bon travail."],
            ["6ème A", "Mamadou Diallo", "Français", 3, 14.0, 20, "1er Trimestre", "Bon ensemble."],
            ["CP", "Fatou Sow", "Graphisme / Écriture", 1, 8.5, 10, "1er Trimestre", "Très bien."]
        ]
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
        data=[
            ["6ème A", "Mamadou Diallo", "2026-06-02", "Encouragement", "Participation active en classe."]
        ]
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
    pdf.cell(100, 6, f"Établissement : Cours Privé Nelson Mandela", 0, 0, "L")
    pdf.cell(90, 6, f"Barème officiel : / {bareme}", 0, 1, "R")
    pdf.ln(5)

    df_n = st.session_state.notes_db[
        (st.session_state.notes_db["Élève"] == eleve_nom) & 
        (st.session_state.notes_db["Trimestre"] == trimestre_sel)
    ]

    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    
    w_mat, w_coef, w_note, w_tot, w_app = 55, 20, 30, 30, 55
    pdf.cell(w_mat, 7, "Matière", 1, 0, "C", True)
    pdf.cell(w_coef, 7, "Coef", 1, 0, "C", True)
    pdf.cell(w_note, 7, f"Note /{bareme}", 1, 0, "C", True)
    pdf.cell(w_tot, 7, "Total Coef", 1, 0, "C", True)
    pdf.cell(w_app, 7, "Appréciation", 1, 1, "C", True)

    pdf.set_font("Arial", "", 9)
    pdf.set_text_color(0, 0, 0)

    total_points = 0.0
    total_coefs = 0

    if not df_n.empty:
        for _, r in df_n.iterrows():
            coef = int(r["Coefficient"])
            note = float(r["Note"])
            tot = note * coef
            total_points += tot
            total_coefs += coef

            pdf.cell(w_mat, 6, str(r["Matière"])[:28], 1, 0, "L")
            pdf.cell(w_coef, 6, str(coef), 1, 0, "C")
            pdf.cell(w_note, 6, f"{note:.2f}", 1, 0, "C")
            pdf.cell(w_tot, 6, f"{tot:.2f}", 1, 0, "C")
            pdf.cell(w_app, 6, str(r["Appréciation"])[:28], 1, 1, "L")

    moyenne = (total_points / total_coefs) if total_coefs > 0 else 0.0
    pdf.ln(3)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(95, 7, f"Total des Points : {total_points:.2f}", 1, 0, "L")
    pdf.cell(95, 7, f"Total des Coefficients : {total_coefs}", 1, 1, "L")
    
    pdf.set_fill_color(230, 242, 255)
    pdf.cell(190, 8, f"MOYENNE GÉNÉRALE : {moyenne:.2f} / {bareme}", 1, 1, "C", True)

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

    if bareme == 20:
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
    
    use_dejavu = os.path.exists("DejaVuSans.ttf")
    
    if use_dejavu:
        pdf.add_font("DejaVu", "", "DejaVuSans.ttf", uni=True)
        font_main = "DejaVu"
        bullet = "• "
    else:
        font_main = "Arial"
        bullet = "- "
    
    pdf.set_font(font_main, "B", 14)
    pdf.cell(0, 8, "RAPPORT GÉNÉRAL & CONSOLIDATION ANNUELLE", 0, 1, "C")
    pdf.set_font(font_main, "I", 10)
    pdf.cell(0, 5, "Synthèse Globale des Évaluations, Renseignements, Absences et Activités", 0, 1, "C")
    pdf.ln(6)

    # 1. STATISTIQUES GÉNÉRALES
    pdf.set_font(font_main, "B", 11)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 7, "1. STATISTIQUES GÉNÉRALES DE L'ÉTABLISSEMENT", 1, 1, "L", True)
    
    pdf.set_font(font_main, "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(95, 6, f"Total Élèves Inscrits : {len(st.session_state.eleves_db)}", 1, 0, "L")
    pdf.cell(95, 6, f"Total Classes Actives : {len(st.session_state.classes_db)}", 1, 1, "L")
    pdf.cell(95, 6, f"Corps Enseignant : {len(st.session_state.prof_credentials)} professeurs", 1, 0, "L")
    pdf.cell(95, 6, f"Total Entrées Base Globale : {len(st.session_state.base_globale_db)}", 1, 1, "L")
    pdf.ln(5)

    # 2. SUIVI DES ENSEIGNANTS
    pdf.set_font(font_main, "B", 11)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 7, "2. SUIVI DES ENSEIGNANTS ET RAPPORTS DE SÉANCE", 1, 1, "L", True)
    
    pdf.set_font(font_main, "", 9)
    pdf.set_text_color(0, 0, 0)
    if not st.session_state.rapports_journaliers_prof.empty:
        for _, r in st.session_state.rapports_journaliers_prof.iterrows():
            txt = f"{bullet}[{r['Date']}] {r['Professeur']} ({r['Classe']} - {r['Matière']}) : {r['Bilan du Cours'][:60]}"
            if not use_dejavu:
                txt = txt.encode('latin-1', 'replace').decode('latin-1')
            pdf.cell(190, 6, txt, 1, 1, "L")
    else:
        pdf.cell(190, 6, "Aucun rapport déposé.", 1, 1, "L")
    pdf.ln(5)

    # 3. EXTRAIT RENSEIGNEMENTS BASE GLOBALE
    pdf.set_font(font_main, "B", 11)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 7, "3. EXTRAIT RENSEIGNEMENTS BASE GLOBALE", 1, 1, "L", True)

    pdf.set_font(font_main, "B", 8)
    pdf.set_fill_color(220, 230, 242)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(25, 6, "Date", 1, 0, "C", True)
    pdf.cell(30, 6, "Période", 1, 0, "C", True)
    pdf.cell(45, 6, "Acteur / Classe", 1, 0, "C", True)
    pdf.cell(30, 6, "Type", 1, 0, "C", True)
    pdf.cell(60, 6, "Détail", 1, 1, "C", True)

    pdf.set_font(font_main, "", 8)
    if not st.session_state.base_globale_db.empty:
        for _, row in st.session_state.base_globale_db.head(15).iterrows():
            d_str = str(row["Date"])
            per_str = f"{row['Mois']}/{str(row['Trimestre'])[:3]}"
            act_str = f"{str(row['Nom Acteur'])[:18]} ({row['Classe']})"
            typ_str = str(row["Type Entrée"])[:15]
            det_str = str(row["Détail / Contenu"])[:35]
            
            if not use_dejavu:
                d_str = d_str.encode('latin-1', 'replace').decode('latin-1')
                per_str = per_str.encode('latin-1', 'replace').decode('latin-1')
                act_str = act_str.encode('latin-1', 'replace').decode('latin-1')
                typ_str = typ_str.encode('latin-1', 'replace').decode('latin-1')
                det_str = det_str.encode('latin-1', 'replace').decode('latin-1')

            pdf.cell(25, 6, d_str, 1, 0, "C")
            pdf.cell(30, 6, per_str, 1, 0, "C")
            pdf.cell(45, 6, act_str, 1, 0, "L")
            pdf.cell(30, 6, typ_str, 1, 0, "C")
            pdf.cell(60, 6, det_str, 1, 1, "L")

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
        return "📝 Le système applique le barème sénégalais officialisé : **/10 pour le préscolaire/élémentaire** et **/20 pour le collège**, synchronisé avec la base globale."
    else:
        return "🤖 **IA Administration Nelson Mandela :** Je suis là pour vous assister ! Posez-moi des questions sur la base globale, les effectifs, emplois du temps ou les rapports."

# ==========================================
# 4. EN-TÊTE ET NAVIGATION GLOBALE
# ==========================================
st.markdown('<div class="header-ecole">🦁 Cours Privé Nelson Mandela</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Excellence, Discipline et Ancrage Culturel au Cœur du Sénégal</div>', unsafe_allow_html=True)

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
                Sélectionnez votre espace. Le système intègre désormais une Base Globale centralisant tout l'historique annuel des élèves et professeurs.
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
                <p style="font-size: 0.85rem; color: #64748B;">Notes, fiches d'appel, rapports & alimentation de la base globale.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Bulletins PDF synchronisés avec absences, conduite & notes.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Gestion Base Globale, Éleves par niveau, EDT & PDF.</p>
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

# ESPACE PROFESSEURS
elif st.session_state.espace_actif == "👨‍🏫 Espace Professeurs / Maîtres":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Espace Enseignants & Maîtres</div>', unsafe_allow_html=True)

    if "prof_logged" not in st.session_state:
        st.session_state.prof_logged = False
    if "prof_nom_connecte" not in st.session_state:
        st.session_state.prof_nom_connecte = ""

    if not st.session_state.prof_logged:
        st.info("Veuillez vous identifier avec vos accès professeurs.")
        with st.form("form_login_prof"):
            p_nom = st.text_input("Nom")
            p_prenom = st.text_input("Prénom")
            p_pass = st.text_input("Mot de passe", type="password")
            btn_p_login = st.form_submit_button("Se connecter")

            if btn_p_login:
                match_prof = False
                for _, row in st.session_state.prof_credentials.iterrows():
                    if (str(row["Nom"]).strip().lower() == p_nom.strip().lower() and 
                        str(row["Prénom"]).strip().lower() == p_prenom.strip().lower() and 
                        str(row["Mot de passe"]) == p_pass):
                        match_prof = True
                        break
                if match_prof:
                    st.session_state.prof_logged = True
                    st.session_state.prof_nom_connecte = f"{p_prenom} {p_nom}"
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects.")
    else:
        st.success(f"Connecté en tant que : **{st.session_state.prof_nom_connecte}**")
        if st.button("Se déconnecter"):
            st.session_state.prof_logged = False
            st.session_state.prof_nom_connecte = ""
            st.rerun()

        st.markdown("---")
        menu_prof = st.radio("Menu Professeur :", [
            "📋 Fiche d'Appel", 
            "📝 Saisie des Notes par Fiche Matière", 
            "⚠️ Conduite", 
            "📖 Cahier de Textes", 
            "📊 Rapport Journalier"
        ], horizontal=True)
        prof_connecte = st.session_state.prof_nom_connecte

        if menu_prof == "📋 Fiche d'Appel":
            st.markdown("### Feuille d'Appel Journalière")
            if not st.session_state.classes_db.empty and not st.session_state.eleves_db.empty:
                date_jour = st.date_input("Date", value=datetime.today())
                cls_appel = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist())
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
                            tri_actuel = "1er Trimestre"

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
                            st.success("Appel enregistré et synchronisé dans la Base Globale !")
                else:
                    st.info("Aucun élève dans cette classe.")

        elif menu_prof == "📝 Saisie des Notes par Fiche Matière":
            st.markdown("### Fiche de Matière — Saisie des Notes et Appréciations")
            
            c_cls, c_tri = st.columns(2)
            with c_cls:
                cls_n = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
            with c_tri:
                trimestre_sel = st.selectbox("Trimestre", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])

            row_c = st.session_state.classes_db[st.session_state.classes_db["Classe"] == cls_n]
            cycle_sel = row_c["Cycle"].values[0] if not row_c.empty else "Collège"
            bareme_sel = 10 if cycle_sel in ["Préscolaire", "Élémentaire"] else 20
            
            # --- MODIFICATION SOLICITÉE : Saisie directe de la matière et du coefficient ---
            mode_mat = st.radio("Saisie Matière :", ["Saisir directement la matière & coef", "Choisir parmi les matières prédéfinies"], horizontal=True)
            
            c_mat, c_coef = st.columns([3, 1])
            if mode_mat == "Saisir directement la matière & coef":
                with c_mat:
                    matiere_sel = st.text_input("Saisir le nom de la Matière", value="", placeholder="ex: Mathématiques, Arabe, Physique...")
                with c_coef:
                    coef_val = st.number_input("Coefficient", min_value=1, max_value=10, value=2)
            else:
                with c_mat:
                    mats_filt = st.session_state.matieres_def[st.session_state.matieres_def["Cycle"] == cycle_sel]["Matière"].tolist()
                    if not mats_filt:
                        mats_filt = ["Mathématiques", "Français", "Histoire-Géo"]
                    matiere_sel = st.selectbox("Matière Prédéfinie", mats_filt)
                
                row_mat = st.session_state.matieres_def[st.session_state.matieres_def["Matière"] == matiere_sel]
                coef_def = int(row_mat["Coefficient"].values[0]) if not row_mat.empty else 2
                with c_coef:
                    coef_val = st.number_input("Coefficient", min_value=1, max_value=10, value=coef_def)

            st.info(f"📌 Cycle : **{cycle_sel}** | Barème : **Note /{bareme_sel}** | Coef : **{coef_val}**")

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
                            (st.session_state.notes_db["Trimestre"] == trimestre_sel)
                        ]
                        note_init = float(existing["Note"].values[0]) if not existing.empty else float(bareme_sel / 2)
                        appr_init = str(existing["Appréciation"].values[0]) if not existing.empty else "Bon travail"

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
                        key=f"editor_{cls_n}_{matiere_sel}_{trimestre_sel}"
                    )

                    if st.button("💾 Enregistrer la Fiche de Matière"):
                        st.session_state.notes_db = st.session_state.notes_db[
                            ~((st.session_state.notes_db["Classe"] == cls_n) & 
                              (st.session_state.notes_db["Matière"] == matiere_sel) & 
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
                                "Coefficient": coef_val,
                                "Note": r[f"Note /{bareme_sel}"],
                                "Barème": bareme_sel,
                                "Trimestre": trimestre_sel,
                                "Appréciation": r["Appréciation"]
                            })
                            new_bg_rows.append({
                                "Date": d_today, "Année": "2025-2026", "Trimestre": trimestre_sel, "Mois": m_today,
                                "Type Acteur": "Élève", "Nom Acteur": r["Élève"], "Classe": cls_n,
                                "Type Entrée": "Note", "Détail / Contenu": f"{matiere_sel} (Coef {coef_val}): {r[f'Note /{bareme_sel}']}/{bareme_sel}",
                                "Appréciation": r["Appréciation"]
                            })
                        
                        st.session_state.notes_db = pd.concat([st.session_state.notes_db, pd.DataFrame(new_rows)], ignore_index=True)
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, pd.DataFrame(new_bg_rows)], ignore_index=True)
                        st.success(f"Fiche de {matiere_sel} (Coef {coef_val}) enregistrée et synchronisée !")

                editeur_notes_fragment()

            elif not matiere_sel.strip():
                st.warning("Veuillez indiquer ou saisir le nom de la matière.")
            else:
                st.warning("Aucun élève trouvé dans cette classe.")

        elif menu_prof == "⚠️ Conduite":
            st.markdown("### Suivi de Conduite")
            with st.form("form_cond_prof"):
                cls_c = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
                eleves_c = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_c]["Nom Complet"].tolist()
                el_c = st.selectbox("Élève", eleves_c if eleves_c else ["--"])
                type_s = st.selectbox("Type", ["Avertissement", "Blâme", "Retenue", "Félicitations", "Encouragement"])
                desc = st.text_area("Description des faits")
                if st.form_submit_button("Enregistrer"):
                    if el_c and desc:
                        d_str = str(datetime.today().date())
                        new_cd = pd.DataFrame([{"Classe": cls_c, "Élève": el_c, "Date": d_str, "Type": type_s, "Description": desc}])
                        st.session_state.conduite_db = pd.concat([st.session_state.conduite_db, new_cd], ignore_index=True)
                        
                        bg_entry = pd.DataFrame([{
                            "Date": d_str, "Année": "2025-2026", "Trimestre": "1er Trimestre", "Mois": datetime.today().strftime("%B"),
                            "Type Acteur": "Élève", "Nom Acteur": el_c, "Classe": cls_c,
                            "Type Entrée": "Conduite", "Détail / Contenu": f"{type_s}: {desc}", "Appréciation": type_s
                        }])
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, bg_entry], ignore_index=True)
                        st.success("Remarque enregistrée et synchronisée.")

        elif menu_prof == "📖 Cahier de Textes":
            st.markdown("### Cahier de Textes Numérique")
            with st.form("form_cahier"):
                cls_ct = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
                mat_ct = st.text_input("Matière")
                contenu = st.text_area("Contenu de la séance")
                travail = st.text_area("Travail à faire")
                if st.form_submit_button("Publier"):
                    if mat_ct and contenu:
                        new_ct = pd.DataFrame([{"Professeur": prof_connecte, "Date": str(datetime.today().date()), "Classe": cls_ct, "Matière": mat_ct, "Contenu": contenu, "Travail à faire": travail}])
                        st.session_state.cahier_textes = pd.concat([st.session_state.cahier_textes, new_ct], ignore_index=True)
                        st.success("Leçon publiée.")

        elif menu_prof == "📊 Rapport Journalier":
            st.markdown("### Rédiger un Rapport Journalier")
            st.caption("Ce rapport sera directement transmis à la direction et enregistré dans la base globale.")
            with st.form("form_rap_prof"):
                cls_r = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
                mat_r = st.text_input("Matière")
                bilan = st.text_area("Bilan du cours")
                diff = st.text_area("Difficultés ou remarques")
                if st.form_submit_button("Soumettre à l'administration"):
                    if mat_r and bilan:
                        d_str = str(datetime.today().date())
                        new_r = pd.DataFrame([{"Professeur": prof_connecte, "Date": d_str, "Classe": cls_r, "Matière": mat_r, "Bilan du Cours": bilan, "Difficultés / Remarques": diff}])
                        st.session_state.rapports_journaliers_prof = pd.concat([st.session_state.rapports_journaliers_prof, new_r], ignore_index=True)
                        
                        bg_prof = pd.DataFrame([{
                            "Date": d_str, "Année": "2025-2026", "Trimestre": "1er Trimestre", "Mois": datetime.today().strftime("%B"),
                            "Type Acteur": "Professeur", "Nom Acteur": prof_connecte, "Classe": cls_r,
                            "Type Entrée": "Rapport", "Détail / Contenu": f"{mat_r} - {bilan}", "Appréciation": diff if diff else "RAS"
                        }])
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, bg_prof], ignore_index=True)
                        st.success("Rapport transmis et centralisé dans la Base Globale !")

# ESPACE PARENTS
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

        st.markdown("---")
        t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Bulletin & Notes", "📅 Emploi du Temps", "📉 Absences", "⚠️ Conduite", "📖 Cahier de Textes", "🪪 Carte Scolaire"])
        
        with t1:
            st.subheader("Bulletin de Notes Officiel Synchronisé")
            tri_p = st.selectbox("Sélectionner le Trimestre", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
            
            notes_el = st.session_state.notes_db[
                (st.session_state.notes_db["Élève"] == eleve) & 
                (st.session_state.notes_db["Trimestre"] == tri_p)
            ]

            if not notes_el.empty:
                st.dataframe(notes_el[["Matière", "Coefficient", "Note", "Barème", "Appréciation"]], use_container_width=True)
                
                total_pts = (notes_el["Note"] * notes_el["Coefficient"]).sum()
                total_coef = notes_el["Coefficient"].sum()
                bareme_c = notes_el["Barème"].iloc[0] if "Barème" in notes_el.columns else 20
                
                if total_coef > 0:
                    moy = total_pts / total_coef
                    st.markdown(f"### 🎯 Moyenne générale : **{moy:.2f} / {bareme_c}**")

                pdf_bulletin = generer_bulletin_pdf(eleve, classe, tri_p)
                st.download_button(
                    label="📄 Télécharger le Bulletin Officiel Synchronisé (PDF)",
                    data=pdf_bulletin,
                    file_name=f"bulletin_{eleve.replace(' ', '_')}_{tri_p}.pdf",
                    mime="application/pdf"
                )
            else:
                st.info("Aucune note enregistrée pour ce trimestre.")

        with t2:
            st.subheader("Emploi du Temps de la Classe")
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
            st.subheader("Cahier de Textes de la Classe")
            ct_cls = st.session_state.cahier_textes[st.session_state.cahier_textes["Classe"] == classe]
            if not ct_cls.empty: st.dataframe(ct_cls, use_container_width=True)
            else: st.info("Aucune leçon publiée.")

        with t6:
            st.subheader("Carte Scolaire Numérique")
            st.markdown(
                f"""
                <div style="border: 2px solid #1E3A8A; padding: 20px; border-radius: 12px; background-color: #FFF; max-width: 400px;">
                    <h4 style="color: #1E3A8A; text-align: center; margin:0;">COURS PRIVÉ NELSON MANDELA</h4>
                    <p style="text-align: center; font-size: 0.7rem; color: #666;">RÉPUBLIQUE DU SÉNÉGAL</p>
                    <hr>
                    <p><b>Nom & Prénom :</b> {eleve}</p>
                    <p><b>Classe :</b> {classe}</p>
                    <p><b>Statut :</b> Élève régulier(ère)</p>
                </div>
                """,
                unsafe_allow_html=True
            )

# ESPACE ADMINISTRATION SÉCURISÉ
elif st.session_state.espace_actif == "🔒 Espace Administration (Sécurisé)":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration Générale (Accès Restreint)</div>', unsafe_allow_html=True)

    if not st.session_state.authenticated_admin:
        with st.form("form_adm_secu"):
            em = st.text_input("Email Administrateur")
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion Admin"):
                match_a = False
                for _, row in st.session_state.admin_credentials.iterrows():
                    if row["Email"] == em and row["Mot de passe"] == pw:
                        match_a = True
                        break
                if match_a:
                    st.session_state.authenticated_admin = True
                    st.success("Accès administrateur accordé !")
                    st.rerun()
                else:
                    st.error("Identifiants erronés.")
    else:
        st.success("Mode Administrateur Général Activé — Gestion Centralisée Complète.")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "📊 Liste & Classement des Élèves (Par Classe & Niveau)",
            "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel",
            "🤖 Assistant IA Administration",
            "📅 Emploi du Temps (Grille Jours x Heures)",
            "👨‍🎓 Élèves (Export PDF, Modif, Suppr)", 
            "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)", 
            "🏫 Classes (Ajouter, Modifier, Supprimer)", 
            "📋 Listes Blanches Parents", 
            "📑 Rapports Journaliers Réceptionnés"
        ])

        # --- MODIFICATION SOLICITÉE : Liste des élèves classés par classe et par niveau ---
        if adm_tab == "📊 Liste & Classement des Élèves (Par Classe & Niveau)":
            st.subheader("📊 Classement et Liste des Élèves par Classe et par Niveau (Cycle)")

            df_merged = pd.merge(st.session_state.eleves_db, st.session_state.classes_db[["Classe", "Cycle"]], on="Classe", how="left")

            t_niv, t_cls = st.tabs(["🏛️ Par Niveau (Cycle)", "🏫 Par Classe"])

            with t_niv:
                st.markdown("### 🏛️ Répartition des Élèves par Niveau (Cycle)")
                cycles_existants = ["Préscolaire", "Élémentaire", "Collège"]
                for cyc in cycles_existants:
                    df_c = df_merged[df_merged["Cycle"] == cyc]
                    if not df_c.empty:
                        with st.expander(f"📌 Cycle {cyc.upper()} ({len(df_c)} Élèves)", expanded=True):
                            st.dataframe(df_c[["Nom Complet", "Classe", "Date de Naissance"]].sort_values(by=["Classe", "Nom Complet"]), use_container_width=True)

            with t_cls:
                st.markdown("### 🏫 Répartition des Élèves par Classe")
                classes_existantes = st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else []
                for cl in classes_existantes:
                    df_cl = df_merged[df_merged["Classe"] == cl]
                    if not df_cl.empty:
                        with st.expander(f"🏫 Classe : {cl} ({len(df_cl)} Élèves)", expanded=True):
                            st.dataframe(df_cl[["Nom Complet", "Date de Naissance"]].sort_values(by="Nom Complet"), use_container_width=True)

        elif adm_tab == "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel":
            st.subheader("🗄️ Base Globale de Suivi des Élèves et Professeurs")
            st.caption("Consultation, segmentation par type d'entrée (Notes, Présences/Absences, Rapports) et impression globale.")

            f1, f2, f3, f4, f5 = st.columns(5)
            with f1:
                filtre_acteur = st.selectbox("Type d'Acteur", ["Tous", "Élève", "Professeur"])
            with f2:
                filtre_entree = st.selectbox("Catégorie d'Entrée", ["Toutes", "Note", "Absence", "Présence/Retard", "Rapport", "Conduite", "Appréciation"])
            with f3:
                filtre_annee = st.selectbox("Année Scolaire", ["Toutes", "2025-2026", "2024-2025"])
            with f4:
                filtre_tri = st.selectbox("Trimestre", ["Tous", "1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
            with f5:
                filtre_mois = st.selectbox("Mois", ["Tous", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"])

            df_bg = st.session_state.base_globale_db.copy()

            if filtre_acteur != "Tous": df_bg = df_bg[df_bg["Type Acteur"] == filtre_acteur]
            if filtre_entree != "Toutes": df_bg = df_bg[df_bg["Type Entrée"] == filtre_entree]
            if filtre_annee != "Toutes": df_bg = df_bg[df_bg["Année"] == filtre_annee]
            if filtre_tri != "Tous": df_bg = df_bg[df_bg["Trimestre"] == filtre_tri]
            if filtre_mois != "Tous": df_bg = df_bg[df_bg["Mois"] == filtre_mois]

            st.dataframe(df_bg, use_container_width=True)

            col_pdf1, col_pdf2 = st.columns(2)
            with col_pdf1:
                pdf_base_g = export_table_pdf("EXTRAIT BASE GLOBALE DE SUIVI", df_bg)
                st.download_button(
                    label="📄 Télécharger la vue filtrée en PDF",
                    data=pdf_base_g,
                    file_name="extrait_base_globale.pdf",
                    mime="application/pdf"
                )
            with col_pdf2:
                pdf_rap_gen = generer_rapport_general_pdf()
                st.download_button(
                    label="📊 Télécharger le RAPPORT GÉNÉRAL OFFICIEL (PDF)",
                    data=pdf_rap_gen,
                    file_name="rapport_general_nelson_mandela.pdf",
                    mime="application/pdf",
                    type="primary"
                )

            st.markdown("---")
            with st.expander("➕ Inserer une nouvelle entrée administrative dans la Base Globale"):
                with st.form("form_add_bg"):
                    c_date = st.date_input("Date", value=datetime.today())
                    c_annee = st.selectbox("Année Scolaire", ["2025-2026", "2026-2027"])
                    c_tri = st.selectbox("Trimestre", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
                    c_mois = st.selectbox("Mois", ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"])
                    c_type_act = st.selectbox("Type d'Acteur", ["Élève", "Professeur"])
                    c_nom_act = st.text_input("Nom de l'Élève ou Enseignant")
                    c_cls = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"])
                    c_type_ent = st.selectbox("Type d'Entrée", ["Note", "Absence", "Présence/Retard", "Rapport", "Conduite", "Appréciation", "Sanction", "Félicitation"])
                    c_det = st.text_area("Détail / Contenu")
                    c_app = st.text_input("Appréciation Générale")

                    if st.form_submit_button("Enregistrer dans la Base Globale"):
                        if c_nom_act and c_det:
                            new_entry = pd.DataFrame([{
                                "Date": str(c_date), "Année": c_annee, "Trimestre": c_tri, "Mois": c_mois,
                                "Type Acteur": c_type_act, "Nom Acteur": c_nom_act, "Classe": c_cls,
                                "Type Entrée": c_type_ent, "Détail / Contenu": c_det, "Appréciation": c_app
                            }])
                            st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, new_entry], ignore_index=True)
                            st.success("Entrée ajoutée à la Base Globale !")
                            st.rerun()

        elif adm_tab == "🤖 Assistant IA Administration":
            st.subheader("🤖 Assistant virtuel IA - Administration Nelson Mandela")
            st.caption("Posez une question ou demandez une analyse de situation de l'établissement.")
            q_ia = st.text_input("Posez votre question à l'IA :", placeholder="ex: Quel est l'effectif ou quel est le bilan de la base globale ?")
            if st.button("Consulter l'IA"):
                if q_ia:
                    rep = assistant_ia_repondre(q_ia)
                    st.markdown(f"> {rep}")
                else:
                    st.warning("Veuillez saisir une question.")

        elif adm_tab == "📅 Emploi du Temps (Grille Jours x Heures)":
            st.subheader("Édition de l'Emploi du Temps (Jours à gauche | Heures en haut)")
            cls_selected = st.selectbox("Sélectionner la classe à configurer", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"])
            
            st.info("Remplissez la grille d'emploi du temps ci-dessous. Chaque case représente la matière ou l'activité.")
            
            grid_edt = get_or_create_edt(cls_selected)

            edited_grid = st.data_editor(
                grid_edt,
                use_container_width=True,
                key=f"edt_editor_{cls_selected}"
            )

            if st.button("💾 Enregistrer la Grille de l'Emploi du Temps"):
                st.session_state.edt_grid_db[cls_selected] = edited_grid
                st.success(f"Emploi du temps de la classe {cls_selected} mis à jour !")

        elif adm_tab == "👨‍🎓 Élèves (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Élèves & Impression PDF")
            
            pdf_eleves = export_table_pdf("LISTE OFFICIELLE DES ÉLÈVES", st.session_state.eleves_db, ["Nom Complet", "Date de Naissance", "Classe"])
            st.download_button(
                label="🖨️ Imprimer / Télécharger la Liste des Élèves (PDF)",
                data=pdf_eleves,
                file_name="liste_eleves_nelson_mandela.pdf",
                mime="application/pdf"
            )

            st.markdown("---")
            with st.expander("➕ Ajouter un nouvel élève"):
                with st.form("form_add_eleve"):
                    c_nom = st.text_input("Nom complet de l'élève")
                    c_date = st.date_input("Date de naissance", value=datetime(2012, 1, 1))
                    c_cls = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"])
                    if st.form_submit_button("Ajouter l'élève"):
                        if c_nom:
                            new_el = pd.DataFrame([{"Nom Complet": c_nom, "Date de Naissance": str(c_date), "Classe": c_cls, "Photo": None}])
                            st.session_state.eleves_db = pd.concat([st.session_state.eleves_db, new_el], ignore_index=True)
                            st.success("Élève ajouté avec succès.")
                            st.rerun()

            st.markdown("#### Liste des Élèves (Modifiable & Supprimable)")
            edited_eleves = st.data_editor(st.session_state.eleves_db, num_rows="dynamic", use_container_width=True, key="editor_eleves")
            if st.button("💾 Enregistrer les Modifications Élèves"):
                st.session_state.eleves_db = edited_eleves
                st.success("Base des élèves mise à jour !")

        elif adm_tab == "👨‍🏫 Professeurs (Export PDF, Modif, Suppr)":
            st.subheader("Gestion des Professeurs & Impression PDF")
            
            pdf_profs = export_table_pdf("LISTE DU CORPS ENSEIGNANT", st.session_state.prof_credentials, ["Nom", "Prénom", "Matière Principale"])
            st.download_button(
                label="🖨️ Imprimer / Télécharger la Liste des Professeurs (PDF)",
                data=pdf_profs,
                file_name="liste_professeurs_nelson_mandela.pdf",
                mime="application/pdf"
            )

            st.markdown("---")
            with st.expander("➕ Enregistrer un professeur"):
                with st.form("form_add_prof"):
                    p_n = st.text_input("Nom")
                    p_p = st.text_input("Prénom")
                    p_mat = st.text_input("Matière principale")
                    p_pwd = st.text_input("Mot de passe", type="password")
                    if st.form_submit_button("Enregistrer le professeur"):
                        if p_n and p_p and p_pwd:
                            new_p = pd.DataFrame([{"Nom": p_n, "Prénom": p_p, "Mot de passe": p_pwd, "Matière Principale": p_mat}])
                            st.session_state.prof_credentials = pd.concat([st.session_state.prof_credentials, new_p], ignore_index=True)
                            st.success("Professeur enregistré.")
                            st.rerun()

            st.markdown("#### Liste des Professeurs (Modifiable & Supprimable)")
            edited_profs = st.data_editor(st.session_state.prof_credentials, num_rows="dynamic", use_container_width=True, key="editor_profs")
            if st.button("💾 Enregistrer les Modifications Professeurs"):
                st.session_state.prof_credentials = edited_profs
                st.success("Base professeurs mise à jour !")

        elif adm_tab == "🏫 Classes (Ajouter, Modifier, Supprimer)":
            st.subheader("Gestion des Classes")
            
            with st.expander("➕ Créer une classe"):
                with st.form("form_add_classe"):
                    nom_c = st.text_input("Nom de la classe (ex: 4ème A)")
                    cycle = st.selectbox("Cycle", ["Préscolaire", "Élémentaire", "Collège"])
                    if st.form_submit_button("Créer la classe"):
                        if nom_c:
                            new_cl = pd.DataFrame([{"Classe": nom_c, "Cycle": cycle, "Professeur Responsable": "Non assigné"}])
                            st.session_state.classes_db = pd.concat([st.session_state.classes_db, new_cl], ignore_index=True)
                            st.success("Classe créée.")
                            st.rerun()

            st.markdown("#### Liste des Classes (Modifiable)")
            edited_classes = st.data_editor(st.session_state.classes_db, num_rows="dynamic", use_container_width=True, key="editor_classes")
            if st.button("💾 Enregistrer les Modifications Classes"):
                st.session_state.classes_db = edited_classes
                st.success("Classes mises à jour !")

        elif adm_tab == "📋 Listes Blanches Parents":
            st.subheader("Listes Blanches des Parents")
            with st.form("form_wl"):
                t_p = st.text_input("Téléphone parent")
                pr_e = st.text_input("Prénom de l'élève")
                no_e = st.text_input("Nom de l'élève")
                an_n = st.number_input("Année de naissance", 2012)
                cl_s = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"])
                if st.form_submit_button("Ajouter l'autorisation"):
                    if t_p and pr_e:
                        new_w = pd.DataFrame([{"Téléphone": t_p, "Prénom Élève": pr_e, "Nom Élève": no_e, "Année Naissance": int(an_n), "Classe": cl_s}])
                        st.session_state.parents_white_list = pd.concat([st.session_state.parents_white_list, new_w], ignore_index=True)
                        st.success("Autorisation enregistrée.")
            st.dataframe(st.session_state.parents_white_list, use_container_width=True)

        elif adm_tab == "📑 Rapports Journaliers Réceptionnés":
            st.subheader("Rapports Journaliers Déposés par les Professeurs")
            if not st.session_state.rapports_journaliers_prof.empty:
                st.dataframe(st.session_state.rapports_journaliers_prof, use_container_width=True)
            else:
                st.info("Aucun rapport journalier reçu pour l'instant.")

# ESPACE RAPPORTS GLOBAUX
elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Tableau de Bord Global & Rapports Officiels</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Élèves Inscrits", len(st.session_state.eleves_db))
    with col2: st.metric("Classes Actives", len(st.session_state.classes_db))
    with col3: st.metric("Professeurs Répertoriés", len(st.session_state.prof_credentials))
    with col4: st.metric("Historiques Base Globale", len(st.session_state.base_globale_db))

    st.markdown("### Exportation du Rapport Général Complet")
    pdf_gen = generer_rapport_general_pdf()
    st.download_button(
        label="📊 Télécharger le Rapport Général de l'Établissement (PDF)",
        data=pdf_gen,
        file_name="rapport_general_nelson_mandela.pdf",
        mime="application/pdf"
    )
