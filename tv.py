"""Extrait le programme TV du soir (TNT) depuis le flux XMLTV public de xmltvfr.fr
et l'écrit dans tv.json, un petit fichier lu par le tableau de bord « Maison »."""
import gzip, io, json, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SOURCE = "https://xmltvfr.fr/xmltv/xmltv_tnt.xml"
PARIS = ZoneInfo("Europe/Paris")
now = datetime.now(PARIS)
days = [(now + timedelta(days=d)).date() for d in (0, 1)]

def parse_time(s):
    # format XMLTV : 20261118210500 +0100
    return datetime.strptime(s.strip(), "%Y%m%d%H%M%S %z").astimezone(PARIS)

req = urllib.request.Request(SOURCE, headers={"User-Agent": "maison-dashboard/1.0", "Accept-Encoding": "gzip"})
raw = urllib.request.urlopen(req, timeout=120).read()
if raw[:2] == b"\x1f\x8b":
    raw = gzip.decompress(raw)

names, order, out = {}, [], {d.isoformat(): {} for d in days}
for _, el in ET.iterparse(io.BytesIO(raw), events=("end",)):
    if el.tag == "channel":
        cid = el.get("id")
        dn = el.findtext("display-name") or cid
        names[cid] = dn.strip()
        order.append(cid)
        el.clear()
    elif el.tag == "programme":
        try:
            start, stop = parse_time(el.get("start")), parse_time(el.get("stop"))
        except Exception:
            el.clear(); continue
        key = start.date().isoformat()
        # soirée : programmes qui commencent entre 19 h 55 et 23 h 59
        if key in out and (start.hour > 19 or (start.hour == 19 and start.minute >= 55)):
            desc = (el.findtext("desc") or "").strip()
            out[key].setdefault(el.get("channel"), []).append({
                "start": start.strftime("%H:%M"), "stop": stop.strftime("%H:%M"),
                "title": (el.findtext("title") or "").strip(),
                "sub": (el.findtext("sub-title") or "").strip()[:80],
                "cat": (el.findtext("category") or "").strip(),
                "desc": desc[:280] + ("…" if len(desc) > 280 else ""),
            })
        el.clear()

result = {"generated": now.isoformat(timespec="minutes"), "source": "xmltvfr.fr", "days": {}}
for key, chans in out.items():
    result["days"][key] = [{"name": names.get(cid, cid), "programs": sorted(chans[cid], key=lambda p: p["start"])}
                           for cid in order if cid in chans]
with open("tv.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
print("tv.json :", {k: len(v) for k, v in result["days"].items()}, "chaînes")
