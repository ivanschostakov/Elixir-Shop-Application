class WebsiteIdentityError(RuntimeError):
    def __init__(self, *, status_code: int, code: str, message: str, message_ru: str | None = None, message_en: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message_ru = message_ru or message
        self.message_en = message_en or message