from datetime import datetime
import base64
from fpdf import FPDF
import pandas as pd
import streamlit as st
import io
import os

# ==========================================
# ==========================================
# 1. CONFIGURATION DE LA PAGE & DESIGN XXL RESPONSIVE
# ==========================================
st.set_page_config(
    page_title="Portail Pédagogique XXL - Cours Privé Nelson Mandela | Sénégal",
    page_icon="🇸🇳",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* Global Styles & Mobile Reset */
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

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(15px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Cartes adaptatives pour iPhone, Tablettes et Ordinateurs */
    .animated-card {
        animation: fadeIn 0.6s ease-in-out;
        border: 2px solid #E2E8F0;
        padding: clamp(15px, 3vw, 25px);
        border-radius: 16px;
        background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
        transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
        text-align: center;
        cursor: pointer;
        margin-bottom: 15px;
        height: 100%;
    }
    
    .animated-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 35px rgba(30, 58, 138, 0.15);
        border-color: #2563EB;
    }

    /* Boutons tactiles optimisés pour mobile (iPhone/Android) et desktop */
    .stButton>button { 
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%); 
        color: white; 
        border-radius: 8px; 
        font-weight: bold; 
        border: none;
        padding: 0.75rem 1rem;
        transition: all 0.3s ease;
        width: 100%;
        min-height: 44px; /* Norme ergonomique tactile mobile */
        font-size: 1rem;
    }
    
    .stButton>button:hover {
        background: linear-gradient(135deg, #152E69 0%, #1D4ED8 100%);
        box-shadow: 0 5px 15px rgba(37, 99, 235, 0.3);
    }

    /* Media Queries spécifiques pour petits écrans (smartphones / iPhones) */
    @media screen and (max-width: 768px) {
        .header-ecole {
            font-size: 1.6rem;
        }
        .sub-header {
            font-size: 0.95rem;
        }
        .animated-card {
            padding: 15px;
            margin-bottom: 12px;
        }
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
            ["Aminata Ba", "2013-02-10", "6ème A", None]
        ]
    )

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
        columns=["Classe", "Élève", "Matière", "Coefficient", "Note", "Trimestre", "Appréciation"],
        data=[
            ["6ème A", "Mamadou Diallo", "Mathématiques", 3, 15.5, "1er Trimestre", "Très bon travail."]
        ]
    )

if "conduite_db" not in st.session_state:
    st.session_state.conduite_db = pd.DataFrame(
        columns=["Classe", "Élève", "Date", "Type", "Description"],
        data=[
            ["6ème A", "Mamadou Diallo", "2026-06-02", "Encouragement", "Participation active en classe."]
        ]
    )

if "messagerie_db" not in st.session_state:
    st.session_state.messagerie_db = pd.DataFrame(
        columns=["Auteur", "Destinataire", "Date", "Message"]
    )

# ==========================================
# 3. FONCTIONS UTILITAIRES
# ==========================================
def creer_rapport_pdf(titre_rapport, data_dict):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "COURS PRIVE NELSON MANDELA - SENEGAL", 0, 1, "C")
    pdf.set_font("Arial", "I", 10)
    pdf.cell(0, 8, "Rapport Officiel de l'Etablissement - Annee 2026", 0, 1, "C")
    pdf.ln(10)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, titre_rapport, 0, 1, "L")
    pdf.set_font("Arial", "", 11)
    for k, v in data_dict.items():
        pdf.cell(0, 8, f"- {k}: {v}", 0, 1, "L")
    pdf.ln(10)
    pdf.set_font("Arial", "I", 9)
    pdf.cell(0, 10, f"Genere automatiquement le {datetime.now().strftime('%d/%m/%Y a %H:%M')}", 0, 1, "C")
    return pdf.output(dest='S').encode('latin1')

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
            <h3 style="color: #1E3A8A; font-weight: 800;">Portail Numérique Intelligent & Suivi Pédagogique</h3>
            <p style="font-size: 1.1rem; color: #475569; max-width: 800px; margin: 0 auto;">
                Veuillez sélectionner votre espace ci-dessous pour accéder aux fonctionnalités dédiées. Chaque profil dispose d'un accès strictement cloisonné et sécurisé.
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
                <p style="font-size: 0.85rem; color: #64748B;">Notes, cahier de textes, feuilles d'appel et rapports journaliers.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Suivi des notes, absences, conduite et carte scolaire numérique.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Gestion complète des effectifs, classes et listes blanches.</p>
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
                <p style="font-size: 0.85rem; color: #64748B;">Tableaux de bord statistiques et génération de documents PDF.</p>
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
    with s1: st.metric("Élèves Inscrits", len(st.session_state.eleves_db))
    with s2: st.metric("Classes Actives", len(st.session_state.classes_db))
    with s3: st.metric("Professeurs", len(st.session_state.prof_credentials))
    with s4: st.metric("Rapports Journaliers", len(st.session_state.rapports_journaliers_prof))

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
        menu_prof = st.radio("Menu Professeur :", ["📋 Fiche d'Appel", "📝 Saisie des Notes", "⚠️ Conduite", "📖 Cahier de Textes", "📊 Rapport Journalier"], horizontal=True)
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
                            for el in eleves_cibles:
                                if res_appel[el] != "Présent":
                                    nouveaux_abs.append({"Date": str(date_jour), "Classe": cls_appel, "Élève": el, "Statut": res_appel[el], "Motif": "Non renseigné"})
                            if nouveaux_abs:
                                st.session_state.absences_db = pd.concat([st.session_state.absences_db, pd.DataFrame(nouveaux_abs)], ignore_index=True)
                            st.success("Appel enregistré !")
                else:
                    st.info("Aucun élève dans cette classe.")

        elif menu_prof == "📝 Saisie des Notes":
            st.markdown("### Saisie des Notes")
            with st.form("form_notes_prof"):
                cls_n = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
                eleves_cls = st.session_state.eleves_db[st.session_state.eleves_db["Classe"] == cls_n]["Nom Complet"].tolist()
                eleve_n = st.selectbox("Élève", eleves_cls if eleves_cls else ["--"])
                matiere_n = st.text_input("Matière")
                coef_n = st.number_input("Coefficient", 1, 5, 2)
                note_val = st.number_input("Note (/20)", 0.0, 20.0, 10.0, 0.5)
                trimestre = st.selectbox("Trimestre", ["1er Trimestre", "2ème Trimestre", "3ème Trimestre"])
                appr = st.text_input("Appréciation")
                if st.form_submit_button("Enregistrer la note"):
                    if eleves_cls and matiere_n:
                        new_n = pd.DataFrame([{"Classe": cls_n, "Élève": eleve_n, "Matière": matiere_n, "Coefficient": coef_n, "Note": note_val, "Trimestre": trimestre, "Appréciation": appr}])
                        st.session_state.notes_db = pd.concat([st.session_state.notes_db, new_n], ignore_index=True)
                        st.success("Note enregistrée avec succès.")
                    else:
                        st.error("Veuillez remplir les champs obligatoires.")

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
                        new_cd = pd.DataFrame([{"Classe": cls_c, "Élève": el_c, "Date": str(datetime.today().date()), "Type": type_s, "Description": desc}])
                        st.session_state.conduite_db = pd.concat([st.session_state.conduite_db, new_cd], ignore_index=True)
                        st.success("Remarque enregistrée.")

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
            with st.form("form_rap_prof"):
                cls_r = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["--"])
                mat_r = st.text_input("Matière")
                bilan = st.text_area("Bilan du cours")
                diff = st.text_area("Difficultés ou remarques")
                if st.form_submit_button("Soumettre à l'administration"):
                    if mat_r and bilan:
                        new_r = pd.DataFrame([{"Professeur": prof_connecte, "Date": str(datetime.today().date()), "Classe": cls_r, "Matière": mat_r, "Bilan du Cours": bilan, "Difficultés / Remarques": diff}])
                        st.session_state.rapports_journaliers_prof = pd.concat([st.session_state.rapports_journaliers_prof, new_r], ignore_index=True)
                        st.success("Rapport transmis avec succès à l'administration !")

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
        t1, t2, t3, t4, t5 = st.tabs(["📊 Notes", "📉 Absences", "⚠️ Conduite", "📖 Cahier de Textes", "🪪 Carte Scolaire"])
        
        with t1:
            st.subheader("Bulletins & Notes")
            notes_el = st.session_state.notes_db[st.session_state.notes_db["Élève"].str.contains(eleve, case=False, na=False)]
            if not notes_el.empty:
                st.dataframe(notes_el[["Trimestre", "Matière", "Coefficient", "Note", "Appréciation"]], use_container_width=True)
                total_pts = (notes_el["Note"] * notes_el["Coefficient"]).sum()
                total_coef = notes_el["Coefficient"].sum()
                if total_coef > 0:
                    st.metric("Moyenne générale", f"{total_pts / total_coef:.2f} / 20")
            else:
                st.info("Aucune note enregistrée.")

        with t2:
            st.subheader("Absences")
            abs_el = st.session_state.absences_db[st.session_state.absences_db["Élève"].str.contains(eleve, case=False, na=False)]
            if not abs_el.empty: st.dataframe(abs_el, use_container_width=True)
            else: st.success("Aucune absence recensée.")

        with t3:
            st.subheader("Conduite")
            cond_el = st.session_state.conduite_db[st.session_state.conduite_db["Élève"].str.contains(eleve, case=False, na=False)]
            if not cond_el.empty: st.dataframe(cond_el, use_container_width=True)
            else: st.info("Aucune observation disciplinaire.")

        with t4:
            st.subheader("Cahier de Textes de la Classe")
            ct_cls = st.session_state.cahier_textes[st.session_state.cahier_textes["Classe"] == classe]
            if not ct_cls.empty: st.dataframe(ct_cls, use_container_width=True)
            else: st.info("Aucune leçon publiée.")

        with t5:
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
        st.success("Mode Administrateur Général Activé — Accès complet sur toutes les tables.")
        if st.button("Se déconnecter de l'admin"):
            st.session_state.authenticated_admin = False
            st.rerun()

        st.markdown("---")
        adm_tab = st.selectbox("Gestion Administrative :", ["Élèves", "Classes", "Professeurs", "Listes Blanches Parents", "Rapports Journaliers des Profs"])

        if adm_tab == "Élèves":
            st.subheader("Gestion des Élèves")
            with st.form("form_add_eleve"):
                c_nom = st.text_input("Nom complet de l'élève")
                c_cls = st.selectbox("Classe", st.session_state.classes_db["Classe"].tolist() if not st.session_state.classes_db.empty else ["6ème A"])
                if st.form_submit_button("Ajouter l'élève"):
                    if c_nom:
                        new_el = pd.DataFrame([{"Nom Complet": c_nom, "Date de Naissance": "2012-01-01", "Classe": c_cls, "Photo": None}])
                        st.session_state.eleves_db = pd.concat([st.session_state.eleves_db, new_el], ignore_index=True)
                        st.success("Élève ajouté avec succès.")
            st.dataframe(st.session_state.eleves_db, use_container_width=True)

        elif adm_tab == "Classes":
            st.subheader("Gestion des Classes")
            with st.form("form_add_classe"):
                nom_c = st.text_input("Nom de la classe (ex: 4ème A)")
                cycle = st.selectbox("Cycle", ["Préscolaire", "Élémentaire", "Collège"])
                if st.form_submit_button("Créer la classe"):
                    if nom_c:
                        new_cl = pd.DataFrame([{"Classe": nom_c, "Cycle": cycle, "Professeur Responsable": "Non assigné"}])
                        st.session_state.classes_db = pd.concat([st.session_state.classes_db, new_cl], ignore_index=True)
                        st.success("Classe créée.")
            st.dataframe(st.session_state.classes_db, use_container_width=True)

        elif adm_tab == "Professeurs":
            st.subheader("Gestion des Professeurs")
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
            st.dataframe(st.session_state.prof_credentials, use_container_width=True)

        elif adm_tab == "Listes Blanches Parents":
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

        elif adm_tab == "Rapports Journaliers des Profs":
            st.subheader("Rapports Journaliers Soumis par le Corps Enseignant")
            if not st.session_state.rapports_journaliers_prof.empty:
                st.dataframe(st.session_state.rapports_journaliers_prof, use_container_width=True)
            else:
                st.info("Aucun rapport journalier reçu pour l'instant.")

# ESPACE RAPPORTS GLOBAUX
elif st.session_state.espace_actif == "🏫 Administration XXL & Rapports":
    st.markdown('<div style="color: #1E3A8A; font-size: 1.8rem; font-weight: bold;">Tableau de Bord Global & Rapports Officiels</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Total Élèves Inscrits", len(st.session_state.eleves_db))
    with col2: st.metric("Classes Actives", len(st.session_state.classes_db))
    with col3: st.metric("Professeurs Répertoriés", len(st.session_state.prof_credentials))

    st.markdown("### Exportation des Rapports de l'Établissement")
    if st.button("Télécharger le rapport général de l'établissement (PDF)"):
        data_rap = {
            "Total Élèves": len(st.session_state.eleves_db),
            "Total Classes": len(st.session_state.classes_db),
            "Total Professeurs": len(st.session_state.prof_credentials),
            "Date d'édition": datetime.now().strftime("%d/%m/%Y")
        }
        pdf_bytes = creer_rapport_pdf("Rapport Global de l'Établissement", data_rap)
        st.download_button(
            label="Cliquer ici pour télécharger le PDF",
            data=pdf_bytes,
            file_name="rapport_general_nelson_mandela.pdf",
            mime="application/pdf"
        )
