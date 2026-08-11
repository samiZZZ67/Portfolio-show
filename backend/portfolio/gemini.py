import json
import socket
from urllib import error, request

from django.conf import settings

GEMINI_API_URL_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class GeminiAPIError(Exception):
    """Raised when Gemini configuration or upstream responses fail."""


def _extract_text(payload):
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        parts = content.get("parts") or []
        text_parts = [part.get("text", "") for part in parts if isinstance(part, dict)]
        merged = "".join(text_parts).strip()
        if merged:
            return merged
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

    prompt_feedback = payload.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason", "")
    if isinstance(block_reason, str) and block_reason.strip():
        return f"Gemini blocked that request ({block_reason.lower()})."

    return fallback


def generate_gemini_text(message):
    api_key = (getattr(settings, "GEMINI_API_KEY", "") or "").strip()
    model = (getattr(settings, "GEMINI_MODEL", "") or "gemini-2.5-flash").strip()
    timeout_seconds = max(1, int(getattr(settings, "GEMINI_API_TIMEOUT_SECONDS", 20)))

    if not api_key:
        raise GeminiAPIError("Gemini is not configured on this server yet.")

    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": message,
                    }
                ]
            }
        ]
    }

    request_body = json.dumps(payload).encode("utf-8")
    gemini_request = request.Request(
        GEMINI_API_URL_TEMPLATE.format(model=model),
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
        },
        method="POST",
    )

    try:
        with request.urlopen(gemini_request, timeout=timeout_seconds) as response:
            raw_response = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise GeminiAPIError(
            _extract_error_message(
                raw_error,
                f"Gemini request failed with HTTP {exc.code}.",
            )
        ) from exc
    except (error.URLError, socket.timeout, TimeoutError) as exc:
        raise GeminiAPIError(
            "Unable to reach Gemini right now. Please try again in a moment."
        ) from exc

    try:
        response_payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise GeminiAPIError("Gemini returned an unreadable response.") from exc

    response_text = _extract_text(response_payload)
    if response_text:
        return response_text

    raise GeminiAPIError(
        _extract_error_message(
            raw_response,
            "Gemini did not return a text response for that request.",
        )
    )
