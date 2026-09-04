import aiofiles
import mimetypes
import hashlib

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any, TYPE_CHECKING
from uuid import uuid4
from fastapi import HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from config import (
    AI_CHAT_MAX_ATTACHMENTS,
    AI_CHAT_MAX_ATTACHMENT_BYTES,
    AI_CHAT_MAX_TOTAL_ATTACHMENT_BYTES,
    ufa_now,
)
from .chat_interactive import (
    attach_ai_action_tokens,
    build_ai_chat_output_schema,
    build_ai_interactive_payload,
    find_ai_interactive_action,
    load_ai_interactive_payload,
    parse_structured_ai_chat_output,
    verify_ai_action_token,
)
from .chat_tools import SHOP_AI_FUNCTION_TOOLS, ShopAIToolExecutor
from .pricing import calculate_openai_text_cost
from src.app.services.basket import add_variant_to_basket_for_user
from src.app.services.notifications.core import send_ai_reply_notification
from src.app.services.upload_limits import format_upload_size_limit, read_upload_file_limited
from src.database.crud import (
    create_ai_attachment,
    create_ai_chat,
    create_ai_message,
    create_ai_message_usage,
    get_ai_chat_by_id,
    get_ai_chat_by_user_id,
    update_ai_chat,
    update_ai_message,
)
from src.database.models import AIMessage, Order, User
from src.app.services.customer_intelligence import record_customer_event_safe
from src.database.models.ai.chat import AIChat
from src.database.schemas import (
    AIAttachmentCreate,
    AIChatCreate,
    AIChatUpdate,
    AIMessageCreate,
    AIMessageUpdate,
    AIMessageUsageCreate,
)
if TYPE_CHECKING:
    from src.integrations.ai.client import ProfessorClient
from src.integrations.ai.enums import AttachmentType, BotModel, MessageSender
from .schemas.chat import _LoadedUpload, AIChatActionResult, AIChatSendResult

PREMIUM_MONTHLY_PAID_ORDERS_THRESHOLD = Decimal("5000")
FAILED_PAYMENT_STATUSES = {"canceled", "error", "refunded"}
OPENAI_IMAGE_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".png", ".webp"}
HEIC_IMAGE_EXTENSIONS = {".heic", ".heif"}
OPENAI_IMAGE_EXTENSION_BY_MIME_TYPE = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
HEIC_IMAGE_MIME_TYPES = {"image/heic", "image/heif", "image/heic-sequence", "image/heif-sequence"}
SUPPORTED_CHAT_IMAGE_TYPES = "JPEG, PNG, GIF, WEBP, and HEIC"
AI_CHAT_EMPTY_REPLY = "Не смогла подготовить ответ. Попробуйте переформулировать запрос."


def _build_commerce_ai_input(text: str) -> str:
    return (
        "Контекст приложения: это чат магазина Elixir Peptide. "
        "Отвечай как уверенный консультант, который помогает выбрать и купить подходящий товар: живо, полезно, без сухого канцелярита. "
        "Для целей пользователя используй свои медицинские и физиологические знания, чтобы понять, какие классы/пептиды подходят; затем используй tools, чтобы найти совпадающие товары в каталоге, проверить наличие, цены и точные product_id/variant_id. "
        "Если пользователь спрашивает общо, например про похудение, сам предложи 2-4 сильных направления из доступного каталога вместо строгого отказа или длинных оговорок. "
        "Не выдумывай product_id, variant_id, цены, остатки и ссылки: эти данные только из tools. "
        "Когда называешь товар из каталога в assistant_text, делай название markdown-ссылкой вида [Семаглутид](/products/{id}). "
        "Заполняй product_refs только товарами, найденными через tools; карточки должны поддерживать рекомендации и продажу. "
        "Для каждого product_ref заполняй button_rows: это клавиатура карточки. Используй ключи open_product, compare, alternatives, checkout и variant:{variant_id}. "
        "Группируй связанные кнопки в строки по 1-3 штуки: главные действия можно делать одной заметной строкой, варианты дозировок обычно группируй по 2 в строку. "
        "Если пользователь уже выбрал нужный товар, ты добавляешь товар в корзину, или по данным get_my_basket корзина уже содержит нужные позиции и пользователь может быть готов завершать покупку, добавь checkout в отдельную заметную строку или рядом с главным действием. "
        "Не добавляй follow-up questions и не проси повторное подтверждение, если пользователь уже явно написал, что хочет купить/добавить товар. "
        "Заполняй basket_addition только когда пользователь явно хочет купить/добавить в корзину конкретный товар, точную дозировку/вариант и количество, а tools подтвердили variant_id и наличие. "
        "Если вариантов несколько, дозировка или количество неясны, не заполняй basket_addition; покажи подходящие товары и коротко попроси выбрать точный вариант. "
        "AI может добавлять только в корзину; не создавай черновики, финальные заказы и оплату.\n\n"
        f"Сообщение пользователя:\n{text}"
    )


def _ai_message_context(*, tool_executor: ShopAIToolExecutor, ai_result: dict[str, object]) -> dict[str, Any]:
    return {
        "tool_calls": tool_executor.calls,
        "tool_rounds": ai_result.get("tool_rounds") or 0,
    }


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12: next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else: next_month_start = month_start.replace(month=month_start.month + 1)
    return month_start, next_month_start


def _normalize_filename(filename: str | None, fallback_index: int) -> str:
    value = (filename or "").strip()
    if value: return Path(value).name
    return f"attachment_{fallback_index}"


def _attachment_type_from_upload(filename: str, mime_type: str | None) -> AttachmentType:
    extension = Path(filename).suffix.lower()
    if (mime_type or "").lower().startswith("image/") or extension in OPENAI_IMAGE_EXTENSIONS | HEIC_IMAGE_EXTENSIONS: return AttachmentType.IMAGE
    return AttachmentType.DOCUMENT


def _normalized_mime_type(mime_type: str | None) -> str | None:
    value = (mime_type or "").split(";", maxsplit=1)[0].strip().lower()
    return value or None


def _is_heic_image(filename: str, mime_type: str | None) -> bool: return Path(filename).suffix.lower() in HEIC_IMAGE_EXTENSIONS or _normalized_mime_type(mime_type) in HEIC_IMAGE_MIME_TYPES


def _load_pillow_image_modules():
    try: from PIL import Image, UnidentifiedImageError
    except ImportError as error: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Image processing is unavailable. Supported image formats: {SUPPORTED_CHAT_IMAGE_TYPES}") from error
    return Image, UnidentifiedImageError


def _register_heif_opener() -> None:
    try: from pillow_heif import register_heif_opener
    except ImportError as error: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="HEIC images are supported after the backend image dependencies are installed") from error
    register_heif_opener()


def _convert_image_to_jpeg(content: bytes) -> bytes:
    _register_heif_opener()
    Image, UnidentifiedImageError = _load_pillow_image_modules()
    try:
        with Image.open(BytesIO(content)) as uploaded_image:
            image = uploaded_image.convert("RGB")
            output = BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    
    except (UnidentifiedImageError, OSError, ValueError) as error: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded HEIC image is not valid") from error


def _openai_image_filename(filename: str, mime_type: str | None, fallback_index: int) -> str:
    path = Path(filename)
    stem = path.stem or f"attachment_{fallback_index}"
    extension = path.suffix.lower()
    if _is_heic_image(filename, mime_type): return f"{stem}.jpg"
    if extension in OPENAI_IMAGE_EXTENSIONS:return f"{stem}{extension}"

    mime_extension = OPENAI_IMAGE_EXTENSION_BY_MIME_TYPE.get(_normalized_mime_type(mime_type) or "")
    if mime_extension is not None: return f"{stem}{mime_extension}"

    if extension: return f"{stem}{extension}"
    return f"{stem}.jpg"


def _prepare_ai_upload(filename: str, content: bytes, *, mime_type: str | None, kind: AttachmentType, fallback_index: int) -> tuple[str, bytes]:
    if kind != AttachmentType.IMAGE: return filename, content

    ai_filename = _openai_image_filename(filename, mime_type, fallback_index)
    if _is_heic_image(filename, mime_type): return ai_filename, _convert_image_to_jpeg(content)
    if Path(ai_filename).suffix.lower() not in OPENAI_IMAGE_EXTENSIONS: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unsupported image format. Supported image formats: {SUPPORTED_CHAT_IMAGE_TYPES}")
    return ai_filename, content


def _response_attachment_type(kind: str | None) -> AttachmentType:
    if (kind or "").lower() == "image": return AttachmentType.IMAGE
    return AttachmentType.DOCUMENT


def _guess_mime_type(filename: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def _attachment_storage_filename(original_filename: str, mime_type: str | None) -> str:
    extension = Path(original_filename).suffix.lower()
    if 1 < len(extension) <= 16 and extension.replace(".", "").isalnum(): return f"{uuid4().hex}{extension}"

    guessed_extension = mimetypes.guess_extension(_normalized_mime_type(mime_type) or "")
    if guessed_extension == ".jpe": guessed_extension = ".jpg"
    if guessed_extension: return f"{uuid4().hex}{guessed_extension}"

    return uuid4().hex


async def _load_uploads(attachments: list[UploadFile] | None) -> list[_LoadedUpload]:
    uploads = attachments or []
    if len(uploads) > AI_CHAT_MAX_ATTACHMENTS: raise HTTPException( status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=f"Too many attachments. Maximum is {AI_CHAT_MAX_ATTACHMENTS}")

    loaded: list[_LoadedUpload] = []
    total_bytes = 0
    for index, upload in enumerate(uploads, start=1):
        content = await read_upload_file_limited(upload, max_bytes=AI_CHAT_MAX_ATTACHMENT_BYTES, label=f"Attachment {index}")
        if not content: continue
        total_bytes += len(content)
        if total_bytes > AI_CHAT_MAX_TOTAL_ATTACHMENT_BYTES: raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=f"Attachments exceed {format_upload_size_limit(AI_CHAT_MAX_TOTAL_ATTACHMENT_BYTES)} total")
        filename = _normalize_filename(upload.filename, index)
        mime_type = (upload.content_type or "").strip() or None
        kind = _attachment_type_from_upload(filename, mime_type)
        ai_filename, ai_content = _prepare_ai_upload(filename, content, mime_type=mime_type, kind=kind, fallback_index=index)
        loaded.append(_LoadedUpload(filename=filename, ai_filename=ai_filename, content=content, ai_content=ai_content, mime_type=mime_type, kind=kind))
    
    return loaded


async def _write_attachment_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as target_file: await target_file.write(content)


def _unlink_if_exists(path: Path) -> None:
    try: path.unlink(missing_ok=True)
    except Exception: return


async def _create_attachment_with_file(db: AsyncSession, *, message_id: int, attachment_type: AttachmentType, content: bytes, original_filename: str, mime_type: str | None, is_private: bool = False) -> Path:
    attachment = await create_ai_attachment(db, AIAttachmentCreate(message_id=message_id, is_private=is_private, type=attachment_type, original_filename=original_filename, filename=_attachment_storage_filename(original_filename, mime_type), mime_type=mime_type, size_bytes=len(content)), commit=False)
    await _write_attachment_file(attachment.path, content)
    return attachment.path


async def resolve_user_bot_model(db: AsyncSession, *, user_id: int) -> BotModel:
    now = ufa_now()
    month_start, next_month_start = _month_bounds(now)
    monthly_total = (await db.execute(select(func.coalesce(func.sum(Order.grand_total), 0)).where(Order.user_id == user_id).where(Order.is_paid.is_(True)).where(Order.is_canceled.is_(False)).where(Order.payment_paid_at.is_not(None)).where(Order.payment_paid_at >= month_start).where(Order.payment_paid_at < next_month_start).where(func.coalesce(Order.payment_status, "").notin_(FAILED_PAYMENT_STATUSES)))).scalar_one()
    total = Decimal(str(monthly_total or 0))
    return BotModel.PREMIUM if total > PREMIUM_MONTHLY_PAID_ORDERS_THRESHOLD else BotModel.FREE


async def get_or_create_user_chat(db: AsyncSession, *, user: User, professor_client: "ProfessorClient") -> AIChat:
    existing = await get_ai_chat_by_user_id(db, user.id)
    if existing is not None: return existing

    conversation_id = await professor_client.create_conversation(user_id=user.id)
    created = await create_ai_chat(db, AIChatCreate(user_id=user.id, conversation_id=conversation_id, current_tokens=0, total_tokens=0), commit=True)
    return created


async def send_user_chat_message(db: AsyncSession, *, user: User, text: str, attachments: list[UploadFile] | None, professor_client: "ProfessorClient", allow_commerce: bool = True, companion_profile=None, client_request_id: str | None = None, dialogue_protocol: int = 1) -> AIChatSendResult:
    chat = await get_or_create_user_chat(db, user=user, professor_client=professor_client)
    companion_profile_id = companion_profile.id if companion_profile is not None else None
    starting_conversation_id = chat.conversation_id
    loaded_uploads = await _load_uploads(attachments)
    input_fingerprint = hashlib.sha256((text + "\n" + "\n".join(hashlib.sha256(u.content).hexdigest() for u in loaded_uploads)).encode()).hexdigest()
    duplicate = None
    if client_request_id:
        duplicate = (await db.execute(select(AIMessage).where(AIMessage.user_id == user.id, AIMessage.client_request_id == client_request_id))).scalar_one_or_none()
        if duplicate is not None:
            if duplicate.text != text or (dialogue_protocol == 2 and (duplicate.context_json or {}).get("input_fingerprint", input_fingerprint) != input_fingerprint):
                raise HTTPException(409, "Ключ сообщения уже использован")
            if (duplicate.context_json or {}).get("generation_status") == "completed":
                return AIChatSendResult(chat=await get_ai_chat_by_id(db, chat.id, user_id=user.id), turn_meta={}, basket_updated=False)
            if dialogue_protocol != 2:
                raise HTTPException(409, "Сообщение сохранено, но ответ не завершён. Обновите чат; при необходимости отправьте новый запрос.")
    selected_model = await resolve_user_bot_model(db, user_id=user.id)
    user_attachment_paths: list[Path] = []
    ai_attachment_paths: list[Path] = []
    ai_message_id: int | None = None
    input_tokens = 0
    cached_input_tokens = 0
    output_tokens = 0
    ai_result: dict[str, object] | None = None
    basket_updated = False

    if companion_profile is not None:
        from .companion import service as companion_service
        companion_profile = await companion_service.assert_session_active(db, user.id, companion_profile_id)

    user_message = duplicate or await create_ai_message(db, AIMessageCreate( user_id=user.id, chat_id=chat.id, text=text, sender=MessageSender.USER, client_request_id=client_request_id, is_sensitive=companion_profile is not None, context_json={"input_fingerprint": input_fingerprint} if companion_profile is not None else None), commit=False)

    # Persist user message first so it is durable even if AI generation request is interrupted.
    try:
        for item in ([] if duplicate is not None else loaded_uploads):
            saved_path = await _create_attachment_with_file(db, message_id=user_message.id, attachment_type=item.kind, content=item.content, original_filename=item.filename, mime_type=item.mime_type, is_private=companion_profile is not None)
            user_attachment_paths.append(saved_path)

        await db.commit()

    except Exception:
        await db.rollback()
        for path in user_attachment_paths: _unlink_if_exists(path)
        raise

    if companion_profile is None:
        await record_customer_event_safe(
            db,
            user_id=user.id,
            event_name="ai_chat_message_sent",
            source="api",
            entity_type="ai_chat",
            entity_id=chat.id,
            properties={"message_id": user_message.id, "attachments_count": len(loaded_uploads)},
            commit=True,
        )

    try:
        if companion_profile is not None and dialogue_protocol == 2 and not loaded_uploads:
            from .companion import dialogue
            from .companion.schemas import Action
            direct = await dialogue.direct_reply(db, user.id, user_message)
            if direct is not None:
                if isinstance(direct, tuple):
                    source, card, kind = direct
                    await companion_service.apply_action(db, user.id, Action(request_key=f"text-message-{user_message.id}", kind=kind, message_id=source.id, action_id=card["id"], action_token=card["action_token"]), allow_commerce=allow_commerce)
                    await dialogue.say(db, user.id, "Подтверждено и сохранено." if kind == "dialogue_confirm" else "Черновик отменён.")
                user_message.context_json = {**(user_message.context_json or {}), "generation_status": "completed"}
                await db.commit()
                return AIChatSendResult(chat=await get_ai_chat_by_id(db, chat.id, user_id=user.id), turn_meta={}, basket_updated=False)
        file_contents = [(item.ai_filename, item.ai_content) for item in loaded_uploads if item.kind == AttachmentType.DOCUMENT]
        image_contents = [(item.ai_filename, item.ai_content) for item in loaded_uploads if item.kind == AttachmentType.IMAGE]
        tool_executor = ShopAIToolExecutor(db, user_id=user.id)
        companion_kwargs = {}
        function_tools = SHOP_AI_FUNCTION_TOOLS if allow_commerce else []
        if companion_profile is not None:
            from .companion import service as companion_service
            from .companion.tools import COMPANION_TOOLS, CompanionToolExecutor
            snapshot = await companion_service.context_for(db, user.id)
            if snapshot is None: raise HTTPException(403, "Сопровождение отключено")
            snapshot["commerce_allowed"] = allow_commerce
            if dialogue_protocol == 2:
                from .companion import dialogue
                flow = await dialogue.workflow(db, user.id, True)
                snapshot["dialogue"] = await dialogue.snapshot(db, user.id)
                dialogue_version = flow.version
                dialogue_guards = {kind: await dialogue.guard_for(db, user.id, kind) for kind in ("profile", "nutrition", "settings", "plan", "plan_status")}
            tool_executor = CompanionToolExecutor(db, user.id, shop=tool_executor if allow_commerce else None, dialogue=dialogue_protocol == 2)
            function_tools = [*COMPANION_TOOLS, *function_tools]
            if dialogue_protocol == 2:
                from .companion.dialogue_tools import DIALOGUE_TOOLS
                function_tools = [*COMPANION_TOOLS, *[t for t in DIALOGUE_TOOLS if allow_commerce or t["name"] != "match_course_products"]]
            if not allow_commerce:
                function_tools = [t for t in function_tools if t["name"] != "calculate_course_supply"]
            recent = list((await db.execute(select(AIMessage).where(AIMessage.chat_id == chat.id, AIMessage.id < user_message.id).order_by(AIMessage.id.desc()).limit(20))).scalars().all())
            replay = [{"role": "assistant" if m.sender == MessageSender.AI else "user", "content": m.text[:6000]} for m in reversed(recent)]
            async def record_resource(kind, external_id):
                # Erasure and provider callbacks serialize on the same user lock.
                await db.execute(select(User.id).where(User.id == user.id).with_for_update())
                await companion_service.register_resource(db, user.id, kind, external_id)
                await db.flush()
                active = await companion_service.profile_for(db, user.id)
                if active is None or active.id != companion_profile_id or not active.enabled:
                    from src.database.models.ai.companion import AIProviderResource
                    from sqlalchemy import update
                    await db.execute(update(AIProviderResource).where(AIProviderResource.kind == kind, AIProviderResource.external_id == external_id).values(status="pending_delete"))
                    await db.commit()
                    raise HTTPException(409, "Сопровождение отключено")
                await db.commit()
            companion_kwargs = {"companion_context": snapshot, "replay_history": replay, "resource_recorder": record_resource}

        ai_result = await professor_client.send_message_v2(
            input_text=text if companion_profile is not None else _build_commerce_ai_input(text) if allow_commerce else (
                "В этой версии приложения каталог и покупки недоступны. Не рекламируй товары, "
                "не предлагай покупку, скидки или переход в магазин. Не выполняй действия с корзиной. "
                "Отвечай на вопрос без коммерческих рекомендаций. product_refs=[], basket_addition=null.\n\n"
                + text
            ),
            conversation_id=chat.conversation_id,
            bot_model=selected_model,
            known_input_tokens=chat.current_tokens,
            file_contents=file_contents,
            image_contents=image_contents,
            user_id=user.id,
            function_tools=function_tools,
            function_tool_executor=tool_executor.execute if function_tools else None,
            output_schema=build_ai_chat_output_schema(include_companion=companion_profile is not None, dialogue=companion_profile is not None and dialogue_protocol == 2),
            output_schema_name="ai_chat_output",
            **companion_kwargs,
        )

        if companion_profile is not None:
            companion_profile = await companion_service.assert_session_active(db, user.id, companion_profile_id)
            current_conversation = (await db.execute(select(AIChat.conversation_id).where(AIChat.id == chat.id))).scalar_one()
            if current_conversation != starting_conversation_id:
                raise HTTPException(409, "Контекст сопровождения изменился. Отправьте запрос заново.")
            proposal_version = snapshot["profile_version"]
        input_tokens = int(ai_result.get("input_tokens") or 0)
        cached_input_tokens = int(ai_result.get("cached_input_tokens") or 0)
        output_tokens = int(ai_result.get("output_tokens") or 0)
        openai_model = str(ai_result.get("openai_model") or "")
        final_conversation_id = str(ai_result.get("conversation_id") or chat.conversation_id)
        structured_output = parse_structured_ai_chat_output(ai_result.get("structured_output") or ai_result.get("text"))
        reply_text = str(ai_result.get("text") or "").strip()
        if companion_profile is not None and structured_output is None:
            reply_text = "Не удалось обработать запись. Данные не изменены. Уточните запрос или попробуйте ещё раз."
        interactive_payload = None
        assistant_context = _ai_message_context(tool_executor=tool_executor, ai_result=ai_result)
        resolved_openai_model = openai_model or professor_client._resolve_model_name(selected_model)
        usage_cost = calculate_openai_text_cost(
            model=resolved_openai_model,
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            file_search_calls=int(ai_result.get("file_search_calls") or 0),
            occurred_at=ufa_now(),
        )
        if usage_cost is not None:
            assistant_context["usage_pricing"] = usage_cost.as_snapshot()
        if structured_output is not None:
            if companion_profile is not None:
                structured_output = structured_output.model_copy(update={"basket_addition": None})
            else:
                structured_output = structured_output.model_copy(update={"companion_proposals": []})
            if not allow_commerce:
                # Enforce this even if a generated reply ignores the prompt.
                structured_output = structured_output.model_copy(update={"product_refs": [], "basket_addition": None})
            reply_text = structured_output.assistant_text.strip() or reply_text
            assistant_context["structured_output"] = structured_output.model_dump(mode="json", exclude_none=True)
            interactive_payload = await build_ai_interactive_payload(db, structured_output) if allow_commerce else None
            if interactive_payload is not None:assistant_context["interactive"] = interactive_payload.model_dump(mode="json", exclude_none=True)
            if structured_output.basket_addition is not None:
                applied_items: list[dict[str, int]] = []
                try:
                    async with db.begin_nested():
                        for item in structured_output.basket_addition.items:
                            basket_item = await add_variant_to_basket_for_user(db, user_id=user.id, variant_id=item.variant_id, quantity=item.quantity, commit=False)
                            applied_items.append({"variant_id": item.variant_id, "quantity": item.quantity, "basket_item_id": basket_item.id})

                    if applied_items:
                        basket_updated = True
                        assistant_context["basket_addition_applied"] = applied_items
                        if interactive_payload is not None:
                            applied_by_variant_id = {item["variant_id"]: item for item in applied_items}
                            for card in interactive_payload.cards:
                                for action in card.actions:
                                    applied_item = applied_by_variant_id.get(action.variant_id or 0)
                                    if action.type != "add_to_basket" or applied_item is None: continue
                                    action.completed = True
                                    action.created_basket_item_id = applied_item["basket_item_id"]
                                    action.quantity = applied_item["quantity"]
                                    action.action_token = None
                                    action.label = "В корзине"

                except HTTPException as exc:
                    basket_updated = False
                    assistant_context["basket_addition_error"] = str(exc.detail)
                    reply_text = f"{reply_text}\n\n"f"Не получилось добавить товар в корзину: {exc.detail}".strip()

        ai_message = await create_ai_message(db, AIMessageCreate(user_id=user.id, chat_id=chat.id, text=reply_text or AI_CHAT_EMPTY_REPLY, sender=MessageSender.AI, context_json=assistant_context, is_sensitive=companion_profile is not None), commit=False)
        ai_message_id = ai_message.id
        if companion_profile is not None and structured_output is not None:
            if dialogue_protocol == 2:
                from .companion.dialogue_schemas import DialogueTurn
                await dialogue.attach_turn(db, user.id, ai_message, structured_output.companion_dialogue or DialogueTurn(), user_message, allow_commerce=allow_commerce, expected_workflow_version=dialogue_version, expected_guards=dialogue_guards)
            else:
                await companion_service.attach_proposals(db, user.id, ai_message, structured_output.companion_proposals, companion_profile, expected_version=proposal_version)
            assistant_context = dict(ai_message.context_json or {})
        await create_ai_message_usage(db, AIMessageUsageCreate( message_id=ai_message.id, input_tokens=input_tokens, cached_input_tokens=cached_input_tokens, output_tokens=output_tokens, bot_model=selected_model, openai_model=resolved_openai_model), commit=False)
        interactive_payload = attach_ai_action_tokens(interactive_payload, user_id=user.id, chat_id=chat.id, message_id=ai_message.id)
        if interactive_payload is not None:
            assistant_context["interactive"] = interactive_payload.model_dump(mode="json", exclude_none=True)
            await update_ai_message(db, ai_message, AIMessageUpdate(context_json=assistant_context), commit=False)

        for output_file in ai_result.get("files", []):
            if not isinstance(output_file, dict): continue
            payload = output_file.get("content")

            if not isinstance(payload, (bytes, bytearray)): continue
            filename = _normalize_filename(str(output_file.get("filename") or ""), len(user_attachment_paths) + len(ai_attachment_paths) + 1)
            mime_type = _guess_mime_type(filename)
            attachment_type = _response_attachment_type(output_file.get("kind"))
            saved_path = await _create_attachment_with_file(db, message_id=ai_message.id, attachment_type=attachment_type, content=bytes(payload), original_filename=filename, mime_type=mime_type, is_private=companion_profile is not None)
            ai_attachment_paths.append(saved_path)

        await update_ai_chat(db, chat, AIChatUpdate(conversation_id=final_conversation_id, current_tokens=int(ai_result.get("context_input_tokens") or input_tokens), total_tokens=int(chat.total_tokens) + input_tokens + output_tokens), commit=False)
        if companion_profile is not None:
            user_message.context_json = {**(user_message.context_json or {}), "generation_status": "completed"}
        await db.commit()

    except Exception:
        await db.rollback()
        for path in ai_attachment_paths: _unlink_if_exists(path)
        raise

    if interactive_payload is not None:
        await record_customer_event_safe(
            db,
            user_id=user.id,
            event_name="ai_recommendation_shown",
            source="api",
            entity_type="ai_message",
            entity_id=ai_message_id,
            properties={
                "chat_id": chat.id,
                "cards_count": len(interactive_payload.cards),
                "product_ids": [card.product_id for card in interactive_payload.cards],
            },
            commit=True,
        )
    if basket_updated:
        await record_customer_event_safe(
            db,
            user_id=user.id,
            event_name="ai_action_completed",
            source="api",
            entity_type="ai_message",
            entity_id=ai_message_id,
            properties={"chat_id": chat.id, "action_type": "auto_add_to_basket"},
            commit=True,
        )

    refreshed_chat = await get_ai_chat_by_id(db, chat.id, user_id=user.id)
    if refreshed_chat is None: raise RuntimeError("Failed to reload chat after update")
    if ai_message_id is not None: await send_ai_reply_notification(db, user_id=user.id, chat_id=chat.id, message_id=ai_message_id)

    return AIChatSendResult(chat=refreshed_chat, turn_meta={
        "selected_bot_model": selected_model,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "openai_model": openai_model or ProfessorClient._resolve_model_name(selected_model),
        "conversation_reset_reason": ai_result.get("conversation_reset_reason") if ai_result else None,
    }, basket_updated=basket_updated)


async def _get_locked_ai_message_for_action(session: AsyncSession, *, message_id: int, user_id: int) -> AIMessage | None:
    stmt = select(AIMessage).options(selectinload(AIMessage.attachments)).where(AIMessage.id == message_id).where(AIMessage.user_id == user_id).where(AIMessage.sender == MessageSender.AI).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def perform_user_ai_chat_action(db: AsyncSession, *, user: User, message_id: int, action_id: str, action_token: str, quantity: int | None = None) -> AIChatActionResult:
    try: token_payload = verify_ai_action_token(action_token)
    except ValueError as exc: raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="AI action token is invalid or expired") from exc

    if token_payload.user_id != user.id or token_payload.message_id != message_id or token_payload.action_id != action_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI action token does not match this request")

    basket_item_id: int | None = None
    try:
        message = await _get_locked_ai_message_for_action(db, message_id=message_id, user_id=user.id)
        if message is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI message was not found")
        chat_id = message.chat_id
        if token_payload.chat_id != chat_id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="AI action token does not match this chat")

        interactive = load_ai_interactive_payload(message.context_json)
        if interactive is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI message has no interactive action")

        action = find_ai_interactive_action(interactive, action_id)
        if action is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI action was not found")
        if action.type != "add_to_basket": raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI action is handled on the client")

        if action.completed and action.created_basket_item_id is not None:
            basket_item_id = action.created_basket_item_id
            await db.commit()
            refreshed_chat = await get_ai_chat_by_id(db, chat_id, user_id=user.id)
            if refreshed_chat is None: raise RuntimeError("Failed to reload chat after action")
            return AIChatActionResult(chat=refreshed_chat, basket_updated=True, basket_item_id=basket_item_id)

        if action.action_token != action_token: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="AI action is no longer available")
        if action.variant_id is None: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI basket action is missing a variant")

        selected_quantity = quantity or action.quantity or 1
        if selected_quantity < 1 or selected_quantity > 100: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="AI action quantity is invalid")

        basket_item = await add_variant_to_basket_for_user(db, user_id=user.id, variant_id=action.variant_id, quantity=selected_quantity, commit=False)
        basket_item_id = basket_item.id

        action.completed = True
        action.created_basket_item_id = basket_item_id
        action.action_token = None
        action.quantity = selected_quantity
        action.label = "В корзине"
        action.style = "secondary"

        context_json = dict(message.context_json or {})
        context_json["interactive"] = interactive.model_dump(mode="json", exclude_none=True)
        await update_ai_message(db, message, AIMessageUpdate(context_json=context_json), commit=False)
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    await record_customer_event_safe(
        db,
        user_id=user.id,
        event_name="ai_action_clicked",
        source="api",
        entity_type="ai_message",
        entity_id=message_id,
        properties={
            "chat_id": chat_id,
            "action_id": action_id,
            "action_type": "add_to_basket",
            "variant_id": action.variant_id,
        },
        commit=True,
    )
    await record_customer_event_safe(
        db,
        user_id=user.id,
        event_name="ai_action_completed",
        source="api",
        entity_type="ai_message",
        entity_id=message_id,
        properties={
            "chat_id": chat_id,
            "action_id": action_id,
            "action_type": "add_to_basket",
            "variant_id": action.variant_id,
            "basket_item_id": basket_item_id,
        },
        commit=True,
    )

    refreshed_chat = await get_ai_chat_by_id(db, chat_id, user_id=user.id)
    if refreshed_chat is None: raise RuntimeError("Failed to reload chat after action")
    return AIChatActionResult(chat=refreshed_chat, basket_updated=True, basket_item_id=basket_item_id)
