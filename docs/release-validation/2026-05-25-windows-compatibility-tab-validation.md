# Windows Compatibility Tab Validation

## Scope

Ovaj validation zapis pokriva dedicated `Compatibility` tab, dva polish prolaza oko njegovog UX-a i lokalni Windows upgrade na ovu masinu.

## Verifikacija

### 1. Puna test baza

Komanda:

```powershell
python -m pytest -q
```

Ishod:

- `449 passed`

### 2. Python artefakti

Komanda:

```powershell
python -m build
```

Ishod:

- uspesan `sdist`
- uspesan `wheel`
- nova verzija: `0.4.21`

### 3. Frontend build

Komanda:

```powershell
$node='C:\Users\<user>\.cache\<bundled-runtime-cache>\codex-primary-runtime\dependencies\node\bin\node.exe'
& $node frontend/node_modules/typescript/bin/tsc -b frontend
Push-Location frontend
& $node node_modules/vite/bin/vite.js build
Pop-Location
```

Ishod:

- novi frontend asseti:
  - `frontend/dist/assets/index-DWZvgWTk.js`
  - `frontend/dist/assets/index-BdnxT14F.css`

### 4. Packaged frontend provera

Komanda:

```powershell
python -m pytest tests/test_control_center_frontend_dist.py -q
```

Ishod:

- `25 passed`

### 5. Windows installer build

Komanda:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Ishod:

- uspesan build:
  - `dist/LocalAIControlCenterSetup-v0.4.21.exe`

### 6. Lokalni upgrade ove masine

Komanda:

```powershell
cmd /c "(echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.& echo.) | dist\LocalAIControlCenterSetup-v0.4.21.exe"
```

Ishod:

- uspesan upgrade install root-a:
  - `C:\Users\<user>\LocalAIControlCenter`
- installer report:
  - `C:\Users\<user>\AppData\Local\Temp\LocalAIControlCenterInstaller\runs\2026-05-25T01-54-35+00-00\install-report.json`
- ključni statusi:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`
  - `runtime_status = ready`
  - `turboquant_status = ready`
  - `first_run_status = ready`

### 7. Live provera instalirane aplikacije

Komande:

```powershell
Invoke-RestMethod http://127.0.0.1:3210/api/status
```

```powershell
Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\LocalAIControlCenter'
```

```powershell
@'
import re
import urllib.request
html = urllib.request.urlopen("http://127.0.0.1:3210/").read().decode("utf-8")
print(html)
'@ | python -
```

```powershell
@'
import urllib.request
text = urllib.request.urlopen("http://127.0.0.1:3210/assets/index-DWZvgWTk.js").read().decode("utf-8")
for token in ["Compatibility", "System snapshot", "Remote catalog", "Open Browser", "Open Models"]:
    print(f"{token}={token in text}")
'@ | python -
```

Ishod:

- `api/status` vraca:
  - `version = 0.4.21`
  - `health = ok`
  - `runtimeLiveStatus = started`
  - `activeRuntimeLabel = TurboQuant`
- uninstall registry vraca:
  - `DisplayVersion = 0.4.21`
- instalirani panel servira:
  - `index-DWZvgWTk.js`
  - `index-BdnxT14F.css`
- bundle sadrzi dedicated Compatibility tab copy:
  - `Compatibility`
  - `System snapshot`
  - `Remote catalog`
  - `Open Browser`
  - `Open Models`

## Rezultat

Compatibility calculator vise nije sakriven samo iza modala. U `0.4.21` postoji dedicated `Compatibility` tab, ostaju i brzi modal ulazi iz `Models` i `Browser`, a ova masina je uspesno podignuta na novu verziju i zivi panel servira novi build.


