from typing import Optional
from pydantic import BaseModel, Field

class PriceRequest(BaseModel):
    manufacturer: str
    model: str
    year: int = Field(ge=1990, le=2030)
    mileage: float = Field(ge=0, le=300000)
    condition: Optional[str] = None
    fuel: Optional[str] = None
    title_status: Optional[str] = None
    transmission: Optional[str] = None
    drive: Optional[str] = None
    vehicle_type: Optional[str] = None
    state: Optional[str] = None

class PriceResponse(BaseModel):
    predicted_price: float
    comparable_count: int
    comparable_median: float
    comparable_q25: float
    comparable_q75: float
    comparable_scope: str
    market_year: int

class AskRequest(BaseModel):
    manufacturer: str
    model: str
    year: Optional[int] = Field(default=None, ge=1990, le=2030)
    question: str = Field(min_length=5, max_length=500)
    k: int = Field(default=5, ge=1, le=10)

class ReviewSource(BaseModel):
    review_id: str
    vehicle_year: Optional[int] = None
    rating: Optional[float] = None
    review_title: str
    excerpt: str
    similarity: Optional[float] = None

class AskResponse(BaseModel):
    answer: str
    scope: str
    citation_valid: bool
    fallback_used: bool
    generation_mode: str
    sources: list[ReviewSource]
    answerable: bool = True
    reason: Optional[str] = None
    suggested_question: Optional[str] = None
    max_similarity: Optional[float] = None
