"""Transactional game rules. Call these inside a locked player transaction."""
from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .models import Branch, BranchClaim, Card, CardAlias, CardPortal, GameEvent, Inventory, Player, Portal, Ticket, Tree

CURRENCY_CAP = 3000
PASSIVE_RATE = 1.0
PACK_COST = 300
PACK_SIZE = 4
STARTER_GRANT = 600
RARITY_WEIGHTS = {"common": 5500, "rare": 2800, "epic": 1200, "legendary": 450, "mythic": 50}
DUPLICATE_VALUES = {"common": 30, "rare": 75, "epic": 150, "legendary": 300, "mythic": 600}
# Collection rewards scale with size: a large collection is longer to finish, so
# it pays more, and its completion bonus grows with every page beyond the four
# of the former micro-collections.
COLLECTION_BASE_UNIT = 75
COLLECTION_FULL_UNIT = 150
COLLECTION_SIZE_BONUS = 30
COLLECTION_BONUS_PIVOT = 4


class GameError(Exception):
    def __init__(self, message: str, code: str = "invalid_action", status: int = 409):
        self.message, self.code, self.status = message, code, status
        super().__init__(message)


def accrue(player: Player, now: float | None = None) -> None:
    now = time.time() if now is None else now
    delta = max(0.0, now - player.last_accrual)
    player.currency = min(CURRENCY_CAP, player.currency + delta * PASSIVE_RATE)
    # A backwards wall clock must not re-credit previously elapsed seconds.
    player.last_accrual = max(now, player.last_accrual)


def credit(player: Player, amount: float) -> float:
    before = player.currency
    player.currency = min(CURRENCY_CAP, before + amount)
    return round(player.currency - before, 6)


def session_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_player(session: Session, token: str | None, create: bool = False, now: float | None = None) -> tuple[Player, str | None]:
    player = None
    if token and len(token) <= 200:
        query = select(Player).where(Player.session_hash == session_hash(token))
        if session.get_bind().dialect.name != "sqlite":
            query = query.with_for_update()
        player = session.scalar(query)
    if player is not None:
        return player, None
    if not create:
        raise GameError("Session absente ou expirée. Rechargez votre collection.", "session_required", 401)
    now = time.time() if now is None else now
    token = secrets.token_urlsafe(48)
    player = Player(id=str(uuid.uuid4()), session_hash=session_hash(token), currency=STARTER_GRANT, last_accrual=now, created_at=now, packs_opened=0)
    session.add(player)
    session.flush()
    physics = session.scalar(select(Portal).where(Portal.title == "Portail:Physique"))
    if physics is not None:
        session.add(Ticket(player_id=player.id, portal_id=physics.id, quantity=1))
    record_event(session, player, "welcome", {"currency": STARTER_GRANT, "physics_ticket": physics is not None}, now)
    return player, token


def record_event(session: Session, player: Player, kind: str, detail: dict, now: float | None = None) -> None:
    session.add(GameEvent(player_id=player.id, kind=kind, detail=detail, created_at=time.time() if now is None else now))


def card_payload(card: Card, quantity: int | None = None, visible_set_ids: set[int] | None = None) -> dict:
    result = {"id": card.id, "title": card.title, "url": card.url, "rarity": card.rarity,
              "languages": card.languages, "monthly_views": card.monthly_views, "snippet": card.snippet,
              "image_url": card.image_url, "image_page_url": card.image_page_url, "image_artist": card.image_artist,
              "image_license": card.image_license, "is_mother": card.is_mother, "verified": card.verified,
              "metrics_source": card.metrics_source, "active": card.active,
              "portals": [{"id": link.portal.id, "title": link.portal.title, "verified": link.verified} for link in card.portal_links],
              "parent_sets": [{"id": member.parent_set.id, "title": member.parent_set.title,
                               "macro": {"id": member.parent_set.macro.id, "title": member.parent_set.macro.title}}
                              for member in card.memberships if member.set_id in (visible_set_ids or set())]}
    if quantity is not None:
        result["quantity"] = quantity
    return result


def portal_pool(session: Session, portal_id: int) -> list[Card]:
    return list(session.scalars(select(Card).join(CardPortal).where(CardPortal.portal_id == portal_id,
                CardPortal.verified.is_(True), Card.verified.is_(True), Card.active.is_(True))).unique())


def rarity_rates(cards: list[Card]) -> dict[str, float]:
    available = {card.rarity for card in cards}
    total = sum(weight for rarity, weight in RARITY_WEIGHTS.items() if rarity in available)
    return {rarity: round(weight / total * 100, 6) if total and rarity in available else 0
            for rarity, weight in RARITY_WEIGHTS.items()}


def state_payload(session: Session, player: Player, now: float | None = None) -> dict:
    session.flush()
    rows = list(session.scalars(select(Inventory).where(Inventory.player_id == player.id, Inventory.quantity > 0)
                .options(selectinload(Inventory.card).selectinload(Card.portal_links).selectinload(CardPortal.portal))))
    tickets = []
    for row in session.scalars(select(Ticket).where(Ticket.player_id == player.id, Ticket.quantity > 0).options(selectinload(Ticket.portal))):
        pool = portal_pool(session, row.portal_id)
        tickets.append({"portal_id": row.portal_id, "title": row.portal.title, "quantity": row.quantity,
                        "available": bool(pool), "rarity_rates": rarity_rates(pool)})
    cards_count = session.scalar(select(func.count()).select_from(Card).where(Card.active.is_(True)))
    visible_sets = visible_parent_sets(session, player)
    return {"currency": round(player.currency, 6), "currency_cap": CURRENCY_CAP, "passive_rate": PASSIVE_RATE,
            "pack_cost": PACK_COST, "server_time": time.time() if now is None else now,
            "inventory": [card_payload(row.card, row.quantity, visible_sets) for row in sorted(rows, key=lambda row: row.card.title.casefold())],
            "tickets": tickets, "stats": {"unique_cards": len(rows), "total_cards": sum(row.quantity for row in rows),
            "duplicates": sum(row.quantity - 1 for row in rows), "packs_opened": player.packs_opened},
            "catalogue": {"cards": cards_count, "trees": session.scalar(select(func.count()).select_from(Tree)),
                "verified_cards": session.scalar(select(func.count()).select_from(Card).where(Card.verified.is_(True), Card.active.is_(True)))},
            "starter_grant": STARTER_GRANT, "imported": player.imported_at is not None}


def owned_ids(session: Session, player: Player) -> set[int]:
    return set(session.scalars(select(Inventory.card_id).where(Inventory.player_id == player.id, Inventory.quantity > 0)))


def visible_parent_sets(session: Session, player: Player) -> set[int]:
    return set(session.scalars(select(Tree.parent_set_id).join(Inventory, Inventory.card_id == Tree.mother_card_id)
                              .where(Inventory.player_id == player.id, Inventory.quantity > 0)))


def branch_rewards(branch) -> dict[str, int]:
    """Nominal payout of each tier, proportional to the size of the collection."""
    base_pages = sum(page.tier == "base" for page in branch.pages)
    full_pages = sum(page.tier == "full" for page in branch.pages)
    bonus = COLLECTION_SIZE_BONUS * max(0, base_pages + full_pages - COLLECTION_BONUS_PIVOT)
    return {"base": COLLECTION_BASE_UNIT * base_pages, "full": COLLECTION_FULL_UNIT * full_pages + bonus}


def branch_status(branch, owned: set[int]) -> tuple[bool, bool]:
    base = {page.card_id for page in branch.pages if page.tier == "base"}
    full = {page.card_id for page in branch.pages if page.tier == "full"}
    base_complete = bool(base) and base <= owned
    return base_complete, base_complete and bool(full) and full <= owned


def evaluate_milestones(session: Session, player: Player) -> list[dict]:
    session.flush()
    owned = owned_ids(session, player)
    claims = {(row.branch_id, row.tier) for row in session.scalars(select(BranchClaim).where(BranchClaim.player_id == player.id))}
    milestones = []
    for tree in session.scalars(select(Tree)):
        if tree.mother_card_id not in owned:
            continue
        for branch in tree.branches:
            base, full = branch_status(branch, owned)
            rewards = branch_rewards(branch)
            for tier, complete, nominal in (("base", base, rewards["base"]), ("full", full, rewards["full"])):
                if not complete or (branch.id, tier) in claims:
                    continue
                actual = credit(player, nominal)
                session.add(BranchClaim(player_id=player.id, branch_id=branch.id, tier=tier, reward=actual, claimed_at=time.time()))
                claims.add((branch.id, tier))
                milestone = {"branch_title": branch.title, "mother_title": tree.mother.title, "tier": tier, "reward": actual, "nominal_reward": nominal}
                milestones.append(milestone)
                record_event(session, player, "milestone", milestone)
    return milestones


def trees_payload(session: Session, player: Player) -> dict:
    owned = owned_ids(session, player)
    visible_sets = visible_parent_sets(session, player)
    claimed = {(row.branch_id, row.tier) for row in session.scalars(select(BranchClaim).where(BranchClaim.player_id == player.id))}
    result = []
    for tree in session.scalars(select(Tree).order_by(Tree.id)):
        public_id = hashlib.sha256((player.id + ":" + tree.id).encode()).hexdigest()[:24]
        if tree.mother_card_id not in owned:
            result.append({"id": public_id, "locked": True})
            continue
        parent, branches = tree.parent_set, []
        collected_pages = total_pages = completed_branches = 0
        for branch in tree.branches:
            base, full = branch_status(branch, owned)
            total_pages += len(branch.pages)
            collected_pages += sum(page.card_id in owned for page in branch.pages)
            completed_branches += int(full)
            rewards = branch_rewards(branch)
            branches.append({"id": branch.id, "title": branch.title, "description": branch.description,
                             "base_complete": base, "full_complete": full,
                             "base_reward": rewards["base"], "full_reward": rewards["full"],
                             "total_pages": len(branch.pages),
                             "base_reward_claimed": (branch.id, "base") in claimed, "full_reward_claimed": (branch.id, "full") in claimed,
                             **{tier + "_pages": [{**card_payload(page.card, visible_set_ids=visible_sets), "owned": True} if page.card_id in owned else {"owned": False}
                                for page in branch.pages if page.tier == tier] for tier in ("base", "full")}})
        result.append({"id": public_id, "locked": False, "macro": {"id": parent.macro.id, "title": parent.macro.title},
                       "parent_set": {"id": parent.id, "title": parent.title}, "mother": card_payload(tree.mother, visible_set_ids=visible_sets),
                       "collected_pages": collected_pages, "total_pages": total_pages,
                       "completed_branches": completed_branches, "total_branches": len(branches),
                       "complete": bool(branches) and completed_branches == len(branches), "branches": branches})
    return {"trees": result}


def draw_cards(pool: list[Card], count: int, require_all_rarities: bool, randbelow: Callable[[int], int] | None = None) -> list[Card]:
    randbelow = randbelow or secrets.randbelow
    buckets = {rarity: [card for card in pool if card.rarity == rarity] for rarity in RARITY_WEIGHTS}
    if not pool or (require_all_rarities and any(not bucket for bucket in buckets.values())):
        raise GameError("Catalogue incomplet : aucune dépense effectuée. Lancez ou terminez l’ingestion Wikipédia.", "catalogue_incomplete")
    total = sum(weight for rarity, weight in RARITY_WEIGHTS.items() if buckets[rarity])
    drawn = []
    for _ in range(count):
        roll = randbelow(total)
        for rarity, weight in RARITY_WEIGHTS.items():
            if not buckets[rarity]:
                continue
            if roll < weight:
                drawn.append(buckets[rarity][randbelow(len(buckets[rarity]))])
                break
            roll -= weight
    return drawn


def add_card(session: Session, player: Player, card: Card, quantity: int = 1) -> None:
    row = session.get(Inventory, (player.id, card.id))
    if row is None:
        session.add(Inventory(player_id=player.id, card_id=card.id, quantity=quantity))
        session.flush()
    else:
        row.quantity += quantity


def buy_pack(session: Session, player: Player, portal_id: int | None = None, randbelow=None) -> dict:
    if portal_id is None:
        if player.currency < PACK_COST:
            raise GameError("Curiosité insuffisante : un pack coûte 300.", "insufficient_currency")
        pool = list(session.scalars(select(Card).where(Card.active.is_(True))))
        drawn = draw_cards(pool, PACK_SIZE, True, randbelow)
        player.currency -= PACK_COST
    else:
        ticket = session.get(Ticket, (player.id, portal_id))
        if ticket is None or ticket.quantity < 1:
            raise GameError("Vous ne possédez aucun ticket pour ce portail.", "insufficient_tickets")
        pool = portal_pool(session, portal_id)
        if not pool:
            raise GameError("Aucune page vérifiée pour ce portail. Votre ticket est conservé.", "portal_unavailable")
        drawn = draw_cards(pool, 1, False, randbelow)
        ticket.quantity -= 1
    acquisitions = []
    for card in drawn:
        before = session.get(Inventory, (player.id, card.id))
        previous_quantity = before.quantity if before else 0
        add_card(session, player, card)
        acquisitions.append((card, previous_quantity + 1, previous_quantity > 0))
    player.packs_opened += 1
    milestones = evaluate_milestones(session, player)
    record_event(session, player, "pack", {"portal_id": portal_id, "cost": PACK_COST if portal_id is None else 0,
                                          "card_ids": [card.id for card in drawn], "titles": [card.title for card in drawn]})
    visible_sets = visible_parent_sets(session, player)
    return {"cards": [{**card_payload(card, quantity, visible_sets), "is_duplicate": duplicate}
                      for card, quantity, duplicate in acquisitions],
            "milestones": milestones, "state": state_payload(session, player)}


def sell_duplicates(session: Session, player: Player, card_id: int | None, all_duplicates: bool) -> dict:
    query = select(Inventory).where(Inventory.player_id == player.id, Inventory.quantity > 1)
    if not all_duplicates:
        query = query.where(Inventory.card_id == card_id)
    rows = list(session.scalars(query))
    if not rows:
        raise GameError("Aucun doublon disponible.", "no_duplicates")
    nominal, sold = 0, 0
    for row in rows:
        count = row.quantity - 1 if all_duplicates else 1
        nominal += count * DUPLICATE_VALUES[row.card.rarity]
        row.quantity -= count
        sold += count
    actual = credit(player, nominal)
    record_event(session, player, "sale", {"count": sold, "earned": actual, "nominal_value": nominal})
    return {"earned": actual, "state": state_payload(session, player)}


def convert_duplicate(session: Session, player: Player, card_id: int, portal_id: int) -> dict:
    row = session.get(Inventory, (player.id, card_id))
    if row is None or row.quantity < 2:
        raise GameError("La conversion nécessite un doublon ; votre exemplaire est conservé.", "no_duplicates")
    link = session.get(CardPortal, (card_id, portal_id))
    if link is None or not link.verified or not row.card.verified or not row.card.active:
        raise GameError("Ce portail n’est pas un portail Wikipédia vérifié de cette carte.", "invalid_portal")
    row.quantity -= 1
    ticket = session.get(Ticket, (player.id, portal_id))
    if ticket is None:
        session.add(Ticket(player_id=player.id, portal_id=portal_id, quantity=1))
    else:
        ticket.quantity += 1
    record_event(session, player, "conversion", {"card_id": card_id, "portal_id": portal_id})
    return {"state": state_payload(session, player)}


def export_save(session: Session, player: Player) -> dict:
    """Portable gameplay state, including reward receipts to prevent restore payouts."""
    return {"format": "wikidex-save", "version": 2, "currency": round(player.currency, 6),
            "inventory": {row.card.title: row.quantity for row in session.scalars(
                select(Inventory).where(Inventory.player_id == player.id, Inventory.quantity > 0))},
            "portalTickets": {row.portal.title: row.quantity for row in session.scalars(
                select(Ticket).where(Ticket.player_id == player.id, Ticket.quantity > 0))},
            "packs_opened": player.packs_opened,
            "branch_claims": [{"branch_id": row.branch_id, "tier": row.tier, "reward": row.reward,
                               "claimed_at": row.claimed_at} for row in session.scalars(
                select(BranchClaim).where(BranchClaim.player_id == player.id)
                .order_by(BranchClaim.branch_id, BranchClaim.tier))]}


def import_prototype(session: Session, player: Player, payload: dict, legacy_aliases: dict[str, str] | None = None) -> dict:
    if player.imported_at is not None:
        raise GameError("Cette sauvegarde a déjà été migrée.", "already_imported")
    if player.packs_opened or owned_ids(session, player):
        raise GameError("L’import exige une nouvelle partie vide afin de préserver votre collection actuelle.", "import_requires_empty_player")
    cards = {card.title: card for card in session.scalars(select(Card))}
    alias_cards = {alias.title: alias.card for alias in session.scalars(select(CardAlias))}
    portals = {portal.title: portal for portal in session.scalars(select(Portal))}
    aliases = legacy_aliases or {}
    ignored = []
    if sum(payload["inventory"].values()) > 10000 or sum(payload["portalTickets"].values()) > 1000:
        raise GameError("Sauvegarde trop volumineuse (10 000 cartes et 1 000 tickets maximum).", "invalid_import", 422)
    for title, count in payload["inventory"].items():
        normalized = aliases.get(title, title)
        card = cards.get(normalized) or alias_cards.get(normalized) or alias_cards.get(title)
        if card is None:
            ignored.append(title)
        elif count:
            add_card(session, player, card, count)
    for row in session.scalars(select(Ticket).where(Ticket.player_id == player.id)):
        row.quantity = 0
    for title, count in payload["portalTickets"].items():
        title = title if title.startswith("Portail:") else "Portail:" + title
        portal = portals.get(title)
        if portal is None:
            ignored.append(title)
        elif count:
            ticket = session.get(Ticket, (player.id, portal.id))
            if ticket:
                ticket.quantity = count
            else:
                session.add(Ticket(player_id=player.id, portal_id=portal.id, quantity=count))
    player.currency = max(0, min(CURRENCY_CAP, float(payload["currency"])))
    player.imported_at = time.time()
    if payload.get("format") == "wikidex-save" and payload.get("version") == 2:
        owned = owned_ids(session, player)
        receipts = set()
        for claim in payload["branch_claims"]:
            key = (claim["branch_id"], claim["tier"])
            branch = session.get(Branch, claim["branch_id"])
            if key in receipts or branch is None or branch.tree.mother_card_id not in owned:
                raise GameError("Historique de récompenses incompatible avec cette collection.", "invalid_save", 422)
            receipts.add(key)
            session.add(BranchClaim(player_id=player.id, **claim))
        player.packs_opened = payload["packs_opened"]
        milestones = []  # Restoring never awards already-collected bonuses again.
    else:
        milestones = evaluate_milestones(session, player)
    record_event(session, player, "import", {"ignored_titles": ignored, "milestones": len(milestones)})
    return {"state": state_payload(session, player), "ignored_titles": ignored, "milestones": milestones}


def request_fingerprint(path: str, payload: dict) -> str:
    return hashlib.sha256(json.dumps({"path": path, "payload": payload}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
