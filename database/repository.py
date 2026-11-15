"""Accès aux données (SQLite). Aucune logique métier ici."""
from database.connection import get_conn


def _rows(cur) -> list[dict]:
    return [dict(r) for r in cur.fetchall()]


# ---------- Paramètres ----------
def get_setting(key: str, default: str | None = None) -> str | None:
    with get_conn() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_setting(key: str, value: str) -> None:
    with get_conn() as c:
        c.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


# ---------- Utilisateurs ----------
def get_user_by_username(username: str) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    return dict(r) if r else None


def get_user(user_id: int) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return dict(r) if r else None


def list_collaborateurs(actif_only: bool = True, manager_id: int | None = None) -> list[dict]:
    sql = ("SELECT id, username, nom_complet, actif, role, manager_id FROM users "
           "WHERE role='collaborateur'")
    params: list = []
    if actif_only:
        sql += " AND actif=1"
    if manager_id is not None:
        sql += " AND manager_id=?"
        params.append(manager_id)
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY nom_complet", params))


def list_managers(actif_only: bool = False) -> list[dict]:
    sql = "SELECT id, username, nom_complet, actif, role, manager_id, periodicite FROM users WHERE role='manager'"
    if actif_only:
        sql += " AND actif=1"
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY nom_complet"))


def list_users_full() -> list[dict]:
    """Tous les comptes, avec le nom du manager de rattachement."""
    with get_conn() as c:
        return _rows(c.execute(
            """SELECT u.id, u.username, u.nom_complet, u.role, u.actif, u.manager_id, u.periodicite,
                      m.nom_complet AS manager
               FROM users u LEFT JOIN users m ON m.id = u.manager_id
               ORDER BY CASE u.role WHEN 'admin' THEN 0 WHEN 'manager' THEN 1 ELSE 2 END,
                        u.nom_complet"""))


def count_admins(actif_only: bool = True) -> int:
    sql = "SELECT COUNT(*) FROM users WHERE role='admin'" + (" AND actif=1" if actif_only else "")
    with get_conn() as c:
        return c.execute(sql).fetchone()[0]


def create_user(username, password_hash, role, nom_complet, must_change=1, manager_id=None,
                periodicite="annuelle") -> int:
    with get_conn() as c:
        cur = c.execute(
            "INSERT INTO users (username, password_hash, role, nom_complet, must_change_password, "
            "manager_id, periodicite) VALUES (?,?,?,?,?,?,?)",
            (username, password_hash, role, nom_complet, must_change, manager_id, periodicite))
        return cur.lastrowid


def set_periodicity(user_id: int, periodicite: str) -> None:
    with get_conn() as c:
        c.execute("UPDATE users SET periodicite=? WHERE id=?", (periodicite, user_id))


def update_user(user_id: int, nom_complet: str, actif: bool, manager_id: int | None = None) -> None:
    with get_conn() as c:
        c.execute("UPDATE users SET nom_complet=?, actif=?, manager_id=? WHERE id=?",
                  (nom_complet, int(actif), manager_id, user_id))


def delete_user(user_id: int) -> None:
    """Supprime le compte ; tâches et évaluations du compte partent en cascade."""
    with get_conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (user_id,))


def reassign_team(from_manager_id: int, to_manager_id: int) -> None:
    with get_conn() as c:
        c.execute("UPDATE users SET manager_id=? WHERE manager_id=?", (to_manager_id, from_manager_id))


def set_password(user_id: int, password_hash: str, must_change: int) -> None:
    with get_conn() as c:
        c.execute("UPDATE users SET password_hash=?, must_change_password=? WHERE id=?",
                  (password_hash, must_change, user_id))


# ---------- Tâches ----------
def list_tasks(user_id: int, annee: int | None = None, actif_only: bool = False) -> list[dict]:
    sql, params = "SELECT * FROM tasks WHERE user_id=?", [user_id]
    if annee is not None:
        sql += " AND annee=?"
        params.append(annee)
    if actif_only:
        sql += " AND actif=1"
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY id", params))


def add_task(user_id: int, description: str, statut: str, annee: int) -> None:
    with get_conn() as c:
        c.execute("INSERT INTO tasks (user_id, description, statut, annee) VALUES (?,?,?,?)",
                  (user_id, description, statut, annee))


def set_task_active(task_id: int, actif: bool) -> None:
    with get_conn() as c:
        c.execute("UPDATE tasks SET actif=? WHERE id=?", (int(actif), task_id))


def update_task_status(task_id: int, statut: str) -> None:
    with get_conn() as c:
        c.execute("UPDATE tasks SET statut=? WHERE id=?", (statut, task_id))


def delete_task(task_id: int) -> None:
    with get_conn() as c:
        c.execute("DELETE FROM tasks WHERE id=?", (task_id,))


def get_task(task_id: int) -> dict | None:
    with get_conn() as c:
        r = c.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(r) if r else None


def delete_tasks(user_id: int, annee: int) -> int:
    with get_conn() as c:
        return c.execute("DELETE FROM tasks WHERE user_id=? AND annee=?", (user_id, annee)).rowcount


def list_tasks_scope(annee: int, manager_id: int | None = None, user_id: int | None = None) -> list[dict]:
    sql = ("SELECT t.id, t.user_id, u.nom_complet AS collaborateur, t.description, t.statut, t.annee, t.actif "
           "FROM tasks t JOIN users u ON u.id = t.user_id WHERE t.annee=?")
    params: list = [annee]
    if manager_id is not None:
        sql += " AND u.manager_id=?"
        params.append(manager_id)
    if user_id is not None:
        sql += " AND t.user_id=?"
        params.append(user_id)
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY u.nom_complet, t.id", params))


# ---------- Critères ----------
def list_criteria(active_only: bool = True) -> list[dict]:
    sql = "SELECT * FROM criteria"
    if active_only:
        sql += " WHERE actif=1"
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY ordre, id"))


def add_criterion(nom: str, description: str, poids: float, ordre: int, mode: str = "manuel") -> None:
    with get_conn() as c:
        c.execute("INSERT INTO criteria (nom, description, poids, ordre, mode) VALUES (?,?,?,?,?)",
                  (nom, description, poids, ordre, mode))


def update_criterion(crit_id: int, nom: str, description: str, poids: float,
                     ordre: int, actif: bool, mode: str = "manuel") -> None:
    with get_conn() as c:
        c.execute("UPDATE criteria SET nom=?, description=?, poids=?, ordre=?, actif=?, mode=? WHERE id=?",
                  (nom, description, poids, ordre, int(actif), mode, crit_id))


# ---------- Évaluations ----------
def get_evaluation(user_id: int, annee: int, periode: str, type_: str) -> dict | None:
    with get_conn() as c:
        ev = c.execute("SELECT * FROM evaluations WHERE user_id=? AND annee=? AND periode=? AND type=?",
                       (user_id, annee, periode, type_)).fetchone()
        if not ev:
            return None
        ev = dict(ev)
        ev["scores"] = _rows(c.execute(
            """SELECT es.criterion_id, cr.nom, cr.ordre, cr.mode, es.score, es.commentaire,
                      es.poids_applique AS poids
               FROM evaluation_scores es JOIN criteria cr ON cr.id = es.criterion_id
               WHERE es.evaluation_id=? ORDER BY cr.ordre, cr.id""", (ev["id"],)))
        ev["items"] = _rows(c.execute(
            "SELECT task_id, libelle, score, commentaire FROM evaluation_items "
            "WHERE evaluation_id=? ORDER BY id", (ev["id"],)))
    return ev


def save_evaluation(user_id, evaluateur_id, annee, periode, type_, scores, items, commentaires,
                    score_final, submit) -> int:
    """scores : {criterion_id: (score, commentaire, poids)} ; items : [(task_id, libelle, score, commentaire)]"""
    statut = "soumise" if submit else "brouillon"
    with get_conn() as c:
        row = c.execute("SELECT id, statut FROM evaluations WHERE user_id=? AND annee=? AND periode=? "
                        "AND type=?", (user_id, annee, periode, type_)).fetchone()
        if row and row["statut"] == "soumise":
            raise ValueError("Cette évaluation est déjà soumise.")
        if row:
            eid = row["id"]
            c.execute("UPDATE evaluations SET evaluateur_id=?, commentaires=?, score_final=?, "
                      "statut=?, date=datetime('now') WHERE id=?",
                      (evaluateur_id, commentaires, score_final, statut, eid))
            c.execute("DELETE FROM evaluation_scores WHERE evaluation_id=?", (eid,))
            c.execute("DELETE FROM evaluation_items WHERE evaluation_id=?", (eid,))
        else:
            eid = c.execute(
                "INSERT INTO evaluations (user_id, evaluateur_id, annee, periode, type, commentaires, "
                "score_final, statut) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, evaluateur_id, annee, periode, type_, commentaires, score_final, statut)).lastrowid
        c.executemany(
            "INSERT INTO evaluation_scores (evaluation_id, criterion_id, score, commentaire, "
            "poids_applique) VALUES (?,?,?,?,?)",
            [(eid, cid, s, com, p) for cid, (s, com, p) in scores.items()])
        c.executemany(
            "INSERT INTO evaluation_items (evaluation_id, task_id, libelle, score, commentaire) "
            "VALUES (?,?,?,?,?)", [(eid, *it) for it in items])
    return eid


def reopen_evaluation(user_id: int, annee: int, periode: str, type_: str) -> None:
    with get_conn() as c:
        c.execute("UPDATE evaluations SET statut='brouillon' "
                  "WHERE user_id=? AND annee=? AND periode=? AND type=?", (user_id, annee, periode, type_))


def delete_evaluation(user_id: int, annee: int, periode: str, type_: str) -> int:
    """Supprime l'évaluation, ses notes et ses notes par élément (cascade)."""
    with get_conn() as c:
        return c.execute("DELETE FROM evaluations WHERE user_id=? AND annee=? AND periode=? AND type=?",
                         (user_id, annee, periode, type_)).rowcount


def list_evaluations(annee: int | None = None, user_id: int | None = None,
                     manager_id: int | None = None, periode: str | None = None) -> list[dict]:
    sql = ("SELECT e.id, e.user_id, u.nom_complet, e.annee, e.periode, e.type, e.score_final, e.statut, "
           "e.date, ev.nom_complet AS evaluateur "
           "FROM evaluations e JOIN users u ON u.id = e.user_id "
           "LEFT JOIN users ev ON ev.id = e.evaluateur_id WHERE 1=1")
    params: list = []
    for col, val in (("e.annee", annee), ("e.user_id", user_id), ("u.manager_id", manager_id),
                     ("e.periode", periode)):
        if val is not None:
            sql += f" AND {col}=?"
            params.append(val)
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY e.annee, e.periode", params))


def used_periods(annee: int, manager_id: int | None = None, user_id: int | None = None) -> set[str]:
    """Périodes pour lesquelles des évaluations existent (équipe ou collaborateur)."""
    return {e["periode"] for e in list_evaluations(annee=annee, user_id=user_id, manager_id=manager_id)}


def list_scores_year(annee: int, manager_id: int | None = None, periode: str | None = None) -> list[dict]:
    """Notes des évaluations soumises (export équipe), éventuellement d'une équipe / d'une période."""
    sql = """SELECT u.nom_complet AS collaborateur, e.periode, e.type, cr.nom AS critere,
                    es.poids_applique AS poids, es.score, es.commentaire
             FROM evaluation_scores es
             JOIN evaluations e ON e.id = es.evaluation_id
             JOIN users u ON u.id = e.user_id
             JOIN criteria cr ON cr.id = es.criterion_id
             WHERE e.annee=? AND e.statut='soumise'"""
    params: list = [annee]
    if manager_id is not None:
        sql += " AND u.manager_id=?"
        params.append(manager_id)
    if periode is not None:
        sql += " AND e.periode=?"
        params.append(periode)
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY u.nom_complet, e.periode, e.type, cr.ordre", params))


# ---------- Journal d'activité ----------
def add_log(user_id, username, role, action: str, details: str = "") -> None:
    with get_conn() as c:
        c.execute("INSERT INTO audit_log (user_id, username, role, action, details) VALUES (?,?,?,?,?)",
                  (user_id, username, role, action, details))


def list_logs(ts_from: str | None = None, ts_to: str | None = None, username: str | None = None,
              action: str | None = None, limit: int = 5000) -> list[dict]:
    sql = "SELECT id, ts, user_id, username, role, action, details FROM audit_log WHERE 1=1"
    params: list = []
    if ts_from:
        sql += " AND ts>=?"
        params.append(ts_from)
    if ts_to:
        sql += " AND ts<=?"
        params.append(ts_to)
    if username:
        sql += " AND username=?"
        params.append(username)
    if action:
        sql += " AND action=?"
        params.append(action)
    with get_conn() as c:
        return _rows(c.execute(sql + " ORDER BY id DESC LIMIT ?", params + [limit]))


def list_log_usernames() -> list[str]:
    with get_conn() as c:
        return [r[0] for r in c.execute(
            "SELECT DISTINCT username FROM audit_log WHERE username IS NOT NULL ORDER BY username")]


def last_logins() -> dict[int, str]:
    with get_conn() as c:
        return {r["user_id"]: r["last"] for r in c.execute(
            "SELECT user_id, MAX(ts) AS last FROM audit_log "
            "WHERE action='LOGIN' AND user_id IS NOT NULL GROUP BY user_id")}
