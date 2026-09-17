import json

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.wikidex.catalogue import load_bundle, validate_bundle
from backend.wikidex.db import ROOT, init_db, make_engine, begin_write, seed_catalogue_regroup
from backend.wikidex.game import evaluate_milestones
from backend.wikidex.models import Branch, BranchClaim, BranchPage, Card, CatalogueSeed, GameEvent, Inventory, Player, Tree


def bundle():
    return {"cards": [{"title": title, "verified": True, "active": True, "monthly_views": 999999}
                      for title in ("Marie Curie", "Physique", "Chimie")],
            "trees": [{"id": "curie", "macro": "Sciences", "parent_set": "Chercheurs", "mother_title": "Marie Curie",
                       "branches": [{"id": "disciplines", "title": "Disciplines", "base_pages": ["Physique"], "full_pages": ["Chimie"]}]}]}


def test_bundle_is_pending_idempotent_and_relational(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'bundle.sqlite3'))
    init_db(engine, seed=False)
    with Session(engine) as session:
        begin_write(session)
        first = load_bundle(session, bundle())
        assert first['added_cards'] == 3 and first['added_trees'] == 1
        assert load_bundle(session, bundle())['status'] == 'already_loaded'
        assert all(not c.active and not c.verified and c.monthly_views == 0 for c in session.scalars(select(Card)))
        assert session.get(Tree, 'curie').mother.title == 'Marie Curie'
        session.commit()
    engine.dispose()


@pytest.mark.parametrize('bad_pages', [['Inconnue'], ['Marie Curie'], ['Physique'], []])
def test_bundle_rejects_invalid_or_overlapping_leaves(bad_pages):
    raw = bundle()
    raw['trees'][0]['branches'][0]['full_pages'] = bad_pages
    with pytest.raises(ValueError):
        validate_bundle(raw, set())


def test_shipped_catalogue_ends_on_regrouped_collections(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'expanded.sqlite3'))
    init_db(engine)
    with Session(engine) as session:
        assert session.get(CatalogueSeed, 'editorial-expansion-v1') is not None
        assert session.get(CatalogueSeed, 'editorial-regroup-v1') is not None
        assert session.query(Card).count() == 218
        # The 53 micro-collections of four pages become 17 wide collections.
        branches = list(session.scalars(select(Branch)))
        assert len(branches) == 17
        assert min(len(branch.pages) for branch in branches) == 6
        assert max(len(branch.pages) for branch in branches) == 22
        # Every leaf published by the prototype and its expansion is still placed.
        assert session.query(BranchPage).count() == 215
        assert {page.card_id for page in session.scalars(select(BranchPage))} ==                {card.id for card in session.scalars(select(Card)) if not card.is_mother}
        for branch in branches:
            assert {page.tier for page in branch.pages} == {'base', 'full'}
        # Retired branch ids are gone; the merged collections carry their pages.
        assert session.get(Branch, 'ddhc:ddhc_articles') is None
        droits = session.get(Branch, 'ddhc:ddhc_droits')
        assert droits.title == 'Droits, libertés & garanties'
        assert 'Liberté' in {page.card.title for page in droits.pages if page.tier == 'base'}
    engine.dispose()


def test_regroup_archives_old_receipts_and_pays_the_new_collection(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'migrated.sqlite3'))
    init_db(engine, ROOT / 'data' / 'catalogue.json')
    with Session(engine) as session:
        begin_write(session)
        player = Player(id='p1', session_hash='h1', currency=0, last_accrual=0, created_at=0)
        session.add(player)
        for card in session.scalars(select(Card)):
            session.add(Inventory(player_id=player.id, card_id=card.id, quantity=1))
        session.flush()
        earned = sum(item['reward'] for item in evaluate_milestones(session, player))
        assert session.query(BranchClaim).count() == 14
        session.commit()
    # A second boot brings the expansion and then the regrouping.
    init_db(engine)
    with Session(engine) as session:
        player = session.get(Player, 'p1')
        assert player.currency == earned  # Currency already earned is never taken back.
        assert session.query(BranchClaim).count() == 0
        archived = list(session.scalars(select(GameEvent).where(GameEvent.kind == 'collection_migration')))
        assert len(archived) == 3
        assert sum(len(event.detail['archived_claims']) for event in archived) == 14
    engine.dispose()


def test_regroup_refuses_a_manifest_that_drops_or_invents_a_page(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'partial.sqlite3'))
    init_db(engine, ROOT / 'data' / 'catalogue.json')
    raw = json.loads((ROOT / 'data' / 'catalogue-regroup-v1.json').read_text(encoding='utf-8'))
    path = tmp_path / 'regroup.json'
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding='utf-8')
    with Session(engine) as session:
        begin_write(session)
        # The shipped manifest covers the expansion, which this database never received.
        with pytest.raises(ValueError):
            seed_catalogue_regroup(session, path)
        session.rollback()
    engine.dispose()
