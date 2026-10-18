const C="l19hours-v47",F=["./","index.html","manifest.json","icon-192.png","icon-512.png"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(F.map(u=>new Request(u,{cache:"reload"})))).then(()=>self.skipWaiting()));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==C).map(x=>caches.delete(x)))).then(()=>self.clients.claim()));});
self.addEventListener("fetch",e=>{if(e.request.method!=="GET")return;
 const u=new URL(e.request.url);if(u.origin!==self.location.origin&&u.hostname!=="www.gstatic.com")return; /* Firebase/Firestore/Auth network calls are never cached or intercepted; only the pinned SDK scripts on gstatic use network-first */
 e.respondWith(fetch(e.request,{cache:"no-cache"}).then(r=>{const cp=r.clone();caches.open(C).then(c=>c.put(e.request,cp));return r;}).catch(()=>caches.match(e.request).then(m=>m||caches.match("index.html"))));});
