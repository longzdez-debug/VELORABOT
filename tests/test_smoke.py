from app.config import Settings
from app.scoring import calculate_deal_score
from app.collector import parse_page
from app.events import ListingEvent, new_listing_event
from app.kufar import normalize_ad
from app.alert_index import terms
from app.telegram_auth import validate_init_data


def test_settings():
    assert Settings().api_port == 8000
    assert Settings().event_stream


def test_deal_score_has_explainable_output():
    d = calculate_deal_score(100, [150, 160, 170], "идеал, полный комплект")
    assert 0 <= d.score <= 100
    assert d.market_price == 160
    assert d.reasons


def test_html_page_parser_preserves_description():
    html = """<html><body><article><h2>iPhone 15 Pro</h2><a href='/item/1'>open</a>
    <p>Полное описание: батарея 92%, комплект, без ремонтов.</p><span>1 500 р.</span></article></body></html>"""
    rows = parse_page(html, "https://example.test/search")
    assert rows and rows[0]["title"] == "iPhone 15 Pro"
    assert "батарея 92%" in rows[0]["description_raw"]
    assert rows[0]["url"] == "https://example.test/item/1"


def test_kufar_normalizer_uses_ad_id_and_full_body():
    row = normalize_ad({
        "ad_id": "123456",
        "subject": "iPhone 15 Pro",
        "price_byn": 150000,
        "ad_link": "https://www.kufar.by/item/123456",
        "body": "Батарея 92%, полный комплект, без ремонта.",
        "ad_parameters": [{"p": "region", "vl": "Минск"}],
        "images": [{"path": "12/123.jpg"}],
    })
    assert row["source_id"] == "123456"
    assert row["price"] == 1500
    assert "Батарея 92%" in row["description_raw"]
    assert row["location"] == "Минск"
    assert row["image_url"].endswith("/12/123.jpg")


def test_listing_event_roundtrip():
    event = new_listing_event("NEW", 42, "kufar", "123456", 1500)
    restored = ListingEvent.from_fields(event.to_fields())
    assert restored == event
    assert restored.detected_at_ms > 0


def test_alert_terms_preserve_unicode_tokens():
    assert terms("iPhone 15 Pro") == {"iphone", "15", "pro"}


def test_telegram_webapp_init_data_signature(monkeypatch):
    import hashlib
    import hmac
    import json
    import time
    from urllib.parse import quote

    token = "123456:test-token"
    monkeypatch.setattr("app.config.settings.telegram_bot_token", token)
    auth_date = int(time.time())
    pairs = {
        "auth_date": str(auth_date),
        "user": json.dumps({"id": 42, "first_name": "Test"}, separators=(",", ":")),
    }
    check = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    digest = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    init_data = "&".join(f"{k}={quote(v)}" for k, v in pairs.items()) + "&hash=" + digest
    assert validate_init_data(init_data) == 42
\n\nfrom app.market import _percentile\n\ndef test_market_percentiles_are_robust():\n    values = [100, 200, 300, 400, 500]\n    assert _percentile(values, 0.10) == 140\n    assert _percentile(values, 0.50) == 300\n    assert _percentile(values, 0.90) == 460\n\ndef test_market_percentile_empty():\n    assert _percentile([], 0.5) is None\n\n\nfrom app.attributes import extract_attributes\n\ndef test_attribute_extraction_uses_title_and_description():\n    a = extract_attributes("iPhone 15 Pro 256GB", "Батарея 92%, полный комплект, без ремонтов")\n    assert a.model == "iphone 15 pro"\n    assert a.storage_gb == 256\n    assert a.condition == "unknown" or a.condition == "excellent"\n    assert a.repair_signal is False\n    assert a.completeness_signal == "complete"\n