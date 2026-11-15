import streamlit as st

from components.styles import page_header
from config import MIN_PASSWORD_LENGTH
from services import audit_service as audit
from services.auth_service import authenticate, change_password, current_user

user = current_user()
forced = bool(user["must_change_password"])
page_header("🔑 Mon compte", "Vous devez choisir un nouveau mot de passe pour continuer." if forced
            else "Modifier mon mot de passe")

with st.form("pwd"):
    old = st.text_input("Mot de passe actuel", type="password")
    new = st.text_input("Nouveau mot de passe", type="password")
    confirm = st.text_input("Confirmer le nouveau mot de passe", type="password")
    ok = st.form_submit_button("Enregistrer", type="primary")

if ok:
    if not authenticate(user["username"], old):
        st.error("Mot de passe actuel incorrect.")
    elif len(new) < MIN_PASSWORD_LENGTH:
        st.error(f"Le nouveau mot de passe doit contenir au moins {MIN_PASSWORD_LENGTH} caractères.")
    elif new != confirm:
        st.error("La confirmation ne correspond pas.")
    elif new == old:
        st.error("Le nouveau mot de passe doit être différent de l'ancien.")
    else:
        change_password(user["id"], new)
        audit.log("PASSWORD_CHANGED", "par l'utilisateur lui-même")
        user["must_change_password"] = 0
        st.session_state["user"] = user
        st.success("Mot de passe modifié.")
        st.rerun()
