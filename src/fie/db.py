"""Database (Section 6) — a SQLite subset for Phase 1.

Beyond raw events we keep the predictions made and what actually happened, so the
model can be validated on real data (Section 20). Standard-library only
(``sqlite3``).
"""

from __future__ import annotations

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id                TEXT PRIMARY KEY,
    competition       TEXT,
    season            TEXT,
    home_team         TEXT,
    away_team         TEXT,
    status            TEXT,
    home_goals_final  INTEGER,
    away_goals_final  INTEGER
);

CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY,
    match_id   TEXT REFERENCES matches(id),
    minute     REAL,
    team       TEXT,
    type       TEXT,
    player_id  TEXT,
    x          REAL,
    y          REAL,
    xg         REAL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY,
    match_id      TEXT REFERENCES matches(id),
    minute        REAL,
    momentum      REAL,
    regime        TEXT,
    lambda_home   REAL,
    lambda_away   REAL
);

CREATE TABLE IF NOT EXISTS predictions (
    id           INTEGER PRIMARY KEY,
    match_id     TEXT REFERENCES matches(id),
    minute       REAL,
    target       TEXT,
    probability  REAL
);

CREATE TABLE IF NOT EXISTS outcomes (
    prediction_id INTEGER REFERENCES predictions(id),
    happened      INTEGER
);

-- Consolidated "DNA" of each player (Section 12)
CREATE TABLE IF NOT EXISTS player_profiles (
    player_id        TEXT PRIMARY KEY,
    name             TEXT,
    team             TEXT,
    position         TEXT,
    actions          INTEGER,
    passes           INTEGER,
    shots            INTEGER,
    goals            INTEGER,
    assists          INTEGER,
    pass_accuracy    REAL,
    progressive_pass REAL,
    key_pass_rate    REAL,
    shot_share       REAL,
    turnover_rate    REAL,
    archetype        TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_match ON events(match_id);
CREATE INDEX IF NOT EXISTS idx_pred_match ON predictions(match_id);
"""


def connect(path=":memory:"):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn):
    conn.executescript(SCHEMA)
    conn.commit()


def insert_match(conn, match, competition=None, season=None):
    conn.execute(
        "INSERT OR REPLACE INTO matches "
        "(id, competition, season, home_team, away_team, status, "
        " home_goals_final, away_goals_final) VALUES (?,?,?,?,?,?,?,?)",
        (
            match["match_id"], competition, season, match.get("home_team"),
            match.get("away_team"), "finished", match.get("home_score"),
            match.get("away_score"),
        ),
    )
    conn.commit()


def insert_events(conn, match_id, events):
    conn.executemany(
        "INSERT INTO events (match_id, minute, team, type, player_id, x, y, xg) "
        "VALUES (?,?,?,?,?,?,?,?)",
        [(match_id, e.minute, e.team, e.type, e.player_id, e.x, e.y, e.xg) for e in events],
    )
    conn.commit()


def insert_snapshot(conn, match_id, minute, momentum, regime, lam_home, lam_away):
    conn.execute(
        "INSERT INTO snapshots (match_id, minute, momentum, regime, lambda_home, lambda_away) "
        "VALUES (?,?,?,?,?,?)",
        (match_id, minute, momentum, regime, lam_home, lam_away),
    )


def insert_prediction(conn, record, happened):
    cur = conn.execute(
        "INSERT INTO predictions (match_id, minute, target, probability) VALUES (?,?,?,?)",
        (record["match_id"], record["minute"], record["target"], record["prob"]),
    )
    conn.execute(
        "INSERT INTO outcomes (prediction_id, happened) VALUES (?, ?)",
        (cur.lastrowid, happened),
    )


def prediction_pairs(conn):
    """Read back every (probability, happened) pair for calibration."""
    rows = conn.execute(
        "SELECT p.probability, o.happened FROM predictions p "
        "JOIN outcomes o ON o.prediction_id = p.id"
    ).fetchall()
    return [(float(p), int(h)) for p, h in rows]


def insert_player_profile(conn, profile):
    """Persist one player DNA profile (Section 12)."""
    conn.execute(
        "INSERT OR REPLACE INTO player_profiles "
        "(player_id, name, team, position, actions, passes, shots, goals, assists, "
        " pass_accuracy, progressive_pass, key_pass_rate, shot_share, turnover_rate, "
        " archetype) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            profile["player_id"], profile["name"], profile["team"], profile["position"],
            profile["actions"], profile["passes"], profile["shots"], profile["goals"],
            profile["assists"], profile["pass_accuracy"], profile["progressive_pass_share"],
            profile["key_pass_rate"], profile["shot_share"], profile["turnover_rate"],
            profile["archetype"],
        ),
    )


def insert_player_profiles(conn, profiles):
    for profile in profiles:
        insert_player_profile(conn, profile)
    conn.commit()
