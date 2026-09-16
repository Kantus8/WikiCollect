"""Relational catalogue and player ledger. No game state lives in the browser."""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SchemaVersion(Base):
    __tablename__ = "schema_version"
    version: Mapped[int] = mapped_column(primary_key=True)
    applied_at: Mapped[float] = mapped_column(Float)


class CatalogueSeed(Base):
    __tablename__ = "catalogue_seeds"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    imported_at: Mapped[float] = mapped_column(Float)


class Card(Base):
    __tablename__ = "cards"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), unique=True)
    wikipedia_page_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    url: Mapped[str] = mapped_column(Text)
    rarity: Mapped[str] = mapped_column(String(16), default="common", index=True)
    languages: Mapped[int] = mapped_column(Integer, default=0)
    monthly_views: Mapped[int] = mapped_column(Integer, default=0)
    snippet: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(Text)
    image_page_url: Mapped[str | None] = mapped_column(Text)
    image_artist: Mapped[str | None] = mapped_column(Text)
    image_license: Mapped[str | None] = mapped_column(String(256))
    is_mother: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics_source: Mapped[str] = mapped_column(String(256), default="prototype")
    updated_at: Mapped[float] = mapped_column(Float, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    portal_links: Mapped[list[CardPortal]] = relationship(back_populates="card", cascade="all, delete-orphan")
    memberships: Mapped[list[SetMembership]] = relationship(cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("languages >= 0 AND monthly_views >= 0"), CheckConstraint("rarity IN ('common','rare','epic','legendary','mythic')"))


class Portal(Base):
    __tablename__ = "portals"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), unique=True)
    url: Mapped[str] = mapped_column(Text)


class CardAlias(Base):
    """Stable resolution of prototype labels and Wikipedia redirects."""
    __tablename__ = "card_aliases"
    title: Mapped[str] = mapped_column(String(512), primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    card: Mapped[Card] = relationship()


class CardPortal(Base):
    __tablename__ = "card_portals"
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), primary_key=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    card: Mapped[Card] = relationship(back_populates="portal_links")
    portal: Mapped[Portal] = relationship()
    __table_args__ = (Index("ix_card_portals_portal", "portal_id", "card_id"),)


class PopularitySnapshot(Base):
    __tablename__ = "popularity_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7))
    languages: Mapped[int] = mapped_column(Integer)
    monthly_views: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(256))
    fetched_at: Mapped[float] = mapped_column(Float)
    __table_args__ = (UniqueConstraint("card_id", "month", "source"),)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[float] = mapped_column(Float)
    finished_at: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), index=True)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str] = mapped_column(Text, default="{}")


class IngestionItem(Base):
    __tablename__ = "ingestion_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingestion_runs.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), index=True)
    requested_title: Mapped[str] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    __table_args__ = (UniqueConstraint("run_id", "card_id"), Index("ix_ingestion_items_run_status", "run_id", "status"))


class MacroSet(Base):
    __tablename__ = "macro_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), unique=True)


class ParentSet(Base):
    __tablename__ = "parent_sets"
    id: Mapped[int] = mapped_column(primary_key=True)
    macro_id: Mapped[int] = mapped_column(ForeignKey("macro_sets.id"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    macro: Mapped[MacroSet] = relationship()
    __table_args__ = (UniqueConstraint("macro_id", "title"),)


class SetMembership(Base):
    """Belonging to a parent set is independent of a card's child tree."""
    __tablename__ = "set_memberships"
    set_id: Mapped[int] = mapped_column(ForeignKey("parent_sets.id", ondelete="CASCADE"), primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True)
    parent_set: Mapped[ParentSet] = relationship()


class Tree(Base):
    __tablename__ = "trees"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    parent_set_id: Mapped[int] = mapped_column(ForeignKey("parent_sets.id"), index=True)
    mother_card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), unique=True)
    parent_set: Mapped[ParentSet] = relationship()
    mother: Mapped[Card] = relationship()
    branches: Mapped[list[Branch]] = relationship(back_populates="tree", cascade="all, delete-orphan", order_by="Branch.position")


class Branch(Base):
    __tablename__ = "branches"
    id: Mapped[str] = mapped_column(String(256), primary_key=True)
    tree_id: Mapped[str] = mapped_column(ForeignKey("trees.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    tree: Mapped[Tree] = relationship(back_populates="branches")
    pages: Mapped[list[BranchPage]] = relationship(cascade="all, delete-orphan", order_by="BranchPage.position")


class BranchPage(Base):
    __tablename__ = "branch_pages"
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    tier: Mapped[str] = mapped_column(String(8), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    card: Mapped[Card] = relationship()
    __table_args__ = (CheckConstraint("tier IN ('base', 'full')"), Index("ix_branch_pages_card", "card_id"))


class Player(Base):
    __tablename__ = "players"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_hash: Mapped[str] = mapped_column(String(64), unique=True)
    currency: Mapped[float] = mapped_column(Float, default=600)
    last_accrual: Mapped[float] = mapped_column(Float)
    created_at: Mapped[float] = mapped_column(Float)
    packs_opened: Mapped[int] = mapped_column(Integer, default=0)
    imported_at: Mapped[float | None] = mapped_column(Float)
    __table_args__ = (CheckConstraint("currency >= 0 AND currency <= 3000"),)


class Inventory(Base):
    __tablename__ = "inventory"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    card: Mapped[Card] = relationship()
    __table_args__ = (CheckConstraint("quantity >= 0"),)


class Ticket(Base):
    __tablename__ = "tickets"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id"), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    portal: Mapped[Portal] = relationship()
    __table_args__ = (CheckConstraint("quantity >= 0"),)


class BranchClaim(Base):
    __tablename__ = "branch_claims"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    branch_id: Mapped[str] = mapped_column(ForeignKey("branches.id"), primary_key=True)
    tier: Mapped[str] = mapped_column(String(8), primary_key=True)
    reward: Mapped[float] = mapped_column(Float)
    claimed_at: Mapped[float] = mapped_column(Float)
    __table_args__ = (CheckConstraint("tier IN ('base', 'full')"),)


class GameEvent(Base):
    __tablename__ = "game_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[float] = mapped_column(Float)
    detail: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (Index("ix_game_events_player_time", "player_id", "created_at"),)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[float] = mapped_column(Float)
