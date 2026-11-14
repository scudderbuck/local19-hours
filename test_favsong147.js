/* v147: favorite song plays first at start-up; ⏭ continues through the rest; stored on the phone and in backups. Run: node test_favsong147.js [index.html] */
const fs=require("fs"),A=require("assert"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html"),dir=path.dirname(file);
const html=fs.readFileSync(file,"utf8"),sw=fs.readFileSync(path.join(dir,"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};
const PL=eval((js.match(/const PLAYLIST=(\[[^\]]*\]);/)||[])[1]);
t("version is v148 and the service worker cache name matches",()=>{A.strictEqual(L.APP_VERSION,"v148");A.strictEqual(L.L19_BOOT_VER,"v148");A.strictEqual(L.CACHE_VERSION,"l19hours-v148");A.ok(sw.includes('const C="l19hours-v148"'));});
t("Waterfront Woman is in the playlist and its file exists",()=>{const w=PL.find(s=>s.title==="Waterfront Woman");A.ok(w);A.strictEqual(w.src,"music/waterfront-woman.mp3");A.ok(fs.statSync(path.join(dir,w.src)).size>1e6);});
t("every playlist file exists",()=>{for(const s of PL)A.ok(fs.existsSync(path.join(dir,s.src)),s.src);});
t("favorite index: found, missing, empty, junk",()=>{A.strictEqual(L.musFavIdx(PL,"music/waterfront-woman.mp3"),1);A.strictEqual(L.musFavIdx(PL,"music/king-of-the-docks.mp3"),PL.length-1);
  for(const f of ["","music/nope.mp3",null,undefined,"Waterfront Woman"])A.strictEqual(L.musFavIdx(PL,f),0,String(f));A.strictEqual(L.musFavIdx([],"x"),0);});
t("musFavOk only accepts a playlist file",()=>{A.ok(L.musFavOk(PL,"music/waterfront-woman.mp3"));A.ok(!L.musFavOk(PL,""));A.ok(!L.musFavOk(PL,"music/x.mp3"));A.ok(!L.musFavOk(PL,"javascript:alert(1)"));});
t("after the favorite, Next walks the rest in the usual order and wraps",()=>{let i=L.musFavIdx(PL,"music/waterfront-woman.mp3");const seq=[PL[i].title];for(let k=0;k<PL.length;k++){i=(i+1)%PL.length;seq.push(PL[i].title);}
  A.deepStrictEqual(seq,["Waterfront Woman","Breakin my bones","Velvet Umbrella","Cold Coffee","Rust Coffee Shift","Bloody Thursday Sirens","Nooner or Sooner","King of the Docks","Longshore Life","Waterfront Woman"]);
  A.ok(js.includes("function musNext(){const L=musList();if(L!==musL){musL=L;musI=0;}else musI=(musI+1)%musL.length;return musL[musI];}"),"musNext unchanged");});
t("player starts at the favorite (not on July 5)",()=>{A.ok(js.includes("musI=isBloodyThursday()?0:musFavIdx(musL,musFav());a.loop=false;a.src=musL[musI].src;"));});
t("autoplay is only tried with a favorite, music on, visible, not July 5, not already playing",()=>{const ok={fav:"music/waterfront-woman.mp3",on:true,hidden:false,bt:false,started:false};A.strictEqual(L.musAutoWanted(ok),true);
  for(const [k,v] of [["fav",""],["on",false],["hidden",true],["bt",true],["started",true]])A.strictEqual(L.musAutoWanted({...ok,[k]:v}),false,k);A.strictEqual(L.musAutoWanted(),false);});
t("blocked autoplay leaves the first-tap start in place",()=>{A.ok(js.includes('if(musStarted||(e.target&&e.target.closest&&e.target.closest("#hdMus,#hdSkip")))return;musPlay();'));A.ok(js.includes("function musPlay(){const a=musEl();if(a&&musOn()&&a.paused){musBusy(a);a.play().then(()=>{musStarted=true;},()=>{musLoading=false;musUI();});}}"));});
t("favorite key is a backed-up l19 setting",()=>{A.strictEqual(L.MUS_FAV_K,"l19.musicFav");const re=eval((js.match(/const L19_SET_SKIP=(\/[^\n]*\/);/)||[])[1]);A.ok(re instanceof RegExp);A.ok(!re.test("l19.musicFav"));});
t("controls: toast star, Settings select, set-current and clear buttons",()=>{for(const id of ['id="musFavS"','id="musFavCur"','id="musFavClr"','id="musFavV"','id="musFavT"'])A.ok(html.includes(id),id);});
t("no personal name in the v147 code",()=>{const seg=js.slice(js.indexOf("/* v147: favorite song."),js.indexOf("if(typeof document!==\"undefined\"){\nconst $"))+js.slice(js.indexOf("function musFav()"),js.indexOf("function musEscT"));A.ok(seg.length>500);A.ok(!/daniel|scudder/i.test(seg));});
console.log("\n"+pass+" passed, "+fail+" failed");process.exit(fail?1:0);
