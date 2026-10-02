from app.config import Settings
from app.scoring import calculate_deal_score

def test_settings():
    assert Settings().api_port == 8000

def test_deal_score_has_explainable_output():
    d=calculate_deal_score(100,[150,160,170],"идеал, полный комплект")
    assert 0 <= d.score <= 100
    assert d.market_price == 160
    assert d.reasons
