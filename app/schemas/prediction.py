from pydantic import BaseModel, Field


class PredictionCreate(BaseModel):
    pool_id: int
    match_id: int
    predicted_home: int = Field(ge=0)
    predicted_away: int = Field(ge=0)
