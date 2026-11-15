"""Configuration globale de l'application."""
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "evaluation.db"

APP_TITLE = "Évaluation annuelle"
MIN_PASSWORD_LENGTH = 6

SCORE_LABELS = {1: "Insuffisant", 2: "À améliorer", 3: "Satisfaisant", 4: "Très bien", 5: "Excellent"}
STATUTS_TACHES = {"a_faire": "À faire", "en_cours": "En cours", "terminee": "Terminée", "annulee": "Annulée"}
STATUTS_EVAL = {"brouillon": "📝 Brouillon", "soumise": "✅ Soumise"}
VISIBILITY_MODES = {
    "after_both": "Après soumission des deux évaluations (auto + manager)",
    "immediate": "Immédiatement après soumission par le manager",
}

TIMEZONE = "Africa/Algiers"   # affichage du journal (les dates sont stockées en UTC)
ROLE_LABELS = {"admin": "Administrateur", "manager": "Manager", "collaborateur": "Collaborateur"}

# Compte administrateur créé au premier lancement (mot de passe à changer à la 1re connexion)
DEFAULT_ADMIN = {"username": "admin", "password": "admin123", "nom_complet": "Administrateur"}

# (nom, description, poids, ordre, mode) — mode « elements » : note calculée à partir des
# éléments à évaluer propres à chaque collaborateur (moyenne) ; « manuel » : note saisie directement
DEFAULT_CRITERIA = [
    ("Réalisation des tâches", "Atteinte des tâches assignées", 40, 1, "elements"),
    ("Innovation", "Propositions et initiatives hors tâches", 20, 2, "manuel"),
    ("Présence / Ponctualité", "Assiduité et respect des horaires", 20, 3, "manuel"),
    ("Qualité du service client", "Qualité des échanges avec les clients", 10, 4, "manuel"),
    ("Esprit d'équipe", "Collaboration et entraide", 10, 5, "manuel"),
]
CRITERION_MODES = {"manuel": "Note saisie", "elements": "Moyenne des éléments"}

# Périodicité des évaluations (réglée par équipe)
PERIODICITES = {"annuelle": "Annuelle", "semestrielle": "Semestrielle", "trimestrielle": "Trimestrielle"}
PERIODES_DE = {"annuelle": ["A"], "semestrielle": ["S1", "S2"], "trimestrielle": ["T1", "T2", "T3", "T4"]}
PERIODES_ORDRE = ["A", "S1", "S2", "T1", "T2", "T3", "T4"]
PERIODE_LABELS = {"A": "Année complète", "S1": "1er semestre", "S2": "2e semestre",
                  "T1": "1er trimestre", "T2": "2e trimestre", "T3": "3e trimestre", "T4": "4e trimestre"}


def periode_label(code: str, annee: int) -> str:
    return f"{PERIODE_LABELS[code]} {annee}"


def periode_courante(periodicite: str, today: date | None = None) -> str:
    month = (today or date.today()).month
    if periodicite == "trimestrielle":
        return f"T{(month - 1) // 3 + 1}"
    if periodicite == "semestrielle":
        return "S1" if month <= 6 else "S2"
    return "A"


def current_year() -> int:
    return date.today().year


def year_options(n: int = 6) -> list[int]:
    y = current_year()
    return list(range(y, y - n, -1))
