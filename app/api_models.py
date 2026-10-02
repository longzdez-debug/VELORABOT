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
