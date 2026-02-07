import socket
from urllib import error

from llm.anthropic_provider import _classify_url_error, _is_retryable_network_reason


def test_classify_url_error_dns():
    exc = error.URLError(socket.gaierror(8, "nodename nor servname provided, or not known"))
    assert _classify_url_error(exc) == "llm_dns_error"


def test_classify_url_error_timeout():
    exc = error.URLError(socket.timeout("timed out"))
    assert _classify_url_error(exc) == "llm_timeout"


def test_classify_url_error_connection_refused():
    exc = error.URLError(ConnectionRefusedError("connection refused"))
    assert _classify_url_error(exc) == "llm_connection_refused"


def test_retryable_network_reasons():
    assert _is_retryable_network_reason("llm_dns_error") is True
    assert _is_retryable_network_reason("llm_timeout") is True
    assert _is_retryable_network_reason("llm_network_error") is True
    assert _is_retryable_network_reason("llm_ssl_error") is False
