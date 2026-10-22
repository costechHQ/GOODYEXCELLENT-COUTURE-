from pydantic import BaseModel, ConfigDict


class TestimonialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_name: str
    quote: str
    photo_url: str | None
