import sqlite3

import pandas as pd
import streamlit as st

from components.compat import STRETCH

from components.styles import page_header
from config import CRITERION_MODES, VISIBILITY_MODES
from database import repository as repo
from services import audit_service as audit
from services.auth_service import current_user

if current_user()["role"] != "admin":
    st.error("Accès réservé à l'administrateur.")
    st.stop()

page_header("⚙️ Critères & paramètres", "Pondérations, critères et visibilité des résultats")

st.subheader("Visibilité de l'évaluation du manager")
modes = list(VISIBILITY_MODES)
current = repo.get_setting("visibility_mode", "after_both")
choice = st.radio("Le collaborateur voit son évaluation manager :", modes, index=modes.index(current),
                  format_func=VISIBILITY_MODES.get)
if choice != current:
    repo.set_setting("visibility_mode", choice)
    audit.log("SETTING_CHANGED", f"visibilité de l'évaluation manager : {choice}")
    st.toast("Paramètre enregistré.", icon="✅")

st.subheader("Critères d'évaluation")
st.caption("Les modifications de pondération n'affectent pas les évaluations déjà enregistrées "
           "(le poids appliqué est conservé).")
crit = repo.list_criteria(active_only=False)
df = pd.DataFrame(crit)[["id", "nom", "description", "poids", "ordre", "mode", "actif"]]
df["actif"] = df["actif"].astype(bool)
edited = st.data_editor(
    df, hide_index=True, **STRETCH, key="crit_editor",
    column_config={
        "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
        "nom": "Nom", "description": "Description",
        "poids": st.column_config.NumberColumn("Poids (%)", min_value=1, max_value=100, step=1),
        "ordre": st.column_config.NumberColumn("Ordre", step=1), "actif": "Actif",
        "mode": st.column_config.SelectboxColumn("Mode de notation", options=list(CRITERION_MODES),
                                                 required=True, help="« elements » : la note du critère est la "
                                                 "moyenne des éléments à évaluer propres à chaque collaborateur"),
    })
total = float(edited.loc[edited["actif"], "poids"].sum())
if abs(total - 100) < 0.01:
    st.success("Total des poids actifs : 100 % ✅")
else:
    st.warning(f"Total des poids actifs : {total:g} %. Le score reste calculé proportionnellement, "
               "mais un total de 100 % est recommandé.")

st.caption("Mode « elements » : la note du critère est la moyenne des éléments à évaluer propres à "
           "chaque collaborateur (créés par le manager). Mode « manuel » : note saisie directement. "
           "Un seul critère actif peut utiliser le mode « elements ».")
if st.button("💾 Enregistrer les critères", type="primary"):
    try:
        if int(((edited["mode"] == "elements") & edited["actif"]).sum()) > 1:
            raise ValueError("Un seul critère actif peut utiliser le mode « elements ».")
        for r in edited.to_dict("records"):
            if not str(r["nom"]).strip() or not r["poids"] or r["poids"] <= 0:
                raise ValueError("Chaque critère doit avoir un nom et un poids > 0.")
            repo.update_criterion(int(r["id"]), str(r["nom"]).strip(), r["description"] or "",
                                  float(r["poids"]), int(r["ordre"]), bool(r["actif"]), r["mode"])
        audit.log("CRITERIA_UPDATED", f"{len(edited)} critère(s), total actif {total:g} %")
        st.success("Critères mis à jour.")
        st.rerun()
    except ValueError as e:
        st.error(str(e))
    except sqlite3.IntegrityError:
        st.error("Deux critères ne peuvent pas avoir le même nom.")

with st.expander("➕ Ajouter un critère"):
    with st.form("new_crit", clear_on_submit=True):
        nom = st.text_input("Nom")
        desc = st.text_input("Description")
        poids = st.number_input("Poids (%)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
        ordre = st.number_input("Ordre", min_value=0, value=len(crit) + 1, step=1)
        mode = st.selectbox("Mode de notation", list(CRITERION_MODES), format_func=CRITERION_MODES.get)
        if st.form_submit_button("Ajouter"):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            elif mode == "elements" and any(c["mode"] == "elements" and c["actif"] for c in crit):
                st.error("Un critère actif utilise déjà le mode « elements ».")
            else:
                try:
                    repo.add_criterion(nom.strip(), desc.strip(), poids, int(ordre), mode)
                    audit.log("CRITERION_ADDED", f"« {nom.strip()} » ({poids:g} %)")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Ce critère existe déjà.")
