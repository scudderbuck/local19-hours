const fs=require("fs"),A=require("assert"),path=require("path"),{execSync}=require("child_process");
const root=__dirname;
let pass=0,fail=0;
const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

function read(rel){return fs.readFileSync(path.join(root,rel));}
function pngSize(buf){
  const sig=Buffer.from([137,80,78,71,13,10,26,10]);
  A.ok(buf.slice(0,8).equals(sig),"not a PNG");
  return {w:buf.readUInt32BE(16),h:buf.readUInt32BE(20)};
}
function icoSizes(buf){
  A.strictEqual(buf.readUInt16LE(0),0,"ico reserved");
  A.strictEqual(buf.readUInt16LE(2),1,"ico type");
  const n=buf.readUInt16LE(4);
  const sizes=new Set();
  for(let i=0;i<n;i++){
    const o=6+i*16;
    sizes.add((buf[o]||256)+"x"+(buf[o+1]||256));
  }
  return sizes;
}
function gitClean(rel){
  const out=execSync("git status --porcelain -- "+rel,{cwd:root,encoding:"utf8"}).trim();
  A.strictEqual(out,"",rel+" should be unchanged, got: "+out);
}
function gitSame(rel){
  execSync("git diff --exit-code -- "+rel,{cwd:root});
}

const oldMan=JSON.parse(read("manifest.json").toString());
const newMan=JSON.parse(read("manifest-new.json").toString());
const html=read("index.html").toString();
const sw=read("sw.js").toString();

t("old manifest.json still points at the original icon files",()=>{
  gitClean("manifest.json");
  const srcs=oldMan.icons.map(i=>i.src).sort();
  A.deepStrictEqual(srcs,["icon-192.png","icon-512.png","img/icon-512-maskable.png"].sort());
  const by=Object.fromEntries(oldMan.icons.map(i=>[i.src,i]));
  A.strictEqual(by["icon-192.png"].sizes,"192x192");
  A.strictEqual(by["icon-192.png"].purpose,"any");
  A.strictEqual(by["icon-512.png"].sizes,"512x512");
  A.strictEqual(by["icon-512.png"].purpose,"any");
  A.strictEqual(by["img/icon-512-maskable.png"].sizes,"512x512");
  A.strictEqual(by["img/icon-512-maskable.png"].purpose,"maskable");
  A.strictEqual(oldMan.background_color,"#dfe0db");
  A.strictEqual(oldMan.theme_color,"#00214e");
});

t("old-site icon files still exist at the original sizes and are unchanged",()=>{
  const expect={
    "icon-192.png":[192,192],
    "icon-512.png":[512,512],
    "img/apple-touch-icon.png":[180,180],
    "img/icon-512-maskable.png":[512,512]
  };
  for(const [rel,wh] of Object.entries(expect)){
    gitClean(rel);
    const s=pngSize(read(rel));
    A.deepStrictEqual([s.w,s.h],wh,rel);
  }
  gitClean("favicon.ico");
  A.deepStrictEqual(icoSizes(read("favicon.ico")), new Set(["16x16","32x32","48x48"]));
  gitClean("img/logo-header.png");
});

t("new manifest lists any and maskable icons separately, and the files have the right pixel sizes",()=>{
  A.strictEqual(newMan.name,"Longshore Life");
  A.strictEqual(newMan.theme_color,"#00214e");
  A.strictEqual(newMan.background_color,"#06203e");
  const any=newMan.icons.filter(i=>i.purpose==="any");
  const mask=newMan.icons.filter(i=>i.purpose==="maskable");
  A.strictEqual(any.length,2);
  A.strictEqual(mask.length,2);
  A.ok(newMan.icons.every(i=>i.purpose==="any"||i.purpose==="maskable"));
  A.ok(newMan.icons.every(i=>!String(i.purpose).includes(" ")),"purpose any and maskable must be separate entries");
  const expect={
    "icons/icon-192.png":[192,192],
    "icons/icon-512.png":[512,512],
    "icons/maskable-192.png":[192,192],
    "icons/maskable-512.png":[512,512]
  };
  for(const icon of newMan.icons){
    A.ok(icon.src in expect, "unexpected icon "+icon.src);
    A.ok(fs.existsSync(path.join(root,icon.src)), icon.src+" missing");
    const s=pngSize(read(icon.src));
    A.deepStrictEqual([s.w,s.h], expect[icon.src], icon.src);
    A.strictEqual(icon.type,"image/png");
    A.strictEqual(icon.sizes, expect[icon.src][0]+"x"+expect[icon.src][1]);
  }
});

t("new-domain apple-touch, favicons, and store 512 exist at the right sizes",()=>{
  const expect={
    "icons/apple-touch-icon.png":[180,180],
    "icons/favicon-32.png":[32,32],
    "icons/favicon-16.png":[16,16],
    "icons/store-512.png":[512,512]
  };
  for(const [rel,wh] of Object.entries(expect)){
    A.ok(fs.existsSync(path.join(root,rel)), rel+" missing");
    const s=pngSize(read(rel));
    A.deepStrictEqual([s.w,s.h],wh,rel);
  }
  A.deepStrictEqual(icoSizes(read("icons/favicon.ico")), new Set(["16x16","32x32","48x48"]));
});

t("index.html serves new icons only on the new domain, and still references the old icons for the old site",()=>{
  A.ok(html.includes('href="manifest-new.json"'));
  A.ok(html.includes('href="icons/favicon-32.png"'));
  A.ok(html.includes('href="icons/favicon-16.png"'));
  A.ok(html.includes('href="icons/favicon.ico"'));
  A.ok(html.includes('href="icons/icon-192.png"'));
  A.ok(html.includes('href="icons/apple-touch-icon.png"'));
  A.ok(html.includes('href="manifest.json"'));
  A.ok(html.includes('href="favicon.ico"'));
  A.ok(html.includes('href="icon-192.png"'));
  A.ok(html.includes('href="img/apple-touch-icon.png"'));
  // new-domain branch is gated
  const newBranch=html.slice(html.indexOf('if(role==="new")'), html.indexOf("}else{"));
  const oldBranch=html.slice(html.indexOf("}else{"), html.indexOf("})();"));
  A.ok(newBranch.includes("manifest-new.json") && newBranch.includes("icons/apple-touch-icon.png"), newBranch);
  A.ok(!newBranch.includes('href="img/apple-touch-icon.png"'));
  A.ok(oldBranch.includes('href="manifest.json"') && oldBranch.includes('href="img/apple-touch-icon.png"') && oldBranch.includes('href="icon-192.png"') && oldBranch.includes('href="favicon.ico"'), oldBranch);
  A.ok(!oldBranch.includes("manifest-new.json"));
  A.ok(!oldBranch.includes("icons/icon-192.png"));
  A.ok(html.includes('host==="longshorelife.app"'));
  A.ok(html.includes('l19site'));
});

t("service worker cache lists both the old and the new icon files under l19hours-v147",()=>{
  A.ok(sw.includes('const C="l19hours-v147"'));
  for(const f of ["manifest.json","icon-192.png","icon-512.png","img/icon-512-maskable.png","img/apple-touch-icon.png","favicon.ico",
                  "manifest-new.json","icons/icon-192.png","icons/icon-512.png","icons/maskable-192.png","icons/maskable-512.png",
                  "icons/apple-touch-icon.png","icons/favicon-32.png","icons/favicon-16.png","icons/favicon.ico"]){
    A.ok(sw.includes('"'+f+'"'), "sw cache missing "+f);
  }
});


t("new-domain header uses the v8 mark plus visible Longshore Life text; old site keeps the original badge",()=>{
  gitClean("img/logo-header.png");
  const neuStart=html.indexOf('if(neu)');
  A.ok(neuStart>0);
  // There are two if(neu) blocks (splash and header). Check both branches include the right logo.
  A.ok(html.includes('src="img/logo-header-new.png"'));
  A.ok(html.includes('class="hdName">Longshore Life<span class="tm" aria-hidden="true">™</span></span>'));
  A.ok(html.includes('src="img/logo-header.png" alt="Longshore Life" width="76" height="112"'));
  // The new-domain header write includes the wordmark and new art, not the old badge
  const hdr=html.slice(html.indexOf('<header id="hdr">'), html.indexOf("</header>"));
  const hdrNeu=hdr.slice(hdr.indexOf("if(neu)"), hdr.indexOf("}else{"));
  const hdrOld=hdr.slice(hdr.indexOf("}else{"), hdr.indexOf("})();"));
  A.ok(hdrNeu.includes("img/logo-header-new.png") && hdrNeu.includes("hdName") && hdrNeu.includes("Longshore Life"), hdrNeu);
  A.ok(!hdrNeu.includes("img/logo-header.png"));
  A.ok(hdrOld.includes("img/logo-header.png") && hdrOld.includes('width="76"') && hdrOld.includes('height="112"'), hdrOld);
  A.ok(!hdrOld.includes("logo-header-new.png") && !hdrOld.includes("hdName") && hdrOld.includes("logo-header.png"), hdrOld);
  A.ok(fs.existsSync(path.join(root,"img/logo-header-new.png")));
  const s=pngSize(read("img/logo-header-new.png"));
  A.deepStrictEqual([s.w,s.h],[240,240],"logo-header-new.png should be 80 CSS px at 3x");
  // merch still uses the original badge
  A.ok(html.includes('const MERCH_LOGO="img/logo-header.png"'));
});

t("service worker cache includes the new header mark and still lists the old badge",()=>{
  const sw=fs.readFileSync(path.join(root,"sw.js"),"utf8");
  A.ok(sw.includes('"img/logo-header.png"'));
  A.ok(sw.includes('"img/logo-header-new.png"'));
});

console.log("\n"+pass+" passed, "+fail+" failed");
if(fail) process.exit(1);
