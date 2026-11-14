/* v146: sexual-content chat filter, privacy/terms/delete-data links in settings + footer, no visible github.io / account name. Run: node test_polish146.js [index.html] */
const fs=require("fs"),A=require("assert"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html");
const html=fs.readFileSync(file,"utf8"),sw=fs.readFileSync(path.join(path.dirname(file),"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};
t("version is v147 and the service worker cache name matches",()=>{A.strictEqual(L.APP_VERSION,"v147");A.strictEqual(L.L19_BOOT_VER,"v147");A.strictEqual(L.CACHE_VERSION,"l19hours-v147");A.ok(sw.includes('const C="l19hours-v147"'));});
const BAD=["send nudes","Send NUDES pls","p0rn","check out pornhub","my onlyfans","dick pic","sent a dickpic","blowjob","blow  job","handjob","you horny?","h0rny","jerk off","jerking off","dildo","titties","nice boobs","suck my dick","show me your tits","wanna fuck","let's fuck","let’s fuck","lets fuck","sex tape","milf","orgasm","masturbating","cumshot","gangbang","hentai","sexting"];
const OK=["Lashing gang on the hatch covers","Bang the twistlocks loose","Strip the box at the CFS","Stuff and strip","Erect the gangway","Cock the boom","Stopcock is stuck","Cockpit of the crane","The escort tug is late","Hooker on the crane","Analysis of the board","Booby hatch on bay 12","Bring the balls of twine","Screw the turnbuckle tight","Sussex class ship","Scunthorpe","Horn on the tug","Hornblower","Nude-colored paint","The dock is spread out","Load the bananas","Pole and lay the lashing","Butt end of the lash bar","Bitt and bollard","Nuts and bolts","Pornography laws were in the news","Cum rate? no, the CUM tons","Penske truck","Shaft alley","Hardhat","Laid off","Gang boss","Stiff wind","Hatch cover","Screwed by the board again","Blow out the hose","Hand the job to the next gang","Jack the container off","Jerk the line","Off the dock","Fuck this weather"];
t("blocks sexual words and phrases (incl. leetspeak, spacing, curly apostrophe)",()=>{for(const x of BAD){A.ok(L.chatSexual(x),x);const c=L.chatCheck(x,[],1);A.strictEqual(c.ok,false,x);A.strictEqual(c.why,"sexual",x);A.ok(/sexual content isn/.test(c.msg));}});
t("does not catch normal waterfront talk",()=>{for(const x of OK){A.strictEqual(L.chatSexual(x),false,x);A.notStrictEqual(L.chatCheck(x,[],1).why,"sexual",x);}});
t("display hides sexual messages already on the server",()=>{const r=L.chatShow("send nudes");A.strictEqual(r.hidden,true);A.strictEqual(r.text,"Message hidden by the chat filter (sexual content).");A.strictEqual(L.chatShow("Lashing gang at 8").hidden,false);});
t("threats are still checked first, slurs still masked",()=>{A.strictEqual(L.chatCheck("i will kill you",[],1).why,"threat");A.ok(L.chatShow("i will kill you").text.includes("threat"));});
t("word list is encoded in the source (no plain wall of explicit words)",()=>{A.ok(!/pornhub|blowjob|dickpic/.test(js));A.ok(L.CHAT_SEX.includes("pornhub"));A.ok(L.CHAT_SEX.every(w=>!/^(cock|bang|screw|strip|erect|hooker|escort|balls|sex|nude|cum|ass)$/.test(w)));});
const LINKS=['href="https://longshorelife.app/privacy.html"','href="https://longshorelife.app/terms.html"','href="https://longshorelife.app/delete-data.html"'];
t("settings card links privacy, terms and delete data",()=>{const p=(html.match(/<p class="mut" id="legalLn">([\s\S]*?)<\/p>/)||[])[1]||"";for(const l of LINKS)A.ok(p.includes(l),l);A.ok(p.includes("Privacy policy"));});
t("footer links privacy, terms and delete data",()=>{const f=(html.match(/<footer id="ft">([\s\S]*?)<\/footer>/)||[])[1]||"";for(const l of LINKS)A.ok(f.includes(l),l);A.ok(/<nav id="ftl" aria-label="Legal">/.test(f));A.ok(f.includes('<small id="ftc">© 2026 Longshore Life™. All rights reserved.</small>'));});
t("links open outside the app shell safely",()=>{for(const a of html.match(/<a href="https:\/\/longshorelife\.app\/(privacy|terms|delete-data)\.html"[^>]*>/g)||[])A.ok(/target="_blank" rel="noopener"/.test(a),a);});
t("no visible github.io / account name; only the migration origin check remains",()=>{
  const body=html.replace(/^[\s\S]*?<body[^>]*>/i,"").replace(/<script[\s\S]*$/i,"");A.ok(!/scudderbuck|github\.io/i.test(body));
  const strs=[...js.matchAll(/`([^`]*)`|"([^"\n]{0,2000})"|'([^'\n]{0,2000})'/g)].map(x=>x[1]||x[2]||x[3]||"").filter(x=>/scudderbuck|github\.io/i.test(x));
  A.deepStrictEqual(strs,["scudderbuck.github.io"]);A.ok(js.includes('u.hostname==="scudderbuck.github.io"'));A.ok(!("L19_OLD_ORIGIN" in L));
  A.ok(L.l19TrustedMoveSource("https://scudderbuck.github.io"));A.ok(!L.l19TrustedMoveSource("https://scudderbuck.github.io.evil.com"));});
t("chat rules text in settings mentions sexual content",()=>{A.ok(/id="chatRules">[^<]*<b>Chat rules:<\/b>[^<]*sexual content/.test(html));});
console.log("\n"+pass+" passed, "+fail+" failed");process.exit(fail?1:0);
