import pytest

from src.integrations.intellectmoney.client import AsyncIntellectMoney


@pytest.mark.anyio
async def test_create_invoice_formats_recipient_amount_to_two_decimals(monkeypatch: pytest.MonkeyPatch):
    client = AsyncIntellectMoney()
    client.shop_id = "shop-id"
    client.secret_key = "secret-key"
    client.sign_secret_key = "sign-secret-key"

    captured_form: dict[str, str] = {}

    async def fake_post_form(path: str, form_data: dict[str, str], *_sign_parts):
        assert path == "/merchant/createInvoice"
        captured_form.update(form_data)
        return {"OperationState": {"Code": 0}, "Result": {"InvoiceId": "123"}}

    monkeypatch.setattr(client, "_post_form", fake_post_form)

    await client.create_invoice(
        order_id="EP-39T6A2UU",
        service_name="Заказ №39",
        amount_rub=199,
        user_name="Test User",
        email="test@example.com",
        success_url="https://example.com/success",
        fail_url="https://example.com/fail",
        back_url="https://example.com/back",
        result_url="https://example.com/result",
        preference="Sbp",
    )

    assert captured_form["RecipientAmount"] == "199.00"


def test_parse_payment_state_is_available_on_client():
    client = AsyncIntellectMoney()

    parsed = client.parse_payment_state(
        {
            "Result": {
                "PaymentStep": "Created",
                "Form3DS": '{"SbpQrCodeUrl":"https://example.com/qr","SbpQrCodeImage":"data:image/png;base64,AAA"}',
            },
        }
    )

    assert parsed == {
        "payment_step": "Created",
        "qr_url": "https://example.com/qr",
        "qr_image": "data:image/png;base64,AAA",
    }


def test_parse_payment_state_normalizes_raw_base64_qr_image():
    client = AsyncIntellectMoney()

    parsed = client.parse_payment_state(
        {
            "Result": {
                "PaymentStep": "SendTo3DS",
                "Form3DS": '{"SbpQrCodeUrl":"https://example.com/qr","SbpQrCodeImage":"QUJD"}',
            },
        }
    )

    assert parsed["payment_step"] == "SendTo3DS"
    assert parsed["qr_url"] == "https://example.com/qr"
    assert parsed["qr_image"] == "data:image/png;base64,QUJD"
