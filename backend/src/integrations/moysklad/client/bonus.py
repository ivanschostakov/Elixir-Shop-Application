from typing import Any
from uuid import UUID
from src.normalize import coerce_uuid, optional_str


class BonusMixin:
    async def get_bonus_program(self, bonus_program_id: UUID | str) -> dict[str, Any] | None:
        normalized_id = coerce_uuid(bonus_program_id)
        if normalized_id is None: return None
        return await self._get_entity_by_id("bonusprogram", normalized_id)


    async def get_default_bonus_program(self) -> dict[str, Any] | None:
        programs = await self.get_all("/entity/bonusprogram")
        return next((program for program in programs if program.get("active") is not False and coerce_uuid(program.get("id")) is not None), None,)


    async def assign_counterparty_bonus_program(self, counterparty_id: UUID | str, bonus_program_id: UUID | str,) -> dict[str, Any]:
        normalized_counterparty_id = coerce_uuid(counterparty_id)
        normalized_program_id = coerce_uuid(bonus_program_id)
        if normalized_counterparty_id is None or normalized_program_id is None: raise ValueError("Invalid MoySklad counterparty or bonus program id")
        return await self._update_entity("counterparty", normalized_counterparty_id, {"bonusProgram": self._meta_payload(href=self.entity_href("bonusprogram", normalized_program_id), entity_type="bonusprogram",)},)


    async def find_bonus_transaction_by_external_code(self, external_code: str,) -> dict[str, Any] | None:
        return await self._find_entity_by_external_code("bonustransaction", external_code)


    async def resolve_or_create_bonus_transaction(self, *, counterparty_id: UUID | str, bonus_program_id: UUID | str, bonus_points: int, transaction_type: str, external_code: str, name: str, description: str | None = None,) -> dict[str, Any]:
        existing = await self.find_bonus_transaction_by_external_code(external_code)
        if existing is not None: return existing

        normalized_counterparty_id = coerce_uuid(counterparty_id)
        normalized_program_id = coerce_uuid(bonus_program_id)
        normalized_type = transaction_type.strip().upper()
        if normalized_counterparty_id is None: raise ValueError("Invalid MoySklad counterparty id")
        if normalized_program_id is None: raise ValueError("Invalid MoySklad bonus program id")
        if normalized_type not in {"EARNING", "SPENDING"}: raise ValueError("Invalid MoySklad bonus transaction type")
        if int(bonus_points) <= 0: raise ValueError("MoySklad bonus points must be positive")

        payload: dict[str, Any] = {
            "name": name,
            "externalCode": external_code,
            "applicable": True,
            "agent": self._meta_payload(
                href=self.entity_href("counterparty", normalized_counterparty_id),
                entity_type="counterparty",
            ),
            "bonusProgram": self._meta_payload(
                href=self.entity_href("bonusprogram", normalized_program_id),
                entity_type="bonusprogram",
            ),
            "transactionType": normalized_type,
            "bonusValue": int(bonus_points),
        }
        if optional_str(description): payload["description"] = optional_str(description)
        try: return await self._create_entity("bonustransaction", payload)
        except Exception:
            existing = await self.find_bonus_transaction_by_external_code(external_code)
            if existing is not None: return existing
            raise
