#!/usr/bin/env python3
"""Convierte la página oficial de condiciones de mapa de ARC Raiders en un JSON compacto.

Fuente: https://arcraiders.com/map-conditions (Embark). La página es Next.js y lleva el horario
incrustado en el payload RSC como ``liveEntries``; no hay API ni CORS. Este script es el corazón
del espejo (GitHub Action horaria) descrito en docs/arc-raiders-brief.md §4. Sólo biblioteca
estándar. Uso:

    python dev/arc/conditions.py                      # descarga y escribe dev/cache/arc/schedule.json
    python dev/arc/conditions.py --html pagina.html   # parsea un HTML guardado
    python dev/arc/conditions.py --out schedule.json  # ruta de salida
    python dev/arc/conditions.py --check              # sólo valida y resume, no escribe

Salida (epoch en segundos salvo serverNow, como la fuente):
    {
      "generatedAt": "2026-10-13T06:45:28Z", "source": "...", "serverNow": 1791873928963,
      "horizonEnd": 1791997200, "regions": {"europe": 0, "north-america": 7, ...},
      "conditions": {"night-raid": {"name": "Night Raid", "type": "major"}},
      "maps": {"buried-city": "Buried City"},
      "entries": [{"c": "night-raid", "m": "buried-city", "s": 1791846000, "e": 1791849600,
                   "r": {"north-america": 1791871200, ...}}]
    }
El código de salida es 1 si el parseo no supera las comprobaciones mínimas (para que la Action
no publique un JSON vacío y conserve el anterior).
"""
import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

SOURCE = "https://arcraiders.com/map-conditions"
USER_AGENT = "arc-conditions-mirror/0.1 (+https://simple-code.cloud; legal@simple-code.cloud)"
ENTRY = re.compile(
    r'\{"conditionName":"(?P<c>[^"]+)","mapDisplayName":"(?P<m>[^"]+)",'
    r'"durationInSeconds":(?P<d>\d+),"startTimestamp":(?P<s>\d+),"endTimestamp":(?P<e>\d+),'
    r'"regionTimestamps":(?P<r>\{[^}]*\})\}'
)
CONDITION = re.compile(r'\{"name":"(?P<n>[^"]+)","type":"(?P<t>major|minor)"\}')
MAPS = re.compile(r'"mapNames":\[(?P<l>[^\]]*)\]')
SERVER_NOW = re.compile(r'"serverNow":(?P<v>\d+)')


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def parse(html: str, source: str = SOURCE) -> dict:
    text = html.replace('\\"', '"')
    now_match = SERVER_NOW.search(text)
    server_now = int(now_match.group("v")) if now_match else None

    conditions = {}
    for m in CONDITION.finditer(text):
        conditions.setdefault(slug(m.group("n")), {"name": m.group("n"), "type": m.group("t")})

    maps = {}
    mm = MAPS.search(text)
    if mm:
        for name in re.findall(r'"([^"]+)"', mm.group("l")):
            maps[slug(name)] = name

    entries = []
    seen = set()
    offsets = {}
    for m in ENTRY.finditer(text):
        s = int(m.group("s")) // 1000
        e = int(m.group("e")) // 1000
        regions = json.loads(m.group("r"))
        key = (m.group("c"), m.group("m"), s)
        if key in seen:
            continue
        seen.add(key)
        c = slug(m.group("c"))
        mp = slug(m.group("m"))
        conditions.setdefault(c, {"name": m.group("c"), "type": "unknown"})
        maps.setdefault(mp, m.group("m"))
        r = {}
        for region, span in regions.items():
            start = int(span[0]) // 1000
            r[region] = start
            offsets.setdefault(region, set()).add(round((start - s) / 3600, 2))
        entries.append({"c": c, "m": mp, "s": s, "e": e, "r": r})
    entries.sort(key=lambda x: (x["s"], x["m"]))

    region_offsets = {"europe": 0}
    for region, vals in offsets.items():
        region_offsets[region] = sorted(vals)[0] if len(vals) == 1 else sorted(vals)

    horizon = max((x["e"] for x in entries), default=None)
    return {
        "generatedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "serverNow": server_now,
        "horizonEnd": horizon,
        "regions": region_offsets,
        "conditions": conditions,
        "maps": maps,
        "entries": entries,
    }


def check(data: dict) -> list:
    problems = []
    n = len(data["entries"])
    if n < 20:
        problems.append(f"solo {n} entradas (esperadas 100+)")
    if len(data["maps"]) < 5:
        problems.append(f"solo {len(data['maps'])} mapas")
    if len(data["conditions"]) < 8:
        problems.append(f"solo {len(data['conditions'])} condiciones")
    if data["serverNow"] is None:
        problems.append("sin serverNow")
    else:
        now = data["serverNow"] / 1000
        if data["horizonEnd"] is None or data["horizonEnd"] - now < 6 * 3600:
            problems.append("horizonte menor de 6 h")
        if n and not any(x["s"] <= now < x["e"] for x in data["entries"]):
            problems.append("ninguna entrada activa ahora")
    for region, off in data["regions"].items():
        if isinstance(off, list):
            problems.append(f"desfase no constante en {region}: {off}")
    bad = [x for x in data["entries"] if x["e"] - x["s"] != 3600]
    if bad:
        problems.append(f"{len(bad)} entradas no duran 3600 s")
    unknown = [c for c, v in data["conditions"].items() if v["type"] == "unknown"]
    if unknown:
        problems.append(f"condiciones sin categoria: {unknown}")
    return problems


def summary(data: dict) -> str:
    now = (data["serverNow"] or 0) / 1000

    def fmt(t):
        return dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%d %b %H:%M")

    active = [x for x in data["entries"] if x["s"] <= now < x["e"]]
    return "\n".join([
        f"entradas {len(data['entries'])}, mapas {len(data['maps'])}, condiciones {len(data['conditions'])}",
        f"serverNow {fmt(now)} UTC, horizonte hasta {fmt(data['horizonEnd'])} UTC "
        f"({(data['horizonEnd'] - now) / 3600:.1f} h)",
        f"regiones (h respecto a Europa): {data['regions']}",
        "activas ahora (Europa): " + ", ".join(f"{x['m']}={x['c']}" for x in active),
    ])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--html", help="HTML guardado en vez de descargar")
    ap.add_argument("--out", default="dev/cache/arc/schedule.json")
    ap.add_argument("--check", action="store_true", help="validar y resumir sin escribir")
    args = ap.parse_args()

    html = Path(args.html).read_text(encoding="utf-8", errors="replace") if args.html else fetch(SOURCE)
    data = parse(html, args.html or SOURCE)
    problems = check(data)
    print(summary(data))
    if problems:
        print("PROBLEMAS: " + "; ".join(problems), file=sys.stderr)
        return 1
    if not args.check:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"escrito {out} ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
