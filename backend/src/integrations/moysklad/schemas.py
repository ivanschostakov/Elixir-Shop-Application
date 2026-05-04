import uuid

from dataclasses import asdict, dataclass
from decimal import Decimal


@dataclass(frozen=True)
class MoySkladProductRow:
    system_id: uuid.UUID
    sku: str
    name: str
    description: str | None


@dataclass(frozen=True)
class MoySkladVariantRow:
    system_id: uuid.UUID
    product_system_id: uuid.UUID
    sku: str | None
    name: str
    stock: int
    price: Decimal


@dataclass
class MoySkladCatalogSyncStats:
    fetched_products: int = 0
    fetched_variants: int = 0
    created_products: int = 0
    updated_products: int = 0
    created_variants: int = 0
    updated_variants: int = 0
    skipped_products_invalid_system_id: int = 0
    skipped_variants_invalid_system_id: int = 0
    skipped_variants_missing_product: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class MoySkladInitialRelinkStats:
    fetched_products: int = 0
    fetched_variants: int = 0
    relinked_products: int = 0
    relinked_variants: int = 0
    skipped_products_invalid_external_code: int = 0
    skipped_products_invalid_system_id: int = 0
    skipped_products_missing_local: int = 0
    skipped_products_conflict_system_id: int = 0
    skipped_variants_invalid_external_code: int = 0
    skipped_variants_invalid_system_id: int = 0
    skipped_variants_missing_local: int = 0
    skipped_variants_conflict_system_id: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)
