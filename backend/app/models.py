"""Production persistence schema (Section 6), portable SQLite <-> Postgres.

Mirrors the tables ``fie.db`` already validates against real StatsBomb data
(matches, events, snapshots, predictions/outcomes, player_profiles,
interactions, influence) as proper SQLAlchemy ORM models with foreign keys and
indexes, so the API layer (Phase B) has a real relational store to query instead
of one throwaway SQLite file per script.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, Integer, String
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
