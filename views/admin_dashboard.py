from datetime import date

import pandas as pd
import streamlit as st

from components.compat import STRETCH

from components.styles import page_header
from config import PERIODICITES, PERIODE_LABELS, PERIODES_ORDRE, periode_label, year_options
from database import repository as repo
from services import audit_service as audit
from services import evaluation_service as es
from services.auth_service import current_user

if current_user()["role"] != "admin":
    st.error("Accès réservé à l'administrateur.")
    st.stop()

page_header("🛡️ Administration", "Vue globale : équipes, évaluations et activité")
c_y, c_p, _ = st.columns(3)
annee = c_y.selectbox("Année", year_options(), key="adm_year")
periode = c_p.selectbox("Période", PERIODES_ORDRE, format_func=PERIODE_LABELS.get, key="adm_period")

managers = repo.list_managers()
collabs = repo.list_collaborateurs(actif_only=False)
evals = [e for e in repo.list_evaluations(annee=annee, periode=periode) if e["statut"] == "soumise"]
recent = audit.query_logs(date_from=date.today())
n_login = int((recent["code"] == "LOGIN").sum()) if len(recent) else 0
n_fail = int((recent["code"] == "LOGIN_FAILED").sum()) if len(recent) else 0

c1, c2, c3, c4 = st.columns(4)
c1.metric("Managers", sum(m["actif"] for m in managers), help="Comptes actifs")
c2.metric("Collaborateurs", sum(c["actif"] for c in collabs), help="Comptes actifs")
c3.metric(f"Évaluations soumises — {periode_label(periode, annee)}", len(evals))
c4.metric("Connexions aujourd'hui", n_login, f"{n_fail} échec(s)" if n_fail else None, delta_color="inverse")

orphans = [c for c in collabs if not c["manager_id"]]
if orphans:
    st.warning(f"{len(orphans)} collaborateur(s) sans manager de rattachement : "
               + ", ".join(c["nom_complet"] for c in orphans) + " — à corriger dans « Utilisateurs ».")

st.subheader("Équipes")
rows = []
for m in managers:
    t = es.team_summary(annee, periode, m["id"])
    rows.append({
        "Manager": m["nom_complet"] + ("" if m["actif"] else " (désactivé)"),
        "Périodicité": PERIODICITES[m["periodicite"]],
        "Collaborateurs actifs": len(t),
        "Auto soumises": int((t["Statut auto"] == "soumise").sum()) if len(t) else 0,
        "Évaluations manager soumises": int((t["Statut manager"] == "soumise").sum()) if len(t) else 0,
        "Moyenne manager": t["Manager"].mean() if len(t) else None,
    })
if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, **STRETCH,
                 column_config={"Moyenne manager": st.column_config.NumberColumn(format="%.2f")})
else:
    st.info("Aucun manager. Créez-en depuis la page « Utilisateurs ».")

st.subheader("Activité récente")
last = audit.query_logs(limit=15)
if len(last):
    st.dataframe(last.drop(columns=["code"]), hide_index=True, **STRETCH)
else:
    st.caption("Aucune activité enregistrée.")
