"""Defensive parsers for Patentstyret response shapes.

The exact field names from Patentstyret's developer portal aren't fully
documented yet; we read the most common shapes (camelCase + snake_case +
norsk) and fall back to empty strings rather than raising. Callers see a
stable JSON shape; if Patentstyret changes one field, only this file needs
editing.
"""
from typing import Any


def _first(d: dict, *keys: str, default: Any = None) -> Any:
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _names(items: list | None) -> list[dict]:
    """Normalize people/representatives into [{name, ...}]."""
    if not items:
        return []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _first(item, "name", "navn", "fullName", default="")
        if not name:
            continue
        out.append({"name": name})
    return out


# ── Trademarks ──────────────────────────────────────────────────────


def parse_trademark_summary(item: dict) -> dict:
    classes_raw = _first(item, "classes", "niceClasses", "varemerkeklasser", default=[]) or []
    classes: list[int] = []
    if isinstance(classes_raw, list):
        for c in classes_raw:
            if isinstance(c, int):
                classes.append(c)
            elif isinstance(c, dict):
                n = _first(c, "number", "klasse", "classNumber")
                if isinstance(n, int):
                    classes.append(n)
            elif isinstance(c, str) and c.isdigit():
                classes.append(int(c))
    return {
        "name": _first(item, "name", "navn", "wordmark", "merketekst", default=""),
        "application_number": str(_first(item, "applicationNumber", "soknadsnummer", "application_number", default="")),
        "registration_number": str(_first(item, "registrationNumber", "registreringsnummer", default="")) or None,
        "status": _first(item, "status", "tilstand", default=""),
        "owner": _first(item, "owner", "innehaver", "applicant", default=""),
        "filing_date": _first(item, "filingDate", "soknadsdato", "filing_date", default=""),
        "classes": classes,
        "image_url": _first(item, "imageUrl", "bildeUrl", default=None),
    }


def parse_trademark_search(data: dict, limit: int = 20) -> dict:
    rows = data.get("results") or data.get("trademarks") or data.get("items") or data.get("hits") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "results": [parse_trademark_summary(r) for r in rows[:limit] if isinstance(r, dict)],
        "total": data.get("total") or data.get("totalCount") or len(rows),
    }


def parse_trademark_detail(data: dict) -> dict:
    summary = parse_trademark_summary(data)

    # Owner address (often nested under owner block)
    owner_obj = data.get("ownerObject") or data.get("innehaverObject") or {}
    owner_address = _first(owner_obj, "address", "adresse", default="") or _first(data, "ownerAddress", "innehaverAdresse", default="")

    # Classes with descriptions
    classes_raw = _first(data, "classes", "niceClasses", "varemerkeklasser", default=[]) or []
    classes_detailed: list[dict] = []
    if isinstance(classes_raw, list):
        for c in classes_raw:
            if isinstance(c, dict):
                n = _first(c, "number", "klasse", "classNumber")
                desc = _first(c, "description", "beskrivelse", default="")
                if isinstance(n, int):
                    classes_detailed.append({"number": n, "description": desc})
            elif isinstance(c, int):
                classes_detailed.append({"number": c, "description": ""})

    return {
        **summary,
        "owner_address": owner_address,
        "registration_date": _first(data, "registrationDate", "registreringsdato", default=""),
        "expiry_date": _first(data, "expiryDate", "utlopsdato", default=""),
        "classes_detailed": classes_detailed,
        "representatives": _names(_first(data, "representatives", "fullmektige", default=[])),
    }


# ── Patents ─────────────────────────────────────────────────────────


def _ipc_codes(data: dict) -> list[str]:
    raw = _first(data, "ipcCodes", "ipc", "ipcClassifications", default=[]) or []
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for c in raw:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict):
            code = _first(c, "code", "klassifikasjon", default="")
            if code:
                out.append(code)
    return out


def parse_patent_summary(item: dict) -> dict:
    return {
        "title": _first(item, "title", "tittel", default=""),
        "application_number": str(_first(item, "applicationNumber", "soknadsnummer", default="")),
        "status": _first(item, "status", "tilstand", default=""),
        "applicant": _first(item, "applicant", "soker", default=""),
        "filing_date": _first(item, "filingDate", "soknadsdato", default=""),
        "ipc_codes": _ipc_codes(item),
    }


def parse_patent_search(data: dict, limit: int = 20) -> dict:
    rows = data.get("results") or data.get("patents") or data.get("items") or data.get("hits") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "results": [parse_patent_summary(r) for r in rows[:limit] if isinstance(r, dict)],
        "total": data.get("total") or data.get("totalCount") or len(rows),
    }


def parse_patent_detail(data: dict) -> dict:
    summary = parse_patent_summary(data)
    return {
        **summary,
        "publication_number": _first(data, "publicationNumber", "publiseringsnummer", default=""),
        "inventors": _names(_first(data, "inventors", "oppfinnere", default=[])),
        "publication_date": _first(data, "publicationDate", "publiseringsdato", default=""),
        "grant_date": _first(data, "grantDate", "meddelelsesdato", default=""),
        "abstract": _first(data, "abstract", "sammendrag", default=""),
        "claims_count": _first(data, "claimsCount", "antallKrav", default=None),
    }


# ── Designs ─────────────────────────────────────────────────────────


def parse_design_summary(item: dict) -> dict:
    return {
        "title": _first(item, "title", "tittel", default=""),
        "application_number": str(_first(item, "applicationNumber", "soknadsnummer", default="")),
        "status": _first(item, "status", "tilstand", default=""),
        "owner": _first(item, "owner", "innehaver", "applicant", default=""),
        "filing_date": _first(item, "filingDate", "soknadsdato", default=""),
        "locarno_class": _first(item, "locarnoClass", "locarnoKlasse", "locarno", default=""),
    }


def parse_design_search(data: dict, limit: int = 20) -> dict:
    rows = data.get("results") or data.get("designs") or data.get("items") or data.get("hits") or []
    if not isinstance(rows, list):
        rows = []
    return {
        "results": [parse_design_summary(r) for r in rows[:limit] if isinstance(r, dict)],
        "total": data.get("total") or data.get("totalCount") or len(rows),
    }
