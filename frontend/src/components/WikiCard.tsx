import { ArrowUpRight, GitBranch, Globe2 } from "lucide-react";
import { useState } from "react";
import type { Card } from "../types";
import { RARITIES, portalName } from "../types";

export function CardArt({ card }: { card: Card }) {
  const [failed, setFailed] = useState(false);
  return (
    <div className="card-art">
      {card.image_url && !failed ? (
        <img
          loading="lazy"
          src={card.image_url}
          alt=""
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="image-fallback">
          <Globe2 size={48} />
          <span>{card.title.slice(0, 1)}</span>
        </div>
      )}
      <div className="art-gradient" />
      {card.is_mother && (
        <span className="mother-mark">
          <GitBranch size={12} /> Carte mère
        </span>
      )}
    </div>
  );
}
export function WikiCard({
  card,
  onClick,
  compact = false,
}: {
  card: Card;
  onClick?: () => void;
  compact?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={"wiki-card " + card.rarity + (compact ? " compact" : "")}
    >
      <CardArt card={card} />
      <div className="card-body">
        <span className="rarity-label">
          <i />
          {RARITIES[card.rarity].label}
        </span>
        <h3>{card.title}</h3>
        <div className="card-bottom">
          <span>
            {card.portals[0]
              ? portalName(card.portals[0].title)
              : "Encyclopédie"}
          </span>
          {(card.quantity || 0) > 1 ? (
            <b>×{card.quantity}</b>
          ) : (
            <ArrowUpRight size={15} />
          )}
        </div>
      </div>
    </button>
  );
}
