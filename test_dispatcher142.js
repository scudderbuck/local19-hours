/* v142: 0331 Dispatcher at Skill 3 pay (Daniel, Nov 13 2026). Source: PMA Occupation Codes and Rates 2026
   (pmpr1007, wk ending 10-Jul-2026), group D01 JPLRC Rates, 0331 L/S DISPATCHERS, WA row = Skill III rate. */
const fs=require("fs"),A=require("assert"),path=require("path");
const file=process.argv[2]||path.join(__dirname,"index.html");
const html=fs.readFileSync(file,"utf8");
const sw=fs.readFileSync(path.join(path.dirname(file),"sw.js"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0; const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

t("version is v144 and the service worker cache name matches",()=>{
  A.strictEqual(L.L19_BOOT_VER,"v144");
  A.ok(html.includes('const APP_VERSION="v144",CACHE_VERSION="l19hours-v144"'));
  A.ok(sw.includes('const C="l19hours-v144"'));
});
t("0331 is in the PMA Skill 3 group (tagged WA) and nowhere else",()=>{
  A.ok(L.JOBS["Skill 3"].some(([c,n])=>c==="0331"&&n==="L/S Dispatcher (WA)"));
  for(const g of Object.keys(L.JOBS)) if(g!=="Skill 3") A.ok(!L.JOBS[g].some(([c])=>c==="0331"),g);
  A.strictEqual(L.pmaName("0331"),"L/S Dispatcher (WA)");
});
t("named Dispatcher job: code 0331, Skill 3, user source, note cites Daniel",()=>{
  const j=L.SEATTLE_JOBS.find(r=>r[0]==="Dispatcher");
  A.ok(j); A.strictEqual(j[1],"0331"); A.strictEqual(j[2],"Skill 3"); A.strictEqual(j[3],"user");
  A.ok(/0331 per Daniel/.test(j[4]) && /Skill 3 rates/.test(j[4]));
});
t("Dispatcher pays exactly the Skill 3 rates on every shift and tier (2026-27)",()=>{
  for(const sh of ["1st","2nd","3rd"]) for(const tier of ["4001+","2001-4000","1001-2000","0-1000"]){
    const a=L.defaultRates("Dispatcher",sh,tier,"2026-11-13"), b=L.defaultRates("0331",sh,tier,"2026-11-13"), top=L.defaultRates("Top pick",sh,tier,"2026-11-13");
    A.deepStrictEqual(a,top,sh+" "+tier); A.deepStrictEqual(b,top,sh+" "+tier);
  }
  A.deepStrictEqual(L.defaultRates("Dispatcher","1st","4001+","2026-11-13"),{rate:64.65,otRate:96.98});
  A.deepStrictEqual(L.defaultRates("Dispatcher","2nd","4001+","2026-11-13"),{rate:86.2,otRate:96.98});
  A.deepStrictEqual(L.defaultRates("Dispatcher","3rd","4001+","2026-11-13"),{rate:103.44,otRate:116.37});
});
t("Local 19 job picker lists Dispatcher · 0331 and 0331 under the PMA Skill 3 list",()=>{
  const h=L.jobSelectHtml("19");
  A.ok(h.includes('<option value="Dispatcher">Dispatcher · 0331</option>'),"Seattle jobs entry");
  A.ok(h.includes('<option value="0331">0331 L/S Dispatcher (WA) (Skill 3)</option>'),"Other (PMA list) entry");
});
t("California locals see 0331 only under other areas (CA pays 0331 differently)",()=>{
  const g=L.localJobGroups("13"), other=g.find(x=>x[0]==="PMA codes for other areas");
  A.ok(other && other[1].some(([v])=>v==="0331"));
  A.ok(!g.filter(x=>/coastwide/.test(x[0])).some(x=>x[1].some(([v])=>v==="0331")));
});
t("Dispatcher defaults to 10 h on 1st/2nd shift (Daniel: set dispatch at 10 hrs), like the other 10-h jobs",()=>{
  for(const j of ["Dispatcher","0331"]){
    A.ok(L.DEFH_10.includes(j),j);
    A.strictEqual(L.jobDefHours(j,"1st"),10,j); A.strictEqual(L.jobDefHours(j,"2nd"),10,j);
    A.strictEqual(L.jobDefHours(j,"3rd"),null,j+" 3rd shift is entered by hand, like every job");
    A.deepStrictEqual(L.jobHrs(j),{h:10,kind:"dock",max:11,note:""},j);
  }
  A.strictEqual(L.jobDefHours("Sweeper","1st"),10); A.strictEqual(L.jobDefHours("Stevedore","1st"),8);
});
console.log(pass+" passed, "+fail+" failed"); process.exit(fail?1:0);
