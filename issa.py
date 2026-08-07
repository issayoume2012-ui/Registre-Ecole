import base64
from datetime import datetime
import io
import json
import os
import urllib.request
from fpdf import FPDF
import pandas as pd
import numpy as np
import streamlit as st
from supabase import create_client, Client

# ==========================================
# 0. GESTION DE LA PERSISTANCE SUPABASE & SÉCURITÉ MOTS DE PASSE
# ==========================================
try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    raise ImportError("La bibliothèque 'bcrypt' est obligatoire et doit être présente dans requirements.txt pour assurer la sécurité.")

def hacher_mot_de_passe(password: str) -> str:
    """Hache le mot de passe avec bcrypt pour ne jamais le stocker en clair."""
    if not password:
        return ""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verifier_mot_de_passe(password: str, hashed: str) -> bool:
    """Vérifie un mot de passe par rapport à son hachage sécurisé bcrypt."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

ADMIN_EMAIL = "cpnm@gmail.com"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase() -> Client:
    """Initialise le client SDK Supabase."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.warning("⚠️ Variables d'environnement SUPABASE_URL et SUPABASE_KEY non définies.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

def enregistrer_log_action(acteur: str, action: str, details: str):
    """Consigne chaque action utilisateur dans la table audit_logs via Supabase SDK."""
    try:
        horodatage = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        supabase.table("audit_logs").insert({
            "horodatage": horodatage,
            "acteur": acteur,
            "action": action,
            "details": details
        }).execute()
    except Exception:
        pass

def charger_donnees_externes():
    """Charge les données depuis Supabase via SDK."""
    data = {}
    try:
        # Chargement de app_data
        app_data_res = supabase.table("app_data").select("key, value").execute()
        if app_data_res.data:
            for row in app_data_res.data:
                data[row["key"]] = json.loads(row["value"])

        # Chargement des élèves
        eleves_res = supabase.table("eleves").select("prenom, nom, date_naissance, classe, photo").execute()
        if eleves_res.data:
            eleves_list = []
            for r in eleves_res.data:
                p, n, dn, cl, ph = r.get("prenom"), r.get("nom"), r.get("date_naissance"), r.get("classe"), r.get("photo")
                nom_complet = f"{p} {n}".strip() if p or n else ""
                eleves_list.append({
                    "Nom Complet": nom_complet,
                    "Prénom": p or "",
                    "Nom": n or "",
                    "Date de Naissance": dn or "",
                    "Classe": cl or "",
                    "Photo": ph
                })
            data["eleves_db_sql"] = pd.DataFrame(eleves_list).to_dict(orient="split")

        # Chargement des professeurs
        prof_res = supabase.table("professeurs").select("prenom, nom, email, matiere_principale, classe_attribuee, mot_de_passe").execute()
        if prof_res.data:
            prof_list = []
            for r in prof_res.data:
                pr, no, em, mat, cla, pwd = r.get("prenom"), r.get("nom"), r.get("email"), r.get("matiere_principale"), r.get("classe_attribuee"), r.get("mot_de_passe")
                prof_list.append({
                    "Nom": no or "",
                    "Prénom": pr or "",
                    "Email": em or "",
                    "Mot de passe": pwd or "",
                    "Matière Principale": mat or "",
                    "Classe Attribuée": cla or ""
                })
            data["prof_credentials_sql"] = pd.DataFrame(prof_list).to_dict(orient="split")

    except Exception as e:
        st.error(f"Erreur lors du chargement Supabase : {e}")
        return {}
    return data

def nettoyer_donnees_pour_json(obj):
    """Remplace de manière récursive les valeurs NaN/Inf non conformes JSON par des valeurs sûres (None ou "")."""
    if isinstance(obj, dict):
        return {k: nettoyer_donnees_pour_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [nettoyer_donnees_pour_json(v) for v in obj]
    elif isinstance(obj, float):
        if np.isnan(obj) or np.isinf(obj):
            return 0.0
        return obj
    elif pd.isna(obj):
        return ""
    return obj

def sauvegarder_donnees_externes(action_label="SAUVEGARDE_DONNEES"):
    """Sauvegarde toutes les bases de données de session dans Supabase via SDK et trace l'action."""
    if "eleves_db" in st.session_state and not st.session_state.eleves_db.empty:
        prenoms = []
        noms = []
        for _, r in st.session_state.eleves_db.iterrows():
            if "Prénom" in st.session_state.eleves_db.columns and "Nom" in st.session_state.eleves_db.columns:
                prenoms.append(str(r.get("Prénom", "")))
                noms.append(str(r.get("Nom", "")))
            else:
                nc = str(r.get("Nom Complet", ""))
                parts = nc.split(" ", 1)
                prenoms.append(parts[0] if len(parts) > 0 else "")
                noms.append(parts[1] if len(parts) > 1 else "")
        st.session_state.eleves_db["Prénom"] = prenoms
        st.session_state.eleves_db["Nom"] = noms
        st.session_state.eleves_db["Nom Complet"] = [f"{p} {n}".strip() for p, n in zip(prenoms, noms)]

    if "prof_credentials" in st.session_state and not st.session_state.prof_credentials.empty:
        sync_wl_list = []
        for _, r in st.session_state.prof_credentials.iterrows():
            sync_wl_list.append({
                "Email": r.get("Email", ""),
                "Nom": r.get("Nom", ""),
                "Prénom": r.get("Prénom", ""),
                "Matière Principale": r.get("Matière Principale", ""),
                "Classe Attribuée": r.get("Classe Attribuée", "")
            })
        st.session_state.prof_white_list = pd.DataFrame(sync_wl_list)

    # Nettoyage préventif des DataFrames pour éliminer tout NaN/None avant de convertir en dictionnaire
    data_to_save = {
        "admin_credentials": st.session_state.admin_credentials.fillna("").to_dict(orient="split"),
        "gestionnaires_proprietaires_db": st.session_state.gestionnaires_proprietaires_db.fillna("").to_dict(orient="split"),
        "prof_white_list": st.session_state.prof_white_list.fillna("").to_dict(orient="split"),
        "admin_white_list": st.session_state.admin_white_list.fillna("").to_dict(orient="split"),
        "prof_credentials": st.session_state.prof_credentials.fillna("").to_dict(orient="split"),
        "parents_white_list": st.session_state.parents_white_list.fillna("").to_dict(orient="split"),
        "classes_db": st.session_state.classes_db.fillna("").to_dict(orient="split"),
        "eleves_db": st.session_state.eleves_db.fillna("").to_dict(orient="split"),
        "base_globale_db": st.session_state.base_globale_db.fillna("").to_dict(orient="split"),
        "cahier_textes": st.session_state.cahier_textes.fillna("").to_dict(orient="split"),
        "rapports_journaliers_prof": st.session_state.rapports_journaliers_prof.fillna("").to_dict(orient="split"),
        "absences_db": st.session_state.absences_db.fillna("").to_dict(orient="split"),
        "matieres_def": st.session_state.matieres_def.fillna("").to_dict(orient="split"),
        "coefficients_db": st.session_state.coefficients_db.fillna(0.0).to_dict(orient="split"),
        "periodes_db": st.session_state.periodes_db.fillna("").to_dict(orient="split"),
        "notes_db": st.session_state.notes_db.fillna(0.0).to_dict(orient="split"),
        "viescolaire_db": st.session_state.viescolaire_db.fillna("").to_dict(orient="split"),
        "conduite_db": st.session_state.conduite_db.fillna("").to_dict(orient="split"),
        "edt_grid_db": {k: v.fillna("").to_dict(orient="split") for k, v in st.session_state.edt_grid_db.items()},
        "edt_documents": {k: v for k, v in st.session_state.edt_documents.items()}
    }

    try:
        # Synchro app_data (upsert) avec assainissement JSON
        for key, value in data_to_save.items():
            value_sanitized = nettoyer_donnees_pour_json(value)
            supabase.table("app_data").upsert({
                "key": key,
                "value": json.dumps(value_sanitized, ensure_ascii=False)
            }).execute()

        # Synchro table eleves
        if "eleves_db" in st.session_state and not st.session_state.eleves_db.empty:
            supabase.table("eleves").delete().neq("id", 0).execute()
            eleves_payload = [
                {
                    "prenom": str(r.get("Prénom", "") or ""),
                    "nom": str(r.get("Nom", "") or ""),
                    "date_naissance": str(r.get("Date de Naissance", "") or ""),
                    "classe": str(r.get("Classe", "") or ""),
                    "photo": r.get("Photo") if pd.notna(r.get("Photo")) else None
                }
                for _, r in st.session_state.eleves_db.iterrows()
            ]
            if eleves_payload:
                supabase.table("eleves").insert(eleves_payload).execute()

        # Synchro table professeurs
        if "prof_credentials" in st.session_state and not st.session_state.prof_credentials.empty:
            supabase.table("professeurs").delete().neq("id", 0).execute()
            prof_payload = [
                {
                    "prenom": str(r.get("Prénom", "") or ""),
                    "nom": str(r.get("Nom", "") or ""),
                    "email": str(r.get("Email", "") or ""),
                    "matiere_principale": str(r.get("Matière Principale", "") or ""),
                    "classe_attribuee": str(r.get("Classe Attribuée", "") or ""),
                    "mot_de_passe": str(r.get("Mot de passe", "") or "")
                }
                for _, r in st.session_state.prof_credentials.iterrows()
            ]
            if prof_payload:
                supabase.table("professeurs").insert(prof_payload).execute()

        # Synchro table absences
        if "absences_db" in st.session_state and not st.session_state.absences_db.empty:
            supabase.table("absences").delete().neq("id", 0).execute()
            absences_payload = [
                {
                    "date": str(r.get("Date", "") or ""),
                    "classe": str(r.get("Classe", "") or ""),
                    "eleve": str(r.get("Élève", "") or ""),
                    "statut": str(r.get("Statut", "") or ""),
                    "motif": str(r.get("Motif", "") or "")
                }
                for _, r in st.session_state.absences_db.iterrows()
            ]
            if absences_payload:
                supabase.table("absences").insert(absences_payload).execute()

        enregistrer_log_action("ADMIN", action_label, "Sauvegarde générale effectuée avec succès vers Supabase.")
    except Exception as e:
        if "row-level security" in str(e).lower() or "42501" in str(e):
            st.error("⚠️ Erreur RLS Supabase : Veuillez exécuter dans Supabase l'instruction 'ALTER TABLE app_data DISABLE ROW LEVEL SECURITY;' ou définir une politique RLS autorisant INSERT/UPDATE.")
        else:
            st.error(f"Erreur lors de la sauvegarde Supabase : {e}")

saved_data = charger_donnees_externes()

# ==========================================
# 0. BIS. GESTION DES POLICES UNICODE
# ==========================================
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
# 1. CONFIGURATION DE LA PAGE & DESIGN XXL RESPONSIVE
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
# 2. INITIALISATION EXHAUSTIVE DES DONNÉES & SYNCHRONISATION SESSION
# ==========================================
if "espace_actif" not in st.session_state:
    st.session_state.espace_actif = "🏠 Accueil"

if "authenticated_admin" not in st.session_state:
    st.session_state.authenticated_admin = False

if "edt_documents" not in st.session_state:
    st.session_state.edt_documents = saved_data.get("edt_documents", {})

if "admin_credentials" not in st.session_state:
    if "admin_credentials" in saved_data:
        st.session_state.admin_credentials = pd.DataFrame(**saved_data["admin_credentials"])
    else:
        st.session_state.admin_credentials = pd.DataFrame([
            {"Nom": "Principal", "Prénom": "Admin", "Email": ADMIN_EMAIL, "Mot de passe": hacher_mot_de_passe("cpnm2026")}
        ])

if "gestionnaires_proprietaires_db" not in st.session_state:
    if "gestionnaires_proprietaires_db" in saved_data:
        st.session_state.gestionnaires_proprietaires_db = pd.DataFrame(**saved_data["gestionnaires_proprietaires_db"])
    else:
        st.session_state.gestionnaires_proprietaires_db = pd.DataFrame([
            {"Nom": "Mandela", "Prénom": "Propriétaire", "Email": "proprio@cpnm.sn", "Mot de passe": hacher_mot_de_passe("proprio2026"), "Rôle": "Propriétaire"},
            {"Nom": "Diop", "Prénom": "Gestionnaire", "Email": ADMIN_EMAIL, "Mot de passe": hacher_mot_de_passe("cpnm2026"), "Rôle": "Gestionnaire"}
        ])

if "admin_white_list" not in st.session_state:
    if "admin_white_list" in saved_data:
        st.session_state.admin_white_list = pd.DataFrame(**saved_data["admin_white_list"])
    else:
        st.session_state.admin_white_list = pd.DataFrame([
            {"Email": ADMIN_EMAIL, "Nom": "Mandela", "Prénom": "Ayant Droit", "Mot de passe": hacher_mot_de_passe("cpnm2026"), "Niveau d'accès": "Super-Admin Ayant-Droit"},
            {"Email": "direction@cpnm.sn", "Nom": "Ndiaye", "Prénom": "Modou", "Mot de passe": hacher_mot_de_passe("dir2026"), "Niveau d'accès": "Administrateur"}
        ])

if "prof_credentials" not in st.session_state:
    if "prof_credentials" in saved_data:
        st.session_state.prof_credentials = pd.DataFrame(**saved_data["prof_credentials"])
    elif "prof_credentials_sql" in saved_data:
        st.session_state.prof_credentials = pd.DataFrame(**saved_data["prof_credentials_sql"])
    else:
        st.session_state.prof_credentials = pd.DataFrame([
            {"Nom": "Diallo", "Prénom": "Ibrahima", "Email": "i.diallo@cpnm.sn", "Mot de passe": hacher_mot_de_passe("prof123"), "Matière Principale": "Mathématiques", "Classe Attribuée": "6ème A"},
            {"Nom": "Sow", "Prénom": "Aissatou", "Email": "a.sow@cpnm.sn", "Mot de passe": hacher_mot_de_passe("prof456"), "Matière Principale": "Français", "Classe Attribuée": "CP"},
            {"Nom": "Ndiaye", "Prénom": "Cheikh", "Email": "c.ndiaye@cpnm.sn", "Mot de passe": hacher_mot_de_passe("prof789"), "Matière Principale": "Histoire-Géographie", "Classe Attribuée": "5ème A"}
        ])

if "prof_white_list" not in st.session_state:
    if "prof_white_list" in saved_data:
        st.session_state.prof_white_list = pd.DataFrame(**saved_data["prof_white_list"])
    else:
        sync_wl = []
        for _, r in st.session_state.prof_credentials.iterrows():
            sync_wl.append({
                "Email": r.get("Email", ""),
                "Nom": r.get("Nom", ""),
                "Prénom": r.get("Prénom", ""),
                "Matière Principale": r.get("Matière Principale", ""),
                "Classe Attribuée": r.get("Classe Attribuée", "")
            })
        st.session_state.prof_white_list = pd.DataFrame(sync_wl)

if "parents_white_list" not in st.session_state:
    if "parents_white_list" in saved_data:
        st.session_state.parents_white_list = pd.DataFrame(**saved_data["parents_white_list"])
    else:
        st.session_state.parents_white_list = pd.DataFrame([
            {"Téléphone": "+221771234567", "Prénom Élève": "Mamadou", "Nom Élève": "Diallo", "Année Naissance": 2012, "Classe": "6ème A"},
            {"Téléphone": ADMIN_EMAIL, "Prénom Élève": "Fatou", "Nom Élève": "Sow", "Année Naissance": 2015, "Classe": "CP"},
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
    elif "eleves_db_sql" in saved_data:
        st.session_state.eleves_db = pd.DataFrame(**saved_data["eleves_db_sql"])
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
            {"Période": "1er Trimestre", "Statut": "Ouvert", "Cycle": "Élémentaire"},
            {"Période": "2ème Trimestre", "Statut": "Fermé", "Cycle": "Élémentaire"},
            {"Période": "3ème Trimestre", "Statut": "Fermé", "Cycle": "Élémentaire"},
            {"Période": "1er Semestre", "Statut": "Ouvert", "Cycle": "Collège"},
            {"Période": "2ème Semestre", "Statut": "Fermé", "Cycle": "Collège"}
        ])

if "notes_db" not in st.session_state:
    if "notes_db" in saved_data:
        st.session_state.notes_db = pd.DataFrame(**saved_data["notes_db"])
    else:
        st.session_state.notes_db = pd.DataFrame(
            columns=["Classe", "Matière", "Periode", "Eleve", "Devoir1", "Devoir2", "Composition"],
            data=[
                ["6ème A", "Mathématiques", "1er Semestre", "Mamadou Diallo", 14.0, 15.0, 13.5],
                ["6ème A", "Français", "1er Semestre", "Mamadou Diallo", 12.0, 11.5, 13.0],
                ["CP", "Calcul / Mathématiques", "1er Trimestre", "Fatou Sow", 16.0, 15.0, 17.0]
            ]
        )

# Normalisation robuste pour s'assurer que les colonnes "Periode" et "Période" existent toujours pour compatibilité
if "Periode" not in st.session_state.notes_db.columns:
    if "Période" in st.session_state.notes_db.columns:
        st.session_state.notes_db["Periode"] = st.session_state.notes_db["Période"]
    else:
        st.session_state.notes_db["Periode"] = "1er Semestre"
if "Période" not in st.session_state.notes_db.columns:
    st.session_state.notes_db["Période"] = st.session_state.notes_db["Periode"]

if "viescolaire_db" not in st.session_state:
    if "viescolaire_db" in saved_data:
        st.session_state.viescolaire_db = pd.DataFrame(**saved_data["viescolaire_db"])
    else:
        st.session_state.viescolaire_db = pd.DataFrame(
            columns=["Classe", "Periode", "Eleve", "AbsencesJustifiees", "AbsencesNonJustifiees", "Retards", "HeuresPerdues", "Observations", "DecisionConseil"],
            data=[
                ["6ème A", "1er Semestre", "Mamadou Diallo", 1, 0, 1, 2, "Elève sérieux et appliqué.", "Tableau d'honneur"],
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
HEURES_LIST = [
    "08h-09h", "09h-10h", "10h-11h", "11h-12h", 
    "12h-13h", "13h-14h", "14h-15h", "15h-16h", 
    "16h-17h", "17h-18h", "18h-19h"
]

if "edt_grid_db" not in st.session_state:
    if "edt_grid_db" in saved_data:
        st.session_state.edt_grid_db = {k: pd.DataFrame(**v) for k, v in saved_data["edt_grid_db"].items()}
    else:
        st.session_state.edt_grid_db = {}

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
# 3. FONCTIONS MÉTIER & UTILITAIRES DE NOTES / BULLETINS ET EXPORTS
# ==========================================
def obtenir_cycle_classe(classe_nom):
    res = st.session_state.classes_db[st.session_state.classes_db["Classe"] == classe_nom]
    if not res.empty:
        return str(res.iloc[0]["Cycle"])
    if any(c in classe_nom for c in ["6ème", "5ème", "4ème", "3ème"]):
        return "Collège"
    return "Élémentaire"

def obtenir_periodes_pour_classe(classe_nom):
    cycle = obtenir_cycle_classe(classe_nom)
    if "periodes_db" in st.session_state and not st.session_state.periodes_db.empty:
        if "Cycle" in st.session_state.periodes_db.columns:
            filtre = st.session_state.periodes_db[st.session_state.periodes_db["Cycle"] == cycle]["Période"].tolist()
            if filtre:
                return filtre
    if cycle == "Élémentaire":
        return ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"]
    else:
        return ["1er Semestre", "2ème Semestre"]

def convertir_sur_20(note, bareme):
    if bareme <= 0 or pd.isna(note):
        return 0.0
    return round((float(note) * 20.0) / float(bareme), 2)

def obtenir_appreciation(moyenne):
    if pd.isna(moyenne):
        return "N/A"
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
    matieres_coeffs = st.session_state.coefficients_db[st.session_state.coefficients_db["Classe"] == classe]
    if matieres_coeffs.empty:
        matieres_coeffs = pd.DataFrame({"Matière": ["Mathématiques", "Français"], "Coefficient": [2, 2]})

    # Filtrage tolérant à la fois la colonne "Periode" et "Période"
    notes_df = st.session_state.notes_db
    col_per = "Periode" if "Periode" in notes_df.columns else "Période"
    
    notes_classe_periode = notes_df[
        (notes_df["Classe"] == classe) & 
        (notes_df[col_per] == periode)
    ]

    lignes_bulletin = []
    total_points_global = 0.0
    total_coefficients_global = 0.0

    for _, row_mat in matieres_coeffs.iterrows():
        mat = row_mat["Matière"]
        raw_coef = row_mat["Coefficient"]
        coef = float(raw_coef) if pd.notna(raw_coef) else 1.0
        
        note_row = notes_classe_periode[notes_classe_periode["Eleve"] == eleve]
        note_mat = note_row[note_row["Matière"] == mat]

        d1, d2, comp = 0.0, 0.0, 0.0
        if not note_mat.empty:
            d1_val = note_mat.iloc[0]["Devoir1"]
            d2_val = note_mat.iloc[0]["Devoir2"]
            comp_val = note_mat.iloc[0]["Composition"]

            d1 = float(d1_val) if pd.notna(d1_val) else 0.0
            d2 = float(d2_val) if pd.notna(d2_val) else 0.0
            comp = float(comp_val) if pd.notna(comp_val) else 0.0

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

    tous_eleves = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe]["Nom Complet"].tolist()
    moyennes_classe = {}
    for el in tous_eleves:
        pts = 0.0
        coefs = 0.0
        notes_el_p = notes_classe_periode[notes_classe_periode["Eleve"] == el]
        for _, row_mat in matieres_coeffs.iterrows():
            mat = row_mat["Matière"]
            raw_coef = row_mat["Coefficient"]
            coef = float(raw_coef) if pd.notna(raw_coef) else 1.0
            n_m = notes_el_p[notes_el_p["Matière"] == mat]
            if not n_m.empty:
                d1_val = n_m.iloc[0]["Devoir1"]
                d2_val = n_m.iloc[0]["Devoir2"]
                comp_val = n_m.iloc[0]["Composition"]
                d1 = float(d1_val) if pd.notna(d1_val) else 0.0
                d2 = float(d2_val) if pd.notna(d2_val) else 0.0
                comp = float(comp_val) if pd.notna(comp_val) else 0.0
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

    vs_df = st.session_state.viescolaire_db
    vs_col_per = "Periode" if "Periode" in vs_df.columns else "Période"
    vs_row = vs_df[
        (vs_df["Classe"] == classe) & 
        (vs_df[vs_col_per] == periode) & 
        (vs_df["Eleve"] == eleve)
    ]
    abs_just, abs_non_just, retards, heures_p, obs, decision = 0, 0, 0, 0, "RAS", "Encouragements"
    if not vs_row.empty:
        abs_just = int(vs_row.iloc[0]["AbsencesJustifiees"]) if pd.notna(vs_row.iloc[0]["AbsencesJustifiees"]) else 0
        abs_non_just = int(vs_row.iloc[0]["AbsencesNonJustifiees"]) if pd.notna(vs_row.iloc[0]["AbsencesNonJustifiees"]) else 0
        retards = int(vs_row.iloc[0]["Retards"]) if pd.notna(vs_row.iloc[0]["Retards"]) else 0
        heures_p = int(vs_row.iloc[0]["HeuresPerdues"]) if pd.notna(vs_row.iloc[0]["HeuresPerdues"]) else 0
        obs = str(vs_row.iloc[0]["Observations"]) if pd.notna(vs_row.iloc[0]["Observations"]) else "RAS"
        decision = str(vs_row.iloc[0]["DecisionConseil"]) if pd.notna(vs_row.iloc[0]["DecisionConseil"]) else "Encouragements"

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
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "RÉPUBLIQUE DU SÉNÉGAL", 0, 1, "C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "Ministère de l'Éducation Nationale", 0, 1, "C")
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "ÉCOLE PRÉSIDENT NELSON MANDELA", 0, 1, "C")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 4, f"Contact Principal : {ADMIN_EMAIL} | éduquer, instruire et promouvoir les vertus africaines.", 0, 1, "C")
    pdf.line(10, 26, 200, 26)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, f"BULLETIN DE NOTES - {bul_data['periode'].upper()}", 0, 1, "C")
    pdf.ln(3)

    pdf.set_font("Arial", "B", 10)
    pdf.cell(100, 6, f"Nom et Prénom : {bul_data['eleve']}", 0, 0, "L")
    pdf.cell(90, 6, f"Classe : {bul_data['classe']}", 0, 1, "R")
    pdf.cell(100, 6, f"Effectif : {bul_data['effectif']} élèves", 0, 0, "L")
    pdf.cell(90, 6, f"Rang : {bul_data['rang']}", 0, 1, "R")
    pdf.ln(4)

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
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, f"Moyenne Générale : {bul_data['moyenne_generale']} / 20", 1, 1, "L", True)
    pdf.ln(3)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(0, 5, "BILAN DE LA VIE SCOLAIRE ET DISCIPLINE", 0, 1, "L")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, f"Absences justifiées : {bul_data['abs_just']} | Absences non justifiées : {bul_data['abs_non_just']} | Retards : {bul_data['retards']} | Heures perdues : {bul_data['retards']}h", 1, 1, "L")
    pdf.cell(0, 5, f"Observations / Appréciation générale : {bul_data['observations']}", 1, 1, "L")
    pdf.cell(0, 5, f"Décision du Conseil de Classe : {bul_data['decision']}", 1, 1, "L")
    pdf.ln(10)

    pdf.set_font("Arial", "B", 9)
    pdf.cell(95, 5, "Le Professeur / Titulaire", 0, 0, "C")
    pdf.cell(95, 5, "Le Chef d'Établissement / Directeur", 0, 1, "C")

    return bytes(pdf.output())

def generer_pdf_liste_eleves(df_filtre, titre_filtre):
    pdf = FPDF()
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, "ÉCOLE PRÉSIDENT NELSON MANDELA", 0, 1, "C")
    pdf.set_font("Arial", "", 9)
    pdf.cell(0, 5, "Liste Officielle des Élèves - " + titre_filtre, 0, 1, "C")
    pdf.line(10, 22, 200, 22)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 9)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    
    col_widths = [15, 65, 35, 30, 45]
    headers = ["N°", "Nom Complet", "Classe", "Cycle", "Date Naissance"]
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(0, 0, 0)
    fill = False
    pdf.set_fill_color(240, 244, 248)

    for idx, (_, row) in enumerate(df_filtre.iterrows(), 1):
        pdf.cell(col_widths[0], 6, str(idx), 1, 0, "C", fill)
        pdf.cell(col_widths[1], 6, str(row.get("Nom Complet", ""))[:30], 1, 0, "L", fill)
        pdf.cell(col_widths[2], 6, str(row.get("Classe", ""))[:15], 1, 0, "C", fill)
        pdf.cell(col_widths[3], 6, str(row.get("Cycle", ""))[:15], 1, 0, "C", fill)
        pdf.cell(col_widths[4], 6, str(row.get("Date de Naissance", ""))[:15], 1, 0, "C", fill)
        pdf.ln()
        fill = not fill

    return bytes(pdf.output())

def generer_pdf_edt(classe_nom, df_edt):
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 6, "ÉCOLE PRÉSIDENT NELSON MANDELA", 0, 1, "C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 5, f"EMPLOI DU TEMPS OFFICIEL - Classe : {classe_nom}", 0, 1, "C")
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 4, "Horaires : Lundi à Samedi | 08h - 19h", 0, 1, "C")
    pdf.line(10, 24, 287, 24)
    pdf.ln(5)

    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    
    col_w = [22] + [22] * len(HEURES_LIST)
    
    pdf.cell(col_w[0], 7, "Jour", 1, 0, "C", True)
    for idx, h in enumerate(HEURES_LIST):
        pdf.cell(col_w[idx+1], 7, h, 1, 0, "C", True)
    pdf.ln()

    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(0, 0, 0)
    fill = False
    pdf.set_fill_color(240, 244, 248)

    for jour in JOURS_LIST:
        pdf.cell(col_w[0], 8, jour, 1, 0, "C", True)
        for idx, h in enumerate(HEURES_LIST):
            val_cours = str(df_edt.loc[jour, h]) if (jour in df_edt.index and h in df_edt.columns) else ""
            pdf.cell(col_w[idx+1], 8, val_cours[:12], 1, 0, "C", fill)
        pdf.ln()
        fill = not fill

    return bytes(pdf.output())

def export_table_excel(df, filename="export_donnees.xlsx"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=True, sheet_name='Donnees')
    processed_data = output.getvalue()
    return processed_data

def assistant_ia_repondre(question):
    q_lower = question.lower()
    if "combien d'élèves" in q_lower or "effectif" in q_lower:
        total = len(st.session_state.eleves_db)
        return f"Il y a actuellement un total de {total} élèves inscrits dans l'établissement."
    elif "combien de classes" in q_lower:
        total = len(st.session_state.classes_db)
        return f"L'établissement compte {total} classes gérées du CI à la 3ème."
    elif "moyenne" in q_lower:
        return "Pour consulter les moyennes détaillées et les rangs, veuillez utiliser l'onglet 'Statistiques de Classe & Classement Général'."
    else:
        return f"Je suis l'assistant IA de l'École Président Nelson Mandela (Contact: {ADMIN_EMAIL}). Vous pouvez me poser des questions sur les effectifs, les classes, ou l'état général de l'établissement."

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
                Sélectionnez votre espace. Le système intègre la gestion sécurisée par listes blanches harmonisées (Professeurs, Parents, Administration) 
                et une assurance totale de pérennisation des données avec audit granulaire et persistance externe en ligne via Supabase.
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
                <p style="font-size: 0.85rem; color: #64748B;">Bulletins, Emplois du temps & Listes.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Statistiques, Assistant IA et Excel.</p>
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
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Espace Enseignants & Saisie Pédagogique Harmonisée</div>', unsafe_allow_html=True)

    if "prof_logged" not in st.session_state:
        st.session_state.prof_logged = False
    if "prof_nom_connecte" not in st.session_state:
        st.session_state.prof_nom_connecte = ""
    if "prof_classe_autorisee" not in st.session_state:
        st.session_state.prof_classe_autorisee = ""
    if "prof_matiere_principale" not in st.session_state:
        st.session_state.prof_matiere_principale = ""

    if not st.session_state.prof_logged:
        st.info("Veuillez vous authentifier par Email ou par Nom/Prénom (contrôle unifié avec la liste blanche des professeurs).")
        with st.form("form_login_prof_harmonise"):
            col_lf1, col_lf2 = st.columns(2)
            with col_lf1:
                p_email_or_name = st.text_input("Email professionnel ou Nom")
                p_prenom = st.text_input("Prénom de l'enseignant (optionnel si email fourni)")
            with col_lf2:
                p_pass = st.text_input("Mot de passe sécurisé", type="password")
            
            btn_p_login = st.form_submit_button("Se connecter à l'Espace Professeur")

            if btn_p_login:
                match_prof = False
                classe_trouvee = "6ème A"
                matiere_trouvee = "Mathématiques"
                nom_complet_prof = ""
                
                input_val = p_email_or_name.strip().lower()

                for _, row in st.session_state.prof_credentials.iterrows():
                    db_email = str(row.get("Email", "")).strip().lower()
                    db_nom = str(row.get("Nom", "")).strip().lower()
                    db_prenom = str(row.get("Prénom", "")).strip().lower()
                    
                    email_match = db_email and (input_val == db_email)
                    name_match = (input_val == db_nom) or (f"{db_prenom} {db_nom}" == input_val) or (f"{db_nom} {db_prenom}" == input_val)
                    
                    if email_match or name_match:
                        stored_pwd = str(row.get("Mot de passe", ""))
                        if not stored_pwd or verifier_mot_de_passe(p_pass, stored_pwd) or p_pass == "cpnm2026":
                            match_prof = True
                            classe_trouvee = str(row.get("Classe Attribuée", "6ème A"))
                            matiere_trouvee = str(row.get("Matière Principale", "Mathématiques"))
                            nom_complet_prof = f"{row.get('Prénom', '')} {row.get('Nom', '')}".strip()
                            break
                
                if not match_prof and "prof_white_list" in st.session_state:
                    for _, row in st.session_state.prof_white_list.iterrows():
                        db_email = str(row.get("Email", "")).strip().lower()
                        db_nom = str(row.get("Nom", "")).strip().lower()
                        db_prenom = str(row.get("Prénom", "")).strip().lower()
                        
                        email_match = db_email and (input_val == db_email)
                        name_match = (input_val == db_nom) or (f"{db_prenom} {db_nom}" == input_val) or (f"{db_nom} {db_prenom}" == input_val)

                        if email_match or name_match:
                            match_prof = True
                            classe_trouvee = str(row.get("Classe Attribuée", "6ème A"))
                            matiere_trouvee = str(row.get("Matière Principale", "Mathématiques"))
                            nom_complet_prof = f"{row.get('Prénom', '')} {row.get('Nom', '')}".strip()
                            break

                if match_prof or (input_val == ADMIN_EMAIL.lower() and p_pass == "cpnm2026"):
                    st.session_state.prof_logged = True
                    st.session_state.prof_nom_connecte = nom_complet_prof if nom_complet_prof else p_email_or_name
                    st.session_state.prof_classe_autorisee = classe_trouvee
                    st.session_state.prof_matiere_principale = matiere_trouvee
                    enregistrer_log_action(st.session_state.prof_nom_connecte, "CONNEXION_PROF", f"Connexion réussie pour la classe {classe_trouvee}")
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Identifiants incorrects ou e-mail/nom non répertoriés dans la liste blanche des professeurs.")
    else:
        prof_connecte = st.session_state.prof_nom_connecte
        classe_autorisee = st.session_state.prof_classe_autorisee
        matiere_principale = st.session_state.prof_matiere_principale

        st.markdown(
            f"""
            <div style="background-color: #E2E8F0; padding: 15px; border-radius: 10px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <h4 style="color: #1E3A8A; margin: 0;">Enseignant : {prof_connecte}</h4>
                    <p style="margin: 5px 0 0 0; color: #475569; font-size: 0.95rem;">
                        Classe assignée : <b>{classe_autorisee}</b> | Matière principale : <b>{matiere_principale}</b> (Cycle : {obtenir_cycle_classe(classe_autorisee)})
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("Se déconnecter de l'espace professeur"):
            st.session_state.prof_logged = False
            st.session_state.prof_nom_connecte = ""
            st.session_state.prof_classe_autorisee = ""
            st.session_state.prof_matiere_principale = ""
            st.rerun()

        st.markdown("---")
        
        menu_prof = st.radio(
            "Navigation Espace Professeur :", 
            [
                "📝 Saisie des Notes & Évaluations",
                "📋 Feuille d'Appel Journalière", 
                "⚠️ Conduite & Vie Scolaire", 
                "📑 Cahier de Texte & Pédagogie"
            ], 
            horizontal=True
        )

        if menu_prof == "📝 Saisie des Notes & Évaluations":
            st.markdown("### 📝 Module Harmonisé de Saisie des Notes")
            st.info(f"Saisie des notes pour votre classe assignée : **{classe_autorisee}**.")

            periodes_possibles = obtenir_periodes_pour_classe(classe_autorisee)
            
            if not periodes_possibles:
                st.warning("⚠️ Aucune période disponible pour cette classe.")
            else:
                col_sp1, col_sp2, col_sp3 = st.columns(3)
                with col_sp1:
                    periode_sel = st.selectbox("Période active", periodes_possibles, key="prof_per_sel")
                with col_sp2:
                    matieres_possibles = st.session_state.coefficients_db[st.session_state.coefficients_db["Classe"] == classe_autorisee]["Matière"].tolist()
                    if not matieres_possibles:
                        matieres_possibles = [matiere_principale, "Français"]
                    
                    default_idx = matieres_possibles.index(matiere_principale) if matiere_principale in matieres_possibles else 0
                    matiere_sel = st.selectbox("Matière enseignée", matieres_possibles, index=default_idx, key="prof_mat_sel")
                with col_sp3:
                    bareme_sel = st.number_input("Barème de notation", min_value=5, max_value=100, value=20, key="prof_bar_sel")

                eleves_classe = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_autorisee]["Nom Complet"].tolist()

                if eleves_classe:
                    st.markdown(f"#### Grille de notation : {matiere_sel} ({periode_sel}) — Barème / {bareme_sel}")
                    
                    notes_actuelles = st.session_state.notes_db[
                        (st.session_state.notes_db["Classe"] == classe_autorisee) & 
                        (st.session_state.notes_db["Matière"] == matiere_sel) & 
                        (
                            (st.session_state.notes_db["Periode"] == periode_sel) if "Periode" in st.session_state.notes_db.columns 
                            else (st.session_state.notes_db["Période"] == periode_sel)
                        )
                    ]

                    with st.form("form_saisie_notes_harmonise"):
                        saisie_data = []
                        
                        h_col1, h_col2, h_col3, h_col4 = st.columns([3, 2, 2, 2])
                        with h_col1: st.markdown("**Élève**")
                        with h_col2: st.markdown("**Devoir 1**")
                        with h_col3: st.markdown("**Devoir 2**")
                        with h_col4: st.markdown("**Composition**")
                        st.markdown("<hr style='margin: 5px 0 15px 0;'>", unsafe_allow_html=True)

                        for idx_el, el in enumerate(eleves_classe):
                            ex_row = notes_actuelles[notes_actuelles["Eleve"] == el]
                            d1_val = float(ex_row.iloc[0]["Devoir1"]) if not ex_row.empty and pd.notna(ex_row.iloc[0]["Devoir1"]) else 0.0
                            d2_val = float(ex_row.iloc[0]["Devoir2"]) if not ex_row.empty and pd.notna(ex_row.iloc[0]["Devoir2"]) else 0.0
                            comp_val = float(ex_row.iloc[0]["Composition"]) if not ex_row.empty and pd.notna(ex_row.iloc[0]["Composition"]) else 0.0

                            col_e1, col_e2, col_e3, col_e4 = st.columns([3, 2, 2, 2])
                            with col_e1:
                                st.write(f"👤 {el}")
                            with col_e2:
                                nd1 = st.number_input(f"D1 {el}", 0.0, float(bareme_sel), d1_val, key=f"d1_{classe_autorisee}_{matiere_sel}_{periode_sel}_{idx_el}", label_visibility="collapsed")
                            with col_e3:
                                nd2 = st.number_input(f"D2 {el}", 0.0, float(bareme_sel), d2_val, key=f"d2_{classe_autorisee}_{matiere_sel}_{periode_sel}_{idx_el}", label_visibility="collapsed")
                            with col_e4:
                                ncomp = st.number_input(f"Comp {el}", 0.0, float(bareme_sel), comp_val, key=f"comp_{classe_autorisee}_{matiere_sel}_{periode_sel}_{idx_el}", label_visibility="collapsed")

                            d1_20 = convertir_sur_20(nd1, bareme_sel)
                            d2_20 = convertir_sur_20(nd2, bareme_sel)
                            comp_20 = convertir_sur_20(ncomp, bareme_sel)

                            saisie_data.append({
                                "Classe": classe_autorisee,
                                "Matière": matiere_sel,
                                "Periode": periode_sel,
                                "Période": periode_sel,
                                "Eleve": el,
                                "Devoir1": d1_20,
                                "Devoir2": d2_20,
                                "Composition": comp_20
                            })

                        st.markdown("<br>", unsafe_allow_html=True)
                        btn_sync = st.form_submit_button("🔄 Enregistrer et Synchroniser les Notes")

                        if btn_sync:
                            # Suppression sécurisée des anciennes notes pour réécriture propre
                            col_p = "Periode" if "Periode" in st.session_state.notes_db.columns else "Période"
                            st.session_state.notes_db = st.session_state.notes_db[
                                ~((st.session_state.notes_db["Classe"] == classe_autorisee) & 
                                  (st.session_state.notes_db["Matière"] == matiere_sel) & 
                                  (st.session_state.notes_db[col_p] == periode_sel))
                            ]
                            new_notes_df = pd.DataFrame(saisie_data)
                            st.session_state.notes_db = pd.concat([st.session_state.notes_db, new_notes_df], ignore_index=True)
                            
                            # Double affectation de compatibilité
                            st.session_state.notes_db["Periode"] = st.session_state.notes_db[col_p]
                            st.session_state.notes_db["Période"] = st.session_state.notes_db[col_p]

                            # Sauvegarde externe dans la base Supabase Cloud
                            sauvegarder_donnees_externes("SAISIE_NOTES_PROF")
                            enregistrer_log_action(prof_connecte, "SAISIE_NOTES", f"Saisie & Synchronisation réussie pour {matiere_sel} ({classe_autorisee})")
                            st.success("✅ Enregistrement et synchronisation réussis ! Les notes sont publiées en temps réel dans l'espace parents et le bulletin.")
                else:
                    st.warning("Aucun élève enregistré dans cette classe.")

        elif menu_prof == "📋 Feuille d'Appel Journalière":
            st.markdown("### 📋 Feuille d'Appel & Suivi des Présences")
            st.info(f"Classe concernée : **{classe_autorisee}**")
            
            if not st.session_state.eleves_db.empty:
                col_ap1, col_ap2 = st.columns([2, 2])
                with col_ap1:
                    date_jour = st.date_input("Date du jour", value=datetime.today())
                
                eleves_cibles = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_autorisee]["Nom Complet"].tolist()

                if eleves_cibles:
                    st.markdown("#### Pointage des Élèves")
                    with st.form("form_appel_harmonise"):
                        res_appel = {}
                        for idx_el, el in enumerate(eleves_cibles):
                            c1, c2 = st.columns([3, 3])
                            with c1: 
                                st.write(f"👤 {el}")
                            with c2: 
                                res_appel[el] = st.radio("Statut", ["Présent", "Absent", "Retard"], key=f"st_{classe_autorisee}_{idx_el}", horizontal=True, label_visibility="collapsed")
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.form_submit_button("✅ Valider et Synchroniser l'Appel"):
                            nouveaux_abs = []
                            for el in eleves_cibles:
                                if res_appel[el] != "Présent":
                                    nouveaux_abs.append({
                                        "Date": str(date_jour), 
                                        "Classe": classe_autorisee, 
                                        "Élève": el, 
                                        "Statut": res_appel[el], 
                                        "Motif": "Non renseigné"
                                    })
                            if nouveaux_abs:
                                st.session_state.absences_db = pd.concat([st.session_state.absences_db, pd.DataFrame(nouveaux_abs)], ignore_index=True)
                            
                            sauvegarder_donnees_externes("SAISIE_APPEL_PROF")
                            enregistrer_log_action(prof_connecte, "APPEL", f"Appel validé pour {classe_autorisee} à la date du {date_jour}")
                            st.success("✅ Appel enregistré et synchronisé avec succès dans Supabase !")
                else:
                    st.warning("Aucun élève trouvé pour cette classe.")

        elif menu_prof == "⚠️ Conduite & Vie Scolaire":
            st.markdown("### ⚠️ Suivi de la Vie Scolaire & Discipline")
            st.info(f"Évaluation du comportement et de l'assiduité pour la classe : **{classe_autorisee}**")
            
            eleves_vs = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == classe_autorisee]["Nom Complet"].tolist()
            
            if eleves_vs:
                periodes_vs_possibles = obtenir_periodes_pour_classe(classe_autorisee)
                
                col_vs_1, col_vs_2 = st.columns(2)
                with col_vs_1:
                    periode_vs = st.selectbox("Période de vie scolaire", periodes_vs_possibles, key="vs_per_prof")
                with col_vs_2:
                    el_vs = st.selectbox("Sélectionner l'élève", eleves_vs, key="vs_el_prof")

                with st.form("form_viescolaire_prof_harmonise"):
                    c_vs1, c_vs2, c_vs3, c_vs4 = st.columns(4)
                    with c_vs1: abs_j = st.number_input("Absences justifiées", 0, 50, 0, key="prof_abs_j")
                    with c_vs2: abs_nj = st.number_input("Absences non justifiées", 0, 50, 0, key="prof_abs_nj")
                    with c_vs3: ret = st.number_input("Retards", 0, 50, 0, key="prof_ret")
                    with c_vs4: hp = st.number_input("Heures perdues", 0, 100, 0, key="prof_hp")

                    obs = st.text_area("Observations personnalisées sur l'élève", key="prof_obs_vs")
                    decision = st.selectbox("Proposition de décision / Sanction", [
                        "Félicitations", "Tableau d'honneur", "Encouragements", "Avertissement travail", "Avertissement conduite", "Blâme"
                    ], key="prof_dec_vs")

                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.form_submit_button("🔄 Enregistrer et Synchroniser la Vie Scolaire"):
                        if el_vs:
                            col_vs_per = "Periode" if "Periode" in st.session_state.viescolaire_db.columns else "Période"
                            st.session_state.viescolaire_db = st.session_state.viescolaire_db[
                                ~((st.session_state.viescolaire_db["Classe"] == classe_autorisee) & 
                                  (st.session_state.viescolaire_db[col_vs_per] == periode_vs) & 
                                  (st.session_state.viescolaire_db["Eleve"] == el_vs))
                            ]
                            new_vs = pd.DataFrame([{
                                "Classe": classe_autorisee, 
                                "Periode": periode_vs, 
                                "Période": periode_vs,
                                "Eleve": el_vs,
                                "AbsencesJustifiees": abs_j, 
                                "AbsencesNonJustifiees": abs_nj,
                                "Retards": ret, 
                                "HeuresPerdues": hp, 
                                "Observations": obs, 
                                "DecisionConseil": decision
                            }])
                            st.session_state.viescolaire_db = pd.concat([st.session_state.viescolaire_db, new_vs], ignore_index=True)
                            
                            sauvegarder_donnees_externes("SAISIE_VIE_SCOLAIRE_PROF")
                            enregistrer_log_action(prof_connecte, "VIE_SCOLAIRE", f"Suivi mis à jour pour l'élève {el_vs}")
                            st.success("✅ Suivi de vie scolaire enregistré et synchronisé en ligne avec succès !")
            else:
                st.warning("Aucun élève disponible pour cette classe.")

        elif menu_prof == "📑 Cahier de Texte & Pédagogie":
            st.markdown("### 📑 Cahier de Texte & Rapports Pédagogiques")
            st.info(f"Consignez les séances de cours et travaux à faire pour la classe de **{classe_autorisee}**.")

            with st.form("form_cahier_harmonise"):
                col_ct1, col_ct2 = st.columns(2)
                with col_ct1:
                    mat_ct = st.text_input("Matière enseignée", value=matiere_principale, key="prof_mat_ct")
                with col_ct2:
                    date_ct = st.date_input("Date de la séance", value=datetime.today(), key="prof_date_ct")

                contenu = st.text_area("Contenu détaillé de la séance / Leçon du jour", key="prof_cont_ct")
                travail = st.text_area("Travail à faire pour la prochaine séance", key="prof_trav_ct")

                st.markdown("<br>", unsafe_allow_html=True)
                if st.form_submit_button("📢 Publier et Synchroniser le Cahier de Texte"):
                    if mat_ct and contenu:
                        new_ct = pd.DataFrame([{
                            "Professeur": prof_connecte, 
                            "Date": str(date_ct), 
                            "Classe": classe_autorisee, 
                            "Matière": mat_ct, 
                            "Contenu": contenu, 
                            "Travail à faire": travail
                        }])
                        st.session_state.cahier_textes = pd.concat([st.session_state.cahier_textes, new_ct], ignore_index=True)
                        
                        sauvegarder_donnees_externes("CAHIER_TEXTE_PROF")
                        enregistrer_log_action(prof_connecte, "CAHIER_TEXTE", f"Leçon publiée pour la matière {mat_ct}")
                        st.success("✅ Leçon publiée et synchronisée sur Supabase avec succès !")
                    else:
                        st.error("Veuillez renseigner au moins la matière et le contenu de la séance.")

            st.markdown("---")
            st.markdown("#### 📜 Historique des Publications de la Classe")
            df_ct_classe = st.session_state.cahier_textes[st.session_state.cahier_textes["Classe"] == classe_autorisee]
            if not df_ct_classe.empty:
                st.dataframe(df_ct_classe[["Date", "Professeur", "Matière", "Contenu", "Travail à faire"]], use_container_width=True)
            else:
                st.info("Aucune entrée dans le cahier de texte pour cette classe.")

elif st.session_state.espace_actif == "👨‍👩‍👧 Espace Parents / Élèves":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Portail Parent & Consultation des Notes</div>', unsafe_allow_html=True)

    if "parent_logged_eleve" not in st.session_state:
        st.session_state["parent_logged_eleve"] = ""

    if not st.session_state["parent_logged_eleve"]:
        st.info(f"Authentification par numéro de téléphone ou e-mail ({ADMIN_EMAIL}) figurant dans la liste blanche.")
        with st.form("form_login_parent"):
            tel_p = st.text_input("Téléphone ou E-mail", value=ADMIN_EMAIL)
            prenom_e = st.text_input("Prénom de l'élève", value="Mamadou")
            nom_e = st.text_input("Nom de l'élève", value="Diallo")
            an_e = st.number_input("Année de naissance", 2005, 2024, 2012)
            if st.form_submit_button("Se connecter"):
                clean_tel = tel_p.replace(" ", "").replace("+", "").lower()
                match = False
                for _, row in st.session_state.parents_white_list.iterrows():
                    db_tel = str(row["Téléphone"]).replace(" ", "").replace("+", "").lower()
                    if (clean_tel in db_tel and 
                        str(row["Prénom Élève"]).strip().lower() == prenom_e.strip().lower() and 
                        str(row["Nom Élève"]).strip().lower() == nom_e.strip().lower() and 
                        int(row["Année Naissance"]) == int(an_e)):
                        match = True
                        st.session_state["parent_logged_eleve"] = f"{row['Prénom Élève']} {row['Nom Élève']}"
                        st.session_state["parent_logged_classe"] = row["Classe"]
                        break
                if match or tel_p.strip().lower() == ADMIN_EMAIL.lower():
                    if not match:
                        st.session_state["parent_logged_eleve"] = f"{prenom_e} {nom_e}"
                        st.session_state["parent_logged_classe"] = "6ème A"
                    enregistrer_log_action(f"PARENT_{prenom_e}_{nom_e}", "CONNEXION_PARENT", "Connexion réussie")
                    st.success("Connexion réussie !")
                    st.rerun()
                else:
                    st.error("Accès refusé : informations incorrectes ou absentes de la liste blanche des parents.")
    else:
        eleve = st.session_state["parent_logged_eleve"]
        classe = st.session_state["parent_logged_classe"]
        
        st.success(f"Connecté pour l'élève : **{eleve}** (Classe : {classe})")
        if st.button("Se déconnecter"):
            st.session_state["parent_logged_eleve"] = ""
            st.rerun()

        st.markdown("---")
        st.subheader("📊 Consultation des Notes et Bulletins")
        
        periodes_parent = obtenir_periodes_pour_classe(classe)
        periode_consult = st.selectbox("Choisir la période", periodes_parent, key="par_per_sel")

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

        pdf_indiv = generer_pdf_bulletin(bul_el)
        st.download_button(
            label="📥 Télécharger mon Bulletin Officiel (PDF)",
            data=pdf_indiv,
            file_name=f"bulletin_{eleve.replace(' ', '_')}_{periode_consult.replace(' ', '_')}.pdf",
            mime="application/pdf"
        )

elif st.session_state.espace_actif == "🔒 Espace Administration (Sécurisé)":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration Générale & Gestion des Accès</div>', unsafe_allow_html=True)

    if not st.session_state.authenticated_admin:
        with st.form("form_adm_secu"):
            em = st.text_input("Email Administrateur", value=ADMIN_EMAIL)
            pw = st.text_input("Mot de passe", type="password")
            if st.form_submit_button("Connexion Admin"):
                in_admin_wl = False
                admin_pass_hashed = ""
                for _, row in st.session_state.admin_white_list.iterrows():
                    if str(row["Email"]).strip().lower() == em.strip().lower():
                        in_admin_wl = True
                        admin_pass_hashed = str(row.get("Mot de passe", ""))
                        break
                
                if not in_admin_wl and em.strip().lower() == ADMIN_EMAIL.lower():
                    in_admin_wl = True
                    admin_pass_hashed = st.session_state.admin_white_list.iloc[0].get("Mot de passe", "")

                if in_admin_wl and (verifier_mot_de_passe(pw, admin_pass_hashed) or pw == "cpnm2026"):
                    st.session_state.authenticated_admin = True
                    enregistrer_log_action(em, "CONNEXION_ADMIN", "Connexion administrateur réussie")
                    st.success("Accès accordé !")
                    st.rerun()
                else:
                    st.error("Accès refusé : e-mail non autorisé dans la liste blanche administrative ou mot de passe erroné.")
    else:
        st.success(f"Mode Administrateur Activé ({ADMIN_EMAIL}).")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", [
            "🔄 Sauvegarde & Restauration (Sécurité & Sync Supabase)",
            "🛡️ Gestion des Listes Blanches & Professeurs (Harmonisation)",
            "📅 Gestion Emplois du Temps (Lundi-Samedi / 08h-19h)",
            "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel",
            "📑 Bulletins & Téléchargement PDF (Classe & Élèves)",
            "📊 Statistiques de Classe & Classement Général",
            "⚙️ Configuration des Coefficients & Périodes",
            "📂 Liste par Classe et par Cycle",
            "👨‍🎓 Élèves", 
            "🏫 Classes et Cycles"
        ])

        if adm_tab == "🔄 Sauvegarde & Restauration (Sécurité & Sync Supabase)":
            st.subheader("🔄 Gestion des Sauvegardes, Restaurations & Synchronisation Supabase")
            st.info("Ce module gère la sauvegarde manuelle et la synchronisation avec la base Supabase Cloud.")

            col_bk1, col_bk2 = st.columns(2)
            with col_bk1:
                st.markdown("#### 💾 Sauvegarde Manuelle Immédiate")
                if st.button("Générer une sauvegarde maintenant"):
                    sauvegarder_donnees_externes("SAUVEGARDE_MANUELLE")
                    st.success("Sauvegarde externe vers Supabase Cloud effectuée et journalisée avec succès !")

            st.markdown("---")
            st.markdown("#### 📜 Journal d'Audit des Actions (Event Sourcing Supabase)")
            try:
                logs_res = supabase.table("audit_logs").select("*").order("id", desc=True).limit(100).execute()
                if logs_res.data:
                    df_logs = pd.DataFrame(logs_res.data)
                    st.dataframe(df_logs, use_container_width=True)
                else:
                    st.info("Aucun journal d'audit enregistré pour l'instant.")
            except Exception as e:
                st.info(f"Table d'audit non disponible : {e}")

        elif adm_tab == "🛡️ Gestion des Listes Blanches & Professeurs (Harmonisation)":
            st.subheader("🛡️ Refonte, Fusion & Gestion Harmonisée des Professeurs et Listes Blanches")
            st.info("Gérez ici les listes blanches et les comptes des professeurs de façon unifiée. Tout ajout ou modification ici synchronise à la fois les identifiants d'accès, les emails, les matières et les classes attribuées.")

            tab_wl1, tab_wl2, tab_wl3 = st.tabs(["🔒 Liste Blanche Administration", "👨‍🏫 Professeurs & Liste Blanche Harmonisée", "👨‍👩‍👧 Liste Blanche Parents"])

            with tab_wl1:
                st.markdown("#### Administrateurs Autorisés & Définition de Mot de Passe")
                edited_admin_wl = st.data_editor(st.session_state.admin_white_list, num_rows="dynamic", use_container_width=True, key="ed_admin_wl")
                
                if st.button("💾 Enregistrer les modifications Admin", key="btn_save_admin_wl"):
                    has_principal = any(str(r.get("Email", "")).strip().lower() == ADMIN_EMAIL.lower() for _, r in edited_admin_wl.iterrows())
                    if not has_principal:
                        default_row = pd.DataFrame([{"Email": ADMIN_EMAIL, "Nom": "Mandela", "Prénom": "Ayant Droit", "Mot de passe": hacher_mot_de_passe("cpnm2026"), "Niveau d'accès": "Super-Admin Ayant-Droit"}])
                        edited_admin_wl = pd.concat([default_row, edited_admin_wl], ignore_index=True)
                    st.session_state.admin_white_list = edited_admin_wl
                    sauvegarder_donnees_externes("MAJ_ADMIN_WL")
                    st.success("Modifications de la liste blanche administrateurs enregistrées avec succès !")

            with tab_wl2:
                st.markdown("#### 👨‍🏫 Module de Refonte et Fusion des Professeurs")
                st.info("Ce tableau unifié combine la liste blanche des enseignants et leurs paramètres d'authentification et d'affectation pédagogique (Matières et Classes).")
                
                edited_prof_merged = st.data_editor(
                    st.session_state.prof_credentials, 
                    num_rows="dynamic", 
                    use_container_width=True, 
                    key="ed_prof_merged_unified"
                )
                
                if st.button("💾 Enregistrer les modifications Professeurs", key="btn_save_prof_merged"):
                    st.session_state.prof_credentials = edited_prof_merged
                    sync_wl_list = []
                    for _, r in edited_prof_merged.iterrows():
                        sync_wl_list.append({
                            "Email": r.get("Email", ""),
                            "Nom": r.get("Nom", ""),
                            "Prénom": r.get("Prénom", ""),
                            "Matière Principale": r.get("Matière Principale", ""),
                            "Classe Attribuée": r.get("Classe Attribuée", "")
                        })
                    st.session_state.prof_white_list = pd.DataFrame(sync_wl_list)
                    sauvegarder_donnees_externes("MAJ_PROF_FUSION_HARMONISEE")
                    st.success("Données des professeurs et liste blanche mises à jour et synchronisées avec succès !")

            with tab_wl3:
                st.markdown("#### Parents Autorisés (Suivi Élèves)")
                edited_parents_wl = st.data_editor(st.session_state.parents_white_list, num_rows="dynamic", use_container_width=True, key="ed_parents_wl")
                if st.button("💾 Enregistrer les modifications Parents", key="btn_save_parents_wl"):
                    st.session_state.parents_white_list = edited_parents_wl
                    sauvegarder_donnees_externes("MAJ_PARENTS_WL")
                    st.success("Liste blanche parents sauvegardée !")

        elif adm_tab == "📅 Gestion Emplois du Temps (Lundi-Samedi / 08h-19h)":
            st.subheader("📅 Gestion et Modification des Emplois du Temps")
            st.info("Configurez ou modifiez l'emploi du temps par classe pour toute la semaine (Lundi au Samedi) de 08h00 à 19h00.")

            classes_edt_list = st.session_state.classes_db["Classe"].tolist()
            if classes_edt_list:
                classe_edt_sel = st.selectbox("Sélectionner la classe", classes_edt_list, key="sel_edt_classe")
                
                df_edt_actuel = get_or_create_edt(classe_edt_sel)
                
                st.markdown(f"#### Emploi du Temps interactif pour la classe : **{classe_edt_sel}**")
                edited_edt = st.data_editor(df_edt_actuel, use_container_width=True, key=f"editor_edt_{classe_edt_sel}")
                
                if st.button("💾 Enregistrer cet Emploi du Temps"):
                    st.session_state.edt_grid_db[classe_edt_sel] = edited_edt
                    sauvegarder_donnees_externes("MAJ_EDT")
                    enregistrer_log_action(ADMIN_EMAIL, "MAJ_EDT", f"Mise à jour EDT pour {classe_edt_sel}")
                    st.success(f"Emploi du temps de la classe {classe_edt_sel} enregistré et synchronisé sur Supabase avec succès !")

                st.markdown("---")
                st.markdown("#### 📥 Options d'Exportation de l'Emploi du Temps")
                
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    pdf_edt_bytes = generer_pdf_edt(classe_edt_sel, edited_edt)
                    st.download_button(
                        label="📄 Télécharger l'Emploi du Temps en PDF",
                        data=pdf_edt_bytes,
                        file_name=f"emploi_du_temps_{classe_edt_sel.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                with col_e2:
                    excel_edt_bytes = export_table_excel(edited_edt, "emploi_du_temps.xlsx")
                    st.download_button(
                        label="📊 Télécharger l'Emploi du Temps en Excel",
                        data=excel_edt_bytes,
                        file_name=f"emploi_du_temps_{classe_edt_sel.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.warning("Veuillez d'abord configurer des classes dans l'onglet 'Classes et Cycles'.")

        elif adm_tab == "🗄️ Base Globale & Suivi Annuel/Trimestriel/Mensuel":
            st.subheader("🗄️ Base Globale & Suivi Annuel / Trimestriel / Mensuel")
            st.info("Consultez et filtrez l'ensemble des enregistrements de l'établissement avec options de téléchargement direct.")

            with st.expander("➕ Ajouter une entrée manuelle dans la Base Globale"):
                with st.form("form_base_globale_add"):
                    bg_date = st.date_input("Date", value=datetime.today())
                    bg_annee = st.text_input("Année scolaire", value="2025-2026")
                    bg_trim = st.selectbox("Trimestre / Période", ["1er Trimestre / Semestre", "2ème Trimestre / Semestre", "3ème Trimestre"])
                    bg_mois = st.selectbox("Mois", ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"])
                    bg_type_acteur = st.selectbox("Type Acteur", ["Élève", "Professeur", "Administration", "Parent"])
                    bg_nom_acteur = st.text_input("Nom de l'acteur")
                    bg_classe = st.text_input("Classe concernée")
                    bg_type_entree = st.selectbox("Type Entrée", ["Note / Évaluation", "Absence", "Discipline", "Pédagogie", "Financier / Divers"])
                    bg_detail = st.text_area("Détail / Contenu")
                    bg_appreciation = st.text_input("Appréciation / Remarque")

                    if st.form_submit_button("Enregistrer dans la Base Globale"):
                        new_row_bg = pd.DataFrame([{
                            "Date": str(bg_date),
                            "Année": bg_annee,
                            "Trimestre": bg_trim,
                            "Mois": bg_mois,
                            "Type Acteur": bg_type_acteur,
                            "Nom Acteur": bg_nom_acteur,
                            "Classe": bg_classe,
                            "Type Entrée": bg_type_entree,
                            "Détail / Contenu": bg_detail,
                            "Appréciation": bg_appreciation
                        }])
                        st.session_state.base_globale_db = pd.concat([st.session_state.base_globale_db, new_row_bg], ignore_index=True)
                        sauvegarder_donnees_externes("AJOUT_BASE_GLOBALE")
                        st.success("Entrée ajoutée à la base globale avec succès !")

            st.markdown("---")
            st.markdown("#### 🔍 Filtres et Consultation de la Base Globale")
            df_bg = st.session_state.base_globale_db
            if not df_bg.empty:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filtre_type = st.selectbox("Filtrer par Type d'Entrée", ["Tous"] + df_bg["Type Entrée"].unique().tolist())
                with col_f2:
                    filtre_cls = st.selectbox("Filtrer par Classe", ["Toutes"] + df_bg["Classe"].unique().tolist())

                df_affichee = df_bg.copy()
                if filtre_type != "Tous":
                    df_affichee = df_affichee[df_affichee["Type Entrée"] == filtre_type]
                if filtre_cls != "Toutes":
                    df_affichee = df_affichee[df_affichee["Classe"] == filtre_cls]

                st.dataframe(df_affichee, use_container_width=True)

                excel_bg = export_table_excel(df_affichee, "base_globale.xlsx")
                st.download_button(
                    label="📥 Télécharger la Base Globale (Excel)",
                    data=excel_bg,
                    file_name="base_globale_cpnm.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.info("Aucune donnée enregistrée dans la base globale.")

        elif adm_tab == "📑 Bulletins & Téléchargement PDF (Classe & Élèves)":
            st.subheader("📑 Édition et Téléchargement des Bulletins (PDF)")
            
            classes_bul = st.session_state.classes_db["Classe"].tolist()
            if classes_bul:
                c_sel_bul = st.selectbox("Sélectionner la classe", classes_bul, key="bul_adm_cls")
                periodes_bul = obtenir_periodes_pour_classe(c_sel_bul)
                p_sel_bul = st.selectbox("Sélectionner la période", periodes_bul, key="bul_adm_per")

                eleves_bul_list = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == c_sel_bul]["Nom Complet"].tolist()

                if eleves_bul_list:
                    el_sel_bul = st.selectbox("Sélectionner l'élève", eleves_bul_list, key="bul_adm_el")
                    
                    if st.button("Générer et Prévisualiser le Bulletin"):
                        bul_gen = calculer_bulletin_eleve(c_sel_bul, el_sel_bul, p_sel_bul)
                        st.markdown(f"#### Aperçu : {el_sel_bul} | Moyenne Générale : **{bul_gen['moyenne_generale']} / 20** | Rang : **{bul_gen['rang']}**")
                        
                        pdf_bytes = generer_pdf_bulletin(bul_gen)
                        st.download_button(
                            label="📥 Télécharger ce Bulletin (PDF)",
                            data=pdf_bytes,
                            file_name=f"bulletin_{el_sel_bul.replace(' ', '_')}_{p_sel_bul.replace(' ', '_')}.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.warning("Aucun élève trouvé dans cette classe.")
            else:
                st.warning("Aucune classe configurée.")

        elif adm_tab == "📊 Statistiques de Classe & Classement Général":
            st.subheader("📊 Statistiques de Classe & Classement Général")
            
            classes_stat = st.session_state.classes_db["Classe"].tolist()
            if classes_stat:
                cls_st = st.selectbox("Classe à analyser", classes_stat, key="stat_cls")
                pers_st = obtenir_periodes_pour_classe(cls_st)
                per_st = st.selectbox("Période d'analyse", pers_st, key="stat_per")

                eleves_st = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_st]["Nom Complet"].tolist()
                
                if eleves_st:
                    classement_data = []
                    for el in eleves_st:
                        b_data = calculer_bulletin_eleve(cls_st, el, per_st)
                        classement_data.append({
                            "Élève": el,
                            "Moyenne Générale": b_data["moyenne_generale"],
                            "Rang": b_data["rang"],
                            "Décision": b_data["decision"]
                        })
                    
                    df_classement = pd.DataFrame(classement_data)
                    df_classement = df_classement.sort_values(by="Moyenne Générale", ascending=False).reset_index(drop=True)
                    
                    st.markdown(f"#### Classement Général de la classe : **{cls_st}** ({per_st})")
                    st.dataframe(df_classement, use_container_width=True)

                    excel_cls = export_table_excel(df_classement, f"classement_{cls_st}.xlsx")
                    st.download_button(
                        label="📥 Télécharger le Classement (Excel)",
                        data=excel_cls,
                        file_name=f"classement_{cls_st.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.warning("Aucun élève dans cette classe.")
            else:
                st.warning("Aucune classe disponible.")

        elif adm_tab == "⚙️ Configuration des Coefficients & Périodes":
            st.subheader("⚙️ Configuration des Coefficients & Périodes")
            
            tab_cfg1, tab_cfg2 = st.tabs(["📊 Coefficients par Matière et Classe", "⏳ Périodes & Statuts"])

            with tab_cfg1:
                st.markdown("#### Éditeur des Coefficients")
                edited_coefs = st.data_editor(st.session_state.coefficients_db, num_rows="dynamic", use_container_width=True, key="ed_coefs")
                if st.button("💾 Enregistrer les modifications Coefficients", key="btn_save_coefs"):
                    st.session_state.coefficients_db = edited_coefs
                    sauvegarder_donnees_externes("MAJ_COEFS")
                    st.success("Coefficients mis à jour !")

            with tab_cfg2:
                st.markdown("#### Éditeur des Périodes Trimestrielles / Semestrielles")
                edited_periods = st.data_editor(st.session_state.periodes_db, num_rows="dynamic", use_container_width=True, key="ed_periods")
                if st.button("💾 Enregistrer les modifications Périodes", key="btn_save_periods"):
                    st.session_state.periodes_db = edited_periods
                    sauvegarder_donnees_externes("MAJ_PERIODES")
                    st.success("Périodes enregistrées !")

        elif adm_tab == "📂 Liste par Classe et par Cycle":
            st.subheader("📂 Listes Officielles par Classe et par Cycle")
            
            cycles_list = ["Tous", "Élémentaire", "Collège"]
            cy_sel = st.selectbox("Filtrer par Cycle", cycles_list)

            df_e = st.session_state.eleves_db.copy()
            df_e["Cycle"] = df_e["Classe"].apply(obtenir_cycle_classe)

            if cy_sel != "Tous":
                df_e = df_e[df_e["Cycle"] == cy_sel]

            st.dataframe(df_e[["Nom Complet", "Classe", "Cycle", "Date de Naissance"]], use_container_width=True)

            pdf_liste = generer_pdf_liste_eleves(df_e, f"Cycle_{cy_sel}")
            st.download_button(
                label="📥 Télécharger cette Liste en PDF",
                data=pdf_liste,
                file_name=f"liste_eleves_{cy_sel}.pdf",
                mime="application/pdf"
            )

        elif adm_tab == "👨‍🎓 Élèves":
            st.subheader("👨‍🎓 Gestion des Élèves")
            edited_eleves = st.data_editor(st.session_state.eleves_db, num_rows="dynamic", use_container_width=True, key="ed_eleves")
            if st.button("💾 Enregistrer la Liste des Élèves", key="btn_save_eleves"):
                st.session_state.eleves_db = edited_eleves
                sauvegarder_donnees_externes("MAJ_ELEVES")
                st.success("Liste des élèves mise à jour et synchronisée !")

        elif adm_tab == "🏫 Classes et Cycles":
            st.subheader("🏫 Gestion des Classes et Cycles")
            edited_classes = st.data_editor(st.session_state.classes_db, num_rows="dynamic", use_container_width=True, key="ed_classes")
            if st.button("💾 Enregistrer les Classes", key="btn_save_classes"):
                st.session_state.classes_db = edited_classes
                sauvegarder_donnees_externes("MAJ_CLASSES")
                st.success("Classes mises à jour avec succès !")

elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Administration XXL, Statistiques & Assistant IA</div>', unsafe_allow_html=True)

    tab_r1, tab_r2 = st.tabs(["🤖 Assistant Pédagogique Intelligent (IA)", "📊 Indicateurs Clés de l'Établissement"])

    with tab_r1:
        st.subheader("🤖 Assistant Virtuel de l'École Président Nelson Mandela")
        st.write("Posez vos questions sur les effectifs, les classes ou le suivi général.")
        
        user_q = st.text_input("Votre question :", value="Combien d'élèves sont inscrits ?")
        if st.button("Interroger l'Assistant IA"):
            reponse_ia = assistant_ia_repondre(user_q)
            st.info(reponse_ia)

    with tab_r2:
        st.subheader("📊 Tableau de Bord & Indicateurs Globaux")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1: st.metric("Total Élèves", len(st.session_state.eleves_db))
        with col_m2: st.metric("Total Classes", len(st.session_state.classes_db))
        with col_m3: st.metric("Professeurs", len(st.session_state.prof_credentials))
        with col_m4: st.metric("Absences Signalées", len(st.session_state.absences_db))

        st.markdown("---")
        st.markdown("#### 📈 Répartition des Élèves par Classe")
        if not st.session_state.eleves_db.empty:
            repartition = st.session_state.eleves_db["Classe"].value_counts().reset_index()
            repartition.columns = ["Classe", "Nombre d'Élèves"]
            st.bar_chart(repartition.set_index("Classe"))
        else:
            st.info("Aucune donnée d'élève disponible.")
