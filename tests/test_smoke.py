from app.config import Settings
from app.scoring import calculate_deal_score
from app.collector import parse_page

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
