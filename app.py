"""Point d'entrée : streamlit run app.py"""
import streamlit as st

from components.compat import STRETCH

from components.styles import inject_css, page_header
from config import APP_TITLE, ROLE_LABELS
from database.connection import init_db
from database.seed import seed
from services import audit_service as audit
from services.auth_service import authenticate, current_user, login, logout

st.set_page_config(page_title=APP_TITLE, page_icon="📋", layout="wide")

_major, _minor = (int(x) for x in st.__version__.split(".")[:2])
if (_major, _minor) < (1, 40):
    st.error(f"Streamlit {st.__version__} est trop ancien. Mettez-le à jour : "
             "`pip install --upgrade streamlit`")
    st.stop()


@st.cache_resource
def bootstrap() -> bool:
    init_db()
    seed()
    return True


def login_page() -> None:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        page_header("📋 Évaluation annuelle", "Connectez-vous pour accéder à votre espace")
        with st.form("login"):
            username = st.text_input("Nom d'utilisateur")
            password = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter", type="primary", **STRETCH)
        if ok:
            user = authenticate(username, password)
            if user:
                login(user)
                audit.log("LOGIN", actor=user)
                st.rerun()
            audit.log("LOGIN_FAILED", f"identifiant saisi : {username.strip()}",
                      actor={"id": None, "username": username.strip() or "—", "role": None})
            st.error("Identifiants incorrects ou compte désactivé.")


bootstrap()
inject_css()
user = current_user()

if not user:
    login_page()
    st.stop()

if user["must_change_password"]:
    pages = [st.Page("views/compte.py", title="Changer mon mot de passe", icon="🔑", default=True)]
elif user["role"] == "admin":
    pages = [
        st.Page("views/admin_dashboard.py", title="Administration", icon="🛡️", default=True),
        st.Page("views/admin_users.py", title="Utilisateurs", icon="👥"),
        st.Page("views/admin_data.py", title="Évaluations & tâches", icon="🗂️"),
        st.Page("views/resultats.py", title="Résultats", icon="📈"),
        st.Page("views/admin_journal.py", title="Journal d'activité", icon="📜"),
        st.Page("views/parametres.py", title="Critères & paramètres", icon="⚙️"),
        st.Page("views/compte.py", title="Mon compte", icon="🔑"),
    ]
elif user["role"] == "manager":
    pages = [
        st.Page("views/dashboard.py", title="Tableau de bord", icon="📊", default=True),
        st.Page("views/evaluation.py", title="Évaluer", icon="📝"),
        st.Page("views/resultats.py", title="Résultats", icon="📈"),
        st.Page("views/collaborateurs.py", title="Mon équipe", icon="👥"),
        st.Page("views/compte.py", title="Mon compte", icon="🔑"),
    ]
else:
    pages = [
        st.Page("views/dashboard.py", title="Mon espace", icon="🏠", default=True),
        st.Page("views/evaluation.py", title="Mon auto-évaluation", icon="📝"),
        st.Page("views/resultats.py", title="Mes résultats", icon="📈"),
        st.Page("views/compte.py", title="Mon compte", icon="🔑"),
    ]

nav = st.navigation(pages)
with st.sidebar:
    st.markdown(f"👤 **{user['nom_complet']}**")
    st.caption(ROLE_LABELS[user["role"]])
    if st.button("Se déconnecter", **STRETCH):
        audit.log("LOGOUT")
        logout()
        st.rerun()
nav.run()
