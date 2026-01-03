from __future__ import annotations
import json
from typing import Any, Dict
import logging
from urllib import request

import ollama
from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def _client() -> ollama.Client:
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


def generate_text(system: str, user: str) -> str:
    """
    คืนข้อความล้วน (ไม่บังคับ JSON) — เหมาะสุดสำหรับ summary
    """
    model = getattr(settings, "OLLAMA_MODEL", "llama3")
    try:
        resp = _client().chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.2},
        )
    except Exception as e:
        raise LLMError(str(e)) from e

    text = (resp.get("message", {}).get("content") or "").strip()
    return text


def generate_json(system: str, user: str) -> Dict[str, Any]:
    """
    (ยังเก็บไว้เผื่ออยากใช้ JSON) แต่ถ้าใช้แล้ว fail
    แนะนำให้ไปใช้ generate_text + postprocess แทน
    """
    import json

    model = getattr(settings, "OLLAMA_MODEL", "llama3")
    try:
        resp = _client().chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            format="json",
            options={"temperature": 0.2},
        )
    except Exception as e:
        raise LLMError(str(e)) from e

    raw = (resp.get("message", {}).get("content") or "").strip()
    try:
        return json.loads(raw)
    except Exception as e:
        logger.warning("Invalid JSON from model=%s raw=%r", model, raw[:300])
        raise LLMError(f"Invalid JSON: {raw[:200]}") from e

def generate_text_stream(system: str, user: str):
    model = getattr(settings, "OLLAMA_MODEL", "llama3")

    try:
        stream = _client().chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.2},
            stream=True,
        )

        for part in stream:
            # chunk รูปแบบประมาณ: {"message": {"role": "assistant", "content": "..."}, ...}
            chunk = (part.get("message", {}) or {}).get("content") or ""
            if chunk:
                yield chunk

    except Exception as e:
        raise LLMError(str(e)) from e