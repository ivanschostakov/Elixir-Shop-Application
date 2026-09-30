"""Erase an app account; retain only the existing order/settlement records.

Order foreign keys still require a User. Move those records to a new anonymous,
disabled owner, then DELETE the original User so cascade rules erase its data
and in-flight writes cannot recreate personal rows under the old account ID.
External/file deletion uses the existing durable provider-erasure worker.
"""
import secrets
from datetime import timedelta

from sqlalchemy import delete, or_, select, update

from config import ufa_now
from src.database import models as m
from src.database.models.ai.companion import AIProviderResource
from src.app.services.ai.companion.service import register_resource
from src.app.services.security import hash_password


async def erase_account(db, user):
    user_id = user.id
    await db.execute(select(m.User.id).where(m.User.id == user_id).with_for_update())

    paths = []

    async def queue_file(kind, path):
        paths.append((kind, str(path)))
        await register_resource(db, user_id, kind, str(path))

    chats = (await db.execute(select(m.AIChat).where(m.AIChat.user_id == user_id))).scalars().all()
    for chat in chats:
        await register_resource(db, user_id, "conversation", chat.conversation_id)
    attachments = (await db.execute(select(m.Attachment).join(m.AIMessage).where(m.AIMessage.user_id == user_id))).scalars().all()
    for attachment in attachments:
        await queue_file("local_file" if attachment.is_private else "public_ai_file", attachment.relative_path)

    conversations = select(m.CrmConversation.id).where(m.CrmConversation.customer_user_id == user_id)
    support_files = (await db.execute(select(m.CrmMessageAttachment, m.CrmMessage.conversation_id).join(m.CrmMessage).where(m.CrmMessage.conversation_id.in_(conversations)))).all()
    for attachment, conversation_id in support_files:
        await queue_file("support_file", f"{conversation_id}/{attachment.message_id}/{attachment.filename}")
    review_files = (await db.execute(select(m.ReviewAttachment).join(m.Review).where(m.Review.user_id == user_id))).scalars().all()
    for attachment in review_files:
        await queue_file("review_file", f"{attachment.review_id}/{attachment.filename}")

    authors = list((await db.execute(select(m.CommunityAuthor).where(m.CommunityAuthor.app_user_id == user_id))).scalars().all())
    author_ids = [author.id for author in authors]
    own_messages = or_(m.CommunityMessage.app_user_id == user_id, m.CommunityMessage.author_id.in_(author_ids))
    community_message_ids = select(m.CommunityMessage.id).where(own_messages)
    community_files = (await db.execute(select(m.CommunityAttachment).where(m.CommunityAttachment.message_id.in_(community_message_ids)))).scalars().all()
    for attachment in community_files:
        if attachment.local_filename:
            await queue_file("community_file", attachment.local_filename)
    await db.execute(delete(m.CommunityAttachment).where(m.CommunityAttachment.message_id.in_(community_message_ids)))
    # Keep empty tombstones so existing replies and Telegram mirror IDs stay valid.
    await db.execute(update(m.CommunityMessage).where(own_messages).values(text="", deleted_at=ufa_now(), updated_at=ufa_now(), app_user_id=None, delivery_status="sent", delivery_error=None, unsupported_type=None))
    for author in authors:
        if author.avatar_local_filename:
            await queue_file("community_avatar", author.avatar_local_filename)
        author.full_name = "Deleted member"
        author.kind = "deleted"
        author.telegram_peer_id = author.id
        author.app_user_id = None
        author.avatar_file_id = None
        author.avatar_local_filename = None
        author.avatar_refreshed_at = None
    await db.flush()

    # Erase publications and CRM notes rather than leaving identifiable content
    # behind when their nullable user foreign keys become NULL.
    for model, column in ((m.Review, m.Review.user_id), (m.ProductQuestion, m.ProductQuestion.user_id), (m.CrmLead, m.CrmLead.customer_user_id), (m.BannerClick, m.BannerClick.user_id), (m.BannerImpression, m.BannerImpression.user_id)):
        await db.execute(delete(model).where(column == user_id))
    await db.execute(delete(m.AdminAuditLog).where(m.AdminAuditLog.entity_type.in_(["user", "users", "customer", "customers"]), m.AdminAuditLog.entity_id == str(user_id)))

    # Telegram-linked journal/profile entries are part of the same app account.
    if user.telegram_user_id is not None:
        for model in (m.TelegramAIJournal, m.TelegramAIReminderSettings, m.TelegramAIProfile):
            await db.execute(delete(model).where(model.telegram_user_id == user.telegram_user_id))

    # Orders and settlement ledgers are not silently destroyed on account erasure.
    # Only addresses/recipients actually referenced by a submitted order survive.
    order_ids = list((await db.execute(select(m.Order.id).where(m.Order.user_id == user_id))).scalars().all())
    if order_ids:
        retained = m.User(name="Deleted", surname="Customer", password_hash=hash_password(secrets.token_urlsafe(48)), is_active=False, is_verified=False)
        db.add(retained)
        await db.flush()
        await db.execute(update(m.DeliveryAddress).where(m.DeliveryAddress.user_id == user_id, m.DeliveryAddress.id.in_(select(m.Order.delivery_address_id).where(m.Order.id.in_(order_ids)))).values(user_id=retained.id))
        await db.execute(update(m.DeliveryRecipient).where(m.DeliveryRecipient.user_id == user_id, m.DeliveryRecipient.id.in_(select(m.Order.recipient_id).where(m.Order.id.in_(order_ids)))).values(user_id=retained.id))
        await db.execute(update(m.Order).where(m.Order.id.in_(order_ids)).values(user_id=retained.id, draft_id=None))
        await db.execute(update(m.OrderItem).where(m.OrderItem.order_id.in_(order_ids)).values(user_id=retained.id))
        for model in (m.OrderBenefitApplication, m.LoyaltyBonusCredit):
            await db.execute(update(model).where(model.user_id == user_id).values(user_id=retained.id))

    # These early tables predate ON DELETE CASCADE. Delete them explicitly;
    # all modern personal tables are removed by their database cascade rules.
    for model in (m.UserSession, m.FavouredProduct, m.CdekPickupAddress, m.YandexPickupAddress, m.CdekDoorAddress):
        await db.execute(delete(model).where(model.user_id == user_id))
    # Drafts reference addresses without cascading; remove them first.
    await db.execute(delete(m.OrderDraft).where(m.OrderDraft.user_id == user_id))
    # Provider resources deliberately outlive the account until erasure succeeds.
    await db.execute(update(AIProviderResource).where(AIProviderResource.user_id == user_id).values(user_id=None, status="pending_delete", next_attempt_at=ufa_now() + timedelta(minutes=10)))
    await db.execute(delete(m.User).where(m.User.id == user_id))
    await db.commit()

    # Local files can be erased now; retryable provider cleanup waits for any
    # already-running model call. Failed unlinks remain queued, not forgotten.
    from src.app.services.ai.companion.jobs import delete_provider_resource
    for kind, path in paths:
        try:
            await delete_provider_resource(None, kind, path)
        except (OSError, ValueError):
            continue
        await db.execute(update(AIProviderResource).where(AIProviderResource.kind == kind, AIProviderResource.external_id == path, AIProviderResource.status == "pending_delete").values(status="deleted"))
    await db.commit()
