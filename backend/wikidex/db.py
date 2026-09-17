"""Database initialization and versioned, repeatable catalogue bootstrap."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import quote

from sqlalchemy import create_engine, delete, event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Branch, BranchPage, Card, CardAlias, CardPortal, CatalogueSeed, MacroSet, ParentSet, Portal, SchemaVersion, SetMembership, Tree

ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'wikidex.sqlite3').as_posix()}")


def make_engine(url: str) -> Engine:
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30} if url.startswith("sqlite") else {}, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def configure_sqlite(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=30000")
    return engine


engine = make_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def begin_write(session: Session) -> None:
    """Acquire SQLite's writer reservation before reading mutable state."""
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    else:
        session.begin()


def init_db(bind: Engine | None = None, catalogue_path: Path | None = None, seed: bool = True) -> None:
    bind = bind or engine
    Base.metadata.create_all(bind)
    if bind.dialect.name == "sqlite":
        with bind.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    with Session(bind) as session:
        begin_write(session)
        if session.get(SchemaVersion, 1) is None:
            session.add(SchemaVersion(version=1, applied_at=time.time()))
        if seed:
            seed_catalogue(session, catalogue_path or ROOT / "data" / "catalogue.json")
            if catalogue_path is None:
                seed_catalogue_expansion(session, ROOT / "data" / "catalogue-expansion-v1.json")
        session.commit()


def seed_catalogue_expansion(session: Session, path: Path, seed_key: str = "editorial-expansion-v1") -> None:
    """Add small new branches to shipped trees without invalidating old rewards.

    Existing branches are deliberately left untouched: players keep every
    milestone they already earned. New articles stay out of boosters until the
    Wikimedia ingestion pipeline has validated them.
    """
    if not path.exists() or session.get(CatalogueSeed, seed_key):
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    trees = data.get("trees")
    if not isinstance(trees, list):
        raise ValueError("L’extension éditoriale doit contenir trees[].")

    existing = {card.title: card for card in session.scalars(select(Card))}
    aliases = {alias.title: alias.card for alias in session.scalars(select(CardAlias))}
    referenced_titles: list[str] = []
    branch_ids: set[str] = set()
    for raw_tree in trees:
        tree = session.get(Tree, str(raw_tree.get("id", "")))
        if tree is None:
            raise ValueError("Arbre cible absent de l’extension : " + str(raw_tree.get("id")))
        branches = raw_tree.get("branches")
        if not isinstance(branches, list) or not branches:
            raise ValueError("Chaque arbre étendu doit recevoir au moins une branche.")
        for item in branches:
            local_id = item.get("id")
            if not isinstance(local_id, str) or not local_id.strip():
                raise ValueError("Identité de branche d’extension invalide.")
            branch_id = f"{tree.id}:{local_id}"
            if branch_id in branch_ids:
                raise ValueError("Branche d’extension répétée : " + branch_id)
            branch_ids.add(branch_id)
            seen: set[str] = set()
            for tier in ("base", "full"):
                pages = item.get(tier + "_pages")
                if not isinstance(pages, list) or not pages or any(not isinstance(title, str) or not title.strip() for title in pages):
                    raise ValueError("Chaque micro-branche exige deux paliers non vides.")
                if len(pages) != len(set(pages)) or set(pages) & seen:
                    raise ValueError("Une page doit apparaître une seule fois dans une micro-branche.")
                seen.update(pages)
                referenced_titles.extend(pages)

    for title in dict.fromkeys(referenced_titles):
        if title in existing or title in aliases:
            continue
        card = Card(title=title, url="https://fr.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                    languages=0, monthly_views=0, rarity="common",
                    snippet="Article en attente de vérification Wikipédia.", image_url=None,
                    is_mother=False, verified=False, metrics_source="editorial-pending",
                    updated_at=0, active=False)
        session.add(card)
        session.flush()
        session.add(CardAlias(title=title, card_id=card.id))
        existing[title] = card

    for raw_tree in trees:
        tree = session.get(Tree, str(raw_tree["id"]))
        next_position = max((branch.position for branch in tree.branches), default=-1) + 1
        for item in raw_tree["branches"]:
            branch_id = f"{tree.id}:{item['id']}"
            if session.get(Branch, branch_id):
                continue
            branch = Branch(id=branch_id, tree_id=tree.id, title=item["title"],
                            description=item.get("description", ""), position=next_position)
            next_position += 1
            session.add(branch)
            session.flush()
            for tier in ("base", "full"):
                for position, title in enumerate(item[tier + "_pages"]):
                    card = existing.get(title) or aliases.get(title)
                    session.add(BranchPage(branch_id=branch.id, card_id=card.id, tier=tier, position=position))
    session.add(CatalogueSeed(key=seed_key, imported_at=time.time()))


def seed_catalogue(session: Session, path: Path, seed_key: str = "prototype-v1") -> None:
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = {card.title: card for card in session.scalars(select(Card))}
    # One explicit editorial correction, preserving inventory IDs and aliases.
    # Never overwrite a page already verified by Wikimedia.
    if not session.get(CatalogueSeed, "real-rights-pages-v2"):
        changed = False
        for raw in data["cards"]:
            old = raw.get("replaces_title")
            card = existing.get(old) if old else None
            if card and not card.verified and raw["title"] not in existing:
                existing.pop(old)
                card.title, card.url, card.snippet = raw["title"], raw["url"], raw["snippet"]
                card.languages = card.monthly_views = 0
                card.metrics_source, card.image_url = "editorial-pending", None
                session.execute(delete(CardPortal).where(CardPortal.card_id == card.id))
                existing[card.title] = card
                changed = True
        branch = session.get(Branch, "ddhc:ddhc_articles")
        if branch and changed:
            branch.title = "Droits fondamentaux & Libertés"
            session.execute(delete(BranchPage).where(BranchPage.branch_id == branch.id))
            for tier, titles in (("base", ("Liberté", "Droit naturel")),
                                 ("full", ("Égalité devant la loi", "Liberté d'expression"))):
                for index, title in enumerate(titles):
                    session.add(BranchPage(branch_id=branch.id, card_id=existing[title].id, tier=tier, position=index))
        if changed:
            from .popularity import assign_rarities
            assign_rarities([card for card in existing.values() if card.active])
        session.add(CatalogueSeed(key="real-rights-pages-v2", imported_at=time.time()))
    if session.get(CatalogueSeed, seed_key):
        for raw in data["cards"]:
            previous = session.get(CardAlias, raw["title"])
            card = existing.get(raw["title"]) or (previous.card if previous else None)
            if card:
                for title in {raw["title"], raw.get("legacy_title", raw["title"])}:
                    if not session.get(CardAlias, title):
                        session.add(CardAlias(title=title, card_id=card.id))
        return
    portals = {portal.title: portal for portal in session.scalars(select(Portal))}
    added = []
    for raw in data["cards"]:
        title = raw["title"]
        if title in existing:
            continue  # Never overwrite verified ingestion or player-owned IDs.
        card = Card(title=title, url=raw.get("url") or "https://fr.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                    languages=raw.get("languages", 0), monthly_views=raw.get("monthly_views", raw.get("monthlyViews", 0)),
                    rarity="common", snippet=raw.get("snippet", ""), image_url=raw.get("image_url", raw.get("image")),
                    is_mother=raw.get("is_mother", raw.get("isMother", False)), verified=False, metrics_source=raw.get("metrics_source", "prototype"), updated_at=0,
                    active=raw.get("active", True))
        session.add(card)
        session.flush()
        existing[title] = card
        added.append(card)
        for alias in {title, raw.get("legacy_title", title)}:
            if not session.get(CardAlias, alias):
                session.add(CardAlias(title=alias, card_id=card.id))
        for portal_raw in raw.get("portals", []):
            name = portal_raw["title"] if isinstance(portal_raw, dict) else portal_raw
            name = name if name.startswith("Portail:") else "Portail:" + name
            if name not in portals:
                portals[name] = Portal(title=name, url="https://fr.wikipedia.org/wiki/" + quote(name.replace(" ", "_")))
                session.add(portals[name])
                session.flush()
            session.add(CardPortal(card_id=card.id, portal_id=portals[name].id, verified=False))
    if added:
        from .popularity import assign_rarities
        assign_rarities([card for card in existing.values() if card.active])
    for raw in data.get("trees", []):
        if session.get(Tree, str(raw["id"])):
            continue
        macro_title = raw["macro"]["title"] if isinstance(raw["macro"], dict) else raw["macro"]
        parent_title = raw["parent_set"]["title"] if isinstance(raw["parent_set"], dict) else raw["parent_set"]
        macro = session.scalar(select(MacroSet).where(MacroSet.title == macro_title))
        if macro is None:
            macro = MacroSet(title=macro_title)
            session.add(macro)
            session.flush()
        parent = session.scalar(select(ParentSet).where(ParentSet.macro_id == macro.id, ParentSet.title == parent_title))
        if parent is None:
            parent = ParentSet(macro_id=macro.id, title=parent_title)
            session.add(parent)
            session.flush()
        mother = existing[raw["mother_title"]]
        mother.is_mother = True
        tree = Tree(id=str(raw["id"]), parent_set_id=parent.id, mother_card_id=mother.id)
        session.add(tree)
        session.flush()
        if not session.get(SetMembership, (parent.id, mother.id)):
            session.add(SetMembership(set_id=parent.id, card_id=mother.id))
        for position, item in enumerate(raw["branches"]):
            branch = Branch(id=f"{tree.id}:{item['id']}", tree_id=tree.id, title=item.get("title", item.get("name", "")), description=item.get("description", ""), position=position)
            session.add(branch)
            session.flush()
            for tier in ("base", "full"):
                for index, title in enumerate(dict.fromkeys(item.get(tier + "_pages", []))):
                    session.add(BranchPage(branch_id=branch.id, card_id=existing[title].id, tier=tier, position=index))
    session.add(CatalogueSeed(key=seed_key, imported_at=time.time()))
