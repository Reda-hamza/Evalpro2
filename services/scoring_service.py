"""Calculs purs (sans accès base ni Streamlit)."""


def _is_nan(x) -> bool:
    return x is None or x != x


def weighted_score(pairs: list[tuple[float, float]]) -> float:
    """pairs = [(score, poids), ...] -> score pondéré sur 5."""
    total = sum(p for _, p in pairs)
    if not total:
        return 0.0
    return round(sum(s * p for s, p in pairs) / total, 2)


def to_percent(score) -> float | None:
    return None if _is_nan(score) else round(score / 5 * 100, 1)


def mention(score) -> str:
    if _is_nan(score):
        return "—"
    if score >= 4.5:
        return "Excellent"
    if score >= 3.5:
        return "Très bien"
    if score >= 2.5:
        return "Satisfaisant"
    if score >= 1.5:
        return "À améliorer"
    return "Insuffisant"
