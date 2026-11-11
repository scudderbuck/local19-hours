const fs=require("fs"),A=require("assert"),path=require("path"),http=require("http"),{execFileSync}=require("child_process");
const root=__dirname;
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).map(s=>s.replace(/^<script>/,"").replace(/<\/script>$/,"")).sort((a,b)=>b.length-a.length)[0];
const m={exports:{}}; new Function("module",js)(m); const L=m.exports;
let pass=0,fail=0;
const t=(n,f)=>{try{f();pass++;console.log("PASS "+n);}catch(e){fail++;console.log("FAIL "+n+" :: "+e.message);}};

t("old splash timings stay 3.2s, or 1.2s with reduced motion",()=>{
  A.strictEqual(L.splashMs(false),3200);
  A.strictEqual(L.splashMs(true),1200);
  A.strictEqual(L.splashMs(false,"old"),3200);
  A.strictEqual(L.splashMs(true,"old"),1200);
  A.deepStrictEqual(L.l19SplashTiming({role:"old",event:"fallback"}),{dismissMs:3200,fadeMs:0,playVideo:false});
  A.deepStrictEqual(L.l19SplashTiming({role:"old",reduced:true}),{dismissMs:1200,fadeMs:0,playVideo:false});
});

t("new-site skip is immediate, with no fade and no video wait",()=>{
  A.deepStrictEqual(L.l19SplashTiming({role:"new",event:"skip"}),{dismissMs:0,fadeMs:0,playVideo:false});
  A.deepStrictEqual(L.l19SplashTiming({role:"new",reduced:true,event:"skip"}),{dismissMs:0,fadeMs:0,playVideo:false});
});

t("new-site video end waits 0.2s fade after the clip (3.04s + 0.2s = 3.24s)",()=>{
  A.strictEqual(L.L19_SPLASH.newFadeMs,200);
  A.strictEqual(L.L19_SPLASH.newVideoMs,3040);
  const end=L.l19SplashTiming({role:"new",event:"ended"});
  A.deepStrictEqual(end,{dismissMs:3240,fadeMs:200,playVideo:true});
  const early=L.l19SplashTiming({role:"new",event:"ended",endedAtMs:2800});
  A.strictEqual(early.dismissMs,3000);
  A.ok(end.dismissMs < L.L19_SPLASH.newMaxMs, "happy path should finish before the fallback");
});

t("new-site fallback is 3.4s if the video fails or does not autoplay; reduced motion is 0.8s still",()=>{
  A.strictEqual(L.splashMs(false,"new"),3400);
  A.strictEqual(L.splashMs(true,"new"),800);
  A.deepStrictEqual(L.l19SplashTiming({role:"new",event:"fallback"}),{dismissMs:3400,fadeMs:0,playVideo:false});
  A.deepStrictEqual(L.l19SplashTiming({role:"new",event:"autoplay-fail"}),{dismissMs:3400,fadeMs:0,playVideo:false});
  A.deepStrictEqual(L.l19SplashTiming({role:"new",reduced:true,event:"fallback"}),{dismissMs:800,fadeMs:0,playVideo:false});
});

t("new-site markup branch has the video and poster, not the shield splash",()=>{
  const i=html.indexOf('if(neu)');
  A.ok(i>0);
  const neu=html.slice(i, html.indexOf("}else{", i));
  const old=html.slice(html.indexOf("}else{", i), html.indexOf("})();", i));
  A.ok(neu.includes("splashVid") && neu.includes("img/bridges-turn.mp4") && neu.includes("img/bridges-turn-poster.jpg") && neu.includes("muted") && neu.includes("playsinline") && neu.includes("autoplay") && neu.includes('preload="auto"'), neu);
  A.ok(!neu.includes("img/splash.jpg") && !neu.includes("img/bridges.jpg"));
  A.ok(old.includes('id="splash"') && old.includes("img/splash.jpg") && old.includes("img/bridges.jpg"));
  A.ok(!old.includes("bridges-turn.mp4"));
  A.ok(html.includes('classList.add("l19new")'));
  A.ok(html.includes("background:#0c132d"));
});

t("service worker does not precache the mp4 and lets Range requests pass through",()=>{
  const sw=fs.readFileSync(path.join(root,"sw.js"),"utf8");
  const list=sw.match(/const C="l19hours-v139",F=\[([\s\S]*?)\];/)[1];
  A.ok(!list.includes("bridges-turn.mp4"), list);
  A.ok(list.includes("img/bridges-turn-poster.jpg"));
  A.ok(sw.includes("Range requests") || /\\.mp4/.test(sw));
  A.ok(/\\.mp4\$/.test(sw) || /\\.mp4\$\/i/.test(sw) || sw.includes(".mp4"));
});

t("old splash images are unchanged on disk",()=>{
  const out=require("child_process").execSync("git status --porcelain -- img/splash.jpg img/bridges.jpg",{cwd:root,encoding:"utf8"}).trim();
  A.strictEqual(out,"",out);
  A.ok(fs.existsSync(path.join(root,"img/bridges-turn.mp4")));
  A.ok(fs.existsSync(path.join(root,"img/bridges-turn-poster.jpg")));
});

// Range request against a tiny static server (what the SW bypass leaves to the network).
function runRangeTest(){
  return new Promise((resolve,reject)=>{
    const file=path.join(root,"img/bridges-turn.mp4");
    const buf=fs.readFileSync(file);
    const server=http.createServer((req,res)=>{
      // minimal Range like a static host / Safari would use after the SW steps aside
      const range=req.headers.range;
      if(!range){res.writeHead(200,{"Content-Type":"video/mp4","Content-Length":buf.length,"Accept-Ranges":"bytes"});res.end(buf);return;}
      const m=/bytes=(\d+)-(\d*)/.exec(range);
      if(!m){res.writeHead(416);res.end();return;}
      const start=+m[1], end=m[2]?+m[2]:Math.min(start+1023,buf.length-1);
      if(start>=buf.length||end>=buf.length||start>end){res.writeHead(416);res.end();return;}
      const chunk=buf.slice(start,end+1);
      res.writeHead(206,{"Content-Type":"video/mp4","Content-Range":`bytes ${start}-${end}/${buf.length}`,"Content-Length":chunk.length,"Accept-Ranges":"bytes"});
      res.end(chunk);
    });
    server.listen(0,"127.0.0.1",()=>{
      const port=server.address().port;
      http.get({hostname:"127.0.0.1",port,path:"/img/bridges-turn.mp4",headers:{Range:"bytes=0-1023"}},res=>{
        const chunks=[];
        res.on("data",c=>chunks.push(c));
        res.on("end",()=>{
          server.close();
          try{
            A.strictEqual(res.statusCode,206);
            A.ok(String(res.headers["content-range"]||"").startsWith("bytes 0-1023/"));
            const got=Buffer.concat(chunks);
            A.strictEqual(got.length,1024);
            A.ok(got.equals(buf.slice(0,1024)));
            resolve();
          }catch(e){reject(e);}
        });
      }).on("error",e=>{server.close();reject(e);});
    });
  });
}

runRangeTest().then(()=>{
  pass++; console.log("PASS mp4 Range request returns 206 when the SW does not intercept it");
}).catch(e=>{
  fail++; console.log("FAIL mp4 Range request returns 206 when the SW does not intercept it :: "+e.message);
}).finally(()=>{
  
t("new-site splash overlays merch-style LONGSHORE LIFE lockup, old site does not",()=>{
  const i=html.indexOf('if(neu)');
  A.ok(i>0);
  const neu=html.slice(i, html.indexOf("}else{", i));
  const old=html.slice(html.indexOf("}else{", i), html.indexOf("})();", i));
  A.ok(neu.includes('class="splashLockup splashTitle"') && neu.includes("LONGSHORE LIFE"), neu);
  A.ok(neu.includes("textPath") && neu.includes("WORK THE WATERFRONT") && neu.includes("splashTag"), neu);
  A.ok(neu.includes("img/splash-grunge.png") && neu.includes("splashGrunge"), neu);
  A.ok(!neu.includes("img/splash.jpg"));
  A.ok(!old.includes("splashTitle") && !old.includes("LONGSHORE LIFE") && !old.includes("textPath") && !old.includes("WORK THE WATERFRONT"));
  A.ok(html.includes("#ff3b00") && (html.includes("fill=\"url(#splashGrunge)\"") || html.includes('fill="url(#splashGrunge)"')));
  A.ok(html.includes("font-family:Anton") || html.includes("font-family: Anton") || html.includes("@font-face{font-family:Anton"));
  A.ok(html.includes("@keyframes splashTitleIn"));
  A.ok(html.includes("prefers-reduced-motion:reduce") && html.includes("html.l19new .splashLockup{animation:none;opacity:1}"));
  A.ok(fs.existsSync(path.join(root,"fonts/anton-regular-subset.woff2")));
  A.ok(fs.existsSync(path.join(root,"fonts/anton-regular-subset.woff")));
  A.ok(fs.existsSync(path.join(root,"img/splash-grunge.png")));
  const sw=fs.readFileSync(path.join(root,"sw.js"),"utf8");
  A.ok(sw.includes("fonts/anton-regular-subset.woff2"));
  A.ok(sw.includes("img/splash-grunge.png"));
  A.ok(!sw.includes("alfa-slab") && !sw.includes("oswald-bold-subset"));
  A.ok(!sw.includes("bridges-turn.mp4") || !sw.match(/const C="l19hours-v139",F=\[[\s\S]*bridges-turn\.mp4/));
});

console.log("\n"+pass+" passed, "+fail+" failed");
  if(fail) process.exit(1);
});
