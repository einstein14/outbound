import base64
import os

import pytest

from app.config import load_google_pollen_api_key


@pytest.fixture
def clean_pollen_env(monkeypatch):
    monkeypatch.delenv("GOOGLE_POLLEN_API_KEY_B64", raising=False)
    monkeypatch.delenv("GOOGLE_POLLEN_API_KEY", raising=False)


def test_load_google_pollen_api_key_from_b64(clean_pollen_env, monkeypatch):
    key = "test-google-key-123"
    monkeypatch.setenv(
        "GOOGLE_POLLEN_API_KEY_B64",
        base64.b64encode(key.encode()).decode(),
    )
    assert load_google_pollen_api_key() == key


def test_load_google_pollen_api_key_plain_fallback(clean_pollen_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "plain-key")
    assert load_google_pollen_api_key() == "plain-key"


def test_invalid_b64_falls_back_to_plain(clean_pollen_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY_B64", "not-valid-base64!!!")
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY", "plain-key")
    assert load_google_pollen_api_key() == "plain-key"


def test_invalid_b64_without_plain_returns_none(clean_pollen_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_POLLEN_API_KEY_B64", "not-valid-base64!!!")
    assert load_google_pollen_api_key() is None
