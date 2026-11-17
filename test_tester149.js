/* v149: Founding Tester lifetime pass. Run: node test_tester149.js [index.html] */
const fs=require("fs"),A=require("assert"),path=require("path"),crypto=require("crypto");
const file=process.argv[2]||path.join(__dirname,"index.html"),dir=path.dirname(file);
const html=fs.readFileSync(file,"utf8"),sw=fs.readFileSync(path.join(dir,"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0;
async function t(n,f){try{await f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}}
function mem(){const s={};return{getItem(k){return Object.prototype.hasOwnProperty.call(s,k)?s[k]:null;},setItem(k,v){s[k]=String(v);},removeItem(k){delete s[k];}};}
function sha(s){return crypto.createHash("sha256").update(s,"utf8").digest("hex");}

(async()=>{
await t("version is v149 and the service worker cache name matches",()=>{A.strictEqual(L.APP_VERSION,"v149");A.strictEqual(L.L19_BOOT_VER,"v149");A.strictEqual(L.CACHE_VERSION,"l19hours-v149");A.ok(sw.includes('const C="l19hours-v149"'));A.ok(!sw.includes('const C="l19hours-v'+'148"'));});
await t("helpers and key are exported",()=>{A.strictEqual(L.FT_KEY,"l19.foundingTester");A.strictEqual(typeof L.isFoundingTester,"function");A.strictEqual(typeof L.isLifetimeFree,"function");A.strictEqual(typeof L.ftRedeem,"function");A.ok(/^[0-9a-f]{64}$/.test(L.FT_HASH));});
await t("founding tester key is a backed-up l19 setting",()=>{const re=eval((js.match(/const L19_SET_SKIP=(\/[^\n]*\/);/)||[])[1]);A.ok(re instanceof RegExp);A.ok(!re.test(L.FT_KEY));A.ok(L.FT_KEY.indexOf("l19")===0);});
await t("normalize trims and uppercases; inner text is kept",()=>{A.strictEqual(L.ftNorm("  abc  "),"ABC");A.strictEqual(L.ftNorm("Ab C"),"AB C");A.strictEqual(L.ftNorm(""),"");A.strictEqual(L.ftNorm(null),"");});
await t("ftHex matches Node SHA-256 of the normalized input",async()=>{A.strictEqual(await L.ftHex("  HeLLo  "),sha("HELLO"));A.strictEqual(await L.ftHex("xyz"),sha("XYZ"));});
await t("isFoundingTester / isLifetimeFree read a dated record and ignore junk",()=>{const st=mem();A.ok(!L.isFoundingTester(st));A.ok(!L.isLifetimeFree(st));st.setItem(L.FT_KEY,JSON.stringify({v:1,at:"2026-11-16T19:00:00.000Z"}));A.ok(L.isFoundingTester(st));A.ok(L.isLifetimeFree(st));const st2=mem();st2.setItem(L.FT_KEY,"2026-11-16T19:00:00.000Z");A.ok(L.isFoundingTester(st2));const st3=mem();st3.setItem(L.FT_KEY,"nope");A.ok(!L.isFoundingTester(st3));const st4=mem();st4.setItem(L.FT_KEY,"{}");A.ok(!L.isFoundingTester(st4));});
await t("wrong codes do not save a pass",async()=>{const st=mem();const r=await L.ftRedeem("not-the-code",st);A.strictEqual(r.ok,false);A.ok(/didn't work/i.test(r.msg));A.ok(!st.getItem(L.FT_KEY));A.ok(!L.isLifetimeFree(st));const r2=await L.ftRedeem("   ",st);A.strictEqual(r2.ok,false);A.ok(!st.getItem(L.FT_KEY));});
await t("Settings has the tester code field, error area and badge",()=>{for(const id of ['id="ftBox"','id="ftCode"','id="ftGo"','id="ftMsg"','id="ftBadge"','Enter tester code','Founding Tester ✓'])A.ok(html.includes(id),id);});
await t("paywall hook is present and no paywall exists yet",()=>{A.ok(js.includes("function isLifetimeFree(st){return isFoundingTester(st);}"));A.ok(js.includes("Future paywall / premium checks should call isLifetimeFree()"));A.ok(!/premiumRequired|isPremium\(|showPaywall/.test(js));});
await t("backup object includes an optional foundingTester field; older backups still parse",()=>{const rec=JSON.stringify({v:1,at:"2026-11-16T19:00:00.000Z"});const fresh=L.l19BackupObject({entries:[],settings:{[L.FT_KEY]:rec},foundingTester:rec,appVersion:"v149"});A.strictEqual(fresh.foundingTester,rec);A.strictEqual(fresh.settings[L.FT_KEY],rec);const old=L.l19BackupObject({entries:[{id:"e1",date:"2026-10-12",shift:"1st",job:"Stevedore",hours:8,rate:58.85,otRate:88.28,pier:"T18"}],startHours:10,appVersion:"v148"});A.ok(!old.foundingTester);const parts=L.l19PartsFromPayload(old);A.ok("foundingTester" in parts);A.strictEqual(parts.foundingTester,"");A.ok(L.validImport(old));const fromOld=L.l19PartsFromPayload({app:"local19-hours",version:1,entries:[],settings:{}});A.strictEqual(fromOld.foundingTester,"");});
await t("v149 tester-pass source has no personal name",()=>{const i=js.indexOf("/* v149: Founding Tester pass.");const j=js.indexOf("async function ftRedeem");const k=js.indexOf("function ftUI()");const l=js.indexOf("/* v139: live helpers for the domain move.");A.ok(i>=0&&j>i&&k>=0&&l>k);A.ok(!/daniel|scudder/i.test(js.slice(i,js.indexOf("const RATES_VERSION"))));A.ok(!/daniel|scudder/i.test(js.slice(k,l)));});
console.log("\n"+pass+" passed, "+fail+" failed");
process.exit(fail?1:0);
})().catch(e=>{console.error(e);process.exit(1);});
