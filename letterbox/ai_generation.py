"""Cloud LLM (Groq) generation and template fallback for letter content."""

from __future__ import annotations

import json
import os
import re
import requests
from flask import current_app, has_app_context

from . import settings

REQUEST_TYPES = (
    "ML / Medical Leave",
    "OD / On Duty",
    "Permission",
    "Other",
)


class AIGenerationError(ValueError):
    """Raised when generation is unavailable or produces invalid output."""


def _extract_json(text: str) -> dict[str, object]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text or ""):
        if character != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise AIGenerationError("The AI model returned invalid JSON format.")


def _paragraphs(body: str) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", body or "").strip()
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    return [part.strip() for part in re.split(r"\n\s*\n+", normalized) if part.strip()]


def validate_generated_content(payload: object, original_description: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise AIGenerationError("The model response must be a JSON object.")
    if set(payload) != {"subject", "body"}:
        raise AIGenerationError("The model response has an invalid structure.")

    subject = payload.get("subject")
    body = payload.get("body")
    if not isinstance(subject, str) or not subject.strip():
        raise AIGenerationError("Generated subject is missing.")
    if not isinstance(body, str) or not body.strip():
        raise AIGenerationError("Generated body is missing.")

    if "\n" in subject or "\r" in subject:
        raise AIGenerationError("Generated subject is invalid.")
    subject = re.sub(r"\s+", " ", subject).strip()
    subject = re.sub(r"\s*-\s*(?:reg\.?|registration)$", "", subject, flags=re.IGNORECASE).strip(" .")
    subject = f"{subject}-reg."
    body = body.strip()
    if not subject or len(subject) > settings.AI_MAX_SUBJECT_LENGTH:
        raise AIGenerationError("Generated subject is invalid.")
    if len(body) > settings.AI_MAX_BODY_LENGTH:
        raise AIGenerationError("Generated body is too long.")
    if len(_paragraphs(body)) > 2:
        raise AIGenerationError("Generated body has too many paragraphs.")
    prohibited = r"(?im)^(?:from|to|date|dear|respected|yours sincerely|signature|digitally verified|ai)\s*:"
    if re.search(prohibited, body, re.IGNORECASE):
        raise AIGenerationError("Generated body contains a prohibited letter section.")

    return {"subject": subject, "body": body}


def _prompt(request_type: str, description: str, retry: bool = False) -> str:
    retry_instruction = " Previous output was rejected. Return exactly one or two paragraphs in body, separated by at most one blank line." if retry else ""
    return f"""You generate variable content for a formal university letter.{retry_instruction}
Request type: {request_type}
Student description: {description}

Return ONLY valid JSON with exactly two string keys: subject and body.
The subject must be one concise line. The body must be formal, concise, and at most two paragraphs.
Do not include From, To, Date, salutation, closing, signature, markdown, or any mention of AI."""


def _fallback_template_generation(request_type: str, description: str) -> dict[str, str]:
    """Provide a reliable fallback when external AI APIs are unconfigured or offline."""
    cleaned = re.sub(r"\s+", " ", description).strip()
    subject_map = {
        "ML / Medical Leave": "Requisition for Medical Leave",
        "OD / On Duty": "Requisition for On-Duty (OD) Permission",
        "Permission": "Permission Request for Academic Activity",
        "Other": "Formal Request Letter",
    }
    subj = subject_map.get(request_type, "Formal Letter Request")
    body = (
        f"I am writing this letter to formally request your kind approval regarding {cleaned}. "
        "Kindly review my request and grant the necessary permission at the earliest."
    )
    return {"subject": f"{subj}-reg.", "body": body}


def generate_letter_content(request_type: str, description: str) -> dict[str, str]:
    if request_type not in REQUEST_TYPES or not description.strip():
        raise AIGenerationError("Invalid letter generation input.")

    groq_api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_api_key:
        headers = {
            "Authorization": f"Bearer {groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a university administration letter assistant. Return ONLY valid JSON with string keys 'subject' and 'body'.",
                },
                {"role": "user", "content": _prompt(request_type, description)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        try:
            res = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=15,
            )
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            data = _extract_json(content)
            return validate_generated_content(data, description)
        except Exception as exc:
            if has_app_context():
                current_app.logger.warning("Groq AI generation fallback triggered: %s", exc)

    return _fallback_template_generation(request_type, description)