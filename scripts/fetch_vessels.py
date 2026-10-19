#!/usr/bin/env python3
"""Fetch vessel schedules into vessels.json (v57: Seattle + Tacoma + outports). Covers:
  * NWSA Vessel Schedule Forecast PDF: Seattle container rows (unchanged) + Tacoma container rows
    + Tacoma breakbulk/ro-ro rows (tagged "vessel_type").
  * Outports (each source isolated: a failure or stale feed never breaks the NWSA part):
      Aberdeen     - Port of Grays Harbor published Google Sheet (CSV)      [current]
      Olympia      - Port of Olympia "Vessel Announcement" RSS + newsletter  [current, sparse]
      Everett      - Port of Everett shipping_schedule.php HTML table        [parser OK, page stale]
      Port Angeles - Port of Port Angeles ship-schedule HTML (ninja tables)   [parser OK, page stale]
      Longview / Vancouver WA - Columbia River Pilots dispatch-status +
                     vessel-locations HTML                                   [parser OK, feed frozen]
      Longview / Vancouver WA - The Ship Report daily table (OPT-IN ONLY, env OUTPORTS_SHIPREPORT=1;
                     site is "All Rights Reserved" - get permission first)
Every entry gets "port" (matching the app's NEED_PORTS names) and "terminal" (berth code/name).
Requires: pip install pymupdf.  Usage: fetch_vessels.py [out.json] [local_nwsa.pdf]
Env: OUTPORTS=0 disables outports; OUTPORTS_SHIPREPORT=1 enables the Ship Report parser;
     NO_IMO=1 skips VesselFinder IMO lookups (offline / testing)."""
import csv, html as htmlmod, io, json, os, re, sys, time, urllib.parse, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
import pymupdf

URL = "https://docs.nwseaportalliance.com/Vessel/Schedule.pdf"
TZ = ZoneInfo("America/Los_Angeles")
DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
TIME = re.compile(r"^\d{1,2}:\d{2}$")
UA = "local19-hours-vessel-fetch/1.0 (+https://github.com/scudderbuck/local19-hours)"

def iso(d, t):
    m, dd, y = map(int, d.split("/")); h, mi = map(int, t.split(":"))
    return "%04d-%02d-%02dT%02d:%02d" % (y, m, dd, h, mi)

# --------------------------------------------------------------------------- NWSA PDF
# Table pages start with one of these titles. Seattle keeps container rows only (as before);
# Tacoma keeps container + breakbulk (ro-ro / car carriers / TOTE multipurpose).
SECTIONS = {"Seattle Container Vessels": "container", "Tacoma Container Vessels": "container",
            "Breakbulk Vessels": "breakbulk"}
KEEP = {("Seattle", "container"), ("Tacoma", "container"), ("Tacoma", "breakbulk")}
TERM_RE = re.compile(r"^(T\d+|Pier|\d+|[A-Z][A-Za-z0-9]{1,9})$")

def parse(pdf_bytes):
    """Return (rows, updated). rows carry port + terminal (+ vessel_type for breakbulk)."""
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    rows, updated = [], None
    for page in doc:
        words = page.get_text("words")
        text = " ".join(w[4] for w in words)
        m = re.search(r"Last refreshed:\s*(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})\s*([AP]M)", text)
        if m and not updated:
            u = dt.datetime.strptime(m.group(1) + " " + m.group(2) + " " + m.group(3), "%m/%d/%Y %I:%M:%S %p")
            updated = u.replace(tzinfo=TZ).isoformat(timespec="seconds")
        sect = next((k for k in SECTIONS if text.startswith(k)), None)
        if not sect:
            continue  # the weekly Gantt pages (Current Week / Next Week / Week n) carry no times
        kind = SECTIONS[sect]
        # header row = topmost "Harbor" word; column starts from header words on that line
        hy = min(w[1] for w in words if w[4] == "Harbor")
        hw = sorted([w for w in words if abs(w[1] - hy) < 6], key=lambda w: w[0])
        names = [w[4] for w in hw]
        def hx(name, nth=0):
            xs = [w[0] for w in hw if w[4] == name]
            return xs[nth] if len(xs) > nth else None
        c_harbor, c_term = hx("Harbor"), hx("Terminal")
        if kind == "breakbulk":
            c_svc, c_ves = hx("Vessel", 0), hx("Vessel", 1)        # "Vessel Type" | "Vessel Name"
        else:
            c_svc, c_ves = hx("Service"), hx("Vessel")
        c_agent, c_eta, c_etd = hx("Agent"), hx("ETA"), hx("ETD")
        if None in (c_harbor, c_term, c_svc, c_ves, c_agent, c_eta, c_etd):
            print("skip page, header not found:", sect, names, file=sys.stderr); continue
        foot = min([w[1] for w in words if w[4] == "Schedule" and w[1] > hy + 20] or [1e9])
        starts = []
        for i, w in enumerate(words):
            if w[4] in ("Seattle", "Tacoma") and abs(w[0] - c_harbor) < 40 and hy + 10 < w[1] < foot:
                nxt = next((x for x in words[i + 1:i + 3] if c_term - 40 <= x[0] < c_svc - 5 and TERM_RE.match(x[4])), None)
                if nxt and abs(nxt[1] - w[1]) < 10:
                    starts.append((w[1], w, nxt))
        for k, (y, w, tw) in enumerate(starts):
            harbor = w[4]
            if (harbor, kind) not in KEEP:
                continue
            y1 = starts[k + 1][0] - 5 if k + 1 < len(starts) else min(y + 150, foot - 2)
            band = [x for x in words if y - 5 <= x[1] < y1 and x[4].strip()]
            line = lambda b: (round(b[1] / 8), b[0])
            col = lambda lo, hi: " ".join(b[4] for b in sorted(band, key=line) if lo <= b[0] < hi)
            svc, ves, agent = col(c_svc - 5, c_ves - 5), col(c_ves - 5, c_agent - 5), col(c_agent - 5, c_eta - 5)
            eta = [b[4] for b in sorted(band, key=lambda b: (b[1], b[0])) if c_eta - 5 <= b[0] < c_etd - 5]
            etd = [b[4] for b in sorted(band, key=lambda b: (b[1], b[0])) if b[0] >= c_etd - 5]
            if len(eta) < 2 or len(etd) < 2 or not (DATE.match(eta[0]) and TIME.match(eta[1]) and DATE.match(etd[0]) and TIME.match(etd[1])):
                print("skip unparsable row", harbor, ves, eta, etd, file=sys.stderr); continue
            svc = re.sub(r"^(T\d+|Pier\s*\d+)\s*", "", svc)
            # long service / type names can bleed into the vessel column
            m2 = re.match(r"^(EB Service \d|Matson - [A-Z0-9]+|Tote - [A-Z0-9]+|Car Carrier|Multipurpose|Ro-Ro)\s+(.+)$", ves)
            if m2: svc, ves = (svc + " " + m2.group(1)).strip(), m2.group(2)
            r = {"vessel": ves.strip(), "service": svc.strip() if kind == "container" else "",
                 "terminal": tw[4], "agent": agent.strip(),
                 "eta": iso(eta[0], eta[1]), "etd": iso(etd[0], etd[1]), "port": harbor}
            if kind == "breakbulk":
                r["vessel_type"] = svc.strip()
            rows.append(r)
    return rows, updated

# --------------------------------------------------------------------------- IMO lookup (unchanged)
VF = "https://www.vesselfinder.com/vessels?name="
VF_UA = "Mozilla/5.0 (compatible; local19-hours-vessel-fetch/1.0; +https://github.com/scudderbuck/local19-hours)"
ROW = re.compile(r'href="/vessels/details/(\d{7})".*?class="slna">([^<]*)<', re.S)

def norm(n):
    return re.sub(r"[^A-Z0-9]", "", n.upper())

def parse_imo(html, name):
    for imo, nm in ROW.findall(html):
        if norm(nm.replace("&amp;", "&")) == norm(name):
            return imo
    return None

def lookup_imo(name):
    req = urllib.request.Request(VF + urllib.parse.quote(name), headers={"User-Agent": VF_UA})
    return parse_imo(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace"), name)

def resolve_ids(rows, cache_path, delay=2.5, lookup=lookup_imo):
    try:
        cache = json.load(open(cache_path))
    except Exception:
        cache = {}
    today = dt.date.today()
    first = True
    for r in rows:
        key = r["vessel"].upper().strip()
        c = cache.get(key)
        if c and (c.get("imo") or (today - dt.date.fromisoformat(c["checked"])).days < 7):
            imo = c.get("imo")
        else:
            if not first: time.sleep(delay)
            first = False
            try:
                imo = lookup(r["vessel"])
                cache[key] = {"imo": imo, "checked": today.isoformat()}
            except Exception as e:
                print("imo lookup failed for %s: %s" % (r["vessel"], e), file=sys.stderr)
                imo = None
        if imo: r["imo"] = imo
    try:
        json.dump(cache, open(cache_path, "w"), indent=1, sort_keys=True)
    except Exception as e:
        print("cache write failed:", e, file=sys.stderr)

# --------------------------------------------------------------------------- outport helpers
_last_hit = {}
def get(url, min_gap=0.0, binary=False):
    """Polite GET: per-host minimum gap (robots Crawl-delay), 30 s timeout."""
    host = urllib.parse.urlparse(url).netloc
    wait = _last_hit.get(host, 0) + min_gap - time.time()
    if wait > 0: time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = urllib.request.urlopen(req, timeout=30).read()
    _last_hit[host] = time.time()
    return data if binary else data.decode("utf-8", "replace")

def strip(s):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", s))).strip()

def cells(row_html):
    return [strip(c) for c in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row_html)]

def now_local():
    return dt.datetime.now(TZ).replace(tzinfo=None)

def guess_year(month, day, ref):
    """Year for a yearless M/D, choosing the candidate closest to ref (handles Dec/Jan wrap)."""
    best = None
    for y in (ref.year - 1, ref.year, ref.year + 1):
        try:
            d = dt.datetime(y, month, day)
        except ValueError:
            continue
        if best is None or abs(d - ref) < abs(best - ref):
            best = d
    return best

def day_iso(d):
    return d.strftime("%Y-%m-%dT00:00")   # date-only sources: midnight local, flagged eta_time=false

def entry(vessel, port, terminal, eta, etd=None, **extra):
    r = {"vessel": vessel.strip(), "service": "", "terminal": terminal, "agent": "",
         "eta": eta, "etd": etd, "port": port}
    r.update(extra)
    return r

# --- Aberdeen: Port of Grays Harbor. The "Vessel Schedule" table on
# https://www.portofgraysharbor.com/terminal-tariffs-and-resources is a Squarespace block synced
# (data-gss-sync) from this published-to-web Google Sheet; the CSV export is the live source.
GH_PAGE = "https://www.portofgraysharbor.com/terminal-tariffs-and-resources"
GH_CSV = ("https://docs.google.com/spreadsheets/d/e/2PACX-1vTpAomeTT0eQnICFNJZD2-7wMPnOBeK_3wGTR_"
          "Uf2FOr7UibmUqkliQyL2A9QuzSC_VvbBS7rVo3dpD/pub?output=csv")

def parse_grays_harbor(csv_text, ref):
    out = []
    for rec in csv.DictReader(io.StringIO(csv_text)):
        rec = {(k or "").strip().lower(): (v or "").strip() for k, v in rec.items()}
        name, eta, berth = rec.get("vessel name") or rec.get("ship"), rec.get("eta") or rec.get("date"), rec.get("berth") or rec.get("terminal")
        m = re.match(r"^(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?$", eta or "")
        if not name or not m:
            continue
        mo, dd, yy = int(m.group(1)), int(m.group(2)), m.group(3)
        d = dt.datetime(int(yy) + (2000 if len(yy) == 2 else 0), mo, dd) if yy else guess_year(mo, dd, ref)
        out.append(entry(name, "Aberdeen", berth or "", day_iso(d), None, eta_time=False))
    return out

def fetch_grays_harbor(ref):
    return parse_grays_harbor(get(GH_CSV), ref), GH_CSV, True

# --- Olympia: RSS of "Vessel Announcement" posts; each links a MailerLite newsletter whose body reads
# "The <ship> is expected to arrive at the Port of Olympia's Marine Terminal on <Month D, YYYY>."
OLY_FEED = "https://portolympia.com/category/vessel-announcement/feed/"
OLY_DATE = re.compile(r"(?:expected to arrive|arrived|arrive)\b[^.]{0,120}?\bon\s+([A-Z][a-z]+\.? \d{1,2},? \d{4})")

def parse_olympia_feed(xml):
    items = []
    for it in re.findall(r"(?s)<item>(.*?)</item>", xml):
        g = lambda k: htmlmod.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", (re.search(r"(?s)<%s>(.*?)</%s>" % (k, k), it) or [None, ""])[1])).strip()
        t = g("title")
        m = re.search(r"Arrival of (?:the )?(.+)$", t, re.I)
        if not m: continue
        pub = dt.datetime.strptime(g("pubDate")[:25].strip(), "%a, %d %b %Y %H:%M:%S")
        items.append({"vessel": m.group(1).strip(), "pub": pub, "link": g("link").split("#")[0]})
    return items

def parse_olympia_letter(html, fallback):
    m = OLY_DATE.search(strip(html))
    if m:
        s = m.group(1).replace(",", "").replace(".", "")
        for f in ("%B %d %Y", "%b %d %Y"):
            try: return dt.datetime.strptime(s, f), True
            except ValueError: pass
    return fallback, False

def fetch_olympia(ref, max_items=4):
    out = []
    for it in parse_olympia_feed(get(OLY_FEED))[:max_items]:
        d, exact = it["pub"], False
        if (ref - it["pub"]).days <= 45:       # only open the newsletter for recent posts
            try:
                d, exact = parse_olympia_letter(get(it["link"], min_gap=2), it["pub"])
            except Exception as e:
                print("olympia letter fetch failed:", e, file=sys.stderr)
        out.append(entry(it["vessel"], "Olympia", "Marine Terminal", day_iso(d), None, eta_time=False,
                         eta_source="announcement" if exact else "post date"))
    return out, OLY_FEED, True

# --- Everett: https://www.portofeverett.com/seaport/shipping_schedule.php
# "As of <date>" + table Anticipated Arrival (D-Mon) | Steamship Line | Vessel Name | Cargo.
EV_URL = "https://www.portofeverett.com/seaport/shipping_schedule.php"

def parse_everett(html):
    m = re.search(r"As of\s+([A-Z][a-z]+ \d{1,2},? \d{4})", strip(html))
    asof = dt.datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y") if m else now_local()
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        c = cells(tr)
        if len(c) < 3: continue
        mm = re.match(r"^(\d{1,2})-([A-Za-z]{3})$", c[0])
        if not mm: continue
        d = dt.datetime.strptime("%s %s %d" % (mm.group(1), mm.group(2), asof.year), "%d %b %Y")
        if d < asof - dt.timedelta(days=60): d = d.replace(year=asof.year + 1)
        out.append(entry(c[2], "Everett", "", day_iso(d), None, eta_time=False, agent_line=c[1],
                         cargo=c[3] if len(c) > 3 else ""))
    return out, asof

def fetch_everett(ref):
    rows, asof = parse_everett(get(EV_URL))
    return rows, EV_URL, True, asof

# --- Port Angeles: https://portofpa.com/marine/terminal-facilities/ship-schedule/
# ninja_tables, one per terminal per year (aria-label "2025 Schedule Terminal 1"); Vessel Name | ETA | ETD (M/D/YY).
PA_URL = "https://portofpa.com/marine/terminal-facilities/ship-schedule/"

def parse_port_angeles(html):
    out, seen = [], set()
    for m in re.finditer(r'(?is)<table[^>]*aria-label="([^"]*)"[^>]*id="footable_(\d+)"(.*?)</table>', html):
        label, tid, body = m.group(1), m.group(2), m.group(3)
        if tid in seen: continue
        seen.add(tid)
        tm = re.search(r"Terminal\s*(\d+)", label)
        term = "T" + tm.group(1) if tm else ""
        for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body):
            c = cells(tr)
            if len(c) < 3: continue
            try:
                a = dt.datetime.strptime(c[1], "%m/%d/%y"); b = dt.datetime.strptime(c[2], "%m/%d/%y")
            except ValueError:
                continue
            out.append(entry(c[0], "Port Angeles", term, day_iso(a), b.strftime("%Y-%m-%dT23:59"), eta_time=False))
    return out

def fetch_port_angeles(ref):
    return parse_port_angeles(get(PA_URL)), PA_URL, True

# --- Columbia River Pilots (COLRIP) dispatch. vessel-locations gives "Longview - LGV 7" / "Vancouver - VAN 3";
# dispatch-status gives arrivals / harbor moves / sailings with "HHMM Ddd Mon DD (Est.|Set|Away)" (no year).
CR_STATUS = "https://colrip.com/dispatch-info/dispatch-status/"
CR_LOC = "https://colrip.com/dispatch-info/vessel-locations/"
CR_PORTS = {"Longview": "Longview", "Vancouver": "Vancouver WA"}
CR_TIME = re.compile(r"^(\d{4}) ([A-Z][a-z]{2}) ([A-Z][a-z]{2}) (\d{1,2})")

def cr_when(s, ref):
    m = CR_TIME.match(s or "")
    if not m: return None
    hhmm, wd, mon, dd = m.groups()
    mo = dt.datetime.strptime(mon, "%b").month
    for y in (ref.year, ref.year - 1, ref.year + 1):          # weekday pins the year
        try: d = dt.datetime(y, mo, int(dd), int(hhmm[:2]), int(hhmm[2:]))
        except ValueError: continue
        if d.strftime("%a") == wd: return d
    return guess_year(mo, int(dd), ref)

def parse_colrip(status_html, loc_html, ref):
    loc = {}
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", loc_html):
        c = cells(tr)
        if len(c) >= 2 and " - " in c[1]:
            city, berth = c[1].split(" - ", 1)
            loc[c[0].upper()] = (city.strip(), berth.strip())
    tables = {}
    for name, body in re.findall(r'(?is)class="typehead">\s*([^<]+?)\s*</div>.*?<table[^>]*>(.*?)</table>', status_html):
        tables[name.strip()] = [cells(tr) for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", body)]
    berth_port = {}
    for v, (city, berth) in loc.items():
        if city in CR_PORTS: berth_port[berth] = CR_PORTS[city]
    def port_of(berth):
        if berth in berth_port: return berth_port[berth]
        if re.match(r"^(LGV|LA|WLOG|EGT|LON)", berth or ""): return "Longview"
        if re.match(r"^(VAN|UGC|JTM|T5$)", berth or ""): return "Vancouver WA"
        return None
    calls = {}
    for tname in ("Astoria Arrivals", "Up-River Arrivals", "Harbor Moves"):
        for c in tables.get(tname, []):
            if len(c) < 4: continue
            p = port_of(c[2]); w = cr_when(c[3], ref)
            if p and w: calls.setdefault((c[0].upper(), c[2]), {"vessel": c[0], "port": p, "berth": c[2], "eta": w, "etd": None})
    for tname in ("Harbor Moves", "Sailings"):
        for c in tables.get(tname, []):
            if len(c) < 4: continue
            p = port_of(c[1]); w = cr_when(c[3], ref)
            if not (p and w): continue
            k = (c[0].upper(), c[1])
            calls.setdefault(k, {"vessel": c[0], "port": p, "berth": c[1], "eta": None, "etd": None})["etd"] = w
    for v, (city, berth) in loc.items():                          # at berth now, no move scheduled
        if city in CR_PORTS and not any(k[0] == v for k in calls):
            calls[(v, berth)] = {"vessel": v, "port": CR_PORTS[city], "berth": berth, "eta": None, "etd": None}
    out = []
    for c in calls.values():
        eta = c["eta"].strftime("%Y-%m-%dT%H:%M") if c["eta"] else None
        etd = c["etd"].strftime("%Y-%m-%dT%H:%M") if c["etd"] else None
        out.append(entry(c["vessel"], c["port"], c["berth"], eta, etd, at_berth=c["eta"] is None))
    return out

def colrip_fresh(rows, ref, back_h=36, ahead_h=96):
    """The COLRIP pages keep a fresh "Last Updated" stamp even when the data is frozen (seen Oct 2026: rows from
    Jul 2025). Trust the feed only if at least one move time falls near now; otherwise return nothing."""
    lo, hi = ref - dt.timedelta(hours=back_h), ref + dt.timedelta(hours=ahead_h)
    for r in rows:
        for k in ("eta", "etd"):
            if r.get(k) and lo <= dt.datetime.fromisoformat(r[k]) <= hi:
                return True
    return False

def fetch_colrip(ref):
    rows = parse_colrip(get(CR_STATUS), get(CR_LOC, min_gap=2), ref)
    if not colrip_fresh(rows, ref):
        return rows, CR_STATUS, False
    return rows, CR_STATUS, True

# --- The Ship Report (Columbia River daily traffic). OPT-IN ONLY: "© ... All Rights Reserved"; ask first.
SR_URL = "https://shipreport.net/columbia-river-ship-traffic/"
SR_PORT = [(re.compile(r"\bLongview\b|\bLgv\b", re.I), "Longview"), (re.compile(r"\bVancouver\b(?! Anc)|\bVan\b", re.I), "Vancouver WA")]

def sr_time(s, base):
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)|(Noon|Midnight)", s.strip(), re.I)
    if not m: return None
    if m.group(4): h, mi = (12 if m.group(4).lower() == "noon" else 0), 0
    else:
        h, mi = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0), int(m.group(2) or 0)
    d = base.replace(hour=h, minute=mi)
    if re.search(r"\b(Mon|Tues?|Wed|Thur?s?|Fri|Sat|Sun)\b", s[m.end():m.end() + 8]): d += dt.timedelta(days=1)
    return d

def parse_shipreport(html):
    t = strip(html)
    md = re.search(r"Schedule\s+[A-Za-z ]{3,12},\s+([A-Z][a-z]+ \d{1,2}, \d{4})", t)   # "Mon d ay, October 19, 2026"
    if not md: return []
    base = dt.datetime.strptime(md.group(1).replace(",", ""), "%B %d %Y")
    out = []
    for tr in re.findall(r"(?is)<tr[^>]*>(.*?)</tr>", html):
        c = cells(tr)
        if len(c) < 4 or c[0] in ("Vessel", ""): continue
        vessel, travel, cargo, times = c[0], c[1], c[2], c[3]
        dest = re.split(r"(?i)^to\s+|\s+to\s+", travel)[-1] if re.search(r"(?i)(^|\s)to\s", travel) else ""
        if "Anc" in dest: continue                                  # going to an anchorage, not a berth
        for rx, port in SR_PORT:
            dep = re.match(r"Dep\s+(.+)$", travel)
            if dep and rx.search(dep.group(1)) and "Anc" not in dep.group(1):
                m = re.search(r"Dep~([^/]+)", times)
                etd = sr_time(m.group(1), base) if m else None
                out.append(entry(vessel, port, "", None, etd.strftime("%Y-%m-%dT%H:%M") if etd else None, cargo=cargo, at_berth=True))
            elif dest and rx.search(dest):
                m = re.search(r"(?:Lgv|Van)~([^/]+)", times)
                eta = sr_time(m.group(1), base) if m else None
                out.append(entry(vessel, port, "", eta.strftime("%Y-%m-%dT%H:%M") if eta else None, None, cargo=cargo))
    return out

def fetch_shipreport(ref):
    return parse_shipreport(get(SR_URL)), SR_URL, True

# (ports covered, source credit shown in the app, fetcher). Ship Report is opt-in only (copyright, ask first).
OUTPORT_SOURCES = [(("Aberdeen",), "Port of Grays Harbor vessel schedule", fetch_grays_harbor),
                   (("Olympia",), "Port of Olympia vessel announcements", fetch_olympia),
                   (("Everett",), "Port of Everett shipping schedule", fetch_everett),
                   (("Port Angeles",), "Port of Port Angeles ship schedule", fetch_port_angeles),
                   (("Longview", "Vancouver WA"), "Columbia River Pilots dispatch", fetch_colrip)]
SHIPREPORT_SOURCE = (("Longview", "Vancouver WA"), "The Ship Report (Columbia River)", fetch_shipreport)
# Date-only rows without an ETD stay "in port" this many days after the ETA date (the app uses the same table).
STAY_DAYS = {"Aberdeen": 3, "Olympia": 3, "Everett": 2, "Port Angeles": 2, "Longview": 2, "Vancouver WA": 2}

def current(rows, ref, horizon_days=45):
    """Drop calls that already departed (or, without ETD, whose assumed stay is over), rows with no times at all,
    and anything absurdly far out."""
    out = []
    for r in rows:
        eta = dt.datetime.fromisoformat(r["eta"]) if r.get("eta") else None
        etd = dt.datetime.fromisoformat(r["etd"]) if r.get("etd") else None
        end = etd or ((eta.replace(hour=0, minute=0) + dt.timedelta(days=STAY_DAYS.get(r.get("port"), 0), hours=23, minutes=59)) if eta else None)
        if end is None or end < ref: continue
        if eta and eta > ref + dt.timedelta(days=horizon_days): continue
        if eta and etd and etd < eta: continue
        out.append(r)
    return out

def latest(rows):
    ts = [r[k] for r in rows for k in ("eta", "etd") if r.get(k)]
    return max(ts)[:10] if ts else None

def fetch_outports(ref):
    """Returns (rows, status) where status is keyed by the app's port names:
    {port: {status: ok|stale|empty|error, credit, source, parsed, current, latest}}."""
    rows, meta = [], {}
    srcs = list(OUTPORT_SOURCES)
    if os.environ.get("OUTPORTS_SHIPREPORT") == "1":
        srcs.append(SHIPREPORT_SOURCE)
    for ports, credit, fn in srcs:
        try:
            res = fn(ref)
            got, url, trusted = res[0], res[1], res[2]
            cur = current(got, ref) if trusted else []
            st = {"status": "ok" if cur else ("stale" if got else "empty"), "credit": credit, "source": url,
                  "parsed": len(got), "current": len(cur), "latest": latest(got)}
            if len(res) > 3: st["as_of"] = res[3].date().isoformat()
            rows += cur
        except Exception as e:
            st = {"status": "error", "credit": credit, "error": "%s: %s" % (type(e).__name__, e)}
            print("outport %s failed: %s" % (credit, e), file=sys.stderr)
        for p in ports:
            prev = meta.get(p)
            if prev and prev.get("status") == "ok":   # keep an earlier good source for the port
                continue
            meta[p] = dict(st, current=sum(1 for r in rows if r.get("port") == p)) if "parsed" in st else st
    return rows, meta

# --------------------------------------------------------------------------- main
def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "vessels.json"
    if len(sys.argv) > 2:
        data = open(sys.argv[2], "rb").read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "local19-hours-vessel-fetch/1.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
    rows, updated = parse(data)
    if not any(r["port"] == "Seattle" for r in rows) or not updated:
        sys.exit("parse produced no Seattle rows / no timestamp - leaving %s untouched" % out)
    meta = {}
    if os.environ.get("OUTPORTS", "1") != "0":
        extra, meta = fetch_outports(now_local())
        rows += extra
    rows.sort(key=lambda r: (r["eta"] or "", r["port"], r["terminal"]))
    if os.environ.get("NO_IMO") != "1":
        resolve_ids(rows, os.path.join(os.path.dirname(os.path.abspath(out)), "vessel_ids.json"))
    payload = {"source": URL, "timezone": "America/Los_Angeles", "updated": updated,
               "note": "Times are Pacific local. Schedule subject to change; T91 is cruise (no container calls). "
                       "Outport rows with eta_time=false carry a date only (time shown as 00:00).",
               "outports": meta, "vessels": rows}
    try:
        old = json.load(open(out))
    except Exception:
        old = None
    if old and old.get("vessels") == rows and old.get("updated") == updated:
        print("no change"); return
    json.dump(payload, open(out, "w"), indent=1)
    from collections import Counter
    print("wrote %d vessels, updated %s; per port %s" % (len(rows), updated, dict(Counter(r["port"] for r in rows))))
    for k, v in meta.items(): print("  outport", k, v)

if __name__ == "__main__":
    main()
