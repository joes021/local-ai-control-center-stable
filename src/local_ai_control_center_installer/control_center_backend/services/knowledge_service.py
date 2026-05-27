from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha1
import html
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from local_ai_control_center_installer.control_center_backend.config import (
    ControlCenterConfig,
    get_config,
)
from local_ai_control_center_installer.control_center_backend.services.search_service import (
    perform_search_query,
)
from local_ai_control_center_installer.control_center_backend.services.server_service import (
    ensure_runtime_ready,
)
from local_ai_control_center_installer.control_center_backend.services.settings_service import (
    load_effective_settings_state,
)
from local_ai_control_center_installer.control_center_backend.services.state_helpers import (
    atomic_write_json,
    read_json_object,
)
from local_ai_control_center_installer.control_center_backend.services.status_service import (
    load_runtime_state,
)

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional at import time, enforced in package deps
    PdfReader = None


SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".csv",
    ".html",
    ".htm",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".log",
    ".docx",
    ".pdf",
}
ANSWER_MODES = {"documents-only", "documents+web", "web-only"}
HISTORY_LIMIT = 20
DEFAULT_QUERY_LIMIT = 6
MAX_INDEX_FILE_SIZE_BYTES = 15 * 1024 * 1024
LOCAL_MODEL_ANSWER_TIMEOUT_SECONDS = 180.0
MAX_SNIPPET_LENGTH = 360


@dataclass(frozen=True)
class IndexedDocument:
    doc_id: str
    source_id: str
    path: str
    name: str
    file_type: str
    size_bytes: int
    modified_ns: int
    char_count: int
    content: str


def load_knowledge_summary(
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    sources = _load_sources(config)
    stats = _load_index_stats(config)
    per_source = stats["perSource"]
    summary_sources: list[dict[str, Any]] = []
    collections: set[str] = set()
    tags: set[str] = set()
    document_count = 0
    indexed_document_count = 0
    error_count = 0
    last_reindex_at = ""
    for source in sources:
        source_id = str(source.get("id", "") or "")
        source_stats = per_source.get(source_id, {})
        doc_count = int(source_stats.get("documentCount", int(source.get("documentCount", 0) or 0)) or 0)
        indexed_count = int(
            source_stats.get("indexedDocumentCount", int(source.get("indexedDocumentCount", 0) or 0)) or 0
        )
        source_errors = int(source.get("errorCount", 0) or 0)
        collection = str(source.get("collection", "") or "").strip()
        source_tags = _normalize_tags(source.get("tags", []))
        document_count += doc_count
        indexed_document_count += indexed_count
        error_count += source_errors
        normalized_path = str(source.get("path", "") or "")
        last_indexed_at = str(source.get("lastIndexedAt", "") or "")
        if last_indexed_at and last_indexed_at > last_reindex_at:
            last_reindex_at = last_indexed_at
        if collection:
            collections.add(collection)
        tags.update(source_tags)
        summary_sources.append(
            {
                "id": source_id,
                "path": normalized_path,
                "kind": str(source.get("kind", "") or _detect_source_kind(Path(normalized_path))),
                "exists": Path(normalized_path).exists() if normalized_path else False,
                "collection": collection,
                "tags": source_tags,
                "documentCount": doc_count,
                "indexedDocumentCount": indexed_count,
                "errorCount": source_errors,
                "skippedCount": int(source.get("skippedCount", 0) or 0),
                "lastIndexedAt": last_indexed_at,
                "lastError": str(source.get("lastError", "") or ""),
            }
        )
    return {
        "sources": summary_sources,
        "sourceCount": len(summary_sources),
        "documentCount": document_count,
        "indexedDocumentCount": indexed_document_count,
        "errorCount": error_count,
        "history": load_knowledge_history(config),
        "collections": sorted(collections),
        "tags": sorted(tags),
        "reindexStatus": {
            "lastReindexAt": last_reindex_at,
            "summary": (
                f"Poslednji reindex: {last_reindex_at}"
                if last_reindex_at
                else "Knowledge još nije reindexovan."
            ),
        },
        "supportedExtensions": sorted(SUPPORTED_EXTENSIONS),
        "answerModes": sorted(ANSWER_MODES),
    }


def add_knowledge_source(
    path: str,
    *,
    collection: str = "",
    tags: list[str] | None = None,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    normalized_path = _normalize_source_path(path)
    if not normalized_path:
        return _error_payload("Knowledge path je prazan.")
    candidate = Path(normalized_path)
    if not candidate.exists():
        return _error_payload(f"Knowledge path ne postoji: {normalized_path}")

    sources = _load_sources(config)
    existing = next((item for item in sources if str(item.get("path", "") or "") == normalized_path), None)
    if existing is not None:
        return {
            "status": "ok",
            "summary": "Knowledge source je već prijavljen.",
            "source": existing,
        }

    source = {
        "id": _build_source_id(normalized_path),
        "path": normalized_path,
        "kind": _detect_source_kind(candidate),
        "collection": str(collection or "").strip(),
        "tags": _normalize_tags(tags or []),
        "addedAt": _now_iso(),
        "documentCount": 0,
        "indexedDocumentCount": 0,
        "errorCount": 0,
        "skippedCount": 0,
        "lastIndexedAt": "",
        "lastError": "",
    }
    sources.append(source)
    _write_sources(config, sources)
    return {
        "status": "ok",
        "summary": "Knowledge source je dodat.",
        "source": source,
    }


def remove_knowledge_source(
    source_id: str,
    *,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    normalized_id = str(source_id or "").strip()
    if not normalized_id:
        return _error_payload("Source ID je prazan.")

    sources = _load_sources(config)
    remaining = [item for item in sources if str(item.get("id", "") or "") != normalized_id]
    if len(remaining) == len(sources):
        return _error_payload(f"Knowledge source nije pronađen: {normalized_id}")

    _write_sources(config, remaining)
    _ensure_index_schema(config)
    with _connect_index(config) as connection:
        connection.execute("DELETE FROM knowledge_documents WHERE source_id = ?", (normalized_id,))
        connection.execute("DELETE FROM knowledge_fts WHERE source_id = ?", (normalized_id,))
        connection.commit()
    return {
        "status": "ok",
        "summary": "Knowledge source je uklonjen.",
        "removedSourceId": normalized_id,
    }


def reindex_knowledge_sources(
    *,
    config: ControlCenterConfig | None = None,
) -> dict[str, Any]:
    config = config or get_config()
    sources = _load_sources(config)
    _ensure_index_schema(config)
    with _connect_index(config) as connection:
        connection.execute("DELETE FROM knowledge_documents")
        connection.execute("DELETE FROM knowledge_fts")
        connection.commit()

        total_documents = 0
        indexed_documents = 0
        updated_sources: list[dict[str, Any]] = []

        for source in sources:
            source_path = Path(str(source.get("path", "") or ""))
            files = _collect_source_files(source_path)
            doc_count = 0
            indexed_count = 0
            skipped_count = 0
            error_count = 0
            last_error = ""

            for file_path in files:
                doc_count += 1
                extracted = _extract_document_text(file_path)
                if extracted is None:
                    skipped_count += 1
                    continue
                if not extracted.strip():
                    skipped_count += 1
                    continue
                try:
                    indexed_document = IndexedDocument(
                        doc_id=_build_document_id(file_path),
                        source_id=str(source.get("id", "") or ""),
                        path=str(file_path.resolve()),
                        name=file_path.name,
                        file_type=file_path.suffix.lower(),
                        size_bytes=int(file_path.stat().st_size),
                        modified_ns=int(file_path.stat().st_mtime_ns),
                        char_count=len(extracted),
                        content=extracted,
                    )
                    _index_document(connection, indexed_document)
                    indexed_count += 1
                except OSError as exc:
                    error_count += 1
                    last_error = str(exc)

            if source_path.exists() and source_path.is_file() and not files:
                last_error = f"Nepodrzan ili prevelik fajl: {source_path.name}"
                error_count += 1

            updated_source = dict(source)
            updated_source.update(
                {
                    "kind": _detect_source_kind(source_path),
                    "documentCount": doc_count,
                    "indexedDocumentCount": indexed_count,
                    "errorCount": error_count,
                    "skippedCount": skipped_count,
                    "lastIndexedAt": _now_iso(),
                    "lastError": last_error,
                }
            )
            total_documents += doc_count
            indexed_documents += indexed_count
            updated_sources.append(updated_source)

        connection.commit()

    _write_sources(config, updated_sources)
    return {
        "status": "ok",
        "summary": f"Knowledge reindex je završen. Indeksirano: {indexed_documents}/{total_documents}.",
        "documentCount": total_documents,
        "indexedDocumentCount": indexed_documents,
        "sources": updated_sources,
    }


def run_knowledge_query(
    query: str,
    *,
    config: ControlCenterConfig | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    record_history: bool = False,
    collection: str = "",
    tag: str = "",
) -> dict[str, Any]:
    config = config or get_config()
    normalized_query = str(query or "").strip()
    if not normalized_query:
        return _error_payload("Knowledge query je prazan.")

    _ensure_index_schema(config)
    rows = _search_documents(
        config,
        normalized_query,
        limit=max(1, limit),
        collection=collection,
        tag=tag,
    )
    payload = {
        "status": "ok",
        "query": normalized_query,
        "collection": str(collection or "").strip(),
        "tag": str(tag or "").strip(),
        "resultCount": len(rows),
        "summary": f"Pronađeno je {len(rows)} dokument pogodaka.",
        "results": rows,
    }
    if record_history:
        _append_knowledge_history(
            config,
            query=normalized_query,
            mode="documents-only",
            document_result_count=len(rows),
            web_result_count=0,
        )
        payload["history"] = load_knowledge_history(config)
    return payload


def answer_with_knowledge(
    query: str,
    *,
    mode: str = "documents-only",
    config: ControlCenterConfig | None = None,
    search_func: Callable[[str], dict[str, Any]] | None = None,
    opener: Callable[..., Any] = urlopen,
    collection: str = "",
    tag: str = "",
) -> dict[str, Any]:
    config = config or get_config()
    normalized_query = str(query or "").strip()
    normalized_mode = str(mode or "documents-only").strip().lower()
    if normalized_mode not in ANSWER_MODES:
        normalized_mode = "documents-only"
    if not normalized_query:
        return _knowledge_answer_error("Knowledge query je prazan.", mode=normalized_mode)

    if normalized_mode == "web-only":
        web_payload = _answer_with_web_only(
            normalized_query,
            config=config,
            opener=opener,
        )
        _append_knowledge_history(
            config,
            query=normalized_query,
            mode=normalized_mode,
            document_result_count=0,
            web_result_count=int(web_payload.get("webResultCount", 0) or 0),
        )
        web_payload["history"] = load_knowledge_history(config)
        return web_payload

    document_payload = run_knowledge_query(
        normalized_query,
        config=config,
        limit=DEFAULT_QUERY_LIMIT,
        collection=collection,
        tag=tag,
    )
    document_results = list(document_payload.get("results", []))
    if normalized_mode == "documents-only" and not document_results:
        return _knowledge_answer_error(
            "Nema dokument pogodaka za traženi upit.",
            mode=normalized_mode,
            document_results=document_results,
        )

    web_payload: dict[str, Any] | None = None
    if normalized_mode == "documents+web":
        search_callable = search_func or (
            lambda next_query: perform_search_query(
                next_query,
                config=config,
                mode_label="manual",
                record_history=False,
            )
        )
        web_payload = search_callable(normalized_query)

    runtime_ready = ensure_runtime_ready(config)
    if runtime_ready.get("status") != "ok":
        return _knowledge_answer_error(
            str(runtime_ready.get("summary", "") or "Runtime nije spreman za Knowledge answer."),
            mode=normalized_mode,
            document_results=document_results,
            web_payload=web_payload,
        )

    runtime_state = load_runtime_state(config)
    settings = load_effective_settings_state(config)
    model_name = str(runtime_state.get("active_model", "") or "local-model")
    runtime_name = str(runtime_state.get("active_runtime", "") or "llama.cpp")
    messages = [
        {
            "role": "system",
            "content": _build_knowledge_system_prompt(document_results, web_payload),
        },
        {
            "role": "user",
            "content": normalized_query,
        },
    ]
    request_payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": int(settings.get("outputTokens", 8192) or 8192),
        "stream": False,
    }
    request = Request(
        f"{str(runtime_state.get('base_url', '')).rstrip('/')}/v1/chat/completions",
        data=json.dumps(request_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=LOCAL_MODEL_ANSWER_TIMEOUT_SECONDS) as response:
            raw_payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        return _knowledge_answer_error(
            f"Lokalni runtime je vratio HTTP {exc.code}.",
            mode=normalized_mode,
            document_results=document_results,
            web_payload=web_payload,
        )
    except (OSError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        return _knowledge_answer_error(
            f"Knowledge answer nije uspeo: {exc}",
            mode=normalized_mode,
            document_results=document_results,
            web_payload=web_payload,
        )

    answer_text = (
        raw_payload.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(raw_payload.get("choices"), list)
        else ""
    )
    usage = raw_payload.get("usage", {}) if isinstance(raw_payload.get("usage"), dict) else {}
    result = {
        "status": "ok",
        "query": normalized_query,
        "mode": normalized_mode,
        "collection": str(collection or "").strip(),
        "tag": str(tag or "").strip(),
        "summary": "Knowledge answer je spreman.",
        "answer": str(answer_text or ""),
        "answerModel": model_name,
        "answerRuntime": runtime_name,
        "usage": {
            "promptTokens": usage.get("prompt_tokens"),
            "completionTokens": usage.get("completion_tokens"),
            "totalTokens": usage.get("total_tokens"),
        },
        "documentResultCount": len(document_results),
        "documentResults": document_results,
        "usedCollections": sorted({str(item.get("collection", "") or "") for item in document_results if str(item.get("collection", "") or "").strip()}),
        "usedTags": sorted({tag_item for item in document_results for tag_item in _normalize_tags(item.get("tags", []))}),
        "citations": _build_document_citations(document_results),
        "webResultCount": int(web_payload.get("resultCount", 0) or 0) if isinstance(web_payload, dict) else 0,
        "webResults": list(web_payload.get("results", [])) if isinstance(web_payload, dict) else [],
    }
    _append_knowledge_history(
        config,
        query=normalized_query,
        mode=normalized_mode,
        document_result_count=len(document_results),
        web_result_count=int(result["webResultCount"]),
    )
    result["history"] = load_knowledge_history(config)
    return result


def load_knowledge_history(
    config: ControlCenterConfig | None = None,
) -> list[dict[str, Any]]:
    config = config or get_config()
    payload = read_json_object(config.knowledge_history_path)
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    history: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        history.append(
            {
                "query": str(item.get("query", "") or ""),
                "mode": str(item.get("mode", "") or ""),
                "documentResultCount": int(item.get("documentResultCount", 0) or 0),
                "webResultCount": int(item.get("webResultCount", 0) or 0),
                "askedAt": str(item.get("askedAt", "") or ""),
            }
        )
    return history[:HISTORY_LIMIT]


def _answer_with_web_only(
    query: str,
    *,
    config: ControlCenterConfig,
    opener: Callable[..., Any],
) -> dict[str, Any]:
    from local_ai_control_center_installer.control_center_backend.services.search_service import (
        answer_with_local_model,
    )

    payload = answer_with_local_model(query, config=config, opener=opener)
    return {
        "status": str(payload.get("status", "") or "error"),
        "query": query,
        "mode": "web-only",
        "collection": "",
        "tag": "",
        "summary": str(payload.get("summary", "") or ""),
        "answer": str(payload.get("answer", "") or ""),
        "answerModel": str(payload.get("answerModel", "") or ""),
        "answerRuntime": str(payload.get("answerRuntime", "") or ""),
        "usage": payload.get("usage", {}),
        "documentResultCount": 0,
        "documentResults": [],
        "usedCollections": [],
        "usedTags": [],
        "citations": [],
        "webResultCount": int(payload.get("resultCount", 0) or 0),
        "webResults": list(payload.get("results", [])) if isinstance(payload.get("results"), list) else [],
    }


def _load_sources(config: ControlCenterConfig) -> list[dict[str, Any]]:
    payload = read_json_object(config.knowledge_sources_path)
    items = payload.get("sources")
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _write_sources(config: ControlCenterConfig, sources: list[dict[str, Any]]) -> None:
    atomic_write_json(config.knowledge_sources_path, {"sources": sources})


def _normalize_source_path(path: str) -> str:
    normalized = str(path or "").strip()
    if not normalized:
        return ""
    return str(Path(normalized).expanduser().resolve())


def _detect_source_kind(path: Path) -> str:
    if path.is_dir():
        return "directory"
    if path.is_file():
        return "file"
    return "missing"


def _build_source_id(path: str) -> str:
    return f"src-{sha1(path.encode('utf-8')).hexdigest()[:12]}"


def _build_document_id(path: Path) -> str:
    return f"doc-{sha1(str(path.resolve()).encode('utf-8')).hexdigest()[:16]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_index_schema(config: ControlCenterConfig) -> None:
    config.knowledge_index_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect_index(config) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                doc_id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                path TEXT NOT NULL,
                name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                modified_ns INTEGER NOT NULL,
                char_count INTEGER NOT NULL,
                extracted_at TEXT NOT NULL,
                content TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                doc_id UNINDEXED,
                source_id UNINDEXED,
                name,
                path,
                content
            )
            """
        )
        connection.commit()


def _connect_index(config: ControlCenterConfig) -> sqlite3.Connection:
    return sqlite3.connect(config.knowledge_index_path)


def _index_document(connection: sqlite3.Connection, document: IndexedDocument) -> None:
    connection.execute(
        """
        INSERT OR REPLACE INTO knowledge_documents (
            doc_id, source_id, path, name, file_type, size_bytes, modified_ns, char_count, extracted_at, content
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.doc_id,
            document.source_id,
            document.path,
            document.name,
            document.file_type,
            document.size_bytes,
            document.modified_ns,
            document.char_count,
            _now_iso(),
            document.content,
        ),
    )
    connection.execute("DELETE FROM knowledge_fts WHERE doc_id = ?", (document.doc_id,))
    connection.execute(
        "INSERT INTO knowledge_fts (doc_id, source_id, name, path, content) VALUES (?, ?, ?, ?, ?)",
        (document.doc_id, document.source_id, document.name, document.path, document.content),
    )


def _collect_source_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path] if _is_supported_file(path) else []
    files: list[Path] = []
    for item in path.rglob("*"):
        if item.is_file() and _is_supported_file(item):
            files.append(item)
    return files


def _is_supported_file(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS and path.stat().st_size <= MAX_INDEX_FILE_SIZE_BYTES


def _extract_document_text(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf_text(path)
    if suffix == ".docx":
        return _extract_docx_text(path)
    if suffix in {".html", ".htm"}:
        return _strip_html(_read_text_file(path))
    if suffix in SUPPORTED_EXTENSIONS:
        return _read_text_file(path)
    return None


def _read_text_file(path: Path) -> str:
    payload = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _strip_html(text: str) -> str:
    without_scripts = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", text)
    without_tags = re.sub(r"(?s)<[^>]+>", " ", without_scripts)
    return re.sub(r"\\s+", " ", html.unescape(without_tags)).strip()


def _extract_docx_text(path: Path) -> str:
    try:
        with ZipFile(path) as archive:
            payload = archive.read("word/document.xml")
    except (BadZipFile, KeyError, OSError):
        return ""
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError:
        return ""
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    chunks = [node.text or "" for node in root.findall(".//w:t", namespace)]
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def _extract_pdf_text(path: Path) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""
    chunks: list[str] = []
    for page in getattr(reader, "pages", []):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text:
            chunks.append(text)
    return re.sub(r"\s+", " ", " ".join(chunks)).strip()


def _search_documents(
    config: ControlCenterConfig,
    query: str,
    *,
    limit: int,
    collection: str = "",
    tag: str = "",
) -> list[dict[str, Any]]:
    source_map = {
        str(source.get("id", "") or ""): source
        for source in _load_sources(config)
        if isinstance(source, dict)
    }
    normalized_collection = str(collection or "").strip().lower()
    normalized_tag = str(tag or "").strip().lower()
    with _connect_index(config) as connection:
        connection.row_factory = sqlite3.Row
        try:
            cursor = connection.execute(
                """
                SELECT
                    d.doc_id,
                    d.source_id,
                    d.path,
                    d.name,
                    d.file_type,
                    d.char_count,
                    d.content,
                    bm25(knowledge_fts) AS score
                FROM knowledge_fts
                JOIN knowledge_documents d ON d.doc_id = knowledge_fts.doc_id
                WHERE knowledge_fts MATCH ?
                ORDER BY score
                LIMIT ?
                """,
                (_normalize_match_query(query), max(limit * 5, limit)),
            )
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor = connection.execute(
                """
                SELECT doc_id, source_id, path, name, file_type, char_count, content, 0.0 AS score
                FROM knowledge_documents
                WHERE lower(name) LIKE ? OR lower(content) LIKE ?
                LIMIT ?
                """,
                (f"%{query.lower()}%", f"%{query.lower()}%", max(limit * 5, limit)),
            )
            rows = cursor.fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        source_id = str(row["source_id"])
        source_payload = source_map.get(source_id, {})
        source_collection = str(source_payload.get("collection", "") or "")
        source_tags = _normalize_tags(source_payload.get("tags", []))
        if normalized_collection and source_collection.lower() != normalized_collection:
            continue
        if normalized_tag and normalized_tag not in {item.lower() for item in source_tags}:
            continue
        content = str(row["content"] or "")
        results.append(
            {
                "docId": str(row["doc_id"]),
                "sourceId": source_id,
                "path": str(row["path"]),
                "name": str(row["name"]),
                "fileType": str(row["file_type"]),
                "collection": source_collection,
                "tags": source_tags,
                "charCount": int(row["char_count"] or 0),
                "score": float(row["score"] or 0.0),
                "snippet": _build_snippet(content, query),
            }
        )
        if len(results) >= limit:
            break
    return results


def _build_document_citations(document_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for index, item in enumerate(document_results, start=1):
        citations.append(
            {
                "index": index,
                "name": str(item.get("name", "") or ""),
                "path": str(item.get("path", "") or ""),
                "collection": str(item.get("collection", "") or ""),
                "tags": _normalize_tags(item.get("tags", [])),
                "snippet": str(item.get("snippet", "") or ""),
            }
        )
    return citations


def _normalize_tags(value: object) -> list[str]:
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_items = [str(part or "").strip() for part in value]
    else:
        raw_items = []
    deduped: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(item)
    return deduped


def _normalize_match_query(query: str) -> str:
    tokens = [token for token in re.split(r"\s+", query.strip()) if token]
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)


def _build_snippet(content: str, query: str) -> str:
    normalized_content = re.sub(r"\s+", " ", content).strip()
    if not normalized_content:
        return ""
    lowered_content = normalized_content.lower()
    lowered_query = str(query or "").strip().lower()
    start = 0
    if lowered_query:
        found_at = lowered_content.find(lowered_query)
        if found_at >= 0:
            start = max(0, found_at - 60)
    snippet = normalized_content[start : start + MAX_SNIPPET_LENGTH]
    return snippet if len(normalized_content) <= MAX_SNIPPET_LENGTH else f"{snippet}..."


def _build_knowledge_system_prompt(
    document_results: list[dict[str, Any]],
    web_payload: dict[str, Any] | None,
) -> str:
    lines = [
        "You are answering with installer-managed local context.",
        "Use local documents first when they are relevant.",
        "If local documents or web results do not contain the answer, say so plainly.",
        "",
        "Local documents:",
    ]
    if document_results:
        for index, item in enumerate(document_results, start=1):
            lines.extend(
                [
                    f"[DOC {index}] {item.get('name', '')}",
                    f"Path: {item.get('path', '')}",
                    f"Snippet: {item.get('snippet', '')}",
                    "",
                ]
            )
    else:
        lines.append("No local document results were found.")
        lines.append("")

    lines.append("Web results:")
    if isinstance(web_payload, dict) and str(web_payload.get("status", "")) == "ok":
        for index, item in enumerate(web_payload.get("results", []), start=1):
            lines.extend(
                [
                    f"[WEB {index}] {item.get('title', '')}",
                    f"URL: {item.get('url', '')}",
                    f"Snippet: {item.get('snippet', '')}",
                    "",
                ]
            )
    else:
        lines.append("No web results were included.")
    return "\n".join(lines).strip()


def _append_knowledge_history(
    config: ControlCenterConfig,
    *,
    query: str,
    mode: str,
    document_result_count: int,
    web_result_count: int,
) -> None:
    items = load_knowledge_history(config)
    next_items = [
        {
            "query": query,
            "mode": mode,
            "documentResultCount": document_result_count,
            "webResultCount": web_result_count,
            "askedAt": _now_iso(),
        },
        *items,
    ][:HISTORY_LIMIT]
    atomic_write_json(config.knowledge_history_path, {"items": next_items})


def _load_index_stats(config: ControlCenterConfig) -> dict[str, Any]:
    _ensure_index_schema(config)
    with _connect_index(config) as connection:
        connection.row_factory = sqlite3.Row
        cursor = connection.execute(
            "SELECT source_id, COUNT(*) AS document_count FROM knowledge_documents GROUP BY source_id"
        )
        per_source = {
            str(row["source_id"]): {
                "documentCount": int(row["document_count"] or 0),
                "indexedDocumentCount": int(row["document_count"] or 0),
            }
            for row in cursor.fetchall()
        }
        total_count = sum(int(item["documentCount"]) for item in per_source.values())
    return {
        "totalCount": total_count,
        "perSource": per_source,
    }


def _error_payload(summary: str) -> dict[str, Any]:
    return {
        "status": "error",
        "summary": summary,
    }


def _knowledge_answer_error(
    summary: str,
    *,
    mode: str,
    document_results: list[dict[str, Any]] | None = None,
    web_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "error",
        "mode": mode,
        "collection": "",
        "tag": "",
        "summary": summary,
        "answer": "",
        "answerModel": "",
        "answerRuntime": "",
        "usage": {
            "promptTokens": None,
            "completionTokens": None,
            "totalTokens": None,
        },
        "documentResultCount": len(document_results or []),
        "documentResults": document_results or [],
        "usedCollections": sorted({str(item.get("collection", "") or "") for item in (document_results or []) if str(item.get("collection", "") or "").strip()}),
        "usedTags": sorted({tag_item for item in (document_results or []) for tag_item in _normalize_tags(item.get("tags", []))}),
        "citations": _build_document_citations(document_results or []),
        "webResultCount": int(web_payload.get("resultCount", 0) or 0) if isinstance(web_payload, dict) else 0,
        "webResults": list(web_payload.get("results", [])) if isinstance(web_payload, dict) else [],
    }
