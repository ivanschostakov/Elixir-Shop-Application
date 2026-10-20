from dataclasses import asdict, dataclass
from uuid import UUID


@dataclass
class WebsiteCatalogSyncStats:
    fetched: int = 0
    matched: int = 0
    matched_by_system_id: int = 0
    matched_by_sku: int = 0
    updated_products: int = 0
    updated_description: int = 0
    updated_usage: int = 0
    updated_storage: int = 0
    unchanged: int = 0
    skipped_invalid_system_id: int = 0
    skipped_duplicate_system_id: int = 0
    skipped_ambiguous_sku: int = 0
    skipped_missing_product: int = 0
    categories_fetched: int = 0
    categories_matched: int = 0
    categories_linked: int = 0
    categories_created: int = 0
    categories_renamed: int = 0
    categories_restored: int = 0
    categories_archived: int = 0
    category_links_created: int = 0
    category_links_deleted: int = 0
    category_links_skipped_missing_products: int = 0
    certificates_fetched: int = 0
    certificates_created: int = 0
    certificates_updated: int = 0
    certificates_deleted: int = 0
    certificates_downloaded: int = 0
    certificate_bytes_downloaded: int = 0
    certificate_files_deleted: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class WebsiteCatalogContent:
    system_id: UUID | None
    sku: str | None
    description: str | None
    usage: str | None
    storage: str | None
    certificates: tuple["WebsiteCatalogCertificate", ...] | None = None


@dataclass(frozen=True)
class WebsiteCatalogCertificate:
    source_file_id: int
    title: str
    original_name: str | None
    content_type: str | None
    size_bytes: int
    source_url: str


@dataclass(frozen=True)
class WebsiteCatalogCategory:
    source_id: int
    name: str
    product_system_ids: tuple[UUID, ...]
