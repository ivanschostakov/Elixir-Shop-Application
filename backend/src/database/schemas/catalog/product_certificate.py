from pydantic import BaseModel, ConfigDict, Field


class ProductCertificateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_name: str | None
    content_type: str | None
    size_bytes: int = Field(ge=0)
    url: str
