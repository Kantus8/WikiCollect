export type Rarity = "common" | "rare" | "epic" | "legendary" | "mythic";
export type Portal = { id: number; title: string; verified?: boolean };
export type Card = {
  id: number;
  title: string;
  url: string;
  rarity: Rarity;
  languages: number;
  monthly_views: number;
  snippet: string;
  image_url: string | null;
  is_mother: boolean;
  portals: Portal[];
  quantity?: number;
  is_duplicate?: boolean;
  verified?: boolean;
  metrics_source?: string;
  image_artist?: string;
  image_license?: string;
  image_page_url?: string;
  parent_sets?: {
    id: number;
    title: string;
    macro: { id: number; title: string };
  }[];
};
export type Ticket = {
  portal_id: number;
  title: string;
  quantity: number;
  available?: boolean;
  rarity_rates?: Partial<Record<Rarity, number>>;
};
export type State = {
  currency: number;
  currency_cap: number;
  passive_rate: number;
  pack_cost: number;
  server_time: number;
  inventory: Card[];
  tickets: Ticket[];
  stats: {
    unique_cards: number;
    total_cards: number;
    duplicates: number;
    packs_opened: number;
  };
  catalogue: { cards: number; trees: number; verified_cards: number };
  starter_grant: number;
};
export type Leaf = Card | { owned: false };
export type Branch = {
  id: string | number;
  title: string;
  description: string;
  base_complete: boolean;
  full_complete: boolean;
  base_reward_claimed: boolean;
  full_reward_claimed: boolean;
  base_pages: Leaf[];
  full_pages: Leaf[];
};
export type Tree = {
  id: string | number;
  locked: boolean;
  macro?: { id: string | number; title: string };
  parent_set?: { id: string | number; title: string };
  mother?: Card;
  collected_pages?: number;
  total_pages?: number;
  completed_branches?: number;
  total_branches?: number;
  complete?: boolean;
  branches?: Branch[];
};
export type Milestone = {
  branch_title: string;
  mother_title: string;
  tier: string;
  reward: number;
};
export type Pack = { cards: Card[]; milestones: Milestone[]; state: State };
export const RARITIES: Record<
  Rarity,
  { label: string; rate: number; sell: number }
> = {
  common: { label: "Commune", rate: 55, sell: 30 },
  rare: { label: "Rare", rate: 28, sell: 75 },
  epic: { label: "Épique", rate: 12, sell: 150 },
  legendary: { label: "Légendaire", rate: 4.5, sell: 300 },
  mythic: { label: "Mythique", rate: 0.5, sell: 600 },
};
export const number = (n: number) =>
  new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(n);
export const portalName = (s: string) => s.replace(/^Portail:/, "");

export type Tab = "store" | "collection" | "trees" | "market" | "history";
