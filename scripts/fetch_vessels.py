#!/usr/bin/env python3
"""Download the NWSA Vessel Schedule Forecast PDF and write a compact vessels.json
with the Seattle terminal calls (T5, T18, plus any other Seattle terminal listed).
Requires: pip install pymupdf.  Usage: fetch_vessels.py [out.json] [local.pdf]"""
import json, re, sys, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
import pymupdf

URL = "https://docs.nwseaportalliance.com/Vessel/Schedule.pdf"
TZ = ZoneInfo("America/Los_Angeles")
DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
TIME = re.compile(r"^\d{1,2}:\d{2}$")

def iso(d, t):
    m, dd, y = map(int, d.split("/")); h, mi = map(int, t.split(":"))
    return "%04d-%02d-%02dT%02d:%02d" % (y, m, dd, h, mi)

def parse(pdf_bytes):
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    rows, updated, cols = [], None, None
    for page in doc:
        words = page.get_text("words")
        text = " ".join(w[4] for w in words)
        m = re.search(r"Last refreshed:\s*(\d{1,2}/\d{1,2}/\d{4})\s+(\d{1,2}:\d{2}:\d{2})\s*([AP]M)", text)
        if m and not updated:
            u = dt.datetime.strptime(m.group(1) + " " + m.group(2) + " " + m.group(3), "%m/%d/%Y %I:%M:%S %p")
            updated = u.replace(tzinfo=TZ).isoformat(timespec="seconds")
        if "Container Vessels" not in text and cols is None:
            continue
        # column x positions from the header row (re-read per page when present)
        hdr = {}
        for w in sorted(words, key=lambda w: w[1]):  # topmost occurrence = header row
            if w[4] in ("Service", "Agent", "ETA", "ETD") and w[4] not in hdr and w[1] < 400:
                hdr[w[4]] = w[0]
        vn = [w for w in words if w[4] == "Vessel" and w[1] < 400]
        if all(k in hdr for k in ("Service", "Agent", "ETA", "ETD")) and vn:
            vx = min(w[0] for w in vn)
            if "Type" not in [w[4] for w in words if w[1] < 400]:  # container table: no Vessel Type column
                cols = (hdr["Service"], vx, hdr["Agent"], hdr["ETA"], hdr["ETD"])
        if cols is None or "Breakbulk" in text[:200] or "Tacoma Container" in text[:200]:
            continue
        starts = []
        for i, w in enumerate(words):
            if w[4] == "Seattle" and w[0] < cols[0] - 100 and w[1] > 360:
                nxt = next((x for x in words[i + 1:i + 3] if re.match(r"^T\d+$|^Pier|^\d+$", x[4])), None)
                if nxt and abs(nxt[1] - w[1]) < 10:
                    starts.append((w[1], w, nxt))
        for k, (y, w, tw) in enumerate(starts):
            y1 = starts[k + 1][0] - 5 if k + 1 < len(starts) else y + 150
            band = [x for x in words if y - 5 <= x[1] < y1 and x[4].strip()]
            col = lambda x0, lo, hi: " ".join(b[4] for b in sorted(band, key=lambda b: (round(b[1] / 8), b[0])) if lo <= b[0] < hi)
            svc, ves, agent = col(0, cols[0] - 5, cols[1] - 5), col(0, cols[1] - 5, cols[2] - 5), col(0, cols[2] - 5, cols[3] - 5)
            eta = [b[4] for b in sorted(band, key=lambda b: (b[1], b[0])) if cols[3] - 5 <= b[0] < cols[4] - 5]
            etd = [b[4] for b in sorted(band, key=lambda b: (b[1], b[0])) if b[0] >= cols[4] - 5]
            if len(eta) < 2 or len(etd) < 2 or not (DATE.match(eta[0]) and TIME.match(eta[1]) and DATE.match(etd[0]) and TIME.match(etd[1])):
                print("skip unparsable row", ves, eta, etd, file=sys.stderr); continue
            # words of the terminal column belong to "Seattle Txx"; service starts after it
            svc = re.sub(r"^(T\d+|Pier\s*\d+)\s*", "", svc)
            # service/vessel can bleed together when a long service name is used ("EB Service 1 WESTWOOD RAINIER")
            m2 = re.match(r"^(EB Service \d)\s+(.+)$", ves)
            if m2: svc, ves = m2.group(1), m2.group(2)
            rows.append({"vessel": ves.strip(), "service": svc.strip(), "terminal": tw[4], "agent": agent.strip(),
                         "eta": iso(eta[0], eta[1]), "etd": iso(etd[0], etd[1])})
    return rows, updated

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "vessels.json"
    if len(sys.argv) > 2:
        data = open(sys.argv[2], "rb").read()
    else:
        req = urllib.request.Request(URL, headers={"User-Agent": "local19-hours-vessel-fetch/1.0"})
        data = urllib.request.urlopen(req, timeout=60).read()
    rows, updated = parse(data)
    if not rows or not updated:
        sys.exit("parse produced no Seattle rows / no timestamp - leaving %s untouched" % out)
    rows.sort(key=lambda r: (r["eta"], r["terminal"]))
    for r in rows:
        r["terminal"] = {"T5": "T5", "T18": "T18"}.get(r["terminal"], r["terminal"])
    payload = {"source": URL, "timezone": "America/Los_Angeles", "updated": updated,
               "note": "Times are Pacific local. Schedule subject to change; T91 is cruise (no container calls).",
               "vessels": rows}
    try:
        old = json.load(open(out))
    except Exception:
        old = None
    if old and old.get("vessels") == rows and old.get("updated") == updated:
        print("no change"); return
    json.dump(payload, open(out, "w"), indent=1)
    print("wrote %d vessels, updated %s" % (len(rows), updated))

if __name__ == "__main__":
    main()
