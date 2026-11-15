"""Authentification (bcrypt) et gestion de session Streamlit."""
import bcrypt
import streamlit as st

from database import repository as repo


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def authenticate(username: str, password: str) -> dict | None:
    user = repo.get_user_by_username(username.strip())
    if user and user["actif"] and verify_password(password, user["password_hash"]):
        user.pop("password_hash")
        return user
    return None


def current_user() -> dict | None:
    return st.session_state.get("user")


def login(user: dict) -> None:
    st.session_state["user"] = user


def logout() -> None:
    st.session_state.clear()


def change_password(user_id: int, new_password: str, must_change: int = 0) -> None:
    repo.set_password(user_id, hash_password(new_password), must_change)
