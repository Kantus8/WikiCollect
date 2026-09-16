import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Check,
  Compass,
  GitBranch,
  Globe2,
  Layers3,
  ShieldCheck,
  Sparkles,
  Ticket as TicketIcon,
} from "lucide-react";
import type { Rarity, State, Ticket } from "../types";
import { RARITIES, number, portalName } from "../types";

import type { Tab } from "../types";

export function Store({
  state,
  balance,
  busy,
  openPack,
  setTab,
}: {
  state: State;
  balance: number;
  busy: boolean;
  openPack: (ticket?: Ticket) => void;
  setTab: (tab: Tab) => void;
}) {
  const remaining = Math.max(0, Math.ceil(300 - balance)),
    percent = Math.min(100, (balance / 300) * 100);
  return (
    <>
      <section className="booster-hero">
        <div className="hero-copy">
          <div className="hero-label">
            <span />
            LE BOOSTER CLASSIQUE
          </div>
          <h2>
            Le hasard fait
            <br />
            bien les <em>connaissances.</em>
          </h2>
          <p>
            Quatre cartes. Quatre portes ouvertes sur le monde.
            <br />
            De la découverte familière à la page mythique.
          </p>
          <div className="hero-chips">
            <span>
              <Layers3 size={15} />4 cartes par booster
            </span>
            <span>
              <Globe2 size={15} />
              100 % Wikipédia
            </span>
          </div>
          <button
            className="buy-button"
            onClick={() => openPack()}
            disabled={busy || balance < 300}
          >
            <span>
              {busy ? "Ouverture…" : "Ouvrir un booster"}
              <ArrowRight size={17} />
            </span>
            <b>
              <Sparkles size={15} />
              300
            </b>
          </button>
          <div className="hero-fine">
            <ShieldCheck size={13} />
            Collection sauvegardée à chaque ouverture
          </div>
        </div>
        <div className="pack-scene" aria-hidden="true">
          <div className="orbit orbit-one" />
          <div className="orbit orbit-two" />
          <span className="scene-star star-one">✧</span>
          <span className="scene-star star-two">✦</span>
          <span className="scene-star star-three">+</span>
          <div className="pack-card back-one">
            <span>W</span>
          </div>
          <div className="pack-card back-two">
            <span>W</span>
          </div>
          <div className="pack-card front">
            <div className="pack-top">
              WIKIDEX <span>№ 001</span>
            </div>
            <div className="pack-emblem">
              <div />
              <span>W</span>
              <i>✦</i>
            </div>
            <div className="pack-caption">
              L’ENCYCLOPÉDIE
              <br />
              <strong>À COLLECTIONNER</strong>
            </div>
            <div className="pack-foot">
              4 CARTES <span>∞ DÉCOUVERTES</span>
            </div>
          </div>
          <span className="pack-caption-out">
            UNE PETITE OUVERTURE SUR UN GRAND MONDE.
          </span>
        </div>
      </section>
      <div className="store-panels">
        <section className="panel curiosity-panel">
          <div className="panel-title">
            <span className="icon-tile">
              <Sparkles size={19} />
            </span>
            <h3>La curiosité prend son temps</h3>
            <span className="live-badge">+1 / seconde</span>
          </div>
          <div className="progress-caption">
            <span>
              {remaining === 0
                ? "Votre prochain booster est prêt"
                : "Un nouveau booster dans"}
            </span>
            <strong>
              {remaining === 0 ? (
                <Check size={20} />
              ) : (
                `${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`
              )}
            </strong>
          </div>
          <div className="progress-track">
            <span style={{ width: percent + "%" }} />
          </div>
          <div className="panel-foot">
            <span>
              {number(Math.floor(Math.min(300, balance)))} / 300 Curiosité
            </span>
            <span>Réserve max. 3 000</span>
          </div>
        </section>
        <section className="panel probability-panel">
          <div className="panel-title">
            <span className="icon-tile">
              <Boxes size={19} />
            </span>
            <h3>La part du hasard</h3>
            <span className="subtle-label">PAR CARTE</span>
          </div>
          <div className="rarity-rates">
            {Object.entries(RARITIES).map(([id, r]) => (
              <div key={id} className={id}>
                <span>
                  <i />
                  {r.label}
                </span>
                <strong>
                  {String(r.rate).replace(".", ",")}
                  <small>%</small>
                </strong>
              </div>
            ))}
          </div>
          <p>Chaque tirage est indépendant. Une même carte peut revenir.</p>
        </section>
      </div>
      <section className="portal-section">
        <div className="section-heading">
          <div>
            <span className="eyebrow">CHOISISSEZ VOTRE HORIZON</span>
            <h2>
              Les portails de découverte{" "}
              <span className="count-badge">
                {state.tickets.filter((t) => t.quantity > 0).length}
              </span>
            </h2>
          </div>
          <span className="section-note">
            <TicketIcon size={15} />1 ticket = 1 carte du portail
          </span>
        </div>
        {state.tickets.filter((t) => t.quantity > 0).length ? (
          <div className="portal-grid">
            {state.tickets
              .filter((t) => t.quantity > 0)
              .map((t, i) => (
                <article className="portal-card" key={t.portal_id}>
                  <div className={"portal-symbol portal-" + (i % 3)}>
                    {i % 3 === 0 ? <Globe2 size={33} /> : <Compass size={33} />}
                  </div>
                  <div className="portal-copy">
                    <div className="eyebrow">PORTAIL WIKIPÉDIA</div>
                    <h3>{portalName(t.title)}</h3>
                    <p>Une carte garantie de ce portail.</p>
                    <small>
                      <TicketIcon size={13} />
                      {t.quantity} ticket{t.quantity > 1 ? "s" : ""} disponible
                      {t.quantity > 1 ? "s" : ""}
                    </small>
                  </div>
                  <button
                    className="round-button"
                    disabled={busy || t.available === false}
                    onClick={() => openPack(t)}
                    aria-label={"Ouvrir le portail " + portalName(t.title)}
                  >
                    <ArrowUpRight size={21} />
                  </button>
                  <p className="portal-rates">
                    {t.available === false
                      ? "Synchronisation du portail nécessaire."
                      : `Raretés adaptées aux cartes disponibles du portail${
                          t.rarity_rates
                            ? " : " +
                              Object.entries(t.rarity_rates)
                                .map(
                                  ([r, p]) =>
                                    `${RARITIES[r as Rarity].label} ${Number(p).toFixed(1)} %`,
                                )
                                .join(" · ")
                            : "."
                        }`}
                  </p>
                </article>
              ))}
          </div>
        ) : (
          <div className="empty-inline">
            <TicketIcon size={26} />
            <p>
              Vos tickets ouvrent de nouveaux horizons. Convertissez un doublon
              dans la bourse pour commencer.
            </p>
            <button className="text-button" onClick={() => setTab("market")}>
              Voir la bourse
              <ArrowRight size={16} />
            </button>
          </div>
        )}
      </section>
      <section className="discovery-strip">
        <div className="strip-art">
          <GitBranch size={39} />
        </div>
        <div>
          <span className="eyebrow">LE SAVOIR EST UNE CONSTELLATION</span>
          <h3>Une carte mère. Tout un monde à relier.</h3>
          <p>
            Débloquez un arbre, réunissez ses pages, et gagnez jusqu’à 550
            Curiosité par branche.
          </p>
        </div>
        <button className="secondary" onClick={() => setTab("trees")}>
          Explorer les arbres
          <ArrowRight size={17} />
        </button>
      </section>
    </>
  );
}
