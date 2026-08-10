import logging
import time
from collections.abc import Callable
from typing import TypeVar

import requests

T = TypeVar("T")

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def retry_request(
    operation: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Retry transient API failures with bounded exponential backoff."""
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as error:
            if attempt == attempts - 1 or not _is_retryable(error):
                raise
            delay = _retry_after(error)
            if delay is None:
                delay = base_delay * (2**attempt)
            logger.warning(
                "Temporary API failure (%s); retrying in %.1f seconds",
                error,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (requests.ConnectionError, requests.Timeout)):
        return True
    return _status_code(error) in RETRYABLE_STATUS_CODES


def _status_code(error: Exception) -> int | None:
    status = getattr(error, "http_status", None)
    if status is not None:
        return int(status)
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return int(status) if status is not None else None


def _retry_after(error: Exception) -> float | None:
    headers = getattr(error, "headers", None)
    if headers is None:
        response = getattr(error, "response", None)
        headers = getattr(response, "headers", None)
    if not headers:
        return None
    value = headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None
