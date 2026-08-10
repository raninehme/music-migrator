from unittest.mock import Mock

import pytest
import requests

from music_migrator.core.retry import retry_request


def http_error(status: int, retry_after: str | None = None) -> requests.HTTPError:
    response = requests.Response()
    response.status_code = status
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return requests.HTTPError(response=response)


def test_retries_rate_limits_using_retry_after():
    operation = Mock(side_effect=[http_error(429, "2"), "ok"])
    sleep = Mock()

    result = retry_request(operation, sleep=sleep)

    assert result == "ok"
    sleep.assert_called_once_with(2.0)


def test_retries_transient_server_errors_with_backoff():
    operation = Mock(side_effect=[http_error(503), http_error(503), "ok"])
    sleep = Mock()

    result = retry_request(operation, base_delay=0.25, sleep=sleep)

    assert result == "ok"
    assert [call.args[0] for call in sleep.call_args_list] == [0.25, 0.5]


def test_retries_connection_failures():
    operation = Mock(side_effect=[requests.Timeout(), "ok"])
    sleep = Mock()

    assert retry_request(operation, sleep=sleep) == "ok"
    assert operation.call_count == 2


def test_does_not_retry_non_transient_errors():
    operation = Mock(side_effect=ValueError("invalid"))
    sleep = Mock()

    with pytest.raises(ValueError, match="invalid"):
        retry_request(operation, sleep=sleep)

    operation.assert_called_once_with()
    sleep.assert_not_called()


def test_stops_after_the_attempt_limit():
    operation = Mock(side_effect=http_error(500))

    with pytest.raises(requests.HTTPError):
        retry_request(operation, attempts=3, sleep=Mock())

    assert operation.call_count == 3
