from datetime import datetime, timezone
import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.wikidex.ingestion import (ArticleData, IngestionError, InvalidArticle, WikimediaClient,
                                       last_complete_month, sync_catalogue)
from backend.wikidex.models import Base, Card, CardPortal, IngestionItem, IngestionRun, PopularitySnapshot, Portal
from backend.wikidex.popularity import assign_rarities, popularity_score, rarity_counts


def test_default_user_agent_identifies_project_without_env(monkeypatch):
    monkeypatch.delenv("WIKIMEDIA_USER_AGENT", raising=False)
    seen = []
    with client(lambda request: (seen.append(request.headers['User-Agent']) or httpx.Response(200, json={}))) as api:
        api._request("https://fr.wikipedia.org/w/api.php")
    assert seen == ["Wikidex/1.0 (+https://github.com/Kantus8/WikiCollect)"]


def test_explicit_user_agent_takes_priority_over_environment(monkeypatch):
    monkeypatch.setenv('WIKIMEDIA_USER_AGENT', 'Configured/1.0 (https://example.org/contact)')
    with client(lambda _: httpx.Response(200, json={}), user_agent='Override/1.0 (https://example.com/contact)') as api:
        assert api.user_agent == 'Override/1.0 (https://example.com/contact)'


def client(handler, **kwargs):
    return WikimediaClient(transport=httpx.MockTransport(handler), min_interval=0, sleep=lambda _: None, **kwargs)


def page(**kwargs):
    return {"pageid": 42, "ns": 0, "title": "Albert Einstein", **kwargs}


def test_fetch_resolves_redirects_continues_interwikis_and_verifies_portals():
    calls = []

    def handler(request):
        calls.append(request)
        assert "Wikidex" in request.headers["User-Agent"]
        params = request.url.params
        if "/metrics/" in request.url.path:
            assert "/all-access/user/Albert_Einstein/monthly/2024020100/2024022900" in request.url.path
            return httpx.Response(200, json={"items": [{"timestamp": "2024020100", "views": 12345}]})
        assert params["maxlag"] == "5"
        if params["prop"] == "info":
            return httpx.Response(200, json={"query": {"pages": [
                {"title": "Portail:Physique", "pageid": 7, "ns": 100},
                {"title": "Portail:Faux", "missing": True, "ns": 100},
                {"title": "Portail:Pas un portail", "pageid": 8, "ns": 0},
            ]}})
        if "llcontinue" not in params:
            return httpx.Response(200, json={"query": {"redirects": [{"from": "Einstein", "to": "Albert Einstein"}],
                "pages": [page(langlinks=[{"lang": "en"}], extract="Physicien.", categories=[
                    {"title": "Catégorie:Portail:Physique/Articles liés"},
                    {"title": "Catégorie:Portail:Faux/Articles liés"},
                    {"title": "Catégorie:Portail:Pas un portail/Articles liés"},
                    {"title": "Catégorie:Physiciens"}])]},
                "continue": {"continue": "||", "llcontinue": "42|de"}})
        return httpx.Response(200, json={"query": {"pages": [page(langlinks=[{"lang": "de"}, {"lang": "en"}])]}})

    with client(handler) as api:
        article = api.fetch_article("Einstein", "2024-02")
    assert article.page_id == 42
    assert article.title == "Albert Einstein"
    assert article.languages == 3  # French + distinct interlanguage links.
    assert article.monthly_views == 12345
    assert article.portals == (("Portail:Physique", "https://fr.wikipedia.org/wiki/Portail:Physique"),)
    assert article.snippet == "Physicien."
    assert len(calls) == 4


@pytest.mark.parametrize("bad", [{"missing": True, "ns": 0, "title": "Nope"},
                                   {"pageid": 8, "ns": 14, "title": "Catégorie:X"},
                                   {"pageid": -1, "ns": 0, "title": "Invalid"}])
def test_non_articles_are_rejected_without_pageview_or_portal_requests(bad):
    requests = []
    with client(lambda request: (requests.append(request) or httpx.Response(200, json={"query": {"pages": [bad]}}))) as api:
        with pytest.raises(InvalidArticle):
            api.fetch_article("Nope", "2024-02")
    assert len(requests) == 1


def test_maxlag_and_rate_limit_obey_retry_after_then_succeed():
    responses = [httpx.Response(200, json={"error": {"code": "maxlag"}}),
                 httpx.Response(429, headers={"Retry-After": "8"}), httpx.Response(200, json={"ok": True})]
    delays = []
    with WikimediaClient(transport=httpx.MockTransport(lambda _: responses.pop(0)), min_interval=0, sleep=delays.append) as api:
        assert api._request("https://fr.wikipedia.org/w/api.php") == {"ok": True}
    assert 5 in delays and 8 in delays


def test_pageview_outage_is_not_a_fabricated_zero():
    with client(lambda _: httpx.Response(404, json={"detail": "Not found"})) as api:
        with pytest.raises(IngestionError, match="404"):
            api._pageviews("New article", "2024-02")


def test_malformed_image_metadata_is_a_recoverable_attribution_warning():
    payload = {"query": {"pages": [{"imageinfo": [{"extmetadata": []}]}]}}
    with client(lambda _: httpx.Response(200, json=payload)) as api:
        with pytest.raises(IngestionError, match="metadata is malformed"):
            api._image("Unexpected.svg")


def test_repeated_continuation_is_bounded():
    with client(lambda _: httpx.Response(200, json={"query": {"pages": [page()]},
                                                  "continue": {"llcontinue": "same"}})) as api:
        with pytest.raises(IngestionError, match="Repeated"):
            api._article_properties("Albert Einstein")


def test_last_month_handles_year_boundary():
    assert last_complete_month(datetime(2026, 1, 12, tzinfo=timezone.utc)) == "2025-12"


def test_rarity_is_deterministic_monotonic_and_keeps_five_pools():
    cards = [SimpleNamespace(title=str(i), languages=i * 2, monthly_views=i * 50, rarity="") for i in range(40)]
    assign_rarities(reversed(cards))
    first = [card.rarity for card in cards]
    assign_rarities(cards)
    assert [card.rarity for card in cards] == first
    assert len(set(first)) == 5 and cards[-1].rarity == "mythic" and cards[0].rarity == "common"
    assert popularity_score(40, 50) > popularity_score(20, 50)
    assert popularity_score(40, 100) > popularity_score(40, 50)
    assert rarity_counts(5) == [1, 1, 1, 1, 1]
    assert sum(rarity_counts(1001)) == 1001


@pytest.fixture
def database(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ingestion.sqlite3').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        session.add_all([Card(title=title, url="https://fr.wikipedia.org/wiki/" + title, rarity="common",
                              languages=10, monthly_views=50, metrics_source="prototype") for title in ("A", "B", "C", "D", "E")])
        session.commit()
    yield factory
    engine.dispose()


def measured(title, page_id=42):
    return ArticleData(title=title, page_id=page_id, url="https://fr.wikipedia.org/wiki/" + title,
                       languages=3, monthly_views=100, month="2024-02", snippet="Verified.",
                       portals=(("Portail:Physique", "https://fr.wikipedia.org/wiki/Portail:Physique"),))


def test_checkpoint_resume_preserves_successes_and_upserts_snapshots(database):
    calls = []

    class API:
        broken = True

        def fetch_article(self, title, month):
            calls.append(title)
            if title == "B" and self.broken:
                raise IngestionError("Temporary outage")
            return measured(title, ord(title))

    api = API()
    first = sync_catalogue(database, api, titles=["A", "B"], month="2024-02")
    assert first["processed"] == 1 and first["failed"] == 1
    with database() as session:
        a = session.scalar(select(Card).where(Card.title == "A"))
        assert a.verified and a.active and a.monthly_views == 100
        assert session.scalar(select(CardPortal).where(CardPortal.card_id == a.id)).verified
        assert not session.scalar(select(Card).where(Card.title == "B")).verified
        assert len(list(session.scalars(select(PopularitySnapshot)))) == 1
    api.broken = False
    report = sync_catalogue(database, api, resume_run_id=first["id"])
    assert calls == ["A", "B", "B"]
    assert report["status"] == "completed" and report["failed"] == 0
    sync_catalogue(database, api, titles=["A"], month="2024-02")
    with database() as session:
        assert len(list(session.scalars(select(PopularitySnapshot)))) == 2


def test_invalidation_disables_drops_without_deleting_identity(database):
    class API:
        def fetch_article(self, *args):
            raise InvalidArticle("Deleted page")

    with database() as session:
        card = session.scalar(select(Card).where(Card.title == "A"))
        card_id = card.id
        portal = Portal(title="Portail:Physique", url="https://fr.wikipedia.org/wiki/Portail:Physique")
        session.add(portal)
        session.flush()
        session.add(CardPortal(card_id=card.id, portal_id=portal.id, verified=True))
        session.commit()
    report = sync_catalogue(database, API(), titles=["A"], month="2024-02")
    with database() as session:
        card = session.get(Card, card_id)
        assert card is not None and not card.active and not card.verified
        assert not list(session.scalars(select(CardPortal)))
    assert report["failed"] == 1


def test_canonical_collision_is_reported_and_identity_not_overwritten(database):
    class API:
        def fetch_article(self, *args):
            return measured("B")

    report = sync_catalogue(database, API(), titles=["A"], month="2024-02")
    assert report["items"][0]["status"] == "blocked"
    with database() as session:
        assert len(list(session.scalars(select(Card)))) == 5
        assert not session.scalar(select(Card).where(Card.title == "A")).active
        assert session.scalar(select(Card).where(Card.title == "B")).active


def test_interrupted_run_resumes_only_pending_article(database):
    class API:
        def fetch_article(self, title, month):
            return measured(title, ord(title))

    def interrupt_after_checkpoint(item):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        sync_catalogue(database, API(), titles=["A", "B"], month="2024-02", on_progress=interrupt_after_checkpoint)
    with database() as session:
        run = session.scalar(select(IngestionRun))
        assert run.status == "running"
        assert session.scalar(select(IngestionItem).order_by(IngestionItem.id)).status == "complete"
        run_id = run.id
    report = sync_catalogue(database, API(), resume_run_id=run_id)
    assert report["processed"] == 2 and report["status"] == "completed"
