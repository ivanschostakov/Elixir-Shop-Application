from logging import getLogger
from fastapi import APIRouter, Depends, Query

from src.integrations.delivery.cdek import get_cdek_client, AsyncCDEKClient, CDEKCalculatedDelivery
from src.integrations.delivery.schemas import CountryCode, DeliveryPointMarker, DeliveryPoint, CdekDeliveryMode

cdek_router = APIRouter(prefix="/cdek", tags=["cdek"])
logger = getLogger(__name__)

@cdek_router.get("/delivery-point-markers", response_model=list[DeliveryPointMarker])
async def cdek_get_delivery_point_markers(country_code: CountryCode = "RU", cdek: AsyncCDEKClient = Depends(get_cdek_client)):
    return await cdek.get_delivery_point_markers(country_code)

@cdek_router.get("/delivery-point/{code}", response_model=DeliveryPoint)
async def cdek_delivery_point(code: str, cdek: AsyncCDEKClient = Depends(get_cdek_client)):
    return await cdek.get_delivery_point(code)

@cdek_router.get("/calculate", response_model=CDEKCalculatedDelivery)
async def cdek_delivery_calculate(
    latitude: float = Query(..., alias="latitude"),
    longitude: float = Query(..., alias="longitude"),
    mode: CdekDeliveryMode = Query(..., alias="mode"),
    country_code: CountryCode | None = Query(None, alias="country_code"),
    postal_code: str | None = Query(None, alias="postal_code"),
    address: str | None = Query(None, alias="address"),
    city: str | None = Query(None, alias="city"),
    cdek: AsyncCDEKClient = Depends(get_cdek_client),
):
    return await cdek.calculate_delivery(
        latitude,
        longitude,
        mode,
        country_code=country_code,
        postal_code=postal_code,
        address=address,
        city=city,
    )
