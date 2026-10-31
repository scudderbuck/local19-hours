"""Read the vessel name (and voyage / date / shift / terminal when readable) from a ship move letter picture, then match it to the known ships.
OCR runs locally on the GitHub runner (rapidocr-onnxruntime); nothing is sent to any OCR service."""
import difflib, io, json, re

DIGIT_FIX = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "6": "G"})
PREFIXES = ["CMA CGM", "MSC", "OOCL", "COSCO", "EXPRESS", "WESTWOOD", "XIN", "SM", "MH", "CAPE", "ONE", "HMM", "EVER", "ZIM", "APL", "MAERSK", "ARC", "NYK", "YM", "WAN HAI", "HYUNDAI", "LONG BEACH", "SEASPAN"]


def vkey(name):
    """Same normalisation as the app's glVk(): upper case, look-alike digits to letters, letters only."""
    return re.sub(r"[^A-Z]", "", str(name or "").upper().translate(DIGIT_FIX))


def load_known(vessels_json, ids_json):
    """-> {vkey: {"name":..., "imo":..., "sched":bool}}"""
    known = {}
    try:
        for v in json.load(open(vessels_json)).get("vessels", []):
            n = (v.get("vessel") or "").strip()
            if n:
                known[vkey(n)] = {"name": n, "imo": v.get("imo") or "", "sched": True}
    except Exception:
        pass
    try:
        for n, d in json.load(open(ids_json)).items():
            k = vkey(n)
            if k and k not in known:
                known[k] = {"name": n, "imo": (d or {}).get("imo") or "", "sched": False}
    except Exception:
        pass
    return known


def ocr_lines(raw, engine=None):
    from PIL import Image, ImageOps
    import numpy as np
    if engine is None:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
    im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
    r, _ = engine(np.array(im))
    rows = sorted(((sum(p[1] for p in b[:4]) / 4, b[0][0], t) for b, t, c in (r or [])))
    return [t for _, _, t in rows]


def pretty(squash_or_text):
    """OCR often drops spaces ("CMACGMFORTJAMES"): put a space after a known carrier prefix."""
    s = re.sub(r"\s+", " ", str(squash_or_text or "").strip().upper())
    first, _, rest = s.partition(" ")
    for p in sorted(PREFIXES, key=len, reverse=True):
        q = p.replace(" ", "")
        if first.startswith(q) and len(first) > len(q) + 2:
            return (p + " " + first[len(q):] + (" " + rest if rest else "")).strip()
    return s


def best_known(text, known):
    k = vkey(text)
    if len(k) < 4:
        return None
    if k in known:
        return known[k], 100
    scored = sorted(((difflib.SequenceMatcher(None, k, kk).ratio(), kk) for kk in known), reverse=True)[:2]
    if scored and scored[0][0] >= 0.84 and (len(scored) < 2 or scored[0][0] - scored[1][0] >= 0.04):
        return known[scored[0][1]], int(scored[0][0] * 100)
    return None


def parse(lines, known):
    text = "\n".join(lines)
    out = {"v": "", "vr": "", "vk": "", "imo": "", "ms": "", "sc": 0, "voy": "", "ld": "", "sh": "", "tm": ""}
    read = ""
    for t in lines:
        m = re.search(r"VESS?EL\W{0,3}(.+)", t, re.I)
        if m:
            v = re.split(r"\b(VOY|JOB|DATE|SHIFT|TOWER|TIME)\b", m.group(1), flags=re.I)[0]
            v = re.sub(r"[^A-Za-z0-9 &.\-]", "", v).strip(" -.")
            if len(vkey(v)) >= 3:
                read = v
                break
    src = "vessel"
    if not read:  # file-name style header: "43098 MSC DENISSE X LETTERS", "COSCO VENICE 81N - OPS LETTERS"
        for t in lines:
            m = re.search(r"^(.*?)(OPS\s*)?LETTERS?\b", t, re.I)
            if m and len(vkey(m.group(1))) >= 5:
                v = re.sub(r"^[\d\s\-]+", "", m.group(1))
                v = re.sub(r"[\s\-]*\d+[A-Za-z]?([\-/ ]\d*[A-Za-z]?)*\s*$", "", v).strip(" -")
                if len(vkey(v)) >= 5:
                    read, src = v, "title"
                    break
    hit = best_known(read, known) if read else None
    if not hit and not read:  # no vessel line: accept a known ship name written in the picture ONLY if it is the single one (a working plan lists many ships)
        sq = vkey(text)
        found = [kk for kk in known if len(kk) >= 7 and kk in sq]
        found = [kk for kk in found if not any(kk != o and kk in o for o in found)]
        if len(found) == 1:
            hit, src, read = (known[found[0]], 90), "scan", known[found[0]]["name"]
    if hit:
        info, sc = hit
        out.update(v=info["name"], vk=vkey(info["name"]), imo=info["imo"], ms="sched" if info["sched"] else "list", sc=sc)
    elif read and src == "vessel":
        out.update(v=pretty(read), vk=vkey(read), ms="read", sc=0)
    # a name taken only from a file-name style header that matches no known ship is not trusted: the letter stays unmatched
    out["vr"] = read[:60]
    m = re.search(r"VOY\W{0,3}([A-Z0-9][A-Z0-9/\-]{2,14})", text, re.I)
    if m:
        out["voy"] = m.group(1).upper()
    d = re.search(r"(?:DATE\W{0,3}|\b)(\d{1,2})/(\d{1,2})\D{0,2}(20\d{2})", text)
    if d:
        mo, da, yr = int(d.group(1)), int(d.group(2)), int(d.group(3))
        if 1 <= mo <= 12 and 1 <= da <= 31:
            out["ld"] = "%04d-%02d-%02d" % (yr, mo, da)
    m = re.search(r"SHIFT\W{0,3}(DAY|NIGHT)", text, re.I) or re.search(r"TERMINAL\W{0,3}\d+\W{0,5}(DAY|NIGHT)", text, re.I)
    if m:
        out["sh"] = m.group(1).upper()
    m = re.search(r"TERMINAL\W{0,3}(\d{1,3})", text, re.I)
    if m:
        out["tm"] = "T" + m.group(1)
    out["ocr"] = re.sub(r"[ \t]+", " ", text)[:1500]
    return out
