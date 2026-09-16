import { History } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import { number } from "../types";

export function Journal() {
  const [events, setEvents] = useState<
      {
        id: number;
        kind: string;
        created_at: number | string;
        detail: unknown;
      }[]
    >([]),
    [error, setError] = useState("");
  useEffect(() => {
    void api<{ events: typeof events }>("/history")
      .then((r) => setEvents(r.events))
      .catch((e) => setError(e.message));
  }, []);
  const labels: Record<string, string> = {
    welcome: "Bienvenue dans Wikidex",
    sale: "Doublons revendus",
    conversion: "Ticket Portail créé",
    pack: "Booster ouvert",
    portal_pack: "Portail exploré",
    sell: "Doublons revendus",
    convert: "Ticket Portail créé",
    import: "Sauvegarde importée",
    milestone: "Palier complété",
    starter: "Bienvenue dans Wikidex",
    sell_duplicates: "Doublons revendus",
    convert_duplicate: "Ticket Portail créé",
  };
  return error ? (
    <p role="alert">{error}</p>
  ) : events.length ? (
    <div className="journal-list">
      {events.map((e) => (
        <div key={e.id}>
          <span className="journal-icon">
            <History size={19} />
          </span>
          <div>
            <strong>{labels[e.kind] || e.kind}</strong>
            <p>{eventDescription(e.kind, e.detail)}</p>
          </div>
          <time>
            {new Date(
              typeof e.created_at === "number"
                ? e.created_at * 1000
                : e.created_at,
            ).toLocaleString("fr-FR")}
          </time>
        </div>
      ))}
    </div>
  ) : (
    <div className="empty-state">
      <History size={38} />
      <h2>Votre histoire commence ici</h2>
      <p>Vos prochaines découvertes seront consignées dans ce journal.</p>
    </div>
  );
}

function eventDescription(kind: string, detail: unknown): string {
  if (!detail || typeof detail !== "object")
    return typeof detail === "string" ? detail : "";
  const d = detail as Record<string, unknown>;
  if (kind === "welcome")
    return `${d.currency} Curiosité et un ticket Physique pour commencer.`;
  if (kind === "pack")
    return `${Array.isArray(d.titles) ? d.titles.join(" · ") : "Nouvelles découvertes"} — ${d.portal_id ? "1 ticket utilisé" : String(d.cost) + " Curiosité"}`;
  if (kind === "sale")
    return `${d.count} exemplaire(s) revendu(s) · +${number(Number(d.earned))} Curiosité créditée.`;
  if (kind === "conversion")
    return "Un doublon a été échangé contre un ticket de son portail.";
  if (kind === "milestone")
    return `${d.mother_title} · ${d.branch_title} · ${d.tier === "base" ? "Version de base" : "Version complète"} · +${number(Number(d.reward))} Curiosité`;
  if (kind === "import")
    return "Votre ancienne collection a rejoint votre cabinet.";
  return "Opération enregistrée dans votre partie.";
}
