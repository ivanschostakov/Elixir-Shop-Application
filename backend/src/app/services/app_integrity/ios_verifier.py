import hmac
import cbor2

from typing import Any
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils as asymmetric_utils
from cryptography.x509.oid import ExtensionOID
from pyasn1.codec.der import decoder as der_decoder

from config import WORKING_DIR, ufa_now
from .common import decode_base64, encode_base64, ios_allowed_environments, ios_app_id, ios_environment_from_aaguid, public_key_x962_hash, sha256
from .constants import APPLE_APP_ATTEST_NONCE_OID
from .types import IosAttestationVerification


_APPLE_APP_ATTEST_ROOT_CA_PATH = WORKING_DIR / ".secrets" / "apple_app_attest_root_ca.pem"
_APPLE_APP_ATTEST_ROOT_CA_PEM: bytes | None = None


def _load_apple_app_attest_root_ca_pem() -> bytes:
    global _APPLE_APP_ATTEST_ROOT_CA_PEM
    if _APPLE_APP_ATTEST_ROOT_CA_PEM is not None: return _APPLE_APP_ATTEST_ROOT_CA_PEM
    if not _APPLE_APP_ATTEST_ROOT_CA_PATH.exists(): raise ValueError(f"Apple App Attest root CA file is missing: {_APPLE_APP_ATTEST_ROOT_CA_PATH}")
    _APPLE_APP_ATTEST_ROOT_CA_PEM = _APPLE_APP_ATTEST_ROOT_CA_PATH.read_bytes()
    return _APPLE_APP_ATTEST_ROOT_CA_PEM


def parse_authenticator_data(auth_data: bytes, *, require_attested_credential_data: bool) -> dict[str, Any]:
    if len(auth_data) < 37:
        raise ValueError("authenticator data is too short")

    parsed: dict[str, Any] = {
        "rp_id_hash": auth_data[:32],     "flags": auth_data[32],     "counter": int.from_bytes(auth_data[33:37], "big"), }

    if not require_attested_credential_data: return parsed
    if len(auth_data) < 55: raise ValueError("attestation authenticator data is too short")
    credential_id_length = int.from_bytes(auth_data[53:55], "big")
    credential_id_start = 55
    credential_id_end = credential_id_start + credential_id_length
    if len(auth_data) < credential_id_end: raise ValueError("attestation credential id is truncated")

    parsed.update({
        "aaguid": auth_data[37:53],     "credential_id": auth_data[credential_id_start:credential_id_end], })
    return parsed


def verify_cert_signed_by(child: x509.Certificate, issuer: x509.Certificate) -> None:
    issuer_public_key = issuer.public_key()
    if not isinstance(issuer_public_key, ec.EllipticCurvePublicKey): raise ValueError("unsupported App Attest issuer public key")
    issuer_public_key.verify(
        child.signature,     child.tbs_certificate_bytes,     ec.ECDSA(child.signature_hash_algorithm), )


def verify_app_attest_cert_chain(leaf: x509.Certificate, intermediate: x509.Certificate) -> None:
    root = x509.load_pem_x509_certificate(_load_apple_app_attest_root_ca_pem())
    now = ufa_now()

    for cert in (leaf, intermediate, root):
        if hasattr(cert, "not_valid_before_utc"):
            not_valid_before = cert.not_valid_before_utc
            not_valid_after = cert.not_valid_after_utc
        
        else:
            not_valid_before = cert.not_valid_before.replace(tzinfo=now.tzinfo)
            not_valid_after = cert.not_valid_after.replace(tzinfo=now.tzinfo)
        
        if now < not_valid_before or now > not_valid_after: raise ValueError("App Attest certificate is outside validity window")

    if leaf.issuer != intermediate.subject or intermediate.issuer != root.subject: raise ValueError("App Attest certificate issuer mismatch")

    verify_cert_signed_by(leaf, intermediate)
    verify_cert_signed_by(intermediate, root)

    intermediate_constraints = intermediate.extensions.get_extension_for_oid(ExtensionOID.BASIC_CONSTRAINTS).value
    if not intermediate_constraints.ca: raise ValueError("App Attest intermediate is not a CA")


def extract_app_attest_nonce(leaf: x509.Certificate) -> bytes:
    extension = leaf.extensions.get_extension_for_oid(APPLE_APP_ATTEST_NONCE_OID)
    decoded, remainder = der_decoder.decode(extension.value.value)
    if remainder: raise ValueError("App Attest nonce extension has trailing data")
    return bytes(decoded[0])


def verify_ios_attestation_object(*, key_id: str, challenge: str, attestation_object_b64: str) -> IosAttestationVerification:
    app_id = ios_app_id()
    if app_id is None: raise ValueError("iOS App Attest app id is not configured")

    key_id_bytes = decode_base64(key_id)
    attestation_object = cbor2.loads(decode_base64(attestation_object_b64))
    if not isinstance(attestation_object, dict) or attestation_object.get("fmt") != "apple-appattest": raise ValueError("invalid App Attest attestation object")

    att_stmt = attestation_object.get("attStmt")
    auth_data = attestation_object.get("authData")
    if not isinstance(att_stmt, dict) or not isinstance(auth_data, bytes): raise ValueError("invalid App Attest attestation payload")

    x5c = att_stmt.get("x5c")
    if not isinstance(x5c, list) or len(x5c) < 2 or not all(isinstance(cert, bytes) for cert in x5c[:2]): raise ValueError("invalid App Attest certificate chain")

    leaf = x509.load_der_x509_certificate(x5c[0])
    intermediate = x509.load_der_x509_certificate(x5c[1])
    verify_app_attest_cert_chain(leaf, intermediate)

    client_data_hash = sha256(challenge.encode("utf-8"))
    expected_nonce = sha256(auth_data + client_data_hash)
    if not hmac.compare_digest(extract_app_attest_nonce(leaf), expected_nonce): raise ValueError("App Attest nonce mismatch")

    public_key = leaf.public_key()
    if not isinstance(public_key, ec.EllipticCurvePublicKey): raise ValueError("App Attest public key is not EC")
    if not hmac.compare_digest(decode_base64(public_key_x962_hash(public_key)), key_id_bytes): raise ValueError("App Attest key id mismatch")

    parsed_auth_data = parse_authenticator_data(auth_data, require_attested_credential_data=True)
    if not hmac.compare_digest(parsed_auth_data["rp_id_hash"], sha256(app_id.encode("utf-8"))): raise ValueError("App Attest RP ID mismatch")
    if parsed_auth_data["counter"] != 0: raise ValueError("App Attest initial counter is not zero")
    if not hmac.compare_digest(parsed_auth_data["credential_id"], key_id_bytes): raise ValueError("App Attest credential id mismatch")

    environment = ios_environment_from_aaguid(parsed_auth_data["aaguid"])
    if environment is None or environment not in ios_allowed_environments(): raise ValueError("App Attest environment mismatch")

    receipt = att_stmt.get("receipt")
    public_key_pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    return IosAttestationVerification(public_key_pem=public_key_pem, receipt_b64=encode_base64(receipt) if isinstance(receipt, bytes) else None, environment=environment)


def verify_ios_assertion_signature(*, public_key_pem: str, challenge: str, assertion_b64: str, key_id: str | None = None) -> int:
    app_id = ios_app_id()
    if app_id is None: raise ValueError("iOS App Attest app id is not configured")

    assertion = cbor2.loads(decode_base64(assertion_b64))
    if not isinstance(assertion, dict): raise ValueError("invalid App Attest assertion object")

    signature = assertion.get("signature")
    auth_data = assertion.get("authenticatorData")
    if not isinstance(signature, bytes) or not isinstance(auth_data, bytes): raise ValueError("invalid App Attest assertion payload")

    parsed_auth_data = parse_authenticator_data(auth_data, require_attested_credential_data=False)
    expected_rp_id_hash = sha256(app_id.encode("utf-8"))
    if not hmac.compare_digest(parsed_auth_data["rp_id_hash"], expected_rp_id_hash): raise ValueError("App Attest assertion RP ID mismatch")

    public_key = serialization.load_pem_public_key(public_key_pem.encode("ascii"))
    if not isinstance(public_key, ec.EllipticCurvePublicKey): raise ValueError("App Attest assertion public key is not EC")

    client_data_hash = sha256(challenge.encode("utf-8"))
    nonce = sha256(auth_data + client_data_hash)
    if key_id and not hmac.compare_digest(decode_base64(public_key_x962_hash(public_key)), decode_base64(key_id)): raise ValueError("stored App Attest public key does not match key id")

    signature_variants: list[bytes] = [signature]
    if len(signature) == 64:signature_variants.append(asymmetric_utils.encode_dss_signature(int.from_bytes(signature[:32], "big"), int.from_bytes(signature[32:], "big")))

    verification_attempts: list[tuple[bytes, ec.ECDSA]] = [(nonce, ec.ECDSA(asymmetric_utils.Prehashed(hashes.SHA256()))),     (auth_data + client_data_hash, ec.ECDSA(hashes.SHA256())),     (nonce, ec.ECDSA(hashes.SHA256())), ]

    for signature_variant in signature_variants:
        for signed_data, algorithm in verification_attempts:
            try:
                public_key.verify(signature_variant, signed_data, algorithm)
                return parsed_auth_data["counter"]

            except (InvalidSignature, ValueError): continue

    raise ValueError("invalid App Attest assertion signature")
