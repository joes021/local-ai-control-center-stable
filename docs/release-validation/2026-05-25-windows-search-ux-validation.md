# Windows Search UX Validation

Date: `2026-05-25`
Version: `0.4.28`
Branch: `codex/panel-integration`

## Goal

Ukloniti zabunu u `Search` tabu tako da korisnik jasno vidi razliku izmedju:

- samih web izvora
- finalnog odgovora iz lokalnog modela

Uz to, web rezultati moraju biti klikabilni.

## Implemented UX Changes

- `Search web` je preimenovan u `Find web sources`
- `Answer with local model` je preimenovan u `Search + answer locally`
- `Enter` u query polju sada pokrece primarnu answer akciju
- sekcija `Search results` je preimenovana u `Web sources`
- kada postoje samo izvori bez odgovora, panel jasno kaze:
  - `Ovo su izvori, ne finalan odgovor.`
- dodat je CTA:
  - `Answer from these results`
- naslovi i URL-ovi rezultata su klikabilni
- `Local answer` sekcija je preimenovana u:
  - `Final answer from local model`

## Files

- `frontend/src/pages/SearchPage.tsx`
- `tests/test_control_center_frontend_dist.py`
- packaged frontend bundle in `src/local_ai_control_center_installer/control_center_backend/frontend_dist`

## Verification

### Targeted frontend bundle test

Command:

```powershell
python -m pytest tests\test_control_center_frontend_dist.py -q
```

Result:

- `29 passed`

### Full test suite

Command:

```powershell
python -m pytest -q
```

Result:

- `477 passed`

### Python package build

Command:

```powershell
python -m build
```

Result:

- success

### Windows installer build

Command:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Result:

- success
- produced:
  - `dist/LocalAIControlCenterSetup-v0.4.28.exe`

## Local Machine Upgrade Validation

Upgrade command:

```powershell
cmd /c "(echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.) | dist\LocalAIControlCenterSetup-v0.4.28.exe"
```

Result:

- installer completed successfully
- local machine upgraded to `0.4.28`

### Registry version

Command:

```powershell
reg query HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter /v DisplayVersion
```

Result:

- `DisplayVersion = 0.4.28`

### Live panel status

Command:

```powershell
Invoke-RestMethod http://127.0.0.1:3210/api/status | ConvertTo-Json -Depth 6
```

Result:

- `version = 0.4.28`
- `health = ok`

### Live served bundle checks

Command:

```powershell
Invoke-WebRequest http://127.0.0.1:3210/assets/index-CCuPLHk4.js -UseBasicParsing
```

Confirmed strings in the served bundle:

- `Find web sources`
- `Search + answer locally`
- `Final answer from local model`
- `Ovo su izvori, ne finalan odgovor.`
- `Open source`
- `Answer from these results`

### Live search smoke

Commands:

```powershell
$body = @{ query = 'stoni tenis srbija' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:3210/api/search/query -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod -Uri http://127.0.0.1:3210/api/search/answer -Method Post -ContentType 'application/json' -Body $body
```

Results:

- `/api/search/query`
  - `status = ok`
  - `resultCount = 5`
- `/api/search/answer`
  - `status = ok`
  - `answerModel = gemma-4-E4B-it-Q4_K_M.gguf`
  - `answerRuntime = turboquant`
  - returned non-empty `answer`

## Final Product Truth

Ovaj release ne menja search backend arhitekturu.

Menja korisnicki tok tako da `Search` tab vise ne izgleda kao da je lista rezultata isto sto i finalan odgovor.


