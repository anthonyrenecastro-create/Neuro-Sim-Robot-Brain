"""
Universal slow-brain cognition layer for SPINN Robot Brain.

This module provides:
- A non-blocking cognition worker for planning/explanations/memory/recovery
- A pluggable adapter interface for any LLM HTTP API
- A default OpenAI-compatible adapter that works with many OSS/self-hosted gateways
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class CognitionDirective:
    """Structured output from the slow brain."""

    decision: Optional[str]
    plan: str
    explanation: str
    recovery: str
    memory_update: str
    timestamp: float
    source: str = "slow_brain"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "plan": self.plan,
            "explanation": self.explanation,
            "recovery": self.recovery,
            "memory_update": self.memory_update,
            "timestamp": self.timestamp,
            "source": self.source,
        }


class BaseLLMAdapter(ABC):
    """Interface for pluggable LLM backends."""

    @abstractmethod
    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Return a dict that may include decision/plan/explanation/recovery/memory_update."""


class OpenAICompatibleAdapter(BaseLLMAdapter):
    """Adapter for OpenAI-compatible chat completion APIs.

    Many OSS runtimes expose this contract, including local gateways.
    """

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        endpoint: str = "/chat/completions",
        timeout_sec: float = 2.5,
        auth_header: str = "Authorization",
        auth_scheme: str = "Bearer",
        extra_headers: Optional[Dict[str, str]] = None,
    ):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key.strip()
        self.model = model.strip()
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.timeout_sec = max(float(timeout_sec), 0.1)
        self.auth_header = auth_header.strip() or "Authorization"
        self.auth_scheme = auth_scheme.strip()
        self.extra_headers = extra_headers or {}

        if not self.api_base:
            raise ValueError("api_base is required")
        if not self.model:
            raise ValueError("model is required")

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            token = f"{self.auth_scheme} {self.api_key}".strip()
            headers[self.auth_header] = token
        headers.update(self.extra_headers)
        return headers

    def _build_payload(self, prompt: str) -> Dict[str, Any]:
        return {
            "model": self.model,
            "temperature": 0.1,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the slow cognition layer for a safety-critical mobile robot. "
                        "Return strict JSON with keys: decision, plan, explanation, recovery, memory_update. "
                        "Only choose decision from: avoid_obstacle, explore, navigate_careful, stop, null."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
        }

    @staticmethod
    def _extract_content(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                joined = []
                for part in content:
                    if isinstance(part, dict) and "text" in part:
                        joined.append(str(part["text"]))
                    elif isinstance(part, str):
                        joined.append(part)
                return "\n".join(joined)
            return str(content)

        text = payload.get("output_text")
        if text is not None:
            return str(text)

        return "{}"

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
            raise RuntimeError(f"LLM connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM response was not valid JSON") from exc

        content = self._extract_content(parsed).strip()
        if not content:
            return {}

        try:
            if content.startswith("{"):
                return json.loads(content)
        except json.JSONDecodeError:
            logger.warning("llm_non_json_content content=%s", content[:256])

        return {"explanation": content}


class UniversalHTTPAdapter(BaseLLMAdapter):
    """Generic adapter using user supplied request/response transformers.

    This allows plugging arbitrary vendor APIs while keeping control-loop code unchanged.
    """

    def __init__(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        payload_builder: Callable[[str, Dict[str, Any]], Dict[str, Any]],
        response_parser: Callable[[Dict[str, Any]], Dict[str, Any]],
        timeout_sec: float = 2.5,
    ):
        self.url = url
        self.method = method.upper()
        self.headers = dict(headers)
        self.payload_builder = payload_builder
        self.response_parser = response_parser
        self.timeout_sec = max(float(timeout_sec), 0.1)

    def generate(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.payload_builder(prompt, context)
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url=self.url,
            data=body,
            headers=self.headers,
            method=self.method,
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
                return self.response_parser(parsed) or {}
        except urllib.error.URLError as exc:
            raise RuntimeError(f"LLM connection failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("LLM response was not valid JSON") from exc


class SlowBrainCognition:
    """Non-blocking cognition manager.

    Fast brain remains deterministic; this layer is advisory and asynchronous.
    """

    def __init__(
        self,
        adapter: Optional[BaseLLMAdapter],
        enabled: bool = False,
        min_interval_sec: float = 1.5,
        directive_ttl_sec: float = 15.0,
        memory_size: int = 32,
    ):
        self.adapter = adapter
        self.enabled = bool(enabled and adapter is not None)
        self.min_interval_sec = max(float(min_interval_sec), 0.05)
        self.directive_ttl_sec = max(float(directive_ttl_sec), 0.1)
        self.last_request_ts = 0.0
        self.last_error: Optional[str] = None
        self.total_requests = 0
        self.total_failures = 0

        self._memory: Deque[str] = deque(maxlen=max(int(memory_size), 1))
        self._latest: Optional[CognitionDirective] = None
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=1)
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker: Optional[threading.Thread] = None

        if self.enabled:
            self._start_worker_locked()

    def _start_worker_locked(self) -> None:
        if self._worker and self._worker.is_alive():
            return
        self._stop_event.clear()
        self._worker = threading.Thread(target=self._worker_loop, name="SlowBrainCognition", daemon=True)
        self._worker.start()

    @classmethod
    def from_env(cls) -> "SlowBrainCognition":
        enabled = os.getenv("SPINN_COGNITION_ENABLED", "false").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if not enabled:
            return cls(adapter=None, enabled=False)

        adapter_name = os.getenv("SPINN_LLM_ADAPTER", "openai_compatible").strip().lower()
        timeout_sec = float(os.getenv("SPINN_LLM_TIMEOUT_SEC", "2.5"))
        min_interval_sec = float(os.getenv("SPINN_COGNITION_MIN_INTERVAL_SEC", "1.5"))
        directive_ttl_sec = float(os.getenv("SPINN_COGNITION_TTL_SEC", "15.0"))

        if adapter_name != "openai_compatible":
            logger.warning("unsupported_adapter adapter=%s", adapter_name)
            return cls(adapter=None, enabled=False)

        api_base = os.getenv("SPINN_LLM_API_BASE", "").strip()
        api_key = os.getenv("SPINN_LLM_API_KEY", "").strip()
        model = os.getenv("SPINN_LLM_MODEL", "").strip()
        endpoint = os.getenv("SPINN_LLM_API_ENDPOINT", "/chat/completions").strip()
        auth_header = os.getenv("SPINN_LLM_AUTH_HEADER", "Authorization").strip()
        auth_scheme = os.getenv("SPINN_LLM_AUTH_SCHEME", "Bearer").strip()
        extra_headers_raw = os.getenv("SPINN_LLM_EXTRA_HEADERS_JSON", "").strip()

        extra_headers: Dict[str, str] = {}
        if extra_headers_raw:
            try:
                decoded = json.loads(extra_headers_raw)
                if isinstance(decoded, dict):
                    extra_headers = {str(k): str(v) for k, v in decoded.items()}
            except json.JSONDecodeError:
                logger.warning("invalid_extra_headers_json")

        if not api_base or not model:
            logger.warning("cognition_disabled_missing_llm_config")
            return cls(adapter=None, enabled=False)

        adapter = OpenAICompatibleAdapter(
            api_base=api_base,
            api_key=api_key,
            model=model,
            endpoint=endpoint,
            timeout_sec=timeout_sec,
            auth_header=auth_header,
            auth_scheme=auth_scheme,
            extra_headers=extra_headers,
        )
        return cls(
            adapter=adapter,
            enabled=True,
            min_interval_sec=min_interval_sec,
            directive_ttl_sec=directive_ttl_sec,
        )

    def shutdown(self, timeout_sec: float = 1.0) -> None:
        self._stop_event.set()
        if self._worker and self._worker.is_alive():
            self._worker.join(timeout=timeout_sec)

    def get_config(self) -> Dict[str, Any]:
        with self._lock:
            adapter_name = type(self.adapter).__name__ if self.adapter is not None else None
            config = {
                "enabled": self.enabled,
                "min_interval_sec": self.min_interval_sec,
                "directive_ttl_sec": self.directive_ttl_sec,
                "adapter": adapter_name,
            }

            if isinstance(self.adapter, OpenAICompatibleAdapter):
                config.update(
                    {
                        "llm_api_base": self.adapter.api_base,
                        "llm_api_endpoint": self.adapter.endpoint,
                        "llm_model": self.adapter.model,
                        "llm_timeout_sec": self.adapter.timeout_sec,
                        "llm_auth_header": self.adapter.auth_header,
                        "llm_auth_scheme": self.adapter.auth_scheme,
                        "llm_has_api_key": bool(self.adapter.api_key),
                    }
                )

            return config

    def update_config(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(patch, dict):
            raise ValueError("patch must be a JSON object")

        with self._lock:
            enabled = patch.get("enabled", self.enabled)
            if isinstance(enabled, str):
                enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
            enabled = bool(enabled)

            if "min_interval_sec" in patch:
                self.min_interval_sec = max(float(patch["min_interval_sec"]), 0.05)

            if "directive_ttl_sec" in patch:
                self.directive_ttl_sec = max(float(patch["directive_ttl_sec"]), 0.1)

            wants_openai = any(
                key in patch
                for key in (
                    "llm_api_base",
                    "llm_api_endpoint",
                    "llm_model",
                    "llm_api_key",
                    "llm_timeout_sec",
                    "llm_auth_header",
                    "llm_auth_scheme",
                    "llm_extra_headers",
                )
            )

            if wants_openai:
                existing = self.adapter if isinstance(self.adapter, OpenAICompatibleAdapter) else None
                api_base = str(
                    patch.get("llm_api_base", getattr(existing, "api_base", ""))
                ).strip()
                endpoint = str(
                    patch.get("llm_api_endpoint", getattr(existing, "endpoint", "/chat/completions"))
                ).strip()
                model = str(
                    patch.get("llm_model", getattr(existing, "model", ""))
                ).strip()
                api_key = str(
                    patch.get("llm_api_key", getattr(existing, "api_key", ""))
                ).strip()
                timeout_sec = float(
                    patch.get("llm_timeout_sec", getattr(existing, "timeout_sec", 2.5))
                )
                auth_header = str(
                    patch.get("llm_auth_header", getattr(existing, "auth_header", "Authorization"))
                ).strip()
                auth_scheme = str(
                    patch.get("llm_auth_scheme", getattr(existing, "auth_scheme", "Bearer"))
                ).strip()

                extra_headers = patch.get("llm_extra_headers", getattr(existing, "extra_headers", {}))
                if isinstance(extra_headers, str):
                    try:
                        extra_headers = json.loads(extra_headers)
                    except json.JSONDecodeError as exc:
                        raise ValueError("llm_extra_headers must be a JSON object") from exc
                if not isinstance(extra_headers, dict):
                    raise ValueError("llm_extra_headers must be an object")

                if not api_base or not model:
                    raise ValueError("llm_api_base and llm_model are required for OpenAI-compatible adapter")

                self.adapter = OpenAICompatibleAdapter(
                    api_base=api_base,
                    api_key=api_key,
                    model=model,
                    endpoint=endpoint,
                    timeout_sec=timeout_sec,
                    auth_header=auth_header,
                    auth_scheme=auth_scheme,
                    extra_headers={str(k): str(v) for k, v in extra_headers.items()},
                )

            self.enabled = enabled and (self.adapter is not None)

            if self.enabled:
                self._start_worker_locked()
            else:
                self._stop_event.set()

        return self.get_config()

    def status(self) -> Dict[str, Any]:
        with self._lock:
            latest = self._latest.to_dict() if self._latest else None
            memory_tail = list(self._memory)[-5:]
            return {
                "enabled": self.enabled,
                "requests": self.total_requests,
                "failures": self.total_failures,
                "last_error": self.last_error,
                "latest_directive": latest,
                "memory_tail": memory_tail,
            }

    def submit(self, context: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        now = time.time()
        if (now - self.last_request_ts) < self.min_interval_sec:
            return

        if self._queue.full():
            return

        self.last_request_ts = now
        try:
            self._queue.put_nowait(dict(context))
        except queue.Full:
            return

    def latest_directive(self) -> Optional[CognitionDirective]:
        with self._lock:
            if self._latest is None:
                return None
            age = time.time() - self._latest.timestamp
            if age > self.directive_ttl_sec:
                return None
            return self._latest

    @staticmethod
    def _normalize_response(payload: Dict[str, Any]) -> CognitionDirective:
        decision = payload.get("decision")
        if decision is not None:
            decision = str(decision).strip().lower() or None
            if decision == "null":
                decision = None

        return CognitionDirective(
            decision=decision,
            plan=str(payload.get("plan", "")).strip(),
            explanation=str(payload.get("explanation", "")).strip(),
            recovery=str(payload.get("recovery", "")).strip(),
            memory_update=str(payload.get("memory_update", "")).strip(),
            timestamp=time.time(),
        )

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        summary = {
            "fast_brain_decision": context.get("fast_brain_decision"),
            "threat_level": context.get("threat_level"),
            "sensor_front_left_right": context.get("sensors"),
            "loop_health": context.get("loop_health"),
            "recent_actions": context.get("recent_actions"),
            "memory": list(self._memory)[-8:],
        }
        return (
            "Given the robot context, return JSON with keys: decision, plan, explanation, recovery, memory_update.\n"
            "Rules: never reduce safety. If threat_level >= 0.8 return decision stop or avoid_obstacle.\n"
            f"Context: {json.dumps(summary, separators=(',', ':'))}"
        )

    def _worker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                context = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            try:
                if self.adapter is None:
                    continue

                prompt = self._build_prompt(context)
                payload = self.adapter.generate(prompt=prompt, context=context) or {}
                directive = self._normalize_response(payload)

                with self._lock:
                    self.total_requests += 1
                    self.last_error = None
                    self._latest = directive
                    if directive.memory_update:
                        self._memory.append(directive.memory_update)

            except Exception as exc:
                with self._lock:
                    self.total_requests += 1
                    self.total_failures += 1
                    self.last_error = str(exc)
                logger.warning("slow_brain_failure error=%s", exc)
