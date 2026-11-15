"""Opérations de gestion avec contrôle des droits et journalisation.

- admin   : tous les comptes, toutes les données
- manager : uniquement les collaborateurs de sa propre équipe
- collaborateur : uniquement ses propres tâches (statut)
"""
from config import MIN_PASSWORD_LENGTH, PERIODICITES, periode_label
from database import repository as repo
from services import audit_service as audit
from services.auth_service import hash_password


class PermissionDenied(Exception):
    """Action non autorisée pour ce rôle ou hors de son périmètre."""


def check_manage(actor: dict, target_id: int) -> dict:
    """Vérifie que `actor` peut gérer le compte `target_id` ; retourne ce compte."""
    target = repo.get_user(target_id)
    if not target:
        raise ValueError("Utilisateur introuvable.")
    if actor["role"] == "admin":
        return target
    if (actor["role"] == "manager" and target["role"] == "collaborateur"
            and target["manager_id"] == actor["id"]):
        return target
    raise PermissionDenied("Action non autorisée : ce compte n'appartient pas à votre équipe.")


def _check_password(pwd: str) -> None:
    if len(pwd) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Mot de passe : {MIN_PASSWORD_LENGTH} caractères minimum.")


# ---------------- Comptes ----------------
def create_user(actor, username, password, role, nom_complet, manager_id=None,
                periodicite="annuelle") -> int:
    if actor["role"] == "manager":
        role, manager_id = "collaborateur", actor["id"]
    elif actor["role"] != "admin":
        raise PermissionDenied("Action non autorisée.")
    if not username.strip() or not nom_complet.strip():
        raise ValueError("Nom complet et identifiant obligatoires.")
    _check_password(password)
    if role == "collaborateur":
        boss = repo.get_user(manager_id) if manager_id else None
        if not boss or boss["role"] != "manager":
            raise ValueError("Un collaborateur doit être rattaché à un manager.")
    else:
        manager_id = None
    if periodicite not in PERIODICITES:
        raise ValueError("Périodicité invalide.")
    uid = repo.create_user(username.strip(), hash_password(password), role, nom_complet.strip(),
                           1, manager_id, periodicite)
    audit.log("USER_CREATED", f"{role} « {username.strip()} » ({nom_complet.strip()})", actor)
    return uid


def update_user(actor, user_id, nom_complet, actif, manager_id=None) -> None:
    target = check_manage(actor, user_id)
    if not nom_complet.strip():
        raise ValueError("Le nom ne peut pas être vide.")
    if not actif:
        if actor["id"] == user_id:
            raise ValueError("Vous ne pouvez pas désactiver votre propre compte.")
        if target["role"] == "admin" and repo.count_admins() <= 1:
            raise ValueError("Impossible de désactiver le dernier administrateur actif.")
    new_manager = target["manager_id"]
    if actor["role"] == "admin" and target["role"] == "collaborateur":
        boss = repo.get_user(manager_id) if manager_id else None
        if not boss or boss["role"] != "manager":
            raise ValueError("Un collaborateur doit être rattaché à un manager.")
        new_manager = manager_id
    repo.update_user(user_id, nom_complet.strip(), actif, new_manager)
    audit.log("USER_UPDATED", f"{target['username']} : nom « {nom_complet.strip()} », "
                              f"{'actif' if actif else 'désactivé'}", actor)


def set_periodicity(actor, manager_id, periodicite) -> None:
    """Fréquence des évaluations d'une équipe : le manager (la sienne) ou l'administrateur."""
    boss = repo.get_user(manager_id)
    if not boss or boss["role"] != "manager":
        raise ValueError("Manager introuvable.")
    if actor["role"] != "admin" and actor["id"] != manager_id:
        raise PermissionDenied("Action non autorisée.")
    if periodicite not in PERIODICITES:
        raise ValueError("Périodicité invalide.")
    repo.set_periodicity(manager_id, periodicite)
    audit.log("PERIODICITY_CHANGED", f"équipe de « {boss['username']} » : {PERIODICITES[periodicite]}", actor)


def reset_password(actor, user_id, new_password) -> None:
    target = check_manage(actor, user_id)
    if actor["id"] == user_id:
        raise ValueError("Pour votre propre mot de passe, utilisez « Mon compte ».")
    _check_password(new_password)
    repo.set_password(user_id, hash_password(new_password), 1)
    audit.log("PASSWORD_RESET", f"compte « {target['username']} »", actor)


def delete_user(actor, user_id, reassign_to=None, delete_team=False) -> None:
    target = check_manage(actor, user_id)
    if actor["id"] == user_id:
        raise ValueError("Vous ne pouvez pas supprimer votre propre compte.")
    if target["role"] == "admin" and repo.count_admins(actif_only=False) <= 1:
        raise ValueError("Impossible de supprimer le dernier administrateur.")
    if target["role"] == "manager":
        team = repo.list_collaborateurs(actif_only=False, manager_id=user_id)
        if team:
            if delete_team:
                for m in team:
                    repo.delete_user(m["id"])
                    audit.log("USER_DELETED", f"collaborateur « {m['username']} » (suppression de l'équipe "
                                              f"de « {target['username']} »)", actor)
            elif reassign_to:
                boss = repo.get_user(reassign_to)
                if not boss or boss["role"] != "manager" or boss["id"] == user_id:
                    raise ValueError("Manager de réaffectation invalide.")
                repo.reassign_team(user_id, reassign_to)
            else:
                raise ValueError("Ce manager a une équipe : réaffectez-la ou choisissez de la supprimer.")
    repo.delete_user(user_id)
    audit.log("USER_DELETED", f"{target['role']} « {target['username']} » ({target['nom_complet']})", actor)


# ---------------- Évaluations ----------------
def delete_evaluation(actor, user_id, annee, periode, type_) -> None:
    target = check_manage(actor, user_id)
    if repo.delete_evaluation(user_id, annee, periode, type_):
        audit.log("EVAL_DELETED", f"{type_} — {periode_label(periode, annee)} — « {target['nom_complet']} »", actor)


def reopen_evaluation(actor, user_id, annee, periode, type_) -> None:
    target = check_manage(actor, user_id)
    repo.reopen_evaluation(user_id, annee, periode, type_)
    audit.log("EVAL_REOPENED", f"{type_} — {periode_label(periode, annee)} — « {target['nom_complet']} »", actor)


# ---------------- Tâches ----------------
def add_task(actor, user_id, description, statut, annee) -> None:
    target = check_manage(actor, user_id)
    if not description.strip():
        raise ValueError("La description est obligatoire.")
    repo.add_task(user_id, description.strip(), statut, annee)
    audit.log("TASK_ADDED", f"{target['nom_complet']} ({annee}) : {description.strip()}", actor)


def _task_target(actor, task_id, allow_owner=False) -> dict:
    task = repo.get_task(task_id)
    if not task:
        raise ValueError("Tâche introuvable.")
    if allow_owner and actor["id"] == task["user_id"]:
        return task
    check_manage(actor, task["user_id"])
    return task


def set_task_active(actor, task_id, actif) -> None:
    """Active / désactive un élément à évaluer (hors des prochaines évaluations, historique conservé)."""
    task = _task_target(actor, task_id)
    repo.set_task_active(task_id, actif)
    audit.log("TASK_ACTIVE", f"« {task['description']} » : {'activé' if actif else 'désactivé'}", actor)


def update_task_status(actor, task_id, statut) -> None:
    task = _task_target(actor, task_id, allow_owner=True)
    repo.update_task_status(task_id, statut)
    audit.log("TASK_STATUS", f"« {task['description']} » → {statut}", actor)


def delete_task(actor, task_id) -> None:
    task = _task_target(actor, task_id)
    repo.delete_task(task_id)
    audit.log("TASK_DELETED", f"« {task['description']} » ({task['annee']})", actor)


def delete_tasks_year(actor, user_id, annee) -> int:
    target = check_manage(actor, user_id)
    n = repo.delete_tasks(user_id, annee)
    if n:
        audit.log("TASKS_DELETED", f"{n} tâche(s) {annee} de « {target['nom_complet']} »", actor)
    return n
