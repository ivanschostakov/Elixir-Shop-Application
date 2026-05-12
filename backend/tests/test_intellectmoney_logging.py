import json

import httpx

from src.integrations.intellectmoney.helpers import response_body_for_log


def test_response_body_for_log_redacts_large_sbp_qr_image():
    response = httpx.Response(
        200,
        json={
            "OperationState": {"Code": 0, "Desc": "ok"},
            "Result": {
                "PaymentStep": "SendTo3DS",
                "Form3DS": json.dumps(
                    {
                        "SbpQrCodeUrl": "https://qr.example.test/123",
                        "SbpQrCodeImage": "A" * 5000,
                    }
                ),
            },
        },
    )

    logged_body = response_body_for_log(response)
    assert "SbpQrCodeUrl" in logged_body
    assert "<redacted len=5000>" in logged_body
    assert "A" * 200 not in logged_body
