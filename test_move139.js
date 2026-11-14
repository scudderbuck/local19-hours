const fs=require("fs"),A=require("assert"),zlib=require("zlib"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html");
const html=fs.readFileSync(file,"utf8"); const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

const shift=(d,h,id)=>({id:id||("e"+d),date:d,shift:"1st",job:"Stevedore",hours:h,rate:58.85,otRate:88.28,pier:"T18"});
const srcParts={
  entries:[shift("2026-10-12",8,"a1"),shift("2026-10-13",10,"a2"),shift("2026-10-17",8,"a3")],
  stubs:[{week:"2026-10-11",gross:1200,hours:26,note:"check"}],
  startHours:4010,
  setupDone:true,
  tierMode:"auto",
  tier:"4001+",
  defPier:"T18",
  defJob:"Stevedore",
  needs:[{id:"n1",date:"2026-10-17",text:"dayside 2 lasher",pier:"T18"}],
  pegs:{v:1,boards:{Hall:{cols:10,rows:20,pegs:{}}}},
  pegsNight:{v:1,boards:{}},
  equip:{v:1,rows:[]},
  gear:{foo:{txt:"cell guides tight"}},
  ba:"2065550191",
  mileRate:0.7,
  tourDone:true,
  ratesSeen:"2026-07-04",
  pgp:[{id:"p1",date:"2026-10-14",sh:"day",note:"filed",at:"2026-10-14T18:00:00.000Z"}],
  pgpFiled:{"2026-10-11":true},
  settings:{"l19.local":"19","l19.nightList":"1","l19.holQual1300":"1"},
  appVersion:"v138",
  ratesVersion:"2026-07-04"
};

t("version is v147 and cache/boot match",()=>{
  A.strictEqual(L.APP_VERSION,"v147");
  A.strictEqual(L.CACHE_VERSION,"l19hours-v147");
  A.strictEqual(L.L19_BOOT_VER,"v147");
  A.strictEqual(L.CACHE_VERSION,"l19hours-"+L.APP_VERSION);
});

t("role: apex and www are new, github.io and localhost default old, query override works",()=>{
  A.strictEqual(L.l19MoveRole({hostname:"longshorelife.app",search:""}),"new");
  A.strictEqual(L.l19MoveRole({hostname:"www.longshorelife.app",search:""}),"new");
  A.strictEqual(L.l19MoveRole({hostname:"scudderbuck.github.io",search:"",pathname:"/local19-hours/"}),"old");
  A.strictEqual(L.l19MoveRole({hostname:"127.0.0.1",search:""}),"old");
  A.strictEqual(L.l19MoveRole({hostname:"longshorelife.app",search:"?l19site=old"}),"old");
  A.strictEqual(L.l19MoveRole({hostname:"scudderbuck.github.io",search:"?l19site=new"}),"new");
});

t("trusted origins: old github.io and loopback; reject random https",()=>{
  A.ok(L.l19TrustedMoveSource("https://scudderbuck.github.io"));
  A.ok(L.l19TrustedMoveSource("http://127.0.0.1:8765"));
  A.ok(!L.l19TrustedMoveSource("https://evil.example"));
  A.ok(!L.l19TrustedMoveSource("https://scudderbuck.github.io.evil.com"));
  A.ok(L.l19TrustedMoveDest("https://longshorelife.app"));
  A.ok(L.l19TrustedMoveDest("https://www.longshorelife.app"));
  A.ok(L.l19TrustedMoveDest("http://localhost:9000"));
  A.ok(!L.l19TrustedMoveDest("https://phishing.app"));
});

t("export then hash transfer then import is a faithful copy",()=>{
  const bak=L.l19BackupObject(srcParts);
  A.strictEqual(bak.app,"local19-hours");
  A.strictEqual(bak.version,1);
  A.strictEqual(bak.entries.length,3);
  const enc=L.l19EncodeMoveHash(bak);
  A.ok(enc.ok, enc.reason||"encode");
  A.ok(enc.hash.startsWith("#l19move="));
  const parsed=L.l19ParseMoveHash(enc.hash);
  A.strictEqual(parsed.kind,"payload");
  A.strictEqual(parsed.count,3);
  const plan=L.l19MovePlan({entries:[],stubs:[]},parsed.payload);
  A.ok(plan.ok); A.ok(plan.needsConfirm); A.ok(!plan.replaceWarning);
  const applied=L.l19MoveApply({entries:[],stubs:[]},parsed.payload,true);
  A.ok(applied.ok);
  const out=applied.parts;
  A.deepStrictEqual(out.entries.map(e=>({id:e.id,date:e.date,hours:e.hours,job:e.job,rate:e.rate})),
                    srcParts.entries.map(e=>({id:e.id,date:e.date,hours:e.hours,job:e.job,rate:e.rate})));
  A.strictEqual(out.stubs.length,1); A.strictEqual(out.stubs[0].week,"2026-10-11"); A.strictEqual(out.stubs[0].gross,1200);
  A.strictEqual(out.startHours,4010);
  A.strictEqual(out.setupDone,true);
  A.strictEqual(out.tierMode,"auto");
  A.strictEqual(out.tier,"4001+");
  A.strictEqual(out.defPier,"T18");
  A.strictEqual(out.defJob,"Stevedore");
  A.strictEqual(out.needs[0].text,"dayside 2 lasher");
  A.ok(out.pegs && out.pegs.boards);
  A.ok(out.pegsNight);
  A.ok(out.equip);
  A.ok(out.gear && out.gear.foo);
  A.strictEqual(out.ba,"2065550191");
  A.strictEqual(out.mileRate,0.7);
  A.strictEqual(out.tourDone,true);
  A.strictEqual(out.ratesSeen,"2026-07-04");
  A.strictEqual(out.pgp[0].id,"p1");
  A.strictEqual(out.pgpFiled["2026-10-11"],true);
  A.strictEqual(out.settings["l19.local"],"19");
  A.strictEqual(out.settings["l19.nightList"],"1");
  A.strictEqual(out.settings["l19.holQual1300"],"1");
});

t("unconfirmed apply does not return parts (nothing would be written)",()=>{
  const bak=L.l19BackupObject(srcParts);
  const dest={entries:[shift("2026-01-01",8,"keep")],stubs:[{week:"2026-01-03"}],startHours:9};
  const denied=L.l19MoveApply(dest,bak,false);
  A.ok(!denied.ok);
  A.strictEqual(denied.error,"not confirmed");
  A.ok(denied.plan && denied.plan.replaceWarning);
  A.strictEqual(dest.entries[0].id,"keep");
  A.strictEqual(dest.startHours,9);
});

t("already-has-data at destination requires confirmation and flags replace",()=>{
  const bak=L.l19BackupObject(srcParts);
  const dest={entries:[shift("2026-01-01",8,"old1"),shift("2026-01-02",8,"old2")],stubs:[]};
  const plan=L.l19MovePlan(dest,bak);
  A.ok(plan.ok);
  A.ok(plan.replaceWarning);
  A.strictEqual(plan.destCount,2);
  A.strictEqual(plan.incCount,3);
  const html=L.l19MoveRestoreHtml(plan);
  A.ok(html.includes("already has Longshore Life data"),html);
  A.ok(html.includes("Replace with incoming data"),html);
  A.ok(html.includes("Keep what's here"),html);
  A.ok(!html.includes("Move my data here")||html.includes("Replace with incoming data"));
});

t("empty destination still asks to confirm, without replace warning",()=>{
  const bak=L.l19BackupObject(srcParts);
  const plan=L.l19MovePlan({entries:[],stubs:[],startHours:0},bak);
  A.ok(plan.ok); A.ok(!plan.replaceWarning);
  const html=L.l19MoveRestoreHtml(plan);
  A.ok(html.includes("Move my data here"),html);
  A.ok(html.includes("24")===false); // uses incCount 3
  A.ok(html.includes("3"),html);
  A.ok(html.includes("Not now"),html);
});

t("seeded default peg/equip boards do not count as already-has-data",()=>{
  const seed={entries:[],stubs:[],startHours:0,pegs:{seeded:true,boards:{Hall:{cols:10,rows:20,pegs:{}}}},equip:{seeded:true,rows:[{id:"x"}]}};
  A.ok(!L.l19DestHasUserData(seed));
  A.ok(L.l19DestHasUserData({...seed,pegs:{seeded:true,boards:{Hall:{}},glog:[{id:1}]}}));
  A.ok(L.l19DestHasUserData({...seed,pegs:{seeded:false,boards:{Hall:{}}}}));
  A.ok(!L.l19EquipIsUserData({seeded:true,rows:[{id:"x"}]}));
  A.ok(L.l19EquipIsUserData({seeded:false,rows:[{id:"x"}]}));
});
t("dest has stubs but no shifts still counts as already-has-data",()=>{
  const plan=L.l19MovePlan({entries:[],stubs:[{week:"2026-09-05",gross:10}]},L.l19BackupObject(srcParts));
  A.ok(plan.replaceWarning);
});

t("corrupt payloads are rejected and do not produce parts",()=>{
  const cases=[
    L.l19ValidateMovePayload(null),
    L.l19ValidateMovePayload("nope"),
    L.l19ValidateMovePayload({foo:1}),
    L.l19ValidateMovePayload({entries:[{job:"Stevedore"}]}), // no date
    L.l19ParseMoveHash("#l19move="),
    L.l19ParseMoveHash("#l19move=%%%not-base64%%%"),
    L.l19ParseMoveHash("#l19move="+L.l19ToBase64Url("{not json")),
    L.l19ParseMoveHash("#l19move="+L.l19ToBase64Url(JSON.stringify({hello:"world"}))),
  ];
  for(const c of cases){
    if(c.ok) throw new Error("expected invalid, got ok");
    if(c.kind && c.kind!=="corrupt") throw new Error("expected corrupt kind, got "+c.kind);
    if(!c.error && c.ok!==false) throw new Error("missing error");
  }
  const html=L.l19MoveRestoreHtml({ok:false,error:"that transfer link is damaged or incomplete"});
  A.ok(html.includes("Couldn't move that data"),html);
  A.ok(html.includes("Nothing on this phone was changed"),html);
});

t("hash handoff without payload is a waiting state, not corrupt",()=>{
  A.strictEqual(L.l19ParseMoveHash("#l19move").kind,"handoff");
  A.strictEqual(L.l19ParseMoveHash("#l19handoff").kind,"handoff");
  A.strictEqual(L.l19ParseMoveHash("#other").kind,"none");
});

t("large backups refuse a hash and report too large (file fallback)",()=>{
  const many=[];
  for(let i=0;i<8000;i++){
    const d="2020-01-01";
    many.push({id:"big"+i,date:"2020-01-01",shift:"1st",job:"Stevedore",hours:8,rate:58.85,otRate:88.28,pier:"T18",note:"x".repeat(80),employer:"SSA Terminals",vessel:"EVER GIVEN"});
  }
  const bak=L.l19BackupObject({...srcParts,entries:many});
  const enc=L.l19EncodeMoveHash(bak);
  A.ok(!enc.ok);
  A.strictEqual(enc.reason,"too large");
  A.ok(enc.size>L.L19_HASH_MAX);
  // A legitimately sized backup still fits
  const small=L.l19EncodeMoveHash(L.l19BackupObject(srcParts));
  A.ok(small.ok);
  A.ok(small.size<L.L19_HASH_MAX);
});

t("gzip-prefixed hash decodes back to the same entries",()=>{
  const bak=L.l19BackupObject(srcParts);
  const json=JSON.stringify(bak);
  const gz=zlib.gzipSync(Buffer.from(json,"utf8"));
  const b64=Buffer.from(gz).toString("base64").replace(/\+/g,"-").replace(/\//g,"_").replace(/=+$/,"");
  const parsed=L.l19ParseMoveHash("#l19move=z."+b64);
  A.strictEqual(parsed.kind,"payload", parsed.error||"");
  A.strictEqual(parsed.count,3);
  A.strictEqual(parsed.parts.startHours,4010);
});

t("postMessage from an untrusted origin is rejected",()=>{
  const bak=L.l19BackupObject(srcParts);
  const bad=L.l19ParseMoveMessage({type:L.L19_MSG_PAYLOAD,payload:bak},"https://evil.example","new");
  A.strictEqual(bad.kind,"reject");
  const good=L.l19ParseMoveMessage({type:L.L19_MSG_PAYLOAD,payload:bak},"https://scudderbuck.github.io","new");
  A.strictEqual(good.kind,"payload");
  A.strictEqual(good.count,3);
  const ready=L.l19ParseMoveMessage({type:L.L19_MSG_READY},"https://longshorelife.app","old");
  A.strictEqual(ready.kind,"ready");
});

t("old-site notice has the move button when there is data, and a simple open link when empty",()=>{
  const has=L.l19MoveNoticeHtml({hasData:true,count:24,href:"https://longshorelife.app/"});
  A.ok(has.includes("Longshore Life has a new address"),has);
  A.ok(has.includes("Move my data to longshorelife.app"),has);
  A.ok(has.includes("24 saved shifts"),has);
  A.ok(has.includes("Home Screen"),has);
  A.ok(has.includes("photos"),has.toLowerCase());
  A.ok(has.includes("id=\"moveGo\""),has);
  const empty=L.l19MoveNoticeHtml({hasData:false,count:0,href:"https://longshorelife.app/"});
  A.ok(empty.includes("Open longshorelife.app"),empty);
  A.ok(!empty.includes("Move my data to longshorelife.app"),empty);
  const card=L.l19MoveCardHtml({role:"old",hasData:true,count:24,href:"https://longshorelife.app/"});
  A.ok(card.includes("Move my data to longshorelife.app"),card);
  A.ok(card.includes("Hide this notice"),card);
  const neu=L.l19MoveCardHtml({role:"new",hasData:false,count:0});
  A.ok(neu.includes("You're on the new address"),neu);
  A.ok(neu.includes("Home Screen"),neu);
  A.ok(neu.includes("iPhone"),neu);
});

t("notice HTML only allows http(s) hrefs and URL-encodes junk",()=>{
  const html=L.l19MoveNoticeHtml({hasData:false,href:"https://example.com/\" onclick=alert(1)"});
  A.ok(!html.includes(" onclick="),html);
  A.ok(html.includes("href=\"https://example.com/%22%20onclick=alert(1)\"" ) || html.includes("%22"),html);
  const bad=L.l19MoveNoticeHtml({hasData:false,href:"javascript:alert(1)"});
  A.ok(!bad.includes("javascript:"),bad);
  A.ok(bad.includes("https://longshorelife.app/"),bad);
});

t("existing holiday-pay helpers still present after the move code",()=>{
  A.strictEqual(typeof L.holidayPaysForWeek,"function");
  A.strictEqual(L.holPayHours("19"),8);
  A.strictEqual(L.holPayHours("52"),10);
});

console.log("\n"+pass+" passed, "+fail+" failed");
if(fail)process.exit(1);
