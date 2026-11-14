const fs=require("fs"),A=require("assert"),path=require("path");
const root=__dirname;
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
const sw=fs.readFileSync(path.join(root,"sw.js"),"utf8");
const lic=fs.readFileSync(path.join(root,"LICENSE"),"utf8");
const man=fs.readFileSync(path.join(root,"manifest.json"),"utf8");
const manNew=fs.readFileSync(path.join(root,"manifest-new.json"),"utf8");
let pass=0,fail=0;
const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

function visibleChunks(src){
  // Approximate UI text: HTML body markup and JS string literals that can appear on screen.
  const parts=[];
  const body=src.replace(/^[\s\S]*<body[^>]*>/i,"").replace(/<script[\s\S]*$/i,"");
  parts.push(body);
  // string literals in the main script that include copyright / about / merch / chat copy
  const strings=[...src.matchAll(/["'`]([^"'`]{0,400})["'`]/g)].map(m=>m[1]);
  parts.push(strings.filter(s=>/Daniel|White|©|Longshore Life|Made by|tells |ask /i.test(s)).join("\n"));
  return parts.join("\n");
}

t("version is v147 and the service worker cache name matches",()=>{
  A.ok(html.includes('var L19_BOOT_VER="v147"'));
  A.ok(html.includes('const APP_VERSION="v147",CACHE_VERSION="l19hours-v147"'));
  A.ok(sw.includes('const C="l19hours-v147"'));
  A.ok(!sw.includes('const C="l19hours-v139"'));
});

t("visible footer and about copyright are Longshore Life™, not a personal name",()=>{
  const ftc=(html.match(/<small id="ftc">([\s\S]*?)<\/small>/)||[])[1]||"";
  const about=(html.match(/<p class="mut" id="aboutOwn">([\s\S]*?)<\/p>/)||[])[1]||"";
  const strip=s=>s.replace(/<br\s*\/?>/gi," ").replace(/<[^>]+>/g,"").replace(/\s+/g," ").trim();
  const ftcText=strip(ftc);
  const aboutText=strip(about);
  A.strictEqual(ftcText,"© 2026 Longshore Life™. All rights reserved.");
  A.ok(aboutText.includes("© 2026 Longshore Life™. All rights reserved."));
  A.ok(aboutText.includes("Longshore Life is an independent app."));
  A.ok(!/Daniel|White/.test(ftcText+aboutText), ftcText+" | "+aboutText);
});

t("new-host header wordmark is Longshore Life with a superscript ™; old-host header is the v139 badge only",()=>{
  const neuStart=html.indexOf('src="img/logo-header-new.png"');
  const oldStart=html.indexOf('src="img/logo-header.png"');
  A.ok(neuStart>0 && oldStart>neuStart);
  const neu=html.slice(neuStart, html.indexOf("}else{", neuStart));
  const oldWrite=(()=>{const a=html.indexOf('src="img/logo-header.png"'); const s=html.lastIndexOf("document.write", a); const e=html.indexOf("');", a)+3; return html.slice(s,e);})();
  A.ok(neu.includes("hdName") && neu.includes("Longshore Life") && neu.includes('class="tm"') && neu.includes("™"), neu);
  A.ok(oldWrite.includes('src="img/logo-header.png"') && oldWrite.includes('alt="Longshore Life"') && oldWrite.includes('width="76"') && oldWrite.includes('height="112"'), oldWrite);
  A.ok(!oldWrite.includes("hdName") && !oldWrite.includes("™") && !oldWrite.includes("logo-header-new.png"), oldWrite);
  A.strictEqual(oldWrite, `document.write('<img id="hdLogo" src="img/logo-header.png" alt="Longshore Life" width="76" height="112" decoding="async" onload="if(window.l19HdrFit)l19HdrFit()">');`);
  A.ok(!html.includes("html:not(.l19new) .hdName") && !html.includes("html:not(.l19new) #hdr .hdt"));
});

t("™ is not added to the document title, manifests, or splash lettering",()=>{
  const title=(html.match(/<title>([^<]+)<\/title>/)||[])[1];
  A.strictEqual(title,"Longshore Life");
  const manifests=JSON.parse(man), manifestsNew=JSON.parse(manNew);
  A.strictEqual(manifests.name,"Longshore Life");
  A.strictEqual(manifests.short_name,"Longshore");
  A.strictEqual(manifestsNew.name,"Longshore Life");
  A.strictEqual(manifestsNew.short_name,"Longshore");
  A.ok(!html.includes("LONGSHORE LIFE™") && !html.includes("LONGSHORE LIFE<span"));
  const splashSlice=html.includes("textPath") ? html.slice(html.indexOf("textPath"), html.indexOf("textPath")+400) : "";
  A.ok(splashSlice.includes("LONGSHORE LIFE"));
  A.ok(!splashSlice.includes("™"));
});

t("Daniel White is gone from served visible/meta/legal text",()=>{
  A.ok(!html.includes("Daniel White"));
  A.ok(!sw.includes("Daniel White"));
  A.ok(!lic.includes("Daniel White"));
  A.ok(lic.includes("Copyright (c) 2026 Longshore Life. All rights reserved."));
  A.ok(!html.includes("by Daniel White"));
  A.ok(!html.includes("Made by Daniel"));
  A.ok(!html.includes("ask Daniel"));
  A.ok(!html.includes("tells Daniel"));
  A.ok(!html.includes("(Daniel; local rule"));
  const vis=visibleChunks(html);
  A.ok(!vis.includes("Daniel White"), vis.slice(0,200));
  A.ok(!/by Daniel\b/.test(vis));
});

t("manifests still have no personal name or email",()=>{
  A.ok(!/Daniel|White|scudderbuck|@gmail\.com/.test(man+manNew));
});

console.log("\n"+pass+" passed, "+fail+" failed");
if(fail) process.exit(1);
