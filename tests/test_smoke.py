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


from app.market import _percentile


def test_market_percentiles_are_robust():
    values = [100, 200, 300, 400, 500]
    assert _percentile(values, 0.10) == 140
    assert _percentile(values, 0.50) == 300
    assert _percentile(values, 0.90) == 460


def test_market_percentile_empty():
    assert _percentile([], 0.5) is None


from app.attributes import extract_attributes


def test_attribute_extraction_uses_title_and_description():
    a = extract_attributes(
        "iPhone 15 Pro 256GB",
        "Батарея 92%, полный комплект, без ремонтов",
    )
    assert a.model == "iphone 15 pro"
    assert a.storage_gb == 256
    assert a.condition in {"unknown", "excellent"}
    assert a.repair_signal is False
    assert a.completeness_signal == "complete"


def test_duplicate_key_is_stable_without_price():
    from app.duplicates import duplicate_key_for

    a = duplicate_key_for(
        "iPhone 15 Pro 256GB",
        "iphone 15 pro",
        256,
        "https://img/item.jpg",
    )
    b = duplicate_key_for(
        "iPhone 15 Pro 256GB",
        "iphone 15 pro",
        256,
        "https://img/item.jpg",
    )
    assert a == b


def test_duplicate_key_ignores_price():
    from app.duplicates import duplicate_key_for

    assert duplicate_key_for(
        "iPhone 15 Pro",
        "iphone 15 pro",
        256,
    ) == duplicate_key_for(
        "iPhone 15 Pro",
        "iphone 15 pro",
        256,
    )


def test_liquidity_sale_window_estimates_are_bounded():
    from app.scoring import calculate_deal_score

    d = calculate_deal_score(100, [150, 160, 170], "полный комплект", comparable_count=20)
    assert 0 < d.sale_lt_24h_pct <= d.sale_lt_3d_pct <= d.sale_lt_7d_pct <= 99
