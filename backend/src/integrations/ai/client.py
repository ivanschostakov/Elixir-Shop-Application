import base64
import io
import json
import logging
import mimetypes
import time

from pathlib import Path
from typing import Any, Awaitable, Callable

from openai import AsyncClient, BadRequestError, NotFoundError
from openai.types.responses import FileSearchToolParam, Response, ResponseConversationParamParam, ToolParam
from openai.types.responses.tool import (
    CodeInterpreter,
    CodeInterpreterContainerCodeInterpreterToolAuto,
    ImageGeneration,
)

from config import AI_CONVERSATION_HARD_INPUT_TOKENS, AI_CONVERSATION_SOFT_INPUT_TOKENS, OPENAI_API_KEY
from src.app.services.ai_chat_tools import tool_output_json

from .enums import BotModel

FREE_VECTOR_STORE_ID = "vs_69e94b0c9e048191bf3cd7d79b6efbb6"
PREMIUM_VECTOR_STORE_ID = "vs_69e94b468f6481919aec96887cf97ac9"
FREE_MODEL = "gpt-4.1-mini"
PREMIUM_MODEL = "gpt-4.1"


class ProfessorClient(AsyncClient):
    def __init__(self, api_key: str | None = OPENAI_API_KEY):
        super().__init__(api_key=api_key)
        self.__logger = logging.getLogger(self.__class__.__name__)

    @property
    def log(self):
        return self.__logger

    async def aclose(self) -> None:
        await self.close()

    @staticmethod
    def _load_instructions(model: BotModel) -> str:
        instructions_path = Path(__file__).resolve().parent / "instructions" / f"{model.value}.txt"
        return instructions_path.read_text(encoding="utf-8")

    @staticmethod
    def _resolve_model_name(model: BotModel) -> str:
        if model == BotModel.PREMIUM:
            return PREMIUM_MODEL
        return FREE_MODEL

    @staticmethod
    def _build_tools(model: BotModel, function_tools: list[dict[str, Any]] | None = None) -> list[Any]:
        vector_store_id = PREMIUM_VECTOR_STORE_ID if model == BotModel.PREMIUM else FREE_VECTOR_STORE_ID
        tools: list[Any] = [
            FileSearchToolParam(type="file_search", vector_store_ids=[vector_store_id]),
        ]
        if model == BotModel.PREMIUM:
            tools += [
                CodeInterpreter(
                    container=CodeInterpreterContainerCodeInterpreterToolAuto(type="auto"),
                    type="code_interpreter",
                ),
                ImageGeneration(type="image_generation"),
            ]
        if function_tools:
            tools.extend(function_tools)
        return tools

    @staticmethod
    def _guess_mime_type(filename: str, fallback: str) -> str:
        guessed, _ = mimetypes.guess_type(filename or "")
        return guessed or fallback

    @staticmethod
    def _build_reasoning_payload(model: BotModel) -> dict[str, str] | None:
        return {"effort": "high", "summary": "detailed"} if model == "premium" else None

    async def transcribe_audio_bytes(self, filename: str, content: bytes) -> str:
        audio_file = io.BytesIO(content)
        audio_file.name = filename
        try:
            transcription = await self.audio.transcriptions.create(model="whisper-1", file=audio_file, language="ru")
        except Exception as exc:
            self.__logger.warning("Whisper transcription failed for %s: %s", filename, exc)
            return ""
        return (getattr(transcription, "text", None) or "").strip()

    async def create_conversation(self, user_id: int | None = None) -> str:
        metadata = {"user_id": str(user_id)} if user_id is not None else None
        conversation = await self.conversations.create(metadata=metadata if metadata else None)
        return conversation.id

    @staticmethod
    def _decode_image_payload(payload: str | None) -> bytes | None:
        raw = (payload or "").strip()
        if not raw:
            return None
        if raw.startswith("data:") and "," in raw:
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw, validate=False)
        except Exception:
            return None

    async def _extract_v2_files(self, response: Response, started_at: int) -> list[dict[str, Any]]:
        response_files: list[dict[str, Any]] = []
        seen_file_ids: set[str] = set()

        for idx, item in enumerate(getattr(response, "output", []) or []):
            item_type = getattr(item, "type", None)
            if item_type == "image_generation_call":
                image_bytes = self._decode_image_payload(getattr(item, "result", None))
                if not image_bytes:
                    continue
                image_name = f"imggen_{getattr(item, 'id', None) or idx}.png"
                response_files.append({"filename": image_name, "content": image_bytes, "kind": "image"})
                continue

            if item_type != "code_interpreter_call":
                continue

            container_id = getattr(item, "container_id", None)
            if not container_id:
                continue

            async for file in self.containers.files.list(container_id=container_id, order="desc", limit=100):
                file_id = getattr(file, "id", None)
                if not file_id or file_id in seen_file_ids:
                    continue
                seen_file_ids.add(file_id)

                file_created_at = int(getattr(file, "created_at", 0) or 0)
                if file_created_at and file_created_at < started_at:
                    break

                file_path = str(getattr(file, "path", "") or "")
                if file_path and not file_path.startswith("/mnt/data/"):
                    continue

                meta = await self.containers.files.retrieve(file_id, container_id=container_id)
                created_at = int(getattr(meta, "created_at", 0) or file_created_at or 0)
                if created_at and created_at < started_at:
                    continue

                file_name = Path(getattr(meta, "path", "") or f"{file_id}.bin").name or f"{file_id}.bin"
                content = await self.containers.files.content.retrieve(file_id, container_id=container_id)
                payload = await content.aread()
                if not payload:
                    continue
                response_files.append({"filename": file_name, "content": payload, "kind": "file"})

        return response_files

    @staticmethod
    def _extract_v2_text(response: Response) -> str:
        output_text = (getattr(response, "output_text", None) or "").strip()
        if output_text:
            return output_text

        text_chunks: list[str] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "message":
                continue
            for content_part in getattr(item, "content", []) or []:
                part_type = getattr(content_part, "type", None)
                if part_type == "output_text":
                    chunk = getattr(content_part, "text", None) or ""
                    if chunk:
                        text_chunks.append(chunk)
                elif part_type == "refusal":
                    chunk = getattr(content_part, "refusal", None) or ""
                    if chunk:
                        text_chunks.append(chunk)

        return "\n".join(text_chunks).strip()

    @staticmethod
    def _extract_v2_usage(response: Response) -> tuple[int, int, int]:
        usage = getattr(response, "usage", None)
        if not usage:
            return 0, 0, 0
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        input_details = getattr(usage, "input_tokens_details", None)
        cached_input_tokens = int(getattr(input_details, "cached_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        return input_tokens, cached_input_tokens, output_tokens

    @staticmethod
    def _extract_api_error_payload(exc: Exception) -> dict[str, Any] | None:
        body = getattr(exc, "body", None)
        if not isinstance(body, dict):
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    body = response.json()
                except Exception:
                    body = None
        if not isinstance(body, dict):
            return None
        nested_error = body.get("error")
        if isinstance(nested_error, dict):
            return nested_error
        return body

    @staticmethod
    def _should_retry_with_new_conversation(exc: Exception) -> bool:
        if not isinstance(exc, (BadRequestError, NotFoundError)):
            return False
        error_text = str(exc).lower()
        return "conversation" in error_text and (
            "not found" in error_text or "invalid" in error_text or "unknown" in error_text
        )

    @classmethod
    def _is_context_length_exceeded(cls, exc: Exception) -> bool:
        if not isinstance(exc, BadRequestError):
            return False
        error_payload = cls._extract_api_error_payload(exc) or {}
        error_code = str(error_payload.get("code") or getattr(exc, "code", "") or "").lower()
        if error_code == "context_length_exceeded":
            return True
        error_param = str(error_payload.get("param") or getattr(exc, "param", "") or "").lower()
        error_message = str(error_payload.get("message") or getattr(exc, "message", "") or exc).lower()
        return error_param == "input" and "context window" in error_message

    async def _upload_input_file(self, filename: str, payload: bytes) -> str:
        mime_type = self._guess_mime_type(filename, "application/octet-stream")
        uploaded = await self.files.create(file=(filename, payload, mime_type), purpose="user_data")
        return uploaded.id

    async def _build_v2_input_payload(
        self,
        input_text: str,
        *,
        file_contents: list[tuple[str, bytes]] | None = None,
        image_contents: list[tuple[str, bytes]] | None = None,
    ) -> str | list[dict[str, Any]]:
        normalized_text = (input_text or "").strip()
        files = file_contents or []
        images = image_contents or []

        if not files and not images:
            return normalized_text

        content: list[dict[str, Any]] = []
        if normalized_text:
            content.append({"type": "input_text", "text": normalized_text})

        for filename, payload in files:
            if not payload:
                continue
            file_id = await self._upload_input_file(filename, payload)
            content.append({"type": "input_file", "file_id": file_id})

        for filename, payload in images:
            if not payload:
                continue
            file_id = await self._upload_input_file(filename, payload)
            content.append({"type": "input_image", "detail": "high", "file_id": file_id})

        if not content:
            return normalized_text

        return [{"role": "user", "content": content}]

    async def _create_v2_response(
        self,
        *,
        model: BotModel,
        conversation_id: str,
        input_payload: Any,
        tools: list[Any],
        include: list[str] | None = None,
        text_config: dict[str, Any] | None = None,
    ) -> Response:
        payload: dict[str, Any] = {
            "model": self._resolve_model_name(model),
            "input": input_payload,
            "instructions": self._load_instructions(model),
            "conversation": ResponseConversationParamParam(id=conversation_id),
            "tools": tools,
            "include": include,
            "reasoning": self._build_reasoning_payload(model),
            "truncation": "auto",
        }
        if text_config is not None:
            payload["text"] = text_config
        return await self.responses.create(**payload)

    @staticmethod
    def _build_response_text_config(output_schema: dict[str, Any] | None, output_schema_name: str) -> dict[str, Any] | None:
        if not output_schema:
            return None
        return {
            "format": {
                "type": "json_schema",
                "name": output_schema_name,
                "strict": True,
                "schema": output_schema,
            }
        }

    @staticmethod
    def _extract_function_calls(response: Response) -> list[dict[str, str]]:
        calls: list[dict[str, str]] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            call_id = str(getattr(item, "call_id", None) or getattr(item, "id", None) or "").strip()
            name = str(getattr(item, "name", None) or "").strip()
            arguments = getattr(item, "arguments", None)
            if call_id and name:
                calls.append(
                    {
                        "call_id": call_id,
                        "name": name,
                        "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments or {}, ensure_ascii=False, default=str),
                    }
                )
        return calls

    @staticmethod
    def _extract_v2_structured_output(response_text: str) -> Any:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            return None

    async def _run_function_tool_rounds(
        self,
        *,
        response: Response,
        model: BotModel,
        conversation_id: str,
        tools: list[Any],
        include: list[str] | None,
        text_config: dict[str, Any] | None,
        function_tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None,
        max_tool_rounds: int,
        trace_id: str | None,
    ) -> tuple[Response, int, int]:
        if function_tool_executor is None:
            return response, 0, 0

        current_response = response
        tool_rounds = 0
        tool_calls_count = 0
        while True:
            function_calls = self._extract_function_calls(current_response)
            if not function_calls:
                return current_response, tool_rounds, tool_calls_count
            if tool_rounds >= max_tool_rounds:
                raise RuntimeError("Maximum AI tool rounds exceeded")

            tool_rounds += 1
            tool_calls_count += len(function_calls)
            tool_outputs: list[dict[str, Any]] = []
            for function_call in function_calls:
                try:
                    arguments = json.loads(function_call["arguments"] or "{}")
                    if not isinstance(arguments, dict):
                        arguments = {}
                except json.JSONDecodeError:
                    arguments = {}
                output = await function_tool_executor(function_call["name"], arguments)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": function_call["call_id"],
                        "output": tool_output_json(output),
                    }
                )

            self.__logger.info(
                "AI client tool round | trace=%s | conversation_id=%s | round=%d | calls=%d",
                trace_id,
                conversation_id,
                tool_rounds,
                len(function_calls),
            )
            current_response = await self._create_v2_response(
                model=model,
                conversation_id=conversation_id,
                input_payload=tool_outputs,
                tools=tools,
                include=include,
                text_config=text_config,
            )

    async def send_message_v2(
        self,
        *,
        input_text: str,
        conversation_id: str | None,
        bot_model: BotModel,
        known_input_tokens: int = 0,
        file_contents: list[tuple[str, bytes]] | None = None,
        image_contents: list[tuple[str, bytes]] | None = None,
        user_id: int | None = None,
        trace_id: str | None = None,
        function_tools: list[dict[str, Any]] | None = None,
        function_tool_executor: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
        max_tool_rounds: int = 4,
        output_schema: dict[str, Any] | None = None,
        output_schema_name: str = "ai_chat_output",
    ) -> dict[str, Any]:
        started_at = int(time.time())
        total_started = time.monotonic()
        self.__logger.info(
            "AI client start | trace=%s | user_id=%s | conversation_id=%s | model=%s | input_len=%d",
            trace_id,
            user_id,
            conversation_id,
            bot_model.value,
            len(input_text or ""),
        )

        input_payload = await self._build_v2_input_payload(
            input_text=input_text,
            file_contents=file_contents,
            image_contents=image_contents,
        )
        include = ["code_interpreter_call.outputs"] if bot_model == BotModel.PREMIUM else None
        tools = self._build_tools(bot_model, function_tools if function_tool_executor is not None else None)
        text_config = self._build_response_text_config(output_schema, output_schema_name)

        active_conversation_id = conversation_id
        had_existing_conversation = bool(active_conversation_id)
        conversation_reset_reason: str | None = None

        if not active_conversation_id:
            active_conversation_id = await self.create_conversation(user_id=user_id)
        elif known_input_tokens >= AI_CONVERSATION_HARD_INPUT_TOKENS:
            active_conversation_id = await self.create_conversation(user_id=user_id)
            conversation_reset_reason = "hard_input_limit_preemptive"
        elif known_input_tokens >= AI_CONVERSATION_SOFT_INPUT_TOKENS:
            active_conversation_id = await self.create_conversation(user_id=user_id)
            conversation_reset_reason = "soft_input_limit_preemptive"

        try:
            response = await self._create_v2_response(
                model=bot_model,
                conversation_id=active_conversation_id,
                input_payload=input_payload,
                tools=tools,
                include=include,
                text_config=text_config,
            )
        except Exception as exc:
            should_retry = self._should_retry_with_new_conversation(exc) or (
                had_existing_conversation and self._is_context_length_exceeded(exc)
            )
            if not should_retry:
                raise
            if user_id is None:
                raise

            conversation_reset_reason = (
                "invalid_conversation"
                if self._should_retry_with_new_conversation(exc)
                else "context_length_exceeded"
            )
            active_conversation_id = await self.create_conversation(user_id=user_id)
            response = await self._create_v2_response(
                model=bot_model,
                conversation_id=active_conversation_id,
                input_payload=input_payload,
                tools=tools,
                include=include,
                text_config=text_config,
            )

        response, tool_rounds, tool_calls = await self._run_function_tool_rounds(
            response=response,
            model=bot_model,
            conversation_id=active_conversation_id,
            tools=tools,
            include=include,
            text_config=text_config,
            function_tool_executor=function_tool_executor,
            max_tool_rounds=max_tool_rounds,
            trace_id=trace_id,
        )
        response_text = self._extract_v2_text(response)
        structured_output = self._extract_v2_structured_output(response_text) if text_config is not None else None
        response_files = await self._extract_v2_files(response, started_at)
        input_tokens, cached_input_tokens, output_tokens = self._extract_v2_usage(response)
        openai_model = str(getattr(response, "model", None) or self._resolve_model_name(bot_model))
        final_conversation_id = getattr(getattr(response, "conversation", None), "id", None) or active_conversation_id

        if input_tokens >= AI_CONVERSATION_HARD_INPUT_TOKENS:
            final_conversation_id = await self.create_conversation(user_id=user_id)
            conversation_reset_reason = conversation_reset_reason or "hard_input_limit_post_response"
        elif input_tokens >= AI_CONVERSATION_SOFT_INPUT_TOKENS:
            final_conversation_id = await self.create_conversation(user_id=user_id)
            conversation_reset_reason = conversation_reset_reason or "soft_input_limit_post_response"

        self.__logger.info(
            "AI client done | trace=%s | user_id=%s | conversation_id=%s | elapsed_ms=%d",
            trace_id,
            user_id,
            final_conversation_id,
            int((time.monotonic() - total_started) * 1000),
        )
        return {
            "text": response_text,
            "files": response_files,
            "input_tokens": int(input_tokens),
            "cached_input_tokens": int(cached_input_tokens),
            "output_tokens": int(output_tokens),
            "openai_model": openai_model,
            "conversation_id": str(final_conversation_id),
            "conversation_reset_reason": conversation_reset_reason,
            "structured_output": structured_output,
            "tool_rounds": tool_rounds,
            "tool_calls": tool_calls,
        }


professor_client = ProfessorClient()


def get_professor_client() -> ProfessorClient:
    return professor_client
