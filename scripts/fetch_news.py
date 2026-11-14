#!/usr/bin/env python3
"""Fetch public RSS feeds into news.json for the Longshore Life News card (v128).
Only public feeds, no login, no secrets, stdlib only. Each feed is isolated: one failing feed never breaks the rest,
and old items are kept (until they age out) if every feed is down. Writes the file only when the headlines change.
Usage: fetch_news.py [out.json]"""
import email.utils, html, json, os, re, sys, urllib.parse, urllib.request, datetime as dt
import xml.etree.ElementTree as ET

UA = "LongshoreLife/1.0 (+https://longshorelife.app)"
G = "https://news.google.com/rss/search?hl=en-US&gl=US&ceid=US:en&q="
# (label, url, mode)  mode: "all" = official union/employer feed, keep everything; "rel" = keep only relevant items
FEEDS = [
    ("ILWU", "https://www.ilwu.org/feed/", "all"),
    (None, G + urllib.parse.quote("site:ilwu.org when:90d"), "all"),  # backup for ilwu.org's own feed, which is flaky
    ("PMA", "https://www.pmanet.org/feed/", "all"),
    ("JOC", "https://www.joc.com/rssfeed", "rel"),
    ("gCaptain", "https://gcaptain.com/feed/", "rel"),
    ("Port of Seattle", "https://www.portseattle.org/rss.xml", "rel"),
    (None, G + urllib.parse.quote("ILWU when:60d"), "rel"),
    (None, G + urllib.parse.quote('longshore OR longshoremen OR dockworkers when:60d'), "long"),
    (None, G + urllib.parse.quote('"West Coast ports" when:45d'), "rel"),
    (None, G + urllib.parse.quote('"Port of Seattle" OR "Port of Tacoma" OR "Northwest Seaport Alliance" when:45d'), "rel"),
]
KEEP, PER_SOURCE, PER_FEED = 20, 4, 5  # PER_FEED: newest N from each feed, so one busy search can't crowd out the rest
MAX_DAYS = {"all": 180, "rel": 45, "long": 45}
STRONG = re.compile(r"\bilwu\b|longshore|dockworker|dock worker|\bport worker|stevedor|pacific maritime association|\bpma\b|waterfront|watchm[ae]n|harbou?r worker|marine clerk|(?<!european )(?<!soviet )\bunions?\b(?! pacific)", re.I)
PORT = re.compile(r"seattle|tacoma|los angeles|long beach|oakland|portland|everett|olympia|northwest seaport|\bnwsa\b|west coast|pacific northwest|puget sound|columbia river|\bports?\b", re.I)
TOPIC = re.compile(r"strike|labou?r|contract|automation|tariff|fee|congestion|container|cargo|vessel|crane|terminal|shipping|dock|lockout|negotiat|wage|safety", re.I)
LONGCTX = re.compile(r"worker|union|ilwu|port|dock|harbou?r|ship|cargo|terminal|compensation|maritime|stevedor|pma|local \d", re.I)
JUNK = re.compile(r"obituar|funeral|\bmma\b|sherdog|tribute|rest in peace|football|basketball|\bgolf\b|real estate|for sale", re.I)

def get(url, tries=2):
    for i in range(tries):
        try: return get1(url)
        except Exception:
            if i == tries - 1: raise

def get1(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=25) as r:
        b = r.read(4_000_000)
        if r.headers.get("Content-Encoding") == "gzip":
            import gzip; b = gzip.decompress(b)
    return b.decode("utf-8", "replace")

def parse(text):
    m = re.search(r"<(rss|feed|rdf:RDF)\b", text)  # some sites print HTML comments before the XML
    if not m: raise ValueError("not a feed")
    text = text[m.start():]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    root = ET.fromstring(text.encode("utf-8"))
    out = []
    for it in root.iter():
        tag = it.tag.split("}")[-1]
        if tag not in ("item", "entry"): continue
        def f(n):
            for c in it:
                if c.tag.split("}")[-1] == n: return c
        t = f("title"); l = f("link"); s = f("source"); d = next((x for x in (f("pubDate"), f("published"), f("updated"), f("date")) if x is not None), None)
        if t is None or l is None: continue
        link = (l.text or "").strip() or l.attrib.get("href", "")
        out.append(((t.text or ""), link, (d.text if d is not None else ""), (s.text if s is not None else ""), ((f("description").text or "") if f("description") is not None else "")))
    return out

def when(s):
    s = (s or "").strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except Exception:
        try: d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception: return None
    if d.tzinfo is None: d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)

def clean(t):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", t or ""))).strip()

def relevant(mode, title, blob, src):
    if JUNK.search(title) or JUNK.search(src or ""): return False
    if mode == "all": return True
    if mode == "long": return bool(re.search(r"longshore|dockworker", title + " " + blob, re.I) and LONGCTX.search(title + " " + blob))
    return bool(STRONG.search(title) or (PORT.search(title) and TOPIC.search(title)))

def key(t): return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
def toks(t): return set(w for w in key(t).split() if len(w) > 3)

def main(out):
    now = dt.datetime.now(dt.timezone.utc)
    items, used = [], []
    for label, url, mode in FEEDS:
        try:
            rows = parse(get(url))
        except Exception as e:
            print("FAIL", label or url[:60], str(e)[:80]); continue
        n = 0; got = []
        for title, link, ds, src, desc in rows:
            title = clean(title); d = when(ds)
            if not title or d is None or d > now + dt.timedelta(days=1): continue
            if (now - d).days > MAX_DAYS[mode]: continue
            s = label or clean(src).lstrip("-–| ")
            if label is None:  # Google News appends " - Publisher" to the title
                title = re.sub(r"\s+[-–|]\s+" + re.escape(s) + r"\s*$", "", title) if s else title
                if not s: continue
            title = re.sub(r"\s+[-–|]\s*$", "", title)
            p = urllib.parse.urlsplit(link.strip())
            if p.scheme not in ("http", "https"): continue
            link = urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, "&".join(x for x in p.query.split("&") if x and not x.startswith("utm_")), ""))
            if not relevant(mode, title, clean(desc), s): continue
            got.append({"t": title[:150], "s": s[:40], "d": d.strftime("%Y-%m-%dT%H:%MZ"), "u": link})
        got.sort(key=lambda x: x["d"], reverse=True); items += got[:PER_FEED]; n = len(got[:PER_FEED])
        print("OK", label or "Google News", n)
        used.append(label or "Google News")
    try:
        old = json.load(open(out)).get("items", [])
    except Exception:
        old = []
    for o in old:  # keep earlier items until they age out (a feed having a bad day must not empty the list)
        d = when(o.get("d", "").replace("Z", "+00:00")) if o.get("d") else None
        if d and (now - d).days <= 45 + (135 if o.get("s") in ("ILWU", "PMA") else 0): items.append(o)
    items.sort(key=lambda x: x["d"], reverse=True)
    res, seen, cnt = [], [], {}
    for x in items:
        k = key(x["t"]); tk = toks(x["t"])
        if any(k == a or (tk and len(tk & b) / len(tk | b) >= 0.6) for a, b in seen): continue
        if any(x["u"] == y["u"] for y in res): continue
        if cnt.get(x["s"], 0) >= PER_SOURCE: continue
        cnt[x["s"]] = cnt.get(x["s"], 0) + 1; seen.append((k, tk)); res.append(x)
        if len(res) >= KEEP: break
    if len(res) < 3:
        print("too few items; keeping old file"); return
    prev = None
    try: prev = json.load(open(out)).get("items")
    except Exception: pass
    if prev == res:
        print("no change"); return
    json.dump({"updated": now.strftime("%Y-%m-%dT%H:%MZ"), "items": res}, open(out, "w"), ensure_ascii=False, indent=0)
    print("wrote", len(res), "items from", ", ".join(used))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "news.json")
