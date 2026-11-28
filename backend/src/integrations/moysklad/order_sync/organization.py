from uuid import UUID
from config import MOY_SKLAD_ORGANIZATION_ID, MOY_SKLAD_ORGANIZATION_NAME
from src.normalize import coerce_uuid, optional_str
from src.integrations.moysklad.client import MoySkladClient
from .common import log


def _configured_organization_id() -> UUID | None:
    configured_id = coerce_uuid(MOY_SKLAD_ORGANIZATION_ID)
    if configured_id is None and optional_str(MOY_SKLAD_ORGANIZATION_ID): log.warning("MOY_SKLAD_ORGANIZATION_ID is not a valid UUID: %s", MOY_SKLAD_ORGANIZATION_ID)
    return configured_id


async def _resolve_organization_id(moysklad_client: MoySkladClient) -> UUID | None:
    configured_id = _configured_organization_id()
    organization_name = optional_str(MOY_SKLAD_ORGANIZATION_NAME)
    if configured_id is not None:
        configured_row = await moysklad_client.get_organization(configured_id)
        if configured_row and configured_row.get("archived"):
            log.error("Configured MoySklad organization is archived organization_id=%s", configured_id)
        elif configured_row is not None:
            configured_name = optional_str(configured_row.get("name"))
            if (not organization_name or (configured_name is not None and configured_name.casefold() == organization_name.casefold())): return configured_id
            log.error(
                "Configured MoySklad organization id points to a different organization "
                "organization_id=%s expected_name=%s actual_name=%s",
                configured_id,
                organization_name,
                configured_name,
            )
        else:
            log.error(
                "Configured MoySklad organization does not exist organization_id=%s",
                configured_id,
            )

    if not organization_name: return None
    organization_row = await moysklad_client.find_organization_by_name(organization_name)
    organization_id = coerce_uuid((organization_row or {}).get("id"))
    # The list and the per-ID lookup can have different snapshot times.
    if configured_id is not None and organization_id == configured_id:
        log.error("Organization name lookup returned rejected organization_id=%s", configured_id)
        return None
    if organization_id is None:
        log.error(
            "Configured MoySklad organization was not found organization_name=%s",
            organization_name,
        )
    return organization_id
