from __future__ import annotations

import json
import logging
from typing import Any, Dict, Iterator

from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


# -------------------------
# Bedrock (Claude 3) client
# -------------------------
def _bedrock_runtime():
    import boto3
    region = getattr(settings, "AWS_REGION", "us-east-1")
    return boto3.client("bedrock-runtime", region_name=region)


def _bedrock_model_id() -> str:
    # ใช้ inference profile ARN เป็น modelId ได้เลย
    model_id = getattr(settings, "BEDROCK_INFERENCE_PROFILE_ARN", "") or ""
    if not model_id:
        raise LLMError("Missing BEDROCK_INFERENCE_PROFILE_ARN in settings.")
    return model_id


def _build_claude_payload(system: str, user: str, *, max_tokens: int, temperature: float) -> Dict[str, Any]:
    # Claude 3 on Bedrock uses "anthropic_version": "bedrock-2023-05-31"
    # messages[].content is an array of blocks
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system or "",
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": user or ""}],
            }
        ],
    }


def _extract_claude_text(resp_json: Dict[str, Any]) -> str:
    # Typically: {"content":[{"type":"text","text":"..."}], ...}
    content = resp_json.get("content") or []
    parts = []
    for b in content:
        if isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text") or "")
    return ("".join(parts)).strip()


# -------------------------
# Ollama client (fallback)
# -------------------------
def _ollama_client():
    import ollama
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


def _provider() -> str:
    return (getattr(settings, "LLM_PROVIDER", "") or "ollama").lower().strip()


def generate_text(system: str, user: str) -> str:
    """
    คืนข้อความล้วน (ไม่บังคับ JSON)
    """
    prov = _provider()

    # ---- Bedrock path ----
    if prov == "bedrock":
        try:
            client = _bedrock_runtime()
            model_id = _bedrock_model_id()
            max_tokens = int(getattr(settings, "BEDROCK_MAX_TOKENS", 800))
            temperature = float(getattr(settings, "BEDROCK_TEMPERATURE", 0.2))

            body = _build_claude_payload(system, user, max_tokens=max_tokens, temperature=temperature)

            resp = client.invoke_model(
                modelId=model_id,
                body=json.dumps(body).encode("utf-8"),
                contentType="application/json",
                accept="application/json",
            )

            raw = resp["body"].read()
            data = json.loads(raw.decode("utf-8"))
            return _extract_claude_text(data)

        except Exception as e:
            raise LLMError(str(e)) from e

    # ---- Ollama path (existing) ----
    model = getattr(settings, "OLLAMA_MODEL", "llama3")
    try:
        resp = _ollama_client().chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.2},
        )
        text = (resp.get("message", {}).get("content") or "").strip()
        return text
    except Exception as e:
        raise LLMError(str(e)) from e


def generate_text_stream(system: str, user: str) -> Iterator[str]:
    """
    Stream tokens/chunks. For Bedrock Claude 3, use invoke_model_with_response_stream.
    """
    prov = _provider()

    # ---- Bedrock streaming ----
    if prov == "bedrock":
        try:
            client = _bedrock_runtime()
            model_id = _bedrock_model_id()
            max_tokens = int(getattr(settings, "BEDROCK_MAX_TOKENS", 800))
            temperature = float(getattr(settings, "BEDROCK_TEMPERATURE", 0.2))

            body = _build_claude_payload(system, user, max_tokens=max_tokens, temperature=temperature)

            resp = client.invoke_model_with_response_stream(
                modelId=model_id,
                body=json.dumps(body).encode("utf-8"),
                contentType="application/json",
                accept="application/json",
            )

            stream = resp.get("body")
            if not stream:
                return

            # Bedrock event stream: each event has chunk bytes containing json
            for event in stream:
                chunk = event.get("chunk")
                if not chunk:
                    continue
                b = chunk.get("bytes")
                if not b:
                    continue

                payload = json.loads(b.decode("utf-8"))

                # Claude 3 streaming events typically include:
                # - "type": "content_block_delta", delta: { "type":"text_delta", "text":"..." }
                # - "type": "message_delta", etc.
                t = payload.get("type")

                if t == "content_block_delta":
                    delta = payload.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        text = delta.get("text") or ""
                        if text:
                            yield text

                # Some SDKs emit "content_block_start" / "content_block_stop" / "message_stop"
                # We can ignore non-text events.

            return

        except Exception as e:
            raise LLMError(str(e)) from e

    # ---- Ollama streaming (existing) ----
    model = getattr(settings, "OLLAMA_MODEL", "llama3")
    try:
        stream = _ollama_client().chat(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            options={"temperature": 0.2},
            stream=True,
        )
        for part in stream:
            chunk = (part.get("message", {}) or {}).get("content") or ""
            if chunk:
                yield chunk
    except Exception as e:
        raise LLMError(str(e)) from e


def generate_json(system: str, user: str) -> Dict[str, Any]:
    """
    ถ้าคุณต้องการ JSON: แนะนำให้ทำแบบ "generate_text แล้วค่อย parse" เหมือนเดิม
    เพราะ Claude บน Bedrock ไม่ได้มี format="json" แบบ ollama
    """
    raw = generate_text(system, user)
    try:
        return json.loads(raw)
    except Exception as e:
        raise LLMError(f"Invalid JSON: {raw[:200]}") from e
