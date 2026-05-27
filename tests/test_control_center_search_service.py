import json
import ssl
from pathlib import Path

from local_ai_control_center_installer.control_center_backend.services.search_service import (
    perform_search_query,
    prepare_proxy_chat_completion_body,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeRawResponse:
    def __init__(self, body: str):
        self._body = body

    def read(self) -> bytes:
        return self._body.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _write_settings(install_root: Path, payload: dict[str, object]) -> None:
    settings_path = install_root / "config" / "control-center" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_perform_search_query_normalizes_searxng_payload(tmp_path: Path, monkeypatch):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 3,
            "webSearchTimeoutSeconds": 9,
            "webSearchPromptPrefix": "/web",
        },
    )

    def fake_opener(request, timeout):
        assert "format=json" in request.full_url
        assert "q=kv+cache" in request.full_url
        assert timeout == 9
        return _FakeResponse(
            {
                "query": "kv cache",
                "results": [
                    {
                        "title": "KV cache compression",
                        "url": "https://example.invalid/kv",
                        "content": "Compression reduces memory pressure.",
                        "engine": "demo",
                    },
                    {
                        "title": "llama.cpp docs",
                        "url": "https://example.invalid/llama",
                        "content": "llama.cpp supports OpenAI-compatible chat.",
                        "engine": "demo",
                    },
                ],
            }
        )

    payload = perform_search_query("kv cache", opener=fake_opener)

    assert payload["status"] == "ok"
    assert payload["provider"] == "searxng"
    assert payload["query"] == "kv cache"
    assert payload["resultCount"] == 2
    assert payload["results"][0]["title"] == "KV cache compression"
    assert payload["results"][0]["url"] == "https://example.invalid/kv"
    assert payload["results"][0]["snippet"] == "Compression reduces memory pressure."


def test_perform_search_query_accepts_base_url_that_already_points_to_search_endpoint(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080/search",
            "webSearchMaxResults": 2,
            "webSearchTimeoutSeconds": 6,
            "webSearchPromptPrefix": "/web",
        },
    )

    def fake_opener(request, timeout):
        assert request.full_url.startswith("http://127.0.0.1:18080/search?")
        assert "/search/search?" not in request.full_url
        assert "q=kv+cache" in request.full_url
        assert timeout == 6
        return _FakeResponse(
            {
                "results": [
                    {
                        "title": "Search endpoint works",
                        "url": "https://example.invalid/search-endpoint",
                        "content": "SearxNG search endpoint accepted the request.",
                        "engine": "demo",
                    }
                ]
            }
        )

    payload = perform_search_query("kv cache", opener=fake_opener)

    assert payload["status"] == "ok"
    assert payload["resultCount"] == 1
    assert payload["results"][0]["title"] == "Search endpoint works"


def test_perform_search_query_reports_clear_error_for_html_response(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 3,
            "webSearchTimeoutSeconds": 9,
            "webSearchPromptPrefix": "/web",
        },
    )

    payload = perform_search_query(
        "kv cache",
        opener=lambda request, timeout: _FakeRawResponse("<html><body>SearxNG landing page</body></html>"),
    )

    assert payload["status"] == "error"
    assert "nije vratio JSON" in payload["summary"]
    assert "/search" in payload["summary"]


def test_perform_search_query_supports_duckduckgo_html_results(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "duckduckgo",
            "webSearchBaseUrl": "",
            "webSearchMaxResults": 2,
            "webSearchTimeoutSeconds": 11,
            "webSearchPromptPrefix": "/web",
        },
    )

    html = """
    <html>
      <body>
        <div class="result results_links results_links_deep web-result">
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.invalid%2Fone">First result</a>
          <a class="result__snippet">First snippet</a>
        </div>
        <div class="result results_links results_links_deep web-result">
          <a class="result__a" href="https://example.invalid/two">Second result</a>
          <div class="result__snippet">Second snippet</div>
        </div>
      </body>
    </html>
    """

    def fake_opener(request, timeout):
        assert "duckduckgo.com" in request.full_url
        assert "q=kv+cache" in request.full_url
        assert timeout == 11
        return _FakeRawResponse(html)

    payload = perform_search_query("kv cache", opener=fake_opener)

    assert payload["status"] == "ok"
    assert payload["provider"] == "duckduckgo"
    assert payload["resultCount"] == 2
    assert payload["results"][0]["title"] == "First result"
    assert payload["results"][0]["url"] == "https://example.invalid/one"
    assert payload["results"][0]["snippet"] == "First snippet"
    assert payload["results"][0]["engine"] == "duckduckgo"
    assert payload["summary"] == "Pronađeno je 2 veb rezultata preko DuckDuckGo."


def test_perform_search_query_duckduckgo_uses_ssl_context_when_opener_supports_it(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "duckduckgo",
            "webSearchBaseUrl": "",
            "webSearchMaxResults": 1,
            "webSearchTimeoutSeconds": 11,
            "webSearchPromptPrefix": "/web",
        },
    )

    seen: dict[str, object] = {}

    def fake_opener(request, timeout, context=None):
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["context"] = context
        return _FakeRawResponse(
            """
            <html>
              <body>
                <div class="result results_links results_links_deep web-result">
                  <a class="result__a" href="https://example.invalid/secure">Secure result</a>
                  <div class="result__snippet">Secure snippet</div>
                </div>
              </body>
            </html>
            """
        )

    payload = perform_search_query("secure query", opener=fake_opener)

    assert payload["status"] == "ok"
    assert "duckduckgo.com" in str(seen["url"])
    assert seen["timeout"] == 11
    assert isinstance(seen["context"], ssl.SSLContext)


def test_perform_search_query_duckduckgo_retries_with_relaxed_tls_on_cert_failure(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "duckduckgo",
            "webSearchBaseUrl": "",
            "webSearchMaxResults": 1,
            "webSearchTimeoutSeconds": 11,
            "webSearchPromptPrefix": "/web",
        },
    )

    calls: list[ssl.SSLContext | None] = []

    def fake_opener(request, timeout, context=None):
        calls.append(context)
        if len(calls) == 1:
            raise ssl.SSLCertVerificationError("verify failed")
        return _FakeRawResponse(
            """
            <html>
              <body>
                <div class="result results_links results_links_deep web-result">
                  <a class="result__a" href="https://example.invalid/fallback">Fallback result</a>
                  <div class="result__snippet">Fallback snippet</div>
                </div>
              </body>
            </html>
            """
        )

    payload = perform_search_query("fallback query", opener=fake_opener)

    assert payload["status"] == "ok"
    assert payload["resultCount"] == 1
    assert payload["results"][0]["title"] == "Fallback result"
    assert len(calls) == 2
    assert isinstance(calls[0], ssl.SSLContext)
    assert isinstance(calls[1], ssl.SSLContext)
    assert calls[1].check_hostname is False


def test_perform_search_query_supports_provider_override(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "always",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 2,
            "webSearchTimeoutSeconds": 9,
            "webSearchPromptPrefix": "/web",
        },
    )

    payload = perform_search_query(
        "kv cache",
        provider_override="duckduckgo",
        opener=lambda request, timeout: _FakeRawResponse(
            """
            <html>
              <body>
                <div class="result results_links results_links_deep web-result">
                  <a class="result__a" href="https://example.invalid/override">Override result</a>
                  <div class="result__snippet">Override snippet</div>
                </div>
              </body>
            </html>
            """
        ),
    )

    assert payload["status"] == "ok"
    assert payload["provider"] == "duckduckgo"
    assert payload["results"][0]["title"] == "Override result"


def test_prepare_proxy_chat_completion_body_skips_search_when_mode_is_off(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "off",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 5,
            "webSearchTimeoutSeconds": 20,
            "webSearchPromptPrefix": "/web",
        },
    )

    payload = {
        "model": "local-lacc/demo.gguf",
        "messages": [{"role": "user", "content": "zdravo"}],
        "stream": False,
    }

    next_payload, meta = prepare_proxy_chat_completion_body(
        payload,
        search_func=lambda query: (_ for _ in ()).throw(RuntimeError("search should not run")),
    )

    assert next_payload == payload
    assert meta["usedSearch"] is False
    assert meta["mode"] == "off"
    assert meta["query"] == ""


def test_prepare_proxy_chat_completion_body_uses_prefix_in_on_demand_mode(
    tmp_path: Path,
    monkeypatch,
):
    install_root = tmp_path / "install-root"
    monkeypatch.setenv("LACC_INSTALL_ROOT", str(install_root))
    _write_settings(
        install_root,
        {
            "webSearchMode": "on-demand",
            "webSearchProvider": "searxng",
            "webSearchBaseUrl": "http://127.0.0.1:18080",
            "webSearchMaxResults": 4,
            "webSearchTimeoutSeconds": 7,
            "webSearchPromptPrefix": "/web",
        },
    )

    payload = {
        "model": "local-lacc/demo.gguf",
        "messages": [{"role": "user", "content": "/web najnovije informacije o searxng"}],
        "stream": False,
    }

    next_payload, meta = prepare_proxy_chat_completion_body(
        payload,
        search_func=lambda query: {
            "status": "ok",
            "provider": "searxng",
            "query": query,
            "resultCount": 1,
            "results": [
                {
                    "title": "SearxNG docs",
                    "url": "https://docs.example.invalid/searxng",
                    "snippet": "SearxNG is a metasearch engine.",
                    "engine": "demo",
                }
            ],
            "summary": "Pronađen je 1 rezultat.",
        },
    )

    assert meta["usedSearch"] is True
    assert meta["mode"] == "on-demand"
    assert meta["query"] == "najnovije informacije o searxng"
    assert next_payload["messages"][0]["role"] == "system"
    assert "SearxNG docs" in str(next_payload["messages"][0]["content"])
    assert next_payload["messages"][-1]["content"] == "najnovije informacije o searxng"
