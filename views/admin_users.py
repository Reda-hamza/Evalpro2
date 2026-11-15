import sqlite3

import pandas as pd
import streamlit as st

from components.compat import STRETCH

from components.styles import page_header
from config import PERIODICITES, ROLE_LABELS
from database import repository as repo
from services import audit_service as audit
from services import management_service as ms
from services.auth_service import current_user

admin = current_user()
if admin["role"] != "admin":
    st.error("Accès réservé à l'administrateur.")
    st.stop()

page_header("👥 Utilisateurs", "Création, modification, réinitialisation et suppression de tous les comptes")
ERRORS = (ValueError, ms.PermissionDenied)
users = repo.list_users_full()
managers = repo.list_managers(actif_only=True)
logins = repo.last_logins()

df = pd.DataFrame({
    "Nom complet": [u["nom_complet"] for u in users],
    "Identifiant": [u["username"] for u in users],
    "Rôle": [ROLE_LABELS[u["role"]] for u in users],
    "Équipe de": [u["manager"] or "—" for u in users],
    "Périodicité": [PERIODICITES[u["periodicite"]] if u["role"] == "manager" else "—" for u in users],
    "Actif": [bool(u["actif"]) for u in users],
    "Dernière connexion": [audit.fmt_local(logins.get(u["id"])) for u in users],
})
st.dataframe(df, hide_index=True, **STRETCH)

tab_new, tab_edit, tab_del = st.tabs(["➕ Créer", "✏️ Modifier / réinitialiser", "🗑️ Supprimer"])

# ------------------------------ Créer ------------------------------
with tab_new:
    with st.form("adm_new_user", clear_on_submit=True):
        role = st.selectbox("Rôle", list(ROLE_LABELS), format_func=ROLE_LABELS.get, index=1)
        nom = st.text_input("Nom complet")
        username = st.text_input("Identifiant")
        pwd = st.text_input("Mot de passe initial", type="password",
                            help="L'utilisateur devra le changer à sa première connexion.")
        boss = st.selectbox("Manager de rattachement (collaborateurs uniquement)", [None] + managers,
                            format_func=lambda m: "—" if m is None else m["nom_complet"])
        periodicite = st.selectbox("Fréquence des évaluations (managers uniquement)", list(PERIODICITES),
                                   format_func=PERIODICITES.get)
        ok = st.form_submit_button("Créer le compte", type="primary")
    if ok:
        try:
            ms.create_user(admin, username, pwd, role, nom, boss["id"] if boss else None, periodicite)
            st.success(f"Compte « {username.strip()} » créé.")
            st.rerun()
        except sqlite3.IntegrityError:
            st.error("Cet identifiant existe déjà.")
        except ERRORS as e:
            st.error(str(e))

# ------------------------- Modifier / réinitialiser -------------------------
with tab_edit:
    sel = st.selectbox("Compte", users, key="adm_edit_sel",
                       format_func=lambda u: f"{u['nom_complet']} ({ROLE_LABELS[u['role']]})")
    with st.form("adm_edit_user"):
        k = sel["id"]
        new_nom = st.text_input("Nom complet", value=sel["nom_complet"], key=f"anom_{k}")
        actif = st.checkbox("Compte actif", value=bool(sel["actif"]), key=f"aact_{k}")
        new_boss = None
        if sel["role"] == "collaborateur":
            idx = next((i for i, m in enumerate(managers) if m["id"] == sel["manager_id"]), 0)
            new_boss = st.selectbox("Manager de rattachement", managers, index=idx if managers else None,
                                    format_func=lambda m: m["nom_complet"], key=f"aboss_{k}")
        new_period = None
        if sel["role"] == "manager":
            keys_p = list(PERIODICITES)
            new_period = st.selectbox("Fréquence des évaluations de l'équipe", keys_p,
                                      index=keys_p.index(sel["periodicite"]), format_func=PERIODICITES.get,
                                      key=f"aper_{k}")
        new_pwd = st.text_input("Nouveau mot de passe (laisser vide pour ne pas changer)",
                                type="password", key=f"apwd_{k}",
                                help="L'utilisateur devra le changer à sa prochaine connexion.")
        ok2 = st.form_submit_button("Enregistrer", type="primary")
    if ok2:
        try:
            ms.update_user(admin, sel["id"], new_nom, actif, new_boss["id"] if new_boss else None)
            if new_period and new_period != sel["periodicite"]:
                ms.set_periodicity(admin, sel["id"], new_period)
            if new_pwd:
                ms.reset_password(admin, sel["id"], new_pwd)
            st.success("Modifications enregistrées.")
            st.rerun()
        except ERRORS as e:
            st.error(str(e))

# ------------------------------ Supprimer ------------------------------
with tab_del:
    candidates = [u for u in users if u["id"] != admin["id"]]
    if not candidates:
        st.info("Aucun autre compte à supprimer.")
    else:
        victim = st.selectbox("Compte à supprimer", candidates, key="adm_del_sel",
                              format_func=lambda u: f"{u['nom_complet']} ({ROLE_LABELS[u['role']]})")
        reassign_to, delete_team = None, False
        if victim["role"] == "manager":
            team = repo.list_collaborateurs(actif_only=False, manager_id=victim["id"])
            if team:
                st.info(f"Ce manager a {len(team)} collaborateur(s) dans son équipe.")
                others = [m for m in repo.list_managers() if m["id"] != victim["id"]]
                options = (["Réaffecter l'équipe à un autre manager"] if others else []) + \
                          ["Supprimer aussi toute l'équipe (collaborateurs, tâches, évaluations)"]
                action = st.radio("Que faire de l'équipe ?", options, key=f"adm_team_{victim['id']}")
                if action.startswith("Réaffecter"):
                    reassign_to = st.selectbox("Nouveau manager", others, key=f"adm_re_{victim['id']}",
                                               format_func=lambda m: m["nom_complet"])["id"]
                else:
                    delete_team = True
        st.warning("Suppression **définitive** : le compte, ses tâches et ses évaluations sont effacés "
                   "(le journal d'activité est conservé). Pour bloquer un accès sans rien perdre, "
                   "désactivez le compte à la place.")
        confirm = st.checkbox(f"Je confirme la suppression définitive de {victim['nom_complet']}",
                              key=f"adm_del_ok_{victim['id']}")
        if st.button("Supprimer définitivement", disabled=not confirm, type="primary", key="adm_del_btn"):
            try:
                ms.delete_user(admin, victim["id"], reassign_to=reassign_to, delete_team=delete_team)
                st.success("Compte supprimé.")
                st.rerun()
            except ERRORS as e:
                st.error(str(e))
