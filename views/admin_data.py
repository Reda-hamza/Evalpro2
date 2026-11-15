import pandas as pd
import streamlit as st

from components.compat import STRETCH

from components.styles import page_header
from config import PERIODE_LABELS, PERIODES_ORDRE, STATUTS_EVAL, STATUTS_TACHES, year_options
from database import repository as repo
from services import management_service as ms
from services.auth_service import current_user

admin = current_user()
if admin["role"] != "admin":
    st.error("Accès réservé à l'administrateur.")
    st.stop()

page_header("🗂️ Évaluations & tâches", "Consulter, rouvrir ou supprimer les données de toutes les équipes")
ERRORS = (ValueError, ms.PermissionDenied)
TYPE = {"auto": "Auto-évaluation", "manager": "Évaluation manager"}

c1, c2, c3, c4 = st.columns(4)
annee = c1.selectbox("Année", year_options(), key="ad_year")
periode_f = c4.selectbox("Période", [None] + PERIODES_ORDRE, key="ad_period",
                         format_func=lambda p: "Toutes" if p is None else PERIODE_LABELS[p])
boss = c2.selectbox("Équipe", [None] + repo.list_managers(), key="ad_boss",
                    format_func=lambda m: "Toutes les équipes" if m is None else m["nom_complet"])
members = repo.list_collaborateurs(actif_only=False, manager_id=boss["id"] if boss else None)
who = c3.selectbox("Collaborateur", [None] + members, key="ad_who",
                   format_func=lambda u: "Tous" if u is None else u["nom_complet"])
boss_id = boss["id"] if boss else None
who_id = who["id"] if who else None

tab_ev, tab_tasks = st.tabs(["Évaluations", "Éléments à évaluer"])

with tab_ev:
    evals = repo.list_evaluations(annee=annee, user_id=who_id, manager_id=boss_id, periode=periode_f)
    if not evals:
        st.info("Aucune évaluation pour ces filtres.")
    else:
        st.dataframe(pd.DataFrame({
            "Collaborateur": [e["nom_complet"] for e in evals],
            "Période": [PERIODE_LABELS[e["periode"]] for e in evals],
            "Type": [TYPE[e["type"]] for e in evals],
            "Statut": [STATUTS_EVAL[e["statut"]] for e in evals],
            "Score": [e["score_final"] for e in evals],
            "Évaluateur": [e["evaluateur"] or "—" for e in evals],
            "Dernière modification (UTC)": [e["date"] for e in evals]}),
            hide_index=True, **STRETCH,
            column_config={"Score": st.column_config.NumberColumn(format="%.2f")})
        pick = st.selectbox("Évaluation concernée", evals, key="ad_ev_pick",
                            format_func=lambda e: f"{e['nom_complet']} — {PERIODE_LABELS[e['periode']]} — {TYPE[e['type']]} — "
                                                  f"{STATUTS_EVAL[e['statut']]}")
        b1, b2 = st.columns(2)
        with b1:
            if pick["statut"] == "soumise" and st.button("↩️ Rouvrir (repasser en brouillon)"):
                ms.reopen_evaluation(admin, pick["user_id"], annee, pick["periode"], pick["type"])
                st.rerun()
        with b2:
            ok = st.checkbox("Je confirme la suppression définitive", key=f"ad_ev_ok_{pick['id']}")
            if st.button("🗑️ Supprimer l'évaluation", disabled=not ok, type="primary"):
                try:
                    ms.delete_evaluation(admin, pick["user_id"], annee, pick["periode"], pick["type"])
                    st.success("Évaluation supprimée.")
                    st.rerun()
                except ERRORS as e:
                    st.error(str(e))

with tab_tasks:
    tasks = repo.list_tasks_scope(annee, boss_id, who_id)
    if not tasks:
        st.info("Aucune tâche pour ces filtres.")
    else:
        st.dataframe(pd.DataFrame({
            "Collaborateur": [t["collaborateur"] for t in tasks],
            "Élément": [t["description"] for t in tasks],
            "Actif": [bool(t["actif"]) for t in tasks],
            "Statut": [STATUTS_TACHES[t["statut"]] for t in tasks]}),
            hide_index=True, **STRETCH)
        pick_t = st.selectbox("Élément concerné", tasks, key="ad_task_pick",
                              format_func=lambda t: f"{t['collaborateur']} — {t['description']}")
        if st.button("Désactiver" if pick_t["actif"] else "Activer", key="ad_task_toggle"):
            ms.set_task_active(admin, pick_t["id"], not pick_t["actif"])
            st.rerun()
        ok_t = st.checkbox("Je confirme la suppression définitive", key=f"ad_task_ok_{pick_t['id']}")
        if st.button("🗑️ Supprimer l'élément", disabled=not ok_t, type="primary"):
            try:
                ms.delete_task(admin, pick_t["id"])
                st.success("Élément supprimé.")
                st.rerun()
            except ERRORS as e:
                st.error(str(e))
