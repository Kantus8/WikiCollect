"""Additive editorial bundles; new pages cannot drop before Wikimedia validates them."""
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from sqlalchemy import select

from .db import seed_catalogue
from .models import Card, CatalogueSeed, Tree


def validate_bundle(raw: dict, existing_titles: set[str]) -> dict:
    if not isinstance(raw, dict) or not isinstance(raw.get("cards"), list) or not isinstance(raw.get("trees", []), list):
        raise ValueError("Le manifeste doit contenir cards[] et éventuellement trees[].")
    cards, titles = [], set()
    for item in raw["cards"]:
        title = item.get("title") if isinstance(item, dict) else None
        if not isinstance(title, str) or not title.strip() or len(title) > 512 or title != title.strip():
            raise ValueError("Titre de carte invalide.")
        if title in titles:
            raise ValueError("Titre répété : " + title)
        titles.add(title)
        # No supplied metric, portal or verification flag is trusted.
        cards.append({"title": title, "url": "https://fr.wikipedia.org/wiki/" + quote(title.replace(" ", "_")),
                      "languages": 0, "monthly_views": 0, "snippet": "Article en attente de vérification Wikipédia.",
                      "portals": [], "active": False, "metrics_source": "editorial-pending"})
    available = titles | existing_titles
    trees, tree_ids, mothers = [], set(), set()
    for tree in raw.get("trees", []):
        if not isinstance(tree, dict):
            raise ValueError("Chaque arbre doit être un objet.")
        for field in ("id", "macro", "parent_set", "mother_title"):
            if not isinstance(tree.get(field), str) or not tree[field].strip():
                raise ValueError("Champ d’arbre manquant : " + field)
        if len(tree["id"]) > 100 or tree["id"] in tree_ids or tree["mother_title"] in mothers:
            raise ValueError("Identité d’arbre ou carte mère dupliquée.")
        if tree["mother_title"] not in available:
            raise ValueError("Carte mère absente du catalogue : " + tree["mother_title"])
        tree_ids.add(tree["id"])
        mothers.add(tree["mother_title"])
        if not isinstance(tree.get("branches"), list) or not tree["branches"]:
            raise ValueError("Un arbre doit avoir au moins une branche.")
        branch_ids, branches = set(), []
        for branch in tree["branches"]:
            if not isinstance(branch, dict):
                raise ValueError("Chaque branche doit être un objet.")
            if not isinstance(branch.get("id"), str) or not branch["id"] or len(branch["id"]) > 100 or branch["id"] in branch_ids:
                raise ValueError("Identité de branche invalide ou répétée.")
            if not isinstance(branch.get("title"), str) or not branch["title"].strip():
                raise ValueError("Titre de branche manquant.")
            branch_ids.add(branch["id"])
            seen = set()
            for field in ("base_pages", "full_pages"):
                pages = branch.get(field)
                if not isinstance(pages, list) or not pages or any(not isinstance(p, str) for p in pages):
                    raise ValueError("Chaque palier exige une liste non vide de titres individuels.")
                if len(pages) != len(set(pages)) or set(pages) & seen:
                    raise ValueError("Une page doit apparaître une seule fois dans une branche.")
                seen.update(pages)
                if tree["mother_title"] in pages or not set(pages) <= available:
                    raise ValueError("Une feuille est absente du catalogue ou identique à la carte mère.")
            branches.append({key: branch[key] for key in ("id", "title", "base_pages", "full_pages")} |
                            {"description": str(branch.get("description", ""))})
        trees.append({key: tree[key] for key in ("id", "macro", "parent_set", "mother_title")} | {"branches": branches})
    return {"cards": cards, "trees": trees}


def load_bundle(session, raw: dict) -> dict:
    existing = set(session.scalars(select(Card.title)))
    data = validate_bundle(raw, existing)
    encoded = json.dumps(data, ensure_ascii=False, sort_keys=True)
    key = "bundle:" + hashlib.sha256(encoded.encode()).hexdigest()
    if session.get(CatalogueSeed, key):
        return {"status": "already_loaded", "key": key, "added_cards": 0, "added_trees": 0}
    for tree in data["trees"]:
        mother_tree = session.scalar(select(Tree).join(Card, Card.id == Tree.mother_card_id).where(Card.title == tree["mother_title"]))
        if session.get(Tree, tree["id"]) or mother_tree:
            raise ValueError("Cet arbre ou cette mère existe déjà. Les modifications de branches récompensées nécessitent une migration explicite.")
    # Reuse the central relational importer. Temp file lives only for this call.
    with NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
        handle.write(encoded)
        path = Path(handle.name)
    try:
        seed_catalogue(session, path, seed_key=key)
    finally:
        path.unlink(missing_ok=True)
    return {"status": "loaded", "key": key, "added_cards": sum(card["title"] not in existing for card in data["cards"]),
            "added_trees": len(data["trees"])}
