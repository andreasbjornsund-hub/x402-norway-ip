"""Patentstyret (Norwegian Industrial Property Office) upstream client.

API portal: https://developer.patentstyret.no
Auth: Azure API Management subscription key sent as the
`Ocp-Apim-Subscription-Key` request header. The subscription key lives in
the PATENTSTYRET_API_KEY env var (Fly secret in production).

If PATENTSTYRET_API_KEY is unset, every helper raises PatentstyretError(503)
with a clear message. The /health and /classes endpoints don't depend on
upstream so the app stays useful even without the key.

Endpoint paths follow the spec from the build prompt; if Patentstyret's
actual paths differ once the dev-portal subscription is in place, only this
client needs editing — the parsers and handlers are decoupled.
"""
import asyncio
import os

import httpx

import cache


USER_AGENT = "x402agent-norway-patent-search/1.0 github.com/andreasbjornsund-hub"
BASE = os.getenv("PATENTSTYRET_BASE_URL", "https://api.patentstyret.no")

# Stay polite — Patentstyret's docs don't publish a hard limit but Azure APIM
# tiers usually default to 5 req/sec. We cap at 8 concurrent.
_SEM = asyncio.Semaphore(8)


class PatentstyretError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Patentstyret {status_code}: {message}")


def have_api_key() -> bool:
    return bool(os.getenv("PATENTSTYRET_API_KEY"))


def _headers() -> dict:
    return {
        "Ocp-Apim-Subscription-Key": os.getenv("PATENTSTYRET_API_KEY", ""),
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }


async def _get(client: httpx.AsyncClient, path: str, params: dict | None, ttl: float) -> tuple[dict, bool]:
    if not have_api_key():
        raise PatentstyretError(
            503,
            "PATENTSTYRET_API_KEY not configured. Sign up at developer.patentstyret.no, "
            "subscribe to the relevant product, and run `flyctl secrets set "
            "-a x402-norway-patent-search PATENTSTYRET_API_KEY=<your-key>`.",
        )
    import json as _json
    cache_key = f"ps:{path}:{_json.dumps(params or {}, sort_keys=True)}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached, True

    url = f"{BASE.rstrip('/')}{path}"
    async with _SEM:
        resp = await client.get(url, params=params or {}, headers=_headers())

    if resp.status_code == 401 or resp.status_code == 403:
        raise PatentstyretError(401, "PATENTSTYRET_API_KEY rejected by upstream.")
    if resp.status_code == 404:
        raise PatentstyretError(404, "Not found")
    if resp.status_code != 200:
        raise PatentstyretError(resp.status_code, resp.text[:300])

    data = resp.json()
    cache.put(cache_key, data, ttl)
    return data, False


# ── Trademarks ──────────────────────────────────────────────────────


async def trademark_search(client, query: str, limit: int = 20, ttl: float = 86400.0):
    return await _get(client, "/trademarks/search", {"query": query, "limit": limit}, ttl)


async def trademark_detail(client, app_number: str, ttl: float = 7 * 86400.0):
    return await _get(client, f"/trademarks/{app_number}", None, ttl)


# ── Patents ─────────────────────────────────────────────────────────


async def patent_search(client, query: str, limit: int = 20, ttl: float = 86400.0):
    return await _get(client, "/patents/search", {"query": query, "limit": limit}, ttl)


async def patent_detail(client, app_number: str, ttl: float = 7 * 86400.0):
    return await _get(client, f"/patents/{app_number}", None, ttl)


# ── Designs ─────────────────────────────────────────────────────────


async def design_search(client, query: str, limit: int = 20, ttl: float = 86400.0):
    return await _get(client, "/designs/search", {"query": query, "limit": limit}, ttl)
