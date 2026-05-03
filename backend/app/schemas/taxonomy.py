from pydantic import BaseModel, ConfigDict


class GenreRead(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PlatformRead(BaseModel):
    id: int
    slug: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class GameModeRead(BaseModel):
    id: int
    slug: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class TagRead(BaseModel):
    id: int
    slug: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class CriterionRead(BaseModel):
    id: int
    slug: str
    name: str

    model_config = ConfigDict(from_attributes=True)
