from pydantic import BaseModel, Field

class AlertCreate(BaseModel):
    query: str = Field(default="", max_length=200)
    max_price: float | None = Field(default=None, gt=0)
    min_score: int = Field(default=70, ge=0, le=100)
    region: str = Field(default="", max_length=100)

class ProfitRequest(BaseModel):
    buy_price: float = Field(gt=0)
    resale_price: float = Field(gt=0)
    delivery: float = Field(default=0, ge=0)
    repairs: float = Field(default=0, ge=0)
    selling_costs: float = Field(default=0, ge=0)


class HuntRequest(BaseModel):
    query: str = Field(default="", max_length=200)
    budget: float = Field(gt=0)
    min_profit: float = Field(default=0, ge=0)
    max_risk: int = Field(default=60, ge=0, le=100)
    min_liquidity: int = Field(default=0, ge=0, le=100)
    limit: int = Field(default=25, ge=1, le=100)
