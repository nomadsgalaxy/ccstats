# ccstats — e-ink edition (Badgeware Badger 2350)

A port of the ccstats badge to the **Badgeware Badger 2350** (RP2350, 296-class
**264×176 1-bit e-ink**). It renders the same server feeds as the LCD
[`firmware/`](../firmware/) build, but as **static, mono, no-animation** stat
screens suited to e-ink's slow full refresh.

The **data layer is shared, not forked**: this build reuses
[`firmware/http_client.py`](../firmware/http_client.py) (verified HTTPS, chunked
+ keep-alive) and [`firmware/certificate_authorities.py`](../firmware/certificate_authorities.py)
(pinned roots — incl. the Google Trust Services / GlobalSign chain the public
Cloudflare edge presents) **verbatim**. Only the two files here are
badge-specific:

| File | What it is |
|---|---|
| `__init__.py` | The app: four screens (**TOKENS / USAGE / ACTIVITY / COST**), button handling, slow-refresh draw. Uses the badgewa.re `run()` framework + `screen`/`color`/`shape`/`io`/`rom_font` API. |
| `ccfetch.py` | Fetches `claude-stats.json` + `claude-limits.json`, returns a small dict cached in `State` (survives the e-ink deep-sleep/reset power cycle). |
| `secrets.example.py` | Template for `secrets.py` (WiFi + server URL/token/alias). |

## Differences from the LCD build

- **No live avatar, no animation** — e-ink can't repaint fast enough; the badge
  draws once per wake and sleeps.
- **Mono** — black/white only; palettes and colored status dots become plain
  ink. Utilization bars are outline + fill.
- **Refresh model** — `init()` (cold launch) and **B** fetch over WiFi; **A/C**
  (or UP/DOWN) cycle screens instantly from the `State` cache with no WiFi.
- **USAGE** renders one session+weekly bar per account from the
  `claude-limits.json` `accounts[]` (schema v2), with `HELD` + reset
  countdowns, falling back to the top-level pair.

## Requirements

- A Badgeware **Badger 2350** running the badgewa.re MicroPython build (exposes
  the `badgeware` module, `wifi`, `secrets`, `tls`, `ntptime`).
- `mpremote` on the host, and the badge on USB.
- A running ccstats server (see the top-level [`README.md`](../README.md)).

## Install

```bash
# 1. secrets — copy the template, fill in WiFi + server URL/token/alias
cp firmware-badger/secrets.example.py firmware-badger/secrets.py
$EDITOR firmware-badger/secrets.py
python tools/install-badger-secrets.py        # writes device-root /secrets.py

# 2. app — writes /system/apps/ccstats, then resets
python tools/install-badger.py
```

Both installers default to port `COM8`; pass a different port as the first
argument. Then open the badge's launcher menu and select **Ccstats**.

## Controls

- **A / UP**, **C / DOWN** — previous / next screen (from cache, instant).
- **B** — re-fetch from the server.

## Notes

- `USAGE` reads "no live account data" when every Claude account is idle
  (the server marks them `HELD`) — expected, not a failure.
- The first fetch after launch takes a few seconds (WiFi join + TLS handshake);
  the e-ink only repaints once the draw completes, so it looks static until then.
