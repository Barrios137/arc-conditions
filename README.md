# arc-conditions

Hourly JSON mirror of the public **Map Conditions** schedule that Embark Studios publishes at
<https://arcraiders.com/map-conditions>, so that client-side tools (browser widgets, overlays)
can read it with a plain `fetch`. The page itself sends no CORS headers; this repository serves
the same facts through `raw.githubusercontent.com`, which does.

- `schedule.json` — the current schedule (Europe base times plus per-region start times for
  North America, Brazil, East Asia and Oceania), about 24 h ahead, regenerated every hour by
  the GitHub Action in `.github/workflows/mirror.yml` with `conditions.py`.
- Read it from: `https://raw.githubusercontent.com/Barrios137/arc-conditions/main/schedule.json`

## Format

```json
{
  "generatedAt": "2026-10-13T06:45:28Z",
  "source": "https://arcraiders.com/map-conditions",
  "serverNow": 1791873928963,
  "horizonEnd": 1791997200,
  "regions": { "europe": 0, "north-america": 7, "brazil": 6, "east-asia": -5, "oceania": -9 },
  "conditions": { "night-raid": { "name": "Night Raid", "type": "major" } },
  "maps": { "buried-city": "Buried City" },
  "entries": [ { "c": "night-raid", "m": "buried-city", "s": 1791846000, "e": 1791849600,
                 "r": { "north-america": 1791871200, "brazil": 1791867600, "east-asia": 1791828000, "oceania": 1791813600 } } ]
}
```

Times are Unix seconds except `serverNow` (milliseconds, as the source). `regions` are hour
offsets relative to the Europe base; each entry also carries the explicit per-region start in
`r`. A condition lasts `e - s` seconds (3600 today).

## Conduct

One request per hour from a GitHub runner, with an identifiable User-Agent and a contact
address; `robots.txt` is respected. If Embark publishes an official feed, this mirror will switch
to it or shut down. This is a community resource and is not affiliated with Embark Studios AB or
Nexon. ARC RAIDERS is a trademark of Embark Studios AB.

Maintained by Simple Code · legal@simple-code.cloud
