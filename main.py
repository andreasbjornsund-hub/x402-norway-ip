"""
x402-norway-ip — Norwegian IP Search

x402 micropayment API wrapping Patentstyret's trademark, patent, and design
APIs into a single agent-friendly service.

Endpoints (free):
  GET /                       — landing page (HTML or JSON)
  GET /health                 — health check
  GET /api-status             — uptime + cache shape + upstream readiness
  GET /classes                — Nice classification reference data (45 classes)
  GET /services.json          — agent-readable services manifest
  GET /llms.txt               — LLMs.txt for AI crawlers
  GET /robots.txt             — robots policy
  GET /.well-known/x402.json  — x402 agent-discovery manifest

Endpoints (paid, USDC on Base):
  GET /trademark/search       $0.01    text search across registered marks
  GET /trademark/{app}        $0.01    full trademark details
  GET /patent/search          $0.01    patent text search
  GET /patent/{app}           $0.02    full patent record (claims, abstract)
  GET /design/search          $0.01    registered design search

Data: Patentstyret (https://developer.patentstyret.no). API requires a free
subscription key set as PATENTSTYRET_API_KEY (Fly secret). Without that,
upstream-dependent endpoints return 503 with a clear instruction; /health,
/classes, and the discovery endpoints still work.
"""
import os
import time
from contextlib import asynccontextmanager

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import cache
import nice_classes
import parsers
import patentstyret_client as ps
from patentstyret_client import PatentstyretError

from cdp_auth import create_cdp_auth_provider

from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────

SERVICE_ID = "norway-ip"
SERVICE_NAME = "Norwegian IP Search"
SERVICE_DESCRIPTION = (
    "Search trademarks, patents, and designs from Patentstyret — Norway's "
    "Industrial Property Office. Pay per query with USDC via x402."
)
SERVICE_CATEGORY = "data"

EVM_ADDRESS = os.getenv("EVM_ADDRESS")
EVM_NETWORK: Network = "eip155:8453"
FACILITATOR_URL = os.getenv("FACILITATOR_URL", "https://x402.org/facilitator")
SITE_URL = os.getenv("SITE_URL", "https://x402-norway-ip.fly.dev")
USDC_BASE_MAINNET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

if not EVM_ADDRESS:
    raise ValueError("Set EVM_ADDRESS in .env")

# ── FastAPI app ─────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await _http.aclose()


app = FastAPI(
    title=SERVICE_NAME,
    description=SERVICE_DESCRIPTION,
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

import json as _json

cdp_auth = None
if "cdp.coinbase.com" in FACILITATOR_URL:
    cdp_auth = create_cdp_auth_provider()
facilitator_config = FacilitatorConfig(url=FACILITATOR_URL, auth_provider=cdp_auth)
facilitator = HTTPFacilitatorClient(facilitator_config)

_CAIP2_TO_V1 = {"eip155:8453": "base", "eip155:84532": "base-sepolia"}


def _v2_payload_to_v1(payload_dict: dict) -> dict:
    v1 = {"x402Version": 1}
    v1["scheme"] = payload_dict.get("scheme", "exact")
    raw_net = payload_dict.get("network", EVM_NETWORK)
    v1["network"] = _CAIP2_TO_V1.get(raw_net, raw_net)
    v1["payload"] = payload_dict.get("payload", payload_dict)
    return v1


def _v2_requirements_to_v1(req_dict: dict) -> dict:
    raw_net = req_dict.get("network", EVM_NETWORK)
    extra = req_dict.get("extra", {})
    if isinstance(extra, str):
        try:
            extra = _json.loads(extra)
        except Exception:
            extra = {}
    v1 = {
        "scheme": req_dict.get("scheme", "exact"),
        "network": _CAIP2_TO_V1.get(raw_net, raw_net),
        "maxAmountRequired": req_dict.get("amount", req_dict.get("maxAmountRequired", "0")),
        "resource": req_dict.get("resource", ""),
        "description": req_dict.get("description", ""),
        "mimeType": req_dict.get("mimeType", req_dict.get("mime_type", "application/json")),
        "asset": req_dict.get("asset", ""),
        "payTo": req_dict.get("payTo", req_dict.get("pay_to", "")),
        "maxTimeoutSeconds": req_dict.get("maxTimeoutSeconds", req_dict.get("max_timeout_seconds", 300)),
        "extra": extra,
    }
    extensions = req_dict.get("extensions", {})
    bazaar = extensions.get("bazaar", {})
    if bazaar.get("info"):
        v1["outputSchema"] = bazaar["info"]
    return v1


_orig_verify = facilitator._verify_http
_orig_settle = facilitator._settle_http


async def _v1_verify(version, payload_dict, requirements_dict):
    return await _orig_verify(1, _v2_payload_to_v1(payload_dict), _v2_requirements_to_v1(requirements_dict))


async def _v1_settle(version, payload_dict, requirements_dict):
    return await _orig_settle(1, _v2_payload_to_v1(payload_dict), _v2_requirements_to_v1(requirements_dict))


facilitator._verify_http = _v1_verify
facilitator._settle_http = _v1_settle

server = x402ResourceServer(facilitator)
server.register(EVM_NETWORK, ExactEvmServerScheme())

# ── Endpoint catalog ────────────────────────────────────────────────
# Order: /<thing>/search before /<thing>/{app_number} so the more specific
# x402 route wins.

ENDPOINT_CATALOG: list[dict] = [
    {
        "method": "GET",
        "path": "/trademark/search",
        "route_pattern": "GET /trademark/search",
        "description": "Search Norwegian trademarks by text. Returns up to 20 results with name, application number, status, owner, filing date, and Nice classes.",
        "price_usd": "$0.01",
        "amount_atomic": "10000",
        "query_params": {"q": "equinor"},
        "path_params": {},
        "output_example": {
            "results": [{
                "name": "EQUINOR", "application_number": "201712345", "status": "Registered",
                "owner": "Equinor ASA", "filing_date": "2017-11-15", "classes": [4, 37, 42],
            }],
            "total": 1,
        },
    },
    {
        "method": "GET",
        "path": "/trademark/{app_number}",
        "route_pattern": "GET /trademark/*",
        "description": "Full trademark detail by application number. Includes registration/expiry dates, owner address, Nice class descriptions, representatives.",
        "price_usd": "$0.01",
        "amount_atomic": "10000",
        "query_params": {},
        "path_params": {"app_number": "201712345"},
        "output_example": {
            "name": "EQUINOR", "application_number": "201712345", "registration_number": "300123",
            "status": "Registered", "owner": "Equinor ASA",
            "owner_address": "Forusbeen 50, 4035 Stavanger",
            "filing_date": "2017-11-15", "registration_date": "2018-03-20", "expiry_date": "2028-03-20",
            "classes_detailed": [{"number": 4, "description": "Industrial oils and greases"}],
            "representatives": [{"name": "Zacco Norway AS"}],
        },
    },
    {
        "method": "GET",
        "path": "/patent/search",
        "route_pattern": "GET /patent/search",
        "description": "Search Norwegian patents by text. Returns up to 20 results with title, application number, status, applicant, filing date, IPC codes.",
        "price_usd": "$0.01",
        "amount_atomic": "10000",
        "query_params": {"q": "subsea"},
        "path_params": {},
        "output_example": {
            "results": [{
                "title": "Method for subsea processing", "application_number": "20201234",
                "status": "Granted", "applicant": "Equinor Energy AS",
                "filing_date": "2020-06-15", "ipc_codes": ["E21B 43/36"],
            }],
            "total": 1,
        },
    },
    {
        "method": "GET",
        "path": "/patent/{app_number}",
        "route_pattern": "GET /patent/*",
        "description": "Full patent record by application number. Includes inventors, publication/grant dates, abstract, IPC codes, claim count.",
        "price_usd": "$0.02",
        "amount_atomic": "20000",
        "query_params": {},
        "path_params": {"app_number": "20201234"},
        "output_example": {
            "title": "Method for subsea processing", "application_number": "20201234",
            "publication_number": "NO340567", "status": "Granted",
            "applicant": "Equinor Energy AS",
            "inventors": [{"name": "Ola Nordmann"}],
            "filing_date": "2020-06-15", "publication_date": "2021-01-10",
            "grant_date": "2022-03-15",
            "abstract": "A method for subsea processing of hydrocarbons...",
            "ipc_codes": ["E21B 43/36", "E21B 43/01"], "claims_count": 12,
        },
    },
    {
        "method": "GET",
        "path": "/design/search",
        "route_pattern": "GET /design/search",
        "description": "Search registered industrial designs. Returns title, application number, status, owner, filing date, Locarno class.",
        "price_usd": "$0.01",
        "amount_atomic": "10000",
        "query_params": {"q": "platform"},
        "path_params": {},
        "output_example": {
            "results": [{
                "title": "Offshore platform module", "application_number": "202200456",
                "status": "Registered", "owner": "Aker Solutions ASA",
                "filing_date": "2022-02-10", "locarno_class": "23-04",
            }],
            "total": 1,
        },
    },
    {"method": "GET", "path": "/classes", "route_pattern": None,
     "description": "Nice classification reference (45 classes of goods and services).",
     "price_usd": None, "amount_atomic": None, "query_params": {}, "path_params": {}, "output_example": None},
    {"method": "GET", "path": "/health", "route_pattern": None,
     "description": "Service health check.",
     "price_usd": None, "amount_atomic": None, "query_params": {}, "path_params": {}, "output_example": {"status": "ok"}},
    {"method": "GET", "path": "/api-status", "route_pattern": None,
     "description": "Operational status — uptime, cache shape, and Patentstyret-key readiness.",
     "price_usd": None, "amount_atomic": None, "query_params": {}, "path_params": {}, "output_example": None},
]


def _bazaar_info(entry: dict) -> dict:
    inp = {"type": "http", "method": entry["method"]}
    if entry["query_params"]:
        inp["queryParams"] = entry["query_params"]
    if entry["path_params"]:
        inp["pathParams"] = entry["path_params"]
    return {
        "info": {"input": inp, "output": {"type": "json", "example": entry["output_example"]}},
        "schema": {"$schema": "https://json-schema.org/draft/2020-12/schema",
                   "type": "object",
                   "properties": {"input": {"type": "object"}, "output": {"type": "object"}}},
    }


def _build_paid_routes(catalog: list[dict]) -> dict[str, RouteConfig]:
    return {
        e["route_pattern"]: RouteConfig(
            accepts=[PaymentOption(scheme="exact", pay_to=EVM_ADDRESS, price=e["price_usd"], network=EVM_NETWORK)],
            mime_type="application/json",
            description=e["description"],
            extensions={"bazaar": _bazaar_info(e)},
        )
        for e in catalog if e["route_pattern"] is not None
    }


routes = _build_paid_routes(ENDPOINT_CATALOG)
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)

# ── Shared HTTP client ──────────────────────────────────────────────

_http = httpx.AsyncClient(timeout=30, headers={"Accept": "application/json"})

_PROCESS_START_TS = time.time()


# ── Discovery / metadata endpoints ──────────────────────────────────


@app.get("/")
async def landing(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and os.path.isfile("static/index.html"):
        return FileResponse("static/index.html")
    return {
        "service": SERVICE_NAME, "version": "0.1.0", "description": SERVICE_DESCRIPTION,
        "endpoints": {e["path"]: f"{e['description']} ({e['price_usd']} USDC)" if e["price_usd"]
                      else f"{e['description']} (free)"
                      for e in ENDPOINT_CATALOG} | {"/.well-known/x402.json": "Agent discovery"},
        "payment": "x402 protocol — USDC on Base network",
        "data_source": "Patentstyret (developer.patentstyret.no)",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": SERVICE_ID, "timestamp": int(time.time())}


@app.get("/api-status")
async def api_status():
    return {
        "status": "ok", "service": SERVICE_ID, "version": "0.1.0",
        "uptime_seconds": int(time.time() - _PROCESS_START_TS),
        "upstream": "api.patentstyret.no",
        "upstream_key_configured": ps.have_api_key(),
        "cache": cache.stats(),
    }


@app.get("/classes")
async def list_classes():
    cs = nice_classes.all_classes()
    return {"count": len(cs), "classes": cs}


@app.get("/services.json")
async def services_manifest():
    return {
        "id": SERVICE_ID, "name": SERVICE_NAME, "description": SERVICE_DESCRIPTION,
        "category": SERVICE_CATEGORY, "x402Version": 2, "networks": [EVM_NETWORK],
        "website": SITE_URL,
        "endpoints": [{"method": e["method"], "path": e["path"], "description": e["description"],
                       "price": e["price_usd"] or "$0.00", "currency": "USDC"}
                      for e in ENDPOINT_CATALOG],
    }


@app.get("/.well-known/x402.json")
async def x402_manifest():
    return {
        "x402Version": 2,
        "service": {"id": SERVICE_ID, "name": SERVICE_NAME, "description": SERVICE_DESCRIPTION,
                    "category": SERVICE_CATEGORY, "website": SITE_URL,
                    "documentation": f"{SITE_URL}/llms.txt",
                    "servicesManifest": f"{SITE_URL}/services.json"},
        "payment": {"schemes": ["exact"], "networks": [EVM_NETWORK],
                    "asset": {"symbol": "USDC", "decimals": 6, "address": USDC_BASE_MAINNET, "chain": "Base"},
                    "payTo": EVM_ADDRESS, "facilitator": FACILITATOR_URL},
        "endpoints": [
            {"method": e["method"], "path": e["path"], "description": e["description"],
             "accepts": [{"scheme": "exact", "network": EVM_NETWORK, "asset": "USDC",
                          "amount": e["amount_atomic"], "amountDisplay": e["price_usd"], "payTo": EVM_ADDRESS}]
                        if e["amount_atomic"] else [],
             "input": {"type": "http", "method": e["method"],
                       **({"queryParams": e["query_params"]} if e["query_params"] else {}),
                       **({"pathParams": e["path_params"]} if e["path_params"] else {})},
             "output": ({"type": "json", "example": e["output_example"]}
                        if e["output_example"] is not None else {"type": "json"})}
            for e in ENDPOINT_CATALOG
        ],
    }


@app.get("/llms.txt")
async def llms_txt():
    lines = [f"# {SERVICE_NAME}", f"> {SERVICE_DESCRIPTION}", "", "## Endpoints"]
    for e in ENDPOINT_CATALOG:
        price = f"{e['price_usd']} USDC" if e["price_usd"] else "Free"
        lines.append(f"- {e['method']} {e['path']} — {price} — {e['description']}")
    lines += [
        "", "## Payment",
        "- Protocol: x402 (HTTP 402 micropayments)",
        "- Currency: USDC on Base",
        "- No API keys or accounts needed (we handle Patentstyret auth server-side)",
        "- Agent discovery: GET /.well-known/x402.json",
        "", "## Source data",
        "- Patentstyret (developer.patentstyret.no) — official Norwegian IP office",
        "- Search results cached 24h, detail responses 7d",
        "", "## Reference data (free)",
        "- /classes — Nice classification of goods and services (45 classes)",
        "", "## Links",
        f"- Website: {SITE_URL}",
        f"- Services manifest: {SITE_URL}/services.json",
        "",
    ]
    return PlainTextResponse("\n".join(lines), media_type="text/plain")


@app.get("/robots.txt")
async def robots_txt():
    return PlainTextResponse(
        "User-agent: *\nAllow: /\n\n"
        "User-agent: GPTBot\nAllow: /\n\n"
        "User-agent: ClaudeBot\nAllow: /\n\n"
        "User-agent: PerplexityBot\nAllow: /\n\n"
        "User-agent: Google-Extended\nAllow: /\n",
        media_type="text/plain",
    )


def _set_cache_header(response: Response, hit: bool) -> None:
    response.headers["X-Cache"] = "HIT" if hit else "MISS"


def _ps_error(e: PatentstyretError) -> HTTPException:
    return HTTPException(status_code=e.status_code, detail=e.message)


# ── Paid endpoints ──────────────────────────────────────────────────


@app.get("/trademark/search")
async def trademark_search(
    response: Response,
    q: str = Query(..., min_length=1, max_length=200, description="Search text"),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        data, hit = await ps.trademark_search(_http, q, limit=limit)
    except PatentstyretError as e:
        raise _ps_error(e)
    _set_cache_header(response, hit)
    return parsers.parse_trademark_search(data, limit=limit)


@app.get("/trademark/{app_number}")
async def trademark_detail(
    response: Response,
    app_number: str,
):
    if not app_number or len(app_number) > 32:
        raise HTTPException(400, "Invalid application number")
    try:
        data, hit = await ps.trademark_detail(_http, app_number)
    except PatentstyretError as e:
        raise _ps_error(e)
    _set_cache_header(response, hit)
    return parsers.parse_trademark_detail(data)


@app.get("/patent/search")
async def patent_search(
    response: Response,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        data, hit = await ps.patent_search(_http, q, limit=limit)
    except PatentstyretError as e:
        raise _ps_error(e)
    _set_cache_header(response, hit)
    return parsers.parse_patent_search(data, limit=limit)


@app.get("/patent/{app_number}")
async def patent_detail(
    response: Response,
    app_number: str,
):
    if not app_number or len(app_number) > 32:
        raise HTTPException(400, "Invalid application number")
    try:
        data, hit = await ps.patent_detail(_http, app_number)
    except PatentstyretError as e:
        raise _ps_error(e)
    _set_cache_header(response, hit)
    return parsers.parse_patent_detail(data)


@app.get("/design/search")
async def design_search(
    response: Response,
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=50),
):
    try:
        data, hit = await ps.design_search(_http, q, limit=limit)
    except PatentstyretError as e:
        raise _ps_error(e)
    _set_cache_header(response, hit)
    return parsers.parse_design_search(data, limit=limit)


# ── Static files ────────────────────────────────────────────────────

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
