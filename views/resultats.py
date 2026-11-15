import streamlit as st

from components.compat import STRETCH

from components import charts
from components.styles import page_header
from config import PERIODE_LABELS, periode_label, year_options
from database import repository as repo
from services import evaluation_service as es
from services import audit_service as audit
from services import export_service as ex
from services.auth_service import current_user
from services.scoring_service import mention, to_percent

user = current_user()
is_mgr = user["role"] in ("manager", "admin")   # accès « équipe »
page_header("📈 Résultats", "Synthèse, comparaison auto vs manager et historique")

c1, c2, c3 = st.columns(3)
with c1:
    annee = st.selectbox("Année", year_options(), key="res_year")
target = user
scope_id = user["id"] if user["role"] == "manager" else None   # None = toutes les équipes (admin)
if user["role"] == "admin":
    with c3:
        pick = st.selectbox("Équipe", [None] + repo.list_managers(), key="res_team",
                            format_func=lambda m: "Toutes les équipes" if m is None else m["nom_complet"])
    scope_id = pick["id"] if pick else None
if is_mgr:
    collabs = repo.list_collaborateurs(actif_only=False, manager_id=scope_id)
    if collabs:
        with c2:
            target = st.selectbox("Collaborateur", collabs, format_func=lambda u: u["nom_complet"],
                                  key="res_target")
    else:
        target = None

# --- période : celle de la périodicité du manager (toutes les périodes pour l'administrateur)
if user["role"] == "admin":
    periodicite, scope_kw = None, {"manager_id": scope_id}
elif user["role"] == "manager":
    periodicite, scope_kw = es.periodicity_of(user["id"]), {"manager_id": user["id"]}
else:
    periodicite, scope_kw = es.periodicity_of(user["id"]), {"user_id": user["id"]}
options = es.period_options(periodicite, annee, **scope_kw)
periode = st.columns(3)[0].selectbox("Période", options, key=f"res_period_{annee}",
                                     index=es.default_period_index(options, periodicite, annee),
                                     format_func=PERIODE_LABELS.get)
plabel = periode_label(periode, annee)

labels = ["Synthèse", "Radar", "Comparaison", "Historique"] + (["Équipe"] if is_mgr else [])
tabs = st.tabs(labels)
bundle = es.get_bundle(user, target["id"], annee, periode) if target else None
has_data = bool(bundle and (bundle["auto"] or bundle["manager"]))


def fmt(v):
    return "—" if v is None or v != v else f"{v:.2f}"


def no_data_message():
    if not is_mgr and es.repo.get_evaluation(user["id"], annee, periode, "manager") and not bundle["manager"]:
        st.info("🔒 L'évaluation du manager n'est pas encore disponible.")
    else:
        st.info("Aucune évaluation soumise pour cette année.")


with tabs[0]:
    if not has_data:
        no_data_message()
    else:
        auto, mgr = bundle["auto"], bundle["manager"]
        sa = auto["score_final"] if auto else None
        sm = mgr["score_final"] if mgr else None
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Score auto", f"{fmt(sa)} / 5")
        m2.metric("Score manager", f"{fmt(sm)} / 5",
                  f"{to_percent(sm):.0f} %" if sm is not None else None, delta_color="off")
        m3.metric("Écart (manager − auto)", f"{sm - sa:+.2f}" if sa is not None and sm is not None else "—")
        m4.metric("Mention", mention(sm if sm is not None else float("nan")))
        if not mgr and not is_mgr:
            st.caption("🔒 L'évaluation du manager n'est pas (encore) disponible.")
        st.dataframe(bundle["comparison"], hide_index=True, **STRETCH,
                     column_config={c: st.column_config.NumberColumn(format="%.1f")
                                    for c in ("Auto", "Manager", "Écart")})
        if len(bundle["items_comparison"]):
            st.markdown("**Éléments évalués**")
            st.dataframe(bundle["items_comparison"], hide_index=True,
                         column_config={c: st.column_config.NumberColumn(format="%.0f")
                                        for c in ("Auto", "Manager", "Écart")}, **STRETCH)
        for ev, label in ((auto, "Auto-évaluation"), (mgr, "Évaluation manager")):
            if ev and (ev["commentaires"] or any(s["commentaire"] for s in ev["scores"])):
                with st.expander(f"Commentaires — {label}"):
                    if ev["commentaires"]:
                        st.markdown(f"**Général :** {ev['commentaires']}")
                    for s in ev["scores"]:
                        if s["commentaire"]:
                            st.markdown(f"**{s['nom']} :** {s['commentaire']}")
        e1, e2 = st.columns(2)
        name = bundle["user"]["nom_complet"].replace(" ", "_")
        e1.download_button("📥 Export Excel", ex.excel_individual(bundle),
                           file_name=f"evaluation_{name}_{annee}_{periode}.xlsx", **STRETCH,
                           on_click=lambda: audit.log("EXPORT", f"Excel {plabel} de « {bundle['user']['nom_complet']} »"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        e2.download_button("📄 Export PDF", ex.pdf_individual(bundle),
                           file_name=f"evaluation_{name}_{annee}_{periode}.pdf", mime="application/pdf",
                           **STRETCH,
                           on_click=lambda: audit.log("EXPORT", f"PDF {plabel} de « {bundle['user']['nom_complet']} »"))

with tabs[1]:
    if has_data:
        st.plotly_chart(charts.radar(bundle["comparison"]), **STRETCH)
    else:
        no_data_message()

with tabs[2]:
    if has_data:
        st.plotly_chart(charts.grouped_bar(bundle["comparison"]), **STRETCH)
    else:
        no_data_message()

with tabs[3]:
    hist = es.history(user, target["id"]) if target else None
    if hist is not None and len(hist):
        st.plotly_chart(charts.history_line(hist), **STRETCH)
        st.dataframe(hist, hide_index=True, **STRETCH,
                     column_config={c: st.column_config.NumberColumn(format="%.2f")
                                    for c in ("Auto", "Manager")})
    else:
        st.info("Pas encore d'historique.")

if is_mgr:
    with tabs[4]:
        team = es.team_summary(annee, periode, scope_id)
        if team.empty:
            st.info("Aucun collaborateur actif.")
        else:
            st.dataframe(team.drop(columns=["Statut auto", "Statut manager"]), hide_index=True,
                         **STRETCH,
                         column_config={c: st.column_config.NumberColumn(format="%.2f")
                                        for c in ("Auto", "Manager", "Écart")})
            if team[["Auto", "Manager"]].notna().any().any():
                st.plotly_chart(charts.team_bar(team), **STRETCH)
            t1, t2 = st.columns(2)
            t1.download_button("📥 Export Excel équipe", ex.excel_team(annee, periode, team, scope_id),
                               file_name=f"equipe_{annee}_{periode}.xlsx", **STRETCH,
                               on_click=lambda: audit.log("EXPORT", f"Excel équipe {plabel}"),
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            t2.download_button("📄 Export PDF équipe", ex.pdf_team(annee, periode, team),
                               file_name=f"equipe_{annee}_{periode}.pdf", mime="application/pdf", **STRETCH,
                               on_click=lambda: audit.log("EXPORT", f"PDF équipe {plabel}"))
