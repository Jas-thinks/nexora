"""Polite HTTP: per-host rate limiting, retry with backoff, Retry-After, descriptive User-Agent, timeouts."""
import time
from urllib.parse import urlparse

import httpx

UA = "NexoraCPMentor/0.1 (+educational; contact via repository)"


class FetchError(Exception):
    def __init__(self, msg: str, status: int | None = None, retryable: bool = False):
        super().__init__(msg)
        self.status, self.retryable = status, retryable


class PoliteClient:
    def __init__(self, min_interval: float = 1.0, retries: int = 3, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, timeout: float = 30.0):
        self.min_interval, self.retries, self.sleep = min_interval, retries, sleep
        self.last: dict[str, float] = {}
        self.client = httpx.Client(headers={"User-Agent": UA}, timeout=timeout, transport=transport, follow_redirects=True)

    def _wait(self, host: str) -> None:
        gap = self.min_interval - (time.monotonic() - self.last.get(host, 0.0))
        if gap > 0:
            self.sleep(gap)
        self.last[host] = time.monotonic()

    def get_json(self, url: str, params: dict | None = None, headers: dict | None = None):
        host = urlparse(url).netloc
        for attempt in range(self.retries + 1):
            self._wait(host)
            try:
                r = self.client.get(url, params=params, headers=headers)
            except httpx.TransportError as e:
                if attempt == self.retries:
                    raise FetchError(f"network error: {e}", retryable=True) from e
                self.sleep(2 ** attempt); continue
            if r.status_code == 200:
                try:
                    return r.json()
                except ValueError as e:
                    raise FetchError("response was not valid JSON") from e
            if r.status_code in (429, 500, 502, 503, 504):
                if attempt == self.retries:
                    raise FetchError(f"HTTP {r.status_code} after retries", r.status_code, retryable=True)
                ra = r.headers.get("Retry-After")
                self.sleep(min(float(ra), 60) if ra and ra.isdigit() else 2 ** attempt)
                continue
            # Codeforces returns 400 + JSON {"status":"FAILED","comment":...} for e.g. unknown handle
            comment = ""
            try: comment = r.json().get("comment", "")
            except Exception: pass
            raise FetchError(f"HTTP {r.status_code}: {comment}".strip(": "), r.status_code)
        raise FetchError("unreachable")
