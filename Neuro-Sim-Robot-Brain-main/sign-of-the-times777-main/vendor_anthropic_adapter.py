"""
Concrete non-OpenAI cognition adapter example.

This module provides a plug-and-play adapter for Anthropic's Messages API,
and can be used as a vendor template for any non-OpenAI LLM API.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from cognition_layer import BaseLLMAdapter


class AnthropicMessagesAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Messages API.

    API reference shape (request -> response):
    POST /v1/messages
    {
      "model": "claude-...",
      "max_tokens": 300,
      "system": "...",
      "messages": [{"role": "user", "content": "..."}]
    }
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str = "https://api.anthropic.com",
        endpoint: str = "/v1/messages",
        timeout_sec: float = 2.5,
        anthropic_version: str = "2023-06-01",
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.api_base = api_base.rstrip("/")
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.timeout_sec = max(float(timeout_sec), 0.1)
        self.anthropic_version = anthropic_version.strip() or "2023-06-01"
        self.extra_headers = dict(extra_headers or {})

        if not self.api_key:
            raise ValueError("api_key is required")
        if not self.model:
            raise ValueError("model is required")
        if not self.api_base:
            raise ValueError("api_base is required")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": self.anthropic_version,
        }
        headers.update(self.extra_headers)
        return headers

    def _build_payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": self.model,
            "max_tokens": 300,
            "temperature": 0.1,
            "system": (
                "You are the slow cognition layer for a safety-critical mobile robot. "
                "Return strict JSON with keys: decision, plan, explanation, recovery, memory_update. "
                "Only choose decision from: avoid_obstacle, explore, navigate_careful, stop, null."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }

    @staticmethod
    def _extract_text(payload: Dict[str, Any]) -> str:
        content = payload.get("content")
        if isinstance(content, list):
            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(str(part.get("text", "")))
            if texts:
                return "\n".join(texts).strip()

        # Fallback for vendor gateways that flatten output
        output_text = payload.get("output_text")
        if output_text is not None:
            return str(output_text).strip()

        return ""

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        del context
        url = f"{self.api_base}{self.endpoint}"
        body = json.dumps(self._build_payload(prompt)).encode("utf-8")
        req = urllib.request.Request(url=url, data=body, headers=self._headers(), method="POST")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Vendor API connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Vendor API response was not valid JSON") from exc

        text = self._extract_text(parsed)
        if not text:
            return {}

        try:
            if text.startswith("{"):
                return json.loads(text)
        except json.JSONDecodeError:
            pass

        return {"explanation": text}


def anthropic_adapter_from_env() -> AnthropicMessagesAdapter:
    """Build adapter from environment variables.

    Required:
    - SPINN_ANTHROPIC_API_KEY
    - SPINN_ANTHROPIC_MODEL

    Optional:
    - SPINN_ANTHROPIC_API_BASE
    - SPINN_ANTHROPIC_ENDPOINT
    - SPINN_ANTHROPIC_TIMEOUT_SEC
    - SPINN_ANTHROPIC_VERSION
    - SPINN_ANTHROPIC_EXTRA_HEADERS_JSON
    """

    api_key = os.getenv("SPINN_ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("SPINN_ANTHROPIC_MODEL", "").strip()
    api_base = os.getenv("SPINN_ANTHROPIC_API_BASE", "https://api.anthropic.com").strip()
    endpoint = os.getenv("SPINN_ANTHROPIC_ENDPOINT", "/v1/messages").strip()
    timeout_sec = float(os.getenv("SPINN_ANTHROPIC_TIMEOUT_SEC", "2.5"))
    version = os.getenv("SPINN_ANTHROPIC_VERSION", "2023-06-01").strip()
    extra_headers_raw = os.getenv("SPINN_ANTHROPIC_EXTRA_HEADERS_JSON", "").strip()

    extra_headers: Dict[str, str] = {}
    if extra_headers_raw:
        try:
            decoded = json.loads(extra_headers_raw)
            if isinstance(decoded, dict):
                extra_headers = {str(k): str(v) for k, v in decoded.items()}
        except json.JSONDecodeError as exc:
            raise ValueError("SPINN_ANTHROPIC_EXTRA_HEADERS_JSON must be valid JSON") from exc

    return AnthropicMessagesAdapter(
        api_key=api_key,
        model=model,
        api_base=api_base,
        endpoint=endpoint,
        timeout_sec=timeout_sec,
        anthropic_version=version,
        extra_headers=extra_headers,
    )
