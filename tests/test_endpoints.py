"""End-to-end tests for HTTP handlers (Patentstyret stubbed)."""
import pytest
from fastapi import HTTPException, Response


# ── Free endpoints ──────────────────────────────────────────────────


async def test_health(main_module):
    r = await main_module.health()
    assert r["status"] == "ok"
    assert r["service"] == "norway-patent-search"


async def test_classes_endpoint(main_module, nice_module):
    r = await main_module.list_classes()
    assert r["count"] == 45
    nums = [c["number"] for c in r["classes"]]
    assert nums == list(range(1, 46))
    goods = [c for c in r["classes"] if c["kind"] == "goods"]
    services = [c for c in r["classes"] if c["kind"] == "services"]
    assert len(goods) == 34
    assert len(services) == 11


async def test_api_status_reports_key_state(main_module, monkeypatch):
    # Default fixture sets the key
    r = await main_module.api_status()
    assert r["upstream"] == "api.patentstyret.no"
    assert r["upstream_key_configured"] is True

    # Without the key, api-status still works and reports false
    monkeypatch.delenv("PATENTSTYRET_API_KEY", raising=False)
    r = await main_module.api_status()
    assert r["upstream_key_configured"] is False


# ── Manifest contract ───────────────────────────────────────────────


async def test_x402_manifest_counts(main_module):
    r = await main_module.x402_manifest()
    paid = [e for e in r["endpoints"] if e["accepts"]]
    free = [e for e in r["endpoints"] if not e["accepts"]]
    assert len(paid) == 5  # trademark search/detail, patent search/detail, design search
    assert len(free) == 3  # /classes, /health, /api-status


async def test_atomic_amounts_match_price(main_module):
    for e in main_module.ENDPOINT_CATALOG:
        if e["price_usd"] is None:
            continue
        usd = float(e["price_usd"].replace("$", ""))
        expected = str(int(round(usd * 10**6)))
        assert e["amount_atomic"] == expected, f"{e['path']}: {expected} vs {e['amount_atomic']}"


# ── Paid handlers — happy path ──────────────────────────────────────


async def test_trademark_search_happy_path(main_module, fake_ps):
    fake_ps.stub("/trademarks/search", 200, {"results": [{
        "name": "EQUINOR", "applicationNumber": "201712345",
        "status": "Registered", "owner": "Equinor ASA",
        "filingDate": "2017-11-15", "classes": [4, 37, 42],
    }]})
    out = await main_module.trademark_search(response=Response(), q="equinor", limit=20)
    assert out["total"] >= 1
    assert out["results"][0]["name"] == "EQUINOR"


async def test_trademark_search_sends_subscription_header(main_module, fake_ps):
    fake_ps.stub("/trademarks/search", 200, {"results": []})
    await main_module.trademark_search(response=Response(), q="x", limit=5)
    # Last call's headers should include the APIM subscription key
    headers = fake_ps.calls[-1][2]
    assert headers.get("Ocp-Apim-Subscription-Key") == "test-subscription-key"


async def test_trademark_detail_happy_path(main_module, fake_ps):
    fake_ps.stub("/trademarks/201712345", 200, {
        "name": "EQUINOR", "applicationNumber": "201712345",
        "registrationNumber": "300123", "status": "Registered",
        "owner": "Equinor ASA",
    })
    out = await main_module.trademark_detail(response=Response(), app_number="201712345")
    assert out["registration_number"] == "300123"


async def test_patent_search(main_module, fake_ps):
    fake_ps.stub("/patents/search", 200, {"results": [{
        "title": "Method for subsea processing", "applicationNumber": "20201234",
        "status": "Granted", "ipcCodes": ["E21B 43/36"],
    }]})
    out = await main_module.patent_search(response=Response(), q="subsea", limit=20)
    assert out["results"][0]["ipc_codes"] == ["E21B 43/36"]


async def test_patent_detail(main_module, fake_ps):
    fake_ps.stub("/patents/20201234", 200, {
        "title": "Method", "applicationNumber": "20201234",
        "publicationNumber": "NO340567", "status": "Granted",
        "claimsCount": 12, "ipcCodes": ["E21B 43/36"],
    })
    out = await main_module.patent_detail(response=Response(), app_number="20201234")
    assert out["publication_number"] == "NO340567"
    assert out["claims_count"] == 12


async def test_design_search(main_module, fake_ps):
    fake_ps.stub("/designs/search", 200, {"results": [{
        "title": "Offshore platform module", "applicationNumber": "202200456",
        "status": "Registered", "locarnoClass": "23-04",
    }]})
    out = await main_module.design_search(response=Response(), q="platform", limit=20)
    assert out["results"][0]["locarno_class"] == "23-04"


# ── Error paths ─────────────────────────────────────────────────────


async def test_503_when_api_key_missing(main_module, fake_ps, monkeypatch):
    monkeypatch.delenv("PATENTSTYRET_API_KEY", raising=False)
    with pytest.raises(HTTPException) as exc:
        await main_module.trademark_search(response=Response(), q="x", limit=20)
    assert exc.value.status_code == 503
    assert "PATENTSTYRET_API_KEY" in exc.value.detail
    # And no upstream call was made
    assert len(fake_ps.calls) == 0


async def test_401_from_upstream_propagates(main_module, fake_ps):
    fake_ps.stub("/trademarks/search", 401, {"error": "Invalid key"})
    with pytest.raises(HTTPException) as exc:
        await main_module.trademark_search(response=Response(), q="x", limit=20)
    assert exc.value.status_code == 401


async def test_404_from_upstream_propagates(main_module, fake_ps):
    fake_ps.stub("/trademarks/", 404)
    with pytest.raises(HTTPException) as exc:
        await main_module.trademark_detail(response=Response(), app_number="999999999")
    assert exc.value.status_code == 404


async def test_5xx_from_upstream_propagates(main_module, fake_ps):
    fake_ps.stub("/patents/search", 502, {"error": "Bad gateway"})
    with pytest.raises(HTTPException) as exc:
        await main_module.patent_search(response=Response(), q="x", limit=20)
    assert exc.value.status_code == 502


async def test_invalid_app_number_400(main_module):
    with pytest.raises(HTTPException) as exc:
        await main_module.trademark_detail(response=Response(), app_number="x" * 50)
    assert exc.value.status_code == 400


async def test_cache_hit_on_second_call(main_module, fake_ps):
    fake_ps.stub("/trademarks/search", 200, {"results": [{"name": "X"}]})
    r1 = Response()
    await main_module.trademark_search(response=r1, q="same", limit=20)
    assert r1.headers["X-Cache"] == "MISS"
    r2 = Response()
    await main_module.trademark_search(response=r2, q="same", limit=20)
    assert r2.headers["X-Cache"] == "HIT"
    # Only one upstream call
    assert len(fake_ps.calls) == 1
