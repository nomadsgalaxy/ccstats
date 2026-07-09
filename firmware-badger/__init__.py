# ccstats — e-ink edition for the Badgeware Badger 2350 (264x176, 1-bit mono).
#
# No animations, no live avatar. Fetches the ccstats summary + per-account
# limits over verified HTTPS and draws static stat screens the framework
# refreshes on wake. Buttons: A/UP + C/DOWN cycle screens (from cache, no
# WiFi); B re-fetches. Reuses http_client.py + certificate_authorities.py from
# the LCD firmware unchanged — only this file (and ccfetch.py) is badge-specific.
#
# Power model: the badgeware framework deep-sleeps between wakes and re-runs
# this module on each wake, so the fetched numbers are cached in State (flash);
# only a cold launch or B triggers WiFi + a fresh fetch.

import sys
import os

from badgeware import run, State

sys.path.insert(0, "/system/apps/ccstats")
sys.path.insert(0, "/")
os.chdir("/system/apps/ccstats")

import time
import ntptime

import ccfetch

BIG = rom_font.ignore     # hero numbers
MED = rom_font.smart      # labels / values
SMALL = rom_font.smart    # footer / captions

SCREENS = ("TOKENS", "USAGE", "ACTIVITY", "COST")

state = {"screen": 0, "summary": None, "accounts": [], "error": None, "fetched": ""}
State.load("ccstats", state)


# --------------------------------------------------------------------------- #
# formatting
# --------------------------------------------------------------------------- #
def _abbr(n):
    n = n or 0
    a = abs(n)
    if a >= 1e9:
        return "%.1fB" % (n / 1e9)
    if a >= 1e6:
        return "%.1fM" % (n / 1e6)
    if a >= 1e3:
        return "%.1fK" % (n / 1e3)
    return str(int(n))


def _commas(n):
    s = str(int(n or 0))
    out = ""
    while len(s) > 3:
        out = "," + s[-3:] + out
        s = s[:-3]
    return s + out


def _hours(minutes):
    return "%dh" % round((minutes or 0) / 60.0)


def _dur(sec):
    sec = int(sec or 0)
    if sec <= 0:
        return ""
    if sec >= 86400:
        return "%dd" % (sec // 86400)
    if sec >= 3600:
        return "%dh" % (sec // 3600)
    return "%dm" % (sec // 60)


# --------------------------------------------------------------------------- #
# data
# --------------------------------------------------------------------------- #
def _refresh():
    import wifi
    wifi.connect()
    t0 = time.ticks_ms()
    while not wifi.tick():
        if time.ticks_diff(time.ticks_ms(), t0) > 20000:
            raise OSError("wifi timeout")
        time.sleep_ms(50)
    try:
        ntptime.settime()  # cert validity needs a roughly-correct clock
    except Exception:      # noqa: BLE001
        pass
    data = ccfetch.fetch_all()
    state["summary"] = data["summary"]
    state["accounts"] = data["accounts"]
    state["error"] = None
    state["fetched"] = data["summary"].get("generated", "")
    State.save("ccstats", state)


def _try_refresh():
    try:
        _refresh()
    except Exception as e:  # noqa: BLE001
        state["error"] = (str(e) or repr(e))[:40]
        State.save("ccstats", state)


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #
def _text(s, x, y, fnt=None):
    if fnt is not None:
        screen.font = fnt
    screen.text(str(s), int(x), int(y))


def _right(s, x_right, y, fnt=None):
    if fnt is not None:
        screen.font = fnt
    w, _ = screen.measure_text(str(s))
    screen.text(str(s), int(x_right - w), int(y))


def _center(s, y, fnt=None):
    if fnt is not None:
        screen.font = fnt
    w, _ = screen.measure_text(str(s))
    screen.text(str(s), int((screen.width - w) / 2), int(y))


def _fill(x, y, w, h):
    screen.shape(shape.rectangle(int(x), int(y), int(w), int(h)))


def _bar(x, y, w, h, pct):
    pct = max(0, min(100, pct or 0))
    screen.pen = color.black
    _fill(x, y, w, 1)
    _fill(x, y + h - 1, w, 1)
    _fill(x, y, 1, h)
    _fill(x + w - 1, y, 1, h)
    fw = int((w - 4) * pct / 100)
    if fw > 0:
        _fill(x + 2, y + 2, fw, h - 4)


def _header(title):
    screen.pen = color.black
    _fill(0, 0, screen.width, 20)
    screen.pen = color.white
    alias = (state.get("summary") or {}).get("alias", "ccstats")
    _text(alias, 6, 4, SMALL)
    _right(title, screen.width - 6, 4, SMALL)


def _footer(idx):
    screen.pen = color.black
    y = screen.height - 11
    _text(state.get("fetched") or "no data", 6, y, SMALL)
    _right("%d/%d  B=refresh" % (idx + 1, len(SCREENS)), screen.width - 6, y, SMALL)


def _row(label, value, y, hero=False):
    screen.pen = color.black
    _text(label, 8, y, MED)
    _right(value, screen.width - 8, y - (7 if hero else 0), BIG if hero else MED)


def _draw_tokens(d, y):
    _row("Tokens", _abbr(d["tokens_total"]), y, hero=True); y += 32
    _row("I/O tokens", _abbr(d["tokens_io"]), y); y += 22
    _row("Prompts", _commas(d["prompts"]), y); y += 22
    _row("Streak", "%d d" % d["streak"], y); y += 22
    _row("Best streak", "%d d" % d["longest_streak"], y)


def _draw_activity(d, y):
    _row("Sessions", _commas(d["sessions"]), y, hero=True); y += 32
    _row("Active days", _commas(d["active_days"]), y); y += 22
    _row("Active time", _hours(d["active_min"]), y); y += 22
    _row("Words typed", _abbr(d["words"]), y); y += 22
    _row("Fav model", (d["fav_model"] or "").replace("claude-", ""), y)


def _draw_cost(d, y):
    _row("Est. cost", "$" + _commas(d["cost"]), y, hero=True); y += 32
    _row("Tokens", _abbr(d["tokens_total"]), y); y += 22
    _row("Prompts", _commas(d["prompts"]), y); y += 22
    _row("Sessions", _commas(d["sessions"]), y)


def _draw_usage(y):
    accounts = state.get("accounts") or []
    if not accounts:
        screen.pen = color.black
        _center("no live account data", 70, MED)
        _center("(idle = HELD; press B)", 92, SMALL)
        return
    x = 8
    w = screen.width - 16
    block = (screen.height - y - 16) // len(accounts[:3])
    for a in accounts[:3]:
        screen.pen = color.black
        name = a["label"] + (" HELD" if a["stale"] else "")
        _text(name, x, y, MED)
        bar_y = y + 13
        bh = 9
        # session bar
        _text("S", x, bar_y - 1, SMALL)
        _bar(x + 14, bar_y, w - 60, bh, a["s_util"])
        _right("%d%% %s" % (a["s_util"], _dur(a["s_reset"])), x + w, bar_y - 1, SMALL)
        # weekly bar
        _text("W", x, bar_y + bh + 3, SMALL)
        _bar(x + 14, bar_y + bh + 4, w - 60, bh, a["w_util"])
        _right("%d%% %s" % (a["w_util"], _dur(a["w_reset"])), x + w, bar_y + bh + 3, SMALL)
        y += block


def _draw():
    screen.pen = color.white
    screen.clear()

    idx = state["screen"] % len(SCREENS)
    name = SCREENS[idx]
    _header(name)

    err = state.get("error")
    d = state.get("summary")

    if err and not d:
        screen.pen = color.black
        _center("can't reach server", 64, MED)
        _center(err, 88, SMALL)
        _center("press B to retry", 116, SMALL)
        _footer(idx)
        return
    if not d:
        screen.pen = color.black
        _center("press B to load stats", 84, MED)
        _footer(idx)
        return

    y = 30
    if name == "TOKENS":
        _draw_tokens(d, y)
    elif name == "USAGE":
        _draw_usage(y)
    elif name == "ACTIVITY":
        _draw_activity(d, y)
    else:
        _draw_cost(d, y)

    if err:  # stale data on screen but last refresh failed — flag it small
        screen.pen = color.black
        _center("(refresh failed)", screen.height - 24, SMALL)
    _footer(idx)


# --------------------------------------------------------------------------- #
# framework entry points
# --------------------------------------------------------------------------- #
def init():
    # Cold launch / power-on: pull fresh data once (button wakes reuse cache).
    if state.get("summary") is None:
        _try_refresh()


def update():
    if io.BUTTON_B in io.pressed:
        _try_refresh()
    elif io.BUTTON_A in io.pressed or io.BUTTON_UP in io.pressed:
        state["screen"] = (state["screen"] - 1) % len(SCREENS)
        State.save("ccstats", state)
    elif io.BUTTON_C in io.pressed or io.BUTTON_DOWN in io.pressed:
        state["screen"] = (state["screen"] + 1) % len(SCREENS)
        State.save("ccstats", state)
    _draw()


def on_exit():
    pass


if __name__ == "__main__":
    run(update, init=init, on_exit=on_exit)
