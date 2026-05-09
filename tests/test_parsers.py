"""Tests for the Patentstyret response parsers."""


def test_parse_trademark_summary_camelcase(parsers_module):
    item = {
        "name": "EQUINOR", "applicationNumber": "201712345",
        "status": "Registered", "owner": "Equinor ASA",
        "filingDate": "2017-11-15", "classes": [4, 37, 42],
    }
    out = parsers_module.parse_trademark_summary(item)
    assert out["name"] == "EQUINOR"
    assert out["application_number"] == "201712345"
    assert out["classes"] == [4, 37, 42]


def test_parse_trademark_summary_norsk_keys(parsers_module):
    """Patentstyret may return Norwegian field names."""
    item = {
        "navn": "EQUINOR", "soknadsnummer": "201712345",
        "tilstand": "Registrert", "innehaver": "Equinor ASA",
        "soknadsdato": "2017-11-15",
        "varemerkeklasser": [{"klasse": 4}, {"klasse": 37}],
    }
    out = parsers_module.parse_trademark_summary(item)
    assert out["name"] == "EQUINOR"
    assert out["status"] == "Registrert"
    assert 4 in out["classes"] and 37 in out["classes"]


def test_parse_trademark_search_top_level_shapes(parsers_module):
    """Different upstream might return rows under 'results', 'trademarks', 'items', 'hits'."""
    payload_a = {"results": [{"name": "A"}]}
    payload_b = {"trademarks": [{"name": "B"}]}
    payload_c = {"items": [{"name": "C"}]}
    payload_d = {"hits": [{"name": "D"}]}
    for p, expected in [(payload_a, "A"), (payload_b, "B"), (payload_c, "C"), (payload_d, "D")]:
        out = parsers_module.parse_trademark_search(p)
        assert len(out["results"]) == 1
        assert out["results"][0]["name"] == expected


def test_parse_trademark_detail_with_class_descriptions(parsers_module):
    payload = {
        "name": "EQUINOR", "applicationNumber": "201712345",
        "registrationNumber": "300123",
        "status": "Registered", "owner": "Equinor ASA",
        "ownerAddress": "Forusbeen 50, 4035 Stavanger",
        "filingDate": "2017-11-15", "registrationDate": "2018-03-20",
        "expiryDate": "2028-03-20",
        "classes": [
            {"number": 4, "description": "Industrial oils and greases"},
            {"number": 37, "description": "Construction services"},
        ],
        "representatives": [{"name": "Zacco Norway AS"}],
    }
    out = parsers_module.parse_trademark_detail(payload)
    assert out["registration_number"] == "300123"
    assert out["owner_address"] == "Forusbeen 50, 4035 Stavanger"
    assert len(out["classes_detailed"]) == 2
    assert out["classes_detailed"][0]["description"] == "Industrial oils and greases"
    assert out["representatives"][0]["name"] == "Zacco Norway AS"


def test_parse_patent_summary(parsers_module):
    item = {
        "title": "Method for subsea processing", "applicationNumber": "20201234",
        "status": "Granted", "applicant": "Equinor Energy AS",
        "filingDate": "2020-06-15",
        "ipcCodes": ["E21B 43/36"],
    }
    out = parsers_module.parse_patent_summary(item)
    assert out["title"] == "Method for subsea processing"
    assert out["ipc_codes"] == ["E21B 43/36"]


def test_parse_patent_summary_ipc_as_objects(parsers_module):
    item = {
        "title": "X", "applicationNumber": "1",
        "ipcCodes": [{"code": "E21B 43/36"}, {"code": "F03B 13/24"}],
    }
    out = parsers_module.parse_patent_summary(item)
    assert out["ipc_codes"] == ["E21B 43/36", "F03B 13/24"]


def test_parse_patent_detail(parsers_module):
    payload = {
        "title": "Method", "applicationNumber": "20201234",
        "publicationNumber": "NO340567", "status": "Granted",
        "applicant": "Equinor Energy AS",
        "inventors": [{"name": "Ola Nordmann"}, {"name": "Kari Nordmann"}],
        "filingDate": "2020-06-15", "publicationDate": "2021-01-10",
        "grantDate": "2022-03-15",
        "abstract": "A method for subsea processing of hydrocarbons...",
        "ipcCodes": ["E21B 43/36"],
        "claimsCount": 12,
    }
    out = parsers_module.parse_patent_detail(payload)
    assert out["publication_number"] == "NO340567"
    assert len(out["inventors"]) == 2
    assert out["inventors"][0]["name"] == "Ola Nordmann"
    assert out["claims_count"] == 12


def test_parse_design_search(parsers_module):
    payload = {"results": [{
        "title": "Offshore platform module",
        "applicationNumber": "202200456",
        "status": "Registered",
        "owner": "Aker Solutions ASA",
        "filingDate": "2022-02-10",
        "locarnoClass": "23-04",
    }]}
    out = parsers_module.parse_design_search(payload)
    assert out["results"][0]["locarno_class"] == "23-04"


def test_parsers_handle_empty_input(parsers_module):
    assert parsers_module.parse_trademark_search({})["results"] == []
    assert parsers_module.parse_patent_search({})["results"] == []
    assert parsers_module.parse_design_search({})["results"] == []
    assert parsers_module.parse_patent_detail({})["title"] == ""
