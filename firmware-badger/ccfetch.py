# ccstats-badger — data fetch for the e-ink edition.
#
# Display-agnostic: reuses the LCD firmware's verified-HTTPS client
# (http_client.py) and pinned roots (certificate_authorities.py — includes the
# GTS Root R4 + GlobalSign roots for the Cloudflare edge, and the chunked-body
# fix). Returns SMALL dicts of just the numbers the e-ink screens show, so they
# fit in badgeware State (flash) and survive the deep-sleep/reset power cycle
# between wakes.

import http_client
import secrets  # framework secrets module — reads /secrets.py, exposes its keys


def _get_json(connection, feed, token):
    return connection.get_json("/" + feed + "?token=" + token)


def _summary(payload):
    meta = payload.get("meta", {})
    totals = payload.get("totals", {})
    cost = payload.get("cost_estimate", {})
    return {
        "alias": getattr(secrets, "ALIAS", "me"),
        "generated": meta.get("generated_at", "")[:16].replace("T", " "),
        "sessions": totals.get("sessions", 0),
        "active_days": totals.get("active_days", 0),
        "streak": totals.get("current_streak", 0),
        "longest_streak": totals.get("longest_streak", 0),
        "prompts": totals.get("user_prompts", 0),
        "words": totals.get("user_words", 0),
        "active_min": totals.get("total_active_min", 0),
        "tokens_total": totals.get("tokens_total", 0),
        "tokens_io": totals.get("tokens_input", 0) + totals.get("tokens_output", 0),
        "cost": cost.get("total_usd", 0),
        "fav_model": totals.get("favorite_model", ""),
    }


def _one_account(label, session, weekly, stale):
    def util(block):
        return round((block or {}).get("utilization", 0) or 0)

    def resets(block):
        return (block or {}).get("resets_in_sec", 0) or 0

    return {
        "label": label or "acct",
        "s_util": util(session),
        "s_reset": resets(session),
        "w_util": util(weekly),
        "w_reset": resets(weekly),
        "stale": bool(stale),
    }


def _accounts(payload):
    # schema v2: per-account list. Fall back to the top-level session/weekly
    # pair (older/back-compat) as a single account if `accounts` is absent.
    out = []
    accts = payload.get("accounts")
    if accts:
        for a in accts:
            out.append(_one_account(
                a.get("label"), a.get("session"), a.get("weekly"), a.get("stale")))
    elif payload.get("session") or payload.get("weekly"):
        out.append(_one_account(
            payload.get("source"), payload.get("session"),
            payload.get("weekly"), payload.get("stale")))
    return out


def fetch_all():
    """Fetch stats (required) + limits/accounts (best-effort). Returns a small
    dict safe to persist in State."""
    base = secrets.STATS_BASE_URL
    token = secrets.STATS_TOKEN
    connection = http_client.PersistentConnection(base)
    try:
        status, payload, _ = _get_json(connection, "claude-stats.json", token)
        if status != 200:
            raise http_client.HttpError("stats HTTP %d (token/server?)" % status)
        summary = _summary(payload)

        accounts = []
        try:
            lstatus, lpayload, _ = _get_json(connection, "claude-limits.json", token)
            if lstatus == 200:
                accounts = _accounts(lpayload)
        except (OSError, ValueError, http_client.HttpError):
            accounts = []  # limits are optional — never fail the whole fetch
    finally:
        connection.close()

    return {"summary": summary, "accounts": accounts}
