"""Edge case tests for the FARE backend API."""

import io
from unittest.mock import patch, MagicMock

from starlette.testclient import TestClient
from app import app


def _make_client():
    return TestClient(app, raise_server_exceptions=False)


def _mock_empty_stats():
    return {"total_chunks": 0, "total_documents": 0, "documents": []}


def test_health_endpoint():
    client = _make_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_empty_query_returns_400():
    client = _make_client()
    resp = client.post("/api/query", json={
        "query": "",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_whitespace_only_query_returns_400():
    client = _make_client()
    resp = client.post("/api/query", json={
        "query": "   ",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


def test_long_query_returns_400():
    client = _make_client()
    long_query = "a" * 501
    resp = client.post("/api/query", json={
        "query": long_query,
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"].lower()


@patch("vector_store.get_stats", return_value=_mock_empty_stats())
def test_no_documents_query_returns_400(mock_stats):
    client = _make_client()
    resp = client.post("/api/query", json={
        "query": "What is machine learning?",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "no documents" in resp.json()["detail"].lower()


@patch("vector_store.get_stats", return_value=_mock_empty_stats())
def test_xss_query_no_crash(mock_stats):
    client = _make_client()
    resp = client.post("/api/query", json={
        "query": "<script>alert('xss')</script>",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "no documents" in resp.json()["detail"].lower()


@patch("vector_store.get_stats", return_value=_mock_empty_stats())
def test_unicode_query_no_crash(mock_stats):
    client = _make_client()
    resp = client.post("/api/query", json={
        "query": "機械学習とは何ですか？",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "no documents" in resp.json()["detail"].lower()


def test_upload_non_pdf_returns_400():
    client = _make_client()
    resp = client.post(
        "/api/ingest",
        files={"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "pdf" in resp.json()["detail"].lower()


@patch("vector_store.get_stats", return_value=_mock_empty_stats())
def test_stream_empty_query_returns_400(mock_stats):
    client = _make_client()
    resp = client.post("/api/query/stream", json={
        "query": "",
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@patch("vector_store.get_stats", return_value=_mock_empty_stats())
def test_stream_long_query_returns_400(mock_stats):
    client = _make_client()
    resp = client.post("/api/query/stream", json={
        "query": "b" * 501,
        "k": 5,
        "method": "hybrid",
    })
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"].lower()
