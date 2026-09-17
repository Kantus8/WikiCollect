"""Worker scheduling regressions: failures must not starve a growing catalogue."""
import json

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.wikidex.ingestion import ArticleData, CanonicalCollision, sync_catalogue
from backend.wikidex.models import Base, Card, IngestionItem, IngestionRun
from scripts import import_catalogue as worker


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{(tmp_path / 'worker.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([Card(title=title, url=f"https://fr.wikipedia.org/wiki/{title}")
                         for title in ("A", "B")])
        session.commit()
    monkeypatch.setattr(worker, "SessionLocal", factory)
    yield factory
    engine.dispose()


def interrupted_run(factory, *, titles=None, month="2024-02", version=2):
    with factory() as session:
        cards = list(session.scalars(select(Card).order_by(Card.id)))
        cards = [card for card in cards if titles is None or card.title in titles]
        detail = {"version": version, "month": month, "policy": "log-rank-v1"}
        if version == 1:
            detail["items"] = [{"card_id": card.id, "title": card.title, "status": "pending"} for card in cards]
        run = IngestionRun(status="running", started_at=1, detail=json.dumps(detail))
        session.add(run)
        session.flush()
        if version == 2:
            session.add_all([IngestionItem(run_id=run.id, card_id=card.id,
                                          requested_title=card.title, status="pending") for card in cards])
        session.commit()
        return run.id


@pytest.mark.parametrize("version", [1, 2])
def test_latest_interrupted_full_catalogue_is_resumed(database, version):
    run_id = interrupted_run(database, version=version)
    assert worker.resumable_run("2024-02") == run_id


def test_no_interrupted_run_does_not_resume(database):
    assert worker.resumable_run("2024-02") is None


@pytest.mark.parametrize("latest_status", ["completed", "completed_with_errors", "running"])
def test_older_interruption_never_overrides_a_newer_run(database, latest_status):
    interrupted_run(database)
    with database() as session:
        # Even a newer targeted or different-month run supersedes the old pass.
        session.add(IngestionRun(status=latest_status, started_at=2,
                                 detail=json.dumps({"version": 2, "month": "2024-03"})))
        session.commit()
    assert worker.resumable_run("2024-02") is None


@pytest.mark.parametrize("version", [1, 2])
def test_partial_run_cannot_stand_in_for_a_full_worker_pass(database, version):
    interrupted_run(database, titles={"A"}, version=version)
    assert worker.resumable_run("2024-02") is None


def test_catalogue_added_after_interruption_requires_a_fresh_pass(database):
    interrupted_run(database)
    with database() as session:
        session.add(Card(title="New", url="https://fr.wikipedia.org/wiki/New", active=False))
        session.commit()
    assert worker.resumable_run("2024-02") is None


def test_previous_month_interruption_is_not_resumed(database):
    interrupted_run(database, month="2024-01")
    assert worker.resumable_run("2024-02") is None


def test_blocked_article_does_not_starve_next_full_pass_and_explicit_resume_still_works(database):
    calls = []

    class API:
        def fetch_article(self, title, month):
            calls.append(title)
            if title == "B":
                raise CanonicalCollision("Requires editorial reconciliation")
            return ArticleData(title=title, page_id=ord(title),
                               url=f"https://fr.wikipedia.org/wiki/{title}", languages=2,
                               monthly_views=10, month=month, snippet="Verified", portals=())

    first = sync_catalogue(database, API(), month="2024-02")
    assert first["status"] == "completed_with_errors"
    assert worker.resumable_run("2024-02") is None
    with database() as session:
        session.add(Card(title="C", url="https://fr.wikipedia.org/wiki/C", active=False))
        session.commit()
    second = sync_catalogue(database, API(), month="2024-02", resume_run_id=worker.resumable_run("2024-02"))
    assert second["id"] != first["id"]
    assert calls == ["A", "B", "A", "B", "C"]
    with database() as session:
        assert session.scalar(select(Card).where(Card.title == "C")).verified
    sync_catalogue(database, API(), resume_run_id=first["id"])
    assert calls[-1] == "B" and len(calls) == 6
