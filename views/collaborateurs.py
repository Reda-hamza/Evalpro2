import sqlite3

import pandas as pd
import streamlit as st

from components.compat import STRETCH
from components.styles import page_header
from config import PERIODICITES, PERIODE_LABELS, STATUTS_EVAL, STATUTS_TACHES, year_options
from database import repository as repo
from services import management_service as ms
from services.auth_service import current_user

user = current_user()
if user["role"] != "manager":
    st.error("Accès réservé au manager.")
    st.stop()

page_header("👥 Mon équipe", "Comptes, éléments à évaluer et évaluations de vos collaborateurs")
tab_users, tab_tasks, tab_evals = st.tabs(["Comptes", "Éléments à évaluer", "Évaluations"])
ERRORS = (ValueError, ms.PermissionDenied)

# ============================== COMPTES ==============================
with tab_users:
    team = repo.list_collaborateurs(actif_only=False, manager_id=user["id"])
    if team:
        df = pd.DataFrame(team)[["nom_complet", "username", "actif"]]
        df.columns = ["Nom complet", "Identifiant", "Actif"]
        st.dataframe(df, hide_index=True, **STRETCH)
    else:
        st.info("Votre équipe est vide. Créez votre premier collaborateur ci-dessous.")

    left, right = st.columns(2)
    with left:
        st.subheader("➕ Nouveau collaborateur")
        with st.form("new_user", clear_on_submit=True):
            nom = st.text_input("Nom complet")
            username = st.text_input("Identifiant")
            pwd = st.text_input("Mot de passe initial", type="password",
                                help="Le collaborateur devra le changer à sa première connexion.")
            ok = st.form_submit_button("Créer le compte", type="primary")
        if ok:
            try:
                ms.create_user(user, username, pwd, "collaborateur", nom)
                st.success(f"Compte créé pour {nom.strip()}.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Cet identifiant existe déjà.")
            except ERRORS as e:
                st.error(str(e))
    with right:
        st.subheader("✏️ Modifier / réinitialiser")
        if team:
            sel = st.selectbox("Collaborateur", team, format_func=lambda u: u["nom_complet"], key="edit_sel")
            with st.form("edit_user"):
                new_nom = st.text_input("Nom complet", value=sel["nom_complet"], key=f"nom_{sel['id']}")
                actif = st.checkbox("Compte actif", value=bool(sel["actif"]), key=f"act_{sel['id']}")
                new_pwd = st.text_input("Nouveau mot de passe (laisser vide pour ne pas changer)",
                                        type="password", key=f"pwd_{sel['id']}")
                ok2 = st.form_submit_button("Enregistrer")
            if ok2:
                try:
                    ms.update_user(user, sel["id"], new_nom, actif)
                    if new_pwd:
                        ms.reset_password(user, sel["id"], new_pwd)
                    st.success("Modifications enregistrées.")
                    st.rerun()
                except ERRORS as e:
                    st.error(str(e))

    if team:
        st.divider()
        with st.expander("🗑️ Supprimer un collaborateur"):
            st.warning("La suppression est **définitive** : le compte, ses éléments à évaluer et toutes ses "
                       "évaluations (auto-évaluations et évaluations manager) sont effacés. "
                       "Pour simplement le retirer de l'équipe, désactivez son compte à la place.")
            victim = st.selectbox("Collaborateur à supprimer", team, key="del_user_sel",
                                  format_func=lambda u: u["nom_complet"])
            confirm = st.checkbox(f"Je confirme la suppression définitive de {victim['nom_complet']}",
                                  key=f"del_user_ok_{victim['id']}")
            if st.button("Supprimer définitivement", disabled=not confirm, type="primary", key="del_user_btn"):
                try:
                    ms.delete_user(user, victim["id"])
                    st.success("Collaborateur supprimé.")
                    st.rerun()
                except ERRORS as e:
                    st.error(str(e))

# ======================= ÉLÉMENTS À ÉVALUER =======================
with tab_tasks:
    active = repo.list_collaborateurs(actif_only=True, manager_id=user["id"])
    if not active:
        st.info("Créez d'abord un collaborateur.")
    else:
        st.caption("Ces éléments (tâches, objectifs…) sont **propres à chaque collaborateur** et sont notés dans "
                   "l'évaluation (critère « Réalisation des tâches »). **Désactivez** un élément pour qu'il ne "
                   "soit plus évalué sans perdre l'historique, ou **supprimez-le** pour l'effacer de la liste.")
        c1, c2 = st.columns(2)
        who = c1.selectbox("Collaborateur", active, format_func=lambda u: u["nom_complet"], key="task_who")
        annee = c2.selectbox("Année", year_options(), key="task_year")
        tasks = repo.list_tasks(who["id"], annee)
        keys = list(STATUTS_TACHES)
        if not tasks:
            st.caption("Aucun élément pour cette année.")
        for t in tasks:
            a, b, act, d = st.columns([4, 1.5, 1, 0.7])
            a.markdown(f"• {t['description']}" if t["actif"] else f"• ~~{t['description']}~~ *(désactivé)*")
            new = b.selectbox("Statut", keys, index=keys.index(t["statut"]), format_func=STATUTS_TACHES.get,
                              key=f"mt_{t['id']}", label_visibility="collapsed")
            if new != t["statut"]:
                ms.update_task_status(user, t["id"], new)
                st.rerun()
            on = act.checkbox("Actif", value=bool(t["actif"]), key=f"ta_{t['id']}")
            if on != bool(t["actif"]):
                ms.set_task_active(user, t["id"], on)
                st.rerun()
            if d.button("🗑️", key=f"del_{t['id']}", help="Supprimer l'élément"):
                ms.delete_task(user, t["id"])
                st.rerun()
        with st.form("new_task", clear_on_submit=True):
            desc = st.text_input("Nouvel élément à évaluer")
            statut = st.selectbox("Statut", keys, format_func=STATUTS_TACHES.get)
            if st.form_submit_button("Ajouter l'élément", type="primary"):
                try:
                    ms.add_task(user, who["id"], desc, statut, annee)
                    st.rerun()
                except ERRORS as e:
                    st.error(str(e))
        if tasks:
            with st.expander(f"🗑️ Supprimer tous les éléments {annee} de {who['nom_complet']}"):
                ok_all = st.checkbox("Je confirme la suppression de tous ces éléments",
                                     key=f"del_tasks_ok_{who['id']}_{annee}")
                if st.button("Tout supprimer", disabled=not ok_all, key="del_tasks_btn"):
                    n = ms.delete_tasks_year(user, who["id"], annee)
                    st.success(f"{n} élément(s) supprimé(s).")
                    st.rerun()

# ============================== ÉVALUATIONS ==============================
with tab_evals:
    st.subheader("Fréquence des évaluations de l'équipe")
    current = repo.get_user(user["id"])["periodicite"]
    keys_p = list(PERIODICITES)
    f1, f2 = st.columns([2, 1])
    choice = f1.radio("Les évaluations de votre équipe sont :", keys_p, index=keys_p.index(current),
                      horizontal=True, format_func=PERIODICITES.get,
                      help="Annuelle : 1 évaluation par an · Semestrielle : 2 · Trimestrielle : 4. "
                           "Les évaluations déjà enregistrées sont conservées si vous changez.")
    if choice != current:
        ms.set_periodicity(user, user["id"], choice)
        st.toast("Fréquence enregistrée.", icon="✅")
        st.rerun()

    st.divider()
    members = repo.list_collaborateurs(actif_only=False, manager_id=user["id"])
    if not members:
        st.info("Aucun collaborateur dans votre équipe.")
    else:
        c1, c2 = st.columns(2)
        who = c1.selectbox("Collaborateur", members, format_func=lambda u: u["nom_complet"], key="ev_who")
        annee = c2.selectbox("Année", year_options(), key="ev_year")
        evals = repo.list_evaluations(annee=annee, user_id=who["id"])
        if not evals:
            st.info("Aucune évaluation enregistrée pour ce collaborateur cette année-là.")
        else:
            label = {"auto": "Auto-évaluation", "manager": "Évaluation manager"}
            st.dataframe(pd.DataFrame({
                "Période": [PERIODE_LABELS[e["periode"]] for e in evals],
                "Type": [label[e["type"]] for e in evals],
                "Statut": [STATUTS_EVAL[e["statut"]] for e in evals],
                "Score": [e["score_final"] for e in evals],
                "Dernière modification": [e["date"] for e in evals]}),
                hide_index=True, column_config={"Score": st.column_config.NumberColumn(format="%.2f")},
                **STRETCH)
            st.warning("La suppression est **définitive** (notes et commentaires compris). "
                       "Pour permettre une correction, préférez « Rouvrir » dans la page « Évaluer ».")
            pick = st.selectbox("Évaluation à supprimer", evals, key="ev_pick",
                                format_func=lambda e: f"{PERIODE_LABELS[e['periode']]} — {label[e['type']]} — "
                                                      f"{STATUTS_EVAL[e['statut']]}")
            ok_ev = st.checkbox("Je confirme la suppression définitive de cette évaluation",
                                key=f"ev_ok_{who['id']}_{annee}_{pick['periode']}_{pick['type']}")
            if st.button("🗑️ Supprimer l'évaluation", disabled=not ok_ev, type="primary", key="ev_del_btn"):
                try:
                    ms.delete_evaluation(user, who["id"], annee, pick["periode"], pick["type"])
                    st.success("Évaluation supprimée.")
                    st.rerun()
                except ERRORS as e:
                    st.error(str(e))
