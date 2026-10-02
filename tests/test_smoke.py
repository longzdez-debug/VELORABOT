from app.config import Settings

def test_settings():
    s = Settings()
    assert s.api_port == 8000
