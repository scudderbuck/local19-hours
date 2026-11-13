#!/usr/bin/env python3
import http.server, threading, socketserver, json, traceback, os, re, shutil
from playwright.sync_api import sync_playwright

ROOT = os.environ.get("L19_ROOT", os.path.dirname(os.path.abspath(__file__)))
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self,*a,**k): super().__init__(*a,directory=ROOT,**k)
    def log_message(self,*a): pass
    def do_GET(self):
        path=self.translate_path(self.path)
        if os.path.isfile(path):
            size=os.path.getsize(path)
            ctype=self.guess_type(path)
            rng=self.headers.get("Range")
            if rng:
                m=re.match(r"bytes=(\d*)-(\d*)", rng)
                if m:
                    start=int(m.group(1) or 0)
                    end=int(m.group(2)) if m.group(2) else size-1
                    end=min(end, size-1)
                    if 0<=start<=end:
                        length=end-start+1
                        self.send_response(206)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Accept-Ranges", "bytes")
                        self.send_header("Content-Range", "bytes %d-%d/%d"%(start,end,size))
                        self.send_header("Content-Length", str(length))
                        self.end_headers()
                        with open(path,"rb") as f:
                            f.seek(start)
                            remaining=length
                            while remaining:
                                chunk=f.read(min(65536, remaining))
                                if not chunk: break
                                self.wfile.write(chunk)
                                remaining-=len(chunk)
                        return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(size))
            self.end_headers()
            with open(path,"rb") as f:
                shutil.copyfileobj(f, self.wfile)
            return
        super().do_GET()
S=type("S",(socketserver.ThreadingTCPServer,),{"allow_reuse_address":True})
old=S(("127.0.0.1",8570),H); new=S(("127.0.0.1",8571),H)
threading.Thread(target=old.serve_forever,daemon=True).start()
threading.Thread(target=new.serve_forever,daemon=True).start()

shifts=[{"id":"e1","date":"2026-10-12","shift":"1st","job":"Stevedore","hours":8,"rate":58.85,"otRate":88.28,"pier":"T18"},
        {"id":"e2","date":"2026-10-13","shift":"1st","job":"Top pick","hours":10,"rate":62.12,"otRate":93.18,"pier":"T18"},
        {"id":"e3","date":"2026-10-17","shift":"2nd","job":"Lashing","hours":8,"rate":58.85,"otRate":88.28,"pier":"T5"}]
stubs=[{"week":"2026-10-11","gross":1400,"hours":26}]
dest_shifts=[{"id":"keep1","date":"2026-01-06","shift":"1st","job":"Stevedore","hours":8,"rate":50,"otRate":75,"pier":"T18"}]

def ready(extra=""):
    return "localStorage.setItem('l19.setupDone','1');localStorage.setItem('l19.tourDone','1');localStorage.setItem('l19.ratesSeen','2026-07-04');"+extra

pass_n=fail_n=0
def t(name, ok, detail=""):
    global pass_n,fail_n
    if ok:
        pass_n+=1; print("PASS", name)
    else:
        fail_n+=1; print("FAIL", name, "::", str(detail)[:300])

with sync_playwright() as p:
    browser=p.chromium.launch(executable_path="/usr/bin/google-chrome",headless=True,args=["--no-sandbox","--disable-dev-shm-usage"])
    def ctx_page(init=""):
        ctx=browser.new_context(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True)
        page=ctx.new_page()
        logs=[]
        page.on("pageerror", lambda e: logs.append("PAGEERROR "+str(e)))
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text}") if m.type in ("error","warning") else None)
        if init: page.add_init_script(init)
        return ctx,page,logs
    def clean(page):
        page.wait_for_selector("#bbar", state="attached", timeout=20000)
        page.evaluate("""() => {['splash','splash2','splashVid','setup','tour','lock'].forEach(id=>document.getElementById(id)?.remove());document.documentElement.classList.add('spdone');}""")
        page.wait_for_timeout(200)

    # 1. old builds hash
    ctx,page,logs=ctx_page(ready("localStorage.setItem('l19hours.v1',%s);localStorage.setItem('l19.stubs',%s);localStorage.setItem('l19.startHrs','4010');localStorage.setItem('l19.local','19');localStorage.setItem('l19.ba','2065550191');"%(json.dumps(json.dumps(shifts)),json.dumps(json.dumps(stubs)))))
    page.goto("http://127.0.0.1:8570/index.html?l19site=old", wait_until="domcontentloaded")
    clean(page)
    try:
        page.wait_for_selector("#moveBan", timeout=5000)
    except Exception:
        pass
    notice=page.inner_text("#moveBan") if page.query_selector("#moveBan") else ""
    t("old-site notice shows for live data", "Move my data to longshorelife.app" in notice and "3 saved shifts" in notice, notice)
    payload=page.evaluate("""() => {const bak=l19BackupObject(Object.assign({}, l19LiveBackupParts(), {move:{v:1,from:location.origin}})); const enc=l19EncodeMoveHash(bak); return {ok:enc.ok,hash:enc.hash,count:bak.entries.length,startHours:bak.startHours,ba:bak.ba};}""")
    t("old origin built transfer hash", payload.get("ok") and payload.get("count")==3, payload)
    ctx.close()

    # 2. empty dest apply
    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8571/index.html?l19site=new"+payload["hash"], wait_until="domcontentloaded")
    clean(page)
    try:
        page.wait_for_selector("#moveInYes", timeout=8000)
        banner=page.inner_text("#moveIn")
        t("empty dest asks to confirm without replace warning", "Move my data here" in banner and "already has" not in banner.lower(), banner)
        page.click("#moveInYes")
        page.wait_for_selector("text=Your data is here", timeout=10000)
        state=page.evaluate("""() => ({entries:JSON.parse(localStorage.getItem('l19hours.v1')||'[]'),stubs:JSON.parse(localStorage.getItem('l19.stubs')||'[]'),startHours:localStorage.getItem('l19.startHrs'),ba:localStorage.getItem('l19.ba')})""")
        t("hash transfer apply fidelity on empty dest", len(state["entries"])==3 and {e["id"] for e in state["entries"]}=={"e1","e2","e3"} and state["stubs"][0]["gross"]==1400 and state["startHours"]=="4010" and state["ba"]=="2065550191", state)
    except Exception as e:
        t("hash transfer apply fidelity on empty dest", False, str(e)+" | logs="+"; ".join(logs)+" | html="+(page.inner_text("#moveInHost") if page.query_selector("#moveInHost") else ""))
    ctx.close()

    # 3. already has data, cancel
    ctx,page,logs=ctx_page(ready("localStorage.setItem('l19hours.v1',%s);localStorage.setItem('l19.startHrs','12');"%json.dumps(json.dumps(dest_shifts))))
    page.goto("http://127.0.0.1:8571/index.html?l19site=new"+payload["hash"], wait_until="domcontentloaded")
    clean(page)
    try:
        page.wait_for_selector("#moveInNo", timeout=8000)
        banner=page.inner_text("#moveIn")
        t("already-has-data shows replace warning", "already has Longshore Life data" in banner, banner)
        page.click("#moveInNo")
        page.wait_for_timeout(300)
        state=page.evaluate("""() => ({entries:JSON.parse(localStorage.getItem('l19hours.v1')||'[]'),startHours:localStorage.getItem('l19.startHrs')})""")
        t("already-has-data cancel leaves dest unchanged", [e["id"] for e in state["entries"]]==["keep1"] and state["startHours"]=="12", state)
    except Exception as e:
        t("already-has-data cancel leaves dest unchanged", False, str(e)+" | logs="+"; ".join(logs))

    # 4. confirm replace in same ctx after cancel: need to reload hash
    try:
        page.goto("http://127.0.0.1:8571/index.html?l19site=new&r=2"+payload["hash"], wait_until="domcontentloaded")
        clean(page)
        page.wait_for_selector("#moveInYes", timeout=8000)
        page.click("#moveInYes")
        page.wait_for_selector("text=Your data is here", timeout=10000)
        state=page.evaluate("""() => ({entries:JSON.parse(localStorage.getItem('l19hours.v1')||'[]'),startHours:localStorage.getItem('l19.startHrs')})""")
        t("already-has-data confirm replaces dest", {e["id"] for e in state["entries"]}=={"e1","e2","e3"} and state["startHours"]=="4010", state)
    except Exception as e:
        t("already-has-data confirm replaces dest", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()

    # 5. corrupt
    ctx,page,logs=ctx_page(ready("localStorage.setItem('l19hours.v1',%s);"%json.dumps(json.dumps(dest_shifts))))
    page.goto("http://127.0.0.1:8571/index.html?l19site=new#l19move=not_valid_base64", wait_until="domcontentloaded")
    clean(page)
    try:
        page.wait_for_selector("#moveIn", timeout=8000)
        banner=page.inner_text("#moveIn")
        state=page.evaluate("() => JSON.parse(localStorage.getItem('l19hours.v1')||'[]')")
        t("corrupt payload leaves dest unchanged", "Couldn't move that data" in banner and [e["id"] for e in state]==["keep1"], banner)
    except Exception as e:
        t("corrupt payload leaves dest unchanged", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()

    # 6. icon wiring by site role
    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8570/index.html?l19site=old", wait_until="domcontentloaded")
    icons=page.evaluate("""() => ({
      manifest: document.querySelector('link[rel="manifest"]')?.getAttribute('href'),
      apple: document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href'),
      icons: [...document.querySelectorAll('link[rel="icon"]')].map(l=>l.getAttribute('href')),
      logo: document.getElementById('hdLogo')?.getAttribute('src'),
      name: document.querySelector('#hdr .hdName')?.textContent||null
    })""")
    t("old site still uses the original icons", icons.get("manifest")=="manifest.json" and icons.get("apple")=="img/apple-touch-icon.png" and "icon-192.png" in icons.get("icons",[]) and "icons/icon-192.png" not in icons.get("icons",[]), icons)
    t("old site header still uses the original badge and has no extra title text", icons.get("logo")=="img/logo-header.png" and not icons.get("name"), icons)
    ctx.close()

    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8571/index.html?l19site=new", wait_until="domcontentloaded")
    icons=page.evaluate("""() => ({
      manifest: document.querySelector('link[rel="manifest"]')?.getAttribute('href'),
      apple: document.querySelector('link[rel="apple-touch-icon"]')?.getAttribute('href'),
      icons: [...document.querySelectorAll('link[rel="icon"]')].map(l=>l.getAttribute('href')),
      logo: document.getElementById('hdLogo')?.getAttribute('src'),
      name: document.querySelector('#hdr .hdName')?.textContent||null,
      nameVisible: !!(document.querySelector('#hdr .hdName') && getComputedStyle(document.querySelector('#hdr .hdName')).display!=='none' && (document.querySelector('#hdr .hdName').textContent||'').includes('Longshore Life'))
    })""")
    t("new site uses v8 icons and manifest-new.json", icons.get("manifest")=="manifest-new.json" and icons.get("apple")=="icons/apple-touch-icon.png" and "icons/icon-192.png" in icons.get("icons",[]) and "icons/favicon-32.png" in icons.get("icons",[]), icons)
    t("new site header uses the v8 crane mark and shows Longshore Life as text", icons.get("logo")=="img/logo-header-new.png" and icons.get("nameVisible") and icons.get("name") and "Longshore Life" in icons.get("name"), icons)
    ctx.close()

    # 7. new-domain video splash: skip, ended+fade, fallback timing
    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8571/index.html?l19site=new", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#splashVid", timeout=5000)
        has_old=page.evaluate("() => !!(document.getElementById('splash')||document.getElementById('splash2'))")
        srcs=page.evaluate("() => [...document.querySelectorAll('#splashVideo source')].map(s=>s.getAttribute('src')+'|'+s.getAttribute('type'))")
        src=srcs[0].split("|")[0] if srcs else None
        title=page.evaluate("() => (document.querySelector('#splashVid .splashTitle')?.textContent||'').replace(/\\s+/g,' ').trim()")
        t("new site shows only the Bridges video splash", (not has_old) and src=="img/bridges-turn.mp4" and srcs==["img/bridges-turn.mp4|video/mp4","img/bridges-turn.webm|video/webm"] and page.query_selector("#splashVid") is not None, {"old":has_old,"srcs":srcs})
        t("new-site splash shows LONGSHORE LIFE and WORK THE WATERFRONT over the video", title.startswith("LONGSHORE LIFE") and "WORK THE WATERFRONT" in title, title)
        fit=page.evaluate("""() => {
          const ev=document.getElementById('splashVid');
          const lock=document.querySelector('.splashLockup');
          const svg=document.querySelector('.splashTitleSvg');
          const tag=document.querySelector('.splashTag');
          const vid=document.getElementById('splashVideo');
          const vw=innerWidth, vh=innerHeight;
          const r=el=>el?(()=>{const b=el.getBoundingClientRect();return {t:b.top,l:b.left,r:b.right,b:b.bottom,w:b.width,h:b.height};})():null;
          const L=r(lock), S=r(svg), T=r(tag), V=r(vid);
          const pad=1;
          const inView=b=>b && b.t>=-pad && b.l>=-pad && b.r<=vw+pad && b.b<=vh+pad;
          const faceY=V?V.t+V.h*0.105:0;
          return {
            inView: !!(inView(L)&&inView(S)&&inView(T)&&inView(V)),
            lock:L, svg:S, tag:T, video:V, vw, vh, faceY,
            faceClear: !!(T && V && T.b <= faceY + 2),
            title: (lock?.textContent||'').replace(/\\s+/g,' ').trim()
          };
        }""")
        t("new-site splash lockup and Harry fit on screen without covering his face", fit.get("inView") and fit.get("faceClear") and fit["video"]["h"]>100, fit)
        page.click("#splashVid")
        page.wait_for_timeout(250)
        gone=page.evaluate("() => !document.getElementById('splashVid') && document.documentElement.classList.contains('spdone')")
        t("tap skips the new-site splash immediately", gone, page.evaluate("() => ({vid:!!document.getElementById('splashVid'),spdone:document.documentElement.classList.contains('spdone')})"))
    except Exception as e:
        t("new site shows only the Bridges video splash", False, str(e)+" | logs="+"; ".join(logs))
        t("tap skips the new-site splash immediately", False, str(e))
    ctx.close()

    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8571/index.html?l19site=new", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#splashVid", timeout=5000)
        page.wait_for_function("() => !document.getElementById('splashVid') && document.documentElement.classList.contains('spdone')", timeout=4000)
        t("new-site splash hides after the video ends plus a short fade (under the 3.4s fallback)", True)
    except Exception as e:
        t("new-site splash hides after the video ends plus a short fade (under the 3.4s fallback)", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()

    ctx,page,logs=ctx_page(ready())
    def _abort_clip(r):
        u=r.request.url
        if "bridges-turn.mp4" in u or "bridges-turn.webm" in u:
            r.abort()
        else:
            r.continue_()
    page.route("**/*bridges-turn*", _abort_clip)
    page.goto("http://127.0.0.1:8571/index.html?l19site=new", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#splashVid", timeout=5000)
        page.wait_for_function("() => !document.getElementById('splashVid') && document.documentElement.classList.contains('spdone')", timeout=4500)
        t("new-site splash falls back by 3.4s if the video cannot play", True)
    except Exception as e:
        t("new-site splash falls back by 3.4s if the video cannot play", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()

    # Decoded-frame test: sample the playing <video> via canvas during real
    # playback (not by seeking). Seeking can silently snap to t=0 when the
    # static server lacks HTTP Range, which is how the previous preview
    # captured the poster/first frame on every shot.
    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8571/index.html?l19site=new", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#splashVideo", timeout=5000)
        page.wait_for_function("""() => {
          const v=document.getElementById('splashVideo');
          return !!(v && v.readyState>=2 && v.videoWidth>0 && !v.paused);
        }""", timeout=4000)
        def snap_at(min_t):
            page.wait_for_function(
                """(minT) => { const v=document.getElementById('splashVideo'); return !!(v && v.currentTime>=minT && v.videoWidth>0); }""",
                arg=min_t, timeout=4000)
            return page.evaluate("""() => {
              const v=document.getElementById('splashVideo');
              const w=48, h=64;
              const c=document.createElement('canvas');
              c.width=w; c.height=h;
              c.getContext('2d').drawImage(v,0,0,w,h);
              const d=c.getContext('2d').getImageData(0,0,w,h).data;
              const vis=getComputedStyle(v);
              return {
                t:v.currentTime, rs:v.readyState, paused:v.paused, ended:v.ended,
                w:v.videoWidth, h:v.videoHeight, src:v.currentSrc,
                display:vis.display, visibility:vis.visibility, opacity:vis.opacity,
                rgba:Array.from(d)
              };
            }""")
        a=snap_at(0.2)
        b=snap_at(2.8)
        n=min(len(a["rgba"]), len(b["rgba"]))
        mae=sum(abs(a["rgba"][i]-b["rgba"][i]) for i in range(n))/(n or 1)
        visible=(a.get("display")!="none" and a.get("visibility")!="hidden" and float(a.get("opacity") or 0)>0
                 and a.get("w",0)>=480 and "bridges-turn." in (a.get("src") or ""))
        t("new-site splash decoded frames differ between t=0.2 and t=2.8 (head turn is painted, not a still poster)",
          visible and mae>=8 and a["t"]>=0.2 and b["t"]>=2.8 and a["t"]<1.2,
          {"mae":round(mae,2),"t0":a["t"],"t1":b["t"],"src":a.get("src"),"w":a.get("w"),"vis":(a.get("display"),a.get("visibility"),a.get("opacity"))})
    except Exception as e:
        t("new-site splash decoded frames differ between t=0.2 and t=2.8 (head turn is painted, not a still poster)", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()

    ctx,page,logs=ctx_page(ready())
    page.goto("http://127.0.0.1:8570/index.html?l19site=old", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#splash", timeout=5000)
        state=page.evaluate("""() => ({
          splash:!!document.getElementById('splash'),
          splash2:!!document.getElementById('splash2'),
          vid:!!document.getElementById('splashVid'),
          src:document.querySelector('#splash img')?.getAttribute('src')
        })""")
        t("old site still uses the two-image splash and does not load the video", state.get("splash") and state.get("splash2") and not state.get("vid") and state.get("src")=="img/splash.jpg", state)
    except Exception as e:
        t("old site still uses the two-image splash and does not load the video", False, str(e)+" | logs="+"; ".join(logs))
    ctx.close()
    browser.close()

old.shutdown(); new.shutdown()
print(f"\n{pass_n} passed, {fail_n} failed")
raise SystemExit(1 if fail_n else 0)
