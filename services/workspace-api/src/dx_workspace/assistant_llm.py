# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Desktiny contributors
"""Calls to the LLM services the help assistant can use.

Claude goes through the official Anthropic SDK; OpenAI, DeepSeek and Gemini through their
REST APIs, at endpoints fixed here.

An administrator may also point the assistant at their own gateway that speaks the Anthropic
Messages, OpenAI Chat Completions or OpenAI Responses protocol, or at a model server the office
runs itself: Ollama (its own /api/chat, so the context window can be set) or vLLM (OpenAI Chat
Completions). Those two usually run without an API key. Such a URL must be HTTPS on a
public address; private, loopback and link-local addresses (and plain HTTP) are refused unless
the host is listed in ASSISTANT_ALLOWED_HOSTS. The check runs when the URL is saved and again
before every call, and redirects are never followed.

Ollama and vLLM live on the office network by nature, so for them an administrator may enter a
private or plain-HTTP address directly, like any other service. What keeps that from being a way
into other internal systems: the address must be the server root (or /v1), so only the fixed
model-server paths are ever called, and link-local addresses (where clouds serve instance
credentials) stay refused.
"""

from __future__ import annotations

import base64
import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import anthropic
import httpx

TIMEOUT_SECONDS = 60
# A model on the office's own hardware may answer slowly, especially the first call that loads it.
SELF_HOSTED_TIMEOUT_SECONDS = 180
# Ollama's default context is a few thousand tokens and it silently drops the oldest text when a
# prompt is longer, which here is the system rules. Ask for a window the knowledge excerpts fit in.
OLLAMA_CONTEXT_TOKENS = 16384
MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,120}$")
# Gateways often route by names such as "openrouter/anthropic/claude" or "auto"; the model is
# only ever sent in the JSON body for these, never placed in a URL.
CUSTOM_MODEL_PATTERN = re.compile(r"^[A-Za-z0-9._:/@-]{1,120}$")

# Shown in the settings screen. Suggested models are only a starting point; the
# administrator types the model their account has access to.
KINDS = {
    "anthropic": {"label": "Claude (Anthropic)", "suggested_model": "claude-opus-5-5"},
    "openai": {"label": "OpenAI (ChatGPT)", "suggested_model": ""},
    "gemini": {"label": "Google Gemini", "suggested_model": ""},
    "deepseek": {"label": "DeepSeek", "suggested_model": "deepseek-chat"},
    "custom_anthropic": {
        "label": "Cổng tương thích Anthropic Messages",
        "suggested_model": "auto",
        "custom": True,
    },
    "custom_chat": {
        "label": "Cổng tương thích OpenAI Chat Completions",
        "suggested_model": "auto",
        "custom": True,
    },
    "custom_responses": {
        "label": "Cổng tương thích OpenAI Responses",
        "suggested_model": "auto",
        "custom": True,
    },
    "ollama": {
        "label": "Ollama",
        "suggested_model": "",
        "custom": True,
        "self_hosted": True,
        "key_optional": True,
        "default_base_url": "http://localhost:11434",
    },
    "vllm": {
        "label": "vLLM",
        "suggested_model": "",
        "custom": True,
        "self_hosted": True,
        "key_optional": True,
        "default_base_url": "http://localhost:8000/v1",
    },
}
CUSTOM_PATHS = {
    "custom_anthropic": "/messages",
    "custom_chat": "/chat/completions",
    "custom_responses": "/responses",
    "vllm": "/chat/completions",
    "ollama": "/api/chat",
}
# Where each kind lists the models it serves, for the "fetch models" button.
MODEL_LIST_PATHS = {
    "custom_chat": "/models",
    "custom_responses": "/models",
    "custom_anthropic": "/models",
    "vllm": "/models",
    "ollama": "/api/tags",
}
# Where hosted services list the models a key may use.
MODEL_LIST_URLS = {
    "openai": "https://api.openai.com/v1/models",
    "deepseek": "https://api.deepseek.com/models",
    "anthropic": "https://api.anthropic.com/v1/models?limit=1000",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
}
# Model lists mix chat, embedding, speech and image models; names tell them apart well enough.
EMBEDDING_NAME = re.compile(r"embed|bge|(^|[-_/])e5|gte|minilm|arctic", re.IGNORECASE)
NOT_CHAT_NAME = re.compile(
    r"tts|whisper|dall-e|moderation|image|transcribe|audio|realtime|rerank", re.IGNORECASE
)
THINKING = re.compile(r"<think>.*?(</think>\s*|$)", re.DOTALL)
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Claude models that accept the server-side refusal fallback and the effort setting.
CLAUDE_FALLBACK_MODELS = {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
CLAUDE_EFFORT_PREFIXES = (
    "claude-fable-5",
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-opus-4-6",
    "claude-sonnet-5",
    "claude-sonnet-4-6",
    "claude-haiku-5",
)


class LlmError(Exception):
    """A failure worth showing to people, in plain Vietnamese."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class Reply:
    text: str
    truncated: bool = False


@dataclass
class Attachment:
    """A file sent along with the last question: an image, or a PDF for services that read PDFs."""

    name: str
    mime: str
    data: bytes

    @property
    def b64(self) -> str:
        return base64.b64encode(self.data).decode()

    @property
    def data_url(self) -> str:
        return f"data:{self.mime};base64,{self.b64}"

    @property
    def is_pdf(self) -> bool:
        return self.mime == "application/pdf"


# Services that read PDF files themselves (so a scanned PDF still works). Others get the text a
# PDF carries, extracted on our side, and can only look at images.
READS_PDF = {"anthropic", "openai", "gemini", "custom_anthropic", "custom_responses"}
# DeepSeek's chat API takes text only.
NO_FILES = {"deepseek"}
OPENAI_EMBED_URL = "https://api.openai.com/v1/embeddings"
GEMINI_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"
# Which kinds can turn text into vectors for search by meaning, and where they do it.
EMBED_KINDS = {"openai", "gemini", "ollama", "vllm", "custom_chat"}


def reads_pdf(kind: str) -> bool:
    return kind in READS_PDF


def _with_files(kind: str, messages: list[dict], files: list[Attachment]) -> list[dict]:
    """Attach files to the last user message in the shape each protocol expects."""
    if not files:
        return messages
    if kind in NO_FILES:
        raise LlmError("assistant_no_vision", "Dịch vụ AI này chỉ đọc chữ, không xem được ảnh hay tệp.")
    if any(f.is_pdf for f in files) and kind not in READS_PDF:
        raise LlmError("assistant_no_pdf", "Dịch vụ AI này không đọc trực tiếp được tệp PDF.")
    *head, last = messages
    text = last["content"]
    if kind in {"anthropic", "custom_anthropic"}:
        parts = [
            {
                "type": "document" if f.is_pdf else "image",
                "source": {"type": "base64", "media_type": f.mime, "data": f.b64},
            }
            for f in files
        ]
        return [*head, {"role": "user", "content": [*parts, {"type": "text", "text": text}]}]
    if kind == "gemini":
        parts = [{"inline_data": {"mime_type": f.mime, "data": f.b64}} for f in files]
        return [*head, {"role": "user", "content": text, "parts": [*parts, {"text": text}]}]
    if kind == "ollama":
        return [*head, {"role": "user", "content": text, "images": [f.b64 for f in files]}]
    if kind == "custom_responses":
        parts = [
            {"type": "input_file", "filename": f.name, "file_data": f.data_url}
            if f.is_pdf
            else {"type": "input_image", "image_url": f.data_url}
            for f in files
        ]
        return [*head, {"role": "user", "content": [{"type": "input_text", "text": text}, *parts]}]
    parts = [
        {"type": "file", "file": {"filename": f.name, "file_data": f.data_url}}
        if f.is_pdf
        else {"type": "image_url", "image_url": {"url": f.data_url}}
        for f in files
    ]
    return [*head, {"role": "user", "content": [{"type": "text", "text": text}, *parts]}]


def is_custom(kind: str) -> bool:
    return kind in CUSTOM_PATHS


def key_optional(kind: str) -> bool:
    return bool(KINDS.get(kind, {}).get("key_optional"))


def self_hosted(kind: str) -> bool:
    return bool(KINDS.get(kind, {}).get("self_hosted"))


def check_model(kind: str, model: str) -> None:
    pattern = CUSTOM_MODEL_PATTERN if is_custom(kind) else MODEL_PATTERN
    if not pattern.match(model):
        raise LlmError(
            "assistant_model_invalid", "Tên model chỉ gồm chữ, số và . _ : - (cổng riêng cho phép thêm / @)."
        )


def resolve_host(host: str) -> list[str]:
    """Every address a host name points to. Kept separate so tests can replace it."""
    return list({info[4][0] for info in socket.getaddrinfo(host, None)})


def check_base_url(url: str, allowed_hosts: set[str], kind: str = "custom_chat") -> str:
    """The gateway base URL, normalised to end in its API version (".../v1").

    Ollama's own API has no version segment, so its URL is kept at the server root.
    """
    value = url.strip().rstrip("/")
    if kind == "ollama":
        value = re.sub(r"/(v1|api)$", "", value)
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise LlmError("assistant_url_invalid", "Địa chỉ cổng không hợp lệ.") from exc
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"https", "http"} or not host or parts.username or parts.password:
        raise LlmError("assistant_url_invalid", "Nhập địa chỉ dạng https://ten-may-chu/v1.")
    if parts.query or parts.fragment:
        raise LlmError("assistant_url_invalid", "Địa chỉ cổng không được chứa ? hay #.")
    trusted = host in allowed_hosts
    if self_hosted(kind) and not trusted:
        return _self_hosted_base(kind, value, host, parts.path)
    if parts.scheme == "http" and not trusted:
        raise LlmError(
            "assistant_url_insecure",
            "Cổng phải dùng HTTPS. Muốn dùng HTTP trong mạng nội bộ, thêm máy chủ vào ASSISTANT_ALLOWED_HOSTS.",
        )
    if not trusted:
        try:
            addresses = [ipaddress.ip_address(a.split("%")[0]) for a in resolve_host(host)]
        except (OSError, ValueError) as exc:
            raise LlmError("assistant_url_unresolved", f"Không tìm thấy máy chủ “{host}”.") from exc
        if not addresses or any(not a.is_global for a in addresses):
            raise LlmError(
                "assistant_url_private",
                f"“{host}” là địa chỉ nội bộ. Chỉ dùng được khi quản trị hệ thống thêm nó vào ASSISTANT_ALLOWED_HOSTS.",
            )
    if kind != "ollama" and not re.search(r"/v\d+$", parts.path):
        value += "/v1"
    return value


def _self_hosted_base(kind: str, value: str, host: str, path: str) -> str:
    """An Ollama or vLLM address on any network except link-local, at the server root only."""
    if path not in ({""} if kind == "ollama" else {"", "/v1"}):
        example = "http://192.168.1.20:11434" if kind == "ollama" else "http://192.168.1.20:8000/v1"
        raise LlmError(
            "assistant_url_invalid",
            f"Chỉ nhập địa chỉ gốc của máy chủ, ví dụ {example}, không kèm đường dẫn khác.",
        )
    try:
        addresses = [ipaddress.ip_address(a.split("%")[0]) for a in resolve_host(host)]
    except (OSError, ValueError) as exc:
        raise LlmError("assistant_url_unresolved", f"Không tìm thấy máy chủ “{host}”.") from exc
    if not addresses or any(a.is_link_local or a.is_multicast or a.is_unspecified for a in addresses):
        raise LlmError("assistant_url_private", f"Không dùng được địa chỉ “{host}” cho máy chủ AI.")
    return value if kind == "ollama" or path else value + "/v1"


def endpoint(kind: str, base_url: str) -> str:
    return base_url + CUSTOM_PATHS[kind]


def complete(
    kind: str,
    model: str,
    api_key: str,
    system: str,
    messages: list[dict],
    max_tokens: int,
    transport=None,
    base_url: str | None = None,
    allowed_hosts: set[str] | None = None,
    files: list[Attachment] | None = None,
) -> Reply:
    """Send one chat turn. `messages` alternate user/assistant and end with the user's question.

    `files` (images, or PDFs where `reads_pdf`) go with that last question.
    """
    if kind not in KINDS:
        raise LlmError("assistant_kind_invalid", "Loại dịch vụ AI không được hỗ trợ.")
    check_model(kind, model)
    messages = _with_files(kind, messages, files or [])
    if not api_key and not key_optional(kind):
        raise LlmError("assistant_key_missing", "Dịch vụ AI chưa có khóa API.")
    if is_custom(kind):
        # Checked again here: a name that was public when saved may point elsewhere now.
        base = check_base_url(base_url or "", allowed_hosts or set(), kind)
        if kind == "ollama":
            return _ollama(endpoint(kind, base), model, api_key, system, messages, max_tokens, transport)
        if kind == "custom_anthropic":
            return _anthropic(model, api_key, system, messages, max_tokens, transport, base_url=base)
        if kind == "custom_responses":
            return _responses(endpoint(kind, base), model, api_key, system, messages, max_tokens, transport)
        return _openai_style(
            endpoint(kind, base), kind, model, api_key, system, messages, max_tokens, transport
        )
    if kind == "anthropic":
        return _anthropic(model, api_key, system, messages, max_tokens, transport)
    if kind == "gemini":
        return _gemini(model, api_key, system, messages, max_tokens, transport)
    url = OPENAI_URL if kind == "openai" else DEEPSEEK_URL
    return _openai_style(url, kind, model, api_key, system, messages, max_tokens, transport)


def _anthropic(model, api_key, system, messages, max_tokens, transport, base_url: str | None = None) -> Reply:
    client = anthropic.Anthropic(
        api_key=api_key,
        # The SDK adds "/v1/messages" itself, so a gateway's ".../v1" base is passed without it.
        base_url=base_url.removesuffix("/v1") if base_url else None,
        # The SDK authenticates with a bearer token; gateways that follow the Messages API
        # read x-api-key, so it is sent too.
        default_headers={"x-api-key": api_key} if base_url else None,
        timeout=TIMEOUT_SECONDS,
        max_retries=1,
        http_client=anthropic.DefaultHttpxClient(transport=transport, follow_redirects=False)
        if transport or base_url
        else None,
    )
    params = {"model": model, "max_tokens": max_tokens, "system": system, "messages": messages}
    # A help chat does not need deep reasoning; low effort keeps answers quick and cheap.
    # Gateways get a plain request: they may not know these Claude-specific options.
    if not base_url and model.startswith(CLAUDE_EFFORT_PREFIXES):
        params["output_config"] = {"effort": "low"}
    try:
        if not base_url and model in CLAUDE_FALLBACK_MODELS:
            # If a safety classifier declines, the API retries on a suitable model itself.
            response = client.beta.messages.create(
                **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default"
            )
        else:
            response = client.messages.create(**params)
    except anthropic.AuthenticationError as exc:
        raise LlmError("assistant_key_invalid", "Khóa API Anthropic không hợp lệ.") from exc
    except anthropic.PermissionDeniedError as exc:
        raise LlmError("assistant_forbidden", "Khóa API không được phép dùng model này.") from exc
    except anthropic.NotFoundError as exc:
        raise LlmError("assistant_model_not_found", f"Không tìm thấy model “{model}”.") from exc
    except anthropic.RateLimitError as exc:
        raise LlmError("assistant_rate_limited", "Dịch vụ AI đang quá tải hoặc đã hết hạn mức.") from exc
    except anthropic.BadRequestError as exc:
        raise LlmError("assistant_bad_request", f"Dịch vụ AI từ chối yêu cầu: {exc.message}") from exc
    except anthropic.APIStatusError as exc:
        raise LlmError("assistant_upstream_error", "Dịch vụ AI đang gặp sự cố. Thử lại sau.") from exc
    except anthropic.APIConnectionError as exc:
        raise LlmError("assistant_unreachable", "Không kết nối được tới dịch vụ AI.") from exc
    if response.stop_reason == "refusal":
        raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return Reply(text=text, truncated=response.stop_reason == "max_tokens")


def _http_error(kind: str, response: httpx.Response, model: str) -> LlmError:
    try:
        error = response.json().get("error")
        # OpenAI-style services nest the message; Ollama and vLLM may send a plain string.
        detail = error.get("message", "") if isinstance(error, dict) else str(error or "")
    except (ValueError, AttributeError):
        detail = ""
    status = response.status_code
    if status in (401, 403):
        return LlmError("assistant_key_invalid", "Khóa API không hợp lệ hoặc không có quyền.")
    if status == 404 or (kind == "ollama" and "not found" in detail):
        hint = f" Trên máy chủ Ollama, chạy: ollama pull {model}" if kind == "ollama" else ""
        return LlmError("assistant_model_not_found", f"Không tìm thấy model “{model}”.{hint}")
    if status == 429:
        return LlmError("assistant_rate_limited", "Dịch vụ AI đang quá tải hoặc đã hết hạn mức.")
    if 400 <= status < 500:
        return LlmError("assistant_bad_request", f"Dịch vụ AI từ chối yêu cầu: {detail or status}")
    return LlmError("assistant_upstream_error", "Dịch vụ AI đang gặp sự cố. Thử lại sau.")


def _post(url: str, headers: dict, body: dict, transport, timeout: int = TIMEOUT_SECONDS) -> httpx.Response:
    try:
        with httpx.Client(timeout=timeout, transport=transport, follow_redirects=False) as client:
            return client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise LlmError("assistant_timeout", "Dịch vụ AI phản hồi quá lâu.") from exc
    except httpx.TransportError as exc:
        raise LlmError("assistant_unreachable", "Không kết nối được tới dịch vụ AI.") from exc


def _bearer(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


def _without_thinking(text: str) -> str:
    """Reasoning models served as-is (qwen3, deepseek-r1) put their thinking in <think> tags."""
    return THINKING.sub("", text)


def _openai_style(url, kind, model, api_key, system, messages, max_tokens, transport) -> Reply:
    body = {"model": model, "messages": [{"role": "system", "content": system}, *messages]}
    # OpenAI's newer models only accept max_completion_tokens; DeepSeek and gateways keep max_tokens.
    body["max_completion_tokens" if kind == "openai" else "max_tokens"] = max_tokens
    timeout = SELF_HOSTED_TIMEOUT_SECONDS if self_hosted(kind) else TIMEOUT_SECONDS
    response = _post(url, _bearer(api_key), body, transport, timeout)
    if response.status_code != 200:
        raise _http_error(kind, response, model)
    try:
        choice = response.json()["choices"][0]
        text = choice["message"].get("content") or ""
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về dữ liệu không đọc được.") from exc
    if choice.get("finish_reason") == "content_filter":
        raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    if self_hosted(kind):
        text = _without_thinking(text)
    return Reply(text=text.strip(), truncated=choice.get("finish_reason") == "length")


def _ollama(url, model, api_key, system, messages, max_tokens, transport) -> Reply:
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "stream": False,
        "options": {"num_ctx": OLLAMA_CONTEXT_TOKENS, "num_predict": max_tokens},
    }
    response = _post(url, _bearer(api_key), body, transport, SELF_HOSTED_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise _http_error("ollama", response, model)
    try:
        data = response.json()
        text = data["message"].get("content") or ""
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về dữ liệu không đọc được.") from exc
    return Reply(text=_without_thinking(text).strip(), truncated=data.get("done_reason") == "length")


def list_models(
    kind: str,
    base_url: str,
    api_key: str,
    allowed_hosts: set[str],
    transport=None,
    purpose: str = "chat",
) -> list[str]:
    """Models a service offers for `purpose` ("chat" or "embed"), for the administrator to pick."""
    if kind in MODEL_LIST_URLS:
        url = MODEL_LIST_URLS[kind]
    elif kind in MODEL_LIST_PATHS:
        url = check_base_url(base_url, allowed_hosts, kind) + MODEL_LIST_PATHS[kind]
    else:
        raise LlmError("assistant_models_unsupported", "Dịch vụ này không có danh sách model để lấy.")
    if kind in {"anthropic", "custom_anthropic"}:
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    elif kind == "gemini":
        headers = {"x-goog-api-key": api_key}
    else:
        headers = _bearer(api_key)
    try:
        with httpx.Client(timeout=TIMEOUT_SECONDS, transport=transport, follow_redirects=False) as client:
            response = client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise LlmError("assistant_timeout", "Dịch vụ AI phản hồi quá lâu.") from exc
    except httpx.TransportError as exc:
        raise LlmError("assistant_unreachable", "Không kết nối được tới dịch vụ AI.") from exc
    if response.status_code != 200:
        raise _http_error(kind, response, "")
    try:
        data = response.json()
        if kind == "ollama":
            names = [item["name"] for item in data["models"]]
        elif kind == "gemini":
            method = "embedContent" if purpose == "embed" else "generateContent"
            names = [
                item["name"].removeprefix("models/")
                for item in data["models"]
                if method in (item.get("supportedGenerationMethods") or [])
            ]
        else:
            names = [item["id"] for item in data["data"]]
    except (ValueError, KeyError, TypeError) as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về danh sách model không đọc được.") from exc
    names = [n for n in names if isinstance(n, str) and CUSTOM_MODEL_PATTERN.match(n)]
    if kind != "gemini":
        if purpose == "embed":
            names = [n for n in names if EMBEDDING_NAME.search(n)]
        else:
            names = [n for n in names if not EMBEDDING_NAME.search(n) and not NOT_CHAT_NAME.search(n)]
    return sorted(set(names))


def _gemini(model, api_key, system, messages, max_tokens, transport) -> Reply:
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": m.get("parts") or [{"text": m["content"]}],
            }
            for m in messages
        ],
        "generationConfig": {"maxOutputTokens": max_tokens},
    }
    url = GEMINI_URL.format(model=quote(model, safe=""))
    response = _post(url, {"x-goog-api-key": api_key}, body, transport)
    if response.status_code != 200:
        raise _http_error("gemini", response, model)
    try:
        data = response.json()
    except ValueError as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về dữ liệu không đọc được.") from exc
    if data.get("promptFeedback", {}).get("blockReason"):
        raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    candidates = data.get("candidates") or []
    if not candidates:
        raise LlmError("assistant_bad_response", "Dịch vụ AI không trả về câu trả lời.")
    candidate = candidates[0]
    if candidate.get("finishReason") in {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST"}:
        raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    parts = candidate.get("content", {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought"))
    return Reply(text=text.strip(), truncated=candidate.get("finishReason") == "MAX_TOKENS")


def _responses(url, model, api_key, system, messages, max_tokens, transport) -> Reply:
    """OpenAI Responses protocol: instructions + input items, text in output message items."""
    body = {
        "model": model,
        "instructions": system,
        "input": [{"role": m["role"], "content": m["content"]} for m in messages],
        "max_output_tokens": max_tokens,
    }
    response = _post(url, {"Authorization": f"Bearer {api_key}"}, body, transport)
    if response.status_code != 200:
        raise _http_error("custom_responses", response, model)
    try:
        data = response.json()
        text = data.get("output_text") or "".join(
            part.get("text", "")
            for item in data.get("output") or []
            if item.get("type") == "message"
            for part in item.get("content") or []
            if part.get("type") == "output_text"
        )
    except (ValueError, AttributeError, TypeError) as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về dữ liệu không đọc được.") from exc
    for item in data.get("output") or []:
        for part in item.get("content") or []:
            if part.get("type") == "refusal":
                raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    reason = (data.get("incomplete_details") or {}).get("reason")
    if reason == "content_filter":
        raise LlmError("assistant_refused", "Trợ lý không thể trả lời câu hỏi này.")
    return Reply(text=text.strip(), truncated=reason == "max_output_tokens")


def embed(
    kind: str,
    model: str,
    api_key: str,
    texts: list[str],
    base_url: str | None = None,
    allowed_hosts: set[str] | None = None,
    transport=None,
) -> list[list[float]]:
    """Vectors for `texts`, in order, from a service that offers embeddings."""
    if kind not in EMBED_KINDS:
        raise LlmError(
            "assistant_embed_unsupported", "Dịch vụ này không tạo được vector cho tìm theo ý nghĩa."
        )
    check_model(kind, model)
    if not api_key and not key_optional(kind):
        raise LlmError("assistant_key_missing", "Dịch vụ AI chưa có khóa API.")
    timeout = SELF_HOSTED_TIMEOUT_SECONDS if self_hosted(kind) else TIMEOUT_SECONDS
    if kind == "gemini":
        url = GEMINI_EMBED_URL.format(model=quote(model, safe=""))
        body = {
            "requests": [{"model": f"models/{model}", "content": {"parts": [{"text": x}]}} for x in texts]
        }
        response = _post(url, {"x-goog-api-key": api_key}, body, transport, timeout)
    elif kind == "openai":
        response = _post(
            OPENAI_EMBED_URL, _bearer(api_key), {"model": model, "input": texts}, transport, timeout
        )
    else:
        base = check_base_url(base_url or "", allowed_hosts or set(), kind)
        path = "/api/embed" if kind == "ollama" else "/embeddings"
        response = _post(base + path, _bearer(api_key), {"model": model, "input": texts}, transport, timeout)
    if response.status_code != 200:
        raise _http_error(kind, response, model)
    try:
        data = response.json()
        if kind == "gemini":
            vectors = [item["values"] for item in data["embeddings"]]
        elif kind == "ollama":
            vectors = data["embeddings"]
        else:
            vectors = [
                item["embedding"] for item in sorted(data["data"], key=lambda item: item.get("index", 0))
            ]
    except (ValueError, KeyError, TypeError) as exc:
        raise LlmError("assistant_bad_response", "Dịch vụ AI trả về vector không đọc được.") from exc
    if len(vectors) != len(texts):
        raise LlmError("assistant_bad_response", "Số vector trả về không khớp số đoạn gửi đi.")
    return [[float(v) for v in vector] for vector in vectors]
