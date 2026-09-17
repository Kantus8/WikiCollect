# Contrat interne Wikidex

Backend: Python FastAPI + SQLAlchemy 2, dossier `backend/wikidex`, imports `backend.wikidex`. SQLite local / PostgreSQL via DATABASE_URL. Frontend React TypeScript Vite. API JSON snake_case. Client session opaque HttpOnly créée par GET /api/state; mutations vérifient Origin et Idempotency-Key.

## API frontend
- GET /api/state => {currency, currency_cap:3000, passive_rate:1, pack_cost:300, server_time (epoch seconds), inventory:[Card avec quantity], tickets:[{portal_id,title,quantity}], stats:{unique_cards,total_cards,duplicates,packs_opened}, catalogue:{cards,trees,verified_cards}, starter_grant:600}
- Card = {id (int),title,url,rarity ('common'|'rare'|'epic'|'legendary'|'mythic'),languages,monthly_views,snippet,image_url, is_mother,portals:[{id,title}],quantity?, verified?,metrics_source?}
- GET /api/trees => {trees:[{id,locked:true} OU {id,locked:false,macro:{id,title},parent_set:{id,title},mother:Card,collected_pages,total_pages,completed_branches,total_branches,complete,branches:[{id,title,description,total_pages,base_complete,full_complete,base_reward,full_reward,base_reward_claimed,full_reward_claimed,base_pages:[Card OU {owned:false}],full_pages:[Card OU {owned:false}]}]}]}. Aucun titre, ID carte, métadonnée des inconnues. Arbres verrouillés opaques.
- POST /api/packs {portal_id?:int} => {cards:[Card],milestones:[{branch_title,mother_title,tier,reward}],state:State}. Pack standard 4 cartes coût 300; portail 1 carte coût 1 ticket, sans coût Curiosité. Tirage acquis atomiquement avant animation. Taux standard stricts 55/28/12/4.5/.5; pack portail probabilités renormalisées parmi raretés disponibles (à afficher).
- POST /api/duplicates/sell {card_id?:int,all?:bool} => {earned,state}
- POST /api/duplicates/convert {card_id:int,portal_id:int} => {state}
- GET /api/health => état.
- GET /api/history => {events:[{id,kind,created_at,detail}]}
- POST /api/import {currency,inventory:{title:count},portalTickets:{title:count}} => {state,ignored_titles}; migration unique depuis prototype local, bornée. Documenter local seulement.
- GET /api/export => {format:"wikidex-save",version:2,currency,inventory:{title:count},portalTickets:{title:count},packs_opened,branch_claims:[{branch_id,tier,reward,claimed_at}]}. Solde actualisé côté serveur ; récompenses déjà reçues conservées.
- POST /api/import accepte aussi ce format v2 sur une partie vierge, une seule fois. `packs_opened` et `branch_claims` sont obligatoires en v2 ; reçus inconnus, dupliqués ou sans mère possédée rejetés. Restauration sans nouvelle attribution de paliers. Le JSON ne remplace pas une sauvegarde complète de la base (sessions, journal, catalogue).

## Contrat modèles ingestion
`backend/wikidex/models.py` exporte Base, Card, Portal, CardPortal, PopularitySnapshot, IngestionRun. `backend/wikidex/db.py` exporte SessionLocal, init_db(). Card: id int PK, title str unique, wikipedia_page_id int nullable unique, url str, rarity str, languages int, monthly_views int, snippet str, image_url str nullable, is_mother bool, verified bool, metrics_source str, updated_at float, active bool. Portal: id int PK,title str unique,url str. CardPortal: card_id/portal_id composite PK. PopularitySnapshot: id,card_id,month(str YYYY-MM),languages,monthly_views,score(float),source(str),fetched_at(float); unicité card_id/month/source. IngestionRun: id,started_at(float),finished_at(float nullable),status(str),processed(int),failed(int),detail(str).

Le catalogue initial `data/catalogue.json` a la forme {cards:[champs du prototype normalisés],trees:[{id,macro,parent_set,mother_title,branches:[{id,title,description,base_pages:[titles],full_pages:[titles]}]}]}. `data/catalogue-regroup-v1.json` a la forme {trees:[{id,branches:[{id,title,description,base_pages,full_pages}]}]} et remplace la totalité des branches d’un arbre publié ; il est refusé s’il ne reprend pas exactement les pages déjà présentes. Les métriques initiales sont signalées comme provenant du prototype, non vérifiées avant ingestion. L’ingestion valide les pages et portails réels et désactive les pages invalides. Les raretés sont calculées par le module de popularité ; la provenance distingue les métriques du prototype des données récupérées auprès de Wikimedia.

