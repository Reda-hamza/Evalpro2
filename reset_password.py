"""Secours serveur : réinitialise le mot de passe d'un compte (ex. administrateur oublié).

Usage : python reset_password.py
Le mot de passe temporaire devra être changé à la prochaine connexion.
"""
import getpass

from config import MIN_PASSWORD_LENGTH
from database import repository as repo
from database.connection import init_db
from services import audit_service as audit
from services.auth_service import hash_password

init_db()
username = input("Identifiant du compte [admin] : ").strip() or "admin"
user = repo.get_user_by_username(username)
if not user:
    raise SystemExit("Compte introuvable.")

pwd = getpass.getpass(f"Mot de passe temporaire ({MIN_PASSWORD_LENGTH} caractères min.) : ")
if len(pwd) < MIN_PASSWORD_LENGTH:
    raise SystemExit("Mot de passe trop court.")

repo.set_password(user["id"], hash_password(pwd), 1)
audit.log("PASSWORD_RESET", f"compte « {username} » (script serveur)",
          actor={"id": None, "username": "(script serveur)", "role": None})
print("Mot de passe réinitialisé. Le changement sera demandé à la prochaine connexion.")
