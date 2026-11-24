import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from uuid import uuid4

import cbor2
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import config
import src.app.services.app_integrity.common as common
from src.app.services.app_integrity import service
from src.database.models import AppAttestKey, AppIntegrityChallenge, User

pytestmark = pytest.mark.real_app_integrity


@asynccontextmanager
async def account(monkeypatch):
    monkeypatch.setattr(common, "APP_INTEGRITY_IOS_TEAM_ID", "TEAMID1234")
    monkeypatch.setattr(common, "APP_INTEGRITY_IOS_BUNDLE_ID", "com.example.test")
    engine = create_async_engine(config.ASYNC_DB_URL, poolclass=NullPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    user_id = None
    private_key = ec.generate_private_key(ec.SECP256R1())
    key_id = common.public_key_x962_hash(private_key.public_key())
    try:
        async with sessions() as db:
            user = User(email=f"integrity-{uuid4().hex}@example.test", name="Integrity", surname="Test", password_hash="test-only")
            db.add(user)
            await db.flush()
            user_id = user.id
            db.add(AppAttestKey(user_id=user_id, key_id=key_id, environment="production", public_key_pem=private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode(), counter=0, is_active=True))
            await db.commit()
        yield sessions, user_id, key_id, private_key
    finally:
        if user_id is not None:
            async with sessions() as db:
                await db.execute(delete(AppIntegrityChallenge).where(AppIntegrityChallenge.user_id == user_id))
                await db.execute(delete(AppAttestKey).where(AppAttestKey.user_id == user_id))
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        await engine.dispose()


def assertion(private_key, challenge, counter):
    auth_data = common.sha256(common.ios_app_id().encode()) + b"\x00" + counter.to_bytes(4, "big")
    nonce = common.sha256(auth_data + common.sha256(challenge.encode()))
    signature = private_key.sign(nonce, ec.ECDSA(utils.Prehashed(hashes.SHA256())))
    return common.encode_base64(cbor2.dumps({"authenticatorData": auth_data, "signature": signature}))


async def permit(db, user_id, key_id, private_key, counter, action):
    challenge = await service.create_app_integrity_challenge(db, user_id=user_id, platform="ios", purpose="assertion", action=action)
    return await service.preverify_ios_app_attest_assertion(db, user_id=user_id, key_id=key_id, challenge=challenge.challenge, assertion=assertion(private_key, challenge.challenge, counter), action=action)


async def consume(db, user_id, key_id, grant, action):
    return await service._verify_ios_app_attest_assertion(db, user_id=user_id, key_id=key_id, challenge=grant.challenge, assertion=service.IOS_ASSERTION_GRANT_PREFIX + grant.challenge, action=action)


def test_signed_workout_and_community_proofs_can_finish_in_reverse_order_without_replay(monkeypatch):
    async def run():
        async with account(monkeypatch) as (sessions, user_id, key_id, private_key):
            async with sessions() as db:
                workout = await permit(db, user_id, key_id, private_key, 1, "ai-companion")
                community = await permit(db, user_id, key_id, private_key, 2, "community:read")
                assert await consume(db, user_id, key_id, community, "community:read") == (True, None)
                assert await consume(db, user_id, key_id, workout, "ai-companion") == (True, None)
                assert (await consume(db, user_id, key_id, workout, "ai-companion"))[0] is False
                key = (await db.execute(select(AppAttestKey).where(AppAttestKey.user_id == user_id))).scalar_one()
                assert key.counter == 2
    asyncio.run(run())


@pytest.mark.parametrize("tamper", ["user", "action", "key", "nonce", "expired", "revoked"])
def test_verified_permits_keep_all_authorization_boundaries(monkeypatch, tamper):
    async def run():
        async with account(monkeypatch) as (sessions, user_id, key_id, private_key):
            async with sessions() as db:
                grant = await permit(db, user_id, key_id, private_key, 1, "ai-companion")
                if tamper == "expired":
                    grant.expires_at = config.ufa_now() - timedelta(seconds=1)
                    await db.commit()
                if tamper == "revoked":
                    key = (await db.execute(select(AppAttestKey).where(AppAttestKey.user_id == user_id))).scalar_one()
                    key.is_active = False
                    await db.commit()
                challenge = "different-nonce" if tamper == "nonce" else grant.challenge
                verified, _ = await service._verify_ios_app_attest_assertion(db,
                    user_id=user_id + 100000 if tamper == "user" else user_id,
                    key_id="different-key" if tamper == "key" else key_id,
                    challenge=challenge, assertion=service.IOS_ASSERTION_GRANT_PREFIX + grant.challenge,
                    action="community:read" if tamper == "action" else "ai-companion")
                assert verified is False
    asyncio.run(run())


def test_a_permit_cannot_mint_another_permit_or_accept_a_stale_counter(monkeypatch):
    async def run():
        async with account(monkeypatch) as (sessions, user_id, key_id, private_key):
            async with sessions() as db:
                grant = await permit(db, user_id, key_id, private_key, 2, "ai-companion")
                with pytest.raises(HTTPException) as error:
                    await service.preverify_ios_app_attest_assertion(db, user_id=user_id, key_id=key_id, challenge=grant.challenge, assertion=service.IOS_ASSERTION_GRANT_PREFIX + grant.challenge, action="ai-companion")
                assert error.value.status_code == 400
                with pytest.raises(HTTPException) as error:
                    await permit(db, user_id, key_id, private_key, 1, "ai-companion")
                assert error.value.status_code == 403
                assert await consume(db, user_id, key_id, grant, "ai-companion") == (True, None)
    asyncio.run(run())


def test_invalid_signature_never_creates_a_permit(monkeypatch):
    async def run():
        async with account(monkeypatch) as (sessions, user_id, key_id, private_key):
            async with sessions() as db:
                challenge = await service.create_app_integrity_challenge(db, user_id=user_id, platform="ios", purpose="assertion", action="ai-companion")
                wrong_key = ec.generate_private_key(ec.SECP256R1())
                with pytest.raises(HTTPException) as error:
                    await service.preverify_ios_app_attest_assertion(db, user_id=user_id, key_id=key_id, challenge=challenge.challenge, assertion=assertion(wrong_key, challenge.challenge, 1), action="ai-companion")
                assert error.value.status_code == 403
                await db.rollback()
                rows = list((await db.scalars(select(AppIntegrityChallenge).where(AppIntegrityChallenge.user_id == user_id))).all())
                assert len(rows) == 1 and rows[0].purpose == "assertion"
    asyncio.run(run())


def test_two_concurrent_consumers_cannot_reuse_one_permit(monkeypatch):
    async def run():
        async with account(monkeypatch) as (sessions, user_id, key_id, private_key):
            async with sessions() as db:
                grant = await permit(db, user_id, key_id, private_key, 1, "ai-companion")
            async def use():
                async with sessions() as db:
                    return await consume(db, user_id, key_id, grant, "ai-companion")
            results = await asyncio.gather(use(), use())
            assert sorted(result[0] for result in results) == [False, True]
    asyncio.run(run())
