from pydantic import BaseModel


class PoolCreate(BaseModel):
    name: str
    description: str = ""
