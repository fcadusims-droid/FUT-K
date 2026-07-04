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

-- Passing network edges (Section 12, Layer 5)
CREATE TABLE IF NOT EXISTS interactions (
    scope           TEXT,   -- an aggregation label, e.g. "Barcelona 2015/2016"
    from_player     TEXT,
    to_player       TEXT,
    passes          INTEGER,
    chances_created INTEGER
);

-- Estimated on/off influence of each player on their team's goal rate (Layer 4)
CREATE TABLE IF NOT EXISTS influence (
    player_id   TEXT,
    name        TEXT,
    team        TEXT,
    lambda_on   REAL,
    lambda_off  REAL,
    delta       REAL,
    on_minutes  REAL,
    off_minutes REAL
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
    archetype        TEXT,
    matches          INTEGER,   -- provenance: real matches backing this profile
    sources          TEXT,      -- provenance: contributing datasets (comma-joined)
    confidence       REAL       -- evidence-based reliability in [0, 1)
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
    """Persist one player DNA profile (Section 12), with its provenance."""
    conn.execute(
        "INSERT OR REPLACE INTO player_profiles "
        "(player_id, name, team, position, actions, passes, shots, goals, assists, "
        " pass_accuracy, progressive_pass, key_pass_rate, shot_share, turnover_rate, "
        " archetype, matches, sources, confidence) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            profile["player_id"], profile["name"], profile["team"], profile["position"],
            profile["actions"], profile["passes"], profile["shots"], profile["goals"],
            profile["assists"], profile["pass_accuracy"], profile["progressive_pass_share"],
            profile["key_pass_rate"], profile["shot_share"], profile["turnover_rate"],
            profile["archetype"], profile.get("matches"),
            ",".join(profile.get("sources") or ()), profile.get("confidence"),
        ),
    )


def insert_player_profiles(conn, profiles):
    for profile in profiles:
        insert_player_profile(conn, profile)
    conn.commit()


def insert_influence(conn, rows):
    """Persist on/off influence rows (Layer 4)."""
    conn.executemany(
        "INSERT INTO influence (player_id, name, team, lambda_on, lambda_off, delta, "
        "on_minutes, off_minutes) VALUES (?,?,?,?,?,?,?,?)",
        [
            (r["player_id"], r["name"], r["team"], r["lambda_on"], r["lambda_off"],
             r["delta"], r["on_minutes"], r["off_minutes"])
            for r in rows
        ],
    )
    conn.commit()


def insert_interactions(conn, scope, graph, names=None):
    """Persist a passing-network graph (``{(from,to): {weight, chances}}``)."""
    names = names or {}
    conn.executemany(
        "INSERT INTO interactions (scope, from_player, to_player, passes, "
        "chances_created) VALUES (?,?,?,?,?)",
        [
            (scope, names.get(a, a), names.get(b, b), d["weight"], d["chances"])
            for (a, b), d in graph.items()
        ],
    )
    conn.commit()
