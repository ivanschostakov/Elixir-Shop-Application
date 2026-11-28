from fastapi import HTTPException


class PaymentRejected(HTTPException):
    """Keep the mobile error contract and a separate stable diagnostic code."""

    def __init__(self, code: str, detail: str, *, status: int = 409):
        super().__init__(status_code=status, detail=detail)
        self.reason_code = code
