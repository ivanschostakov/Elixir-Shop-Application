from pydantic import BaseModel, Field

from .country_code import CountryCode


class DeliveryPoint(BaseModel):
    code: str
    name: str
    address: str = ""
    address_full: str = ""
    city: str = ""
    country_code: CountryCode | None = None
    postal_code: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    work_time: str = ""
    phones: list[str] = Field(default_factory=list)
    emails: list[str] = Field(default_factory=list)
    office_image_urls: list[str] = Field(default_factory=list)
    is_handout: bool = False
    is_reception: bool = False
    have_cashless: bool = False
    have_cash: bool = False
    nearest_station: str | None = None
    nearest_metro_station: str | None = None
    note: str | None = None

    @classmethod
    def from_cdek_dict(cls, data: dict) -> "DeliveryPoint":
        location = data.get("location", {})
        raw_emails = data.get("emails")

        emails: list[str]
        if isinstance(raw_emails, str): emails = [raw_emails]
        elif isinstance(raw_emails, list):
            emails = []
            for item in raw_emails:
                if isinstance(item, str) and item:
                    emails.append(item)
                    continue

                if not isinstance(item, dict): continue

                for key in ("email", "address", "value"):
                    value = item.get(key)
                    if isinstance(value, str) and value:
                        emails.append(value)
                        break
        else:
            fallback_email = data.get("email")
            emails = [fallback_email] if isinstance(fallback_email, str) and fallback_email else []

        return cls(
            code=data["code"],
            name=data["name"],
            address=location.get("address", ""),
            address_full=location.get("address_full", ""),
            city=location.get("city", ""),
            country_code=location.get("country_code"),
            postal_code=location.get("postal_code"),
            latitude=location.get("latitude", 0.0),
            longitude=location.get("longitude", 0.0),
            work_time=data.get("work_time", ""),
            phones=[item["number"] for item in data.get("phones", []) if "number" in item],
            emails=emails,
            office_image_urls=[item["url"] for item in data.get("office_image_list", []) if "url" in item],
            is_handout=data.get("is_handout", False),
            is_reception=data.get("is_reception", False),
            have_cashless=data.get("have_cashless", False),
            have_cash=data.get("have_cash", False),
            nearest_station=data.get("nearest_station"),
            nearest_metro_station=data.get("nearest_metro_station"),
            note=data.get("note"),
        )

    @classmethod
    def from_yandex_dict(cls, data: dict) -> "DeliveryPoint":
        address = data.get("address", {})
        position = data.get("position", {})
        contact = data.get("contact", {})
        schedule = data.get("schedule", {})
        restrictions = schedule.get("restrictions", [])
        work_time_parts: list[str] = []
        day_map = {
            1: "Пн",
            2: "Вт",
            3: "Ср",
            4: "Чт",
            5: "Пт",
            6: "Сб",
            7: "Вс",
        }
        for item in restrictions:
            days = item.get("days", [])
            time_from = item.get("time_from", {})
            time_to = item.get("time_to", {})
            if not days: continue
            days_str = ",".join(day_map.get(day, str(day)) for day in days)
            from_str = f'{int(time_from.get("hours", 0)):02d}:{int(time_from.get("minutes", 0)):02d}'
            to_str = f'{int(time_to.get("hours", 0)):02d}:{int(time_to.get("minutes", 0)):02d}'
            work_time_parts.append(f"{days_str} {from_str}-{to_str}")
        phone = contact.get("phone")
        phones = [phone] if isinstance(phone, str) and phone else []
        payment_methods = set(data.get("payment_methods", []))

        return cls(
            code=data["id"],
            name=data.get("name", ""),
            address=" ".join(
                part for part in [address.get("street", ""), address.get("house", "")]
                if part
            ),
            address_full=address.get("full_address", ""),
            city=address.get("locality", ""),
            country_code=address.get("country_code"),
            postal_code=address.get("postal_code"),
            latitude=position.get("latitude", 0.0),
            longitude=position.get("longitude", 0.0),
            work_time="; ".join(work_time_parts),
            phones=phones,
            is_handout=data.get("type") == "pickup_point",
            is_reception=data.get("available_for_dropoff", False),
            have_cashless=any(method in payment_methods for method in {"card_on_receipt", "bound_card"}),
            have_cash="postpay" in payment_methods,
            note=data.get("instruction") or address.get("comment"),
        )
