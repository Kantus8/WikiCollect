import { ArrowRight, BookOpen, Search } from "lucide-react";
import { useState } from "react";
import type { Card } from "../types";
import { RARITIES } from "../types";

import { WikiCard } from "../components/WikiCard";
import type { Tab } from "../types";

export function Collection({
  cards,
  onDetail,
  setTab,
}: {
  cards: Card[];
  onDetail: (c: Card) => void;
  setTab: (t: Tab) => void;
}) {
  const [search, setSearch] = useState(""),
    [rarity, setRarity] = useState("all");
  const visible = cards.filter(
    (c) =>
      c.title
        .toLocaleLowerCase("fr")
        .includes(search.toLocaleLowerCase("fr")) &&
      (rarity === "all" || c.rarity === rarity),
  );
  return (
    <>
      <div className="collection-toolbar">
        <div className="search-field">
          <Search size={18} />
          <input
            aria-label="Rechercher une carte"
            placeholder="Rechercher une découverte…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          aria-label="Filtrer par rareté"
          value={rarity}
          onChange={(e) => setRarity(e.target.value)}
        >
          <option value="all">Toutes les raretés</option>
          {Object.entries(RARITIES).map(([id, r]) => (
            <option value={id} key={id}>
              {r.label}
            </option>
          ))}
        </select>
        <span>
          {visible.length} découverte{visible.length > 1 ? "s" : ""}
        </span>
      </div>
      {visible.length ? (
        <div className="collection-grid">
          {visible.map((c) => (
            <WikiCard card={c} key={c.id} onClick={() => onDetail(c)} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <BookOpen size={40} />
          <h2>
            {cards.length
              ? "Aucune carte ne correspond"
              : "Les premières pages restent à écrire"}
          </h2>
          <p>
            {cards.length
              ? "Essayez un autre titre ou une autre rareté."
              : "Ouvrez votre premier booster pour commencer votre collection."}
          </p>
          {!cards.length && (
            <button className="primary" onClick={() => setTab("store")}>
              Découvrir la boutique
              <ArrowRight size={17} />
            </button>
          )}
        </div>
      )}
    </>
  );
}
