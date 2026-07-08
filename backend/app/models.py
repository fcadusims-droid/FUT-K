"""Production persistence schema (Section 6), portable SQLite <-> Postgres.

Mirrors the tables ``fie.db`` already validates against real StatsBomb data
(matches, events, snapshots, predictions/outcomes, player_profiles,
interactions, influence) as proper SQLAlchemy ORM models with foreign keys and
indexes, so the API layer (Phase B) has a real relational store to query instead
of one throwaway SQLite file per script.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    competition: Mapped[str | None] = mapped_column(String)
    season: Mapped[str | None] = mapped_column(String)
    match_date: Mapped[str | None] = mapped_column(String)
    home_team: Mapped[str | None] = mapped_column(String)
    away_team: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    home_goals_final: Mapped[int | None] = mapped_column(Integer)
    events_hash: Mapped[str | None] = mapped_column(String)  # data provenance (level 18)
    away_goals_final: Mapped[int | None] = mapped_column(Integer)

    events: Mapped[list["MatchEvent"]] = relationship(back_populates="match")
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="match")
    predictions: Mapped[list["Prediction"]] = relationship(back_populates="match")


class MatchEvent(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_match_minute", "match_id", "minute"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    minute: Mapped[float] = mapped_column(Float)
    team: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    player_id: Mapped[str | None] = mapped_column(String)
    target_id: Mapped[str | None] = mapped_column(String)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    xg: Mapped[float | None] = mapped_column(Float)

    match: Mapped[Match] = relationship(back_populates="events")


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (Index("ix_snapshots_match_minute", "match_id", "minute"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    minute: Mapped[float] = mapped_column(Float)
    momentum: Mapped[float | None] = mapped_column(Float)
    regime: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)
    change_score: Mapped[float | None] = mapped_column(Float)
    lambda_home: Mapped[float | None] = mapped_column(Float)
    lambda_away: Mapped[float | None] = mapped_column(Float)

    match: Mapped[Match] = relationship(back_populates="snapshots")


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (Index("ix_predictions_match_minute", "match_id", "minute"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"))
    minute: Mapped[float] = mapped_column(Float)
    target: Mapped[str] = mapped_column(String)
    probability: Mapped[float] = mapped_column(Float)

    match: Mapped[Match] = relationship(back_populates="predictions")
    outcome: Mapped["Outcome | None"] = relationship(
        back_populates="prediction", uselist=False
    )


class Outcome(Base):
    __tablename__ = "outcomes"

    prediction_id: Mapped[int] = mapped_column(
        ForeignKey("predictions.id"), primary_key=True
    )
    happened: Mapped[int] = mapped_column(Integer)

    prediction: Mapped[Prediction] = relationship(back_populates="outcome")


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    position: Mapped[str | None] = mapped_column(String)
    actions: Mapped[int | None] = mapped_column(Integer)
    passes: Mapped[int | None] = mapped_column(Integer)
    shots: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    pass_accuracy: Mapped[float | None] = mapped_column(Float)
    progressive_pass: Mapped[float | None] = mapped_column(Float)
    key_pass_rate: Mapped[float | None] = mapped_column(Float)
    shot_share: Mapped[float | None] = mapped_column(Float)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    archetype: Mapped[str | None] = mapped_column(String)
    # Provenance + evidence-based reliability (Section 12). Nullable: a profile
    # persisted before these were tracked simply reports them as unknown, never
    # a fabricated value.
    matches: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[str | None] = mapped_column(String)  # comma-joined dataset names
    confidence: Mapped[float | None] = mapped_column(Float)


class PlayerSeasonProfile(Base):
    """One player's DNA in one competition/season — the evolution timeline.

    Stores the **full accumulator counters** (additive), so the global
    ``player_profiles`` row can always be rebuilt as the exact sum of a
    player's season rows — cross-competition accumulation instead of
    last-ingest-wins. New seasons (including youth competitions, which are
    just another competition id) slot in without schema changes.
    """

    __tablename__ = "player_season_profiles"
    __table_args__ = (Index("ix_psp_comp_season", "competition", "season"),)

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    competition: Mapped[str] = mapped_column(String, primary_key=True)
    season: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    position: Mapped[str | None] = mapped_column(String)
    # raw counters (fie.profiling.COUNTER_FIELDS) — additive across rows
    actions: Mapped[int | None] = mapped_column(Integer)
    passes: Mapped[int | None] = mapped_column(Integer)
    passes_completed: Mapped[int | None] = mapped_column(Integer)
    progressive: Mapped[int | None] = mapped_column(Integer)
    key_passes: Mapped[int | None] = mapped_column(Integer)
    assists: Mapped[int | None] = mapped_column(Integer)
    shots: Mapped[int | None] = mapped_column(Integer)
    goals: Mapped[int | None] = mapped_column(Integer)
    dribbles: Mapped[int | None] = mapped_column(Integer)
    dribbles_completed: Mapped[int | None] = mapped_column(Integer)
    turnovers: Mapped[int | None] = mapped_column(Integer)
    # derived reading for this season
    pass_accuracy: Mapped[float | None] = mapped_column(Float)
    progressive_pass: Mapped[float | None] = mapped_column(Float)
    key_pass_rate: Mapped[float | None] = mapped_column(Float)
    shot_share: Mapped[float | None] = mapped_column(Float)
    turnover_rate: Mapped[float | None] = mapped_column(Float)
    archetype: Mapped[str | None] = mapped_column(String)
    matches: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)


class PlayerBio(Base):
    """Biographical facts fused from an external source (e.g. Wikidata).

    Every row is traceable: the source name, the matched entity id (``qid``)
    and the fetch date. A player with no confident match has **no row** —
    unknown stays unknown, never a fabricated bio.
    """

    __tablename__ = "player_bios"

    player_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String)
    birth_date: Mapped[str | None] = mapped_column(String)   # ISO yyyy-mm-dd
    height_cm: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[str | None] = mapped_column(String)
    citizenship: Mapped[str | None] = mapped_column(String)
    qid: Mapped[str | None] = mapped_column(String)          # provenance: entity id
    source: Mapped[str | None] = mapped_column(String)       # provenance: dataset
    fetched_at: Mapped[str | None] = mapped_column(String)


class Interaction(Base):
    __tablename__ = "interactions"
    __table_args__ = (Index("ix_interactions_scope", "scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String)  # e.g. "Barcelona 2015/2016"
    from_player: Mapped[str] = mapped_column(String)
    to_player: Mapped[str] = mapped_column(String)
    passes: Mapped[int] = mapped_column(Integer)
    chances_created: Mapped[int] = mapped_column(Integer)


class Influence(Base):
    __tablename__ = "influence"
    __table_args__ = (Index("ix_influence_team", "team"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    team: Mapped[str | None] = mapped_column(String)
    lambda_on: Mapped[float] = mapped_column(Float)
    lambda_off: Mapped[float] = mapped_column(Float)
    delta: Mapped[float] = mapped_column(Float)
    on_minutes: Mapped[float] = mapped_column(Float)
    off_minutes: Mapped[float] = mapped_column(Float)


class IngestionRun(Base):
    """Audit log for the automated data pipeline (product level 18)."""

    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str] = mapped_column(String)          # ISO timestamp
    pairs: Mapped[str] = mapped_column(String)               # e.g. "11/27"
    matches_added: Mapped[int] = mapped_column(Integer)
    matches_skipped: Mapped[int] = mapped_column(Integer)    # already present
    matches_failed: Mapped[int] = mapped_column(Integer)
    quality_ok: Mapped[bool] = mapped_column(Boolean)
    quality_notes: Mapped[str | None] = mapped_column(String)


class ReplayStream(Base):
    """The Digital Match Twin's dense on-ball stream, one row per match.

    Every pass/carry/shot with real start+end locations and sub-second
    timestamps, plus point actions (receipts, recoveries, duels...), extracted
    from the raw provider feed by ``fie.sources.statsbomb.ball_stream``.
    Stored as JSON so the replay endpoint serves one read, no recomputation.
    """

    __tablename__ = "replay_streams"

    match_id: Mapped[str] = mapped_column(
        ForeignKey("matches.id"), primary_key=True
    )
    n_items: Mapped[int] = mapped_column(Integer)
    payload: Mapped[str] = mapped_column(String)      # JSON list of items
    built_at: Mapped[str] = mapped_column(String)


class FusedMatchRecord(Base):
    """Cross-provider fused match records (the Data Fusion Layer, persisted).

    One row per fixture resolved across 2+ providers: every fused field with
    its confidence, winning sources and recorded dissent (JSON), keyed by the
    canonical (date, home, away) identity from ``fie.fusion.match_key``.
    """

    __tablename__ = "fused_matches"
    __table_args__ = (
        Index("ix_fused_key", "match_date", "home_team", "away_team", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league: Mapped[str | None] = mapped_column(String)
    match_date: Mapped[str] = mapped_column(String)
    home_team: Mapped[str] = mapped_column(String)   # canonical entity key
    away_team: Mapped[str] = mapped_column(String)
    n_sources: Mapped[int] = mapped_column(Integer)
    sources: Mapped[str] = mapped_column(String)      # comma-joined names
    fields_json: Mapped[str] = mapped_column(String)  # {field: fuse_field(...)}
    conflicts: Mapped[str | None] = mapped_column(String)  # comma-joined fields
    created_at: Mapped[str] = mapped_column(String)


class LiveSession(Base):
    """A Live-Mode session's durable marker (Edge/scale: state lives in the DB).

    The session itself is *stateless compute*: its panel, vision, log and insights
    are a deterministic function of the stored observations, so any worker can
    rebuild and serve any live match from these rows — no in-process session,
    the horizontal-scale prerequisite for the global/edge vision.
    """

    __tablename__ = "live_sessions"

    match_id: Mapped[str] = mapped_column(String, primary_key=True)
    home: Mapped[str | None] = mapped_column(String)
    away: Mapped[str | None] = mapped_column(String)
    minute: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[str] = mapped_column(String)


class LiveObservation(Base):
    """One observation fed into a live session — the ordered, replayable log.

    Replaying these in ``seq`` order reproduces the live state exactly (the same
    deterministic recomputation the batch panel uses), so the store is the single
    source of truth and the "streamed == batch" guarantee is preserved.
    """

    __tablename__ = "live_observations"
    __table_args__ = (Index("ix_live_obs_match_seq", "match_id", "seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("live_sessions.match_id"))
    seq: Mapped[int] = mapped_column(Integer)
    minute: Mapped[float] = mapped_column(Float)
    team: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    x: Mapped[float | None] = mapped_column(Float)
    y: Mapped[float | None] = mapped_column(Float)
    player_id: Mapped[str | None] = mapped_column(String)
    player: Mapped[str | None] = mapped_column(String)


class PassingNetworkRow(Base):
    """A team's passing network for one match — built at the ingestion boundary.

    Mirrors ``ReplayStream``: the network is derived from raw provider events by
    the network-building module (the only place raw is read), stored as JSON, and
    served from here — so the ``/network`` serving path depends on the canonical
    store, never on a provider (the Dataset Fusion boundary rule).
    """

    __tablename__ = "passing_networks"

    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), primary_key=True)
    side: Mapped[str] = mapped_column(String, primary_key=True)   # HOME | AWAY
    payload: Mapped[str] = mapped_column(String)                  # JSON
    built_at: Mapped[str] = mapped_column(String)


class KnowledgeRecordRow(Base):
    """One datum of the Dataset Fusion, persisted (Phase B).

    The append-only store behind ``fie.fusiondata.KnowledgeRecord``: every datum
    keeps its context, provenance and temporal validity, so nothing is ever mixed
    across the boundaries that give it meaning. ``id`` is the content-addressed
    version id (stable for a given value); ``logical_id`` groups the versions of
    the same thing (the supersede chain). Values are never overwritten — a
    correction is a new row; a supersede only closes the prior row's temporal
    window (``valid_to`` + ``superseded_by``). JSON columns are TEXT, portable
    SQLite <-> Postgres.
    """

    __tablename__ = "knowledge_records"
    __table_args__ = (
        Index("ix_knowledge_logical", "logical_id"),
        Index("ix_knowledge_entity_kind", "entity_id", "kind"),
        Index("ix_knowledge_match", "match_id"),
        Index("ix_knowledge_layer", "layer"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    logical_id: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    layer: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str | None] = mapped_column(String)   # player/team/match
    match_id: Mapped[str | None] = mapped_column(String)    # isolation grouping
    value_json: Mapped[str] = mapped_column(String)
    context_json: Mapped[str] = mapped_column(String)
    provenance_json: Mapped[str] = mapped_column(String)
    valid_from: Mapped[str | None] = mapped_column(String)
    valid_to: Mapped[str | None] = mapped_column(String)
    superseded_by: Mapped[str | None] = mapped_column(String)
    permanence: Mapped[str] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float)
    stored_at: Mapped[str] = mapped_column(String)


class ModelVersion(Base):
    """The continuous-learning loop's version history (product level 19)."""

    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String)
    competition: Mapped[str | None] = mapped_column(String)
    base_rate: Mapped[float] = mapped_column(Float)
    tau: Mapped[float] = mapped_column(Float)
    holdout_log_loss: Mapped[float] = mapped_column(Float)
    baseline_log_loss: Mapped[float] = mapped_column(Float)  # active params, same holdout
    promoted: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str | None] = mapped_column(String)
