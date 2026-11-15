"""Journal d'activité : écriture et consultation (dates stockées en UTC, affichées en heure locale)."""
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from config import TIMEZONE
from database import repository as repo
from services.auth_service import current_user

ACTION_LABELS = {
    "LOGIN": "Connexion", "LOGIN_FAILED": "Échec de connexion", "LOGOUT": "Déconnexion",
    "PASSWORD_CHANGED": "Mot de passe modifié", "PASSWORD_RESET": "Mot de passe réinitialisé",
    "USER_CREATED": "Compte créé", "USER_UPDATED": "Compte modifié", "USER_DELETED": "Compte supprimé",
    "EVAL_DRAFT": "Brouillon d'évaluation", "EVAL_SUBMITTED": "Évaluation soumise",
    "EVAL_REOPENED": "Évaluation rouverte", "EVAL_DELETED": "Évaluation supprimée",
    "TASK_ADDED": "Tâche ajoutée", "TASK_STATUS": "Statut de tâche modifié",
    "TASK_DELETED": "Tâche supprimée", "TASKS_DELETED": "Tâches supprimées (année)",
    "TASK_ACTIVE": "Élément activé / désactivé", "PERIODICITY_CHANGED": "Périodicité modifiée",
    "CRITERIA_UPDATED": "Critères modifiés", "CRITERION_ADDED": "Critère ajouté",
    "SETTING_CHANGED": "Paramètre modifié", "EXPORT": "Export de données",
}
COLUMNS = ["Date / heure", "Utilisateur", "Rôle", "Action", "Détails", "code"]


def log(action: str, details: str = "", actor: dict | None = None) -> None:
    """Ajoute une ligne au journal. N'interrompt jamais l'application en cas d'erreur."""
    try:
        actor = actor or current_user() or {}
        repo.add_log(actor.get("id"), actor.get("username"), actor.get("role"), action, details)
    except Exception:
        pass


def fmt_local(ts_utc: str | None) -> str:
    if not ts_utc:
        return "—"
    dt = datetime.strptime(ts_utc, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo(TIMEZONE)).strftime("%d/%m/%Y %H:%M")


def _to_utc(d, end_of_day: bool) -> str:
    local = datetime.combine(d, time.max if end_of_day else time.min, ZoneInfo(TIMEZONE))
    return local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def query_logs(date_from=None, date_to=None, username=None, action=None, limit=5000) -> pd.DataFrame:
    rows = repo.list_logs(_to_utc(date_from, False) if date_from else None,
                          _to_utc(date_to, True) if date_to else None, username, action, limit)
    if not rows:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(rows)
    df["Date / heure"] = (pd.to_datetime(df["ts"], utc=True).dt.tz_convert(TIMEZONE)
                          .dt.strftime("%d/%m/%Y %H:%M:%S"))
    df["Action"] = df["action"].map(lambda a: ACTION_LABELS.get(a, a))
    df["Rôle"] = df["role"].fillna("—")
    df["Utilisateur"] = df["username"].fillna("—")
    df["Détails"] = df["details"].fillna("")
    df["code"] = df["action"]
    return df[COLUMNS]
