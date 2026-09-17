import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.wikidex.catalogue import load_bundle, validate_bundle
from backend.wikidex.db import init_db, make_engine, begin_write
from backend.wikidex.models import Branch, BranchPage, Card, CatalogueSeed, Tree


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


def test_shipped_expansion_adds_many_short_branches_without_rewriting_old_ones(tmp_path):
    engine = make_engine('sqlite:///' + str(tmp_path / 'expanded.sqlite3'))
    init_db(engine)
    with Session(engine) as session:
        assert session.get(CatalogueSeed, 'editorial-expansion-v1') is not None
        assert session.query(Card).count() == 218
        assert session.query(Branch).count() == 53
        new_branches = list(session.scalars(select(Branch).where(Branch.id.like('%family_origins') |
                                                                  Branch.id.like('%ddhc_drafters') |
                                                                  Branch.id.like('%solar_birth'))))
        assert len(new_branches) == 3
        assert all(len(branch.pages) == 4 for branch in new_branches)
        assert all(not page.card.active and page.card.metrics_source == 'editorial-pending'
                   for branch in new_branches for page in branch.pages)
        assert session.get(Branch, 'ddhc:ddhc_articles').title == 'Droits fondamentaux & Libertés'
    engine.dispose()
