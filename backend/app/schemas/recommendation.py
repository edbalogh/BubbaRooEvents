from pydantic import BaseModel


class ScoreBreakdown(BaseModel):
    category_affinity: float = 0.0
    embedding_similarity: float = 0.0
    popularity: float = 0.0
    distance_penalty: float = 0.0


class RecommendationResponse(BaseModel):
    id: str
    title: str
    description: str | None
    venue_name: str | None
    city: str | None
    state: str | None
    starts_at: str
    price_min: float | None
    price_max: float | None
    currency: str
    url: str | None
    image_url: str | None
    categories: list[str] = []
    score: float
    score_breakdown: ScoreBreakdown | None = None

    model_config = {"from_attributes": True}


class CategoryPreference(BaseModel):
    category_id: int
    category_name: str
    category_slug: str
    weight: float


class PreferenceUpdate(BaseModel):
    category_slug: str
    weight: float


class PreferencesResponse(BaseModel):
    categories: list[CategoryPreference]
    max_distance_miles: float = 25.0


class InteractionCreate(BaseModel):
    interaction_type: str
