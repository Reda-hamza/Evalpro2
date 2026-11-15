import pandas as pd
import streamlit as st

from components.compat import STRETCH
from components.styles import page_header
from config import PERIODE_LABELS, SCORE_LABELS, STATUTS_TACHES, periode_label, year_options
from database import repository as repo
from services import evaluation_service as es
from services import management_service as ms
from services.auth_service import current_user
from services.scoring_service import mention, weighted_score

user = current_user()
is_mgr = user["role"] == "manager"
page_header("📝 Évaluation", "Évaluation manager" if is_mgr else "Auto-évaluation")
ERRORS = (ValueError, ms.PermissionDenied)

c1, c2, c3 = st.columns(3)
with c1:
    annee = st.selectbox("Année", year_options(), key="eval_year")
if is_mgr:
    collabs = repo.list_collaborateurs(actif_only=True, manager_id=user["id"])
    if not collabs:
        st.info("Aucun collaborateur actif dans votre équipe.")
        st.stop()
    with c3:
        target = st.selectbox("Collaborateur", collabs, format_func=lambda u: u["nom_complet"],
                              key="eval_target")
    etype = "manager"
else:
    target, etype = user, "auto"

periodicite = es.periodicity_of(target["id"])
options = es.period_options(periodicite, annee, user_id=target["id"])
with c2:
    periode = st.selectbox("Période", options, index=es.default_period_index(options, periodicite, annee),
                           format_func=PERIODE_LABELS.get, key=f"eval_period_{target['id']}_{annee}")
st.caption(f"Évaluation **{periode_label(periode, annee)}**")

existing = repo.get_evaluation(target["id"], annee, periode, etype)
locked = bool(existing and existing["statut"] == "soumise")
elements = repo.list_tasks(target["id"], annee, actif_only=True)

# ---------- Aides pour le manager ----------
auto_ref, auto_items = {}, {}
if is_mgr:
    auto_ev = repo.get_evaluation(target["id"], annee, periode, "auto")
    if auto_ev and auto_ev["statut"] == "soumise":
        auto_ref = {s["criterion_id"]: s for s in auto_ev["scores"]}
        auto_items = {i["task_id"]: i for i in auto_ev["items"]}
        with st.expander("Rouvrir l'auto-évaluation du collaborateur"):
            st.caption("Permet au collaborateur de la modifier à nouveau.")
            if st.button("Rouvrir l'auto-évaluation"):
                ms.reopen_evaluation(user, target["id"], annee, periode, "auto")
                st.rerun()

# ---------- Évaluation soumise : lecture seule ----------
if locked:
    st.success(f"Évaluation soumise (score final : {existing['score_final']:.2f} / 5 — "
               f"{mention(existing['score_final'])}).")
    df = pd.DataFrame(existing["scores"])[["nom", "poids", "score", "commentaire"]]
    df.columns = ["Critère", "Poids (%)", "Note", "Commentaire"]
    st.dataframe(df, hide_index=True, column_config={"Note": st.column_config.NumberColumn(format="%.2f")},
                 **STRETCH)
    if existing["items"]:
        st.markdown("**Éléments évalués**")
        idf = pd.DataFrame(existing["items"])[["libelle", "score", "commentaire"]]
        idf.columns = ["Élément", "Note", "Commentaire"]
        st.dataframe(idf, hide_index=True, **STRETCH)
    if existing["commentaires"]:
        st.markdown(f"**Commentaire général :** {existing['commentaires']}")
    if is_mgr and st.button("Rouvrir cette évaluation"):
        ms.reopen_evaluation(user, target["id"], annee, periode, etype)
        st.rerun()
    st.stop()

# ---------- Formulaire ----------
criteria = repo.list_criteria(active_only=True)
if not criteria:
    st.warning("Aucun critère actif. L'administrateur doit en définir dans « Critères & paramètres ».")
    st.stop()

prev = {s["criterion_id"]: s for s in existing["scores"]} if existing else {}
prev_items = {i["task_id"]: i for i in existing["items"]} if existing else {}
element_crit = next((c for c in criteria if c["mode"] == "elements"), None)
st.caption("Notez de 1 à 5. Une évaluation soumise n'est plus modifiable.")

values, item_values = {}, []
prefix = f"{etype}_{target['id']}_{annee}_{periode}"
for cr in criteria:
    with st.container(border=True):
        st.markdown(f"**{cr['nom']}** · poids {cr['poids']:g} %")
        if cr["description"]:
            st.caption(cr["description"])

        # --- critère noté à partir des éléments propres au collaborateur
        if cr is element_crit and elements:
            notes = []
            for t in elements:
                with st.container(border=True):
                    st.markdown(f"🔹 {t['description']}")
                    if t["id"] in auto_items:
                        st.caption(f"Auto-évaluation du collaborateur : {auto_items[t['id']]['score']} / 5")
                    p = prev_items.get(t["id"])
                    sc = st.radio("Note", [1, 2, 3, 4, 5], index=(p["score"] - 1) if p else 2,
                                  horizontal=True, key=f"is_{prefix}_{t['id']}",
                                  format_func=lambda x: f"{x} – {SCORE_LABELS[x]}",
                                  label_visibility="collapsed")
                    cm = st.text_input("Commentaire", value=(p["commentaire"] or "") if p else "",
                                       key=f"ic_{prefix}_{t['id']}", placeholder="Commentaire (optionnel)")
                    notes.append(sc)
                    item_values.append((t["id"], t["description"], sc, cm.strip()))
            avg = round(sum(notes) / len(notes), 2)
            st.info(f"Note du critère (moyenne des {len(notes)} élément(s)) : **{avg:.2f} / 5**")
            values[cr["id"]] = (avg, "", cr["poids"])
            continue

        # --- critère noté directement
        if cr is element_crit and not elements:
            st.caption("Aucun élément à évaluer pour ce collaborateur cette année : "
                       "note saisie directement (le manager peut en ajouter dans « Mon équipe »).")
        p = prev.get(cr["id"])
        if cr["id"] in auto_ref:
            st.caption(f"Auto-évaluation du collaborateur : {auto_ref[cr['id']]['score']:g} / 5")
        default = int(round(p["score"])) if p else 3
        score = st.radio("Note", [1, 2, 3, 4, 5], index=min(max(default, 1), 5) - 1, horizontal=True,
                         format_func=lambda x: f"{x} – {SCORE_LABELS[x]}", key=f"s_{prefix}_{cr['id']}",
                         label_visibility="collapsed")
        com = st.text_area("Commentaire", value=(p["commentaire"] or "") if p else "",
                           key=f"c_{prefix}_{cr['id']}", height=70, placeholder="Commentaire (optionnel)")
        values[cr["id"]] = (score, com.strip(), cr["poids"])

general = st.text_area("Commentaire général", value=(existing["commentaires"] or "") if existing else "",
                       key=f"g_{prefix}", height=100)

live = weighted_score([(s, w) for s, _, w in values.values()])
st.metric("Score pondéré estimé", f"{live:.2f} / 5", help=mention(live))

b1, b2, _ = st.columns([1, 1, 3])
if b1.button("💾 Enregistrer le brouillon", **STRETCH):
    try:
        es.save_evaluation(user, target["id"], annee, periode, etype, values, item_values,
                           general.strip(), submit=False)
        st.toast("Brouillon enregistré.", icon="💾")
    except ERRORS as e:
        st.error(str(e))
if b2.button("✅ Soumettre", type="primary", **STRETCH):
    try:
        es.save_evaluation(user, target["id"], annee, periode, etype, values, item_values,
                           general.strip(), submit=True)
        st.rerun()
    except ERRORS as e:
        st.error(str(e))
