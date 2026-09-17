"""Read-only Wikimedia ingestion with durable, per-article checkpoints."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import html
import json
import os
import re
import time
from typing import Callable
from urllib.parse import quote

import httpx
from sqlalchemy import delete, or_, select

from .models import Card, CardAlias, CardPortal, IngestionItem, IngestionRun, PopularitySnapshot, Portal
from .popularity import POLICY_VERSION, assign_rarities, popularity_score

ACTION_API = "https://fr.wikipedia.org/w/api.php"
PAGEVIEWS_API = "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/fr.wikipedia.org/all-access/user"
METRICS_SOURCE = "wikimedia:fr:all-access:user"
DEFAULT_USER_AGENT = "Wikidex/1.0 (+https://github.com/Kantus8/WikiCollect)"
PORTAL_CATEGORY = re.compile(r"^(?:Catégorie|Category):(Portail:.+)/Articles liés$")


class IngestionError(RuntimeError):
    pass


class InvalidArticle(IngestionError):
    """The API positively identified a missing/non-article page."""


class CanonicalCollision(IngestionError):
    """An alias resolves to another catalogue identity; never silently merge progress."""


def last_complete_month(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    year, month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
    return f"{year:04d}-{month:02d}"


def validate_month(month: str) -> tuple[str, str]:
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("Month must use YYYY-MM")
    year, number = (int(value) for value in month.split("-"))
    if number not in range(1, 13) or month < "2015-07" or month > last_complete_month():
        raise ValueError("Month must be complete and no earlier than 2015-07")
    return f"{year:04d}{number:02d}0100", f"{year:04d}{number:02d}{calendar.monthrange(year, number)[1]:02d}00"


def wikipedia_url(title: str) -> str:
    return "https://fr.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="():")


def plain_text(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]*>", " ", value)).split())


@dataclass(frozen=True)
class ArticleData:
    title: str
    page_id: int
    url: str
    languages: int
    monthly_views: int
    month: str
    snippet: str
    portals: tuple[tuple[str, str], ...] = ()
    image_url: str | None = None
    image_page_url: str | None = None
    image_artist: str | None = None
    image_license: str | None = None
    warnings: tuple[str, ...] = ()


class WikimediaClient:
    def __init__(self, *, user_agent: str | None = None, transport: httpx.BaseTransport | None = None,
                 timeout: float = 20, retries: int = 3, min_interval: float = 0.5,
                 sleep: Callable[[float], None] = time.sleep, clock: Callable[[], float] = time.monotonic):
        self.user_agent = user_agent or os.getenv("WIKIMEDIA_USER_AGENT") or DEFAULT_USER_AGENT
        self.http = httpx.Client(headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                                 timeout=timeout, transport=transport, follow_redirects=True)
        self.retries = retries
        self.min_interval = max(0.0, min_interval)
        self.sleep, self.clock = sleep, clock
        self._last_request: float | None = None
        self._portal_cache: dict[str, tuple[str, str] | None] = {}

    def close(self) -> None:
        self.http.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _request(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(self.retries + 1):
            if self._last_request is not None:
                self.sleep(max(0.0, self.min_interval - (self.clock() - self._last_request)))
            self._last_request = self.clock()
            response = None
            try:
                response = self.http.get(url, params=params)
                if response.status_code in (429, 500, 502, 503, 504):
                    raise IngestionError(f"Wikimedia HTTP {response.status_code}")
                if response.is_error:
                    raise httpx.HTTPStatusError(f"Wikimedia HTTP {response.status_code}", request=response.request, response=response)
                data = response.json()
                if not isinstance(data, dict):
                    raise ValueError("API payload is not an object")
                error = data.get("error")
                if error:
                    if error.get("code") in ("maxlag", "ratelimited", "readonly"):
                        raise IngestionError(f"MediaWiki {error['code']}")
                    raise httpx.HTTPError(f"MediaWiki {error.get('code', 'unknown')}: {error.get('info', '')}")
                return data
            except httpx.HTTPStatusError as exc:
                raise IngestionError(str(exc)) from exc
            except (httpx.TransportError, ValueError, IngestionError) as exc:
                if attempt == self.retries:
                    raise IngestionError(f"Request failed after {attempt + 1} attempts: {exc}") from exc
                delay = 2 ** attempt
                if response is not None:
                    if "maxlag" in str(exc):
                        delay = max(delay, 5)
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            try:
                                delay = max(delay, parsedate_to_datetime(retry_after).timestamp() - time.time())
                            except (ValueError, TypeError):
                                pass
                if delay > 300:
                    # Preserve upstream backpressure without blocking a local worker indefinitely.
                    raise IngestionError(f"Upstream requires retry after {delay:.0f}s; resume this run later") from exc
                self.sleep(delay)
            except httpx.HTTPError as exc:
                raise IngestionError(str(exc)) from exc
        raise AssertionError("unreachable")

    def _query(self, params: dict) -> dict:
        return self._request(ACTION_API, {"action": "query", "format": "json", "formatversion": 2,
                                           "redirects": 1, "maxlag": 5, **params})

    def _article_properties(self, title: str) -> dict:
        params = {"titles": title, "prop": "info|langlinks|categories|extracts|pageimages|pageprops",
                  "inprop": "url", "lllimit": "max", "cllimit": "max", "exintro": 1,
                  "explaintext": 1, "exchars": 1000, "piprop": "thumbnail|name", "pithumbsize": 640}
        merged: dict = {}
        languages: set[str] = set()
        categories: set[str] = set()
        continuation: dict = {}
        seen: set[str] = set()
        for _ in range(1000):
            data = self._query({**params, **continuation})
            pages = data.get("query", {}).get("pages", [])
            if len(pages) != 1:
                raise IngestionError(f"Expected exactly one result for {title!r}")
            page = pages[0]
            if "missing" in page or "invalid" in page or page.get("ns") != 0 or page.get("pageid", 0) <= 0:
                raise InvalidArticle(f"Not an existing article in namespace 0: {title}")
            if merged and page["pageid"] != merged["pageid"]:
                raise IngestionError("Page identity changed during pagination; retry")
            merged.update({key: value for key, value in page.items() if key not in ("langlinks", "categories")})
            languages.update(link["lang"] for link in page.get("langlinks", []) if "lang" in link)
            categories.update(category["title"] for category in page.get("categories", []) if "title" in category)
            if not data.get("continue"):
                merged["languages"] = len(languages | {"fr"})
                merged["categories"] = sorted(categories)
                return merged
            continuation = data["continue"]
            marker = json.dumps(continuation, sort_keys=True)
            if marker in seen:
                raise IngestionError("Repeated MediaWiki continuation")
            seen.add(marker)
        raise IngestionError("MediaWiki pagination exceeded 1000 requests")

    def _portals(self, categories: list[str]) -> tuple[tuple[str, str], ...]:
        candidates = sorted({match.group(1) for category in categories if (match := PORTAL_CATEGORY.fullmatch(category))})
        unknown = [title for title in candidates if title not in self._portal_cache]
        for offset in range(0, len(unknown), 50):
            batch = unknown[offset:offset + 50]
            data = self._query({"titles": "|".join(batch), "prop": "info", "inprop": "url"})
            query = data.get("query", {})
            aliases = {entry["from"]: entry["to"] for key in ("normalized", "redirects") for entry in query.get(key, [])}
            pages = {page["title"]: page for page in query.get("pages", [])}
            for requested in batch:
                canonical, seen = requested, set()
                while canonical in aliases and canonical not in seen:
                    seen.add(canonical)
                    canonical = aliases[canonical]
                page = pages.get(canonical)
                if page is None:
                    raise IngestionError(f"Incomplete portal validation response for {requested}")
                valid = page.get("ns") == 100 and page.get("pageid", 0) > 0 and "missing" not in page and "invalid" not in page
                self._portal_cache[requested] = (page["title"], wikipedia_url(page["title"])) if valid else None
        return tuple(sorted({self._portal_cache[title] for title in candidates if self._portal_cache[title] is not None}))

    def _pageviews(self, title: str, month: str) -> int:
        start, end = validate_month(month)
        url = f"{PAGEVIEWS_API}/{quote(title.replace(' ', '_'), safe='')}/monthly/{start}/{end}"
        data = self._request(url)
        items = data.get("items", [])
        if len(items) != 1 or str(items[0].get("timestamp", ""))[:6] != month.replace("-", ""):
            raise IngestionError(f"Missing or inconsistent pageviews for {title} ({month})")
        views = items[0].get("views")
        if not isinstance(views, int) or views < 0:
            raise IngestionError("Invalid pageviews measurement")
        return views

    def _image(self, filename: str) -> dict:
        data = self._query({"titles": "File:" + filename, "prop": "imageinfo", "iiprop": "url|extmetadata",
                            "iiextmetadatafilter": "Artist|LicenseShortName|Attribution", "iiextmetadatalanguage": "fr"})
        infos = [info for page in data.get("query", {}).get("pages", []) for info in page.get("imageinfo", [])]
        if not infos:
            raise IngestionError("Image attribution unavailable")
        info, meta = infos[0], infos[0].get("extmetadata", {})
        artist = meta.get("Attribution", meta.get("Artist", {})).get("value", "")
        return {"image_page_url": info.get("descriptionurl"), "image_artist": plain_text(artist) or None,
                "image_license": plain_text(meta.get("LicenseShortName", {}).get("value", "")) or None}

    def fetch_article(self, title: str, month: str | None = None) -> ArticleData:
        month = month or last_complete_month()
        validate_month(month)
        page = self._article_properties(title)
        portals = self._portals(page["categories"])
        views = self._pageviews(page["title"], month)
        image: dict = {}
        warnings: list[str] = []
        if page.get("pageimage") and page.get("thumbnail", {}).get("source"):
            try:
                image = self._image(page["pageimage"])
                if image.get("image_page_url") and image.get("image_license") and image.get("image_artist"):
                    image["image_url"] = page["thumbnail"]["source"]
                else:
                    warnings.append("Image hidden because attribution metadata is incomplete")
            except IngestionError as exc:
                warnings.append(str(exc))
        return ArticleData(title=page["title"], page_id=page["pageid"], url=wikipedia_url(page["title"]),
                           languages=page["languages"], monthly_views=views, month=month,
                           snippet=page.get("extract", "")[:1000], portals=portals, warnings=tuple(warnings), **image)


def apply_article(session, card: Card, article: ArticleData) -> None:
    collision = session.scalar(select(Card).where(Card.id != card.id, or_(
        Card.wikipedia_page_id == article.page_id, Card.title == article.title)))
    if collision:
        raise CanonicalCollision(f"Canonical page {article.title!r} already belongs to card {collision.id}; manual identity reconciliation required")
    if session.get(CardAlias, card.title) is None:
        session.add(CardAlias(title=card.title, card_id=card.id))
    card.title, card.wikipedia_page_id, card.url = article.title, article.page_id, article.url
    card.languages, card.monthly_views = article.languages, article.monthly_views
    card.snippet, card.image_url = article.snippet, article.image_url
    for field_name in ("image_page_url", "image_artist", "image_license"):
        if hasattr(card, field_name):
            setattr(card, field_name, getattr(article, field_name))
    card.verified, card.active = True, True
    card.metrics_source, card.updated_at = METRICS_SOURCE, time.time()
    session.execute(delete(CardPortal).where(CardPortal.card_id == card.id))
    for title, url in article.portals:
        portal = session.scalar(select(Portal).where(Portal.title == title))
        if portal is None:
            portal = Portal(title=title, url=url)
            session.add(portal)
            session.flush()
        session.add(CardPortal(card_id=card.id, portal_id=portal.id, verified=True))
    snapshot = session.scalar(select(PopularitySnapshot).where(PopularitySnapshot.card_id == card.id,
        PopularitySnapshot.month == article.month, PopularitySnapshot.source == METRICS_SOURCE))
    if snapshot is None:
        snapshot = PopularitySnapshot(card_id=card.id, month=article.month, source=METRICS_SOURCE)
        session.add(snapshot)
    snapshot.languages, snapshot.monthly_views = article.languages, article.monthly_views
    snapshot.score, snapshot.fetched_at = popularity_score(article.languages, article.monthly_views), time.time()


def _write_transaction(session) -> None:
    if session.get_bind().dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    else:
        session.begin()


def run_report(session, run_id: int) -> dict:
    run = session.get(IngestionRun, run_id)
    if run is None:
        raise ValueError(f"Unknown ingestion run: {run_id}")
    detail = json.loads(run.detail)
    if detail.get("version") == 2:
        detail["items"] = [{"card_id": item.card_id, "title": item.requested_title, "status": item.status,
                            **({"error": item.error} if item.error else {}), "warnings": item.warnings}
                           for item in session.scalars(select(IngestionItem).where(IngestionItem.run_id == run_id)
                                                       .order_by(IngestionItem.id))]
    return {"id": run.id, "status": run.status, "processed": run.processed, "failed": run.failed,
            "started_at": run.started_at, "finished_at": run.finished_at, **detail}


def sync_catalogue(session_factory, client: WikimediaClient, *, titles: list[str] | None = None,
                   month: str | None = None, resume_run_id: int | None = None,
                   on_progress: Callable[[dict], None] | None = None) -> dict:
    """Commit each card and checkpoint together; resume retries failed and pending items."""
    with session_factory() as session:
        _write_transaction(session)
        if resume_run_id is not None:
            run = session.get(IngestionRun, resume_run_id, with_for_update=True)
            if run is None:
                raise ValueError(f"Unknown ingestion run: {resume_run_id}")
            detail = json.loads(run.detail)
            if month is not None and month != detail["month"]:
                raise ValueError("A resumed run must retain its original metrics month")
            # Upgrade the first development format without losing its checkpoints.
            if detail.get("version") == 1:
                for old in detail.pop("items"):
                    session.add(IngestionItem(run_id=run.id, card_id=old["card_id"], requested_title=old["title"],
                                              status=old["status"], error=old.get("error"), warnings=old.get("warnings", [])))
                detail["version"] = 2
                run.detail = json.dumps(detail, ensure_ascii=False)
            run.status, run.finished_at = "running", None
        else:
            month = month or last_complete_month()
            validate_month(month)
            query = select(Card).order_by(Card.id)
            if titles is not None:
                query = query.where(Card.title.in_(titles))
            cards = list(session.scalars(query))
            missing = set(titles or []) - {card.title for card in cards}
            if missing:
                raise ValueError("Titles are not in the catalogue: " + ", ".join(sorted(missing)))
            detail = {"version": 2, "month": month, "policy": POLICY_VERSION}
            run = IngestionRun(started_at=time.time(), status="running", processed=0, failed=0,
                               detail=json.dumps(detail, ensure_ascii=False))
            session.add(run)
            session.flush()
            session.add_all([IngestionItem(run_id=run.id, card_id=card.id, requested_title=card.title,
                                          status="pending", warnings=[]) for card in cards])
        session.commit()
        run_id = run.id
    cursor = 0
    while True:
        # A bounded batch of checkpoint records; no DB transaction spans HTTP work.
        with session_factory() as session:
            batch = [(item.id, item.requested_title) for item in session.scalars(select(IngestionItem).where(
                IngestionItem.run_id == run_id, IngestionItem.id > cursor, IngestionItem.status != "complete")
                .order_by(IngestionItem.id).limit(100))]
        if not batch:
            break
        for item_id, requested_title in batch:
            cursor = item_id
            error = None
            try:
                article = client.fetch_article(requested_title, detail["month"])
            except IngestionError as exc:
                error = exc
            with session_factory() as session:
                _write_transaction(session)
                item = session.get(IngestionItem, item_id, with_for_update=True)
                card = session.get(Card, item.card_id, with_for_update=True)
                if card is None:
                    error = IngestionError("Catalogue identity no longer exists")
                if error is None:
                    try:
                        apply_article(session, card, article)
                    except CanonicalCollision as exc:
                        error = exc
                if isinstance(error, (InvalidArticle, CanonicalCollision)) and card is not None:
                    card.active, card.verified = False, False
                    card.updated_at = time.time()
                    session.execute(delete(CardPortal).where(CardPortal.card_id == card.id))
                was_failed = item.status in ("failed", "blocked")
                if error:
                    item.status = "blocked" if isinstance(error, CanonicalCollision) else "failed"
                    item.error = str(error)
                else:
                    item.status = "complete"
                    item.warnings, item.error = list(article.warnings), None
                run = session.get(IngestionRun, run_id, with_for_update=True)
                run.processed += int(error is None)
                run.failed += int(error is not None) - int(was_failed)
                session.commit()
                update = {"card_id": item.card_id, "title": item.requested_title, "status": item.status,
                          **({"error": item.error} if item.error else {}), "warnings": item.warnings}
            if on_progress:
                on_progress(update)
    with session_factory() as session:
        _write_transaction(session)
        # Reclassification happens once, after all durable article checkpoints.
        assign_rarities(session.scalars(select(Card).where(Card.active.is_(True))))
        run = session.get(IngestionRun, run_id)
        run.status = "completed_with_errors" if run.failed else "completed"
        run.finished_at = time.time()
        session.commit()
        return run_report(session, run_id)
