from pydantic import BaseModel


class MatchResult(BaseModel):
    home_score: int
    away_score: int


class MatchRetroactive(BaseModel):
    allow_retroactive: bool
