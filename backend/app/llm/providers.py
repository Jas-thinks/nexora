"""LLM providers. Gemini, Groq, OpenRouter and Ollama all expose OpenAI-compatible /chat/completions, so one client covers them.
Free-tier availability and limits change; models are configurable (CODEMIND_*_MODEL) and nothing here assumes a particular quota."""
import json
import time
from dataclasses import dataclass

import httpx

from app.core.config import Settings


class LLMError(Exception):
    def __init__(self, msg: str, retryable: bool = True):
        super().__init__(msg)
        self.retryable = retryable


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    latency_ms: int


class Provider:
    name = ""
    model = ""

    def available(self) -> bool: return False
    def chat(self, messages: list[dict], max_tokens: int, timeout: float, temperature: float = 0.3) -> LLMResult: raise NotImplementedError
    def stream(self, messages: list[dict], max_tokens: int, timeout: float, temperature: float = 0.3):
        """Default: no native streaming -> one chunk. Providers override."""
        yield self.chat(messages, max_tokens, timeout, temperature).text


class OpenAICompat(Provider):
    def __init__(self, name: str, base_url: str, key: str, model: str, needs_key: bool = True, transport: httpx.BaseTransport | None = None):
        self.name, self.base, self.key, self.model, self.needs_key, self.transport = name, base_url.rstrip("/"), key, model, needs_key, transport

    embed_model: str | None = None

    def can_embed(self) -> bool:
        if not self.embed_model or not self.available():
            return False
        return self.needs_key or any(self.embed_model.split(":")[0] in (m or "") for m in self._models)

    def embed(self, texts: list[str], timeout: float = 60.0) -> list[list[float]]:
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as c:
                r = c.post(f"{self.base}/embeddings", json={"model": self.embed_model, "input": texts}, headers=headers)
        except httpx.HTTPError as e:
            raise LLMError(f"{self.name}: embed network error {type(e).__name__}") from e
        if r.status_code >= 400:
            raise LLMError(f"{self.name}: embed HTTP {r.status_code}", retryable=r.status_code >= 429)
        try:
            return [d["embedding"] for d in sorted(r.json()["data"], key=lambda x: x["index"])]
        except (KeyError, ValueError) as e:
            raise LLMError(f"{self.name}: malformed embeddings response") from e

    _probe: tuple[float, bool] | None = None
    _models: list = []
    local_timeout = 180.0  # local CPU inference is slow; applies to keyless (local) providers only

    def available(self) -> bool:
        if self.needs_key:
            return bool(self.key)
        # Keyless providers (local Ollama) are only "available" if something is actually listening. Probe /models, cached for 30 s.
        now = time.monotonic()
        if self._probe and now - self._probe[0] < 30:
            return self._probe[1]
        try:
            with httpx.Client(timeout=1.5, transport=self.transport) as c:
                r = c.get(f"{self.base}/models")
            ok = r.status_code == 200
            self._models = [m.get("id") for m in (r.json().get("data") or [])] if ok else []
        except (httpx.HTTPError, ValueError):
            ok, self._models = False, []
        self._probe = (now, ok)
        return ok

    def chat(self, messages, max_tokens, timeout, temperature=0.3) -> LLMResult:
        t0 = time.perf_counter()
        headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
        model = self.model
        if not self.needs_key:  # local server: use the configured model if installed, otherwise whatever is installed
            timeout = max(timeout, self.local_timeout)
            chat_models = [m for m in self._models if "embed" not in (m or "").lower()]  # an installed embedding model must never be used for chat
            if chat_models and model not in self._models:
                model = chat_models[0]
        body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature}
        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as c:
                r = c.post(f"{self.base}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LLMError(f"{self.name}: network error {type(e).__name__}") from e
        if r.status_code in (429, 500, 502, 503, 504):
            raise LLMError(f"{self.name}: HTTP {r.status_code}", retryable=True)
        if r.status_code >= 400:
            raise LLMError(f"{self.name}: HTTP {r.status_code}", retryable=False)
        try:
            d = r.json()
            text = d["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, ValueError) as e:
            raise LLMError(f"{self.name}: malformed response") from e
        u = d.get("usage") or {}
        return LLMResult(text, self.name, model, u.get("prompt_tokens"), u.get("completion_tokens"), int((time.perf_counter() - t0) * 1000))


def _openai_stream(self, messages, max_tokens, timeout, temperature=0.3):
    """Yield text deltas from an OpenAI-compatible SSE stream."""
    headers = {"Authorization": f"Bearer {self.key}"} if self.key else {}
    model = self.model
    if not self.needs_key:
        timeout = max(timeout, self.local_timeout)
        chat_models = [m for m in self._models if "embed" not in (m or "").lower()]
        if chat_models and model not in self._models:
            model = chat_models[0]
    self.last_model = model  # the model actually used (may differ from the configured one for local servers)
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, "stream": True}
    try:
        with httpx.Client(timeout=timeout, transport=self.transport) as c:
            with c.stream("POST", f"{self.base}/chat/completions", json=body, headers=headers) as r:
                if r.status_code >= 400:
                    raise LLMError(f"{self.name}: HTTP {r.status_code}", retryable=r.status_code in (429, 500, 502, 503, 504))
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        return
                    try:
                        delta = json.loads(data)["choices"][0].get("delta", {}).get("content") or ""
                    except (ValueError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta
    except httpx.HTTPError as e:
        raise LLMError(f"{self.name}: network error {type(e).__name__}") from e


OpenAICompat.stream = _openai_stream


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, key: str, model: str, transport: httpx.BaseTransport | None = None):
        self.key, self.model, self.transport = key, model, transport

    def available(self) -> bool: return bool(self.key)

    def chat(self, messages, max_tokens, timeout, temperature=0.3) -> LLMResult:
        t0 = time.perf_counter()
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        msgs = [m for m in messages if m["role"] != "system"]
        try:
            with httpx.Client(timeout=timeout, transport=self.transport) as c:
                r = c.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                           json={"model": self.model, "max_tokens": max_tokens, "system": system, "messages": msgs, "temperature": temperature})
        except httpx.HTTPError as e:
            raise LLMError(f"anthropic: network error {type(e).__name__}") from e
        if r.status_code >= 400:
            raise LLMError(f"anthropic: HTTP {r.status_code}", retryable=r.status_code in (429, 500, 502, 503, 529))
        d = r.json()
        text = "".join(b.get("text", "") for b in d.get("content", []))
        u = d.get("usage") or {}
        return LLMResult(text, "anthropic", self.model, u.get("input_tokens"), u.get("output_tokens"), int((time.perf_counter() - t0) * 1000))


def build_providers(s: Settings) -> dict[str, Provider]:
    ps = {
        "gemini": OpenAICompat("gemini", "https://generativelanguage.googleapis.com/v1beta/openai", s.gemini_api_key, s.gemini_model),
        "groq": OpenAICompat("groq", "https://api.groq.com/openai/v1", s.groq_api_key, s.groq_model),
        "openrouter": OpenAICompat("openrouter", "https://openrouter.ai/api/v1", s.openrouter_api_key, s.openrouter_model),
        "ollama": OpenAICompat("ollama", s.ollama_base_url, "", s.ollama_model, needs_key=False),
        "anthropic": AnthropicProvider(s.anthropic_api_key, s.anthropic_model),
    }
    ps["gemini"].embed_model = s.gemini_embed_model
    ps["ollama"].embed_model = s.ollama_embed_model
    return ps
