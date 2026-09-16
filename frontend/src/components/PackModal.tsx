import { ArrowRight, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import type { Pack } from "../types";

import { Modal } from "./Modal";
import { Sound } from "./Sound";
import { WikiCard } from "./WikiCard";

export function PackModal({
  pack,
  sound,
  onClose,
}: {
  pack: Pack;
  sound: boolean;
  onClose: () => void;
}) {
  const [revealed, setRevealed] = useState<number[]>([]);
  const complete = revealed.length === pack.cards.length;
  return (
    <Modal
      title={
        pack.cards.length === 1
          ? "Une nouvelle porte sur le savoir"
          : "Quatre pages, un nouveau chapitre"
      }
      onClose={onClose}
      wide
    >
      <Sound enabled={sound} />
      <p className="pack-instruction">
        {complete
          ? "Ces découvertes ont rejoint votre collection."
          : "Touchez une carte pour révéler votre découverte."}
      </p>
      <div
        className={"reveal-grid " + (pack.cards.length === 1 ? "single" : "")}
      >
        {pack.cards.map((c, i) => (
          <div key={i} className="reveal-slot">
            {revealed.includes(i) ? (
              <div className="revealed-card">
                <WikiCard card={c} />
                <span className="reveal-owned">
                  {c.is_duplicate
                    ? "Un nouvel exemplaire"
                    : "Une nouvelle découverte"}
                </span>
              </div>
            ) : (
              <button
                className="card-back"
                aria-label={"Révéler la carte " + (i + 1)}
                onClick={() => setRevealed((v) => [...v, i])}
              >
                <small>WIKIDEX</small>
                <span>
                  W<i>✦</i>
                </span>
                <em>LE SAVOIR SE DÉVOILE</em>
              </button>
            )}
          </div>
        ))}
      </div>
      {complete && pack.milestones.length > 0 && (
        <div className="milestone-list">
          {pack.milestones.map((m, i) => (
            <p key={i}>
              <Sparkles size={18} />
              <strong>{m.branch_title}</strong> ·{" "}
              {m.tier === "base" ? "Base" : "100 %"}
              <span>+{m.reward} Curiosité</span>
            </p>
          ))}
        </div>
      )}
      <div className="pack-actions">
        <p>
          <ShieldCheck size={14} />
          Vos cartes sont déjà sauvegardées.
        </p>
        <button
          className="primary"
          onClick={
            complete ? onClose : () => setRevealed(pack.cards.map((_, i) => i))
          }
        >
          {complete ? "Continuer l’exploration" : "Tout révéler"}
          <ArrowRight size={17} />
        </button>
      </div>
    </Modal>
  );
}
