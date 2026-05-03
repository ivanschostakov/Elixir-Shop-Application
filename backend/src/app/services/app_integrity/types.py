from dataclasses import dataclass


class AppIntegrityVerifierUnavailable(Exception):
    pass


@dataclass(frozen=True)
class IosAttestationVerification:
    public_key_pem: str
    receipt_b64: str | None
    environment: str
