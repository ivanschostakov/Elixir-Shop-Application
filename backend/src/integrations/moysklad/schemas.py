import uuid

from dataclasses import asdict, dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class MoySkladProductRow:
    system_id: uuid.UUID
    sku: str
    name: str
    description: str | None
    archived: bool = False


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
    skipped_products_variant_external_code: int = 0
    skipped_products_excluded_name: int = 0
    skipped_products_conflict_sku: int = 0
    skipped_products_conflict_name: int = 0
    skipped_variants_invalid_system_id: int = 0
    skipped_variants_missing_product: int = 0
    archived_products: int = 0
    unarchived_products: int = 0
    archived_variants: int = 0
    unarchived_variants: int = 0
    missing_variants_archived: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass
class MoySkladInitialRelinkStats:
    dry_run: bool = False
    fetched_products: int = 0
    fetched_variants: int = 0
    matched_products: int = 0
    matched_variants: int = 0
    relinked_products: int = 0
    relinked_variants: int = 0
    already_relinked_products: int = 0
    already_relinked_variants: int = 0
    skipped_products_invalid_external_code: int = 0
    skipped_products_invalid_system_id: int = 0
    skipped_products_missing_local: int = 0
    skipped_products_conflict_system_id: int = 0
    skipped_variants_invalid_external_code: int = 0
    skipped_variants_invalid_system_id: int = 0
    skipped_variants_missing_local: int = 0
    skipped_variants_conflict_system_id: int = 0
    skipped_variants_ambiguous: int = 0
    skipped_variants_missing_parent_match: int = 0
    images_planned_for_rename: int = 0
    images_renamed: int = 0
    images_missing: int = 0
    image_rename_failures: int = 0
    image_backup_path: str | None = None
    image_renames: list[dict[str, str]] = field(default_factory=list)
    images_missing_report: list[dict[str, str]] = field(default_factory=list)
    image_rename_failures_report: list[dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class MoySkladCounterpartySyncResult:
    counterparty_id: uuid.UUID
    external_code: str
    created: bool = False
    updated: bool = False


@dataclass
class MoySkladCustomerOrderSyncResult:
    customerorder_id: uuid.UUID
    external_code: str
    created: bool = False


@dataclass
class MoySkladOrderSyncResult:
    enabled: bool
    skipped_reason: str | None = None
    counterparty: MoySkladCounterpartySyncResult | None = None
    customerorder: MoySkladCustomerOrderSyncResult | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)
