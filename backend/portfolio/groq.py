import json
import socket
from urllib import error, request

from django.conf import settings

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_HTTP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/147.0.0.0 Safari/537.36"
)


class GroqAPIError(Exception):
    """Raised when Groq configuration or upstream responses fail."""


def _extract_text(payload):
    choices = payload.get("choices") or []
    for choice in choices:
        message = choice.get("message") or {}
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
    return ""


def _extract_error_message(raw_body, fallback):
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body.strip() or fallback

    error_payload = payload.get("error") or {}
    if isinstance(error_payload, dict):
        message = error_payload.get("message", "")
        if isinstance(message, str) and message.strip():
            return message.strip()

    return fallback


def generate_groq_text(message):
    api_key = (getattr(settings, "GROQ_API_KEY", "") or "").strip()
    model = (getattr(settings, "GROQ_MODEL", "") or "llama-3.1-8b-instant").strip()
    timeout_seconds = max(1, int(getattr(settings, "GROQ_API_TIMEOUT_SECONDS", 20)))

    if not api_key:
        raise GroqAPIError("Groq is not configured on this server yet.")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful AI assistant for a video editor portfolio website.",
            },
            {
                "role": "user",
                "content": message,
            },
        ],
    }

    request_body = json.dumps(payload).encode("utf-8")
    groq_request = request.Request(
        GROQ_API_URL,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": GROQ_HTTP_USER_AGENT,
        },
        method="POST",
    )

    try:
        with request.urlopen(groq_request, timeout=timeout_seconds) as response:
            raw_response = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise GroqAPIError(
            _extract_error_message(
                raw_error,
                f"Groq request failed with HTTP {exc.code}.",
            )
        ) from exc
    except (error.URLError, socket.timeout, TimeoutError) as exc:
        raise GroqAPIError(
            "Unable to reach Groq right now. Please try again in a moment."
        ) from exc

    try:
        response_payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise GroqAPIError("Groq returned an unreadable response.") from exc

    response_text = _extract_text(response_payload)
    if response_text:
        return response_text

    raise GroqAPIError(
        _extract_error_message(
            raw_response,
            "Groq did not return a text response for that request.",
        )
    )
