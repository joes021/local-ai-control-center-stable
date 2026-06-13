# Windows validation - UD-IQ activation truth

Date: 2026-05-25
Version: 0.4.29

## Problem

`Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf` was downloaded and ready, but activation failed with a hard compatibility block claiming roughly `14.6 / 12.0 GiB` VRAM even though the same machine could run the model with TurboQuant under tighter-but-usable conditions.

## Root cause

The compatibility normalization path treated `UD-IQ*` and `UD-Q*` quantizations as if they were not TurboQuant-friendly, only because they carried the `UD-` prefix. That disabled the TurboQuant-aware VRAM heuristic and pushed the model into a false `ne radi` result during activation.

## Fix

- Normalize `UD-` prefixed quantization labels before TurboQuant readiness checks.
- Keep the original label for UI display, but evaluate runtime fit using the de-prefixed quant family key.

## Verification

- `python -m pytest -q` -> `479 passed`
- `python -m build` -> success
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python` -> success
- local machine upgraded to `0.4.29`
- local installed panel:
  - `GET /api/status` -> `version = 0.4.29`
  - `POST /api/models/activate` for `unsloth-unsloth-qwen3-6-35b-a3b-gguf-qwen3-6-35b-a3b-ud-iq2-xxs` -> `status = ok`
  - `GET /api/server/status` -> `activeModel = Qwen3.6-35B-A3B-UD-IQ2_XXS.gguf`, `activeRuntime = turboquant`, `health = ok`
  - `POST /api/compatibility/check` for the same model -> `overallFitStatus = granicno`, `bestRuntime = turboquant`

## Outcome

The model can now be activated on this 12 GiB VRAM machine instead of being falsely blocked as unusable.


