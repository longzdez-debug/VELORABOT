from app.config import Settings
from app.scoring import calculate_deal_score
from app.collector import parse_page
from app.kufar import normalize_ad

def test_settings():
    assert Settings().api_port == 8000

def test_deal_score_has_explainable_output():
    d=calculate_deal_score(100,[150,160,170],"идеал, полный комплект")
    assert 0 <= d.score <= 100
    assert d.market_price == 160
    assert d.reasons

def test_html_page_parser_preserves_description():
    html="""<html><body><article><h2>iPhone 15 Pro</h2><a href='/item/1'>open</a>
    <p>Полное описание: батарея 92%, комплект, без ремонтов.</p><span>1 500 р.</span></article></body></html>"""
    rows=parse_page(html,"https://example.test/search")
    assert rows and rows[0]["title"]=="iPhone 15 Pro"
    assert "батарея 92%" in rows[0]["description_raw"]
    assert rows[0]["url"]=="https://example.test/item/1"

def test_kufar_normalizer_uses_ad_id_and_full_body():
    row=normalize_ad({
        "ad_id":"123456","subject":"iPhone 15 Pro","price_byn":150000,
        "ad_link":"https://www.kufar.by/item/123456",
        "body":"Батарея 92%, полный комплект, без ремонта.",
        "ad_parameters":[{"p":"region","vl":"Минск"}],
        "images":[{"path":"12/123.jpg"}],
    })
    assert row["source_id"]=="123456"
    assert row["price"]==1500
    assert "Батарея 92%" in row["description_raw"]
    assert row["location"]=="Минск"
    assert row["image_url"].endswith("/12/123.jpg")
