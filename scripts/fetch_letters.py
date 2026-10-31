#!/usr/bin/env python3
"""Copy the daily ship move letters from the GroupMe "Ship Letters" group into the app's private Firestore room.

READ-ONLY toward GroupMe: only HTTP GET (list messages, download images). Never posts, likes, joins, leaves or changes anything there.
Secrets come from the environment only (GROUPME_TOKEN, LETTERS_FB_REFRESH) and are never printed or written to a file.
Letters are written to Firestore rooms/<room>/letters (member-gated by the app's room code), never to this public repo.
"""
import base64, io, json, os, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

GM_API = os.environ.get("GROUPME_API", "https://api.groupme.com/v3").rstrip("/")
GROUP = os.environ.get("GROUPME_GROUP_ID", "112213694")
ROOM = (os.environ.get("LETTERS_ROOM") or "LOCAL19").strip().upper()
POSTER = (os.environ.get("LETTERS_POSTER") or "").strip().lower()   # empty = ANY image in the group is a letter
SHOW_DAYS = int(os.environ.get("LETTERS_DAYS") or 30)
KEEP_DAYS = SHOW_DAYS + 5
PROJECT = os.environ.get("FIREBASE_PROJECT", "ilwu-life-chat")
API_KEY = os.environ.get("FIREBASE_API_KEY", "AIzaSyAskyTwFl7zd0ferXLF7EmDvOU1CE33oeE")  # public web key, same as the app
EMU = os.environ.get("FIRESTORE_EMULATOR_HOST", "")
FS = ("http://" + EMU) if EMU else "https://firestore.googleapis.com"
DOCS = FS + "/v1/projects/" + PROJECT + "/databases/(default)/documents"
MAX_FULL = 640000          # raw bytes of the full picture (base64 must stay under the 1 MB document limit)
MAX_DELETES = 20           # safety: never wipe more than this in one run
UA = "l19-letters/1"
ALLOW_HOSTS = tuple(h for h in (os.environ.get("LETTERS_ALLOW_HOSTS") or "groupme.com").split(",") if h)
TOKEN = os.environ.get("GROUPME_TOKEN", "").strip()
DRY = os.environ.get("LETTERS_DRY_RUN", "") in ("1", "true", "True")   # read GroupMe + OCR only, write nothing


def log(*a):
    print(*a, flush=True)


def warn(msg):
    log("::warning::" + msg)


class Denied(Exception):
    pass


def gm_get(path, **q):
    """GET only. The token travels in a header so it can never end up in a URL, log or exception text."""
    url = GM_API + path + ("?" + urllib.parse.urlencode(q) if q else "")
    req = urllib.request.Request(url, method="GET", headers={"X-Access-Token": TOKEN, "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)


def img_get(url):
    p = urllib.parse.urlparse(url)
    h = (p.hostname or "").lower()
    if p.scheme not in ("https", "http") or not any(h == a or h.endswith("." + a) for a in ALLOW_HOSTS):
        raise ValueError("image host not allowed")
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        b = r.read(15_000_001)
    if len(b) > 15_000_000:
        raise ValueError("image too large")
    return b


def fb_token():
    t = os.environ.get("LETTERS_TEST_ID_TOKEN")
    if t:
        return t
    rt = os.environ.get("LETTERS_FB_REFRESH", "").strip()
    if not rt:
        return ""
    body = urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": rt}).encode()
    req = urllib.request.Request("https://securetoken.googleapis.com/v1/token?key=" + API_KEY, data=body, method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["id_token"]


def fs_req(method, url, tok, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            raise Denied("Firestore refused (%d)" % e.code)
        if e.code == 404 and method in ("GET", "DELETE"):
            return {}
        raise


def encode_img(raw):
    from PIL import Image, ImageOps
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    out = None
    for mx in (1600, 1400, 1200, 1000):
        k = min(1.0, mx / max(im.size))
        z = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS) if k < 1 else im
        for q in (80, 72, 64, 56):
            b = io.BytesIO()
            z.save(b, "JPEG", quality=q, optimize=True, progressive=True)
            if b.tell() <= MAX_FULL:
                out = (b.getvalue(), z.width, z.height)
                break
        if out:
            break
    if not out:
        raise ValueError("picture too detailed to shrink")
    th = im.copy()
    th.thumbnail((240, 240), Image.LANCZOS)
    tb = io.BytesIO()
    th.save(tb, "JPEG", quality=62, optimize=True)
    return out[0], out[1], out[2], tb.getvalue(), th.width, th.height


def dataurl(b):
    return "data:image/jpeg;base64," + base64.b64encode(b).decode()


def i(n):
    return {"integerValue": str(int(n))}


def s(v):
    return {"stringValue": v}


def list_existing(tok):
    ids, tk = {}, None
    while True:
        u = DOCS + "/rooms/" + ROOM + "/letters?pageSize=300&mask.fieldPaths=t" + ("&pageToken=" + urllib.parse.quote(tk) if tk else "")
        r = fs_req("GET", u, tok)
        for d in r.get("documents", []):
            ids[d["name"].rsplit("/", 1)[1]] = int(d.get("fields", {}).get("t", {}).get("integerValue", "0"))
        tk = r.get("nextPageToken")
        if not tk:
            return ids


def gm_window(cutoff):
    """messages newer than cutoff, newest first. complete=True when we reached the cutoff or the start of the group."""
    msgs, before, complete = [], None, False
    for _ in range(30):
        q = {"limit": 100}
        if before:
            q["before_id"] = before
        try:
            r = gm_get("/groups/" + GROUP + "/messages", **q)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                complete = True
                break
            raise
        page = (r.get("response") or {}).get("messages") or []
        if not page:
            complete = True
            break
        msgs += page
        before = page[-1]["id"]
        if page[-1]["created_at"] < cutoff or len(page) < 100:
            complete = True
            break
    return msgs, complete


_ocr = {"engine": None, "known": None, "off": False}


def read_letter(raw):
    """OCR the letter (on this runner) and match its vessel to the known ships. Never fatal: a letter that can't be read is simply unmatched."""
    if _ocr["off"]:
        return {}
    try:
        import letters_match as LM
        if _ocr["engine"] is None:
            from rapidocr_onnxruntime import RapidOCR
            _ocr["engine"] = RapidOCR()
            root = os.path.dirname(HERE)
            _ocr["known"] = LM.load_known(os.path.join(root, "vessels.json"), os.path.join(root, "vessel_ids.json"))
        return LM.parse(LM.ocr_lines(raw, _ocr["engine"]), _ocr["known"])
    except ImportError:
        _ocr["off"] = True
        warn("OCR is not installed; letters are copied without a ship match.")
    except Exception as e:
        log("could not read letter text -", type(e).__name__, str(e)[:80])
    return {}


def meta_fields(info):
    f = {}
    for k in ("v", "vr", "vk", "imo", "voy", "ld", "sh", "tm", "ms", "ocr"):
        if isinstance(info.get(k), str) and info[k]:
            f[k] = s(info[k][:1500 if k == "ocr" else 60])
    if isinstance(info.get("sc"), int) and info["sc"]:
        f["sc"] = i(info["sc"])
    return f


def main():
    if not TOKEN:
        warn("GROUPME_TOKEN secret is not set; nothing to do.")
        return 0
    if DRY:
        log("DRY RUN: GroupMe is read and the letters are OCR'd, nothing is written anywhere.")
    try:
        tok = fb_token() if not DRY else "dry"
    except Exception as e:
        log("Could not get a Firebase sign-in for the letters bot:", type(e).__name__)
        return 1
    if not tok and not DRY:
        warn("LETTERS_FB_REFRESH secret is not set; nothing to do.")
        return 0
    now = time.time()
    try:
        existing = {} if DRY else list_existing(tok)
    except Denied:
        warn("Firestore refused the letters bot: the letters rules are not published yet (or the bot uid is not allowed). Nothing written.")
        return 0
    msgs, complete = gm_window(now - SHOW_DAYS * 86400)
    log("GroupMe: %d messages read (window complete: %s); %d letters already stored" % (len(msgs), complete, len(existing)))
    if not msgs:
        warn("GroupMe returned no messages; leaving stored letters untouched.")
        return 0
    want = {}
    for m in msgs:
        if m.get("system") or m["created_at"] < now - SHOW_DAYS * 86400:
            continue
        if POSTER and (m.get("name") or "").strip().lower() != POSTER:
            continue
        imgs = [a.get("url") for a in (m.get("attachments") or []) if a.get("type") == "image" and a.get("url")]
        for n, u in enumerate(imgs):
            want[m["id"] if n == 0 else "%s-%d" % (m["id"], n + 1)] = (m["created_at"] * 1000, u)
    added = failed = 0
    for lid, (ms, url) in sorted(want.items(), key=lambda x: x[1][0]):
        if lid in existing:
            continue
        try:
            raw = img_get(url)
            full, w, h, th, tw, thh = encode_img(raw)
            info = read_letter(raw)
            if DRY:
                added += 1
                log("would add", lid, "%dx%d" % (w, h), "| ship:", info.get("v") or "(not matched)", "[%s]" % (info.get("ms") or "-"), "| read:", info.get("vr") or "-", "| voy", info.get("voy") or "-", "| date", info.get("ld") or "-")
                continue
            fs_req("PATCH", DOCS + "/rooms/" + ROOM + "/letters/" + lid + "/img/full", tok,
                   {"fields": {"data": s(dataurl(full)), "w": i(w), "h": i(h)}})
            fs_req("PATCH", DOCS + "/rooms/" + ROOM + "/letters/" + lid, tok,
                   {"fields": dict({"t": i(ms), "w": i(w), "h": i(h), "thumb": s(dataurl(th)), "tw": i(tw), "th": i(thh)}, **meta_fields(info))})
            added += 1
            log("added letter", lid, "%dx%d" % (w, h), "%d KB" % (len(full) // 1024), "| ship:", info.get("v") or "(not matched)", "[%s]" % (info.get("ms") or "-"))
        except Denied:
            warn("Firestore refused a write: letters rules not published (or bot uid not allowed).")
            return 0
        except Exception as e:
            failed += 1
            log("could not copy letter", lid, "-", type(e).__name__, str(e)[:80])
    removed = 0
    if complete and not DRY:
        gone = [l for l, t in existing.items() if (l not in want and t >= (now - SHOW_DAYS * 86400) * 1000) or t < (now - KEEP_DAYS * 86400) * 1000]
        if len(gone) > MAX_DELETES:
            warn("%d letters look deleted; refusing to remove more than %d in one run." % (len(gone), MAX_DELETES))
            gone = gone[:MAX_DELETES]
        for l in gone:
            try:
                fs_req("DELETE", DOCS + "/rooms/" + ROOM + "/letters/" + l + "/img/full", tok)
                fs_req("DELETE", DOCS + "/rooms/" + ROOM + "/letters/" + l, tok)
            except Denied:
                warn("Firestore refused a delete: bot uid not allowed.")
                return 0
            removed += 1
            log("removed letter", l)
    log("done: %d added, %d removed, %d failed, %d letters in window" % (added, removed, failed, len(want)))
    return 1 if failed and not added else 0   # every new letter failed: show a red run so it gets noticed


if __name__ == "__main__":
    sys.exit(main())
