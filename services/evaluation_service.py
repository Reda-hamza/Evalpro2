"""Logique métier : enregistrement, visibilité, périodes, comparaisons, synthèses."""
import pandas as pd

from config import PERIODES_DE, PERIODES_ORDRE, current_year, periode_courante, periode_label
from database import repository as repo
from services import audit_service as audit
from services.management_service import PermissionDenied, check_manage
from services.scoring_service import mention, weighted_score


# ------------------------------------------------------------------ périodes
def periodicity_of(user_id: int) -> str:
    """Périodicité applicable : celle du manager (pour un collaborateur) ou la sienne."""
    user = repo.get_user(user_id)
    if not user:
        return "annuelle"
    if user["role"] == "collaborateur" and user["manager_id"]:
        boss = repo.get_user(user["manager_id"])
        return boss["periodicite"] if boss else "annuelle"
    return user.get("periodicite") or "annuelle"


def period_options(periodicite: str | None, annee: int, manager_id: int | None = None,
                   user_id: int | None = None) -> list[str]:
    """Périodes proposées : celles de la périodicité + celles qui contiennent déjà des évaluations.
    periodicite=None -> toutes les périodes (administrateur)."""
    base = set(PERIODES_DE[periodicite]) if periodicite else set(PERIODES_ORDRE)
    used = repo.used_periods(annee, manager_id=manager_id, user_id=user_id)
    return [p for p in PERIODES_ORDRE if p in base | used]


def default_period_index(options: list[str], periodicite: str | None, annee: int) -> int:
    if periodicite and annee == current_year():
        wanted = periode_courante(periodicite)
    else:
        wanted = options[-1] if periodicite else "A"
    return options.index(wanted) if wanted in options else 0


# ------------------------------------------------------------------ enregistrement
def save_evaluation(actor, target_id, annee, periode, type_, values, items, commentaires, submit) -> float:
    """values : {criterion_id: (score, commentaire, poids)} ; items : [(task_id, libelle, score, com)].
    Auto-évaluation : le collaborateur lui-même. Évaluation manager : le manager de l'équipe."""
    if type_ == "auto":
        if actor["role"] != "collaborateur" or actor["id"] != target_id:
            raise PermissionDenied("Action non autorisée.")
    else:
        if actor["role"] != "manager":
            raise PermissionDenied("Seul le manager de l'équipe peut évaluer.")
        check_manage(actor, target_id)
    score = weighted_score([(s, p) for s, _, p in values.values()])
    repo.save_evaluation(target_id, actor["id"], annee, periode, type_, values, items, commentaires,
                         score, submit)
    target = repo.get_user(target_id)
    audit.log("EVAL_SUBMITTED" if submit else "EVAL_DRAFT",
              f"{type_} — {periode_label(periode, annee)} — « {target['nom_complet']} » (score {score:.2f})",
              actor)
    return score


# ------------------------------------------------------------------ visibilité
def manager_eval_visible(user_id: int, annee: int, periode: str) -> bool:
    """Le collaborateur peut-il voir l'évaluation du manager ? (selon le paramétrage)."""
    mgr = repo.get_evaluation(user_id, annee, periode, "manager")
    if not mgr or mgr["statut"] != "soumise":
        return False
    if repo.get_setting("visibility_mode", "after_both") == "immediate":
        return True
    auto = repo.get_evaluation(user_id, annee, periode, "auto")
    return bool(auto and auto["statut"] == "soumise")


def get_bundle(viewer: dict, target_id: int, annee: int, periode: str) -> dict:
    """Évaluations soumises visibles par `viewer` pour `target_id` sur la période."""
    auto = repo.get_evaluation(target_id, annee, periode, "auto")
    mgr = repo.get_evaluation(target_id, annee, periode, "manager")
    if auto and auto["statut"] != "soumise":
        auto = None
    if mgr and (mgr["statut"] != "soumise" or (viewer["role"] == "collaborateur"
                                              and not manager_eval_visible(target_id, annee, periode))):
        mgr = None
    return {"user": repo.get_user(target_id), "annee": annee, "periode": periode, "auto": auto,
            "manager": mgr, "comparison": build_comparison(auto, mgr),
            "items_comparison": build_items_comparison(auto, mgr)}


# ------------------------------------------------------------------ tableaux
def build_comparison(auto: dict | None, manager: dict | None) -> pd.DataFrame:
    rows: dict[int, dict] = {}
    for ev, key in ((auto, "Auto"), (manager, "Manager")):
        if not ev:
            continue
        for s in ev["scores"]:
            r = rows.setdefault(s["criterion_id"], {
                "Critère": s["nom"], "Poids (%)": s["poids"], "ordre": s["ordre"],
                "Auto": None, "Manager": None})
            r[key] = s["score"]
    cols = ["Critère", "Poids (%)", "Auto", "Manager", "Écart"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(sorted(rows.values(), key=lambda r: r["ordre"])).drop(columns="ordre")
    df["Auto"] = pd.to_numeric(df["Auto"], errors="coerce")
    df["Manager"] = pd.to_numeric(df["Manager"], errors="coerce")
    df["Écart"] = df["Manager"] - df["Auto"]
    return df[cols]


def build_items_comparison(auto: dict | None, manager: dict | None) -> pd.DataFrame:
    """Notes par élément à évaluer (propres au collaborateur), auto vs manager."""
    rows: dict[str, dict] = {}
    for ev, key in ((auto, "Auto"), (manager, "Manager")):
        if not ev:
            continue
        for it in ev["items"]:
            r = rows.setdefault(it["libelle"], {"Élément": it["libelle"], "Auto": None, "Manager": None})
            r[key] = it["score"]
    cols = ["Élément", "Auto", "Manager", "Écart"]
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(list(rows.values()))
    df["Auto"] = pd.to_numeric(df["Auto"], errors="coerce")
    df["Manager"] = pd.to_numeric(df["Manager"], errors="coerce")
    df["Écart"] = df["Manager"] - df["Auto"]
    return df[cols]


def history(viewer: dict, target_id: int) -> pd.DataFrame:
    """Score final par période (auto / manager), en respectant la visibilité."""
    by_key: dict[tuple, dict] = {}
    for ev in repo.list_evaluations(user_id=target_id):
        if ev["statut"] != "soumise":
            continue
        key = (ev["annee"], PERIODES_ORDRE.index(ev["periode"]))
        row = by_key.setdefault(key, {"Période": periode_label(ev["periode"], ev["annee"]),
                                      "Auto": None, "Manager": None})
        if ev["type"] == "auto":
            row["Auto"] = ev["score_final"]
        elif viewer["role"] != "collaborateur" or manager_eval_visible(target_id, ev["annee"], ev["periode"]):
            row["Manager"] = ev["score_final"]
    if not by_key:
        return pd.DataFrame(columns=["Période", "Auto", "Manager"])
    df = pd.DataFrame([by_key[k] for k in sorted(by_key)])
    df["Auto"] = pd.to_numeric(df["Auto"], errors="coerce")
    df["Manager"] = pd.to_numeric(df["Manager"], errors="coerce")
    return df


def team_summary(annee: int, periode: str, manager_id: int | None = None) -> pd.DataFrame:
    """Synthèse par collaborateur actif pour une période ; manager_id=None -> toutes les équipes."""
    evals = repo.list_evaluations(annee=annee, manager_id=manager_id, periode=periode)
    idx = {(e["user_id"], e["type"]): e for e in evals}
    rows = []
    for u in repo.list_collaborateurs(actif_only=True, manager_id=manager_id):
        a, m = idx.get((u["id"], "auto")), idx.get((u["id"], "manager"))
        sa = a["score_final"] if a and a["statut"] == "soumise" else None
        sm = m["score_final"] if m and m["statut"] == "soumise" else None
        rows.append({
            "Collaborateur": u["nom_complet"],
            "Statut auto": a["statut"] if a else None,
            "Statut manager": m["statut"] if m else None,
            "Auto": sa, "Manager": sm,
            "Écart": (sm - sa) if sa is not None and sm is not None else None,
            "Mention": mention(sm if sm is not None else float("nan")),
        })
    df = pd.DataFrame(rows, columns=["Collaborateur", "Statut auto", "Statut manager",
                                     "Auto", "Manager", "Écart", "Mention"])
    for col in ("Auto", "Manager", "Écart"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df
