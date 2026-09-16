from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.wikidex import game
from backend.wikidex.api import create_app
from backend.wikidex.db import begin_write, init_db, make_engine, seed_catalogue
from backend.wikidex.models import Branch, BranchClaim, BranchPage, Card, CardAlias, CardPortal, GameEvent, Inventory, MacroSet, ParentSet, Player, Portal, SetMembership, Ticket, Tree


@pytest.fixture
def database(tmp_path):
    engine = make_engine("sqlite:///" + (tmp_path / "test.sqlite3").as_posix())
    init_db(engine, seed=False)
    with Session(engine) as session:
        cards = [Card(title=f"Page {rarity}", url="https://fr.wikipedia.org/wiki/Test", rarity=rarity, languages=10,
                      monthly_views=100, snippet="Page réelle", is_mother=i == 0, verified=True, metrics_source="test", active=True)
                 for i, rarity in enumerate(game.RARITY_WEIGHTS)]
        physics = Portal(title="Portail:Physique", url="https://fr.wikipedia.org/wiki/Portail:Physique")
        other = Portal(title="Portail:Astronomie", url="https://fr.wikipedia.org/wiki/Portail:Astronomie")
        macro = MacroSet(title="Sciences")
        session.add_all(cards + [physics, other, macro])
        session.flush()
        parent = ParentSet(title="Physique", macro_id=macro.id)
        session.add(parent)
        session.flush()
        tree = Tree(id="a-secret-encyclopedic-title", mother_card_id=cards[0].id, parent_set_id=parent.id)
        session.add(tree)
        session.flush()
        branch = Branch(id="origins", tree_id=tree.id, title="Origines", description="Une branche")
        session.add(branch)
        session.flush()
        session.add_all([BranchPage(branch_id=branch.id, card_id=cards[1].id, tier="base"),
                         BranchPage(branch_id=branch.id, card_id=cards[2].id, tier="full")])
        for card in cards:
            session.add(CardPortal(card_id=card.id, portal_id=physics.id, verified=True))
        session.commit()
    yield engine
    engine.dispose()


@pytest.fixture
def player_session(database):
    with Session(database, expire_on_commit=False) as session:
        begin_write(session)
        player, _ = game.get_player(session, None, create=True, now=1000)
        session.flush()
        yield session, player
        session.rollback()


@pytest.fixture
def client(database):
    with TestClient(create_app(database, seed=False), client=("127.0.0.1", 40000)) as client:
        assert client.get("/api/state").status_code == 200
        yield client


def test_passive_fixed_fractional_and_clock_rollback(player_session):
    _, player = player_session
    game.accrue(player, 1000.125)
    assert player.currency == 600.125
    game.accrue(player, 999)
    assert player.currency == 600.125
    assert player.last_accrual == 1000.125
    game.accrue(player, 1000.5)
    assert player.currency == 600.5
    game.accrue(player, 90000)
    assert player.currency == 3000
    game.accrue(player, 90001)
    assert player.currency == 3000


def test_exact_five_minute_pack(player_session):
    session, player = player_session
    player.currency = 0
    game.accrue(player, 1299.99)
    with pytest.raises(game.GameError, match="insuffisante"):
        game.buy_pack(session, player)
    game.accrue(player, 1300)
    result = game.buy_pack(session, player, randbelow=lambda _: 0)
    assert result["state"]["currency"] == 0
    assert len(result["cards"]) == 4


def test_exhaustive_rarity_boundaries(player_session):
    session, _ = player_session
    pool = list(session.scalars(select(Card)))
    rolls = iter(value for roll in range(10000) for value in (roll, 0))
    result = game.draw_cards(pool, 10000, True, lambda bound: next(rolls))
    assert Counter(card.rarity for card in result) == game.RARITY_WEIGHTS


def test_pack_reports_each_acquisition_including_intra_pack_duplicates(player_session):
    session, player = player_session
    result = game.buy_pack(session, player, randbelow=lambda _: 0)
    assert [card["quantity"] for card in result["cards"]] == [1, 2, 3, 4]
    assert [card["is_duplicate"] for card in result["cards"]] == [False, True, True, True]
    assert result["state"]["stats"]["total_cards"] == 4


def test_incomplete_standard_pool_does_not_debit(player_session):
    session, player = player_session
    session.get(Card, 5).active = False
    with pytest.raises(game.GameError, match="Catalogue incomplet"):
        game.buy_pack(session, player)
    assert player.currency == 600
    assert not game.owned_ids(session, player)
    assert player.packs_opened == 0


def test_full_requires_base_and_rewards_are_unique(player_session):
    session, player = player_session
    game.add_card(session, player, session.get(Card, 1))
    game.add_card(session, player, session.get(Card, 3))
    assert game.evaluate_milestones(session, player) == []
    game.add_card(session, player, session.get(Card, 2))
    result = game.evaluate_milestones(session, player)
    assert [(item["tier"], item["reward"]) for item in result] == [("base", 150), ("full", 400)]
    assert player.currency == 1150
    game.add_card(session, player, session.get(Card, 2))
    assert game.evaluate_milestones(session, player) == []
    assert session.scalar(select(func.count()).select_from(BranchClaim)) == 2


def test_hidden_tree_no_reveal_and_delayed_mother_rewards(player_session):
    session, player = player_session
    for card_id in (2, 3):
        game.add_card(session, player, session.get(Card, card_id))
    assert game.evaluate_milestones(session, player) == []
    tree = game.trees_payload(session, player)["trees"][0]
    assert set(tree) == {"id", "locked"}
    assert tree["locked"] is True
    assert "secret" not in json.dumps(tree)
    assert session.scalar(select(func.count()).select_from(BranchClaim)) == 0
    game.add_card(session, player, session.get(Card, 1))
    assert len(game.evaluate_milestones(session, player)) == 2
    assert game.evaluate_milestones(session, player) == []


def test_missing_leaf_has_no_identity_or_metadata(player_session):
    session, player = player_session
    game.add_card(session, player, session.get(Card, 1))
    session.flush()
    branch = game.trees_payload(session, player)["trees"][0]["branches"][0]
    assert branch["base_pages"] == [{"owned": False}]
    assert branch["full_pages"] == [{"owned": False}]
    game.add_card(session, player, session.get(Card, 2))
    session.flush()
    branch = game.trees_payload(session, player)["trees"][0]["branches"][0]
    assert branch["base_pages"][0]["title"] == "Page rare"
    assert branch["full_pages"] == [{"owned": False}]


def test_parent_sets_are_explicit_and_separate_from_child_branches(player_session):
    session, player = player_session
    session.add(SetMembership(set_id=1, card_id=1))
    game.add_card(session, player, session.get(Card, 2))
    state = game.state_payload(session, player)
    # A leaf belongs to the branch, not automatically to the mother's parent set.
    assert state["inventory"][0]["parent_sets"] == []
    game.add_card(session, player, session.get(Card, 1))
    state = game.state_payload(session, player)
    mother = next(card for card in state["inventory"] if card["id"] == 1)
    assert mother["parent_sets"] == [{"id": 1, "title": "Physique", "macro": {"id": 1, "title": "Sciences"}}]


def test_milestone_cap_reports_actual_credit(player_session):
    session, player = player_session
    player.currency = 2990
    for card_id in (1, 2, 3):
        game.add_card(session, player, session.get(Card, card_id))
    result = game.evaluate_milestones(session, player)
    assert [item["reward"] for item in result] == [10, 0]
    assert player.currency == 3000
    player.currency = 2000
    assert game.evaluate_milestones(session, player) == []
    assert player.currency == 2000


@pytest.mark.parametrize("card_id,expected", [(1,30),(2,75),(3,150),(4,300),(5,600)])
def test_sale_each_rarity_keeps_owned_card(player_session, card_id, expected):
    session, player = player_session
    game.add_card(session, player, session.get(Card, card_id), 2)
    result = game.sell_duplicates(session, player, card_id, False)
    assert result["earned"] == expected
    assert session.get(Inventory, (player.id, card_id)).quantity == 1


def test_bulk_sale_cap_and_keep_one(player_session):
    session, player = player_session
    player.currency = 2999.5
    for card_id in range(1, 6):
        game.add_card(session, player, session.get(Card, card_id), 3)
    result = game.sell_duplicates(session, player, None, True)
    assert result["earned"] == 0.5
    assert result["state"]["currency"] == 3000
    assert all(row.quantity == 1 for row in session.scalars(select(Inventory)))
    with pytest.raises(game.GameError):
        game.sell_duplicates(session, player, None, True)


def test_portal_conversion_membership_and_preservation(player_session):
    session, player = player_session
    game.add_card(session, player, session.get(Card, 2), 2)
    with pytest.raises(game.GameError, match="portail"):
        game.convert_duplicate(session, player, 2, 2)
    assert session.get(Inventory, (player.id, 2)).quantity == 2
    result = game.convert_duplicate(session, player, 2, 1)
    assert session.get(Inventory, (player.id, 2)).quantity == 1
    assert result["state"]["tickets"][0]["quantity"] == 2
    with pytest.raises(game.GameError):
        game.convert_duplicate(session, player, 2, 1)


def test_unverified_portal_rejected(player_session):
    session, player = player_session
    game.add_card(session, player, session.get(Card, 2), 2)
    session.get(CardPortal, (2, 1)).verified = False
    with pytest.raises(game.GameError):
        game.convert_duplicate(session, player, 2, 1)
    assert session.get(Inventory, (player.id, 2)).quantity == 2


def test_ticket_one_card_free_curiosity_and_portal_guarantee(player_session):
    session, player = player_session
    for card_id in (1, 2, 3, 4):
        session.get(CardPortal, (card_id, 1)).verified = False
    player.currency = 0
    result = game.buy_pack(session, player, 1)
    assert len(result["cards"]) == 1
    assert result["cards"][0]["id"] == 5
    assert result["state"]["currency"] == 0
    assert session.get(Ticket, (player.id, 1)).quantity == 0


def test_unavailable_portal_never_spends_ticket(player_session):
    session, player = player_session
    for card in session.scalars(select(Card)):
        card.verified = False
    with pytest.raises(game.GameError, match="ticket est conservé"):
        game.buy_pack(session, player, 1)
    assert session.get(Ticket, (player.id, 1)).quantity == 1
    assert player.currency == 600
    assert game.owned_ids(session, player) == set()


def test_portal_renormalization_retains_relative_weights(player_session):
    session, _ = player_session
    pool = [session.get(Card, 4), session.get(Card, 5)]
    assert game.rarity_rates(pool) == {"common": 0, "rare": 0, "epic": 0, "legendary": 90, "mythic": 10}
    rolls = iter(value for roll in range(500) for value in (roll, 0))
    assert Counter(card.rarity for card in game.draw_cards(pool, 500, False, lambda _: next(rolls))) == {"legendary": 450, "mythic": 50}


def test_session_cookie_is_opaque_and_httponly(client):
    token = client.cookies["wikidex_session"]
    assert len(token) >= 48
    fresh = TestClient(client.app)
    with fresh:
        response = fresh.get("/api/state")
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert response.json()["inventory"] == []


def test_pack_idempotency_and_body_consistency(client):
    first = client.post("/api/packs", json={}, headers={"Idempotency-Key": "same-pack"})
    assert first.status_code == 200
    again = client.post("/api/packs", json={}, headers={"Idempotency-Key": "same-pack"})
    assert again.json() == first.json()
    assert len(first.json()["cards"]) == 4
    assert client.get("/api/state").json()["stats"]["packs_opened"] == 1
    conflict = client.post("/api/packs", json={"portal_id": 1}, headers={"Idempotency-Key": "same-pack"})
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "idempotency_conflict"


def test_concurrent_same_key_delivers_once(client):
    def buy(_):
        return client.post("/api/packs", json={}, headers={"Idempotency-Key": "concurrent"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(buy, range(8)))
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == responses[0].json() for response in responses)
    assert client.get("/api/state").json()["stats"]["packs_opened"] == 1


def test_concurrent_different_keys_never_overspend(client, monkeypatch):
    monkeypatch.setattr(game, "evaluate_milestones", lambda *_: [])
    def buy(index):
        return client.post("/api/packs", json={}, headers={"Idempotency-Key": f"independent-{index}"})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(buy, range(8)))
    assert Counter(response.status_code for response in responses) == {200: 2, 409: 6}
    state = client.get("/api/state").json()
    assert state["stats"]["packs_opened"] == 2
    assert state["stats"]["total_cards"] == 8
    assert 0 <= state["currency"] < 30


def test_mutation_rollback_on_mid_purchase_failure(client, database, monkeypatch):
    def failure(*_):
        raise RuntimeError("Simulated failure after delivery")
    monkeypatch.setattr(game, "evaluate_milestones", failure)
    with pytest.raises(RuntimeError):
        client.post("/api/packs", json={}, headers={"Idempotency-Key": "failed"})
    with Session(database) as session:
        assert session.scalar(select(func.count()).select_from(Inventory)) == 0
        player = session.scalar(select(Player))
        assert player.packs_opened == 0
        assert 600 <= player.currency < 601


def test_origin_and_required_key_guards(client):
    denied = client.post("/api/packs", json={}, headers={"Idempotency-Key": "bad-origin", "Origin": "https://attacker.example"})
    assert denied.status_code == 403
    assert client.post("/api/packs", json={}).status_code == 400
    assert client.post("/api/packs", json={"portal_id": True}, headers={"Idempotency-Key": "invalid-id"}).status_code == 422
    assert client.get("/api/state", headers={"Host": "attacker.example"}).status_code == 400


def test_game_state_persists_and_players_are_isolated(client, database):
    token = client.cookies["wikidex_session"]
    assert client.post("/api/packs", json={}, headers={"Idempotency-Key": "persist"}).status_code == 200
    with TestClient(create_app(database, seed=False)) as restarted:
        restarted.cookies.set("wikidex_session", token)
        assert restarted.get("/api/state").json()["stats"]["total_cards"] == 4
        restarted.cookies.clear()
        assert restarted.get("/api/state").json()["stats"]["total_cards"] == 0


def test_import_once_bounded_and_no_offline_clock_credit(client):
    payload = {"currency": 200, "inventory": {"Page common": 2, "Unknown": 1}, "portalTickets": {"Physique": 4}}
    response = client.post("/api/import", json=payload, headers={"Idempotency-Key": "import1"})
    assert response.status_code == 200
    assert response.json()["ignored_titles"] == ["Unknown"]
    assert response.json()["state"]["currency"] == 200
    assert response.json()["state"]["stats"]["total_cards"] == 2
    assert response.json()["state"]["tickets"][0]["quantity"] == 4
    assert client.post("/api/import", json=payload, headers={"Idempotency-Key": "import1"}).json() == response.json()
    assert client.post("/api/import", json=payload, headers={"Idempotency-Key": "import2"}).status_code == 409


def test_import_preserves_redirect_alias_after_title_canonicalization(player_session):
    session, player = player_session
    card = session.get(Card, 4)
    session.add(CardAlias(title="Old title", card_id=card.id))
    card.title = "Canonical title"
    result = game.import_prototype(session, player, {"currency": 10, "inventory": {"Legacy abbreviated title": 2}, "portalTickets": {}}, {"Legacy abbreviated title": "Old title"})
    assert result["ignored_titles"] == []
    assert result["state"]["inventory"][0]["title"] == "Canonical title"
    assert result["state"]["inventory"][0]["quantity"] == 2


def test_import_rejects_nonlocal_and_oversized(client, database):
    payload = {"currency": 0, "inventory": {"Page common": 10001}, "portalTickets": {}}
    assert client.post("/api/import", json=payload, headers={"Idempotency-Key": "oversized"}).status_code == 422
    with TestClient(create_app(database, seed=False), client=("203.0.113.5", 40000)) as remote:
        remote.get("/api/state")
        assert remote.post("/api/import", json={"currency": 0, "inventory": {}}, headers={"Idempotency-Key": "remote"}).status_code == 403


def test_seed_does_not_reintroduce_redirected_titles(database, tmp_path):
    path = tmp_path / "seed.json"
    path.write_text(json.dumps({"cards": [{"title": "Old title", "languages": 1, "monthly_views": 1}], "trees": []}), encoding="utf8")
    with Session(database) as session:
        seed_catalogue(session, path)
        session.commit()
        card = session.scalar(select(Card).where(Card.title == "Old title"))
        card.title = "Canonical title"
        session.commit()
        seed_catalogue(session, path)
        session.commit()
        assert session.scalar(select(Card).where(Card.title == "Old title")) is None
        assert session.scalar(select(Card).where(Card.title == "Canonical title")) is not None
