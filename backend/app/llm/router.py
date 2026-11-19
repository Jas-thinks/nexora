"""Provider chain with timeouts, fallback on retryable failure, and per-call usage logging. Never raises for 'no provider': returns None."""
import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.llm.providers import LLMError, LLMResult, Provider, build_providers
from app.models.ai import LLMCall

log = logging.getLogger("nexora.llm")


def _metric(provider, ok, pt=None, ct=None):
    try:
        from app.core.observability import LLM_CALLS, LLM_TOK
        LLM_CALLS.labels(provider, str(ok)).inc()
        if pt: LLM_TOK.labels(provider, "prompt").inc(pt)
        if ct: LLM_TOK.labels(provider, "completion").inc(ct)
    except Exception:  # noqa: BLE001 - metrics must never break a request
        pass


class Router:
    def __init__(self, providers: dict[str, Provider] | None = None, chain: list[str] | None = None):
        s = get_settings()
        self.providers = providers if providers is not None else build_providers(s)
        self.chain = chain if chain is not None else list(s.llm_chain)
        self.timeout, self.max_tokens = s.llm_timeout_seconds, s.llm_max_output_tokens

    def active(self) -> list[str]:
        return [n for n in self.chain if n in self.providers and self.providers[n].available()]

    def status(self) -> dict:
        return {"configured": self.active(), "chain": self.chain,
                "providers": {n: {"model": p.model, "ready": p.available()} for n, p in self.providers.items()}}

    def chat(self, db: Session | None, user_id: int | None, messages: list[dict], purpose: str = "mentor", max_tokens: int | None = None) -> LLMResult | None:
        errors = []
        for name in self.active():
            p = self.providers[name]
            try:
                res = p.chat(messages, max_tokens or self.max_tokens, self.timeout)
            except LLMError as e:
                errors.append(str(e)); log.warning("llm provider failed: %s", e); _metric(name, False)
                if db is not None:
                    db.add(LLMCall(user_id=user_id, provider=name, model=p.model, purpose=purpose, ok=False, error=str(e)[:290])); db.commit()
                continue
            _metric(res.provider, True, res.prompt_tokens, res.completion_tokens)
            if db is not None:
                db.add(LLMCall(user_id=user_id, provider=res.provider, model=res.model, purpose=purpose, prompt_tokens=res.prompt_tokens,
                               completion_tokens=res.completion_tokens, latency_ms=res.latency_ms, ok=True)); db.commit()
            return res
        return None

    def stream(self, db: Session | None, user_id: int | None, messages: list[dict], purpose: str = "mentor", max_tokens: int | None = None):
        """Yield (provider, model, delta). Falls back to the next provider only if one fails BEFORE producing a token."""
        import time
        for name in self.active():
            p = self.providers[name]
            got, t0 = False, time.perf_counter()
            try:
                for delta in p.stream(messages, max_tokens or self.max_tokens, self.timeout):
                    got = True
                    yield name, getattr(p, 'last_model', None) or p.model, delta
            except LLMError as e:
                if db is not None:
                    db.add(LLMCall(user_id=user_id, provider=name, model=p.model, purpose=purpose, ok=False, error=str(e)[:290])); db.commit()
                if got:
                    return  # cannot restart mid-answer; the caller finalises what it has
                continue
            if db is not None:
                db.add(LLMCall(user_id=user_id, provider=name, model=p.model, purpose=purpose, latency_ms=int((time.perf_counter() - t0) * 1000), ok=True)); db.commit()
            return

    def embed(self, texts: list[str]) -> tuple[list[list[float]], str] | None:
        """-> (vectors, 'provider:model') from the first provider that can embed, or None (callers fall back to keyword search)."""
        for name in self.chain:
            p = self.providers.get(name)
            if p is not None and hasattr(p, "can_embed") and p.can_embed():
                try:
                    return p.embed(texts), f"{name}:{p.embed_model}"
                except LLMError as e:
                    log.warning("embedding failed: %s", e)
        return None
