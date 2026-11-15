PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash        TEXT NOT NULL,
    role                 TEXT NOT NULL CHECK (role IN ('admin','manager','collaborateur')),
    nom_complet          TEXT NOT NULL,
    actif                INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 1,
    manager_id           INTEGER REFERENCES users(id) ON DELETE SET NULL,
    periodicite          TEXT NOT NULL DEFAULT 'annuelle'
                         CHECK (periodicite IN ('annuelle','semestrielle','trimestrielle')),
    created_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS criteria (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nom         TEXT NOT NULL UNIQUE,
    description TEXT,
    poids       REAL NOT NULL CHECK (poids > 0 AND poids <= 100),
    ordre       INTEGER NOT NULL DEFAULT 0,
    actif       INTEGER NOT NULL DEFAULT 1,
    mode        TEXT NOT NULL DEFAULT 'manuel' CHECK (mode IN ('manuel','elements'))
);

CREATE TABLE IF NOT EXISTS tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    statut      TEXT NOT NULL DEFAULT 'a_faire'
                CHECK (statut IN ('a_faire','en_cours','terminee','annulee')),
    annee       INTEGER NOT NULL,
    actif       INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS evaluations (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    evaluateur_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    annee         INTEGER NOT NULL,
    periode       TEXT NOT NULL DEFAULT 'A' CHECK (periode IN ('A','S1','S2','T1','T2','T3','T4')),
    type          TEXT NOT NULL CHECK (type IN ('auto','manager')),
    commentaires  TEXT,
    score_final   REAL,
    statut        TEXT NOT NULL DEFAULT 'brouillon' CHECK (statut IN ('brouillon','soumise')),
    date          TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, annee, periode, type)
);

CREATE TABLE IF NOT EXISTS evaluation_scores (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id  INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    criterion_id   INTEGER NOT NULL REFERENCES criteria(id),
    score          REAL NOT NULL CHECK (score BETWEEN 1 AND 5),
    commentaire    TEXT,
    poids_applique REAL NOT NULL,
    UNIQUE (evaluation_id, criterion_id)
);

-- Notes par élément à évaluer (propres à chaque collaborateur) ; libellé copié pour l'historique
CREATE TABLE IF NOT EXISTS evaluation_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    task_id       INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    libelle       TEXT NOT NULL,
    score         INTEGER NOT NULL CHECK (score BETWEEN 1 AND 5),
    commentaire   TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Journal d'activité : pas de clé étrangère, pour survivre à la suppression des comptes
CREATE TABLE IF NOT EXISTS audit_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL DEFAULT (datetime('now')),   -- UTC
    user_id  INTEGER,
    username TEXT,
    role     TEXT,
    action   TEXT NOT NULL,
    details  TEXT
);

CREATE INDEX IF NOT EXISTS idx_eval_user_annee ON evaluations(user_id, annee, periode);
CREATE INDEX IF NOT EXISTS idx_items_eval ON evaluation_items(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_users_manager ON users(manager_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
