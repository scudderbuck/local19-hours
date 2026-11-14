/* v148: add Nooner or Sooner to the playlist, just before King of the Docks. Run: node test_song148.js [index.html] */
const fs=require("fs"),A=require("assert"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html"),dir=path.dirname(file);
const html=fs.readFileSync(file,"utf8"),sw=fs.readFileSync(path.join(dir,"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};
const PL=eval((js.match(/const PLAYLIST=(\[[^\]]*\]);/)||[])[1]);
t("version is v148 and the service worker cache name matches",()=>{A.strictEqual(L.APP_VERSION,"v148");A.strictEqual(L.L19_BOOT_VER,"v148");A.strictEqual(L.CACHE_VERSION,"l19hours-v148");A.ok(sw.includes('const C="l19hours-v148"'));A.ok(!sw.includes('const C="l19hours-v'+'147"'));});
t("music files are not precached",()=>{A.ok(sw.includes("pathname.includes(\"/music/\")"));A.ok(!/music\/[a-z0-9-]+\.mp3/.test(sw.match(/const C="l19hours-v148",F=\[([\s\S]*?)\];/)[1]));});
t("Nooner or Sooner sits just before King of the Docks",()=>{
  const titles=PL.map(s=>s.title);
  A.deepStrictEqual(titles,["Longshore Life","Waterfront Woman","Breakin my bones","Velvet Umbrella","Cold Coffee","Rust Coffee Shift","Bloody Thursday Sirens","Nooner or Sooner","King of the Docks"]);
  const n=PL.find(s=>s.title==="Nooner or Sooner");
  A.ok(n);A.strictEqual(n.src,"music/nooner-or-sooner.mp3");
  A.strictEqual(titles[titles.length-1],"King of the Docks");
  A.strictEqual(titles[titles.length-2],"Nooner or Sooner");
});
t("every playlist file exists",()=>{for(const s of PL)A.ok(fs.existsSync(path.join(dir,s.src)),s.src);});
t("the new mp3 is a real track and is not tagged with a personal name",()=>{
  const p=path.join(dir,"music/nooner-or-sooner.mp3");
  const st=fs.statSync(p);A.ok(st.size>1e6,st.size);
  const buf=fs.readFileSync(p);
  A.ok(!/scudderbuck/i.test(buf),"artist/tag still has scudderbuck");
  A.ok(!/daniel\s*white/i.test(buf),"personal name in file");
});
t("Next from Rust Coffee Shift goes Bloody Thursday Sirens, then Nooner or Sooner, then King of the Docks",()=>{
  let i=PL.findIndex(s=>s.title==="Rust Coffee Shift");A.ok(i>=0);
  const seq=[PL[i].title];
  for(let k=0;k<3;k++){i=(i+1)%PL.length;seq.push(PL[i].title);}
  A.deepStrictEqual(seq,["Rust Coffee Shift","Bloody Thursday Sirens","Nooner or Sooner","King of the Docks"]);
});
t("July 5 still plays only Bloody Thursday Sirens",()=>{
  A.ok(/function isBloodyThursday\(d\)\{d=d\|\|new Date\(\);return d\.getMonth\(\)===6&&d\.getDate\(\)===5;\}function musList\(d\)\{return isBloodyThursday\(d\)\?\[BT_SONG\]:PLAYLIST;\}/.test(js),"isBloodyThursday/musList unchanged");
  const isBT=d=>{d=d||new Date();return d.getMonth()===6&&d.getDate()===5;};
  const BT_SONG=PL.find(s=>s.title==="Bloody Thursday Sirens");
  const musList=d=>isBT(d)?[BT_SONG]:PL;
  const bt=new Date(2026,6,5), other=new Date(2026,6,6);
  A.ok(isBT(bt));A.ok(!isBT(other));
  A.deepStrictEqual(musList(bt).map(s=>s.title),["Bloody Thursday Sirens"]);
  A.strictEqual(musList(other).length,PL.length);
  A.ok(musList(other).some(s=>s.title==="Nooner or Sooner"));
});
t("favorite can be set to the new song and is accepted like the others",()=>{
  A.ok(L.musFavOk(PL,"music/nooner-or-sooner.mp3"));
  A.strictEqual(L.musFavIdx(PL,"music/nooner-or-sooner.mp3"),PL.length-2);
});
t("new song title and path have no personal name",()=>{
  const n=PL.find(s=>s.src==="music/nooner-or-sooner.mp3");
  A.ok(n);A.ok(!/scudder|daniel/i.test(n.title+" "+n.src));
});
console.log("\n"+pass+" passed, "+fail+" failed");process.exit(fail?1:0);
