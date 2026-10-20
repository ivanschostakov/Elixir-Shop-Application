from dataclasses import asdict, dataclass


@dataclass
class WebsiteReviewSyncStats:
    pulled: int = 0
    imported: int = 0
    updated_from_website: int = 0
    skipped_missing_product: int = 0
    pushed: int = 0
    created_on_website: int = 0
    updated_on_website: int = 0
    conflicts: int = 0
    attachments_imported: int = 0
    attachments_linked: int = 0
    attachments_skipped: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)
