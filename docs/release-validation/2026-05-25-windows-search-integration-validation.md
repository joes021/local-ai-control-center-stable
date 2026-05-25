# Windows Search Integration Validation

## Scope

Ovaj validation zapis pokriva shared `SearxNG` search sloj za:

- dedicated `Search` tab u panelu
- lokalni model answer tok
- `OpenCode` `local-lacc` put preko control-center runtime proxy-ja

Takodje pokriva lokalni Windows build, installer i proveru da je ova masina stvarno na `0.4.23`.

## Verifikacija

### 1. Ciljani backend i frontend testovi

Komanda:

```powershell
python -m pytest tests\test_control_center_settings.py tests\test_control_center_search_service.py tests\test_control_center_search_routes.py tests\test_control_center_runtime_proxy.py tests\test_control_center_models_service.py tests\test_opencode_bootstrap.py tests\test_control_center_frontend_dist.py -q
```

Ishod:

- `65 passed`

### 2. Puna test baza

Komanda:

```powershell
python -m pytest -q
```

Ishod:

- `460 passed`

### 3. Frontend build i packaged frontend refresh

Komande:

```powershell
npm.cmd install
node .\node_modules\typescript\bin\tsc -b
node .\node_modules\vite\bin\vite.js build
```

Ishod:

- novi frontend asseti:
  - `frontend/dist/assets/index-C4wfPtGo.js`
  - `frontend/dist/assets/index-BdnxT14F.css`
- isti build je osvezen i u:
  - `src/local_ai_control_center_installer/control_center_backend/frontend_dist`

### 4. Python artefakti

Komanda:

```powershell
python -m build
```

Ishod:

- uspesan `sdist`
- uspesan `wheel`
- nova verzija: `0.4.23`

### 5. Windows installer build

Komanda:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Ishod:

- uspesan build:
  - `dist/LocalAIControlCenterSetup-v0.4.23.exe`

### 6. Live provera lokalne instalacije

Komande:

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter'
```

```powershell
Invoke-RestMethod http://127.0.0.1:3210/api/status
```

```powershell
Get-Content C:\Users\<user>\LocalAIControlCenter\config\opencode\managed-config.json
```

Ishod:

- uninstall registry vraca:
  - `DisplayVersion = 0.4.23`
- instalirani panel vraca:
  - `version = 0.4.23`
- installer-managed `local-lacc` provider pokazuje na proxy:
  - `http://127.0.0.1:3210/api/runtime-proxy/v1`

### 7. Live Search + runtime proxy smoke

Postupak:

- podignut je kratak lokalni mock `SearxNG` server na:
  - `http://127.0.0.1:18080/search`
- kroz instalirani panel privremeno su podeseni:
  - `webSearchMode = on-demand`
  - `webSearchBaseUrl = http://127.0.0.1:18080`
  - `webSearchMaxResults = 2`
  - `webSearchTimeoutSeconds = 10`
  - `webSearchPromptPrefix = /web`
- zatim su pokrenuti:
  - `POST /api/search/query`
  - `POST /api/search/answer`
  - `POST /api/runtime-proxy/v1/chat/completions`
- na kraju su settings vraceni na prethodno stanje:
  - `webSearchMode = off`
  - `webSearchBaseUrl = http://127.0.0.1:8080`

Ishod:

- `Search summary` je vratio:
  - `mode = on-demand`
  - `baseUrl = http://127.0.0.1:18080`
- `POST /api/search/query` je vratio:
  - `status = ok`
  - `resultCount = 2`
  - prvi rezultat:
    - `Mock rezultat za Qwen3.6 web test`
- `POST /api/search/answer` je vratio:
  - `status = ok`
  - `answerRuntime = turboquant`
  - lokalni model je iskoristio sinteticki web context i vratio odgovor
- `POST /api/runtime-proxy/v1/chat/completions` je vratio:
  - `choices = 1`
  - odgovor sazet iz web rezultata za `/web` prompt
- posle vracanja settings-a:
  - `GET /api/search` ponovo vraca `mode = off`
- search history je ostao upisan kao dokaz query i answer toka

## Granice

- Cloud `opencode` provider ostaje dozvoljen izbor modela, ali ne prolazi kroz lokalni search proxy u ovom slice-u.
- Shared search sloj vazi za:
  - dedicated `Search` tab
  - `OpenCode` kada koristi installer-managed `local-lacc` provider

## Rezultat

Search vise nije samo ideja u UI-ju, nego stvarni shared backend sloj sa jednim skupom podesavanja, jednim Search workspace-om i istim web-search augmentation putem za lokalni model i `OpenCode local-lacc`. Ova masina je vec na `0.4.23`, a zivi API smoke je potvrdio da rade i `Search` answer tok i `runtime-proxy` on-demand web search put.
