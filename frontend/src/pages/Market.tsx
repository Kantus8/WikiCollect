import {
  ArrowRight,
  Layers3,
  Sparkles,
  Ticket as TicketIcon,
} from "lucide-react";
import { useState } from "react";
import type { Card, State } from "../types";
import { RARITIES, number, portalName } from "../types";

export function Market({
  state,
  busy,
  sell,
  convert,
  onDetail,
}: {
  state: State;
  busy: boolean;
  sell: (id?: number, all?: boolean) => void;
  convert: (card: number, portal: number) => void;
  onDetail: (c: Card) => void;
}) {
  const cards = state.inventory.filter((c) => (c.quantity || 0) > 1);
  const total = cards.reduce(
    (n, c) => n + ((c.quantity || 1) - 1) * RARITIES[c.rarity].sell,
    0,
  );
  return (
    <>
      <div className="market-summary">
        <div>
          <Layers3 size={28} />
          <span>
            <strong>{state.stats.duplicates}</strong> doublon
            {state.stats.duplicates > 1 ? "s" : ""} à échanger
          </span>
        </div>
        <div>
          <small>VALEUR TOTALE</small>
          <strong>
            <Sparkles size={18} />
            {number(total)} Curiosité
          </strong>
        </div>
        <button
          className="primary"
          disabled={busy || !cards.length}
          onClick={() => sell(undefined, true)}
        >
          Tout revendre
          <ArrowRight size={17} />
        </button>
      </div>
      <p className="market-note">
        Votre premier exemplaire est toujours conservé. Le crédit est limité à
        la place disponible dans votre réserve de 3 000 Curiosité.
      </p>
      {cards.length ? (
        <div className="market-list">
          {cards.map((c) => (
            <MarketRow
              key={c.id}
              card={c}
              busy={busy}
              sell={sell}
              convert={convert}
              onDetail={onDetail}
            />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <Layers3 size={42} />
          <h2>Chaque découverte est encore unique</h2>
          <p>
            Vos exemplaires supplémentaires apparaîtront ici.
            <br />
            Vendez-les ou transformez-les en tickets pour leurs vrais portails
            Wikipédia.
          </p>
        </div>
      )}
      <div className="sell-values">
        {Object.entries(RARITIES).map(([id, r]) => (
          <span key={id} className={id}>
            <i />
            {r.label}
            <strong>{r.sell}</strong>
            <Sparkles size={12} />
          </span>
        ))}
      </div>
    </>
  );
}
function MarketRow({
  card,
  busy,
  sell,
  convert,
  onDetail,
}: {
  card: Card;
  busy: boolean;
  sell: (id?: number, all?: boolean) => void;
  convert: (card: number, portal: number) => void;
  onDetail: (c: Card) => void;
}) {
  const portals = card.portals.filter((p) => p.verified);
  const [selected, setSelected] = useState<number>(portals[0]?.id || 0);
  const selectedPortal = portals.some((p) => p.id === selected)
    ? selected
    : portals[0]?.id || 0;
  return (
    <article className={"market-row " + card.rarity}>
      <button className="market-card-name" onClick={() => onDetail(card)}>
        <div className="small-monogram">{card.title.charAt(0)}</div>
        <span>
          <span className="rarity-label">
            <i />
            {RARITIES[card.rarity].label}
          </span>
          <strong>{card.title}</strong>
          <small>
            {(card.quantity || 1) - 1} doublon
            {(card.quantity || 1) > 2 ? "s" : ""}
          </small>
        </span>
      </button>
      <button
        className="secondary"
        disabled={busy}
        onClick={() => sell(card.id)}
      >
        Vendre 1<Sparkles size={14} />
        {RARITIES[card.rarity].sell}
      </button>
      <div className="convert-action">
        <select
          aria-label={"Portail pour " + card.title}
          value={selectedPortal}
          onChange={(e) => setSelected(Number(e.target.value))}
          disabled={!portals.length}
        >
          {!portals.length && <option value={0}>Aucun portail vérifié</option>}
          {portals.map((p) => (
            <option key={p.id} value={p.id}>
              {portalName(p.title)}
            </option>
          ))}
        </select>
        <button
          className="secondary"
          disabled={busy || !portals.length}
          onClick={() => convert(card.id, selectedPortal)}
        >
          <TicketIcon size={16} />
          Convertir 1
        </button>
      </div>
    </article>
  );
}
