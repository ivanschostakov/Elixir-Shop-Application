from pydantic import BaseModel


class DeliveryPointMarker(BaseModel):
    code: str
    latitude: float
    longitude: float

    @classmethod
    def from_dict(cls, d: dict) -> "DeliveryPointMarker":
        return DeliveryPointMarker(
            code=d["code"],
            latitude=d["location"]["latitude"],
            longitude=d["location"]["longitude"],
        )
