"""Connexion SQLite et initialisation du schéma."""
import sqlite3
from contextlib import contextmanager

from config import BASE_DIR, DB_PATH


@contextmanager
def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _cols(conn, table: str) -> list[str]:
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]


def _statements(sql: str):
    """Découpe un script SQL en instructions (pour une migration atomique)."""
    buf = ""
    for line in sql.splitlines(keepends=True):
        buf += line
        if sqlite3.complete_statement(buf):
            yield buf.strip()
            buf = ""


def _needs_migration(conn) -> bool:
    """Base créée par une version précédente (rôle admin, cadence, éléments, périodes)."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if not row:
        return False
    return ("'admin'" not in row["sql"] or "periodicite" not in _cols(conn, "users")
            or "periode" not in _cols(conn, "evaluations"))


def _migrate(conn, schema: str) -> None:
    """Reconstruit les tables users et evaluations (nouvelles contraintes) en conservant les données.
    - ancienne base sans équipes : les collaborateurs sont rattachés au premier manager
    - les évaluations existantes deviennent des évaluations annuelles (période « A »)
    - le critère « Réalisation des tâches » passe en mode « éléments »."""
    old_users = _cols(conn, "users")
    conn.executescript("PRAGMA foreign_keys = OFF; PRAGMA legacy_alter_table = ON;")
    try:
        conn.execute("BEGIN")
        if "actif" not in _cols(conn, "tasks"):
            conn.execute("ALTER TABLE tasks ADD COLUMN actif INTEGER NOT NULL DEFAULT 1")
        new_mode = "mode" not in _cols(conn, "criteria")
        if new_mode:
            conn.execute("ALTER TABLE criteria ADD COLUMN mode TEXT NOT NULL DEFAULT 'manuel' "
                         "CHECK (mode IN ('manuel','elements'))")
        for ix in ("idx_eval_user_annee", "idx_users_manager"):
            conn.execute(f"DROP INDEX IF EXISTS {ix}")
        conn.execute("ALTER TABLE users RENAME TO users_old")
        conn.execute("ALTER TABLE evaluations RENAME TO evaluations_old")
        for stmt in _statements(schema):
            conn.execute(stmt)
        for table in ("users", "evaluations"):
            common = [c for c in _cols(conn, table) if c in _cols(conn, f"{table}_old")]
            cols = ", ".join(common)
            conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM {table}_old")
        if "manager_id" not in old_users:
            conn.execute("UPDATE users SET manager_id = (SELECT MIN(id) FROM users WHERE role='manager') "
                         "WHERE role='collaborateur'")
        if new_mode:
            conn.execute("UPDATE criteria SET mode='elements' WHERE nom='Réalisation des tâches'")
        conn.execute("DROP TABLE evaluations_old")
        conn.execute("DROP TABLE users_old")
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.executescript("PRAGMA legacy_alter_table = OFF; PRAGMA foreign_keys = ON;")
    conn.executescript(schema)   # recrée les index éventuellement perdus


def init_db() -> None:
    schema = (BASE_DIR / "database" / "schema.sql").read_text(encoding="utf-8")
    with get_conn() as conn:
        if _needs_migration(conn):
            _migrate(conn, schema)
        else:
            conn.executescript(schema)
