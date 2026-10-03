import fs from 'fs';
const mod = await import(process.argv[2]);
const IDX = await mod.loadIndex();
const req = JSON.parse(fs.readFileSync(0,'utf8'));
const text = req.text, doc = req.doc||"x.md", ctx = req.citing_repo||null;
const cits = mod.extractCitations(text, doc, true);
const ub = cits.unbackticked||[], bt = cits.filter(x=>!x.unbackticked);
console.log(JSON.stringify({ backticked: bt.length, unbackticked: ub.length,
  path_shaped_tokens_in_raw_text: mod.countPathShaped ? mod.countPathShaped(text) : null,
  findings: [...bt,...ub].map(c=>mod.resolveCitation(IDX,c,ctx)) },null,1));
