## Windows force activation warning validation

Version validated: `0.4.30`

### Scope

- Model list now truthfully marks hardware-risky installed models with:
  - `requiresForceConfirmation = true`
  - `activationRiskLevel = warn`
  - `activationRiskSummary`
- `Activate` no longer silently fails for those cases.
- UI now:
  - clearly highlights the risk
  - asks `Da li zelis ipak da pokusas aktivaciju?`
  - only sends `force = true` after explicit user confirmation
- Backend only bypasses the hardware-fit gate when forced.
- Unsupported formats and missing files remain blocked.

### Fresh verification

- `python -m pytest -q`
  - result: `482 passed`
- `python -m build`
  - result: success
- `powershell -ExecutionPolicy Bypass -File packaging/build_windows_installer.ps1 -PythonExe python`
  - result: success
  - artifact: `dist/LocalAIControlCenterSetup-v0.4.30.exe`

### Installer upgrade verification on this machine

- Ran the real installer upgrade over the existing local install root.
- Latest installer report:
  - `product_installation_status = complete`
  - `first_run_status = ready`
  - `control_center_launch_status = ready`
- Windows uninstall registry:
  - `DisplayVersion = 0.4.30`
- Live installed panel:
  - `GET http://127.0.0.1:3210/api/status`
  - `version = 0.4.30`

### UI packaging proof

- Packaged frontend bundle contains:
  - `Ovaj model verovatno ne bi trebalo da radi na ovoj masini.`
  - `Da li zelis ipak da pokusas aktivaciju?`
  - `Ipak pokusaj aktivaciju`

### Notes

- On this machine there was no naturally installed risky model in the live catalog at validation time, so the force-confirmation runtime path was locked primarily by backend tests plus packaged frontend proof.
- This release keeps the existing safe default:
  - no force override for unsupported or missing models
  - force override only for hardware-fit risk cases


