from datetime import date, timedelta

import plotly.graph_objects as go
import streamlit as st

from components.compat import STRETCH

from components.styles import page_header
from database import repository as repo
from services import audit_service as audit
from services import export_service as ex
from services.auth_service import current_user

if current_user()["role"] != "admin":
    st.error("Accès réservé à l'administrateur.")
    st.stop()

page_header("📜 Journal d'activité", "Historique d'utilisation : connexions, créations, modifications, suppressions, exports")

c1, c2, c3 = st.columns(3)
period = c1.date_input("Période", (date.today() - timedelta(days=7), date.today()), key="jr_period")
user_pick = c2.selectbox("Utilisateur", [None] + repo.list_log_usernames(), key="jr_user",
                         format_func=lambda u: "Tous" if u is None else u)
action_pick = c3.selectbox("Action", [None] + list(audit.ACTION_LABELS), key="jr_action",
                           format_func=lambda a: "Toutes" if a is None else audit.ACTION_LABELS[a])

if isinstance(period, (tuple, list)) and len(period) == 2:
    d_from, d_to = period
elif isinstance(period, (tuple, list)) and len(period) == 1:
    d_from = d_to = period[0]
else:
    d_from = d_to = period

df = audit.query_logs(d_from, d_to, user_pick, action_pick)
m1, m2, m3, m4 = st.columns(4)
m1.metric("Événements", len(df))
m2.metric("Connexions", int((df["code"] == "LOGIN").sum()))
m3.metric("Échecs de connexion", int((df["code"] == "LOGIN_FAILED").sum()))
m4.metric("Suppressions", int(df["code"].isin(["USER_DELETED", "EVAL_DELETED", "TASK_DELETED",
                                               "TASKS_DELETED"]).sum()))

if df.empty:
    st.info("Aucun événement pour ces filtres.")
    st.stop()

per_day = df.assign(Jour=df["Date / heure"].str[:10]).groupby("Jour").size()
per_day = per_day.sort_index(key=lambda idx: idx.str[6:10] + idx.str[3:5] + idx.str[:2])
fig = go.Figure(go.Bar(x=per_day.index, y=per_day.values, marker_color="#1B998B"))
fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor="rgba(0,0,0,0)",
                  plot_bgcolor="rgba(0,0,0,0)", yaxis_title="Événements / jour")
st.plotly_chart(fig, **STRETCH)

shown = df.drop(columns=["code"])
st.dataframe(shown, hide_index=True, **STRETCH, height=420)
st.caption("Heures affichées en heure locale. Le journal est en lecture seule : "
           "il ne peut être ni modifié ni supprimé depuis l'application.")
e1, e2 = st.columns(2)
e1.download_button("📥 Export Excel", ex.excel_logs(df), file_name="journal_activite.xlsx", **STRETCH,
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   on_click=lambda: audit.log("EXPORT", "Journal d'activité (Excel)"))
e2.download_button("📄 Export CSV", shown.to_csv(index=False).encode("utf-8-sig"),
                   file_name="journal_activite.csv", mime="text/csv", **STRETCH,
                   on_click=lambda: audit.log("EXPORT", "Journal d'activité (CSV)"))
