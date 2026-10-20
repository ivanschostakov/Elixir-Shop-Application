class BitrixDeliveryError(RuntimeError):
    def __init__(self, *, status_code: int, code: str, message_ru: str, message_en: str) -> None:
        super().__init__(message_ru)
        self.status_code = status_code
        self.code = code
        self.message_ru = message_ru
        self.message_en = message_en