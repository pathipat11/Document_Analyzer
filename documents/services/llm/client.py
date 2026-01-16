from __future__ import annotations
import boto3, time, json, logging
from botocore.config import Config
from typing import Any, Dict, Iterator
from documents.models import LLMCallLog

from documents.services.llm.guardrails import check_daily_limit, incr_daily_limit
from documents.services.llm.token_ledger import can_spend, spend

from django.conf import settings

logger = logging.getLogger(__name__)

class LLMError(Exception):
    pass

# -------------------------
# Bedrock (Claude 3) client
# -------------------------
def _bedrock_runtime():
    region = getattr(settings, "AWS_REGION", "us-east-1")
    cfg = Config(
        retries={"max_attempts": 3, "mode": "standard"},
        connect_timeout=5,
        read_timeout=60,
    )
    return boto3.client("bedrock-runtime", region_name=region, config=cfg)


def _bedrock_model_id() -> str:
    # ใช้ inference profile ARN เป็น modelId ได้เลย
    model_id = getattr(settings, "BEDROCK_INFERENCE_PROFILE_ARN", "") or ""
    if not model_id:
        raise LLMError("Missing BEDROCK_INFERENCE_PROFILE_ARN in settings.")
    return model_id

def _build_claude_payload(system: str, user: str, *, max_tokens: int, temperature: float) -> Dict[str, Any]:
    # Claude 3.5 on Bedrock uses "anthropic_version": "bedrock-2023-05-31"
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

def _estimate_tokens(text: str) -> int:
    # heuristic: 1 token ~ 4 chars (คร่าว ๆ)
    t = (text or "").strip()
    return max(1, len(t) // 4)

# -------------------------
# Ollama client (fallback)
# -------------------------
def _ollama_client():
    import ollama
    host = getattr(settings, "OLLAMA_HOST", "http://localhost:11434")
    return ollama.Client(host=host)


def _provider() -> str:
    return (getattr(settings, "LLM_PROVIDER", "") or "ollama").lower().strip()

def _enforce_daily_limit(owner):
    """
    owner: Django User หรือ None
    - ถ้าไม่มี owner -> ไม่บังคับ (หรือคุณจะบังคับก็ได้)
    - ถ้ามี owner -> เช็ค quota
    """
    if not owner or not getattr(owner, "id", None):
        return
    if not check_daily_limit(owner.id):
        raise LLMError("Daily LLM limit reached. Please try again tomorrow.")



def generate_text(system: str, user: str, *, owner=None, purpose="") -> str:
    prov = _provider()
    t0 = time.time()
    
    _enforce_daily_limit(owner)

    # ---- precheck (token budget) ----
    if owner and getattr(owner, "id", None):
        est_in = _estimate_tokens((system or "") + "\n" + (user or ""))
        if not can_spend(owner.id, purpose, est_in):
            raise LLMError("Token budget is low or exhausted for this feature. Please try again tomorrow.")
    
    if prov == "bedrock":
        model_id = _bedrock_model_id()
        try:
            client = _bedrock_runtime()
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
            text = _extract_claude_text(data)
            
            if owner and getattr(owner, "id", None):
                incr_daily_limit(owner.id)

            usage = data.get("usage") or {}
            in_tok = int(usage.get("input_tokens") or 0)
            out_tok = int(usage.get("output_tokens") or 0)

            if owner and getattr(owner, "id", None):
                spend(owner.id, purpose, in_tok + out_tok)
                
            LLMCallLog.objects.create(
                owner=owner,
                provider="bedrock",
                model_id=model_id,
                purpose=purpose,
                ok=True,
                latency_ms=int((time.time() - t0) * 1000),
                input_tokens=in_tok,
                output_tokens=out_tok,
            )
            return text

        except Exception as e:
            LLMCallLog.objects.create(
                owner=owner,
                provider="bedrock",
                model_id=model_id,
                purpose=purpose,
                ok=False,
                error=str(e),
                latency_ms=int((time.time() - t0) * 1000),
            )
            raise LLMError(str(e)) from e

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
        in_tok = _estimate_tokens((system or "") + "\n" + (user or ""))
        out_tok = _estimate_tokens(text)

        if owner and getattr(owner, "id", None):
            spend(owner.id, purpose, in_tok + out_tok)

        LLMCallLog.objects.create(
            owner=owner,
            provider="ollama",
            model_id=model,
            purpose=purpose,
            ok=True,
            latency_ms=int((time.time() - t0) * 1000),
            input_tokens=in_tok,
            output_tokens=out_tok
        )
        return text

    except Exception as e:
        LLMCallLog.objects.create(
            owner=owner,
            provider="ollama",
            model_id=model,
            purpose=purpose,
            ok=False,
            error=str(e),
            latency_ms=int((time.time() - t0) * 1000),
        )
        raise LLMError(str(e)) from e


def generate_text_stream(system: str, user: str, *, owner=None, purpose="") -> Iterator[str]:
    prov = _provider()
    t0 = time.time()

    _enforce_daily_limit(owner)

    # ---- precheck (token budget) ----
    if owner and getattr(owner, "id", None):
        est_in = _estimate_tokens((system or "") + "\n" + (user or ""))
        if not can_spend(owner.id, purpose, est_in):
            raise LLMError("Token budget is low or exhausted for this feature. Please try again tomorrow.")

    # ---- Bedrock streaming ----
    if prov == "bedrock":
        model_id = _bedrock_model_id()

        # จะใช้ประมาณ token เพราะ stream ไม่ได้คืน usage ให้แบบตรง ๆ
        est_in = _estimate_tokens((system or "") + "\n" + (user or ""))
        est_out_acc = 0

        try:
            client = _bedrock_runtime()
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

            for event in stream:
                chunk = event.get("chunk")
                if not chunk:
                    continue
                b = chunk.get("bytes")
                if not b:
                    continue

                try:
                    payload = json.loads(b.decode("utf-8"))
                except Exception:
                    continue

                t = payload.get("type")

                if t == "content_block_delta":
                    delta = payload.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        text = delta.get("text") or ""
                        if text:
                            est_out_acc += _estimate_tokens(text)
                            yield text

            if owner and getattr(owner, "id", None):
                incr_daily_limit(owner.id)
                spend(owner.id, purpose, est_in + est_out_acc)

            LLMCallLog.objects.create(
                owner=owner,
                provider="bedrock",
                model_id=model_id,
                purpose=purpose,
                ok=True,
                latency_ms=int((time.time() - t0) * 1000),
                input_tokens=est_in,
                output_tokens=est_out_acc,
            )
            return

        except Exception as e:
            LLMCallLog.objects.create(
                owner=owner,
                provider="bedrock",
                model_id=model_id,
                purpose=purpose,
                ok=False,
                error=str(e),
                latency_ms=int((time.time() - t0) * 1000),
            )
            raise LLMError(str(e)) from e

    # ---- Ollama streaming ----
    model = getattr(settings, "OLLAMA_MODEL", "llama3")
    est_in = _estimate_tokens((system or "") + "\n" + (user or ""))
    est_out_acc = 0

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
                est_out_acc += _estimate_tokens(chunk)
                yield chunk

        if owner and getattr(owner, "id", None):
            incr_daily_limit(owner.id)
            spend(owner.id, purpose, est_in + est_out_acc)

        LLMCallLog.objects.create(
            owner=owner,
            provider="ollama",
            model_id=model,
            purpose=purpose,
            ok=True,
            latency_ms=int((time.time() - t0) * 1000),
            input_tokens=est_in,
            output_tokens=est_out_acc,
        )

    except Exception as e:
        LLMCallLog.objects.create(
            owner=owner,
            provider="ollama",
            model_id=model,
            purpose=purpose,
            ok=False,
            error=str(e),
            latency_ms=int((time.time() - t0) * 1000),
        )
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
