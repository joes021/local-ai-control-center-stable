from __future__ import annotations

from dataclasses import dataclass
import json
import re
from urllib import parse as urllib_parse
from urllib import request as urllib_request


HF_API = "https://huggingface.co/api/models"


@dataclass
class SourceFetchResult:
    models: list[dict[str, object]]
    errors: list[str]
    warnings: list[str]


def fetch_source_catalog(source: str) -> dict[str, object]:
    normalized = (source or "all").strip().lower()
    if normalized == "all":
        hf = fetch_huggingface_catalog()
        unsloth = fetch_unsloth_catalog()
        return {
            "models": hf.models + unsloth.models,
            "errors": hf.errors + unsloth.errors,
            "warnings": hf.warnings + unsloth.warnings,
        }
    if normalized == "huggingface":
        result = fetch_huggingface_catalog()
        return {"models": result.models, "errors": result.errors, "warnings": result.warnings}
    if normalized == "unsloth":
        result = fetch_unsloth_catalog()
        return {"models": result.models, "errors": result.errors, "warnings": result.warnings}
    return {"models": [], "errors": [f"Nepoznat source za refresh: {source}"], "warnings": []}


def fetch_huggingface_catalog(limit: int = 80) -> SourceFetchResult:
    return _fetch_hf_models(
        {
            "search": "GGUF",
            "limit": str(limit),
            "sort": "lastModified",
            "direction": "-1",
            "full": "true",
            "config": "false",
        },
        source="huggingface",
    )


def fetch_unsloth_catalog(limit: int = 80) -> SourceFetchResult:
    return _fetch_hf_models(
        {
            "author": "unsloth",
            "search": "GGUF",
            "limit": str(limit),
            "sort": "lastModified",
            "direction": "-1",
            "full": "true",
            "config": "false",
        },
        source="unsloth",
    )


def _fetch_hf_models(
    query: dict[str, str],
    *,
    source: str,
    max_files_per_repo: int | None = None,
) -> SourceFetchResult:
    url = f"{HF_API}?{urllib_parse.urlencode(query)}"
    try:
        payload = _read_json(url)
    except Exception as exc:  # noqa: BLE001
        return SourceFetchResult(models=[], errors=[f"{source}: {exc}"], warnings=[])

    models: list[dict[str, object]] = []
    warnings: list[str] = []
    if not isinstance(payload, list):
        return SourceFetchResult(models=[], errors=[f"{source}: neocekivan API odgovor"], warnings=[])

    for repo in payload:
        if not isinstance(repo, dict):
            continue
        repo_id = str(repo.get("id", "") or "")
        siblings = repo.get("siblings") or []
        if not repo_id or not isinstance(siblings, list):
            continue
        sibling_sizes = _read_repo_file_sizes(repo_id)
        gguf_files = [
            sibling
            for sibling in siblings
            if isinstance(sibling, dict) and str(sibling.get("rfilename", "") or "").lower().endswith(".gguf")
        ]
        if not gguf_files:
            continue
        if max_files_per_repo is not None and len(gguf_files) > max_files_per_repo:
            warnings.append(f"{repo_id}: prikazan je samo prvih {max_files_per_repo} GGUF fajlova.")
            gguf_files = gguf_files[:max_files_per_repo]
        for sibling in gguf_files:
            filename = str(sibling.get("rfilename", "") or "")
            size_bytes = sibling.get("size")
            if size_bytes in (None, ""):
                size_bytes = sibling_sizes.get(filename)
            models.append(
                _normalize_model_entry(
                    source=source,
                    repo_id=repo_id,
                    repo=repo,
                    sibling={**sibling, "size": size_bytes},
                    filename=filename,
                )
            )
    return SourceFetchResult(models=models, errors=[], warnings=warnings)


def _normalize_model_entry(
    *,
    source: str,
    repo_id: str,
    repo: dict[str, object],
    sibling: dict[str, object],
    filename: str,
) -> dict[str, object]:
    quantization = _extract_quantization(filename)
    approx_size_gib = _to_gib(sibling.get("size"))
    size_bytes = _to_int(sibling.get("size"))
    family = _guess_family(repo_id, filename)
    mtp_status = "has-mtp" if _has_mtp(repo_id, filename) else ("no-mtp" if source == "unsloth" else "unknown")
    context_window = _guess_context_window(repo_id, filename)
    default_output = 4096 if "35b" in repo_id.lower() or "27b" in repo_id.lower() else 2048
    moe = "a3b" in repo_id.lower() or "moe" in repo_id.lower()
    turboquant_ready = quantization.startswith(("IQ", "Q2", "Q3", "Q4"))
    model_id = f"{source}/{repo_id}/{filename}"
    return {
        "id": model_id,
        "label": filename,
        "family": family,
        "source": source,
        "repoId": repo_id,
        "filename": filename,
        "quantization": quantization,
        "sizeBytes": size_bytes,
        "sizeLabel": f"{approx_size_gib:.1f} GiB" if approx_size_gib is not None else "Unknown",
        "approxSizeGiB": approx_size_gib,
        "publishedAt": str(repo.get("createdAt", "") or ""),
        "lastUpdated": str(repo.get("lastModified", "") or ""),
        "mtpStatus": mtp_status,
        "mtpStatusLabel": _mtp_label(mtp_status),
        "sourceUrl": f"https://huggingface.co/{repo_id}",
        "downloadUrl": f"https://huggingface.co/{repo_id}/resolve/main/{'/'.join(urllib_parse.quote(part) for part in filename.split('/'))}",
        "description": str(repo.get("description", "") or ""),
        "minimumRamGiB": _guess_min_ram(approx_size_gib, moe=moe),
        "minimumVramGiB": _guess_min_vram(approx_size_gib, turboquant_ready=turboquant_ready),
        "recommendedVramGiB": _guess_recommended_vram(approx_size_gib, turboquant_ready=turboquant_ready),
        "contextWindow": context_window,
        "defaultOutputTokens": default_output,
        "moe": moe,
        "turboQuantReady": turboquant_ready,
        "fit": {"status": "nije provereno"},
        "downloads": _to_int(repo.get("downloads")),
        "likes": _to_int(repo.get("likes")),
        "tags": [str(item) for item in (repo.get("tags") or []) if isinstance(item, str)],
    }


def _read_json(url: str) -> object:
    request = urllib_request.Request(url, headers={"User-Agent": "LocalAIControlCenter/2"})
    with urllib_request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _read_repo_file_sizes(repo_id: str) -> dict[str, int]:
    url = f"{HF_API}/{urllib_parse.quote(repo_id, safe='/')}/tree/main?recursive=1"
    try:
        payload = _read_json(url)
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(payload, list):
        return {}
    file_sizes: dict[str, int] = {}
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path", "") or "")
        size = _to_int(entry.get("size"))
        if path and size is not None:
            file_sizes[path] = size
    return file_sizes


def _extract_quantization(filename: str) -> str:
    matches = re.findall(r"(UD-[A-Z0-9_]+|IQ[0-9A-Z_]+|Q[2-9]_[A-Z0-9_]+|Q[2-9][A-Z0-9_]+)", filename, re.IGNORECASE)
    if not matches:
        return "unknown"
    return matches[-1].upper()


def _guess_family(repo_id: str, filename: str) -> str:
    lowered = f"{repo_id} {filename}".lower()
    if "qwen" in lowered:
        return "Qwen"
    if "gemma" in lowered:
        return "Gemma"
    if "llama" in lowered:
        return "Llama"
    if "mistral" in lowered:
        return "Mistral"
    return repo_id.split("/", 1)[0] if "/" in repo_id else repo_id


def _has_mtp(repo_id: str, filename: str) -> bool:
    lowered = f"{repo_id} {filename}".lower()
    return "mtp" in lowered


def _guess_context_window(repo_id: str, filename: str) -> int:
    lowered = f"{repo_id} {filename}".lower()
    if "qwen3.6" in lowered:
        return 262144
    if "qwen3" in lowered:
        return 131072
    return 32768


def _guess_min_ram(size_gib: float | None, *, moe: bool) -> float | None:
    if size_gib is None:
        return None
    base = max(8, round(size_gib * 1.4, 2))
    return round(base + (4 if moe else 0), 2)


def _guess_min_vram(size_gib: float | None, *, turboquant_ready: bool) -> float | None:
    if size_gib is None:
        return None
    multiplier = 0.8 if turboquant_ready else 1.0
    return round(max(4, size_gib * multiplier), 2)


def _guess_recommended_vram(size_gib: float | None, *, turboquant_ready: bool) -> float | None:
    if size_gib is None:
        return None
    multiplier = 1.0 if turboquant_ready else 1.2
    return round(max(6, size_gib * multiplier), 2)


def _to_gib(size_bytes: object) -> float | None:
    try:
        if size_bytes in (None, ""):
            return None
        return round(float(size_bytes) / (1024 ** 3), 2)
    except (TypeError, ValueError):
        return None


def _to_int(value: object) -> int | None:
    try:
        if value in (None, ""):
            return None
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _mtp_label(status: str) -> str:
    return {
        "no-mtp": "bez MTP",
        "has-mtp": "ima MTP",
        "unknown": "nepoznato",
    }.get(status, "nepoznato")
