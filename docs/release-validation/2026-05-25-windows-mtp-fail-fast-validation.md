# Windows MTP Fail-Fast Validation

## Scope

Ovaj validation zapis pokriva hardverski-aware fail-fast za model activation/start put, lokalni upgrade ove masine na `0.4.22` i remote proveru na `192.0.2.10`.

## Verifikacija

### 1. Ciljani testovi za novi guard

Komanda:

```powershell
python -m pytest tests/test_control_center_compatibility.py tests/test_control_center_models_service.py tests/test_control_center_server.py -k "installed_size_when_approx_size_is_missing or hardware_incompatible_model_before_state_change or hardware_incompatible_active_model_before_launch" -q
```

Ishod:

- `3 passed`

### 2. Sire relevantne backend provere

Komanda:

```powershell
python -m pytest tests/test_control_center_compatibility.py tests/test_control_center_models_service.py tests/test_control_center_server.py -q
```

Ishod:

- `33 passed`

### 3. Puna test baza

Komanda:

```powershell
python -m pytest -q
```

Ishod:

- `452 passed`

### 4. Python artefakti

Komanda:

```powershell
python -m build
```

Ishod:

- uspesan `sdist`
- uspesan `wheel`
- nova verzija: `0.4.22`

### 5. Windows installer build

Komanda:

```powershell
powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python
```

Ishod:

- uspesan build:
  - `dist/LocalAIControlCenterSetup-v0.4.22.exe`

### 6. Lokalni upgrade ove masine

Komanda:

```powershell
@'











'@ | & "dist\LocalAIControlCenterSetup-v0.4.22.exe"
```

Ishod:

- uspesan upgrade install root-a:
  - `C:\Users\<user>\LocalAIControlCenter`
- uninstall registry:
  - `DisplayVersion = 0.4.22`
- zivi panel:
  - `http://127.0.0.1:3210/api/status`
  - `version = 0.4.22`
  - `health = ok`

### 7. Remote upgrade na 192.0.2.10

Komande:

```powershell
scp dist\LocalAIControlCenterSetup-v0.4.22.exe operator@192.0.2.10:C:/Users/<remote-user>/Downloads/LocalAIControlCenterSetup-v0.4.22.exe
```

```powershell
@'
import subprocess, sys
cmd = [r"C:\Windows\System32\OpenSSH\ssh.exe", "operator@192.0.2.10", r"C:\Users\<remote-user>\Downloads\LocalAIControlCenterSetup-v0.4.22.exe"]
payload = "\n" * 20
proc = subprocess.run(cmd, input=payload, text=True, timeout=1800)
sys.exit(proc.returncode)
'@ | python -
```

Ishod:

- installer je prosao do kraja
- remote uninstall registry vraca:
  - `DisplayVersion = 0.4.22`
- remote installer zavrsni status:
  - `product_installation_status = complete`
  - `control_center_launch_status = ready`

### 8. Remote MTP fail-fast smoke

Okruzenje:

- host: `operator@192.0.2.10`
- GPU: `GTX 1060 6 GB`
- problem model:
  - `unsloth-unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-iq2-xxs`

Komanda:

```powershell
$payload = @{ modelId = "unsloth-unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-iq2-xxs" } | ConvertTo-Json -Compress
Invoke-RestMethod http://127.0.0.1:3210/api/models/activate -Method Post -ContentType application/json -Body $payload
Invoke-RestMethod http://127.0.0.1:3210/api/status
```

Ishod:

- activation vise ne prolazi lazno
- vraceni status:
  - `activate.status = error`
- summary sada odmah kaze da model verovatno nije upotrebljiv na toj masini bez ozbiljnih kompromisa
- aktivni model ostaje:
  - `gemma-4-E4B-it-Q4_K_M.gguf`
- runtime vise ne odlazi u lazni `warming`

## Rezultat

U `0.4.22` model activation i server start vise ne dozvoljavaju da hardverski neizvodljiv model udje u lazni "spreman sam" tok. Na slabijoj remote masini problem MTP model sada biva odbijen odmah, sa poštenom porukom i bez ostavljanja runtime-a u `warming`.


