from types import SimpleNamespace

from app.comparables import comparable_score


def _listing(**kwargs):
    base = {
        "id": 1,
        "title": "iPhone 15 Pro 256GB",
        "model": "iphone 15 pro",
        "storage_gb": 256,
        "memory_gb": None,
        "condition": "excellent",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def test_comparable_score_prefers_same_model_and_storage():
    source = _listing()
    same = _listing(id=2)
    different = _listing(id=3, title="Samsung Galaxy S24", model="galaxy s24", storage_gb=128)
    assert comparable_score(source, same) > comparable_score(source, different)
    assert comparable_score(source, same) >= 70


def test_comparable_score_penalizes_condition_mismatch():
    source = _listing(condition="excellent")
    damaged = _listing(id=2, condition="damaged")
    assert comparable_score(source, damaged) < comparable_score(source, _listing(id=3))
