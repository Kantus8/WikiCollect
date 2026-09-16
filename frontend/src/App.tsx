import {
  BookOpen,
  Check,
  ChevronRight,
  Compass,
  Download,
  ExternalLink,
  GitBranch,
  Globe2,
  History,
  Layers3,
  Leaf,
  RefreshCw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Ticket as TicketIcon,
  Upload,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Card, Pack, State, Ticket, Tree } from "./types";
import { RARITIES, number, portalName } from "./types";

import { Modal } from "./components/Modal";
import { PackModal } from "./components/PackModal";
import { CardArt } from "./components/WikiCard";
import { Collection } from "./pages/Collection";
import { Journal } from "./pages/Journal";
import { Market } from "./pages/Market";
import { Store } from "./pages/Store";
import { Trees } from "./pages/Trees";
import type { Tab } from "./types";
const tabs = [
  { id: "store", label: "Boutique", icon: Compass },
  { id: "collection", label: "Mon classeur", icon: BookOpen },
  { id: "trees", label: "Arbres du savoir", icon: GitBranch },
  { id: "market", label: "Bourse aux doublons", icon: Layers3 },
  { id: "history", label: "Journal", icon: History },
] as const;
const tabTitles: Record<Tab, string> = {
  store: "Le comptoir des découvertes",
  collection: "Votre cabinet de curiosités",
  trees: "Les liens qui font le savoir",
  market: "Une nouvelle vie pour vos doublons",
  history: "Le fil de vos découvertes",
};

export default function App() {
  const [state, setState] = useState<State | null>(null),
    [tab, setTab] = useState<Tab>("store"),
    [trees, setTrees] = useState<Tree[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [detail, setDetail] = useState<Card | null>(null),
    [pack, setPack] = useState<Pack | null>(null),
    [settings, setSettings] = useState(false),
    [sound, setSound] = useState(
      () => localStorage.getItem("wikidex_sound") === "true",
    ),
    [now, setNow] = useState(Date.now()),
    [received, setReceived] = useState(Date.now());
  const busyRef = useRef(false),
    latestState = useRef(0);
  const accept = useCallback((value: State) => {
    if (value.server_time < latestState.current) return;
    latestState.current = value.server_time;
    setState(value);
    setReceived(Date.now());
  }, []);
  const refresh = useCallback(async () => {
    const s = await api<State>("/state");
    accept(s);
  }, [accept]);
  const refreshTrees = useCallback(async () => {
    setTrees((await api<{ trees: Tree[] }>("/trees")).trees);
  }, []);
  useEffect(() => {
    void refresh()
      .then(refreshTrees)
      .catch((e) => setError(e.message));
    const tick = setInterval(() => setNow(Date.now()), 1000);
    const sync = setInterval(() => {
      if (!busyRef.current) void refresh().catch(() => {});
    }, 15000);
    return () => {
      clearInterval(tick);
      clearInterval(sync);
    };
  }, [refresh, refreshTrees]);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(""), 6000);
    return () => clearTimeout(timer);
  }, [notice]);
  async function mutate<T extends { state: State }>(
    path: string,
    body: unknown,
    onSuccess?: (result: T) => void,
  ) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<T>(path, body);
      accept(result.state);
      onSuccess?.(result);
      await refreshTrees();
    } catch (e) {
      setError((e as Error).message);
      void refresh().catch(() => {});
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  const balance = state
    ? Math.min(
        state.currency_cap,
        state.currency +
          Math.max(0, (now - received) / 1000) * state.passive_rate,
      )
    : 0;
  const closeDetail = useCallback(() => setDetail(null), []),
    closePack = useCallback(() => setPack(null), []),
    closeSettings = useCallback(() => setSettings(false), []);
  const openPack = (portal?: Ticket) =>
    void mutate<Pack>(
      "/packs",
      portal ? { portal_id: portal.portal_id } : {},
      setPack,
    );
  function exportSave() {
    if (!state) return;
    const save = {
      version: 1,
      currency: Math.floor(balance),
      inventory: Object.fromEntries(
        state.inventory.map((c) => [c.title, c.quantity]),
      ),
      portalTickets: Object.fromEntries(
        state.tickets.map((t) => [portalName(t.title), t.quantity]),
      ),
    };
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(save, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "wikidex-collection.json";
    a.click();
    URL.revokeObjectURL(url);
  }
  async function importSave(raw: string) {
    try {
      const parsed = JSON.parse(raw);
      const data = {
        currency: parsed.currency,
        inventory: parsed.inventory,
        portalTickets: parsed.portalTickets || {},
      };
      await mutate<{ state: State; ignored_titles: string[] }>(
        "/import",
        data,
        (result) => {
          setNotice(
            "Sauvegarde importée." +
              (result.ignored_titles.length
                ? ` ${result.ignored_titles.length} article(s) inconnu(s) ignoré(s).`
                : ""),
          );
          setSettings(false);
        },
      );
    } catch {
      setError("Ce fichier ne contient pas une sauvegarde JSON valide.");
    }
  }
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("store");
          }}
        >
          <span className="brand-symbol">
            W<span>✦</span>
          </span>
          <span>
            Wikidex<small>LE SAVOIR SE COLLECTIONNE</small>
          </span>
        </a>
        <div className="sidebar-label">VOTRE EXPLORATION</div>
        <nav>
          {tabs.map((t) => (
            <button
              key={t.id}
              className={"nav-item " + (tab === t.id ? "active" : "")}
              onClick={() => setTab(t.id)}
            >
              <t.icon size={19} />
              <span>{t.label}</span>
              {t.id === "collection" && (
                <small>{state?.stats.unique_cards || 0}</small>
              )}
              {t.id === "market" && !!state?.stats.duplicates && (
                <small>{state.stats.duplicates}</small>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="field-note">
            <div>
              <Leaf size={17} />
              <span>LA CURIOSITÉ GRANDIT</span>
            </div>
            <p>
              Le prochain savoir vous attend.
              <br />
              Laissez le temps faire son œuvre.
            </p>
            <strong>
              +1 <small>Curiosité / seconde</small>
            </strong>
          </div>
          <button
            className="nav-item settings"
            onClick={() => setSettings(true)}
          >
            <Settings2 size={18} />
            Préférences & sauvegarde
          </button>
          <div className="local-status">
            <i /> Sauvegarde locale · sur cet appareil
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            Votre espace <ChevronRight size={14} />
            <strong>{tabs.find((t) => t.id === tab)?.label}</strong>
          </div>
          <div className="top-resources">
            <span className="ticket-count" title="Tickets Portail">
              <TicketIcon size={17} />
              {state?.tickets.reduce((n, t) => n + t.quantity, 0) || 0}
              <span>
                ticket
                {(state?.tickets.reduce((n, t) => n + t.quantity, 0) || 0) > 1
                  ? "s"
                  : ""}
              </span>
            </span>
            <div className="currency">
              <Sparkles size={17} />
              <strong>{number(Math.floor(balance))}</strong>
              <span>/ 3 000</span>
              <i>+1/s</i>
            </div>
            <button
              className="avatar"
              onClick={() => setSettings(true)}
              aria-label="Préférences du collectionneur"
            >
              W
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                <span />
                L’ENCYCLOPÉDIE, AUTREMENT
              </div>
              <h1>{tabTitles[tab]}</h1>
              <p>
                {tab === "store"
                  ? "Ouvrez un booster. Découvrez un article. Reliez les connaissances."
                  : tab === "collection"
                    ? "Chaque carte est une vraie page Wikipédia. Chaque découverte vous appartient."
                    : tab === "trees"
                      ? "Des grandes familles aux détails qui les composent."
                      : tab === "market"
                        ? "Échangez vos exemplaires en trop contre de nouvelles découvertes."
                        : "Vos acquisitions et échanges, conservés dans votre base locale."}
              </p>
            </div>
            <div className="edition-tag">
              <span>COLLECTION</span>
              <strong>Vol. 01</strong>
            </div>
          </div>
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              <button
                onClick={() => {
                  setError("");
                  void refresh().catch((e) => setError(e.message));
                }}
              >
                <RefreshCw size={15} />
                Réessayer
              </button>
            </div>
          )}
          {!state ? (
            <div className="loading">
              <Compass size={32} />
              <p>Ouverture de votre cabinet de curiosités…</p>
            </div>
          ) : (
            <>
              {state.catalogue.verified_cards < state.catalogue.cards && (
                <div className="catalogue-note">
                  <ShieldCheck size={16} />
                  <span>
                    Catalogue initial du prototype ·{" "}
                    {state.catalogue.verified_cards}/{state.catalogue.cards}{" "}
                    pages synchronisées. Les statistiques sont provisoires ; les
                    portails attendent leur vérification Wikipédia.
                  </span>
                </div>
              )}
              {tab === "store" && (
                <Store
                  state={state}
                  balance={balance}
                  busy={busy}
                  openPack={openPack}
                  setTab={setTab}
                />
              )}
              {tab === "collection" && (
                <Collection
                  cards={state.inventory}
                  onDetail={setDetail}
                  setTab={setTab}
                />
              )}
              {tab === "trees" && <Trees trees={trees} onDetail={setDetail} />}
              {tab === "market" && (
                <Market
                  state={state}
                  busy={busy}
                  onDetail={setDetail}
                  sell={(id, all) =>
                    void mutate<{ state: State; earned: number }>(
                      "/duplicates/sell",
                      all ? { all: true } : { card_id: id },
                      (r) =>
                        setNotice(
                          `Doublons revendus : +${number(r.earned)} Curiosité créditée.`,
                        ),
                    )
                  }
                  convert={(card_id, portal_id) =>
                    void mutate(
                      "/duplicates/convert",
                      { card_id, portal_id },
                      () =>
                        setNotice(
                          "Votre ticket Portail est prêt dans la boutique.",
                        ),
                    )
                  }
                />
              )}
              {tab === "history" && <Journal />}
            </>
          )}
          <footer>
            <span>
              <span className="mini-w">W</span> Un monde de connaissances à
              découvrir.
            </span>
            <span>
              Articles Wikipédia ·{" "}
              <a
                href="https://creativecommons.org/licenses/by-sa/4.0/deed.fr"
                target="_blank"
                rel="noreferrer"
              >
                CC BY-SA
              </a>
            </span>
          </footer>
        </main>
      </div>
      {notice && (
        <div className="toast" role="status">
          <Check size={18} />
          {notice}
          <button
            aria-label="Fermer la notification"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}
      {detail && (
        <Modal title="Une page, une découverte" onClose={closeDetail}>
          <div className={"detail " + detail.rarity}>
            <CardArt card={detail} />
            <span className="rarity-label">
              <i />
              {RARITIES[detail.rarity].label}
            </span>
            <h2>{detail.title}</h2>
            <p>{detail.snippet}</p>
            <div className="detail-stats">
              <span>
                <Globe2 size={18} />
                <b>{number(detail.languages)}</b> langues
              </span>
              <span>
                <BookOpen size={18} />
                <b>{number(detail.monthly_views)}</b> vues / mois
              </span>
            </div>
            <div className="tags">
              {detail.portals.map((p) => (
                <span key={p.id}>
                  {portalName(p.title)}
                  {p.verified && <Check size={12} />}
                </span>
              ))}
            </div>
            <div className="membership">
              <h4>Sets parents d’appartenance</h4>
              {detail.parent_sets?.map((s) => (
                <p key={s.id}>
                  {s.macro.title} → {s.title}
                </p>
              ))}
              <p className="muted">
                Seules les appartenances aux arbres débloqués sont visibles.
              </p>
              <h4>Sets enfants de cette carte mère</h4>
              {trees
                .filter((t) => t.mother?.id === detail.id)
                .flatMap((t) => t.branches || [])
                .map((b) => (
                  <p key={b.id}>{b.title}</p>
                ))}
              {!detail.is_mother && (
                <p className="muted">
                  Cette carte ne possède pas d’arbre enfant.
                </p>
              )}
            </div>
            <p className="source-note">
              {detail.verified
                ? "Article vérifié sur Wikipédia."
                : "Données initiales du prototype, en attente de synchronisation."}{" "}
              {detail.metrics_source === "prototype"
                ? "Les statistiques initiales ne sont pas des mesures récentes."
                : ""}
            </p>
            {detail.image_page_url && (
              <p className="source-note">
                <a
                  href={detail.image_page_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Source de l’image
                </a>{" "}
                · {detail.image_artist} · {detail.image_license}
              </p>
            )}
            <a
              className="primary"
              href={detail.url}
              target="_blank"
              rel="noreferrer"
            >
              Lire l’article sur Wikipédia
              <ExternalLink size={16} />
            </a>
          </div>
        </Modal>
      )}
      {pack && <PackModal pack={pack} sound={sound} onClose={closePack} />}
      {settings && (
        <Modal title="Votre cabinet, vos préférences" onClose={closeSettings}>
          <div className="settings-content">
            {error && (
              <div className="error-banner" role="alert">
                {error}
              </div>
            )}
            <button
              className="setting-row"
              onClick={() =>
                setSound((v) => {
                  localStorage.setItem("wikidex_sound", String(!v));
                  return !v;
                })
              }
            >
              {sound ? <Volume2 /> : <VolumeX />}
              <span>Son à l’ouverture des boosters</span>
              <strong>{sound ? "Activé" : "Désactivé"}</strong>
            </button>
            <h3>Votre sauvegarde</h3>
            <p>
              La collection et la Curiosité sont enregistrées dans la base de
              données sur cet appareil. Votre navigateur conserve uniquement la
              clé de votre partie.
            </p>
            <button className="secondary" onClick={exportSave}>
              <Download size={17} />
              Exporter ma collection en JSON
            </button>
            <h3>Importer le prototype</h3>
            <p>
              L’import est possible une seule fois, sur une partie vierge.
              Exportez la valeur <code>wikidex_v4_state</code> du stockage local
              de l’ancien prototype dans un fichier JSON.
            </p>
            <label className="secondary file-upload">
              <Upload size={17} />
              Choisir une sauvegarde JSON
              <input
                type="file"
                accept="application/json,.json"
                disabled={busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void file.text().then(importSave);
                }}
              />
            </label>
            {localStorage.getItem("wikidex_v4_state") && (
              <button
                className="secondary"
                disabled={busy}
                onClick={() =>
                  void importSave(localStorage.getItem("wikidex_v4_state")!)
                }
              >
                Importer la sauvegarde détectée
              </button>
            )}
            <div className="info-note">
              <ShieldCheck size={20} />
              <span>
                Les règles sont calculées par le serveur local. Aucun compte
                externe n’est nécessaire.
              </span>
            </div>
            <h3>État du catalogue</h3>
            <p>
              {state?.catalogue.verified_cards || 0} /{" "}
              {state?.catalogue.cards || 0} pages vérifiées. La synchronisation
              Wikimedia se lance avec <code>scripts/import_catalogue.py</code>.
              Les statistiques ne modifient jamais le taux passif.
            </p>
          </div>
        </Modal>
      )}
    </div>
  );
}
