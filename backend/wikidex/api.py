"""Same-origin HTTP API; every mutation is one durable, idempotent transaction."""
from __future__ import annotations

from contextlib import asynccontextmanager
import ipaddress
import json
import logging
import os
import time
from pathlib import Path
from typing import Annotated, Callable, Literal

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import game
from .db import ROOT, begin_write, engine as default_engine, init_db
from .models import Card, GameEvent, IdempotencyRecord, IngestionRun, SchemaVersion

SESSION_COOKIE = "wikidex_session"
PositiveId = Annotated[int, Field(strict=True, gt=0)]
ImportCount = Annotated[int, Field(strict=True, ge=0, le=10000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PackRequest(StrictModel):
    portal_id: PositiveId | None = None


class SellRequest(StrictModel):
    card_id: PositiveId | None = None
    all: bool = False

    @model_validator(mode="after")
    def require_target(self):
        if self.all == (self.card_id is not None):
            raise ValueError("Indiquez soit card_id, soit all=true.")
        return self


class ConvertRequest(StrictModel):
    card_id: PositiveId
    portal_id: PositiveId


class SavedClaim(StrictModel):
    branch_id: Annotated[str, Field(min_length=1, max_length=256)]
    tier: Literal["base", "full"]
    reward: Annotated[float, Field(allow_inf_nan=False, ge=0, le=400)]
    claimed_at: Annotated[float, Field(allow_inf_nan=False, ge=0)]

    @model_validator(mode="after")
    def tier_reward(self):
        if self.tier == "base" and self.reward > 150:
            raise ValueError("Une récompense de base ne dépasse pas 150.")
        return self


class ImportRequest(StrictModel):
    currency: Annotated[float, Field(allow_inf_nan=False, ge=0, le=3000)]
    inventory: Annotated[dict[str, ImportCount], Field(max_length=5000)]
    portalTickets: Annotated[dict[str, ImportCount], Field(max_length=1000)] = Field(default_factory=dict)
    format: Literal["wikidex-save"] | None = None
    version: Literal[2] | None = None
    branch_claims: Annotated[list[SavedClaim], Field(max_length=10000)] = Field(default_factory=list)
    packs_opened: Annotated[int, Field(strict=True, ge=0, le=2147483647)] = 0

    @model_validator(mode="after")
    def save_format(self):
        if self.format is None and self.version is None:
            if self.branch_claims or self.packs_opened:
                raise ValueError("L’historique des récompenses exige le format Wikidex version 2.")
        elif self.format != "wikidex-save" or self.version != 2:
            raise ValueError("Format de sauvegarde Wikidex invalide.")
        elif not {"branch_claims", "packs_opened"} <= self.model_fields_set:
            raise ValueError("Sauvegarde incomplète : historique des récompenses et packs requis.")
        return self


def create_app(bind: Engine | None = None, *, seed: bool = True, import_enabled: bool | None = None, static_dir: Path | None = None) -> FastAPI:
    bind = bind or default_engine
    if import_enabled is None:
        import_enabled = os.getenv("ENABLE_LEGACY_IMPORT", "1") == "1" and bind.dialect.name == "sqlite"
    secure_cookie = os.getenv("COOKIE_SECURE", "0") == "1"
    allowed_origins = {value.rstrip("/") for value in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173").split(",") if value}
    allowed_hosts = [value.strip() for value in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",") if value.strip()]

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(bind, seed=seed)
        yield

    app = FastAPI(title="Wikidex", version="1.0.0", lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.state.engine = bind

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(game.GameError)
    async def game_error(_: Request, exc: game.GameError):
        return JSONResponse({"detail": exc.message, "code": exc.code}, status_code=exc.status)

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_: Request, exc: SQLAlchemyError):
        logging.getLogger("wikidex").exception("Database transaction failed", exc_info=exc)
        return JSONResponse({"detail": "La base est momentanément indisponible. Aucune opération partielle n’est conservée.", "code": "database_unavailable"}, status_code=503)

    def check_mutation(request: Request) -> str:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in allowed_origins:
            raise game.GameError("Origine de la requête refusée.", "origin_rejected", 403)
        if not origin and request.headers.get("sec-fetch-site") == "cross-site":
            raise game.GameError("Requête intersite refusée.", "origin_rejected", 403)
        key = request.headers.get("Idempotency-Key", "")
        if not key or len(key) > 128 or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise game.GameError("Une clé Idempotency-Key de 1 à 128 caractères est requise.", "idempotency_key_required", 400)
        return key

    def mutate(request: Request, body: BaseModel, action: Callable) -> dict:
        key = check_mutation(request)
        payload = body.model_dump()
        fingerprint = game.request_fingerprint(request.url.path, payload)
        with Session(bind, expire_on_commit=False) as session:
            begin_write(session)
            player, _ = game.get_player(session, request.cookies.get(SESSION_COOKIE))
            existing = session.get(IdempotencyRecord, (player.id, key))
            if existing:
                if existing.request_hash != fingerprint:
                    raise game.GameError("Cette clé a déjà servi pour une autre opération.", "idempotency_conflict")
                return existing.response
            game.accrue(player)
            result = action(session, player, payload)
            session.add(IdempotencyRecord(player_id=player.id, key=key, request_hash=fingerprint, response=result, created_at=time.time()))
            session.commit()
            return result

    @app.get("/api/state")
    def state(request: Request, response: Response):
        with Session(bind, expire_on_commit=False) as session:
            begin_write(session)
            player, token = game.get_player(session, request.cookies.get(SESSION_COOKIE), create=True)
            game.accrue(player)
            result = game.state_payload(session, player)
            session.commit()
        if token:
            response.set_cookie(SESSION_COOKIE, token, max_age=31536000, httponly=True, secure=secure_cookie, samesite="strict", path="/")
        return result

    @app.get("/api/trees")
    def trees(request: Request):
        with Session(bind) as session:
            begin_write(session)
            player, _ = game.get_player(session, request.cookies.get(SESSION_COOKIE))
            return game.trees_payload(session, player)

    @app.get("/api/export")
    def export_save(request: Request):
        with Session(bind, expire_on_commit=False) as session:
            begin_write(session)
            player, _ = game.get_player(session, request.cookies.get(SESSION_COOKIE))
            game.accrue(player)
            result = game.export_save(session, player)
            session.commit()
            return result

    @app.post("/api/packs")
    def packs(request: Request, body: PackRequest):
        return mutate(request, body, lambda session, player, data: game.buy_pack(session, player, data["portal_id"]))

    @app.post("/api/duplicates/sell")
    def sell(request: Request, body: SellRequest):
        return mutate(request, body, lambda session, player, data: game.sell_duplicates(session, player, data["card_id"], data["all"]))

    @app.post("/api/duplicates/convert")
    def convert(request: Request, body: ConvertRequest):
        return mutate(request, body, lambda session, player, data: game.convert_duplicate(session, player, data["card_id"], data["portal_id"]))

    @app.post("/api/import")
    def import_save(request: Request, body: ImportRequest):
        client_host = request.client.host if request.client else ""
        try:
            loopback = ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            loopback = client_host == "localhost"
        if not import_enabled or not loopback:
            raise game.GameError("La migration du prototype est disponible uniquement sur le serveur local.", "import_disabled", 403)
        path = ROOT / "data" / "catalogue.json"
        aliases = {}
        if path.exists():
            aliases = {card.get("legacy_title", card["title"]): card["title"] for card in json.loads(path.read_text(encoding="utf-8"))["cards"]}
        return mutate(request, body, lambda session, player, data: game.import_prototype(session, player, data, aliases))

    @app.get("/api/history")
    def history(request: Request):
        with Session(bind) as session:
            begin_write(session)
            player, _ = game.get_player(session, request.cookies.get(SESSION_COOKIE))
            rows = session.scalars(select(GameEvent).where(GameEvent.player_id == player.id).order_by(GameEvent.id.desc()).limit(100))
            return {"events": [{"id": event.id, "kind": event.kind, "created_at": event.created_at, "detail": event.detail} for event in rows]}

    @app.get("/api/health")
    def health():
        with Session(bind) as session:
            counts = dict(session.execute(select(Card.rarity, func.count()).where(Card.active.is_(True)).group_by(Card.rarity)).all())
            run = session.scalar(select(IngestionRun).order_by(IngestionRun.id.desc()).limit(1))
            return {"status": "ok", "schema_version": session.scalar(select(func.max(SchemaVersion.version))),
                    "catalogue_ready": all(counts.get(rarity, 0) > 0 for rarity in game.RARITY_WEIGHTS),
                    "rarity_pools": counts, "last_ingestion": {"status": run.status, "processed": run.processed,
                    "failed": run.failed, "finished_at": run.finished_at} if run else None}

    distribution = static_dir or ROOT / "frontend" / "dist"

    @app.get("/{file_path:path}", include_in_schema=False)
    def frontend(file_path: str):
        if file_path.startswith("api/"):
            return JSONResponse({"detail": "Route inconnue."}, status_code=404)
        candidate = (distribution / file_path).resolve()
        try:
            candidate.relative_to(distribution.resolve())
        except ValueError:
            return JSONResponse({"detail": "Chemin interdit."}, status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        index = distribution / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "Interface non compilée. Exécutez npm run build dans frontend, ou utilisez le serveur Vite.", "api": "/docs"}, status_code=503)

    return app


app = create_app()
