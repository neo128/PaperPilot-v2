from __future__ import annotations

import time
from typing import Any, Optional

import requests


def create_session(headers: dict | None = None, use_env_proxy: bool = True) -> requests.Session:
    session = requests.Session()
    session.trust_env = use_env_proxy
    if not use_env_proxy:
        session.proxies = {}
    if headers:
        session.headers.update(headers)
    return session


def request_with_retry(
    session: requests.Session,
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff: float = 1.0,
    timeout: int = 30,
    **kwargs: Any,
) -> requests.Response:
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = session.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code == 429 and attempt < retries - 1:
                time.sleep(backoff * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_exc = exc
            if attempt == retries - 1:
                raise
            time.sleep(backoff * (attempt + 1))
    assert last_exc is not None
    raise last_exc
