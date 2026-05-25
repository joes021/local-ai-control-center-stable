# Windows Knowledge / Documents Validation

## Scope

Ovaj validation zapis pokriva prvi installer-managed `Knowledge` workspace:

- lokalni source registry
- lokalni SQLite FTS indeks
- `docx` i `pdf` extraction put
- `documents-only`, `documents+web` i `web-only` answer semantiku
- Windows build, installer i lokalni upgrade ove masine na `0.4.24`

## Verifikacija

### 1. Ciljani Knowledge testovi

Komanda:

```powershell
python -m pytest tests\test_control_center_knowledge.py tests\test_control_center_knowledge_routes.py tests\test_control_center_frontend_dist.py -q
```

Ishod:

- `33 passed`

### 2. Puna test baza

Komanda:

```powershell
python -m pytest -q
```

Ishod:

- `466 passed`

### 3. Frontend build i packaged frontend refresh

Komande:

```powershell
npm.cmd install
node .\node_modules\typescript\bin\tsc -b
node .\node_modules\vite\bin\vite.js build
Copy-Item frontend\dist\* src\local_ai_control_center_installer\control_center_backend\frontend_dist -Recurse -Force
```

Ishod:

- novi frontend asseti:
  - `frontend/dist/assets/index-DeNrMP4r.js`
  - `frontend/dist/assets/index-BdnxT14F.css`
- isti build je osvezen i u packaged `frontend_dist`
- `Knowledge` source red sada ima i `Browse` folder picker, ne samo rucni path unos

### 4. Python artefakti

Komanda:

```powershell
python -m build
```

Ishod:

- uspesan `sdist`
- uspesan `wheel`
- nova verzija: `0.4.24`

### 5. Windows installer build

Komanda:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Ishod:

- uspesan build:
  - `dist/LocalAIControlCenterSetup-v0.4.24.exe`

### 6. Lokalni upgrade ove masine

Postupak:

- pokrenut je paketovani installer nad postojecim default install root-om
- izabran je `Upgrade` tok

Live provere:

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter'
```

```powershell
Invoke-RestMethod http://127.0.0.1:3210/api/status
```

Ishod:

- uninstall registry vraca:
  - `DisplayVersion = 0.4.24`
- instalirani panel vraca:
  - `version = 0.4.24`

### 7. Live Knowledge smoke nad instaliranom aplikacijom

Postupak:

- napravljen je privremeni lokalni knowledge folder sa:
  - `notes.md`
- podignut je lokalni mock `SearxNG` server na:
  - `http://127.0.0.1:18080/search`
- kroz instalirani panel privremeno su podeseni:
  - `webSearchMode = on-demand`
  - `webSearchBaseUrl = http://127.0.0.1:18080`
- zatim su pokrenuti:
  - `POST /api/knowledge/sources/add`
  - `POST /api/knowledge/reindex`
  - `POST /api/knowledge/query`
  - `POST /api/knowledge/answer` sa `documents-only`
  - `POST /api/knowledge/answer` sa `documents+web`
- na kraju su source i settings vraceni na prethodno stanje

Ishod:

- source registry je prihvatio privremeni folder
- reindex je vratio:
  - `documentCount = 1`
  - `indexedDocumentCount = 1`
- local query za `knowledge provera` je vratio:
  - `resultCount = 1`
  - prvi pogodak: `notes.md`
- `documents-only` answer je vratio:
  - `status = ok`
  - `answerRuntime = turboquant`
- `documents+web` answer je vratio:
  - `status = ok`
  - `webResultCount = 1`
  - prvi web naslov: `Knowledge web title`
  - upisan Knowledge history zapis sa `mode = documents+web`

## Granice

- Ovo je lokalni full-text/FTS slice, ne semantic search.
- OCR nije deo ovog slice-a.
- Cloud `opencode` provider nije ukljucen u lokalni Knowledge sloj.

## Rezultat

Knowledge vise nije samo ideja za sledeci korak, nego stvarni installer-managed workspace u aplikaciji. Na ovoj masini je potvrdjeno da radi source registry, lokalni indeks, query kroz dokumente i answer tok koji po potrebi spaja lokalne dokumente sa shared web-search slojem.
