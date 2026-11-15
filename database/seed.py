"""Données initiales : critères par défaut, compte administrateur, paramètres."""
from config import DEFAULT_ADMIN, DEFAULT_CRITERIA
from database.connection import get_conn
from services.auth_service import hash_password


def seed() -> None:
    with get_conn() as conn:
        if conn.execute("SELECT COUNT(*) FROM criteria").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO criteria (nom, description, poids, ordre, mode) VALUES (?,?,?,?,?)",
                DEFAULT_CRITERIA,
            )
        if conn.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0] == 0:
            conn.execute(
                "INSERT OR IGNORE INTO users (username, password_hash, role, nom_complet, "
                "must_change_password) VALUES (?,?,?,?,1)",
                (DEFAULT_ADMIN["username"], hash_password(DEFAULT_ADMIN["password"]),
                 "admin", DEFAULT_ADMIN["nom_complet"]))
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('visibility_mode', 'after_both')")
