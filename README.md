# Évaluation annuelle — application Streamlit (multi-managers)

## Installation
```bash
pip install -r requirements.txt   # Streamlit >= 1.40 (testé avec 1.44 et 1.67)
streamlit run app.py
```

## Première connexion
- Identifiant : `admin`  /  mot de passe : `admin123` (changement exigé immédiatement).
- L'administrateur crée les managers ; chaque manager crée ses propres collaborateurs.
- Mot de passe admin oublié : `python reset_password.py` sur le serveur.

## Rôles
| Rôle | Droits |
|---|---|
| Administrateur | Tous les comptes (créer, modifier, désactiver, réinitialiser, supprimer), toutes les évaluations et tâches, résultats de toutes les équipes, critères & paramètres, journal d'activité |
| Manager | Uniquement son équipe : comptes, tâches, évaluations (évaluer, rouvrir, supprimer), résultats et exports |
| Collaborateur | Son auto-évaluation, ses tâches (statut), ses résultats |

## Éléments à évaluer et périodicité
- Le manager crée, pour **chaque collaborateur**, ses propres éléments à évaluer (page « Mon équipe » > « Éléments à évaluer »). Chaque élément peut être **désactivé** (il n'est plus évalué, l'historique est conservé) ou **supprimé**.
- Dans l'évaluation, chaque élément actif est noté de 1 à 5 ; la note du critère « Réalisation des tâches » est la **moyenne** de ces notes (sans élément : note saisie directement). L'administrateur peut changer le mode d'un critère dans « Critères & paramètres ».
- Le manager choisit la fréquence des évaluations de son équipe : annuelle, semestrielle ou trimestrielle (« Mon équipe » > « Évaluations »). Une évaluation existe par collaborateur, par période et par type (auto / manager).

## Journal d'activité
Connexions (réussies et échouées), déconnexions, changements de mot de passe, créations/modifications/suppressions de comptes, évaluations, tâches, critères, paramètres et exports. Dates stockées en UTC, affichées en heure d'Alger (`TIMEZONE` dans `config.py`). Lecture seule dans l'interface.

## Mise à jour d'une ancienne base
Automatique au premier lancement : les évaluations existantes deviennent des évaluations annuelles, les collaborateurs existants sont rattachés au premier manager, un compte `admin` est créé. Sauvegardez `data/evaluation.db` avant.

## Structure
- `app.py` : connexion + navigation selon le rôle
- `views/` : pages ; `services/` : droits, logique métier, exports, journal ; `database/` : schéma, dépôt, migration
