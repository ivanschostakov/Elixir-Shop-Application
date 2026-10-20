from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class IntegrationStatusRead(BaseModel):
    provider: str
    label: str
    configured: bool
    status: Literal["healthy", "warning", "error", "disabled"]
    last_run_at: datetime | None
    last_run_status: str | None
    last_error: str | None


class IntegrationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    operation: str
    status: str
    target_type: str | None
    target_id: str | None
    retry_of_id: int | None
    attempts: int
    max_attempts: int
    counters_json: dict[str, Any]
    error: str | None
    started_at: datetime
    heartbeat_at: datetime | None
    next_attempt_at: datetime | None
    finished_at: datetime | None


class IntegrationRetryPayload(BaseModel):
    operation: Literal["catalog_sync"]
    idempotency_key: str = Field(min_length=8, max_length=160)


class IntegrationRunRetryPayload(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=160)


class IntegrationQueueHealthRead(BaseModel):
    queue_available: bool
    queue_depth: int
    processing_depth: int
    scheduled_depth: int
    queued: int
    running: int
    retrying: int
    failed_24h: int
    stale_running: int
    oldest_pending_at: datetime | None


class AdminExportCreatePayload(BaseModel):
    resource: Literal["orders", "customers", "products", "reviews", "audit"]
    format: Literal["csv", "xlsx"]
    columns: list[str] = Field(min_length=1, max_length=32)
    filters: dict[str, Any] = Field(default_factory=dict)
    selected_ids: list[int] = Field(default_factory=list, max_length=5000)
    locale: Literal["ru", "en"] = "ru"
    idempotency_key: str = Field(min_length=8, max_length=160)


class AdminExportRead(BaseModel):
    id: int
    resource: str
    format: str
    status: str
    rows: int | None
    file_name: str | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class AuditLogRead(BaseModel):
    id: int
    actor_name: str
    action: str
    entity_type: str
    entity_id: str | None
    before_json: dict[str, Any] | None
    after_json: dict[str, Any] | None
    context_json: dict[str, Any]
    ip_address: str | None
    request_id: str | None
    created_at: datetime
