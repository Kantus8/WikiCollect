import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.wikidex.catalogue import load_bundle, validate_bundle
from backend.wikidex.db import init_db, make_engine, begin_write
from backend.wikidex.models import Card, Tree


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
