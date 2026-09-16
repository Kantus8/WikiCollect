const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(process.argv[2], 'utf8');
// Evaluate only the isolated data literal in a sandbox; never execute the application.
const match = source.match(/const WIKIPEDIA_PAGES = (\[[\s\S]*?\n        \]);/);
if (!match) throw new Error('Catalogue absent');
const pages = vm.runInNewContext(`(${match[1]})`, Object.create(null), { timeout: 500 });
const aliases = Object.fromEntries(pages.filter(p => p.title.startsWith('Article ')).map(p => [p.title, decodeURIComponent(p.url.split('/wiki/')[1]).replaceAll('_', ' ')]));
// The prototype invents separate pages for DDHC article numbers. Use actual,
// individually addressable encyclopedia pages until a source proves otherwise.
const replacements = {'Article 1er...':'Égalité devant la loi','Article 2...':'Droit naturel','Article 4...':'Liberté','Article 11...':"Liberté d'expression"};
const title = t => replacements[t] || aliases[t] || t;
const groups = [['Sciences & découvertes', 'Figures de la physique'], ['Histoire & civilisations', 'Textes fondateurs'], ['Sciences & découvertes', 'Mondes & univers']];
const trees = pages.filter(p => p.isMother).map((p, i) => ({
  id: ['einstein','ddhc','solar'][i], macro: groups[i][0], parent_set: groups[i][1], mother_title: title(p.title),
  branches: p.branches.map(b => ({id:b.id,title:b.name,description:b.description,base_pages:b.basePages.map(title),full_pages:b.fullPages.map(title)}))
}));
const cards = pages.map(p => ({title:title(p.title),legacy_title:p.title,url:p.url,languages:p.languages,monthly_views:p.monthlyViews,snippet:p.snippet,image_url:p.image.includes('placehold.co') ? null : p.image,is_mother:p.isMother,portals:p.portals.map(t=>'Portail:'+t),verified:false,metrics_source:'prototype',...(replacements[p.title]?{replaces_title:aliases[p.title],url:'https://fr.wikipedia.org/wiki/'+encodeURIComponent(title(p.title).replaceAll(' ','_')),languages:0,monthly_views:0,snippet:'Page encyclopédique individuelle consacrée à '+title(p.title)+'. Métadonnées à synchroniser avec Wikipédia.',image_url:null,portals:[],metrics_source:'editorial-pending'}:{})}));
const rights = trees[1].branches[0];
rights.title = 'Droits fondamentaux & Libertés';
rights.base_pages = ['Liberté','Droit naturel'];
rights.full_pages = ['Égalité devant la loi',"Liberté d'expression"];
fs.writeFileSync('data/catalogue.json', JSON.stringify({source:'Prototype fourni — statistiques et portails à vérifier par ingestion',cards,trees},null,2)+'\n');
