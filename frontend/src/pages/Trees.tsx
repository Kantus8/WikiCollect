import { ArrowUpRight, Check, GitBranch, LockKeyhole } from "lucide-react";
import { useState } from "react";
import type { Branch, Card, Tree, Leaf as TreeLeaf } from "../types";

function LeafCard({
  leaf,
  onDetail,
}: {
  leaf: TreeLeaf;
  onDetail: (c: Card) => void;
}) {
  return "title" in leaf ? (
    <button
      className={"tree-leaf owned " + leaf.rarity}
      onClick={() => onDetail(leaf)}
    >
      <Check size={14} />
      <span>{leaf.title}</span>
      <ArrowUpRight size={13} />
    </button>
  ) : (
    <div className="tree-leaf unknown">
      <LockKeyhole size={13} />
      <span>???</span>
    </div>
  );
}
function BranchView({
  branch,
  onDetail,
}: {
  branch: Branch;
  onDetail: (c: Card) => void;
}) {
  return (
    <section className="branch">
      <div className="branch-head">
        <span
          className={"branch-indicator " + (branch.full_complete ? "done" : "")}
        >
          <GitBranch size={18} />
        </span>
        <h3>{branch.title}</h3>
      </div>
      <p>{branch.description}</p>
      <div className="tier-title">
        <strong>01 · Version de base</strong>
        <span className={branch.base_complete ? "completed" : ""}>
          {branch.base_complete ? (
            <>
              <Check size={13} />
              Complétée
            </>
          ) : (
            "+150 Curiosité"
          )}
        </span>
      </div>
      <div className="leaves">
        {branch.base_pages.map((c, i) => (
          <LeafCard key={i} leaf={c} onDetail={onDetail} />
        ))}
      </div>
      <div className="tier-title">
        <strong>02 · Version complète</strong>
        <span className={branch.full_complete ? "completed" : ""}>
          {branch.full_complete ? (
            <>
              <Check size={13} />
              Complétée
            </>
          ) : (
            "+400 Curiosité"
          )}
        </span>
      </div>
      <div className="leaves">
        {branch.full_pages.map((c, i) => (
          <LeafCard key={i} leaf={c} onDetail={onDetail} />
        ))}
      </div>
      <div className="branch-foot">
        {branch.full_complete
          ? "Toutes les pages sont réunies."
          : "100 % = toutes les pages de base et les pages précises."}
      </div>
    </section>
  );
}
export function Trees({
  trees,
  onDetail,
}: {
  trees: Tree[];
  onDetail: (c: Card) => void;
}) {
  const [selected, setSelected] = useState<string>("");
  const unlocked = trees.filter((t) => !t.locked);
  const tree = unlocked.find((t) => String(t.id) === selected) || unlocked[0];
  return (
    <>
      <div className="tree-toolbar">
        <span>
          <GitBranch size={18} />
          {unlocked.length} / {trees.length} arbres débloqués
        </span>
        {unlocked.length > 0 && (
          <select
            aria-label="Choisir une carte mère"
            value={String(tree.id)}
            onChange={(e) => setSelected(e.target.value)}
          >
            {unlocked.map((t) => (
              <option value={t.id} key={t.id}>
                {t.mother?.title}
              </option>
            ))}
          </select>
        )}
        <span className="fog-label">
          <LockKeyhole size={14} />
          Brouillard encyclopédique actif
        </span>
      </div>
      {tree ? (
        <>
          <div className="tree-hierarchy">
            <div className="hierarchy-level">
              <small>NIVEAU 1 · MACRO-ENSEMBLE</small>
              <strong>{tree.macro?.title}</strong>
            </div>
            <div className="vertical-line" />
            <div className="hierarchy-level parent">
              <small>NIVEAU 2 · SET PARENT D’APPARTENANCE</small>
              <strong>{tree.parent_set?.title}</strong>
            </div>
            <div className="vertical-line" />
            <div className="mother-node">
              <small>NIVEAU 3 · CARTE MÈRE FOCALE</small>
              <button onClick={() => tree.mother && onDetail(tree.mother)}>
                <span className="mother-monogram">
                  {tree.mother?.title.charAt(0)}
                </span>
                <span>
                  {tree.mother?.title}
                  <em>Arbre débloqué</em>
                </span>
                <ArrowUpRight size={18} />
              </button>
            </div>
            <div className="vertical-line" />
          </div>
          <section className={"tree-progress " + (tree.complete ? "complete" : "")}>
            <div>
              <span>{tree.complete ? "SET ACHEVÉ" : "PROGRESSION DU GRAND SET"}</span>
              <strong>
                {tree.collected_pages} / {tree.total_pages} pages
              </strong>
            </div>
            <progress value={tree.collected_pages || 0} max={tree.total_pages || 1} />
            <small>
              {tree.completed_branches} / {tree.total_branches} micro-collections terminées
              {tree.complete ? " · Collection magistrale !" : " · Chaque branche se complète en 4 cartes"}
            </small>
          </section>
          <div className="children-label">
            SETS ENFANTS · BRANCHES ET FEUILLES TERMINALES
          </div>
          <div className="branches-grid">
            {tree.branches?.map((b) => (
              <BranchView key={b.id} branch={b} onDetail={onDetail} />
            ))}
          </div>
        </>
      ) : (
        <div className="empty-state tree-empty">
          <div className="locked-tree-art">
            <div />
            <LockKeyhole size={32} />
            <span />
            <span />
            <span />
          </div>
          <h2>Un savoir encore à dévoiler</h2>
          <p>
            Obtenez une carte mère pour révéler son arbre.
            <br />
            Ses branches et ses pages restent entièrement masquées jusque-là.
          </p>
        </div>
      )}
      {trees.some((t) => t.locked) && (
        <div className="locked-trees">
          {trees
            .filter((t) => t.locked)
            .map((t) => (
              <div key={t.id}>
                <LockKeyhole size={20} />
                <span>
                  <strong>Arbre inconnu</strong>
                  <small>Carte mère non découverte</small>
                </span>
                <span>???</span>
              </div>
            ))}
        </div>
      )}
    </>
  );
}
