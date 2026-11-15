import pandas as pd
import streamlit as st

from components.compat import STRETCH

from components import charts
from components.styles import page_header
from config import PERIODE_LABELS, STATUTS_EVAL, STATUTS_TACHES, periode_label, year_options
from database import repository as repo
from services import evaluation_service as es
from services import management_service as ms
from services.auth_service import current_user
from services.scoring_service import mention

user = current_user()
periodicite = es.periodicity_of(user["id"])
c_year, c_per, _ = st.columns(3)
annee = c_year.selectbox("Année", year_options(), key="dash_year")
options = es.period_options(periodicite, annee, **({"manager_id": user["id"]} if user["role"] == "manager"
                                                    else {"user_id": user["id"]}))
periode = c_per.selectbox("Période", options, index=es.default_period_index(options, periodicite, annee),
                          format_func=PERIODE_LABELS.get, key=f"dash_period_{annee}")


def statut_label(s):
    return STATUTS_EVAL.get(s, "⏳ À faire")


def fmt(v):
    return "—" if v is None or v != v else f"{v:.2f}"


# ------------------------------------------------------------------ MANAGER
if user["role"] == "manager":
    page_header("📊 Tableau de bord", f"Vue d'ensemble de votre équipe — {periode_label(periode, annee)}")
    team = es.team_summary(annee, periode, user["id"])
    if team.empty:
        st.info("Aucun collaborateur dans votre équipe. Ajoutez-en depuis la page « Mon équipe ».")
        st.stop()

    n = len(team)
    auto_ok = int((team["Statut auto"] == "soumise").sum())
    mgr_ok = int((team["Statut manager"] == "soumise").sum())
    avg = team["Manager"].mean()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Collaborateurs", n)
    c2.metric("Auto-évaluations soumises", f"{auto_ok} / {n}")
    c3.metric("Évaluations manager soumises", f"{mgr_ok} / {n}")
    c4.metric("Moyenne équipe (manager)", fmt(avg) if avg == avg else "—")

    view = pd.DataFrame({
        "Collaborateur": team["Collaborateur"],
        "Auto-évaluation": team["Statut auto"].map(statut_label),
        "Évaluation manager": team["Statut manager"].map(statut_label),
        "Score auto": team["Auto"], "Score manager": team["Manager"],
        "Écart": team["Écart"], "Mention": team["Mention"],
    })
    st.dataframe(view, hide_index=True, **STRETCH,
                 column_config={c: st.column_config.NumberColumn(format="%.2f")
                                for c in ("Score auto", "Score manager", "Écart")})
    if team[["Auto", "Manager"]].notna().any().any():
        st.plotly_chart(charts.team_bar(team), **STRETCH)

# ------------------------------------------------------------- COLLABORATEUR
else:
    page_header(f"🏠 Bonjour {user['nom_complet'].split()[0]}", f"Votre espace — {periode_label(periode, annee)}")

    st.subheader("Mes tâches / éléments à évaluer")
    tasks = repo.list_tasks(user["id"], annee, actif_only=True)
    if not tasks:
        st.info("Aucun élément assigné pour cette année.")
    else:
        actives = [t for t in tasks if t["statut"] != "annulee"]
        done = sum(t["statut"] == "terminee" for t in actives)
        if actives:
            st.progress(done / len(actives), text=f"{done} / {len(actives)} tâche(s) terminée(s)")
        keys = list(STATUTS_TACHES)
        for t in tasks:
            c1, c2 = st.columns([3, 1])
            c1.markdown(f"• {t['description']}")
            new = c2.selectbox("Statut", keys, index=keys.index(t["statut"]),
                               format_func=STATUTS_TACHES.get, key=f"task_{t['id']}",
                               label_visibility="collapsed")
            if new != t["statut"]:
                ms.update_task_status(user, t["id"], new)
                st.rerun()

    st.subheader(f"Mon évaluation — {periode_label(periode, annee)}")
    auto = repo.get_evaluation(user["id"], annee, periode, "auto")
    bundle = es.get_bundle(user, user["id"], annee, periode)
    c1, c2 = st.columns(2)
    with c1, st.container(border=True):
        st.markdown("**Auto-évaluation**")
        st.write(statut_label(auto["statut"] if auto else None))
        if bundle["auto"]:
            st.metric("Mon score", f"{bundle['auto']['score_final']:.2f} / 5")
        else:
            st.caption("Rendez-vous dans « Mon auto-évaluation » pour la compléter.")
    with c2, st.container(border=True):
        st.markdown("**Évaluation du manager**")
        if bundle["manager"]:
            st.metric("Score manager", f"{bundle['manager']['score_final']:.2f} / 5",
                      help=mention(bundle["manager"]["score_final"]))
        else:
            st.write("🔒 Pas encore disponible")
